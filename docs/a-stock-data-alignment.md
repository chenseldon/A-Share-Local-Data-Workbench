# a-stock-data V3.4.0 Alignment

`a-stock-data-main` is a local reference copy of `simonlin1212/a-stock-data`. It is a `SKILL.md` style source map with embedded Python snippets, not an installable Python package. This project ports selected public, read-only connectors into the FastAPI backend and keeps the upstream directory out of application imports.

## Source Priority

- Market data: free-stockdb local K-line is the only wired chart source for daily bars. Tencent quote remains the latest quote/valuation source; Baidu/Tencent K-line fallbacks are disabled for charts. `mootdx` is tracked as an optional dependency.
- Eastmoney: used for reportapi, stock profile, concept ownership and fund-flow endpoints. Calls go through a throttled helper.
- CNINFO: used for announcement search with dynamic `orgId` lookup and fallback rules.
- Sina: used for financial-statement records through the open API endpoint.
- iwencai: registered as `needs_key`; it is disabled unless `IWENCAI_API_KEY` is configured.

## Wired Functions

| Layer | Upstream function | Local behavior |
| --- | --- | --- |
| Market | `free_stockdb_kline` | Writes local `stockdb.exe` daily K-line rows into `market_bars` as `adjustment=qfq`. |
| Market | `free_stockdb_security` | Resolves complete six-digit code searches from the latest local free-stockdb K-line row and writes `securities`. |
| Market | `tencent_quote` | Writes latest quote and valuation fields into `market_quotes`. |
| Reports | `eastmoney_reports` | Writes company report metadata and PDF URLs into `reports`. |
| Signals | `eastmoney_concept_blocks` | Writes block ownership rows into `module_records`. |
| Chip/Liquidity | `stock_fund_flow_120d` | Writes daily fund-flow rows into `money_flow`. |
| Fundamentals | `eastmoney_stock_info` | Updates `securities` and `fundamentals` with profile and market-cap context. |
| Fundamentals | `sina_financial_report` | Writes statement records into `module_records`. |
| Announcements | `cninfo_announcements` | Writes announcement titles, timestamps and detail URLs into `announcements`. |

## API Surface

- `GET /api/connectors/capabilities` returns the full V3.4.0 function registry with `wired`, `planned`, `needs_key`, or `optional_dependency_missing`.
- `POST /api/modules/{module}/refresh?symbol=600519.SH` triggers a module-specific read-only collection job.
- `POST /api/security/{symbol}/refresh` refreshes market data by default. Passing `include_modules=true` also attempts fundamentals, reports, announcements, signals and fund flow; non-market failures are recorded in `source_health` and returned in `module_results`.

## Safety

All external responses are cached in DuckDB before the UI reads them. The workbench does not connect to broker accounts, does not route orders, and does not treat public-source refreshes as trading-grade real-time feeds.
