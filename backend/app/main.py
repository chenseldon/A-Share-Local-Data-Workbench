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
    eastmoney_dragon_tiger_board,
    eastmoney_fund_flow_minute,
    eastmoney_industry_comparison,
    eastmoney_industry_reports,
    eastmoney_reports,
    eastmoney_stock_info,
    normalize_eastmoney_stock_profile,
    normalize_eastmoney_industry_report,
    normalize_eastmoney_report,
    sina_financial_report,
    stock_fund_flow_120d,
)
from .connectors.capabilities import capability_summary_by_module, list_capabilities
from .connectors.public_market import (
    FREE_STOCKDB_EXPECTED_SOURCE_COUNT,
    FREE_STOCKDB_INDICATOR_CONFIG,
    FREE_STOCKDB_UNIVERSE_PREFIXES,
    MarketDataError,
    MarketBar,
    fetch_free_stockdb_board_mapping,
    fetch_free_stockdb_bars,
    fetch_free_stockdb_indicators,
    fetch_free_stockdb_security,
    fetch_free_stockdb_security_universe,
    fetch_public_market_snapshot,
    normalize_symbol,
)
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
        else:
            DataRepository(resolved_db_path).delete_fixture_data()
        yield

    app = FastAPI(title="A-Share Local Data Workbench API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://[::1]:5173",
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
        limit: int = Query(default=5, ge=1, le=20),
        remote: bool = Query(default=False),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        rows = repository.search_securities(q, limit)
        remote_status = "not_needed"
        remote_error = None
        if remote and not rows and should_remote_resolve(q):
            try:
                normalized_symbol = normalize_symbol(q)
                security = fetch_free_stockdb_security(normalized_symbol)
                repository.save_security(security)
                rows = repository.search_securities(normalized_symbol, limit)
                remote_status = "fetched" if rows else "not_collected"
            except (ValueError, MarketDataError) as exc:
                remote_status = "failed"
                remote_error = str(exc)
                repository.record_market_failure("free_stockdb_security", str(exc))
        return {"query": q, "rows": rows, "remote_status": remote_status, "remote_error": remote_error}

    @app.get("/api/securities/universe/status")
    def securities_universe_status(repository: DataRepository = Depends(get_repository)) -> dict[str, object]:
        return repository.security_universe_status()

    @app.post("/api/securities/universe/refresh")
    def refresh_securities_universe(repository: DataRepository = Depends(get_repository)) -> dict[str, object]:
        try:
            securities = fetch_free_stockdb_security_universe()
            records_written = repository.save_securities(securities)
            repository.record_source_success("market", "free_stockdb_universe", records_written)
        except MarketDataError as exc:
            repository.record_market_failure("free_stockdb_universe", str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "status": "fresh",
            "records_written": records_written,
            "candidates_scanned": len(FREE_STOCKDB_UNIVERSE_PREFIXES) * 1000,
            "prefixes_scanned": len(FREE_STOCKDB_UNIVERSE_PREFIXES),
            "expected_source_count": FREE_STOCKDB_EXPECTED_SOURCE_COUNT,
            "source": "free_stockdb_universe",
        }

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
            try:
                boards = fetch_free_stockdb_board_mapping(normalized_symbol)
                repository.update_security_sector(
                    normalized_symbol,
                    boards.sw_l1[0] if boards.sw_l1 else None,
                    boards.source,
                    boards.fetched_at,
                )
                repository.record_source_success("signals", boards.source, 1)
            except MarketDataError as exc:
                repository.record_source_failure("signals", "free_stockdb_bk", str(exc))
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
        period: str = Query(default="1d", pattern="^(1m|5m|15m|30m|60m|1d|1w|1M)$"),
        adjustment: str = Query(default="auto", pattern="^(auto|none|qfq|hfq)$"),
        limit: int = Query(default=2000, ge=1, le=2000),
        indicators: str | None = Query(default=None),
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        try:
            normalized_symbol = normalize_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            bars = fetch_free_stockdb_bars(
                normalized_symbol,
                limit=limit,
                frequency=period,
                fq=_indicator_adjustment(adjustment) or None,
            )
            rows = _market_bars_to_chart_rows(bars)
            _append_moving_averages(rows)
        except MarketDataError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        requested_indicators = _parse_indicators(indicators)
        indicator_status = "not_requested"
        indicator_error = None
        if requested_indicators and rows:
            try:
                indicator_rows = fetch_free_stockdb_indicators(
                    normalized_symbol,
                    requested_indicators,
                    start=_chart_boundary(rows, 0, period),
                    end=_chart_boundary(rows, -1, period),
                    frequency=period,
                    fq=_indicator_adjustment(adjustment),
                )
                _merge_indicator_rows(rows, indicator_rows, requested_indicators)
                indicator_status = "fresh"
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except MarketDataError as exc:
                indicator_status = "failed"
                indicator_error = str(exc)
        return {
            "symbol": normalized_symbol,
            "period": period,
            "adjustment": adjustment,
            "status": "fresh" if rows else "not_collected",
            "rows": rows,
            "requested_indicators": list(requested_indicators),
            "indicator_status": indicator_status,
            "indicator_error": indicator_error,
        }

    @app.get("/api/security/{symbol}/boards")
    def security_boards(
        symbol: str,
        repository: DataRepository = Depends(get_repository),
    ) -> dict[str, object]:
        try:
            normalized_symbol = normalize_symbol(symbol)
            boards = fetch_free_stockdb_board_mapping(normalized_symbol)
        except (ValueError, MarketDataError) as exc:
            repository.record_source_failure("signals", "free_stockdb_bk", str(exc))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        repository.update_security_sector(
            normalized_symbol,
            boards.sw_l1[0] if boards.sw_l1 else None,
            boards.source,
            boards.fetched_at,
        )
        repository.record_source_success("signals", boards.source, 1)
        return {
            "symbol": boards.symbol,
            "concepts": boards.concepts,
            "sw_l1": boards.sw_l1,
            "sw_l2": boards.sw_l2,
            "sw_l3": boards.sw_l3,
            "source": boards.source,
            "fetched_at": boards.fetched_at,
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
        records_written += repository.save_module_records([normalize_eastmoney_stock_profile(symbol, info, fetched_at)])
        statement_records = []
        for report_type in ("lrb", "fzb", "llb"):
            try:
                records = sina_financial_report(symbol, report_type=report_type, num=4)
                repository.record_source_success("fundamentals", f"sina_financial_report:{report_type}", len(records))
                statement_records.extend(records)
            except AStockSourceError as exc:
                repository.record_source_failure("fundamentals", f"sina_financial_report:{report_type}", str(exc))
        records_written += repository.save_module_records(statement_records)
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": records_written}

    if module_id == "reports":
        if not symbol:
            raise ValueError("Reports refresh requires a symbol.")
        fetched_at = datetime.now(UTC)
        reports = [normalize_eastmoney_report(symbol, record, fetched_at) for record in eastmoney_reports(symbol, max_pages=1)]
        records_written = repository.save_reports(reports)
        if not reports:
            repository.record_source_success("reports", "eastmoney_reports", 0)
        optional_results: dict[str, object] = {}
        try:
            industry_records = [
                normalize_eastmoney_industry_report(symbol, record, fetched_at)
                for record in eastmoney_industry_reports(industry_code="*", max_pages=1)
            ]
            industry_written = repository.save_module_records(industry_records)
            if not industry_records:
                repository.record_source_success("reports", "eastmoney_industry_reports", 0)
            optional_results["eastmoney_industry_reports"] = {
                "status": "fresh",
                "records_written": industry_written,
            }
            records_written += industry_written
        except AStockSourceError as exc:
            repository.record_source_failure("reports", "eastmoney_industry_reports", str(exc))
            optional_results["eastmoney_industry_reports"] = {"status": "failed", "error": str(exc)}
        return {
            "module": module_id,
            "symbol": symbol,
            "status": "fresh",
            "records_written": records_written,
            "optional_results": optional_results,
        }

    if module_id == "announcements":
        if not symbol:
            raise ValueError("Announcements refresh requires a symbol.")
        fetched_at = datetime.now(UTC)
        announcements = cninfo_announcements(symbol, page_size=30)
        return {"module": module_id, "symbol": symbol, "status": "fresh", "records_written": repository.save_announcements(announcements, fetched_at)}

    if module_id == "signals":
        if not symbol:
            raise ValueError("Signals refresh requires a symbol.")
        records_written = 0
        optional_results: dict[str, object] = {}
        fetchers = (
            ("eastmoney_concept_blocks", lambda: eastmoney_concept_blocks(symbol)),
            ("eastmoney_fund_flow_minute", lambda: eastmoney_fund_flow_minute(symbol)),
            ("eastmoney_dragon_tiger_board", lambda: eastmoney_dragon_tiger_board(symbol)),
            ("eastmoney_industry_comparison", lambda: eastmoney_industry_comparison(symbol)),
        )
        for source, fetcher in fetchers:
            try:
                records = fetcher()
                written = repository.save_module_records(records)
                if not records:
                    repository.record_source_success("signals", source, 0)
                records_written += written
                optional_results[source] = {"status": "fresh", "records_written": written}
            except AStockSourceError as exc:
                repository.record_source_failure("signals", source, str(exc))
                optional_results[source] = {"status": "failed", "error": str(exc)}
        status = "fresh" if any(result.get("status") == "fresh" for result in optional_results.values() if isinstance(result, dict)) else "failed"
        return {
            "module": module_id,
            "symbol": symbol,
            "status": status,
            "records_written": records_written,
            "optional_results": optional_results,
        }

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


def _parse_indicators(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    indicators: list[str] = []
    for item in value.split(","):
        key = item.strip().lower()
        if not key:
            continue
        if key not in FREE_STOCKDB_INDICATOR_CONFIG and key != "volume":
            raise HTTPException(status_code=400, detail=f"Unsupported chart indicator: {item}")
        if key != "volume" and key not in indicators:
            indicators.append(key)
    return tuple(indicators)


def _market_bars_to_chart_rows(bars: tuple[MarketBar, ...]) -> list[dict[str, object]]:
    return [
        {
            "symbol": bar.symbol,
            "trade_date": bar.trade_date,
            "chart_time": bar.chart_time,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "amount": bar.amount,
            "adjustment": bar.adjustment,
            "source": bar.source,
            "fetched_at": bar.fetched_at,
        }
        for bar in bars
    ]


def _append_moving_averages(rows: list[dict[str, object]]) -> None:
    closes: list[float | None] = []
    for row in rows:
        close = row.get("close")
        closes.append(float(close) if isinstance(close, (int, float)) else None)
        row["ma5"] = _moving_average(closes, 5)
        row["ma10"] = _moving_average(closes, 10)
        row["ma20"] = _moving_average(closes, 20)


def _moving_average(values: list[float | None], window: int) -> float | None:
    if len(values) < window:
        return None
    sample = values[-window:]
    if any(value is None for value in sample):
        return None
    return round(sum(value for value in sample if value is not None) / window, 4)


def _chart_boundary(rows: list[dict[str, object]], index: int, period: str) -> str | None:
    if not rows:
        return None
    value = rows[index].get("trade_date")
    if value is None:
        return None
    text = str(value)
    if period.endswith("m"):
        return text.replace("-", "").replace(":", "").replace(" ", "")[:14]
    return text[:10].replace("-", "")


def _indicator_adjustment(adjustment: str) -> str | None:
    if adjustment == "auto":
        return "qfq"
    if adjustment == "none":
        return None
    return adjustment


def _merge_indicator_rows(
    rows: list[dict[str, object]],
    indicator_rows: dict[str, dict[str, object]],
    requested_indicators: tuple[str, ...] = (),
) -> None:
    ordered_indicator_values = [values for _, values in sorted(indicator_rows.items(), key=lambda item: item[0])]
    expected_fields = _requested_indicator_fields(requested_indicators, ordered_indicator_values)
    positional_fallback = len(ordered_indicator_values) == len(rows)

    for index, row in enumerate(rows):
        trade_date = row.get("trade_date")
        if trade_date is None:
            continue
        values = indicator_rows.get(str(trade_date)) or indicator_rows.get(str(trade_date)[:10])
        if values is None and positional_fallback:
            values = ordered_indicator_values[index]
        if values:
            row.update(values)
        for field in expected_fields:
            row.setdefault(field, None)


def _requested_indicator_fields(
    requested_indicators: tuple[str, ...],
    indicator_values: list[dict[str, object]],
) -> set[str]:
    fields = {key for values in indicator_values for key in values.keys()}
    default_fields: dict[str, set[str]] = {
        "ma": {"ma5", "ma10", "ma20"},
        "ema": {"ema5", "ema10", "ema20", "ema"},
        "sma": {"sma5", "sma10", "sma20", "sma"},
        "wma": {"wma5", "wma10", "wma20", "wma"},
        "dma": {"dma10", "dma"},
        "std": {"std20", "std"},
        "sum": {"sum20", "sum"},
        "hhv": {"hhv20", "hhv"},
        "llv": {"llv20", "llv"},
        "ref": {"ref1", "ref"},
        "macd": {"dif", "dea", "macd"},
        "kdj": {"k", "d", "j"},
        "rsi": {"rsi", "rsi6", "rsi12", "rsi24"},
        "boll": {"upper", "mid", "lower"},
    }
    for indicator in requested_indicators:
        fields.update(default_fields.get(indicator.lower(), set()))
    return fields
