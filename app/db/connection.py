import re
import psycopg
from psycopg import sql
from .rows import _row_factory
from .statements import _INSERT_OR, _placeholders
from .config import dsn
from .routing import target, _created_temp
from .schema import exists


class Conn:
    def __init__(self, url: str, schema: str, *, read_only=False, autocommit=False):
        self.schema = schema
        self.raw = psycopg.connect(url, autocommit=True, row_factory=_row_factory)
        self.raw.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
        ) if not read_only else None
        self.raw.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        if read_only:
            self.raw.execute("SET default_transaction_read_only = on")
        self.raw.autocommit = autocommit
        self._pk_cache: dict = {}
        self.row_factory = None

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
            self.raw.execute(script)
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        return False

    def _primary_key(self, table: str) -> list[str]:
        if table not in self._pk_cache:
            rows = self.raw.execute(
                "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) WHERE i.indrelid = to_regclass(%s) AND i.indisprimary ORDER BY a.attnum",
                (table,),
            ).fetchall()
            cols = self.raw.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
                (table.split(".")[-1],),
            ).fetchall()
            self._pk_cache[table] = ([r[0] for r in rows], [r[0] for r in cols])
        return self._pk_cache[table]

    def _translate(self, query: str, params):
        m = _INSERT_OR.match(query)
        if m:
            mode, table, collist = (m.group(1).upper(), m.group(2), m.group(3))
            rest = query[m.end() :]
            head = f"INSERT INTO {table} {collist or ''} "
            if mode == "IGNORE":
                query = head + rest.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
            else:
                pk, cols = self._primary_key(table)
                if not pk:
                    raise psycopg.ProgrammingError(f"INSERT OR REPLACE cần khoá chính: {table}")
                target_cols = (
                    [c.strip() for c in collist.strip("()").split(",")] if collist else cols
                )
                updates = ", ".join((f"{c} = EXCLUDED.{c}" for c in target_cols if c not in pk))
                query = (
                    head
                    + rest.rstrip().rstrip(";")
                    + f" ON CONFLICT ({', '.join(pk)}) "
                    + (f"DO UPDATE SET {updates}" if updates else "DO NOTHING")
                )
        if isinstance(params, dict):
            return (re.sub(":(\\w+)", "%(\\1)s", query.replace("%", "%%")), params)
        return (_placeholders(query), tuple(params) if params is not None else ())


def connect(database="thienla.db", *, read_only=False, autocommit=False) -> Conn:
    url, schema = target(database)
    if read_only and (not exists(database)):
        raise FileNotFoundError(database)
    conn = Conn(url, schema, read_only=read_only, autocommit=autocommit or read_only)
    if url != dsn():
        _created_temp.add((url, schema))
    return conn
