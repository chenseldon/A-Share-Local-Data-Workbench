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
- Project-level sub-agent prompts are kept as root `agents/*.toml` templates using Codex-compatible agent role fields. Automatic discovery from the project root has not been verified, so the files should be treated as project-local templates unless the runtime explicitly loads them.
- Use `start_workbench.cmd` as the Windows one-click local dev launcher; it starts backend and frontend in separate terminal windows and defaults to no fixture data. Use `-DemoData` only for labeled fixture validation.
- V1.1 treats public market refresh as an explicit `POST /api/security/{symbol}/refresh` action; normal page loads read DuckDB cache first to reduce public-source request pressure.
- Use Tencent public endpoints for the first read-only quote/K-line connector and `lightweight-charts` for the TradingView-style local K-line panel.
- V1.2 aligns with the local `a-stock-data-main/SKILL.md` reference by porting selected public read-only functions into local connectors, not importing or committing the upstream folder as app code.
- Connector capability status is exposed through `/api/connectors/capabilities`; unsupported upstream functions are visible as `planned`, `needs_key`, or `optional_dependency_missing`.

## Data Notes
- Public web data sources can fail due to throttling, anti-scraping controls, schema drift, or source outages.
- All external data should be represented with `source`, `fetched_at`, and freshness state.
- Demo fixtures are allowed only for development and testing, and must be labeled as fixtures.
- Demo market bars remain available only under `-DemoData`; they are labeled `local_fixture` and are not current market data. Default startup purges existing `local_fixture` rows so old demo rows do not leak into normal use.
- Tencent quote fields include valuation and limit fields, but chart K-line rows are read only from local free-stockdb instead of Tencent/Baidu fallbacks.
- free-stockdb integration expects `stockdb.exe` on `127.0.0.1:7899` and `stock_sdk` installed in the backend Python environment. K-line rows are stored as `source=free_stockdb_kline` and `adjustment=qfq`; on-demand indicators use `zhibiao.zb.get()` and do not persist calculated rows.
- free-stockdb board mapping uses `zhibiao.bk.get()` for concepts and Shenwan level 1/2/3. Shenwan level 1 is the preferred `securities.sector` value when present.
- K-line UI follows a TradingView-style split: candles, volume and overlay indicators stay in the main chart; oscillator/technical indicators such as MACD, RSI and KDJ render in separate panes to avoid lightweight-charts price-scale crashes.
- The chart indicator menu exposes 38 single-security `zb.get()` technical indicators plus the built-in volume toggle. `zhishu` remains a basket/index calculation capability and is not shown as a single-stock chart overlay.
- The search directory is built through `/api/securities/universe/refresh` by scanning supported A-share and ETF prefixes in free-stockdb. The old observed 7,034-symbol directory was incomplete; the refreshed scan targets 7,400+ and the 2026-07-17 local SDK scan found 7,860 candidates across 61 prefixes after adding 160-169, 501/502/506/508/520/526/530/551, 560-563 and 589.
- Selecting a search candidate or pressing the top refresh button triggers market refresh plus best-effort fundamentals, announcements, reports, signals and chip/liquidity refresh. Slow or failed sources surface in the centered progress/toast flow rather than blocking silently.
- Security View now keeps symbol search and the full refresh action inside the K-line header, removes the separate topbar for that view, and uses a dark scrollable workspace with the quote/freshness/detail panels restored below the chart.
- K-line drawing tools are front-end session state only. Cursor mode leaves chart drag/zoom behavior available; drawing modes write SVG overlay objects against main-chart time and price coordinates and do not persist to DuckDB.
- Security View no longer defaults to `600519.SH` on first load. It starts from a dark symbol-search landing screen, then enters the K-line workspace only after the user selects a local free-stockdb candidate.
- Chart periods use free-stockdb native frequencies only: `1m`, `5m`, `15m`, `30m`, `60m`, `1d`, `1w`, and `1M`; `4h` is intentionally not shown because the local SDK does not expose it as a native period.
- Weekly and monthly K-line indicators are kept enabled. free-stockdb may return indicator dates at period starts while aggregated K-line bars use period-end dates, so the backend merges indicators by exact date first and falls back to sorted positional alignment when row counts match.
- Security View chart legends show the hovered bar's OHLCV and selected indicator values, and the custom front-end crosshair overlay spans the main chart plus indicator panes.
- Browser access remains local-only through `http://127.0.0.1:5173/`. CORS includes localhost IPv4 and IPv6, and `start_workbench.ps1` checks `/api/health` when port 8000 is already occupied to distinguish a reusable backend from a stale conflicting process.
- Empty Security View overview states now expose a `Refresh and reload` recovery action that reuses the full symbol refresh flow instead of requiring a browser reload.
- The Market module is treated as a dark-theme, current-symbol market workspace with K-line, period switching, quote snapshot, source context, and explicit `Not configured` placeholders for unimplemented order-book/index/ETF capabilities.
- K-line chart requests now default to the latest 2,000 bars for every supported free-stockdb native period. The backend chart API accepts `limit=2000`; the UI does not currently expose full-history loading or lazy backfill.
- K-line charts load 2,000 rows but initialize the visible logical range to the latest 500 rows when enough data is available. Indicator toggles preserve the current visible range for the same symbol/period dataset.
- The Market module now returns a structured `market` payload from `/api/modules/market/data`, with quote snapshot, valuation, price-limit, liquidity, order-book status, index/ETF status, and market source status. K-line data still comes from free-stockdb; mootdx order book remains an optional capability unless the dependency/runtime is enabled.
- Market module numeric panels show source and fetch time in section headers instead of value cards. Index/ETF support is currently a quick-entry workflow that switches symbols through the existing loader, not a full index/ETF browser. mootdx is not installed by default, so five-level order book remains `optional_dependency_missing`.
- The Research Reports module now exposes a structured dark-theme `reports` payload from `/api/modules/reports/data`, with dynamic sections, company report rows, industry report rows, PDF URLs generated from Eastmoney `infoCode`, and explicit source statuses for Eastmoney, optional 10jqka EPS, and iwencai key availability.
- Eastmoney reportapi remains the primary reports source. Company reports use `qType=0`; industry reports use `qType=1` as a latest-page V1 feed because precise stock-to-Eastmoney-industry-code filtering is not implemented yet.
- The Signals module now exposes a structured dark-theme `signals` payload from `/api/modules/signals/data`, with dynamic sections, Eastmoney concept/block ownership, current-symbol minute fund flow, dragon-tiger records/seats, industry ranking, and explicit source statuses.
- Signals V1 treats Eastmoney concept blocks, Eastmoney minute fund flow, Eastmoney dragon-tiger board, Eastmoney industry comparison, and free-stockdb board mapping as wired/read-only sources. Northbound flow remains a prepared boundary because Shenzhen Connect minute disclosure became less reliable after 2024-08; 10jqka hot reason remains planned until its endpoint is revalidated.
- The News module now exposes a structured dark-theme `news` payload from `/api/modules/news/data`, with Eastmoney current-symbol stock news, CLS telegraphs, Eastmoney global 7x24 news, dynamic sections/tables, and explicit source statuses.
- News V1 treats Eastmoney stock news, CLS telegraph and Eastmoney global news as wired/read-only sources. CLS uses a local `md5(sha1(sorted query string))` signature with no key; CLS and Eastmoney global news are market-wide context and remain visible in symbol-scoped News views. Eastmoney news calls still use the throttled helper because public endpoints can be IP-throttled or drift.
- The Announcements module now exposes a structured dark-theme `announcements` payload from `/api/modules/announcements/data`, with CNINFO announcement sections, clickable disclosure rows, and explicit source statuses.
- Announcements V1 treats CNINFO full-text disclosure search as the wired primary source with dynamic `orgId` lookup. mootdx F10 latest tips remains `optional_dependency_missing`; the `a-stock-data` backup route (SZSE official for Shenzhen tickers, Eastmoney PDF announcements for Shanghai tickers) is registered as `prepared` but is not used as the default source.
- The Chip/Liquidity module now exposes a structured dark-theme `chip_liquidity` payload from `/api/modules/chip_liquidity/data`, with dynamic sections for margin financing, block trades, holder count/chip concentration, dividends, 120-day fund flow, and explicit source statuses.
- Chip/Liquidity V1 treats Eastmoney datacenter margin trading, block trades, holder count, dividend history, and Eastmoney push2his 120-day fund flow as wired/read-only sources. Sina fund-flow backup is prepared but not wired. Eastmoney datacenter/push2his can be IP-throttled, so source failures must be displayed without pretending data is current.
- The ETF Options module now exposes a structured dark-theme `etf_options` payload from `/api/modules/etf_options/data`, with Sina ETF option contract chains, near-month T-quotes, Greeks/IV tables, and explicit source statuses.
- ETF Options V1 treats Sina hq.sinajs as the read-only primary source for 50ETF, 300ETF, STAR 50 ETF and 500ETF option chains. Greeks and IV are source-provided; the app does not calculate BSM values, does not download files, and does not provide option strategy/trading execution.
- Windows backend environments require `tzdata` for `ZoneInfo("Asia/Shanghai")`; it is now a declared backend dependency to keep tests and local runtime reproducible.
- The integrated worktree branch combines Fundamentals, Limit-Up Board, ETF Options, and Sentiment module work. `/api/modules/{module_id}/data` can now return structured `fundamentals`, `limit_up`, `etf_options`, and `sentiment` payloads alongside the earlier module payloads.
- Global UI defaults are now dark theme tokens. Module, System, topbar, table, empty-state, toast, progress, and fallback surfaces should render against dark backgrounds by default; Security and K-line keep their specialized dark workspace layout.
- Limit-Up Board refresh is market/date scoped and accepts `trade_date`; it should not be treated as a normal single-symbol background refresh.
- Local development CORS allows localhost/127.0.0.1/[::1] ports so Vite fallback ports can call the backend during UI QA without loosening access to non-local origins.

## Secrets
- No secrets are stored in this project memory.
