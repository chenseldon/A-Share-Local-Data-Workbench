# Project Memory

## Long-Term Context
- The project was initialized on 2026-07-14 as a local A-share research data workbench.
- V1 prioritizes local schema, API contracts, a high-density web workbench, and explicit data freshness states over broad live data coverage.
- `simonlin1212/a-stock-data` is treated as a connector reference and source map, not as application code to copy wholesale.

## Decisions
- Use FastAPI for the local API surface.
- Use DuckDB for the V1 local database because it is lightweight, file-based, and suitable for local research snapshots.
- Use React + Vite + TypeScript for the workbench UI.
- Keep all trading actions out of scope.
- Use `start_workbench.cmd` as the Windows one-click local dev launcher; it starts backend and frontend in separate terminal windows and defaults to no fixture data. Use `-DemoData` only for labeled fixture validation.
- V1.1 treats public market refresh as an explicit `POST /api/security/{symbol}/refresh` action; normal page loads read DuckDB cache first to reduce public-source request pressure.
- Use Tencent public endpoints for the first read-only quote/K-line connector and `lightweight-charts` for the TradingView-style local K-line panel.
- V1.2 aligns with the local `a-stock-data-main/SKILL.md` reference by porting selected public read-only functions into local connectors, not importing or committing the upstream folder as app code.
- Connector capability status is exposed through `/api/connectors/capabilities`; unsupported upstream functions are visible as `planned`, `needs_key`, or `optional_dependency_missing`.

## Data Notes
- Public web data sources can fail due to throttling, anti-scraping controls, schema drift, or source outages.
- All external data should be represented with `source`, `fetched_at`, and freshness state.
- Demo fixtures are allowed only for development and testing, and must be labeled as fixtures.
- Demo market bars remain available only under `-DemoData`; they are labeled `local_fixture` and are not current market data.
- Tencent quote fields include valuation and limit fields, but chart K-line rows are read only from local free-stockdb instead of Tencent/Baidu fallbacks.
- free-stockdb integration expects `stockdb.exe` on `127.0.0.1:7899` and `stock_sdk` installed in the backend Python environment. K-line rows are stored as `source=free_stockdb_kline` and `adjustment=qfq`; exact code searches can resolve securities from the latest local free-stockdb K-line row.
- Confirming a symbol in the search box triggers a market refresh plus best-effort fundamentals, announcements, reports, concept and fund-flow refreshes; module failures are recorded and shown instead of blocking the market chart.

## Secrets
- No secrets are stored in this project memory.
