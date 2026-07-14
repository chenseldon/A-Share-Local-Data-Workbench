# A-Share Local Data Workbench PRD

## Objective
Build a local web workbench that turns a ten-layer A-share data architecture into browseable, searchable, cache-backed research surfaces.

## Users
- Primary user: an A-share focused trader or researcher who needs fast local inspection of market, fundamental, announcement, report, and signal data.
- Secondary user: an engineering agent or developer extending data connectors and database coverage.

## V1 Scope
- Module View: browse data by ten-layer architecture.
- Security View: inspect one security across local market, fundamental, announcement, report, and money-flow context.
- System View: inspect source health, job status, freshness, and failures.
- Local API and DuckDB schema for the first research database layer.
- Clear empty states for modules that are not collected yet.

## V1 Data Modules
- Connected in schema and UI: market, fundamentals, announcements, reports.
- Prepared in schema and UI: money flow and limit-up pool.
- Navigation-only for later expansion: news, signal, chip/liquidity, ETF options, sentiment/interaction.

## Out Of Scope
- Live order placement, cancellation, allocation, broker account access, or fund transfer.
- Production-grade real-time market data guarantees.
- Full historical backfill of all A-share securities.
- Backtest engine and strategy execution.
- Undisclosed API keys or paid data provider integrations.

## Acceptance Criteria
- User can run backend and frontend locally.
- User can search local securities.
- User can open Security View and see explicit local data or empty states.
- User can browse the ten module groups.
- System View shows data source and job health.
- API responses expose source and freshness metadata.
- Tests cover API schema, connector result shape, database idempotency, and failure/empty states.
