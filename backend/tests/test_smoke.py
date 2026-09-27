from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_demo_search_report_evidence_and_explanation(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    search = client.get("/api/search", params={"q": "demo"})
    assert search.status_code == 200
    assert len(search.json()) == 3

    report = client.get("/api/buildings/demo-elm-court/report", params={"months": 12})
    assert report.status_code == 200
    payload = report.json()
    assert payload["mode"] == "demo"
    assert payload["summary"]["complaints_311"] == 11
    assert payload["summary"]["open_hpd_violations"] == 2
    evidence_ids = {row["id"] for row in payload["records"]}
    assert evidence_ids
    located = [row for row in payload["records"] if row["floor"] is not None]
    assert {row["floor"] for row in located} == {2, 4, 6}
    assert all(set(finding["evidence_ids"]) <= evidence_ids for finding in payload["findings"])

    explanation = client.post("/api/buildings/demo-elm-court/explanation")
    assert explanation.status_code == 200
    summary = explanation.json()
    assert summary["label"] == "Summary"
    assert all(set(finding["evidence_ids"]) <= evidence_ids for finding in summary["findings"])


def test_missing_source_is_not_displayed_as_zero():
    response = client.get("/api/buildings/demo-cypress-place/report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["complaints_311"] == 0
    assert payload["summary"]["dob_complaints"] is None
    dob = next(source for source in payload["coverage"] if source["key"] == "DOB")
    assert dob["status"] == "unavailable"
    assert dob["record_count"] is None


def test_period_is_bounded():
    assert client.get("/api/buildings/demo-elm-court/report", params={"months": 2}).status_code == 422
    assert client.get("/api/buildings/demo-elm-court/report", params={"months": 25}).status_code == 422
