from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import connect, initialize_database
from .connectors.astock_sources import ModuleRecord, payload_hash
from .connectors.public_market import MarketSnapshot
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

    def save_market_snapshot(self, snapshot: MarketSnapshot) -> int:
        connection = connect(self.db_path)
        records_written = 0
        started_at = datetime.now(UTC)
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO securities
                (symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at)
                VALUES (?, ?, ?, ?, NULL, ?, true, ?, ?)
                """,
                (
                    snapshot.security.symbol,
                    snapshot.security.name,
                    snapshot.security.exchange,
                    snapshot.security.asset_type,
                    snapshot.security.sector,
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
            return self._fetch_all(
                """
                SELECT symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at
                FROM securities
                WHERE lower(symbol) LIKE lower(?) OR lower(name) LIKE lower(?)
                ORDER BY symbol
                LIMIT ?
                """,
                (pattern, pattern, limit),
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

    def chart_bars(self, symbol: str, limit: int = 120, adjustment: str = "none") -> list[dict[str, Any]]:
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
        ordered = list(reversed(rows))
        closes: list[float | None] = []
        for row in ordered:
            close = row.get("close")
            closes.append(float(close) if isinstance(close, (int, float)) else None)
            row["ma5"] = _moving_average(closes, 5)
            row["ma10"] = _moving_average(closes, 10)
            row["ma20"] = _moving_average(closes, 20)
        return ordered

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
        if module_id == "market":
            quote = self.latest_market_quote(symbol) if symbol else None
            rows = ([quote] if quote else []) + self._list_market_bars(symbol, limit)
        elif module_id == "fundamentals":
            rows = self._list_fundamentals(symbol, limit)
        elif module_id == "announcements":
            rows = self.list_announcements(symbol, limit)
        elif module_id == "reports":
            rows = self.list_reports(symbol, limit)
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
        return {"module": module_id, "status": status, "rows": rows}

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
