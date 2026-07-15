from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import connect, initialize_database
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
                    (symbol, price_time, last_price, previous_close, open, high, low, volume, amount, bid1, ask1, source, fetched_at, raw_payload_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    VALUES ('tencent_kline', 'market', 'fresh', ?, NULL, NULL, ?)
                    """,
                    (finished_at, finished_at),
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

    def record_market_failure(self, source: str, error_message: str) -> None:
        now = datetime.now(UTC)
        connection = connect(self.db_path)
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO source_health
                (source, module, status, last_success_at, last_failure_at, last_error, updated_at)
                VALUES (?, 'market', 'failed', NULL, ?, ?, ?)
                """,
                (source, now, error_message[:500], now),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO data_jobs
                (id, job_type, module, source, status, started_at, finished_at, records_written, error_message)
                VALUES (?, 'refresh', 'market', ?, 'failed', ?, ?, 0, ?)
                """,
                (str(uuid4()), source, now, now, error_message[:500]),
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
            SELECT symbol, price_time, last_price, previous_close, open, high, low, volume, amount, bid1, ask1, source, fetched_at
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
        elif module_id == "limit_up":
            rows = self._list_limit_up(symbol, limit)
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
