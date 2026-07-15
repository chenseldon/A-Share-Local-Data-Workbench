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

## Market Refresh API
- `POST /api/security/{symbol}/refresh` is the only V1.1 endpoint that triggers public-source market fetches and writes them to DuckDB.
- `GET /api/security/{symbol}/quote` reads the latest cached row from `market_quotes`.
- `GET /api/security/{symbol}/chart?period=1d&adjustment=none` reads cached daily bars and returns `ma5`, `ma10`, and `ma20`.
- `GET /api/securities/search?q=...` may remote-resolve only complete six-digit symbols or `SYMBOL.EXCHANGE` inputs; partial search text remains local-only.
