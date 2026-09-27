from __future__ import annotations

from datetime import date

from app.adapters.base import AdapterResult, cached_json, dataset_updated
from app.models import Building


DATASET_ID = "wvxf-dwi5"
DATASET_URL = "https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Violations/wvxf-dwi5"
API_URL = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"


async def fetch(building: Building, _start: date, _end: date) -> AdapterResult:
    if not building.bin:
        return AdapterResult([], "unavailable", warnings=["No BIN was available for building-level HPD matching."])
    fields = "violationid,buildingid,boroid,boro,housenumber,streetname,story,class,inspectiondate,approveddate,novdescription,currentstatus,currentstatusdate,violationstatus,bin,bbl"
    payload, cached, retrieved = await cached_json(
        API_URL,
        {"$select": fields, "$where": f"bin='{building.bin}'", "$order": "violationid ASC", "$limit": "3000"},
    )
    status = "incomplete" if len(payload) >= 3000 else "complete"
    warnings = ["The 3,000-record retrieval limit was reached."] if status == "incomplete" else []
    return AdapterResult(payload, status, retrieved, await dataset_updated(DATASET_ID), warnings, cached)
