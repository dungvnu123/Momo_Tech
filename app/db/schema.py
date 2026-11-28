from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import Conn
import psycopg
from psycopg import sql
from .routing import target


def exists(database) -> bool:
    """Thay cho Path(...).is_file(): schema có tồn tại và có ít nhất 1 bảng."""
    url, schema = target(database)
    try:
        with psycopg.connect(url, autocommit=True) as c:
            return bool(
                c.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema=%s LIMIT 1",
                    (schema,),
                ).fetchone()
            )
    except psycopg.OperationalError:
        return False


def drop(database) -> None:
    url, schema = target(database)
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


def has_table(conn: Conn, table: str) -> bool:
    return bool(
        conn.raw.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=%s",
            (table,),
        ).fetchone()
    )


def table_columns(conn: Conn, table: str) -> list[str]:
    return [
        r[0]
        for r in conn.raw.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
            (table,),
        ).fetchall()
    ]
