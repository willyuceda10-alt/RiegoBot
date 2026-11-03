from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from .settings import load_settings


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    settings = load_settings()
    if not settings.database_url:
        raise RuntimeError("RIEGOBOT_DATABASE_URL is not configured.")

    connection = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        yield connection
    finally:
        connection.close()


def database_health() -> dict[str, object]:
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT current_database() AS database_name, now() AS database_time"
            ).fetchone()
        return {
            "configured": True,
            "reachable": True,
            "databaseName": row["database_name"],
            "databaseTime": row["database_time"].isoformat(),
        }
    except Exception as exc:
        return {
            "configured": bool(load_settings().database_url),
            "reachable": False,
            "error": str(exc),
        }
