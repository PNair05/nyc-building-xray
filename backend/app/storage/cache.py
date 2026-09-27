from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_configured_db_path = os.getenv("XRAY_DB_PATH")
DB_PATH = Path(_configured_db_path) if _configured_db_path else Path(__file__).with_name("xray.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS cache (cache_key TEXT PRIMARY KEY, value TEXT NOT NULL, stored_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS buildings (building_id TEXT PRIMARY KEY, value TEXT NOT NULL, stored_at TEXT NOT NULL)"
    )
    return connection


def get_cache(key: str, ttl_seconds: int | None = None) -> dict[str, Any] | list[Any] | None:
    ttl = ttl_seconds or int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    with _connect() as connection:
        row = connection.execute("SELECT value, stored_at FROM cache WHERE cache_key = ?", (key,)).fetchone()
    if not row:
        return None
    stored = datetime.fromisoformat(row[1])
    if datetime.now(timezone.utc) - stored > timedelta(seconds=ttl):
        return None
    value = json.loads(row[0])
    if isinstance(value, dict):
        value["_cache_stored_at"] = row[1]
    return value


def set_cache(key: str, value: dict[str, Any] | list[Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO cache(cache_key, value, stored_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), now),
        )


def save_building(building_id: str, value: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO buildings(building_id, value, stored_at) VALUES (?, ?, ?)",
            (building_id, json.dumps(value), datetime.now(timezone.utc).isoformat()),
        )


def load_building(building_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT value FROM buildings WHERE building_id = ?", (building_id,)).fetchone()
    return json.loads(row[0]) if row else None
