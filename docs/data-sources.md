# Verified data sources

Verified against official metadata and bounded live queries on **2026-09-26**. No adapter is considered working solely because a dataset page exists; each mapping below was checked against a real API response.

## NYC GeoSearch

- Official documentation: <https://geosearch.planninglabs.nyc/docs/>
- Endpoint: `GET https://geosearch.planninglabs.nyc/v2/search?text=...&size=...`
- Authentication: none documented or required by the verified request.
- Verified response fields: GeoJSON `features[].geometry.coordinates`; `properties.name`, `borough`, `confidence`, `match_type`, `gid`; `properties.addendum.pad.bin`; `properties.addendum.pad.bbl`.
- Application mapping: creates a confirmation candidate. The app never silently merges candidates. A confidence below 0.9 produces an ambiguity prompt.
- Verified query: `350 5th Avenue Manhattan` returned `350 5 AVENUE`, Manhattan, BIN `1015862`, BBL `1008350041`, and point coordinates.

## NYC 311 Service Requests from 2020 to Present

- Dataset ID: `erm2-nwe9`
- Dataset: <https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9>
- API: <https://data.cityofnewyork.us/resource/erm2-nwe9.json>
- Update frequency: daily in official metadata.
- Authentication: public requests work without credentials; `X-App-Token` is supported and recommended for rate limits.
- Stable record ID: `unique_key`.
- Verified fields: `unique_key`, `created_date`, `closed_date`, `agency`, `complaint_type`, `descriptor`, `status`, `resolution_description`, `incident_address`, `borough`, `bbl`.
- Coverage: the current dataset is 2020-present. The older 2010-2019 data is in `76ig-c548` and is not needed for the MVP 12-month view.
- Matching: 311 exposes BBL but not BIN. Since BBL is a tax lot and can contain several buildings, the adapter queries by BBL and period, then requires the normalized `incident_address` to equal the selected building address. Same-lot records with another address are excluded and counted in a warning.
- Time semantics: `created_date` is a Socrata floating timestamp. The app constructs period boundaries in `America/New_York` and excludes the current incomplete month.
- Interpretation: service requests are reports. `Closed` is preserved as a source status and is not presented as proof of repair.

## HPD Housing Maintenance Code Violations

- Dataset ID: `wvxf-dwi5`
- Dataset: <https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Violations/wvxf-dwi5>
- API: <https://data.cityofnewyork.us/resource/wvxf-dwi5.json>
- Update frequency: daily in official metadata.
- Authentication: public requests work without credentials; optional Socrata app token.
- Stable record ID: `violationid`.
- Verified fields: `violationid`, `buildingid`, `boroid`, `boro`, `housenumber`, `streetname`, `story`, `apartment`, `class`, `inspectiondate`, `approveddate`, `novdescription`, `currentstatus`, `currentstatusdate`, `violationstatus`, `bin`, `bbl`.
- Matching: exact BIN. `buildingid` is retained by the source but is not assumed to be BIN.
- Classification mapping from official metadata: A = non-hazardous; B = hazardous; C = immediately hazardous; I = information order.
- Status mapping: `violationstatus=Open` or `currentstatus=VIOLATION OPEN` maps to open. `Close`/`Closed`, `VIOLATION CLOSED`, and `VIOLATION DISMISSED` map to closed. Every other value maps to unknown. Unknown is never treated as open.
- Time basis: all matching violations are retrieved so the report can show the current source-status snapshot. It is deliberately distinct from a time-filtered event count.
- Spatial display: a positive numeric `story` may become a floor marker. Non-numeric values such as basement labels are not guessed. Apartment identifiers are not shown in the public report because a floor is sufficient for this visualization.
- Verified live response: a recent row included BIN `4075086`, BBL `4031680013`, class A, `violationstatus=Open`, and `currentstatus=VIOLATION OPEN`.

## DOB Complaints Received

- Dataset ID: `eabe-havv`
- Dataset: <https://data.cityofnewyork.us/Housing-Development/DOB-Complaints-Received/eabe-havv>
- API: <https://data.cityofnewyork.us/resource/eabe-havv.json>
- Authentication: public requests work without credentials; optional Socrata app token.
- Stable record ID: `complaint_number`.
- Verified fields: `complaint_number`, `status`, `date_entered`, `house_number`, `house_street`, `zip_code`, `bin`, `complaint_category`, `unit`, `disposition_date`, `disposition_code`, `inspection_date`.
- Matching: exact BIN.
- Date caveat: official metadata types `date_entered` as text, and live values use `MM/DD/YYYY`. The adapter retrieves a bounded BIN result and applies the selected complete-month period in application code. Invalid/missing dates are excluded with a warning.
- Interpretation: DOB complaints remain complaints, separate from verified HPD violations.
- Verified live response: complaint `3811511` included BIN `3068769`, date `08/27/2021`, category `73`, and status `CLOSED`.

## Category mapping

Classification is deterministic and runs in application code. It checks uppercased source category and description text in this order:

1. Heat and hot water: `HEAT`, `HOT WATER`, `BOILER`
2. Plumbing and leaks: `PLUMB`, `LEAK`, `PIPE`, `SEWER`, `WATER`
3. Pests: `PEST`, `ROACH`, `MICE`, `MOUSE`, `RAT`, `VERMIN`
4. Elevators: `ELEVATOR`, `LIFT`
5. Noise: `NOISE`, `LOUD`
6. Other maintenance: `PAINT`, `DOOR`, `WINDOW`, `MOLD`, `CEILING`, `FLOOR`
7. Other reports: fallback

Original source categories and descriptions are preserved on each evidence record.

## Model district coverage (verified September 26, 2026)

- Official PLUTO dataset: https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks
- API: `https://data.cityofnewyork.us/resource/64uk-42ks.json`, exact `bbl` filter, `$select=bbl,cd`, `$limit=2`. Public read without a key.
- `cd` is the three-digit community district; the first digit is the borough. Joint-interest areas are excluded from this lookup.
- Verified BBL `1009240013` returned `cd=106`, address `317 EAST 18 STREET`; it requires **MN06**. The available **MN08** does not cover it.
- Successful lookups are cached for 24 hours. Missing/ambiguous data or a network failure leaves coverage unknown.
- The published MN06 ZIP URL returned HTTP 403 during verification. That source file is required before extraction for this address can succeed.

## Completeness and freshness

Each adapter returns source name, dataset URL, retrieval time, dataset update time when the metadata call succeeds, requested coverage period, match method, status, record count, cache flag, and warnings. A network failure yields `unavailable`; a retrieval cap yields `incomplete`; only a successful complete query can display zero.
