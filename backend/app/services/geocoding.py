from __future__ import annotations

import hashlib
from typing import Any

from app.adapters.base import cached_json
from app.models import Building
from app.storage.cache import save_building


BOROUGHS = {"MANHATTAN", "BRONX", "BROOKLYN", "QUEENS", "STATEN ISLAND"}


async def search_live(query: str, borough: str | None = None) -> list[Building]:
    text = f"{query}, {borough}" if borough else query
    payload, _, _ = await cached_json(
        "https://geosearch.planninglabs.nyc/v2/search", {"text": text, "size": "6"}
    )
    results: list[Building] = []
    for feature in payload.get("features", []):
        properties: dict[str, Any] = feature.get("properties", {})
        found_borough = str(properties.get("borough", "")).upper()
        if found_borough not in BOROUGHS:
            continue
        if borough and found_borough != borough.upper():
            continue
        pad = properties.get("addendum", {}).get("pad", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [None, None])
        address = properties.get("name") or properties.get("label", "Unknown address").split(",")[0]
        identity = f"{pad.get('bin')}:{pad.get('bbl')}:{address}:{found_borough}"
        building_id = "live-" + hashlib.sha1(identity.encode()).hexdigest()[:14]
        confidence = float(properties.get("confidence", 0))
        match_type = properties.get("match_type", "unknown")
        building = Building(
            id=building_id,
            address=address,
            borough=found_borough.title(),
            longitude=coordinates[0],
            latitude=coordinates[1],
            bin=str(pad["bin"]) if pad.get("bin") else None,
            bbl=str(pad["bbl"]) if pad.get("bbl") else None,
            source_ids={"geosearch": str(properties.get("gid", ""))},
            match_method=f"NYC GeoSearch {match_type}",
            confidence=confidence,
            ambiguity="Confirm this is the intended building." if confidence < 0.9 else None,
        )
        save_building(building_id, building.model_dump())
        results.append(building)
    return results
