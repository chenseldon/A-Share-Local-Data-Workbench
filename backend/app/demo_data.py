from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .database import connect


FIXTURE_SOURCE = "local_fixture"
FETCHED_AT = datetime(2026, 7, 14, 7, 0, 0)
HASH = "local-fixture-not-market-data"


def seed_demo_data(db_path: Path | str | None = None) -> None:
    connection = connect(db_path)
    try:
        connection.executemany(
            """
            INSERT OR REPLACE INTO securities
            (symbol, name, exchange, asset_type, listing_date, sector, is_active, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("600519.SH", "Kweichow Moutai", "SSE", "stock", "2001-08-27", "Consumer Staples", True, FIXTURE_SOURCE, FETCHED_AT),
                ("300750.SZ", "CATL", "SZSE", "stock", "2018-06-11", "New Energy", True, FIXTURE_SOURCE, FETCHED_AT),
                ("688981.SH", "SMIC", "SSE STAR", "stock", "2020-07-16", "Semiconductors", True, FIXTURE_SOURCE, FETCHED_AT),
                ("510300.SH", "CSI 300 ETF", "SSE", "etf", "2012-05-28", "ETF", True, FIXTURE_SOURCE, FETCHED_AT),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO market_bars
            (symbol, trade_date, open, high, low, close, volume, amount, adjustment, source, fetched_at, raw_payload_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("600519.SH", "2026-07-13", 1510.0, 1528.5, 1498.0, 1519.2, 2145000, 3256000000, "none", FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("300750.SZ", "2026-07-13", 198.4, 204.8, 197.1, 202.7, 18450000, 3712000000, "none", FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("688981.SH", "2026-07-13", 62.2, 64.8, 61.4, 63.9, 52100000, 3298000000, "none", FIXTURE_SOURCE, FETCHED_AT, HASH),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO fundamentals
            (symbol, report_period, eps, roe, net_profit, revenue, total_market_cap, pe_ttm, pb, source, fetched_at, raw_payload_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("600519.SH", "2026-03-31", 18.7, 0.091, 24000000000, 46400000000, 1908000000000, 24.8, 8.1, FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("300750.SZ", "2026-03-31", 2.5, 0.052, 10900000000, 83200000000, 892000000000, 19.6, 4.2, FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("688981.SH", "2026-03-31", 0.18, 0.018, 1500000000, 13200000000, 508000000000, 68.4, 3.5, FIXTURE_SOURCE, FETCHED_AT, HASH),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO announcements
            (id, symbol, title, published_at, url, source, fetched_at, raw_payload_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("fixture-ann-600519-1", "600519.SH", "Quarterly operating update fixture", "2026-07-12 18:30:00", None, FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("fixture-ann-300750-1", "300750.SZ", "Capacity expansion progress fixture", "2026-07-11 20:10:00", None, FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("fixture-ann-688981-1", "688981.SH", "Technology platform update fixture", "2026-07-10 19:45:00", None, FIXTURE_SOURCE, FETCHED_AT, HASH),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO reports
            (id, symbol, title, institution, analyst, rating, report_date, eps_forecast, url, source, fetched_at, raw_payload_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("fixture-rpt-600519-1", "600519.SH", "Premium baijiu demand tracker fixture", "Example Securities", "Fixture Analyst", "Hold", "2026-07-09", "{\"2026E\": 72.1}", None, FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("fixture-rpt-300750-1", "300750.SZ", "Battery margin sensitivity fixture", "Example Securities", "Fixture Analyst", "Buy", "2026-07-08", "{\"2026E\": 10.4}", None, FIXTURE_SOURCE, FETCHED_AT, HASH),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO money_flow
            (symbol, trade_date, main_net_inflow, retail_net_inflow, turnover_rate, source, fetched_at, raw_payload_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("600519.SH", "2026-07-13", 128000000, -82000000, 0.31, FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("300750.SZ", "2026-07-13", 246000000, -154000000, 1.72, FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("688981.SH", "2026-07-13", -96000000, 43000000, 2.18, FIXTURE_SOURCE, FETCHED_AT, HASH),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO limit_up_pool
            (trade_date, symbol, name, reason, board_count, status, source, fetched_at, raw_payload_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-07-13", "002000.SZ", "Fixture Tech", "AI infrastructure fixture", 3, "limit_up", FIXTURE_SOURCE, FETCHED_AT, HASH),
                ("2026-07-13", "603000.SH", "Fixture Materials", "Semiconductor material fixture", 2, "broken_board", FIXTURE_SOURCE, FETCHED_AT, HASH),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO source_health
            (source, module, status, last_success_at, last_failure_at, last_error, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (FIXTURE_SOURCE, "market", "fresh", FETCHED_AT, None, None, FETCHED_AT),
                ("eastmoney", "reports", "not_collected", None, None, None, FETCHED_AT),
                ("cninfo", "announcements", "not_collected", None, None, None, FETCHED_AT),
                ("mootdx", "market", "not_collected", None, None, None, FETCHED_AT),
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO data_jobs
            (id, job_type, module, source, status, started_at, finished_at, records_written, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("fixture-job-1", "seed", "market", FIXTURE_SOURCE, "success", FETCHED_AT, FETCHED_AT, 4, None),
                ("fixture-job-2", "seed", "fundamentals", FIXTURE_SOURCE, "success", FETCHED_AT, FETCHED_AT, 3, None),
            ],
        )
    finally:
        connection.close()
