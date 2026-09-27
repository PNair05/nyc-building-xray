from __future__ import annotations

from datetime import date

from app.adapters.base import AdapterResult, cached_json, dataset_updated
from app.models import Building
from app.services.matching import same_building_address


DATASET_ID = "erm2-nwe9"
DATASET_URL = "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9"
API_URL = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"


async def fetch(building: Building, start: date, end: date) -> AdapterResult:
    if not building.bbl:
        return AdapterResult([], "unavailable", warnings=["No BBL was available for a bounded 311 query."])
    selected = "unique_key,created_date,closed_date,agency,complaint_type,descriptor,status,resolution_description,incident_address,borough,bbl"
    where = (
        f"bbl='{building.bbl}' AND created_date >= '{start.isoformat()}T00:00:00' "
        f"AND created_date < '{end.isoformat()}T00:00:00'"
    )
    payload, cached, retrieved = await cached_json(
        API_URL,
        {"$select": selected, "$where": where, "$order": "created_date ASC, unique_key ASC", "$limit": "3000"},
    )
    # BBL identifies a lot, so corroborate the exact building address before attribution.
    records = [row for row in payload if same_building_address(row.get("incident_address"), building.address)]
    warnings = []
    if len(payload) != len(records):
        warnings.append(f"Excluded {len(payload) - len(records)} lot-level records whose address did not match this building.")
    status = "incomplete" if len(payload) >= 3000 else "complete"
    if status == "incomplete":
        warnings.append("The 3,000-record retrieval limit was reached.")
    return AdapterResult(records, status, retrieved, await dataset_updated(DATASET_ID), warnings, cached)
