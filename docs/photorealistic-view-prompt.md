# Implementation prompt: optional photorealistic building view

Implement the following feature in the existing NYC Building X-Ray project. Read the repository instructions and inspect the current implementation before editing. Complete the code, setup documentation, and appropriate verification; do not stop at a plan.

## Goal

Add a two-view toggle to the building report's 3D panel:

- **Building analysis**: preserve the existing isolated NYC building model, evidence controls, original Rhino download, and drag/zoom/pan interaction.
- **Real-world view**: stream Google Maps Photorealistic 3D Tiles, with the camera centered on the selected building's geographic location so users can recognize the property and its surroundings.

Default to Building analysis. Load Google's viewer only when the user selects Real-world view. Keep the design consistent with the existing report and responsive on mobile.

## Existing project context

- Next.js/React frontend: `frontend/`.
- FastAPI backend: `backend/`.
- Current model viewer: `frontend/components/BuildingModel3D.tsx`.
- Report integration: `frontend/components/ReportDashboard.tsx`.
- Building identity and model response types: `frontend/lib/types.ts`.
- API client: `frontend/lib/api.ts`.
- Local building extraction: `backend/app/services/building_models.py`.
- Original district models and generated building assets: `frontend/public/models/`.
- Building identity includes latitude, longitude, BIN, BBL, and a demo flag. Check the actual files for changes before relying on these details.

## Implementation requirements

1. Verify the current official Google Map Tiles API documentation, renderer compatibility, attribution requirements, and usage terms before implementation. Prefer CesiumJS for the geographic viewer unless another supported renderer integrates materially better with the current app; document the choice.
2. Treat Google's content as a separate streamed, textured geographic scene. Do not extract Google textures and apply them to the NYC model, export Google geometry into our GLBs, or store tiles in our model directory or an S3 bucket. Honor the API's current caching rules and response headers.
3. Render Google's tiles through the supported authenticated tileset flow. Implement the required Google Maps and per-tile provider attribution visibly, including on mobile. Verify the renderer's attribution behavior rather than assuming it is automatic.
4. Initialize the camera near the selected building using its coordinates. Determine a sensible ground-relative camera target using supported renderer capabilities; account for terrain elevation. Provide orbit, zoom, pan, and reset-to-building controls.
5. Indicate the selected address with a marker or outline derived from our independent address/footprint data. Do not derive outlines or building identity from Google's imagery or mesh. If there is no verified footprint, use a location marker and describe it as the address location.
6. Keep incident evidence separate from visual appearance. Preserve the existing floor evidence controls. Do not attach incidents to specific windows or apartments. This task does not require adding floor overlays; any optional floor positioning must use documented source floors and clearly label estimated heights.
7. Preserve the existing isolated-model experience. Photorealistic coverage must not depend on whether a local NYC district model is installed. Allow Real-world view for a live building with valid coordinates even when Building analysis has no model.
8. For fictional demo addresses, do not imply that a real photographed building represents the fictional records. Keep photorealistic mode unavailable with a short explanation, while preserving the existing labeled source example.
9. Handle missing configuration, invalid coordinates, authorization errors, quota errors, unavailable coverage, network failures, and WebGL failures within the model panel. The rest of the report must remain usable. Show a concise status and a way to return to Building analysis.
10. Lazy-load the geographic viewer and its assets, using a client-only boundary appropriate to the installed Next.js version. Avoid SSR access to browser globals. Clean up render loops, event handlers, requests where supported, and GPU resources when switching views or buildings or leaving the report. Avoid duplicate viewer instances and unnecessary root tileset requests.

## Configuration and setup

- Document how to enable Map Tiles API and billing in Google Cloud and create a key restricted to the required API and allowed website referrers.
- Use an environment variable such as `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` if the selected renderer calls Google directly from the browser. Explain that a browser key is visible to users and must be restricted; it is not a server secret. Keep any server-only credentials out of public variables.
- Add a placeholder to the appropriate example environment file. Never commit a real key.
- Do not create a cloud account or enable billing as part of code implementation. If credentials are absent, finish the implementation and test its unconfigured/error states, then identify the exact configuration needed for a live verification.
- Document applicable billing units and quota controls using current official documentation. Do not promise zero cost. No S3 storage is required for this feature.

## Verification and acceptance criteria

- Building analysis still loads an isolated building, supports its controls, and opens source evidence.
- Real-world view shows the selected live address and surrounding photorealistic scene when configuration and coverage permit.
- Switching views repeatedly or selecting another building does not leave stale geometry, markers, camera targets, or active duplicate viewers.
- No Google tile requests occur before the user opens Real-world view.
- A missing local district model does not block Real-world view.
- Missing Google configuration and failed requests produce a readable panel state without breaking the report.
- Attribution is visible and unobscured at desktop and mobile widths.
- Verify drag, zoom, reset, and switching back to the isolated model in the browser. Use 317 East 18 Street, Manhattan, as an existing live example if it remains available.
- Run the frontend's applicable type, lint, and build checks. Add focused tests for meaningful new logic where appropriate.
- Distinguish checks performed with real Google tiles from mocked or unconfigured tests. Do not claim a live integration was verified without a working authorized key.

## Official references to check

- Photorealistic 3D Tiles: https://developers.google.com/maps/documentation/tile/3d-tiles
- Renderer integration: https://developers.google.com/maps/documentation/tile/use-renderer
- Policies and attribution: https://developers.google.com/maps/documentation/tile/policies
- Usage and billing: https://developers.google.com/maps/documentation/tile/usage-and-billing
- Google Cloud setup: https://developers.google.com/maps/documentation/tile/cloud-setup

Deliver a working implementation, updated setup instructions, and a concise summary of verification and any remaining configuration requirements.
