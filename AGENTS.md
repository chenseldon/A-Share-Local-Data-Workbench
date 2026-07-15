# Project Instructions

## Purpose
This project is a local A-share financial data workbench for research, data inspection, and reproducible local caching. It is not a trading system and must not place, cancel, or route live orders.

## Default Workflow
- Keep changes scoped to the current task.
- Prefer simple, inspectable data flows over clever abstractions.
- External market data must be cached locally before it is shown in the UI.
- Every displayed data point should carry source, fetch time, and freshness state when practical.
- Never store secrets, API keys, tokens, broker credentials, account IDs, or private trading information in code, docs, logs, fixtures, or snapshots.

## Stack
- Frontend: React, Vite, TypeScript.
- Backend: Python, FastAPI, DuckDB.
- Data layer: connector interface inspired by `simonlin1212/a-stock-data`; do not copy the upstream `SKILL.md` wholesale into application code.
- Package preference: use `uv` for Python when available; use npm for the Vite frontend unless a lockfile later establishes another package manager.

## Commands
- Backend install: `cd backend && uv sync`
- Backend dev server: `python -m uvicorn app.main:app --app-dir backend --reload`
- Backend tests: `cd backend && uv run pytest`
- Frontend install: `cd frontend && npm install`
- Frontend dev server: `cd frontend && npm run dev`
- Frontend build: `cd frontend && npm run build`
- Docker config check: `docker compose config`
- Docker build: `docker compose build`
- Docker run: `docker compose up --build`
- Docker demo run: `docker compose --env-file .env.docker.example up --build`
- Docker stop: `docker compose down`

## Data And Research Safety
- Distinguish `trade_date` from `fetched_at`; do not use fetch time as a market observation time.
- Mark missing, stale, failed, and not-yet-collected data explicitly.
- Fixtures and demo data must be labeled as fixtures and must not be presented as current market data.
- Backtest or signal outputs must never be framed as trade instructions.
- Docker images must not bake in local DuckDB files or research data; use the `ashare-data` volume.

## Git
- Run `git status --short --branch` before scoped changes.
- Commit focused changes after validation when possible.
- Do not run destructive Git commands unless the user explicitly requests them.
