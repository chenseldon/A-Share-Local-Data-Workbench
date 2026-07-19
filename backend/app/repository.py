from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import connect, initialize_database
from .connectors.astock_sources import ModuleRecord, payload_hash
from .connectors.public_market import MarketSnapshot, ResolvedSecurity
from .modules import MODULE_BY_ID


class DataRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        initialize_database(self.db_path)

    def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        connection = connect(self.db_path)
        try:
            cursor = connection.execute(query, params)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            connection.close()

    def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

    def save_security(self, security: ResolvedSecurity) -> int:
        connection = connect(self.db_path)
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO securities
                (symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at)
                VALUES (?, ?, ?, ?, NULL, COALESCE(?, (SELECT sector FROM securities WHERE symbol = ?)), true, ?, ?)
                """,
                (
                    security.symbol,
                    security.name,
                    security.exchange,
                    security.asset_type,
                    security.sector,
                    security.symbol,
                    security.source,
                    security.fetched_at,
                ),
            )
            return 1
        finally:
            connection.close()

    def save_securities(self, securities: tuple[ResolvedSecurity, ...]) -> int:
        if not securities:
            return 0
        connection = connect(self.db_path)
        try:
            connection.executemany(
                """
                INSERT OR REPLACE INTO securities
                (symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at)
                VALUES (?, ?, ?, ?, NULL, COALESCE(?, (SELECT sector FROM securities WHERE symbol = ?)), true, ?, ?)
                """,
                [
                    (
                        security.symbol,
                        security.name,
                        security.exchange,
                        security.asset_type,
                        security.sector,
                        security.symbol,
                        security.source,
                        security.fetched_at,
                    )
                    for security in securities
                ],
            )
            return len(securities)
        finally:
            connection.close()

    def record_source_success(self, module: str, source: str, records_written: int) -> None:
        connection = connect(self.db_path)
        try:
            self._record_success(connection, module, source, records_written)
        finally:
            connection.close()

    def delete_fixture_data(self) -> int:
        connection = connect(self.db_path)
        tables = (
            "securities",
            "market_quotes",
            "market_bars",
            "fundamentals",
            "announcements",
            "reports",
            "money_flow",
            "limit_up_pool",
            "module_records",
            "source_health",
        )
        deleted = 0
        try:
            for table in tables:
                deleted += int(connection.execute(f"SELECT count(*) FROM {table} WHERE source = 'local_fixture'").fetchone()[0])
                connection.execute(f"DELETE FROM {table} WHERE source = 'local_fixture'")
            return deleted
        finally:
            connection.close()

    def save_market_snapshot(self, snapshot: MarketSnapshot) -> int:
        connection = connect(self.db_path)
        records_written = 0
        started_at = datetime.now(UTC)
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO securities
                (symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at)
                VALUES (?, ?, ?, ?, NULL, COALESCE(?, (SELECT sector FROM securities WHERE symbol = ?)), true, ?, ?)
                """,
                (
                    snapshot.security.symbol,
                    snapshot.security.name,
                    snapshot.security.exchange,
                    snapshot.security.asset_type,
                    snapshot.security.sector,
                    snapshot.security.symbol,
                    snapshot.security.source,
                    snapshot.security.fetched_at,
                ),
            )
            records_written += 1

            if snapshot.quote:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO market_quotes
                    (symbol, price_time, last_price, previous_close, open, high, low, volume, amount, bid1, ask1,
                     change_amt, change_pct, turnover_pct, pe_ttm, amplitude_pct, total_market_cap, float_market_cap,
                     pb, limit_up, limit_down, volume_ratio, pe_static, source, fetched_at, raw_payload_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.quote.symbol,
                        snapshot.quote.price_time,
                        snapshot.quote.last_price,
                        snapshot.quote.previous_close,
                        snapshot.quote.open,
                        snapshot.quote.high,
                        snapshot.quote.low,
                        snapshot.quote.volume,
                        snapshot.quote.amount,
                        snapshot.quote.bid1,
                        snapshot.quote.ask1,
                        snapshot.quote.change_amt,
                        snapshot.quote.change_pct,
                        snapshot.quote.turnover_pct,
                        snapshot.quote.pe_ttm,
                        snapshot.quote.amplitude_pct,
                        snapshot.quote.total_market_cap,
                        snapshot.quote.float_market_cap,
                        snapshot.quote.pb,
                        snapshot.quote.limit_up,
                        snapshot.quote.limit_down,
                        snapshot.quote.volume_ratio,
                        snapshot.quote.pe_static,
                        snapshot.quote.source,
                        snapshot.quote.fetched_at,
                        snapshot.quote.raw_payload_hash,
                    ),
                )
                records_written += 1

            if snapshot.bars:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO market_bars
                    (symbol, trade_date, open, high, low, close, volume, amount, adjustment, source, fetched_at, raw_payload_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            bar.symbol,
                            bar.trade_date,
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.volume,
                            bar.amount,
                            bar.adjustment,
                            bar.source,
                            bar.fetched_at,
                            bar.raw_payload_hash,
                        )
                        for bar in snapshot.bars
                    ],
                )
                records_written += len(snapshot.bars)

            finished_at = datetime.now(UTC)
            connection.execute(
                """
                INSERT OR REPLACE INTO source_health
                (source, module, status, last_success_at, last_failure_at, last_error, updated_at)
                VALUES (?, 'market', 'fresh', ?, NULL, NULL, ?)
                """,
                (snapshot.security.source, finished_at, finished_at),
            )
            if snapshot.bars:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO source_health
                    (source, module, status, last_success_at, last_failure_at, last_error, updated_at)
                    VALUES (?, 'market', 'fresh', ?, NULL, NULL, ?)
                    """,
                    (snapshot.bars[0].source, finished_at, finished_at),
                )
            connection.execute(
                """
                INSERT OR REPLACE INTO data_jobs
                (id, job_type, module, source, status, started_at, finished_at, records_written, error_message)
                VALUES (?, 'refresh', 'market', ?, 'success', ?, ?, ?, NULL)
                """,
                (str(uuid4()), snapshot.security.source, started_at, finished_at, records_written),
            )
            return records_written
        finally:
            connection.close()

    def update_security_sector(self, symbol: str, sector: str | None, source: str, fetched_at: datetime) -> int:
        if not sector:
            return 0
        connection = connect(self.db_path)
        try:
            connection.execute(
                """
                UPDATE securities
                SET sector = ?
                WHERE upper(symbol) = ?
                """,
                (sector, symbol.upper()),
            )
            return 1
        finally:
            connection.close()

    def save_eastmoney_stock_info(self, symbol: str, info: dict[str, Any], fetched_at: datetime) -> int:
        normalized_symbol = symbol.upper()
        connection = connect(self.db_path)
        records_written = 0
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO securities
                (symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at)
                VALUES (?, ?, ?, 'stock', ?, ?, true, 'eastmoney_stock_info', ?)
                """,
                (
                    normalized_symbol,
                    info.get("name") or normalized_symbol,
                    "SSE" if normalized_symbol.endswith(".SH") else ("BSE" if normalized_symbol.endswith(".BJ") else "SZSE"),
                    info.get("list_date"),
                    info.get("industry"),
                    fetched_at,
                ),
            )
            records_written += 1
            connection.execute(
                """
                INSERT OR REPLACE INTO fundamentals
                (symbol, report_period, eps, roe, net_profit, revenue, total_market_cap, pe_ttm, pb, source, fetched_at, raw_payload_hash)
                VALUES (?, ?, NULL, NULL, NULL, NULL, ?, NULL, NULL, 'eastmoney_stock_info', ?, ?)
                """,
                (
                    normalized_symbol,
                    fetched_at.date().isoformat(),
                    info.get("mcap"),
                    fetched_at,
                    payload_hash(info),
                ),
            )
            records_written += 1
            self._record_success(connection, "fundamentals", "eastmoney_stock_info", records_written)
            return records_written
        finally:
            connection.close()

    def save_reports(self, reports: list[dict[str, Any]]) -> int:
        if not reports:
            return 0
        connection = connect(self.db_path)
        try:
            connection.executemany(
                """
                INSERT OR REPLACE INTO reports
                (id, symbol, title, institution, analyst, rating, report_date, eps_forecast, url, source, fetched_at, raw_payload_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["id"],
                        row["symbol"],
                        row["title"],
                        row.get("institution"),
                        row.get("analyst"),
                        row.get("rating"),
                        row["report_date"],
                        row.get("eps_forecast"),
                        row.get("url"),
                        row["source"],
                        row["fetched_at"],
                        row["raw_payload_hash"],
                    )
                    for row in reports
                ],
            )
            self._record_success(connection, "reports", "eastmoney_reports", len(reports))
            return len(reports)
        finally:
            connection.close()

    def save_announcements(self, announcements: list[dict[str, Any]], fetched_at: datetime) -> int:
        if not announcements:
            return 0
        connection = connect(self.db_path)
        try:
            connection.executemany(
                """
                INSERT OR REPLACE INTO announcements
                (id, symbol, title, published_at, url, source, fetched_at, raw_payload_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["id"],
                        row["symbol"],
                        row["title"],
                        row["published_at"],
                        row.get("url"),
                        row["source"],
                        fetched_at,
                        row["raw_payload_hash"],
                    )
                    for row in announcements
                ],
            )
            self._record_success(connection, "announcements", "cninfo_announcements", len(announcements))
            return len(announcements)
        finally:
            connection.close()

    def save_money_flow(self, rows: list[dict[str, Any]], fetched_at: datetime) -> int:
        if not rows:
            return 0
        connection = connect(self.db_path)
        try:
            connection.executemany(
                """
                INSERT OR REPLACE INTO money_flow
                (symbol, trade_date, main_net_inflow, retail_net_inflow, turnover_rate, source, fetched_at, raw_payload_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["symbol"],
                        row["trade_date"],
                        row.get("main_net_inflow"),
                        row.get("retail_net_inflow"),
                        row.get("turnover_rate"),
                        row["source"],
                        fetched_at,
                        row["raw_payload_hash"],
                    )
                    for row in rows
                ],
            )
            self._record_success(connection, "chip_liquidity", "stock_fund_flow_120d", len(rows))
            return len(rows)
        finally:
            connection.close()

    def save_module_records(self, records: list[ModuleRecord]) -> int:
        if not records:
            return 0
        connection = connect(self.db_path)
        try:
            connection.executemany(
                """
                INSERT OR REPLACE INTO module_records
                (module, source, data_key, symbol, record_date, payload_json, fetched_at, raw_payload_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.module,
                        record.source,
                        record.data_key,
                        record.symbol or "",
                        record.record_date,
                        json_dumps(record.payload),
                        record.fetched_at,
                        record.raw_payload_hash,
                    )
                    for record in records
                ],
            )
            for module, source in {(record.module, record.source) for record in records}:
                self._record_success(connection, module, source, len([record for record in records if record.module == module and record.source == source]))
            return len(records)
        finally:
            connection.close()

    def record_market_failure(self, source: str, error_message: str) -> None:
        self.record_source_failure("market", source, error_message)

    def record_source_failure(self, module: str, source: str, error_message: str) -> None:
        now = datetime.now(UTC)
        connection = connect(self.db_path)
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO source_health
                (source, module, status, last_success_at, last_failure_at, last_error, updated_at)
                VALUES (?, ?, 'failed', NULL, ?, ?, ?)
                """,
                (source, module, now, error_message[:500], now),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO data_jobs
                (id, job_type, module, source, status, started_at, finished_at, records_written, error_message)
                VALUES (?, 'refresh', ?, ?, 'failed', ?, ?, 0, ?)
                """,
                (str(uuid4()), module, source, now, now, error_message[:500]),
            )
        finally:
            connection.close()

    def search_securities(self, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        if query.strip():
            exact = query.strip().upper()
            normalized_exact = exact if "." in exact else exact.split(".")[0]
            return self._fetch_all(
                """
                SELECT symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at
                FROM securities
                WHERE lower(symbol) LIKE lower(?) OR lower(name) LIKE lower(?)
                ORDER BY
                  CASE
                    WHEN upper(symbol) = upper(?) THEN 0
                    WHEN split_part(upper(symbol), '.', 1) = upper(?) THEN 1
                    WHEN lower(name) = lower(?) THEN 2
                    WHEN lower(name) LIKE lower(?) THEN 3
                    ELSE 4
                  END,
                  symbol
                LIMIT ?
                """,
                (pattern, pattern, exact, normalized_exact, query.strip(), pattern, limit),
            )
        return self._fetch_all(
            """
            SELECT symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at
            FROM securities
            ORDER BY symbol
            LIMIT ?
            """,
            (limit,),
        )

    def security_universe_status(self) -> dict[str, Any]:
        row = self._fetch_one(
            """
            SELECT count(*) AS count, max(fetched_at) AS last_fetched_at
            FROM securities
            WHERE source IN ('free_stockdb_universe', 'free_stockdb_security', 'free_stockdb_security_preload')
            """
        )
        return {
            "count": int(row["count"] or 0) if row else 0,
            "last_fetched_at": row["last_fetched_at"] if row else None,
            "source": "free_stockdb_universe",
        }

    def get_security_overview(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = symbol.upper()
        security = self._fetch_one(
            """
            SELECT symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at
            FROM securities
            WHERE upper(symbol) = ?
            """,
            (normalized_symbol,),
        )
        return {
            "symbol": normalized_symbol,
            "security": security,
            "market": self._latest_market_bar(normalized_symbol),
            "quote": self.latest_market_quote(normalized_symbol),
            "fundamentals": self._latest_fundamental(normalized_symbol),
            "announcements": self.list_announcements(normalized_symbol, limit=8),
            "reports": self.list_reports(normalized_symbol, limit=8),
            "money_flow": self.list_money_flow(normalized_symbol, limit=8),
            "freshness": self.security_freshness(normalized_symbol),
        }

    def latest_market_quote(self, symbol: str) -> dict[str, Any] | None:
        return self._fetch_one(
            """
            SELECT symbol, price_time, last_price, previous_close, open, high, low, volume, amount, bid1, ask1,
                   change_amt, change_pct, turnover_pct, pe_ttm, amplitude_pct, total_market_cap, float_market_cap,
                   pb, limit_up, limit_down, volume_ratio, pe_static, source, fetched_at
            FROM market_quotes
            WHERE upper(symbol) = ?
            """,
            (symbol.upper(),),
        )

    def chart_bars(self, symbol: str, limit: int = 120, adjustment: str = "auto") -> list[dict[str, Any]]:
        if adjustment == "auto":
            rows = self._chart_bars_for_adjustment(symbol, limit=limit, adjustment="qfq")
            if not rows:
                rows = self._chart_bars_for_adjustment(symbol, limit=limit, adjustment="none")
            if not rows:
                rows = self._chart_bars_for_adjustment(symbol, limit=limit, adjustment="hfq")
        else:
            rows = self._chart_bars_for_adjustment(symbol, limit=limit, adjustment=adjustment)
        ordered = list(reversed(rows))
        closes: list[float | None] = []
        for row in ordered:
            close = row.get("close")
            closes.append(float(close) if isinstance(close, (int, float)) else None)
            row["ma5"] = _moving_average(closes, 5)
            row["ma10"] = _moving_average(closes, 10)
            row["ma20"] = _moving_average(closes, 20)
        return ordered

    def _chart_bars_for_adjustment(self, symbol: str, limit: int, adjustment: str) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT symbol, trade_date, open, high, low, close, volume, amount, adjustment, source, fetched_at
            FROM market_bars
            WHERE upper(symbol) = ? AND adjustment = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (symbol.upper(), adjustment, limit),
        )
        return rows

    def _latest_market_bar(self, symbol: str) -> dict[str, Any] | None:
        return self._fetch_one(
            """
            SELECT symbol, trade_date, open, high, low, close, volume, amount, adjustment, source, fetched_at
            FROM market_bars
            WHERE upper(symbol) = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (symbol,),
        )

    def _latest_fundamental(self, symbol: str) -> dict[str, Any] | None:
        return self._fetch_one(
            """
            SELECT symbol, report_period, eps, roe, net_profit, revenue, total_market_cap, pe_ttm, pb, source, fetched_at
            FROM fundamentals
            WHERE upper(symbol) = ?
            ORDER BY report_period DESC
            LIMIT 1
            """,
            (symbol,),
        )

    def list_announcements(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if symbol:
            return self._fetch_all(
                """
                SELECT id, symbol, title, published_at, url, source, fetched_at
                FROM announcements
                WHERE upper(symbol) = ?
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        return self._fetch_all(
            """
            SELECT id, symbol, title, published_at, url, source, fetched_at
            FROM announcements
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_reports(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if symbol:
            return self._fetch_all(
                """
                SELECT id, symbol, title, institution, analyst, rating, report_date, eps_forecast, url, source, fetched_at
                FROM reports
                WHERE upper(symbol) = ?
                ORDER BY report_date DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        return self._fetch_all(
            """
            SELECT id, symbol, title, institution, analyst, rating, report_date, eps_forecast, url, source, fetched_at
            FROM reports
            ORDER BY report_date DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_money_flow(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if symbol:
            return self._fetch_all(
                """
                SELECT symbol, trade_date, main_net_inflow, retail_net_inflow, turnover_rate, source, fetched_at
                FROM money_flow
                WHERE upper(symbol) = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        return self._fetch_all(
            """
            SELECT symbol, trade_date, main_net_inflow, retail_net_inflow, turnover_rate, source, fetched_at
            FROM money_flow
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_module_data(self, module_id: str, symbol: str | None = None, limit: int = 100) -> dict[str, Any]:
        module = MODULE_BY_ID.get(module_id)
        if module is None:
            return {"module": module_id, "status": "not_found", "rows": []}
        market_payload = None
        reports_payload = None
        if module_id == "market":
            quote = self.latest_market_quote(symbol) if symbol else None
            rows = ([quote] if quote else []) + self._list_market_bars(symbol, limit)
            market_payload = self._market_layer_payload(symbol, limit)
        elif module_id == "fundamentals":
            rows = self._list_fundamentals(symbol, limit)
        elif module_id == "announcements":
            rows = self.list_announcements(symbol, limit)
        elif module_id == "reports":
            rows = self.list_reports(symbol, limit)
            reports_payload = self._reports_layer_payload(symbol, limit)
        elif module_id == "chip_liquidity":
            rows = self.list_money_flow(symbol, limit)
        elif module_id == "signals":
            rows = self._list_module_records("signals", symbol, limit)
        elif module_id == "limit_up":
            rows = self._list_limit_up(symbol, limit)
        elif module_id in {"news", "etf_options", "sentiment"}:
            rows = self._list_module_records(module_id, symbol, limit)
        else:
            rows = []
        status = "ok" if rows else ("not_collected" if module.status != "not_configured" else "not_configured")
        result: dict[str, Any] = {"module": module_id, "status": status, "rows": rows}
        if market_payload is not None:
            result["market"] = market_payload
        if reports_payload is not None:
            result["reports"] = reports_payload
        return result

    def _reports_layer_payload(self, symbol: str | None, limit: int) -> dict[str, Any]:
        stock_reports = self.list_reports(symbol, limit)
        industry_reports = [
            row
            for row in self._list_module_records("reports", symbol, limit)
            if row.get("source") == "eastmoney_industry_reports"
        ]
        latest_report = stock_reports[0] if stock_reports else None
        eps_forecast = _parse_eps_forecast(latest_report.get("eps_forecast") if latest_report else None)
        source_status = self._reports_source_status()
        latest_source = latest_report.get("source") if latest_report else None
        latest_time = latest_report.get("fetched_at") if latest_report else None
        latest_industry_time = industry_reports[0].get("fetched_at") if industry_reports else None
        sections = [
            {
                "id": "coverage",
                "title": "Coverage Snapshot",
                "source": latest_source or "eastmoney_reports",
                "fetched_at": latest_time,
                "cards": [
                    {"label": "Company reports", "value": len(stock_reports)},
                    {"label": "Industry reports", "value": len(industry_reports)},
                    {"label": "Latest rating", "value": latest_report.get("rating") if latest_report else None},
                    {"label": "Latest institution", "value": latest_report.get("institution") if latest_report else None},
                    {"label": "Latest report date", "value": latest_report.get("report_date") if latest_report else None},
                    {"label": "Latest analyst", "value": latest_report.get("analyst") if latest_report else None},
                ],
            },
            {
                "id": "eps_forecast",
                "title": "EPS Forecast",
                "source": latest_source or "eastmoney_reports",
                "fetched_at": latest_time,
                "cards": [
                    {"label": "This-year EPS", "value": eps_forecast.get("this_year")},
                    {"label": "Next-year EPS", "value": eps_forecast.get("next_year")},
                    {"label": "Next-two-year EPS", "value": eps_forecast.get("next_two_year")},
                    {"label": "Consensus EPS", "value": _source_status_label(source_status, "ths_eps_forecast")},
                    {"label": "iwencai NL search", "value": _source_status_label(source_status, "iwencai_search")},
                ],
            },
            {
                "id": "source_capabilities",
                "title": "Source Capabilities",
                "source": "connector_registry",
                "fetched_at": latest_industry_time or latest_time,
                "cards": [
                    _source_capability_card(source_status, "eastmoney_reports", "Company reports"),
                    _source_capability_card(source_status, "eastmoney_industry_reports", "Industry reports"),
                    {"label": "PDF URL", "value": "prepared", "status": "prepared"},
                    _source_capability_card(source_status, "ths_eps_forecast", "10jqka EPS"),
                    _source_capability_card(source_status, "iwencai_search", "iwencai"),
                ],
            },
        ]
        tables = [
            {
                "id": "stock_reports",
                "title": "Company Reports",
                "rows": stock_reports,
                "columns": [
                    {"key": "title", "label": "Title"},
                    {"key": "report_date", "label": "Report date"},
                    {"key": "institution", "label": "Institution"},
                    {"key": "analyst", "label": "Analyst"},
                    {"key": "rating", "label": "Rating"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
            {
                "id": "industry_reports",
                "title": "Industry Reports",
                "rows": industry_reports,
                "columns": [
                    {"key": "title", "label": "Title"},
                    {"key": "report_date", "label": "Report date"},
                    {"key": "industry", "label": "Industry"},
                    {"key": "industry_code", "label": "Industry code"},
                    {"key": "institution", "label": "Institution"},
                    {"key": "rating", "label": "Rating"},
                    {"key": "source", "label": "Source"},
                ],
            },
        ]
        return {
            "symbol": symbol.upper() if symbol else None,
            "sections": sections,
            "tables": tables,
            "source_status": source_status,
        }

    def _reports_source_status(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT source, module, status, last_success_at, last_failure_at, last_error, updated_at
            FROM source_health
            WHERE module = 'reports'
            ORDER BY source
            """
        )
        by_source = {str(row["source"]): row for row in rows}
        defaults = {
            "eastmoney_reports": {"status": "not_collected", "last_error": None},
            "eastmoney_industry_reports": {"status": "not_collected", "last_error": None},
            "ths_eps_forecast": {
                "status": "prepared" if importlib.util.find_spec("pandas") is not None else "optional_dependency_missing",
                "last_error": None if importlib.util.find_spec("pandas") is not None else "Optional dependency pandas is not installed.",
            },
            "iwencai_search": {
                "status": "prepared" if os.getenv("IWENCAI_API_KEY") else "needs_key",
                "last_error": None if os.getenv("IWENCAI_API_KEY") else "IWENCAI_API_KEY is not configured.",
            },
        }
        for source, value in defaults.items():
            if source not in by_source:
                rows.append(
                    {
                        "source": source,
                        "module": "reports",
                        "status": value["status"],
                        "last_success_at": None,
                        "last_failure_at": None,
                        "last_error": value["last_error"],
                        "updated_at": None,
                    }
                )
        return rows

    def _market_layer_payload(self, symbol: str | None, limit: int) -> dict[str, Any]:
        quote = self.latest_market_quote(symbol) if symbol else None
        latest_bar = self._latest_market_bar(symbol) if symbol else None
        recent_bars = self._list_market_bars(symbol, min(limit, 20))
        source_status = self._market_source_status()
        fetched_at = quote.get("fetched_at") if quote else (latest_bar.get("fetched_at") if latest_bar else None)
        return {
            "symbol": symbol.upper() if symbol else None,
            "quote_snapshot": quote,
            "latest_bar": latest_bar,
            "recent_bars": recent_bars,
            "valuation": {
                "pe_ttm": quote.get("pe_ttm") if quote else None,
                "pe_static": quote.get("pe_static") if quote else None,
                "pb": quote.get("pb") if quote else None,
                "total_market_cap": quote.get("total_market_cap") if quote else None,
                "float_market_cap": quote.get("float_market_cap") if quote else None,
                "source": quote.get("source") if quote else "tencent_quote",
                "fetched_at": fetched_at,
            },
            "limits": {
                "limit_up": quote.get("limit_up") if quote else None,
                "limit_down": quote.get("limit_down") if quote else None,
                "change_amt": quote.get("change_amt") if quote else None,
                "change_pct": quote.get("change_pct") if quote else None,
                "amplitude_pct": quote.get("amplitude_pct") if quote else None,
                "source": quote.get("source") if quote else "tencent_quote",
                "fetched_at": fetched_at,
            },
            "liquidity": {
                "turnover_pct": quote.get("turnover_pct") if quote else None,
                "volume_ratio": quote.get("volume_ratio") if quote else None,
                "volume": quote.get("volume") if quote else None,
                "amount": quote.get("amount") if quote else None,
                "bid1": quote.get("bid1") if quote else None,
                "ask1": quote.get("ask1") if quote else None,
                "source": quote.get("source") if quote else "tencent_quote",
                "fetched_at": fetched_at,
            },
            "order_book": {
                "status": "optional_dependency_missing",
                "source": "mootdx",
                "rows": [],
                "note": "mootdx optional dependency is not installed/enabled; five-level order book is unavailable.",
            },
            "index_etf": {
                "status": "prepared",
                "source": "Tencent Finance",
                "entries": [
                    {"label": "SSE Composite", "symbol": "000001.SH"},
                    {"label": "CSI 300", "symbol": "000300.SH"},
                    {"label": "ChiNext", "symbol": "399006.SZ"},
                    {"label": "SSE 50 ETF", "symbol": "510050.SH"},
                    {"label": "CSI 300 ETF", "symbol": "510300.SH"},
                ],
                "note": "Quick entries reuse the existing symbol workflow; full index/ETF browsing is not implemented yet.",
            },
            "source_status": source_status,
        }

    def _market_source_status(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT source, module, status, last_success_at, last_failure_at, last_error, updated_at
            FROM source_health
            WHERE module = 'market'
            ORDER BY source
            """
        )
        known_sources = {
            str(row["source"]) for row in rows
        }
        if "mootdx" not in known_sources:
            rows.append(
                {
                    "source": "mootdx",
                    "module": "market",
                    "status": "optional_dependency_missing",
                    "last_success_at": None,
                    "last_failure_at": None,
                    "last_error": "Optional dependency is not enabled.",
                    "updated_at": None,
                }
            )
        if "tencent_quote" not in known_sources:
            rows.append(
                {
                    "source": "tencent_quote",
                    "module": "market",
                    "status": "not_collected",
                    "last_success_at": None,
                    "last_failure_at": None,
                    "last_error": None,
                    "updated_at": None,
                }
            )
        return rows

    def _list_market_bars(self, symbol: str | None, limit: int) -> list[dict[str, Any]]:
        if symbol:
            return self._fetch_all(
                """
                SELECT symbol, trade_date, open, high, low, close, volume, amount, adjustment, source, fetched_at
                FROM market_bars
                WHERE upper(symbol) = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        return self._fetch_all(
            """
            SELECT symbol, trade_date, open, high, low, close, volume, amount, adjustment, source, fetched_at
            FROM market_bars
            ORDER BY trade_date DESC, symbol
            LIMIT ?
            """,
            (limit,),
        )

    def _list_fundamentals(self, symbol: str | None, limit: int) -> list[dict[str, Any]]:
        if symbol:
            return self._fetch_all(
                """
                SELECT symbol, report_period, eps, roe, net_profit, revenue, total_market_cap, pe_ttm, pb, source, fetched_at
                FROM fundamentals
                WHERE upper(symbol) = ?
                ORDER BY report_period DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        return self._fetch_all(
            """
            SELECT symbol, report_period, eps, roe, net_profit, revenue, total_market_cap, pe_ttm, pb, source, fetched_at
            FROM fundamentals
            ORDER BY report_period DESC, symbol
            LIMIT ?
            """,
            (limit,),
        )

    def _list_limit_up(self, symbol: str | None, limit: int) -> list[dict[str, Any]]:
        if symbol:
            return self._fetch_all(
                """
                SELECT trade_date, symbol, name, reason, board_count, status, source, fetched_at
                FROM limit_up_pool
                WHERE upper(symbol) = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        return self._fetch_all(
            """
            SELECT trade_date, symbol, name, reason, board_count, status, source, fetched_at
            FROM limit_up_pool
            ORDER BY trade_date DESC, board_count DESC NULLS LAST
            LIMIT ?
            """,
            (limit,),
        )

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT id, job_type, module, source, status, started_at, finished_at, records_written, error_message
            FROM data_jobs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_source_health(self) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT source, module, status, last_success_at, last_failure_at, last_error, updated_at
            FROM source_health
            ORDER BY module, source
            """
        )

    def _record_success(self, connection: Any, module: str, source: str, records_written: int) -> None:
        now = datetime.now(UTC)
        connection.execute(
            """
            INSERT OR REPLACE INTO source_health
            (source, module, status, last_success_at, last_failure_at, last_error, updated_at)
            VALUES (?, ?, 'fresh', ?, NULL, NULL, ?)
            """,
            (source, module, now, now),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO data_jobs
            (id, job_type, module, source, status, started_at, finished_at, records_written, error_message)
            VALUES (?, 'refresh', ?, ?, 'success', ?, ?, ?, NULL)
            """,
            (str(uuid4()), module, source, now, now, records_written),
        )

    def _list_module_records(self, module_id: str, symbol: str | None, limit: int) -> list[dict[str, Any]]:
        if symbol:
            rows = self._fetch_all(
                """
                SELECT module, source, data_key, symbol, record_date, payload_json, fetched_at
                FROM module_records
                WHERE module = ? AND upper(coalesce(symbol, '')) = ?
                ORDER BY fetched_at DESC, record_date DESC NULLS LAST
                LIMIT ?
                """,
                (module_id, symbol.upper(), limit),
            )
        else:
            rows = self._fetch_all(
                """
                SELECT module, source, data_key, symbol, record_date, payload_json, fetched_at
                FROM module_records
                WHERE module = ?
                ORDER BY fetched_at DESC, record_date DESC NULLS LAST
                LIMIT ?
                """,
                (module_id, limit),
            )
        return [_flatten_module_record(row) for row in rows]

    def security_freshness(self, symbol: str) -> dict[str, str]:
        checks = {
            "market": self._latest_market_bar(symbol),
            "quote": self.latest_market_quote(symbol),
            "fundamentals": self._latest_fundamental(symbol),
            "announcements": self.list_announcements(symbol, limit=1),
            "reports": self.list_reports(symbol, limit=1),
            "money_flow": self.list_money_flow(symbol, limit=1),
        }
        freshness: dict[str, str] = {}
        for key, value in checks.items():
            freshness[key] = "fresh" if value else "not_collected"
        return freshness


def _moving_average(values: list[float | None], window: int) -> float | None:
    if len(values) < window:
        return None
    sample = values[-window:]
    if any(value is None for value in sample):
        return None
    return round(sum(value for value in sample if value is not None) / window, 4)


def json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _parse_eps_forecast(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _source_status_label(rows: list[dict[str, Any]], source: str) -> str:
    for row in rows:
        if row.get("source") == source:
            return str(row.get("status") or "not_collected").replace("_", " ")
    return "not collected"


def _source_capability_card(rows: list[dict[str, Any]], source: str, label: str) -> dict[str, Any]:
    for row in rows:
        if row.get("source") == source:
            return {"label": label, "value": _source_status_label(rows, source), "status": row.get("status")}
    return {"label": label, "value": "not collected", "status": "not_collected"}


def _flatten_module_record(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.pop("payload_json", None)
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"payload": payload}
    elif isinstance(payload, dict):
        parsed = payload
    else:
        parsed = {"payload": payload}
    return {**row, **parsed}
