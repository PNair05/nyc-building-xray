from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Iterable

from app.models import EvidenceRecord, Finding, MonthlyPoint


CATEGORIES = [
    "Heat and hot water",
    "Plumbing and leaks",
    "Pests",
    "Elevators",
    "Noise",
    "Other maintenance",
    "Other reports",
]

CATEGORY_RULES = [
    ("Heat and hot water", ("HEAT", "HOT WATER", "BOILER")),
    ("Plumbing and leaks", ("PLUMB", "LEAK", "PIPE", "SEWER", "WATER")),
    ("Pests", ("PEST", "ROACH", "MICE", "MOUSE", "RAT", "VERMIN")),
    ("Elevators", ("ELEVATOR", "LIFT")),
    ("Noise", ("NOISE", "LOUD")),
    ("Other maintenance", ("PAINT", "DOOR", "WINDOW", "MOLD", "CEILING", "FLOOR")),
]


def documented_floor(raw_story: str | int | None) -> int | None:
    """Map only an explicit positive numeric HPD story to a display floor."""
    if raw_story is None:
        return None
    text = str(raw_story).strip()
    if not text.isdigit():
        return None
    floor = int(text)
    return floor if floor > 0 else None


def category_for(*values: str | None) -> str:
    text = " ".join(value or "" for value in values).upper()
    for category, needles in CATEGORY_RULES:
        if any(needle in text for needle in needles):
            return category
    return "Other reports"


def hpd_status(raw_status: str | None, current_status: str | None = None) -> str:
    value = (raw_status or "").strip().upper()
    current = (current_status or "").strip().upper()
    if value == "OPEN" or current == "VIOLATION OPEN":
        return "open"
    if value in {"CLOSE", "CLOSED"} or current in {"VIOLATION CLOSED", "VIOLATION DISMISSED"}:
        return "closed"
    return "unknown"


def dob_status(raw_status: str | None) -> str:
    value = (raw_status or "").strip().upper()
    if value in {"ACTIVE", "OPEN"}:
        return "open"
    if value in {"CLOSED", "CLOSE"}:
        return "closed"
    return "unknown"


def normalize_311(rows: list[dict]) -> list[EvidenceRecord]:
    records = []
    for row in _dedupe(rows, "unique_key"):
        record_id = str(row.get("unique_key", "unknown"))
        original = row.get("complaint_type", "Unknown")
        records.append(
            EvidenceRecord(
                id=f"311-{record_id}", source="311", source_record_id=record_id,
                occurred_at=row.get("created_date", ""), category=category_for(original, row.get("descriptor")),
                original_category=original, description=row.get("descriptor") or "No description provided",
                status=row.get("status", "Unknown"), status_group="not_applicable",
                source_url="https://data.cityofnewyork.us/resource/erm2-nwe9.json",
                address=row.get("incident_address"),
            )
        )
    return records


def normalize_hpd(rows: list[dict]) -> list[EvidenceRecord]:
    records = []
    for row in _dedupe(rows, "violationid"):
        record_id = str(row.get("violationid", "unknown"))
        status = row.get("violationstatus") or row.get("currentstatus") or "Unknown"
        description = row.get("novdescription") or "No description provided"
        floor = documented_floor(row.get("story"))
        records.append(
            EvidenceRecord(
                id=f"HPD-{record_id}", source="HPD", source_record_id=record_id,
                occurred_at=row.get("inspectiondate", ""), category=category_for(description),
                original_category="Housing Maintenance Code violation", description=description,
                status=status, status_group=hpd_status(row.get("violationstatus"), row.get("currentstatus")),
                classification=row.get("class"),
                source_url="https://data.cityofnewyork.us/resource/wvxf-dwi5.json",
                floor=floor,
                location_detail=f"Floor {floor}" if floor else None,
            )
        )
    return records


def normalize_dob(rows: list[dict]) -> list[EvidenceRecord]:
    records = []
    for row in _dedupe(rows, "complaint_number"):
        record_id = str(row.get("complaint_number", "unknown"))
        entered = row.get("date_entered", "")
        try:
            occurred = datetime.strptime(entered, "%m/%d/%Y").date().isoformat()
        except ValueError:
            occurred = entered
        original = str(row.get("complaint_category", "Unknown"))
        status = row.get("status", "Unknown")
        records.append(
            EvidenceRecord(
                id=f"DOB-{record_id}", source="DOB", source_record_id=record_id,
                occurred_at=occurred, category=category_for(original), original_category=original,
                description=f"DOB complaint category {original}", status=status,
                status_group=dob_status(status),
                source_url="https://data.cityofnewyork.us/resource/eabe-havv.json",
            )
        )
    return records


def _dedupe(rows: list[dict], key: str) -> Iterable[dict]:
    seen: set[str] = set()
    for row in rows:
        value = str(row.get(key, ""))
        if value and value not in seen:
            seen.add(value)
            yield row


def month_starts(start: date, count: int) -> list[date]:
    values = []
    current = start.replace(day=1)
    for _ in range(count):
        values.append(current)
        current = date(current.year + (current.month == 12), 1 if current.month == 12 else current.month + 1, 1)
    return values


def monthly_series(complaints: list[EvidenceRecord], start: date, months: int) -> list[MonthlyPoint]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for record in complaints:
        if record.source != "311":
            continue
        try:
            month = record.occurred_at[:7]
            counts[month][record.category] += 1
        except (TypeError, IndexError):
            continue
    return [
        MonthlyPoint(
            month=month.isoformat()[:7],
            counts={category: counts[month.isoformat()[:7]][category] for category in CATEGORIES},
            total=sum(counts[month.isoformat()[:7]].values()),
        )
        for month in month_starts(start, months)
    ]


def create_findings(records: list[EvidenceRecord], monthly: list[MonthlyPoint]) -> list[Finding]:
    findings: list[Finding] = []
    complaints = [record for record in records if record.source == "311"]
    for category in CATEGORIES:
        active_months = [point.month for point in monthly if point.counts.get(category, 0) > 0]
        evidence = [record.id for record in complaints if record.category == category]
        if len(active_months) >= 3:
            findings.append(Finding(
                id=f"recurring-{category.lower().replace(' ', '-')}",
                title=f"Recurring {category.lower()} reports",
                detail=f"Reports appeared in {len(active_months)} distinct months during the 12 complete-month view. This is a product heuristic, not a regulatory finding.",
                evidence_ids=evidence, category=category,
            ))
    open_hpd = [record for record in records if record.source == "HPD" and record.status_group == "open"]
    if open_hpd:
        grouped = Counter(record.category for record in open_hpd)
        category, count = grouped.most_common(1)[0]
        evidence = [record.id for record in open_hpd]
        findings.append(Finding(
            id="open-violations", title=f"{len(open_hpd)} open HPD violation{'s' if len(open_hpd) != 1 else ''}",
            detail=f"{count} open violation{'s' if count != 1 else ''} concern {category.lower()}. Status reflects the latest source snapshot.",
            evidence_ids=evidence, category=category,
        ))
    return findings[:3]


def compare_equal_periods(previous: int, current: int) -> dict[str, float | int | str | None]:
    """Return a display-safe equal-period comparison without inventing infinity."""
    if previous == 0:
        return {
            "previous": previous,
            "current": current,
            "percent_change": None,
            "label": f"{current} reports compared with 0 in the previous period.",
        }
    percent = ((current - previous) / previous) * 100
    return {
        "previous": previous,
        "current": current,
        "percent_change": percent,
        "label": f"{current} reports compared with {previous} in the previous period ({percent:+.0f}%).",
    }
