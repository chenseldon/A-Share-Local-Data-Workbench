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

This starts the FastAPI backend and Vite frontend in separate terminal windows, enables labeled fixture data by default, and opens `http://127.0.0.1:5173`.

To start without fixture rows:

```powershell
.\start_workbench.cmd -NoDemoData
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
- `GET /api/securities/search`
- `GET /api/security/{symbol}/overview`
- `GET /api/modules/{module}/data`
- `GET /api/jobs`
- `GET /api/data-sources/status`

## Data Safety
- `trade_date` and `fetched_at` are separate fields.
- Missing, stale, failed, and not collected states are explicit.
- Public web sources may throttle, drift, or fail. Treat connectors as research infrastructure, not guaranteed real-time feeds.
