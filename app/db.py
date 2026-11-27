# path: app/db.py
"""PostgreSQL cho toàn hệ thống + lớp tương thích để code viết kiểu sqlite3 chạy được trên Postgres.

Mỗi "database" cũ (đường dẫn file .db) được ánh xạ thành 1 SCHEMA trong 1 database Postgres:
    thienla.db           → public         (dữ liệu nghiệp vụ, cảnh báo, app khách)
    graph.db             → graph          (đồ thị bằng chứng + kết quả AI)
    *_cache*.db          → ai_cache       (bộ nhớ đệm phản hồi AI)
    file trong thư mục tạm của hệ điều hành (test) → database <tên>_test, schema riêng cho từng đường dẫn,
                            tự xoá khi tiến trình kết thúc — test không bao giờ đụng dữ liệu demo.

Kết nối trả về (`Conn`) giữ hành vi sqlite3 mà code cũ dựa vào:
    • dòng đọc được cả row[0] lẫn row["cột"], dict(row) ra đúng tên cột;
    • `with conn:` = 1 GIAO DỊCH (commit/rollback) — KHÔNG đóng kết nối (khác psycopg);
    • tham số `?`; INSERT OR REPLACE / INSERT OR IGNORE → ON CONFLICT (tự tra khoá chính);
    • executescript / executemany / commit / close.
Chỗ đặc thù hẳn của SQLite (sqlite_master, PRAGMA table_info, json_extract) được sửa thẳng trong code, không giả lập.
"""
import atexit
import hashlib
import os
import re
import tempfile
import threading
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import RowMaker

ROOT = Path(__file__).resolve().parent.parent
Error = psycopg.Error
IntegrityError = psycopg.IntegrityError


def load_env(path=ROOT / ".env"):
    """Nạp .env nhưng KHÔNG ghi đè biến môi trường đã đặt."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()


def dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Thiếu DATABASE_URL — chép .env.example thành .env rồi `docker compose up -d db`")
    return url


# ── ánh xạ đường dẫn cũ → (dsn, schema) ─────────────────────────────────────────────────
_TMP = Path(tempfile.gettempdir()).resolve()
_created_temp: set = set()
_lock = threading.Lock()


def _test_dsn() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    base = dsn()
    name = base.rsplit("/", 1)[1].split("?")[0]
    test_url = base[: base.rfind("/") + 1] + name + "_test"
    with _lock:
        if not getattr(_test_dsn, "ready", False):
            with psycopg.connect(base, autocommit=True) as c:
                if not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name + "_test",)).fetchone():
                    c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name + "_test")))
            _test_dsn.ready = True
    return test_url


def target(database) -> tuple[str, str]:
    """(dsn, schema) cho 1 'database' kiểu cũ (đường dẫn hoặc tên schema)."""
    raw = str(database)
    if "/" not in raw and "\\" not in raw and not raw.endswith(".db"):
        return dsn(), raw                                        # đã là tên schema
    path = Path(raw).resolve()
    if _TMP in path.parents:                                     # test: database riêng, schema theo đường dẫn
        return _test_dsn(), "t_" + hashlib.sha1(str(path).encode()).hexdigest()[:16]
    canonical = {ROOT / "thienla.db": "public", ROOT / "data" / "graph.db": "graph", ROOT / "data" / "ai-cache.db": "ai_cache"}
    if path in canonical:
        return dsn(), canonical[path]
    # đường dẫn khác (vd mỗi lần chạy AI pipeline có graph.db/cache.db riêng) → schema riêng theo đường dẫn, không đè nhau
    stem = re.sub(r"[^a-z0-9_]", "_", path.stem.lower())[:20] or "db"
    return dsn(), f"{stem}_{hashlib.sha1(str(path).encode()).hexdigest()[:10]}"


def exists(database) -> bool:
    """Thay cho Path(...).is_file(): schema có tồn tại và có ít nhất 1 bảng."""
    url, schema = target(database)
    try:
        with psycopg.connect(url, autocommit=True) as c:
            return bool(c.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=%s LIMIT 1", (schema,)).fetchone())
    except psycopg.OperationalError:
        return False


def drop(database) -> None:
    url, schema = target(database)
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


def _cleanup_temp():
    for url, schema in list(_created_temp):
        try:
            with psycopg.connect(url, autocommit=True) as c:
                c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        except Exception:
            pass


atexit.register(_cleanup_temp)


# ── dòng kiểu sqlite3.Row: row[0], row["cột"], dict(row) ──────────────────────────────────
class Row(tuple):
    __slots__ = ()
    _cols: tuple = ()

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return tuple.__getitem__(self, self._cols.index(key))
            except ValueError:
                raise IndexError(f"No item with that key: {key}") from None
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._cols)


def _row_factory(cursor) -> RowMaker:
    cols = tuple(d.name for d in cursor.description) if cursor.description else ()
    cls = type("Row", (Row,), {"_cols": cols, "__slots__": ()})
    return lambda values: cls(values)


# ── dịch câu lệnh ─────────────────────────────────────────────────────────────────────
_INSERT_OR = re.compile(r"^\s*INSERT\s+OR\s+(REPLACE|IGNORE)\s+INTO\s+([A-Za-z_][\w.]*)\s*(\([^)]*\))?\s*", re.I)


def _placeholders(text: str) -> str:
    """'?' → '%s' và '%' → '%%' — bỏ qua phần nằm trong chuỗi '...'."""
    out, quoted = [], False
    for ch in text:
        if ch == "'":
            quoted = not quoted
            out.append(ch)
        elif ch == "%":
            out.append("%%")
        elif ch == "?" and not quoted:
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


class Conn:
    def __init__(self, url: str, schema: str, *, read_only=False, autocommit=False):
        self.schema = schema
        self.raw = psycopg.connect(url, autocommit=True, row_factory=_row_factory)
        self.raw.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))) if not read_only else None
        self.raw.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        if read_only:
            self.raw.execute("SET default_transaction_read_only = on")
        self.raw.autocommit = autocommit
        self._pk_cache: dict = {}
        self.row_factory = None   # code cũ gán sqlite3.Row vào đây — bỏ qua, dòng luôn là Row

    # sqlite3 API -------------------------------------------------------------------
    def execute(self, query: str, params=()):
        query, params = self._translate(query, params)
        return self.raw.execute(query, params)

    def executemany(self, query: str, seq):
        seq = list(seq)
        if not seq:
            return None
        query, _ = self._translate(query, seq[0])
        with self.raw.cursor() as cur:
            cur.executemany(query, seq)
        return None

    def executescript(self, script: str):
        """Giống sqlite3: chạy nhiều câu rồi COMMIT ngay (tạo bảng có hiệu lực tức thì cho mọi kết nối khác)."""
        if script.strip():
            self.raw.execute(script)   # nhiều câu, không tham số — Postgres chạy được trong 1 lần
            self.commit()

    def commit(self):
        if not self.raw.autocommit:
            self.raw.commit()

    def rollback(self):
        if not self.raw.autocommit:
            self.raw.rollback()

    def close(self):
        self.raw.close()

    def cursor(self):
        return self.raw.cursor()

    def __enter__(self):          # giống sqlite3: 1 khối = 1 giao dịch, KHÔNG đóng kết nối
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        return False

    # dịch ---------------------------------------------------------------------------
    def _primary_key(self, table: str) -> list[str]:
        if table not in self._pk_cache:
            rows = self.raw.execute(
                "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) "
                "WHERE i.indrelid = to_regclass(%s) AND i.indisprimary ORDER BY a.attnum", (table,)).fetchall()
            cols = self.raw.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() "
                                    "AND table_name=%s ORDER BY ordinal_position", (table.split(".")[-1],)).fetchall()
            self._pk_cache[table] = ([r[0] for r in rows], [r[0] for r in cols])
        return self._pk_cache[table]

    def _translate(self, query: str, params):
        m = _INSERT_OR.match(query)
        if m:
            mode, table, collist = m.group(1).upper(), m.group(2), m.group(3)
            rest = query[m.end():]
            head = f"INSERT INTO {table} {collist or ''} "
            if mode == "IGNORE":
                query = head + rest.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
            else:
                pk, cols = self._primary_key(table)
                if not pk:
                    raise psycopg.ProgrammingError(f"INSERT OR REPLACE cần khoá chính: {table}")
                target_cols = [c.strip() for c in collist.strip("()").split(",")] if collist else cols
                updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in target_cols if c not in pk)
                query = head + rest.rstrip().rstrip(";") + f" ON CONFLICT ({', '.join(pk)}) " + \
                        (f"DO UPDATE SET {updates}" if updates else "DO NOTHING")
        if isinstance(params, dict):
            return re.sub(r":(\w+)", r"%(\1)s", query.replace("%", "%%")), params
        return _placeholders(query), tuple(params) if params is not None else ()


def connect(database="thienla.db", *, read_only=False, autocommit=False) -> Conn:
    url, schema = target(database)
    if read_only and not exists(database):
        raise FileNotFoundError(database)
    # chỉ đọc → tự commit: kết nối sống lâu trong server không giữ mãi 1 ảnh chụp cũ, luôn thấy dữ liệu mới
    conn = Conn(url, schema, read_only=read_only, autocommit=autocommit or read_only)
    if url != dsn():
        _created_temp.add((url, schema))
    return conn


def has_table(conn: Conn, table: str) -> bool:
    return bool(conn.raw.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=%s",
                                 (table,)).fetchone())


def table_columns(conn: Conn, table: str) -> list[str]:
    return [r[0] for r in conn.raw.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() "
                                           "AND table_name=%s ORDER BY ordinal_position", (table,)).fetchall()]


def pg(query: str) -> str:
    """'?' → '%s' (dùng cho code gọi psycopg trực tiếp)."""
    return _placeholders(query)
