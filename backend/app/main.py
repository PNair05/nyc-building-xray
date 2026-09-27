from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.base import SourceUnavailable
from app.fixtures import BUILDINGS
from app.models import Building, Explanation, Health, Report
from app.services.explanations import generate
from app.services.geocoding import decode_live_building, search_live
from app.services.reports import build_report
from app.services.building_models import building_model
from app.storage.cache import load_building


app = FastAPI(title="NYC Building X-Ray API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", demo_available=True, ai_configured=bool(os.getenv("OPENAI_API_KEY")), version="1.0.0")


@app.get("/api/search", response_model=list[Building])
async def search(q: str = Query(min_length=2, max_length=160), borough: str | None = Query(default=None, max_length=20)):
    if q.strip().lower() in {"demo", "example", "try a demo building"}:
        return BUILDINGS
    try:
        return await search_live(q.strip(), borough)
    except SourceUnavailable:
        raise HTTPException(status_code=503, detail="Address search is temporarily unavailable. Demo mode still works.")


@app.get("/api/buildings/{building_id}/report", response_model=Report)
async def report(building_id: str, months: int = Query(default=12, ge=3, le=24)) -> Report:
    result = await build_report(building_id, months)
    if not result:
        raise HTTPException(status_code=404, detail="Building not found. Search for the address again.")
    return result


@app.post("/api/buildings/{building_id}/explanation", response_model=Explanation)
async def explanation(building_id: str, months: int = Query(default=12, ge=3, le=24)) -> Explanation:
    trusted_report = await build_report(building_id, months)
    if not trusted_report:
        raise HTTPException(status_code=404, detail="Building not found. Search for the address again.")
    return await generate(trusted_report)


@app.get("/api/buildings/{building_id}/model")
def model(building_id: str):
    building = next((item for item in BUILDINGS if item.id == building_id), None)
    if building is None:
        raw = load_building(building_id)
        building = Building.model_validate(raw) if raw else decode_live_building(building_id)
        if building is None:
            raise HTTPException(status_code=404, detail="Building not found. Search for the address again.")
    return building_model(building)
