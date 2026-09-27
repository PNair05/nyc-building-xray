from __future__ import annotations

import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.adapters import dob, hpd, nyc311
from app.adapters.base import AdapterResult, SourceUnavailable
from app.fixtures import FIXTURES, REFERENCE_DATE, find_building
from app.models import Building, Report, SourceCoverage, SummaryMetrics
from app.services.analytics import CATEGORIES, create_findings, monthly_series, normalize_311, normalize_dob, normalize_hpd
from app.storage.cache import load_building


SOURCE_META = {
    "311": ("NYC 311", nyc311.DATASET_URL, "BBL plus exact normalized building address"),
    "HPD": ("HPD Housing Maintenance Code Violations", hpd.DATASET_URL, "BIN exact match"),
    "DOB": ("DOB Complaints Received", dob.DATASET_URL, "BIN exact match"),
}


def period_bounds(reference: date, months: int) -> tuple[date, date]:
    end = reference.replace(day=1)
    year, month = end.year, end.month
    for _ in range(months):
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return date(year, month, 1), end


def _unavailable(message: str) -> AdapterResult:
    return AdapterResult([], "unavailable", warnings=[message])


async def _safe(coro) -> AdapterResult:
    try:
        return await coro
    except SourceUnavailable as exc:
        return _unavailable(f"Source request failed: {str(exc)[:160]}")
    except Exception:
        return _unavailable("Source request failed unexpectedly; other sources remain available.")


async def build_report(building_id: str, months: int) -> Report | None:
    demo_building = find_building(building_id)
    if demo_building:
        building = demo_building
        reference = date.fromisoformat(REFERENCE_DATE)
        source_results = FIXTURES[building_id]
        mode = "demo"
    else:
        raw = load_building(building_id)
        if not raw:
            return None
        building = Building.model_validate(raw)
        reference = datetime.now(ZoneInfo("America/New_York")).date()
        start, end = period_bounds(reference, months)
        fetched = await asyncio.gather(
            _safe(nyc311.fetch(building, start, end)),
            _safe(hpd.fetch(building, start, end)),
            _safe(dob.fetch(building, start, end)),
        )
        source_results = dict(zip(("311", "HPD", "DOB"), fetched))
        mode = "live"
    start, end = period_bounds(reference, months)
    records_311 = normalize_311(source_results["311"].records)
    records_hpd = normalize_hpd(source_results["HPD"].records)
    records_dob = normalize_dob(source_results["DOB"].records)
    records = sorted(records_311 + records_hpd + records_dob, key=lambda row: row.occurred_at, reverse=True)
    monthly = monthly_series(records_311, start, months)
    source_ok = {key: result.status != "unavailable" for key, result in source_results.items()}
    open_hpd = [record for record in records_hpd if record.status_group == "open"]
    hpd_classes = {key: 0 for key in ("A", "B", "C", "I")}
    for record in open_hpd:
        if record.classification in hpd_classes:
            hpd_classes[record.classification] += 1
    category_totals = {category: sum(point.counts[category] for point in monthly) for category in CATEGORIES}
    coverage = []
    for key, result in source_results.items():
        name, url, match = SOURCE_META[key]
        coverage.append(SourceCoverage(
            key=key, name=name, dataset_url=url, status=result.status,
            retrieved_at=result.retrieved_at, dataset_updated_at=result.dataset_updated_at,
            period_start=start.isoformat() if key != "HPD" else None,
            period_end=(end.isoformat() if key != "HPD" else "Current status snapshot"),
            match_method=match if mode == "live" else "Synthetic records using production schema",
            warnings=result.warnings, record_count=len(result.records) if result.status != "unavailable" else None,
            cached=result.cached,
        ))
    limitations = [
        "Complaints are reports, not proof that a violation occurred; closed complaints do not prove a condition was corrected.",
        "No public records does not establish that no problems exist.",
        "Recurring reports is a product heuristic based on three or more distinct months, not a regulatory finding.",
    ]
    if mode == "demo":
        limitations.insert(0, "Demo data is fictional and uses a fixed reference date for reproducibility.")
    if any(result.status != "complete" for result in source_results.values()):
        limitations.append("This is a partial report because at least one source was unavailable or incomplete.")
    return Report(
        id=f"report-{building_id}-{months}", mode=mode, reference_date=reference.isoformat(), building=building,
        period={"months": months, "start": start.isoformat(), "end_exclusive": end.isoformat(), "label": f"{months} complete months"},
        coverage=coverage,
        summary=SummaryMetrics(
            complaints_311=len(records_311) if source_ok["311"] else None,
            open_hpd_violations=len(open_hpd) if source_ok["HPD"] else None,
            hpd_by_class=hpd_classes if source_ok["HPD"] else None,
            dob_complaints=len(records_dob) if source_ok["DOB"] else None,
        ),
        category_totals=category_totals if source_ok["311"] else {}, monthly=monthly,
        findings=create_findings(records, monthly), records=records, limitations=limitations,
    )
