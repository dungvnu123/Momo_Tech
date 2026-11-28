import atexit
import hashlib
import os
import re
import tempfile
import threading
from pathlib import Path
import psycopg
from psycopg import sql
from .config import ROOT, dsn

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
                if not c.execute(
                    "SELECT 1 FROM pg_database WHERE datname=%s", (name + "_test",)
                ).fetchone():
                    c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name + "_test")))
            _test_dsn.ready = True
    return test_url


def target(database) -> tuple[str, str]:
    """(dsn, schema) cho 1 'database' kiểu cũ (đường dẫn hoặc tên schema)."""
    raw = str(database)
    if "/" not in raw and "\\" not in raw and (not raw.endswith(".db")):
        return (dsn(), raw)
    path = Path(raw).resolve()
    if _TMP in path.parents:
        return (_test_dsn(), "t_" + hashlib.sha1(str(path).encode()).hexdigest()[:16])
    canonical = {
        ROOT / "thienla.db": "public",
        ROOT / "data" / "graph.db": "graph",
        ROOT / "data" / "ai-cache.db": "ai_cache",
    }
    if path in canonical:
        return (dsn(), canonical[path])
    stem = re.sub("[^a-z0-9_]", "_", path.stem.lower())[:20] or "db"
    return (dsn(), f"{stem}_{hashlib.sha1(str(path).encode()).hexdigest()[:10]}")


def _cleanup_temp():
    for url, schema in list(_created_temp):
        try:
            with psycopg.connect(url, autocommit=True) as c:
                c.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
                )
        except Exception:
            pass


atexit.register(_cleanup_temp)
