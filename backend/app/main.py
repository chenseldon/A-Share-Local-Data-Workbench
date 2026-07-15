from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .connectors.public_market import MarketDataError, fetch_public_market_snapshot, normalize_symbol
from .database import get_database_path, initialize_database
from .demo_data import seed_demo_data
from .modules import MODULES
from .repository import DataRepository


def should_remote_resolve(query: str) -> bool:
    value = query.strip().upper()
    return bool(re.fullmatch(r"\d{6}|\d{6}\.(SH|SZ|BJ)", value))


def create_app(db_path: Path | str | None = None) -> FastAPI:
    resolved_db_path = db_path or get_database_path()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        initialize_database(resolved_db_path)
        if os.getenv("ASHARE_DEMO_DATA", "").lower() in {"1", "true", "yes"}:
            seed_demo_data(resolved_db_path)
        yield

    app = FastAPI(title="A-Share Local Data Workbench API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_repository() -> DataRepository:
        return DataRepository(resolved_db_path)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "database": str(resolved_db_path)}

    @app.get("/api/modules")
    def modules() -> list[dict[str, object]]:
        return [
            {
                "id": module.id,
                "label": module.label,
                "layer": module.layer,
                "description": module.description,
                "status": module.status,
                "tables": list(module.tables),
                "sources": list(module.sources),
                "planned_fields": list(module.planned_fields),
            }
            for module in MODULES
        ]

    @app.get("/api/securities/search")
    def search_securities(
        q: str = "",
        limit: int = Query(default=20, ge=1, le=100),
        remote: bool = Query(default=True),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        rows = repository.search_securities(q, limit)
        remote_status = "not_needed"
        remote_error = None
        if remote and not rows and should_remote_resolve(q):
            try:
                normalized_symbol = normalize_symbol(q)
                snapshot = fetch_public_market_snapshot(normalized_symbol)
                repository.save_market_snapshot(snapshot)
                rows = repository.search_securities(normalized_symbol, limit)
                remote_status = "fetched" if rows else "not_collected"
            except (ValueError, MarketDataError) as exc:
                remote_status = "failed"
                remote_error = str(exc)
                repository.record_market_failure("public_market", str(exc))
        return {"query": q, "rows": rows, "remote_status": remote_status, "remote_error": remote_error}

    @app.get("/api/security/{symbol}/overview")
    def security_overview(
        symbol: str,
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        overview = repository.get_security_overview(symbol)
        if overview["security"] is None:
            raise HTTPException(status_code=404, detail=f"No local security found for {symbol.upper()}")
        return overview

    @app.post("/api/security/{symbol}/refresh")
    def refresh_security(
        symbol: str,
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        try:
            normalized_symbol = normalize_symbol(symbol)
            snapshot = fetch_public_market_snapshot(normalized_symbol)
            records_written = repository.save_market_snapshot(snapshot)
        except (ValueError, MarketDataError) as exc:
            repository.record_market_failure("public_market", str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "symbol": normalized_symbol,
            "status": "fresh",
            "records_written": records_written,
            "source": snapshot.security.source,
        }

    @app.get("/api/security/{symbol}/quote")
    def security_quote(
        symbol: str,
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        quote = repository.latest_market_quote(symbol)
        if quote is None:
            return {"symbol": symbol.upper(), "status": "not_collected", "quote": None}
        return {"symbol": symbol.upper(), "status": "fresh", "quote": quote}

    @app.get("/api/security/{symbol}/chart")
    def security_chart(
        symbol: str,
        period: str = Query(default="1d", pattern="^1d$"),
        adjustment: str = Query(default="none", pattern="^none$"),
        limit: int = Query(default=120, ge=1, le=500),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        rows = repository.chart_bars(symbol, limit=limit, adjustment=adjustment)
        return {
            "symbol": symbol.upper(),
            "period": period,
            "adjustment": adjustment,
            "status": "fresh" if rows else "not_collected",
            "rows": rows,
        }

    @app.get("/api/modules/{module_id}/data")
    def module_data(
        module_id: str,
        symbol: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        result = repository.get_module_data(module_id, symbol=symbol, limit=limit)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Unknown module: {module_id}")
        return result

    @app.get("/api/jobs")
    def jobs(
        limit: int = Query(default=50, ge=1, le=200),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        return {"rows": repository.list_jobs(limit)}

    @app.get("/api/data-sources/status")
    def source_status(repository: DataRepository = Depends(get_repository)) -> dict[str, object]:
        return {"rows": repository.list_source_health()}

    return app


app = create_app()
