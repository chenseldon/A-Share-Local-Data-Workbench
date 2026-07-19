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
- One-click dev start: `.\start_workbench.cmd`
- One-click dev start with labeled fixtures: `.\start_workbench.cmd -DemoData`
- Backend install: `cd backend && uv sync`
- Backend dev server: `python -m uvicorn app.main:app --app-dir backend --reload`
- Backend tests: `cd backend && uv run pytest`
- Frontend install: `cd frontend && npm install`
- Frontend dev server: `cd frontend && npm run dev`
- Frontend build: `cd frontend && npm run build`

## Data And Research Safety
- Distinguish `trade_date` from `fetched_at`; do not use fetch time as a market observation time.
- Mark missing, stale, failed, and not-yet-collected data explicitly.
- Fixtures and demo data must be labeled as fixtures and must not be presented as current market data.
- Backtest or signal outputs must never be framed as trade instructions.

## Sub-Agent Workflow
- Project-local sub-agent prompt templates live in `agents/*.toml`. They use Codex-compatible agent role TOML fields, but automatic loading from the project root has not been verified in this runtime; treat them as project-local templates unless Codex explicitly discovers them.
- Use `agents/backend.toml` for backend implementation: FastAPI routes, services, repositories, DuckDB schema initialization, connector wrappers, data cache writes, `source_health`, `data_jobs`, freshness states, API contracts, and backend tests.
- Use `agents/frontend.toml` for frontend implementation: React, Vite, TypeScript, Security View, Module View, System View, K-line workspace, indicators, drawing tools, dark theme, responsive layout, tables, API types, and browser visual validation.
- Use `agents/reviewer.toml` for read-only review. The reviewer must not edit files; it reports code quality, security, performance, data-semantics, API compatibility, error-handling, and test-coverage findings.
- Backend and frontend agents must run `git status --short --branch` before edits, preserve unrelated user changes, avoid destructive git commands, and validate their scoped changes before handoff.
- Reviewer output must be code-review style: findings first, ordered by severity, with file path, location, risk, impact, and recommended fix. If there are no blocking issues, it must state that clearly and list residual risks or test gaps.
- No agent may add trading, order routing, account access, broker permissions, fund transfer, secret storage, or UI that implies executable trade advice.

## Git
- Run `git status --short --branch` before scoped changes.
- Commit focused changes after validation when possible.
- Do not run destructive Git commands unless the user explicitly requests them.
