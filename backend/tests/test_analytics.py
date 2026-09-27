from datetime import date

from app.models import Building, Explanation, ExplanationFinding
from app.services.analytics import compare_equal_periods, documented_floor, hpd_status, normalize_311, normalize_hpd
from app.services.geocoding import decode_live_building, encode_live_building
from app.services.explanations import validate_evidence
from app.services.matching import same_building_address
from app.services.reports import period_bounds


def test_building_address_prevents_lot_level_misattribution():
    assert same_building_address("350 5 Avenue", "350 5th Avenue") is False
    assert same_building_address("128 EXAMPLE AVENUE", "128 Example Ave") is True
    assert same_building_address("130 EXAMPLE AVENUE", "128 Example Ave") is False


def test_duplicate_source_ids_are_removed_without_collapsing_distinct_reports():
    rows = [
        {"unique_key": "1", "created_date": "2026-01-01", "complaint_type": "HEAT", "descriptor": "NO HEAT", "status": "Open"},
        {"unique_key": "1", "created_date": "2026-01-01", "complaint_type": "HEAT", "descriptor": "NO HEAT", "status": "Open"},
        {"unique_key": "2", "created_date": "2026-01-01", "complaint_type": "HEAT", "descriptor": "NO HEAT", "status": "Open"},
    ]
    assert [record.source_record_id for record in normalize_311(rows)] == ["1", "2"]


def test_zero_baseline_has_counts_and_no_infinite_percentage():
    result = compare_equal_periods(0, 5)
    assert result["percent_change"] is None
    assert result["label"] == "5 reports compared with 0 in the previous period."


def test_current_incomplete_month_is_excluded():
    start, end = period_bounds(date(2026, 9, 26), 12)
    assert start == date(2025, 9, 1)
    assert end == date(2026, 9, 1)


def test_unknown_hpd_status_stays_unknown():
    assert hpd_status("PENDING REVIEW", "MYSTERY STATUS") == "unknown"


def test_only_documented_numeric_hpd_story_becomes_a_floor_marker():
    assert documented_floor("6") == 6
    assert documented_floor("BASEMENT") is None
    assert documented_floor("0") is None
    record = normalize_hpd([
        {"violationid": "1", "inspectiondate": "2026-01-01", "novdescription": "LEAK", "violationstatus": "Open", "story": "4"}
    ])[0]
    assert record.floor == 4
    assert record.location_detail == "Floor 4"


def test_live_building_identity_is_self_contained():
    building = Building(
        id="",
        address="300 EAST 38 STREET",
        borough="Manhattan",
        latitude=40.748,
        longitude=-73.973,
        bin="1034920",
        bbl="1009437501",
        source_ids={"geosearch": "test"},
        match_method="NYC GeoSearch exact",
        confidence=0.9,
    )
    building_id = encode_live_building(building)
    decoded = decode_live_building(building_id)

    assert decoded is not None
    assert decoded.id == building_id
    assert decoded.address == building.address
    assert decoded.bin == building.bin


def test_ai_evidence_ids_must_exist():
    result = Explanation(
        label="AI-generated", overview="Overview", limitations=[], landlord_questions=[],
        findings=[ExplanationFinding(text="Claim", evidence_ids=["311-1", "FAKE-9"])],
    )
    assert validate_evidence(result, {"311-1"}) is False
