from __future__ import annotations

from datetime import datetime, timezone

from app.adapters.base import AdapterResult
from app.models import Building


REFERENCE_DATE = "2026-09-15"

BUILDINGS = [
    Building(
        id="demo-elm-court",
        address="128 Example Avenue",
        borough="Brooklyn",
        latitude=40.6818,
        longitude=-73.9552,
        bin="9000001",
        bbl="3999990001",
        source_ids={"HPD": "D10001"},
        match_method="Synthetic fixture identity",
        confidence=1,
        demo=True,
    ),
    Building(
        id="demo-harbor-house",
        address="47 Harbor Lane",
        borough="Bronx",
        latitude=40.8441,
        longitude=-73.8932,
        bin="9000002",
        bbl="2999990002",
        source_ids={"HPD": "D10002"},
        match_method="Synthetic fixture identity",
        confidence=1,
        demo=True,
    ),
    Building(
        id="demo-cypress-place",
        address="21 Cypress Place",
        borough="Queens",
        latitude=40.7442,
        longitude=-73.8841,
        bin="9000003",
        bbl="4999990003",
        source_ids={"HPD": "D10003"},
        match_method="Synthetic fixture identity",
        confidence=1,
        demo=True,
    ),
]


def _retrieved() -> datetime:
    return datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)


def _complaint(record_id: str, created: str, complaint: str, descriptor: str, status: str = "Closed") -> dict[str, str]:
    return {
        "unique_key": record_id,
        "created_date": f"{created}T09:30:00.000",
        "closed_date": f"{created}T16:00:00.000" if status == "Closed" else "",
        "agency": "HPD",
        "complaint_type": complaint,
        "descriptor": descriptor,
        "status": status,
        "resolution_description": "The source records this request as closed; this does not establish that the condition was corrected.",
    }


def _violation(
    record_id: str,
    inspected: str,
    cls: str,
    description: str,
    status: str = "Open",
    story: int | None = None,
) -> dict[str, str]:
    record = {
        "violationid": record_id,
        "buildingid": "D10001",
        "class": cls,
        "inspectiondate": f"{inspected}T00:00:00.000",
        "approveddate": f"{inspected}T00:00:00.000",
        "novdescription": description,
        "currentstatus": "VIOLATION OPEN" if status == "Open" else "VIOLATION CLOSED",
        "currentstatusdate": f"{inspected}T00:00:00.000",
        "violationstatus": status,
    }
    if story:
        record["story"] = str(story)
    return record


def _dob(record_id: str, entered: str, category: str, status: str = "CLOSED") -> dict[str, str]:
    return {
        "complaint_number": record_id,
        "status": status,
        "date_entered": entered,
        "complaint_category": category,
        "disposition_code": "L2" if status == "CLOSED" else "",
    }


FIXTURES: dict[str, dict[str, AdapterResult]] = {
    "demo-elm-court": {
        "311": AdapterResult(
            [
                _complaint("D311-001", "2025-10-08", "HEAT/HOT WATER", "ENTIRE BUILDING"),
                _complaint("D311-002", "2025-12-03", "HEAT/HOT WATER", "APARTMENT ONLY"),
                _complaint("D311-003", "2025-12-18", "HEAT/HOT WATER", "ENTIRE BUILDING"),
                _complaint("D311-004", "2026-01-07", "HEAT/HOT WATER", "ENTIRE BUILDING"),
                _complaint("D311-005", "2026-01-20", "HEAT/HOT WATER", "APARTMENT ONLY"),
                _complaint("D311-006", "2026-02-04", "HEAT/HOT WATER", "ENTIRE BUILDING"),
                _complaint("D311-007", "2026-02-22", "HEAT/HOT WATER", "APARTMENT ONLY"),
                _complaint("D311-008", "2026-03-12", "PLUMBING", "LEAKING PIPE"),
                _complaint("D311-009", "2026-04-18", "UNSANITARY CONDITION", "PESTS"),
                _complaint("D311-010", "2026-06-02", "PLUMBING", "WATER LEAK"),
                _complaint("D311-011", "2026-07-14", "NOISE - RESIDENTIAL", "LOUD MUSIC"),
            ],
            retrieved_at=_retrieved(),
            dataset_updated_at=_retrieved(),
        ),
        "HPD": AdapterResult(
            [
                _violation("DHPD-101", "2026-01-11", "C", "PROVIDE AN ADEQUATE SUPPLY OF HEAT AND HOT WATER", story=6),
                _violation("DHPD-102", "2026-03-16", "B", "REPAIR THE WATER LEAK AT THE BATHROOM CEILING", story=4),
                _violation("DHPD-103", "2025-08-20", "A", "PAINT PEELING SURFACES", "Close", story=2),
            ],
            retrieved_at=_retrieved(),
            dataset_updated_at=_retrieved(),
        ),
        "DOB": AdapterResult(
            [_dob("D-DOB-301", "02/14/2026", "45", "ACTIVE"), _dob("D-DOB-302", "05/09/2026", "73")],
            retrieved_at=_retrieved(),
            dataset_updated_at=_retrieved(),
        ),
    },
    "demo-harbor-house": {
        "311": AdapterResult(
            [
                _complaint("D311-201", "2026-02-18", "PLUMBING", "WATER LEAK"),
                _complaint("D311-202", "2026-05-04", "ELEVATOR", "ELEVATOR OUT OF SERVICE"),
                _complaint("D311-203", "2026-07-09", "UNSANITARY CONDITION", "PESTS"),
            ],
            retrieved_at=_retrieved(),
            dataset_updated_at=_retrieved(),
        ),
        "HPD": AdapterResult(
            [
                _violation("DHPD-201", "2026-02-19", "B", "REPAIR THE BROKEN WASTE PIPE", story=3),
                _violation("DHPD-202", "2026-04-06", "C", "ABATE THE INFESTATION OF MICE", story=5),
                _violation("DHPD-203", "2026-05-08", "B", "REPAIR THE SELF-CLOSING ENTRANCE DOOR", story=1),
                _violation("DHPD-204", "2026-06-27", "A", "POST THE REQUIRED BUILDING NOTICE"),
            ],
            retrieved_at=_retrieved(),
            dataset_updated_at=_retrieved(),
        ),
        "DOB": AdapterResult(
            [_dob("D-DOB-401", "05/04/2026", "ELEVATOR", "CLOSED")],
            retrieved_at=_retrieved(),
            dataset_updated_at=_retrieved(),
        ),
    },
    "demo-cypress-place": {
        "311": AdapterResult([], retrieved_at=_retrieved(), dataset_updated_at=_retrieved()),
        "HPD": AdapterResult(
            [_violation("DHPD-301", "2025-10-10", "A", "PAINT PEELING SURFACES", "Close")],
            retrieved_at=_retrieved(),
            dataset_updated_at=_retrieved(),
        ),
        "DOB": AdapterResult(
            [],
            status="unavailable",
            retrieved_at=_retrieved(),
            warnings=["Synthetic source outage included to demonstrate a partial report."],
        ),
    },
}


def find_building(building_id: str) -> Building | None:
    return next((building for building in BUILDINGS if building.id == building_id), None)
