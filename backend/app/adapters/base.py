from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from app.storage.cache import get_cache, set_cache


@dataclass
class AdapterResult:
    records: list[dict[str, Any]]
    status: str = "complete"
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dataset_updated_at: datetime | None = None
    warnings: list[str] = field(default_factory=list)
    cached: bool = False


class SourceUnavailable(RuntimeError):
    pass


async def cached_json(url: str, params: dict[str, str] | None = None) -> tuple[Any, bool, datetime]:
    encoded = httpx.QueryParams(params or {})
    cache_key = hashlib.sha256(f"{url}?{encoded}".encode()).hexdigest()
    cached = get_cache(cache_key)
    if cached is not None:
        stored = cached.pop("_cache_stored_at", None) if isinstance(cached, dict) else None
        payload = cached.get("payload") if isinstance(cached, dict) and "payload" in cached else cached
        retrieved = datetime.fromisoformat(stored) if stored else datetime.now(timezone.utc)
        return payload, True, retrieved

    headers = {"User-Agent": "NYC-Building-X-Ray/1.0"}
    app_token = __import__("os").getenv("NYC_OPEN_DATA_APP_TOKEN")
    if app_token and "data.cityofnewyork.us" in url:
        headers["X-App-Token"] = app_token
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), headers=headers) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                set_cache(cache_key, {"payload": payload})
                return payload, False, datetime.now(timezone.utc)
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt == 0:
                await asyncio.sleep(0.2)
    raise SourceUnavailable(str(last_error))


async def dataset_updated(dataset_id: str) -> datetime | None:
    try:
        payload, _, _ = await cached_json(f"https://data.cityofnewyork.us/api/views/{dataset_id}")
        epoch = payload.get("rowsUpdatedAt")
        return datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else None
    except SourceUnavailable:
        return None
