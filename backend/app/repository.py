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

    def _announcements_layer_payload(self, symbol: str | None, limit: int) -> dict[str, Any]:
        announcement_rows = self.list_announcements(symbol, limit)
        latest = announcement_rows[0] if announcement_rows else None
        source_status = self._announcements_source_status()
        latest_time = _latest_fetched_at(announcement_rows)
        sections = [
            {
                "id": "cninfo_snapshot",
                "title": "CNINFO Announcement Snapshot",
                "source": "cninfo_announcements",
                "fetched_at": latest_time,
                "cards": [
                    {"label": "Announcements", "value": len(announcement_rows)},
                    {"label": "Latest title", "value": latest.get("title") if latest else None},
                    {"label": "Latest date", "value": latest.get("published_at") if latest else None},
                    _source_capability_card(source_status, "cninfo_announcements", "CNINFO full text"),
                ],
            },
            {
                "id": "source_capabilities",
                "title": "Source Capabilities",
                "source": "connector_registry",
                "fetched_at": latest_time,
                "cards": [
                    _source_capability_card(source_status, "cninfo_announcements", "CNINFO full-text search"),
                    _source_capability_card(source_status, "cninfo_orgid_map", "CNINFO orgId map"),
                    _source_capability_card(source_status, "mootdx_f10_latest", "mootdx F10 latest tips"),
                    _source_capability_card(source_status, "announcements_backup", "Official backup route"),
                ],
            },
        ]
        tables = [
            {
                "id": "cninfo_announcements",
                "title": "CNINFO Announcements",
                "rows": announcement_rows,
                "columns": [
                    {"key": "published_at", "label": "Published at"},
                    {"key": "title", "label": "Title"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            }
        ]
        return {
            "symbol": symbol.upper() if symbol else None,
            "sections": sections,
            "tables": tables,
            "source_status": source_status,
        }

    def _announcements_source_status(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT source, module, status, last_success_at, last_failure_at, last_error, updated_at
            FROM source_health
            WHERE module = 'announcements'
            ORDER BY source
            """
        )
        by_source = {str(row["source"]): row for row in rows}
        defaults = {
            "cninfo_announcements": {"status": "not_collected", "last_error": None},
            "cninfo_orgid_map": {"status": "prepared", "last_error": "CNINFO orgId is resolved from the official szse_stock.json mapping with fallback rules."},
            "mootdx_f10_latest": {"status": "optional_dependency_missing", "last_error": "mootdx optional dependency is not installed/enabled; F10 latest announcement summary is unavailable."},
            "announcements_backup": {
                "status": "prepared",
                "last_error": "Backup route is documented from a-stock-data: SZSE official for Shenzhen tickers and Eastmoney announcement PDF for Shanghai tickers; it is not used as the default CNINFO source.",
            },
        }
        for source, value in defaults.items():
            if source not in by_source:
                rows.append(
                    {
                        "source": source,
                        "module": "announcements",
                        "status": value["status"],
                        "last_success_at": None,
                        "last_failure_at": None,
                        "last_error": value["last_error"],
                        "updated_at": None,
                    }
                )
        return rows

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
        announcements_payload = None
        reports_payload = None
        signals_payload = None
        news_payload = None
        chip_liquidity_payload = None
        if module_id == "market":
            quote = self.latest_market_quote(symbol) if symbol else None
            rows = ([quote] if quote else []) + self._list_market_bars(symbol, limit)
            market_payload = self._market_layer_payload(symbol, limit)
        elif module_id == "fundamentals":
            rows = self._list_fundamentals(symbol, limit)
        elif module_id == "announcements":
            rows = self.list_announcements(symbol, limit)
            announcements_payload = self._announcements_layer_payload(symbol, limit)
        elif module_id == "reports":
            rows = self.list_reports(symbol, limit)
            reports_payload = self._reports_layer_payload(symbol, limit)
        elif module_id == "chip_liquidity":
            rows = self.list_money_flow(symbol, limit) + self._list_module_records("chip_liquidity", symbol, limit)
            chip_liquidity_payload = self._chip_liquidity_layer_payload(symbol, limit)
        elif module_id == "signals":
            rows = self._list_module_records("signals", symbol, limit)
            signals_payload = self._signals_layer_payload(symbol, limit)
        elif module_id == "news":
            rows = self._list_news_records(symbol, limit)
            news_payload = self._news_layer_payload(symbol, limit)
        elif module_id == "limit_up":
            rows = self._list_limit_up(symbol, limit)
        elif module_id in {"etf_options", "sentiment"}:
            rows = self._list_module_records(module_id, symbol, limit)
        else:
            rows = []
        status = "ok" if rows else ("not_collected" if module.status != "not_configured" else "not_configured")
        result: dict[str, Any] = {"module": module_id, "status": status, "rows": rows}
        if market_payload is not None:
            result["market"] = market_payload
        if announcements_payload is not None:
            result["announcements"] = announcements_payload
        if reports_payload is not None:
            result["reports"] = reports_payload
        if signals_payload is not None:
            result["signals"] = signals_payload
        if news_payload is not None:
            result["news"] = news_payload
        if chip_liquidity_payload is not None:
            result["chip_liquidity"] = chip_liquidity_payload
        return result

    def _news_layer_payload(self, symbol: str | None, limit: int) -> dict[str, Any]:
        news_rows = self._list_news_records(symbol, limit)
        stock_news = [row for row in news_rows if row.get("source") == "eastmoney_stock_news"]
        cls_rows = [row for row in news_rows if row.get("source") == "cls_telegraph"]
        global_rows = [row for row in news_rows if row.get("source") == "eastmoney_global_news"]
        latest_stock = stock_news[0] if stock_news else None
        latest_cls = cls_rows[0] if cls_rows else None
        latest_global = global_rows[0] if global_rows else None
        source_status = self._news_source_status()
        latest_time = _latest_fetched_at(news_rows)
        sections = [
            {
                "id": "stock_news",
                "title": "Stock News Snapshot",
                "source": "eastmoney_stock_news",
                "fetched_at": _latest_fetched_at(stock_news),
                "cards": [
                    {"label": "Stock news", "value": len(stock_news)},
                    {"label": "Latest title", "value": latest_stock.get("title") if latest_stock else None},
                    {"label": "Latest media", "value": latest_stock.get("media") if latest_stock else None},
                    {"label": "Latest time", "value": latest_stock.get("time") if latest_stock else None},
                    _source_capability_card(source_status, "eastmoney_stock_news", "Eastmoney stock news"),
                ],
            },
            {
                "id": "market_flash",
                "title": "Market Flash Snapshot",
                "source": "cls_telegraph + eastmoney_global_news",
                "fetched_at": _latest_fetched_at(cls_rows) or _latest_fetched_at(global_rows),
                "cards": [
                    {"label": "CLS telegrams", "value": len(cls_rows)},
                    {"label": "Global news", "value": len(global_rows)},
                    {"label": "Latest CLS", "value": latest_cls.get("title") if latest_cls else None},
                    {"label": "Latest global", "value": latest_global.get("title") if latest_global else None},
                    {"label": "Mutual backup", "value": "CLS v1 + Eastmoney 7x24"},
                ],
            },
            {
                "id": "source_capabilities",
                "title": "Source Capabilities",
                "source": "connector_registry",
                "fetched_at": latest_time,
                "cards": [
                    _source_capability_card(source_status, "eastmoney_stock_news", "Stock news"),
                    _source_capability_card(source_status, "cls_telegraph", "CLS telegram"),
                    _source_capability_card(source_status, "eastmoney_global_news", "Eastmoney global"),
                ],
            },
        ]
        tables = [
            {
                "id": "stock_news",
                "title": "Eastmoney Stock News",
                "rows": stock_news,
                "columns": [
                    {"key": "title", "label": "Title"},
                    {"key": "time", "label": "Time"},
                    {"key": "media", "label": "Media"},
                    {"key": "summary", "label": "Summary"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
            {
                "id": "cls_telegraph",
                "title": "CLS Telegrams",
                "rows": cls_rows,
                "columns": [
                    {"key": "title", "label": "Title"},
                    {"key": "time", "label": "Time"},
                    {"key": "summary", "label": "Summary"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
            {
                "id": "eastmoney_global_news",
                "title": "Eastmoney Global News",
                "rows": global_rows,
                "columns": [
                    {"key": "title", "label": "Title"},
                    {"key": "time", "label": "Time"},
                    {"key": "media", "label": "Media"},
                    {"key": "summary", "label": "Summary"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
        ]
        return {
            "symbol": symbol.upper() if symbol else None,
            "sections": sections,
            "tables": tables,
            "source_status": source_status,
        }

    def _news_source_status(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT source, module, status, last_success_at, last_failure_at, last_error, updated_at
            FROM source_health
            WHERE module = 'news'
            ORDER BY source
            """
        )
        by_source = {str(row["source"]): row for row in rows}
        defaults = {
            "eastmoney_stock_news": {"status": "not_collected", "last_error": None},
            "cls_telegraph": {"status": "not_collected", "last_error": None},
            "eastmoney_global_news": {"status": "not_collected", "last_error": None},
        }
        for source, value in defaults.items():
            if source not in by_source:
                rows.append(
                    {
                        "source": source,
                        "module": "news",
                        "status": value["status"],
                        "last_success_at": None,
                        "last_failure_at": None,
                        "last_error": value["last_error"],
                        "updated_at": None,
                    }
                )
        return rows

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

    def _signals_layer_payload(self, symbol: str | None, limit: int) -> dict[str, Any]:
        signal_rows = self._list_module_records("signals", symbol, limit)
        concept_rows = [row for row in signal_rows if row.get("source") == "eastmoney_concept_blocks"]
        flow_rows = [row for row in signal_rows if row.get("source") == "eastmoney_fund_flow_minute"]
        dragon_rows = [row for row in signal_rows if row.get("source") == "eastmoney_dragon_tiger_board"]
        buy_seats = [row for row in signal_rows if row.get("source") == "eastmoney_dragon_tiger_buy_seats"]
        sell_seats = [row for row in signal_rows if row.get("source") == "eastmoney_dragon_tiger_sell_seats"]
        industry_rows = [row for row in signal_rows if row.get("source") == "eastmoney_industry_comparison"]
        latest_flow = flow_rows[0] if flow_rows else None
        latest_dragon = dragon_rows[0] if dragon_rows else None
        top_industry = industry_rows[0] if industry_rows else None
        source_status = self._signals_source_status()
        latest_time = _latest_fetched_at(signal_rows)
        sections = [
            {
                "id": "sector_mapping",
                "title": "Sector / Concept Mapping",
                "source": "eastmoney_concept_blocks + free_stockdb_bk",
                "fetched_at": _latest_fetched_at(concept_rows) or latest_time,
                "cards": [
                    {"label": "Eastmoney blocks", "value": len(concept_rows)},
                    {"label": "Primary block", "value": concept_rows[0].get("name") if concept_rows else None},
                    {"label": "Lead stock", "value": concept_rows[0].get("lead_stock") if concept_rows else None},
                    _source_capability_card(source_status, "eastmoney_concept_blocks", "Eastmoney ownership"),
                    _source_capability_card(source_status, "free_stockdb_bk", "free-stockdb board map"),
                ],
            },
            {
                "id": "fund_flow",
                "title": "Intraday Fund Flow",
                "source": "eastmoney_fund_flow_minute",
                "fetched_at": _latest_fetched_at(flow_rows),
                "cards": [
                    {"label": "Minute points", "value": len(flow_rows)},
                    {"label": "Latest time", "value": latest_flow.get("time") if latest_flow else None},
                    {"label": "Main net", "value": latest_flow.get("main_net") if latest_flow else None},
                    {"label": "Super net", "value": latest_flow.get("super_net") if latest_flow else None},
                    _source_capability_card(source_status, "eastmoney_fund_flow_minute", "Connector"),
                ],
            },
            {
                "id": "dragon_tiger",
                "title": "Dragon Tiger Snapshot",
                "source": "eastmoney_dragon_tiger_board",
                "fetched_at": _latest_fetched_at(dragon_rows),
                "cards": [
                    {"label": "Records", "value": len(dragon_rows)},
                    {"label": "Latest date", "value": latest_dragon.get("date") if latest_dragon else None},
                    {"label": "Reason", "value": latest_dragon.get("reason") if latest_dragon else None},
                    {"label": "Net buy (wan)", "value": latest_dragon.get("net_buy_wan") if latest_dragon else None},
                    _source_capability_card(source_status, "eastmoney_dragon_tiger_board", "Connector"),
                ],
            },
            {
                "id": "industry_rotation",
                "title": "Industry Rotation",
                "source": "eastmoney_industry_comparison",
                "fetched_at": _latest_fetched_at(industry_rows),
                "cards": [
                    {"label": "Industries", "value": len(industry_rows)},
                    {"label": "Top industry", "value": top_industry.get("name") if top_industry else None},
                    {"label": "Top change %", "value": top_industry.get("change_pct") if top_industry else None},
                    {"label": "Leader", "value": top_industry.get("leader") if top_industry else None},
                    _source_capability_card(source_status, "eastmoney_industry_comparison", "Connector"),
                ],
            },
            {
                "id": "source_capabilities",
                "title": "Source Capabilities",
                "source": "connector_registry",
                "fetched_at": latest_time,
                "cards": [
                    _source_capability_card(source_status, "eastmoney_concept_blocks", "Eastmoney blocks"),
                    _source_capability_card(source_status, "eastmoney_fund_flow_minute", "Minute fund flow"),
                    _source_capability_card(source_status, "eastmoney_dragon_tiger_board", "Dragon tiger"),
                    _source_capability_card(source_status, "eastmoney_industry_comparison", "Industry ranking"),
                    _source_capability_card(source_status, "hsgt_realtime", "Northbound boundary"),
                    _source_capability_card(source_status, "ths_hot_reason", "10jqka hot reason"),
                ],
            },
        ]
        tables = [
            {
                "id": "concept_blocks",
                "title": "Sector / Concept Blocks",
                "rows": concept_rows,
                "columns": [
                    {"key": "name", "label": "Name"},
                    {"key": "code", "label": "Code"},
                    {"key": "change_pct", "label": "Change %"},
                    {"key": "lead_stock", "label": "Lead stock"},
                    {"key": "source", "label": "Source"},
                    {"key": "record_date", "label": "Record date"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
            {
                "id": "minute_fund_flow",
                "title": "Intraday Minute Fund Flow",
                "rows": flow_rows,
                "columns": [
                    {"key": "time", "label": "Time"},
                    {"key": "main_net", "label": "Main net"},
                    {"key": "super_net", "label": "Super net"},
                    {"key": "large_net", "label": "Large net"},
                    {"key": "mid_net", "label": "Mid net"},
                    {"key": "small_net", "label": "Small net"},
                    {"key": "source", "label": "Source"},
                ],
            },
            {
                "id": "dragon_tiger_records",
                "title": "Dragon Tiger Records",
                "rows": dragon_rows,
                "columns": [
                    {"key": "date", "label": "Date"},
                    {"key": "reason", "label": "Reason"},
                    {"key": "net_buy_wan", "label": "Net buy (wan)"},
                    {"key": "turnover_pct", "label": "Turnover %"},
                    {"key": "close", "label": "Close"},
                    {"key": "change_pct", "label": "Change %"},
                    {"key": "source", "label": "Source"},
                ],
            },
            {
                "id": "dragon_tiger_buy_seats",
                "title": "Dragon Tiger Buy Seats",
                "rows": buy_seats,
                "columns": [
                    {"key": "date", "label": "Date"},
                    {"key": "name", "label": "Seat"},
                    {"key": "buy_wan", "label": "Buy (wan)"},
                    {"key": "sell_wan", "label": "Sell (wan)"},
                    {"key": "net_wan", "label": "Net (wan)"},
                    {"key": "source", "label": "Source"},
                ],
            },
            {
                "id": "dragon_tiger_sell_seats",
                "title": "Dragon Tiger Sell Seats",
                "rows": sell_seats,
                "columns": [
                    {"key": "date", "label": "Date"},
                    {"key": "name", "label": "Seat"},
                    {"key": "buy_wan", "label": "Buy (wan)"},
                    {"key": "sell_wan", "label": "Sell (wan)"},
                    {"key": "net_wan", "label": "Net (wan)"},
                    {"key": "source", "label": "Source"},
                ],
            },
            {
                "id": "industry_comparison",
                "title": "Industry Comparison",
                "rows": industry_rows,
                "columns": [
                    {"key": "rank", "label": "Rank"},
                    {"key": "name", "label": "Industry"},
                    {"key": "change_pct", "label": "Change %"},
                    {"key": "up_count", "label": "Up"},
                    {"key": "down_count", "label": "Down"},
                    {"key": "leader", "label": "Leader"},
                    {"key": "leader_change", "label": "Leader change"},
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

    def _signals_source_status(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT source, module, status, last_success_at, last_failure_at, last_error, updated_at
            FROM source_health
            WHERE module = 'signals'
            ORDER BY source
            """
        )
        by_source = {str(row["source"]): row for row in rows}
        defaults = {
            "eastmoney_concept_blocks": {"status": "not_collected", "last_error": None},
            "free_stockdb_bk": {"status": "not_collected", "last_error": None},
            "eastmoney_fund_flow_minute": {"status": "not_collected", "last_error": None},
            "eastmoney_dragon_tiger_board": {"status": "not_collected", "last_error": None},
            "eastmoney_industry_comparison": {"status": "not_collected", "last_error": None},
            "hsgt_realtime": {
                "status": "prepared",
                "last_error": "Northbound minute reliability is limited after 2024-08 disclosure changes; check HKEX for authoritative daily data.",
            },
            "ths_hot_reason": {
                "status": "planned",
                "last_error": "10jqka hot reason endpoint has not been revalidated in this runtime.",
            },
        }
        for source, value in defaults.items():
            if source not in by_source:
                rows.append(
                    {
                        "source": source,
                        "module": "signals",
                        "status": value["status"],
                        "last_success_at": None,
                        "last_failure_at": None,
                        "last_error": value["last_error"],
                        "updated_at": None,
                    }
                )
        return rows

    def _chip_liquidity_layer_payload(self, symbol: str | None, limit: int) -> dict[str, Any]:
        record_rows = self._list_module_records("chip_liquidity", symbol, limit)
        money_flow_rows = self.list_money_flow(symbol, limit)
        margin_rows = [row for row in record_rows if row.get("source") == "margin_trading"]
        block_rows = [row for row in record_rows if row.get("source") == "block_trade"]
        holder_rows = [row for row in record_rows if row.get("source") == "holder_num_change"]
        dividend_rows = [row for row in record_rows if row.get("source") == "dividend_history"]
        latest_margin = margin_rows[0] if margin_rows else None
        latest_block = block_rows[0] if block_rows else None
        latest_holder = holder_rows[0] if holder_rows else None
        latest_dividend = dividend_rows[0] if dividend_rows else None
        latest_flow = money_flow_rows[0] if money_flow_rows else None
        source_status = self._chip_liquidity_source_status()
        all_rows = record_rows + money_flow_rows
        latest_time = _latest_fetched_at(all_rows)
        sections = [
            {
                "id": "margin_financing",
                "title": "Margin Financing",
                "source": "margin_trading",
                "fetched_at": _latest_fetched_at(margin_rows),
                "cards": [
                    {"label": "Records", "value": len(margin_rows)},
                    {"label": "Latest date", "value": latest_margin.get("date") if latest_margin else None},
                    {"label": "Margin balance", "value": latest_margin.get("margin_balance") if latest_margin else None},
                    {"label": "Short balance", "value": latest_margin.get("short_balance") if latest_margin else None},
                    {"label": "Total balance", "value": latest_margin.get("margin_short_balance") if latest_margin else None},
                    _source_capability_card(source_status, "margin_trading", "Connector"),
                ],
            },
            {
                "id": "block_trade",
                "title": "Block Trades",
                "source": "block_trade",
                "fetched_at": _latest_fetched_at(block_rows),
                "cards": [
                    {"label": "Records", "value": len(block_rows)},
                    {"label": "Latest date", "value": latest_block.get("date") if latest_block else None},
                    {"label": "Price", "value": latest_block.get("price") if latest_block else None},
                    {"label": "Premium %", "value": latest_block.get("premium_pct") if latest_block else None},
                    {"label": "Amount", "value": latest_block.get("amount") if latest_block else None},
                    _source_capability_card(source_status, "block_trade", "Connector"),
                ],
            },
            {
                "id": "holder_concentration",
                "title": "Holder Count / Chip Concentration",
                "source": "holder_num_change",
                "fetched_at": _latest_fetched_at(holder_rows),
                "cards": [
                    {"label": "Records", "value": len(holder_rows)},
                    {"label": "Latest date", "value": latest_holder.get("date") if latest_holder else None},
                    {"label": "Holder count", "value": latest_holder.get("holder_num") if latest_holder else None},
                    {"label": "QoQ change %", "value": latest_holder.get("change_ratio") if latest_holder else None},
                    {"label": "Avg shares", "value": latest_holder.get("avg_shares") if latest_holder else None},
                    _source_capability_card(source_status, "holder_num_change", "Connector"),
                ],
            },
            {
                "id": "dividend_history",
                "title": "Dividend / Bonus History",
                "source": "dividend_history",
                "fetched_at": _latest_fetched_at(dividend_rows),
                "cards": [
                    {"label": "Records", "value": len(dividend_rows)},
                    {"label": "Latest date", "value": latest_dividend.get("date") if latest_dividend else None},
                    {"label": "Cash dividend", "value": latest_dividend.get("bonus_rmb") if latest_dividend else None},
                    {"label": "Transfer ratio", "value": latest_dividend.get("transfer_ratio") if latest_dividend else None},
                    {"label": "Bonus ratio", "value": latest_dividend.get("bonus_ratio") if latest_dividend else None},
                    _source_capability_card(source_status, "dividend_history", "Connector"),
                ],
            },
            {
                "id": "fund_flow_120d",
                "title": "120-Day Fund Flow",
                "source": "stock_fund_flow_120d",
                "fetched_at": _latest_fetched_at(money_flow_rows),
                "cards": [
                    {"label": "Daily points", "value": len(money_flow_rows)},
                    {"label": "Latest date", "value": latest_flow.get("trade_date") if latest_flow else None},
                    {"label": "Main net inflow", "value": latest_flow.get("main_net_inflow") if latest_flow else None},
                    {"label": "Retail net inflow", "value": latest_flow.get("retail_net_inflow") if latest_flow else None},
                    {"label": "Turnover rate", "value": latest_flow.get("turnover_rate") if latest_flow else None},
                    _source_capability_card(source_status, "stock_fund_flow_120d", "Connector"),
                ],
            },
            {
                "id": "source_capabilities",
                "title": "Source Capabilities",
                "source": "connector_registry",
                "fetched_at": latest_time,
                "cards": [
                    _source_capability_card(source_status, "margin_trading", "Margin financing"),
                    _source_capability_card(source_status, "block_trade", "Block trades"),
                    _source_capability_card(source_status, "holder_num_change", "Holder count"),
                    _source_capability_card(source_status, "dividend_history", "Dividends"),
                    _source_capability_card(source_status, "stock_fund_flow_120d", "120-day fund flow"),
                    _source_capability_card(source_status, "fund_flow_backup", "Sina backup"),
                ],
            },
        ]
        tables = [
            {
                "id": "margin_financing",
                "title": "Margin Financing Detail",
                "rows": margin_rows,
                "columns": [
                    {"key": "date", "label": "Date"},
                    {"key": "margin_balance", "label": "Margin balance"},
                    {"key": "margin_buy", "label": "Margin buy"},
                    {"key": "margin_repay", "label": "Margin repay"},
                    {"key": "short_balance", "label": "Short balance"},
                    {"key": "short_sell_volume", "label": "Short sell vol"},
                    {"key": "short_repay_volume", "label": "Short repay vol"},
                    {"key": "margin_short_balance", "label": "Total balance"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
            {
                "id": "block_trades",
                "title": "Block Trades",
                "rows": block_rows,
                "columns": [
                    {"key": "date", "label": "Date"},
                    {"key": "price", "label": "Price"},
                    {"key": "close", "label": "Close"},
                    {"key": "premium_pct", "label": "Premium %"},
                    {"key": "volume", "label": "Volume"},
                    {"key": "amount", "label": "Amount"},
                    {"key": "buyer", "label": "Buyer"},
                    {"key": "seller", "label": "Seller"},
                    {"key": "source", "label": "Source"},
                ],
            },
            {
                "id": "holder_count",
                "title": "Holder Count Changes",
                "rows": holder_rows,
                "columns": [
                    {"key": "date", "label": "Date"},
                    {"key": "holder_num", "label": "Holder count"},
                    {"key": "change_num", "label": "Change count"},
                    {"key": "change_ratio", "label": "Change %"},
                    {"key": "avg_shares", "label": "Avg shares"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
            {
                "id": "dividends",
                "title": "Dividend / Bonus History",
                "rows": dividend_rows,
                "columns": [
                    {"key": "date", "label": "Date"},
                    {"key": "bonus_rmb", "label": "Cash dividend"},
                    {"key": "transfer_ratio", "label": "Transfer ratio"},
                    {"key": "bonus_ratio", "label": "Bonus ratio"},
                    {"key": "plan", "label": "Plan status"},
                    {"key": "source", "label": "Source"},
                ],
            },
            {
                "id": "fund_flow_120d",
                "title": "120-Day Fund Flow",
                "rows": money_flow_rows,
                "columns": [
                    {"key": "trade_date", "label": "Trade date"},
                    {"key": "main_net_inflow", "label": "Main net inflow"},
                    {"key": "retail_net_inflow", "label": "Retail net inflow"},
                    {"key": "turnover_rate", "label": "Turnover rate"},
                    {"key": "source", "label": "Source"},
                    {"key": "fetched_at", "label": "Fetched at"},
                ],
            },
        ]
        return {
            "symbol": symbol.upper() if symbol else None,
            "sections": sections,
            "tables": tables,
            "source_status": source_status,
        }

    def _chip_liquidity_source_status(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT source, module, status, last_success_at, last_failure_at, last_error, updated_at
            FROM source_health
            WHERE module = 'chip_liquidity'
            ORDER BY source
            """
        )
        by_source = {str(row["source"]): row for row in rows}
        defaults = {
            "margin_trading": {"status": "not_collected", "last_error": None},
            "block_trade": {"status": "not_collected", "last_error": None},
            "holder_num_change": {"status": "not_collected", "last_error": None},
            "dividend_history": {"status": "not_collected", "last_error": None},
            "stock_fund_flow_120d": {"status": "not_collected", "last_error": None},
            "fund_flow_backup": {
                "status": "prepared",
                "last_error": "Sina daily four-tier fund-flow backup is mapped from a-stock-data but not wired in this V1 module.",
            },
        }
        for source, value in defaults.items():
            if source not in by_source:
                rows.append(
                    {
                        "source": source,
                        "module": "chip_liquidity",
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

    def _list_news_records(self, symbol: str | None, limit: int) -> list[dict[str, Any]]:
        if symbol:
            rows = self._fetch_all(
                """
                SELECT module, source, data_key, symbol, record_date, payload_json, fetched_at
                FROM module_records
                WHERE module = 'news'
                  AND (upper(coalesce(symbol, '')) = ? OR coalesce(symbol, '') = '')
                ORDER BY fetched_at DESC, record_date DESC NULLS LAST
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        else:
            rows = self._fetch_all(
                """
                SELECT module, source, data_key, symbol, record_date, payload_json, fetched_at
                FROM module_records
                WHERE module = 'news'
                ORDER BY fetched_at DESC, record_date DESC NULLS LAST
                LIMIT ?
                """,
                (limit,),
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


def _latest_fetched_at(rows: list[dict[str, Any]]) -> Any:
    values = [row.get("fetched_at") for row in rows if row.get("fetched_at")]
    return max(values) if values else None


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
