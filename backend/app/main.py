from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .connectors.astock_sources import (
    AStockSourceError,
    cninfo_announcements,
    eastmoney_concept_blocks,
    eastmoney_reports,
    eastmoney_stock_info,
    normalize_eastmoney_report,
    sina_financial_report,
    stock_fund_flow_120d,
)
from .connectors.capabilities import capability_summary_by_module, list_capabilities
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
        capability_summary = capability_summary_by_module()
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
                "capabilities": capability_summary.get(module.id, {}),
            }
            for module in MODULES
        ]

    @app.get("/api/connectors/capabilities")
    def connector_capabilities() -> dict[str, object]:
        return {"rows": list_capabilities()}

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
        include_modules: bool = Query(default=False),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        try:
            normalized_symbol = normalize_symbol(symbol)
            snapshot = fetch_public_market_snapshot(normalized_symbol)
            records_written = repository.save_market_snapshot(snapshot)
        except (ValueError, MarketDataError) as exc:
            repository.record_market_failure("public_market", str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        optional_results = _refresh_core_modules(repository, normalized_symbol) if include_modules else {}
        return {
            "symbol": normalized_symbol,
            "status": "fresh",
            "records_written": records_written,
            "source": snapshot.security.source,
            "module_results": optional_results,
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
        adjustment: str = Query(default="auto", pattern="^(auto|none|qfq|hfq)$"),
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

    @app.post("/api/modules/{module_id}/refresh")
    def refresh_module(
        module_id: str,
        symbol: str | None = None,
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        if module_id not in {module.id for module in MODULES}:
            raise HTTPException(status_code=404, detail=f"Unknown module: {module_id}")
        normalized_symbol = normalize_symbol(symbol) if symbol else None
        try:
            result = _refresh_module(repository, module_id, normalized_symbol)
        except (ValueError, MarketDataError, AStockSourceError) as exc:
            source = _default_source_for_module(module_id)
            repository.record_source_failure(module_id, source, str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
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


def _refresh_core_modules(repository: DataRepository, symbol: str) -> dict[str, object]:
    results: dict[str, object] = {}
    for module_id in ("fundamentals", "reports", "announcements", "signals", "chip_liquidity"):
        try:
            results[module_id] = _refresh_module(repository, module_id, symbol)
        except (AStockSourceError, MarketDataError, ValueError) as exc:
            repository.record_source_failure(module_id, _default_source_for_module(module_id), str(exc))
            results[module_id] = {"status": "failed", "error": str(exc)}
    return results


def _refresh_module(repository: DataRepository, module_id: str, symbol: str | None) -> dict[str, object]:
    if module_id == "market":
        if not symbol:
            raise ValueError("Market refresh requires a symbol.")
        snapshot = fetch_public_market_snapshot(symbol)
        records_written = repository.save_market_snapshot(snapshot)
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": records_written}

    if module_id == "fundamentals":
        if not symbol:
            raise ValueError("Fundamentals refresh requires a symbol.")
        fetched_at = datetime.now(UTC)
        info = eastmoney_stock_info(symbol)
        records_written = repository.save_eastmoney_stock_info(symbol, info, fetched_at)
        statement_records = []
        for report_type in ("lrb", "fzb", "llb"):
            try:
                statement_records.extend(sina_financial_report(symbol, report_type=report_type, num=4))
            except AStockSourceError as exc:
                repository.record_source_failure("fundamentals", f"sina_financial_report:{report_type}", str(exc))
        records_written += repository.save_module_records(statement_records)
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": records_written}

    if module_id == "reports":
        if not symbol:
            raise ValueError("Reports refresh requires a symbol.")
        fetched_at = datetime.now(UTC)
        reports = [normalize_eastmoney_report(symbol, record, fetched_at) for record in eastmoney_reports(symbol, max_pages=1)]
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": repository.save_reports(reports)}

    if module_id == "announcements":
        if not symbol:
            raise ValueError("Announcements refresh requires a symbol.")
        fetched_at = datetime.now(UTC)
        announcements = cninfo_announcements(symbol, page_size=30)
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": repository.save_announcements(announcements, fetched_at)}

    if module_id == "signals":
        if not symbol:
            raise ValueError("Signals refresh requires a symbol.")
        records = eastmoney_concept_blocks(symbol)
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": repository.save_module_records(records)}

    if module_id == "chip_liquidity":
        if not symbol:
            raise ValueError("Chip and liquidity refresh requires a symbol.")
        fetched_at = datetime.now(UTC)
        rows = stock_fund_flow_120d(symbol)
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": repository.save_money_flow(rows, fetched_at)}

    return {"module": module_id, "symbol": symbol, "status": "not_configured", "records_written": 0}


def _default_source_for_module(module_id: str) -> str:
    return {
        "market": "public_market",
        "fundamentals": "eastmoney_stock_info",
        "reports": "eastmoney_reports",
        "announcements": "cninfo_announcements",
        "signals": "eastmoney_concept_blocks",
        "chip_liquidity": "stock_fund_flow_120d",
    }.get(module_id, "not_configured")
