# Demo fixture contract

The reproducible fixtures are defined in `backend/app/fixtures.py` with a fixed reference date of **2026-09-15**. They use the same raw adapter inputs and normalized report contract as live data.

- `demo-elm-court`: recurring heat/hot-water reports plus two open HPD violations.
- `demo-harbor-house`: several open maintenance violations across categories.
- `demo-cypress-place`: a successful zero-result 311 query and an explicitly unavailable DOB source.

All names, addresses, identifiers, and records are fictional. They must never be described as real NYC properties.
