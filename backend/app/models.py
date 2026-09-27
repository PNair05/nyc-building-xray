from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Category = Literal[
    "Heat and hot water",
    "Plumbing and leaks",
    "Pests",
    "Elevators",
    "Noise",
    "Other maintenance",
    "Other reports",
]


class Building(BaseModel):
    id: str
    address: str
    borough: str
    latitude: float | None = None
    longitude: float | None = None
    bin: str | None = None
    bbl: str | None = None
    source_ids: dict[str, str] = Field(default_factory=dict)
    match_method: str
    confidence: float
    ambiguity: str | None = None
    demo: bool = False


class SourceCoverage(BaseModel):
    key: str
    name: str
    dataset_url: str
    status: Literal["complete", "incomplete", "unavailable"]
    retrieved_at: datetime
    dataset_updated_at: datetime | None = None
    period_start: str | None = None
    period_end: str | None = None
    match_method: str
    warnings: list[str] = Field(default_factory=list)
    record_count: int | None = None
    cached: bool = False


class EvidenceRecord(BaseModel):
    id: str
    source: Literal["311", "HPD", "DOB"]
    source_record_id: str
    occurred_at: str
    category: Category
    original_category: str
    description: str
    status: str
    status_group: Literal["open", "closed", "unknown", "not_applicable"]
    classification: str | None = None
    source_url: str
    address: str | None = None
    floor: int | None = None
    location_detail: str | None = None


class MonthlyPoint(BaseModel):
    month: str
    counts: dict[str, int]
    total: int


class Finding(BaseModel):
    id: str
    title: str
    detail: str
    evidence_ids: list[str]
    category: str | None = None


class SummaryMetrics(BaseModel):
    complaints_311: int | None
    open_hpd_violations: int | None
    hpd_by_class: dict[str, int] | None
    dob_complaints: int | None


class Report(BaseModel):
    id: str
    mode: Literal["demo", "live"]
    reference_date: str
    building: Building
    period: dict[str, str | int]
    coverage: list[SourceCoverage]
    summary: SummaryMetrics
    category_totals: dict[str, int]
    monthly: list[MonthlyPoint]
    findings: list[Finding]
    records: list[EvidenceRecord]
    limitations: list[str]


class ExplanationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    evidence_ids: list[str]


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Literal["Summary", "AI-generated"]
    overview: str
    findings: list[ExplanationFinding]
    landlord_questions: list[str]
    limitations: list[str]


class Health(BaseModel):
    status: str
    demo_available: bool
    ai_configured: bool
    version: str
