# A-Share Local Data Workbench

Local A-share financial data workbench for research, cache-backed inspection, and connector development.

This is not a trading system. It does not place orders, read broker accounts, or provide unconditional trading instructions.

## Stack
- Frontend: React + Vite + TypeScript
- Backend: FastAPI
- Database: DuckDB

## Quick Start

One-click local start on Windows:

```powershell
.\start_workbench.cmd
```

This starts the FastAPI backend and Vite frontend in separate terminal windows, does not seed fixture data by default, clears old `local_fixture` rows, and opens `http://127.0.0.1:5173`.

To start with labeled fixture rows:

```powershell
.\start_workbench.cmd -DemoData
```

Backend:

```bash
cd backend
uv sync
cd ..
uv run uvicorn app.main:app --app-dir backend --reload
```

If `uv` is not installed but the Python dependencies already exist, run:

```bash
python -m uvicorn app.main:app --app-dir backend --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to override it.

## Optional Demo Data

The backend does not seed demo rows by default. To start with labeled fixture data:

```bash
$env:ASHARE_DEMO_DATA="1"
python -m uvicorn app.main:app --app-dir backend --reload
```

Fixture rows are marked with `source = local_fixture` and are not current market data.

## API
- `GET /api/health`
- `GET /api/modules`
- `GET /api/connectors/capabilities`
- `GET /api/securities/search`
- `GET /api/security/{symbol}/overview`
- `POST /api/security/{symbol}/refresh`
- `GET /api/security/{symbol}/quote`
- `GET /api/security/{symbol}/chart`
- `GET /api/modules/{module}/data`
- `POST /api/modules/{module}/refresh`
- `GET /api/jobs`
- `GET /api/data-sources/status`

## a-stock-data Alignment

The local `a-stock-data-main` folder is a reference copy of `simonlin1212/a-stock-data`. It is not imported as an application package. Selected read-only functions are ported into backend connectors and tracked through `GET /api/connectors/capabilities`.

## Local free-stockdb

Daily K-line data is read from local `free-stockdb` when `stockdb.exe` is running on `127.0.0.1:7899` and `stock_sdk` is installed in the backend Python environment. The workbench stores those rows in DuckDB as `source = free_stockdb_kline` and `adjustment = qfq`. Tencent remains a latest quote and valuation source; K-line chart rows do not fall back to Tencent/Baidu example data.

The chart indicator library uses the local `zhibiao.zb.get()` SDK on demand. MA is enabled by default; MACD, KDJ, RSI and BOLL are only requested after the user enables them in the chart menu. `NaN` and infinite SDK values are returned as JSON `null`.

Board and concept mapping uses `zhibiao.bk.get()`. Concepts and Shenwan level 1/2/3 industry mappings are shown in the chart header, and Shenwan level 1 is written back to `securities.sector` when available.

Security search reads the local DuckDB securities directory built from free-stockdb. Run `POST /api/securities/universe/refresh` or use the app startup refresh to scan the supported A-share and ETF prefixes. The previous 7,034-symbol scan was incomplete; the refreshed prefix set targets the README-stated 7,400+ universe, and local validation found 7,860 candidates after adding ETF/fund prefixes. Typing a code or Chinese name returns up to five candidates. Market/module collection starts only after selecting a candidate or pressing refresh.

## Data Safety
- `trade_date` and `fetched_at` are separate fields.
- Missing, stale, failed, and not collected states are explicit.
- Public web sources may throttle, drift, or fail. Treat connectors as research infrastructure, not guaranteed real-time feeds.
