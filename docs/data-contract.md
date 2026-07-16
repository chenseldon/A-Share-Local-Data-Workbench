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
- `GET /api/security/{symbol}/chart?period=1d&adjustment=auto` reads cached daily bars and returns `ma5`, `ma10`, and `ma20`; `auto` prefers local free-stockdb `qfq`, then falls back only to other locally cached adjustments.
- `GET /api/securities/search?q=...` may resolve only complete six-digit symbols or `SYMBOL.EXCHANGE` inputs through local free-stockdb; partial code/name search remains local-cache-only.

## a-stock-data Alignment API
- `GET /api/connectors/capabilities` returns the V3.4.0 connector registry and distinguishes `wired`, `planned`, `needs_key`, and `optional_dependency_missing`.
- `POST /api/modules/{module}/refresh?symbol=...` triggers a read-only module collection job and records success/failure in `data_jobs` and `source_health`.
- Heterogeneous records from statement, concept, sentiment, option, and future module connectors can be cached in `module_records` with source metadata and a JSON payload.

## Local free-stockdb K-line
- `free_stockdb_kline` reads from `stockdb.exe` on `127.0.0.1:7899` through `StockDBClient`.
- Codes are normalized to six digits before querying, preserving leading zeroes.
- Default local K-line request uses `frequency=1d`, `fq=qfq`, and fields `date,code,name,open,high,low,close,volume,amount,pct_chg`.
- K-line charts do not fall back to Tencent, Baidu, or fixture rows unless fixtures were explicitly seeded with `-DemoData`.
