# Architecture

## Request flow

1. The Next.js client sends an address and optional borough to FastAPI.
2. GeoSearch returns one or more candidates; FastAPI assigns a stable local application ID and caches the selected identity in SQLite.
3. The report service queries 311, HPD, and DOB concurrently and independently. One failure cannot erase the other sources.
4. Adapters retain source-native records and apply source-specific building matching.
5. Deterministic services deduplicate by source ID, normalize categories/statuses, build complete-month series, and create evidence-linked findings.
6. The API returns one validated Pydantic report contract used by both live and demo mode.
7. The explanation endpoint rebuilds trusted report data server-side. It never accepts client-supplied metrics.

The report header defaults to an isolated building model extracted from the local NYC district geometry. Its optional real-world view is a separate, lazy client-only CesiumJS boundary that streams Google Photorealistic 3D Tiles directly from Google's authenticated root tileset. It never copies Google textures or geometry into local models or storage. Cesium is the supported renderer chosen for its required per-tile credit aggregation (`showCreditsOnScreen`), scene-height sampling, camera controls, and deterministic resource cleanup. Only records carrying an explicit numeric HPD story receive a clickable floor button; records are never attached to visible windows or apartments.

## Trust boundaries

- Server credentials never reach the browser. The optional Google Maps key is intentionally browser-visible, restricted to Map Tiles API and allowed website referrers, and is not treated as a secret.
- Source text is treated as data and never as instructions.
- The LLM receives only compact, precomputed metrics, selected records, evidence IDs, and limitations.
- Structured output is Pydantic-validated, then every returned evidence ID is checked against the trusted report. Any API, parsing, schema, or citation failure falls back to the deterministic summary.
- SQLite contains cached public responses and temporary building candidates only.

## Time and matching

- User-facing boundaries use `America/New_York`.
- The current incomplete calendar month is excluded from monthly trends.
- BIN is treated as a building identifier and BBL as a tax-lot identifier.
- Same-lot 311 records require address corroboration. Nearby geographic records are never merged.

## Reliability

- HTTP timeout: 12 seconds per public-source request.
- Retry: one bounded retry after 200 ms.
- Cache: SQLite, visible retrieval/cached flag, one-hour default TTL.
- Result cap: 3,000 per source. Reaching it marks the source incomplete.
- UI: distinct complete, incomplete, unavailable, and successful-zero states.
