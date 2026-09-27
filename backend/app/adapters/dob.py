from __future__ import annotations

from datetime import date, datetime

from app.adapters.base import AdapterResult, cached_json, dataset_updated
from app.models import Building


DATASET_ID = "eabe-havv"
DATASET_URL = "https://data.cityofnewyork.us/Housing-Development/DOB-Complaints-Received/eabe-havv"
API_URL = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"


async def fetch(building: Building, start: date, end: date) -> AdapterResult:
    if not building.bin:
        return AdapterResult([], "unavailable", warnings=["No BIN was available for building-level DOB matching."])
    fields = "complaint_number,status,date_entered,house_number,house_street,zip_code,bin,complaint_category,unit,disposition_date,disposition_code,inspection_date"
    payload, cached, retrieved = await cached_json(
        API_URL,
        {"$select": fields, "$where": f"bin='{building.bin}'", "$order": "complaint_number ASC", "$limit": "3000"},
    )
    records = []
    bad_dates = 0
    for row in payload:
        try:
            entered = datetime.strptime(row["date_entered"], "%m/%d/%Y").date()
        except (KeyError, ValueError):
            bad_dates += 1
            continue
        if start <= entered < end:
            records.append(row)
    status = "incomplete" if len(payload) >= 3000 else "complete"
    warnings = []
    if bad_dates:
        warnings.append(f"Excluded {bad_dates} DOB records with missing or invalid dates.")
    if status == "incomplete":
        warnings.append("The 3,000-record retrieval limit was reached before application-side date filtering.")
    return AdapterResult(records, status, retrieved, await dataset_updated(DATASET_ID), warnings, cached)
