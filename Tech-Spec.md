# A-Share Local Data Workbench Technical Spec

## Architecture
- Frontend: React + Vite + TypeScript single-page application.
- Backend: FastAPI JSON API.
- Database: DuckDB file at `data/ashare.duckdb` by default. Run the backend from the project root so the local sandbox can write this file.
- Connectors: Python interfaces returning normalized records with raw payload hashes.

## API Contract
- `GET /api/health`
- `GET /api/modules`
- `GET /api/securities/search?q={query}&limit={limit}`
- `GET /api/security/{symbol}/overview`
- `GET /api/modules/{module}/data?symbol={symbol}&limit={limit}`
- `GET /api/jobs`
- `GET /api/data-sources/status`

## Freshness States
- `fresh`: source was collected and is within the module freshness window.
- `stale`: source exists but is older than expected.
- `failed`: latest collection failed.
- `not_collected`: no local data exists.

## Database Tables
- `securities`
- `trading_calendar`
- `market_bars`
- `fundamentals`
- `announcements`
- `reports`
- `money_flow`
- `limit_up_pool`
- `data_jobs`
- `source_health`

## Connector Contract
Each connector result must include:
- `source`
- `fetched_at`
- `status`
- `records`
- `raw_payload_hash`
- `error_message` when applicable

## Security And Risk Controls
- No credentials in source control.
- No broker or trading API integration in V1.
- External data is fetched by backend jobs and read from local storage by the UI.
- UI must label fixture data and stale data explicitly.

## Verification
- Python unit tests for API and repository behavior.
- TypeScript compilation and Vite build for frontend.
- Manual browser check for desktop and mobile layouts when dependencies are installed.
