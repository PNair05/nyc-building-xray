# NYC Building X-Ray

Understand an NYC building before you sign a lease. Building X-Ray turns public 311 requests, HPD violations, and DOB complaints into an evidence-linked report with complete-month trends and practical questions to ask a landlord.

This is an investigation aid. It does **not** determine whether a building is safe or recommend whether someone should sign a lease.

## What is implemented

- Address search and confirmation through NYC GeoSearch, including BIN, BBL, coordinates, match method, confidence, and ambiguity messaging.
- Independent live adapters for NYC 311, HPD Housing Maintenance Code Violations, and DOB Complaints Received.
- Conservative identity matching: HPD and DOB use exact BIN; 311 uses BBL only as a query bound and then requires an exact normalized building address.
- Three clearly labeled fictional demo buildings, including a true zero result and a partial-source outage.
- Twelve complete calendar months of 311 trends with deterministic category mappings and a category filter.
- Current HPD open-status snapshot with documented A/B/C/I classifications.
- Evidence-backed findings, filterable evidence table, per-source freshness, caching, partial/unavailable states, and explicit limitations.
- Isolated 3D building view extracted from the uploaded NYC district models, with solid roof/facade geometry, orbit controls, and an original Rhino geometry download. Live addresses require a unique footprint containing the geocoded location. Fictional demos use explicitly labeled source examples.
- Optional real-world view that lazy-loads Google Photorealistic 3D Tiles around a live building's coordinates, keeps the Google scene separate from the isolated model, and labels the independently geocoded address location.
- Optional OpenAI structured explanation with evidence-ID validation; deterministic summary fallback with no API key.
- Responsive, keyboard-accessible Next.js dashboard and FastAPI backend.

## Requirements

- Node.js 22 or newer (tested with Node 25.1; required by the current CesiumJS release)
- Python 3.12 or newer (tested with Python 3.13)

## Install

From this directory:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt

cd frontend
npm install
cd ..

cp .env.example .env
```

The demo requires no credentials. An NYC Open Data app token is optional but helps with rate limits. An OpenAI key is optional; without it, the explanation endpoint returns the labeled deterministic `Summary`.

### Optional Google Photorealistic 3D Tiles

Real-world view is optional and only initializes after a user selects it. To enable it:

1. Create or select a Google Cloud project and attach a billing account by following the official [Map Tiles API cloud setup](https://developers.google.com/maps/documentation/tile/cloud-setup).
2. Enable **Map Tiles API** in Google Maps Platform and review the [Map Tiles policies](https://developers.google.com/maps/documentation/tile/policies).
3. Create a browser API key. Apply a **Websites** application restriction for the exact production origins and local referrers you use (for example, `http://localhost:3000/*`). Apply an API restriction for **Map Tiles API** only.
4. Add the key to `frontend/.env.local` and restart Next.js:

   ```dotenv
   NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your_restricted_browser_key
   ```

`NEXT_PUBLIC_` values are shipped to the browser and are visible to users; this key is not a server secret, so both website and API restrictions are required. Do not commit `frontend/.env.local`. CesiumJS is used because it is an officially documented compatible renderer, exposes Google tile credits with `showCreditsOnScreen`, supports a terrain/scene-height sample for the address marker, and destroys its render loop and GPU resources when the view closes. `npm install` and `npm run build` copy Cesium's runtime assets into the ignored `frontend/public/cesium/` directory.

Google requires billing for Map Tiles API. Photorealistic usage is the **Map Tiles API: Photorealistic 3D Tiles** SKU, billed on successful 3D tile responses. As documented in September 2026, the default limits are 10,000 root tileset queries per day and 12,000 renderer queries per minute; a root request establishes a timed session supporting up to three hours of renderer tile requests. Pricing and default quotas can change, so review the current [usage and billing documentation](https://developers.google.com/maps/documentation/tile/usage-and-billing), set a daily quota appropriate to the project, and monitor billing rather than assuming the feature is free. The app neither downloads nor persistently stores Google tiles; browser HTTP caching follows Google's response headers.

## Run

Open two terminals from this directory.

Backend:

```bash
source .venv/bin/activate
set -a; source .env; set +a
cd backend
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), choose **Try a demo building**, and select **128 Example Avenue** for the primary demo flow.

## Verify

```bash
source .venv/bin/activate
cd backend && pytest

cd ../frontend
npm run typecheck
npm run lint
npm run build
```

The backend smoke test covers demo search, report generation, evidence references, explanation fallback, missing-source semantics, and period bounds.

## Prepare single-building models

Unchanged districts are skipped. To add a single district, run `npm run models:buildings -- NYC_3DModel_MN06.3dm` from `frontend`; existing districts stay in the catalog. Use `--force` to rebuild unchanged sources. The index is replaced atomically so concurrent requests cannot read a partially written catalog.

When an address does not match, the model API checks NYC PLUTO's community district using the BBL and returns a specific reason (`missing_district`, `index_outdated`, `footprint_unmatched`, or `extraction_failed`). PLUTO resolves district coverage only; it never selects a building mesh. For example, 317 East 18 Street (BBL 1009240013) needs **MN06**. Install `NYC_3DModel_MN06.3dm` from the official NYC model download, prepare that district, then use the viewer's reset button to retry.

Place original `NYC_3DModel_*.3dm` files in `frontend/public/models`, then run `npm run models:buildings` from `frontend`. This indexes their footprints and creates isolated demo examples. It reads the originals, bypassing the older neighborhood previews and their object-count limit. Re-run after replacing source files.

The backend extracts and caches each live building on its first request. The local backend and frontend must share this project directory and allow writes to `frontend/public/models/buildings`. Large source files can take several seconds to open. The GLB viewer triangulates the source's planar surfaces and outlines without decimation; the `.3dm` download retains selected original geometry and its source units. Model tests cover neighboring-building exclusion, unit conversion, matching ambiguity, concave roofs, roof openings, and details present only as surfaces.

## Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `NEXT_PUBLIC_API_URL` | No | Browser-visible backend URL; defaults to `http://localhost:8000`. |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | No | Browser-visible, restricted Map Tiles API key for optional real-world view. |
| `NYC_OPEN_DATA_APP_TOKEN` | No | Raises Socrata API rate limits. Kept server-side. |
| `OPENAI_API_KEY` | No | Enables the structured AI explanation. Kept server-side. |
| `OPENAI_MODEL` | No | Model for structured explanations; defaults to `gpt-6-astra`. |
| `CACHE_TTL_SECONDS` | No | SQLite response-cache TTL; defaults to 3600 seconds. |
| `XRAY_DB_PATH` | No | SQLite cache/building identity path. |
| `FRONTEND_ORIGINS` | No | Comma-separated allowed browser origins. |

## Known limitations

- A 311 record has BBL but not BIN. To avoid assigning nearby or same-lot records to a selected building, the adapter keeps only records whose normalized incident address exactly matches the GeoSearch building address. This is conservative and can miss legitimate alternate-address records.
- HPD provides a current status snapshot; its open count is intentionally not described as “violations this year.”
- DOB `date_entered` is source text in `MM/DD/YYYY` format, so date filtering is performed after a bounded BIN query.
- Live source calls are bounded at 3,000 records per source. Hitting the bound marks coverage `incomplete` instead of implying a complete total.
- Source record links point to official dataset endpoints rather than a stable per-row public detail page.
- 3D coverage is limited to the uploaded districts and their historical source geometry. Coordinate matching is not a verified BIN match; ambiguous, out-of-coverage, and unsupported geometry returns an unavailable state. Extraction uses the selected footprint, so overhanging or separately mapped building parts may not be included. No windows or details absent from the source are invented. Fictional demo addresses use labeled source examples. Floor buttons open documented records and are not spatially assigned to the model.
- Google Photorealistic 3D Tiles are streamed visual context, not evidence and not a current-condition guarantee. Availability depends on Google coverage, a correctly restricted key, billing, quota, network access, and WebGL. The address marker uses this app's independent geocoded coordinates and is not a traced building outline.
- No neighborhood benchmarks, building-size normalization, permits, comparison mode, or downloadable PDF are included in the MVP.
- SQLite caching is process-local and intended for a local/demo deployment, not a multi-instance production service.

More detail: [data sources](docs/data-sources.md), [architecture](docs/architecture.md), and [two-minute demo](docs/demo-script.md).
