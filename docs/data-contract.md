# Data Contract

## Record Metadata
Connector-written rows should preserve:

- `source`: source adapter or fixture name.
- `fetched_at`: when the backend fetched or generated the row.
- `trade_date` or source-specific observation date when applicable.
- `raw_payload_hash`: hash of the raw response or fixture payload.

## Freshness Semantics
- `fresh`: a local row exists and is within the expected refresh window.
- `stale`: a local row exists but should be refreshed.
- `failed`: latest job failed.
- `not_collected`: no local row exists.
- `not_configured`: the module is visible in navigation but has no connector yet.

## Fixture Semantics
Rows with `source = local_fixture` are deterministic development fixtures. They are useful for UI and API validation but are not market data.
