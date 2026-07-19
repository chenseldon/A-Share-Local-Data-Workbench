from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .public_market import normalize_symbol


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
EM_MIN_INTERVAL = 1.0
_last_em_call = 0.0
_cninfo_orgid_map: dict[str, str] = {}


class AStockSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModuleRecord:
    module: str
    source: str
    data_key: str
    symbol: str | None
    record_date: str | None
    payload: dict[str, Any]
    fetched_at: datetime
    raw_payload_hash: str


def payload_hash(payload: object) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(str(text).encode("utf-8", errors="ignore")).hexdigest()


def six_digit_code(symbol: str) -> str:
    return normalize_symbol(symbol).split(".")[0]


def eastmoney_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> httpx.Response:
    global _last_em_call
    elapsed = time.monotonic() - _last_em_call
    if elapsed < EM_MIN_INTERVAL:
        time.sleep(EM_MIN_INTERVAL - elapsed)

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    try:
        response = http_client.get(url, params=params, headers={"User-Agent": UA, **(headers or {})}, timeout=timeout)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise AStockSourceError(f"Eastmoney request failed: {exc}") from exc
    finally:
        _last_em_call = time.monotonic()
        if owns_client:
            http_client.close()


def eastmoney_post_json(
    url: str,
    *,
    json_payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> httpx.Response:
    global _last_em_call
    if client is None:
        elapsed = time.monotonic() - _last_em_call
        if elapsed < EM_MIN_INTERVAL:
            time.sleep(EM_MIN_INTERVAL - elapsed)

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    try:
        response = http_client.post(url, json=json_payload, headers={"User-Agent": UA, **(headers or {})}, timeout=timeout)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise AStockSourceError(f"Eastmoney request failed: {exc}") from exc
    finally:
        if client is None:
            _last_em_call = time.monotonic()
        if owns_client:
            http_client.close()


def _to_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _to_wan(value: Any) -> float | None:
    number = _to_float(value)
    return round(number / 10000, 2) if number is not None else None


def _to_date(value: Any) -> str | None:
    if value in (None, "", "-", "--"):
        return None
    text = str(value)
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def eastmoney_reports(symbol: str, max_pages: int = 1, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    code = six_digit_code(symbol)
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*",
            "pageSize": "50",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": "2000-01-01",
            "endTime": "2030-01-01",
            "pageNo": str(page),
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": code,
            "rcode": "",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        response = eastmoney_get(REPORT_API, params=params, headers={"Referer": "https://data.eastmoney.com/"}, timeout=30, client=client)
        payload = response.json()
        page_rows = payload.get("data") or []
        if not isinstance(page_rows, list) or not page_rows:
            break
        rows.extend(page_rows)
        total_pages = payload.get("TotalPage") or payload.get("totalPage") or 1
        if page >= int(total_pages):
            break
    return rows


def eastmoney_industry_reports(
    industry_code: str = "*",
    max_pages: int = 1,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": industry_code or "*",
            "pageSize": "50",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": "2000-01-01",
            "endTime": "2030-01-01",
            "pageNo": str(page),
            "fields": "",
            "qType": "1",
            "orgCode": "",
            "code": "",
            "rcode": "",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        response = eastmoney_get(REPORT_API, params=params, headers={"Referer": "https://data.eastmoney.com/"}, timeout=30, client=client)
        payload = response.json()
        page_rows = payload.get("data") or []
        if not isinstance(page_rows, list) or not page_rows:
            break
        rows.extend(page_rows)
        total_pages = payload.get("TotalPage") or payload.get("totalPage") or 1
        if page >= int(total_pages):
            break
    return rows


def normalize_eastmoney_report(symbol: str, record: dict[str, Any], fetched_at: datetime) -> dict[str, Any]:
    info_code = str(record.get("infoCode") or record.get("info_code") or payload_hash(record)[:16])
    eps = {
        "this_year": record.get("predictThisYearEps"),
        "next_year": record.get("predictNextYearEps"),
        "next_two_year": record.get("predictNextTwoYearEps"),
    }
    return {
        "id": f"eastmoney-report-{six_digit_code(symbol)}-{info_code}",
        "symbol": normalize_symbol(symbol),
        "title": str(record.get("title") or ""),
        "institution": record.get("orgSName") or record.get("orgName"),
        "analyst": record.get("researcher"),
        "rating": record.get("emRatingName") or record.get("rating"),
        "report_date": _to_date(record.get("publishDate")) or fetched_at.date().isoformat(),
        "eps_forecast": json.dumps(eps, ensure_ascii=False),
        "url": PDF_TPL.format(info_code=info_code),
        "source": "eastmoney_reports",
        "fetched_at": fetched_at,
        "raw_payload_hash": payload_hash(record),
    }


def eastmoney_pdf_url(info_code: str) -> str:
    return PDF_TPL.format(info_code=info_code)


def normalize_eastmoney_industry_report(symbol: str | None, record: dict[str, Any], fetched_at: datetime) -> ModuleRecord:
    normalized_symbol = normalize_symbol(symbol) if symbol else None
    info_code = str(record.get("infoCode") or record.get("info_code") or payload_hash(record)[:16])
    report_date = _to_date(record.get("publishDate")) or fetched_at.date().isoformat()
    payload = {
        "id": f"eastmoney-industry-report-{info_code}",
        "symbol": normalized_symbol,
        "title": str(record.get("title") or ""),
        "industry": record.get("industryName") or record.get("industry"),
        "industry_code": record.get("industryCode"),
        "institution": record.get("orgSName") or record.get("orgName"),
        "analyst": record.get("researcher"),
        "rating": record.get("emRatingName") or record.get("rating"),
        "report_type": record.get("reportType"),
        "report_date": report_date,
        "url": eastmoney_pdf_url(info_code),
        "source": "eastmoney_industry_reports",
    }
    return ModuleRecord(
        module="reports",
        source="eastmoney_industry_reports",
        data_key=info_code,
        symbol=normalized_symbol,
        record_date=report_date,
        payload=payload,
        fetched_at=fetched_at,
        raw_payload_hash=payload_hash(record),
    )


def eastmoney_stock_info(symbol: str, client: httpx.Client | None = None) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".")
    market_code = 1 if exchange == "SH" else 0
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
        "secid": f"{market_code}.{code}",
    }
    response = eastmoney_get("https://push2.eastmoney.com/api/qt/stock/get", params=params, timeout=10, client=client)
    data = response.json().get("data") or {}
    if not data:
        raise AStockSourceError(f"Eastmoney stock info returned no data for {normalized}")
    return {
        "code": data.get("f57") or code,
        "name": data.get("f58") or normalized,
        "industry": data.get("f127"),
        "total_shares": _to_float(data.get("f84")),
        "float_shares": _to_float(data.get("f85")),
        "mcap": _to_float(data.get("f116")),
        "float_mcap": _to_float(data.get("f117")),
        "list_date": _to_date(data.get("f189")),
        "price": _to_float(data.get("f43")),
        "raw": data,
    }


def eastmoney_concept_blocks(symbol: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".")
    market_code = 1 if exchange == "SH" else 0
    params = {
        "fltt": "2",
        "invt": "2",
        "secid": f"{market_code}.{code}",
        "spt": "3",
        "pi": "0",
        "pz": "200",
        "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    fetched_at = datetime.now(UTC)
    response = eastmoney_get(
        "https://push2.eastmoney.com/api/qt/slist/get",
        params=params,
        headers={"Referer": "https://quote.eastmoney.com/"},
        timeout=15,
        client=client,
    )
    diff = (response.json().get("data") or {}).get("diff") or []
    items = list(diff.values()) if isinstance(diff, dict) else diff
    records: list[ModuleRecord] = []
    for item in items:
        payload = {
            "symbol": normalized,
            "name": item.get("f14"),
            "code": item.get("f12"),
            "change_pct": item.get("f3"),
            "lead_stock": item.get("f128"),
        }
        records.append(
            ModuleRecord(
                module="signals",
                source="eastmoney_concept_blocks",
                data_key=str(payload["code"] or payload_hash(payload)[:16]),
                symbol=normalized,
                record_date=fetched_at.date().isoformat(),
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(payload),
            )
        )
    return records


def eastmoney_datacenter(
    report_name: str,
    *,
    filter_str: str = "",
    page_size: int = 50,
    page_number: int = 1,
    sort_columns: str = "",
    sort_types: str = "",
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "pageSize": str(page_size),
        "pageNumber": str(page_number),
        "reportName": report_name,
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
    }
    if filter_str:
        params["filter"] = filter_str
    response = eastmoney_get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params=params,
        headers={"Referer": "https://data.eastmoney.com/"},
        timeout=20,
        client=client,
    )
    payload = response.json()
    rows = (payload.get("result") or {}).get("data") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    return rows if isinstance(rows, list) else []


def eastmoney_fund_flow_minute(symbol: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".")
    market_code = 1 if exchange == "SH" else 0
    fetched_at = datetime.now(UTC)
    params = {
        "secid": f"{market_code}.{code}",
        "klt": "1",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    response = eastmoney_get(
        "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
        params=params,
        headers={"Referer": "https://quote.eastmoney.com/", "Origin": "https://quote.eastmoney.com"},
        timeout=15,
        client=client,
    )
    klines = (response.json().get("data") or {}).get("klines") or []
    records: list[ModuleRecord] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 6:
            continue
        minute_time = parts[0]
        payload = {
            "symbol": normalized,
            "time": minute_time,
            "main_net": _to_float(parts[1]),
            "small_net": _to_float(parts[2]),
            "mid_net": _to_float(parts[3]),
            "large_net": _to_float(parts[4]),
            "super_net": _to_float(parts[5]),
        }
        records.append(
            ModuleRecord(
                module="signals",
                source="eastmoney_fund_flow_minute",
                data_key=f"{code}-{minute_time}",
                symbol=normalized,
                record_date=_to_date(minute_time) or fetched_at.date().isoformat(),
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(line),
            )
        )
    return records


def eastmoney_dragon_tiger_board(
    symbol: str,
    trade_date: str | None = None,
    look_back: int = 30,
    client: httpx.Client | None = None,
) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    fetched_at = datetime.now(UTC)
    end_date = datetime.fromisoformat(trade_date).date() if trade_date else fetched_at.date()
    start_date = end_date - timedelta(days=look_back)
    filter_str = f"(TRADE_DATE>='{start_date.isoformat()}')(TRADE_DATE<='{end_date.isoformat()}')(SECURITY_CODE=\"{code}\")"
    rows = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=filter_str,
        page_size=50,
        sort_columns="TRADE_DATE",
        sort_types="-1",
        client=client,
    )
    records: list[ModuleRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        record_date = _to_date(row.get("TRADE_DATE")) or end_date.isoformat()
        payload = {
            "symbol": normalized,
            "date": record_date,
            "name": row.get("SECURITY_NAME_ABBR") or row.get("SECURITY_NAME") or row.get("SECURITY_NAME_ABBR"),
            "reason": row.get("EXPLAIN") or row.get("BILLBOARD_NAME") or row.get("TRADE_TYPE"),
            "net_buy_wan": _to_wan(row.get("BILLBOARD_NET_AMT") or row.get("NET_BUY_AMT")),
            "buy_wan": _to_wan(row.get("BILLBOARD_BUY_AMT") or row.get("BUY_AMT")),
            "sell_wan": _to_wan(row.get("BILLBOARD_SELL_AMT") or row.get("SELL_AMT")),
            "turnover_pct": _to_float(row.get("TURNOVERRATE") or row.get("TURNOVER_RATE")),
            "close": _to_float(row.get("CLOSE_PRICE") or row.get("CLOSE")),
            "change_pct": _to_float(row.get("CHANGE_RATE") or row.get("CHANGE_PCT")),
            "source": "eastmoney_dragon_tiger_board",
        }
        records.append(
            ModuleRecord(
                module="signals",
                source="eastmoney_dragon_tiger_board",
                data_key=f"{code}-{record_date}-{index}",
                symbol=normalized,
                record_date=record_date,
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row),
            )
        )
    if records:
        latest_date = str(records[0].record_date or end_date.isoformat())
        records.extend(_eastmoney_dragon_tiger_seats(normalized, latest_date, "buy", client=client))
        records.extend(_eastmoney_dragon_tiger_seats(normalized, latest_date, "sell", client=client))
    return records


def _eastmoney_dragon_tiger_seats(symbol: str, trade_date: str, side: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    code = symbol.split(".")[0]
    report_name = "RPT_BILLBOARD_DAILYDETAILSBUY" if side == "buy" else "RPT_BILLBOARD_DAILYDETAILSSELL"
    amount_field = "BUY" if side == "buy" else "SELL"
    rows = eastmoney_datacenter(
        report_name,
        filter_str=f"(TRADE_DATE='{trade_date}')(SECURITY_CODE=\"{code}\")",
        page_size=10,
        sort_columns=amount_field,
        sort_types="-1",
        client=client,
    )
    fetched_at = datetime.now(UTC)
    records: list[ModuleRecord] = []
    for index, row in enumerate(rows[:5]):
        if not isinstance(row, dict):
            continue
        payload = {
            "symbol": symbol,
            "date": _to_date(row.get("TRADE_DATE")) or trade_date,
            "side": side,
            "name": row.get("OPERATEDEPT_NAME") or row.get("OPERATE_DEPT_NAME") or row.get("SALES_DEPT_NAME"),
            "buy_wan": _to_wan(row.get("BUY")),
            "sell_wan": _to_wan(row.get("SELL")),
            "net_wan": _to_wan(row.get("NET")),
            "source": f"eastmoney_dragon_tiger_{side}_seats",
        }
        records.append(
            ModuleRecord(
                module="signals",
                source=f"eastmoney_dragon_tiger_{side}_seats",
                data_key=f"{code}-{trade_date}-{side}-{index}",
                symbol=symbol,
                record_date=payload["date"],
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row),
            )
        )
    return records


def eastmoney_industry_comparison(
    symbol: str | None = None,
    top_n: int = 20,
    client: httpx.Client | None = None,
) -> list[ModuleRecord]:
    normalized_symbol = normalize_symbol(symbol) if symbol else None
    fetched_at = datetime.now(UTC)
    params = {
        "pn": "1",
        "pz": str(max(top_n, 20)),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f6,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    response = eastmoney_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params=params,
        headers={"Referer": "https://quote.eastmoney.com/"},
        timeout=15,
        client=client,
    )
    diff = (response.json().get("data") or {}).get("diff") or []
    items = list(diff.values()) if isinstance(diff, dict) else diff
    records: list[ModuleRecord] = []
    for rank, item in enumerate(items[:top_n], start=1):
        if not isinstance(item, dict):
            continue
        payload = {
            "symbol": normalized_symbol,
            "rank": rank,
            "name": item.get("f14"),
            "code": item.get("f12"),
            "change_pct": _to_float(item.get("f3")),
            "amount": _to_float(item.get("f6")),
            "up_count": item.get("f104"),
            "down_count": item.get("f105"),
            "leader": item.get("f128") or item.get("f140"),
            "leader_change": _to_float(item.get("f136") or item.get("f207")),
            "scope": "market_wide",
            "source": "eastmoney_industry_comparison",
        }
        records.append(
            ModuleRecord(
                module="signals",
                source="eastmoney_industry_comparison",
                data_key=str(payload["code"] or rank),
                symbol=normalized_symbol,
                record_date=fetched_at.date().isoformat(),
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(item),
            )
        )
    return records


def margin_trading(symbol: str, page_size: int = 30, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    fetched_at = datetime.now(UTC)
    rows = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str=f'(SCODE="{code}")',
        page_size=page_size,
        sort_columns="DATE",
        sort_types="-1",
        client=client,
    )
    records: list[ModuleRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        record_date = _to_date(row.get("DATE")) or fetched_at.date().isoformat()
        payload = {
            "symbol": normalized,
            "date": record_date,
            "margin_balance": _to_float(row.get("RZYE")),
            "margin_buy": _to_float(row.get("RZMRE")),
            "margin_repay": _to_float(row.get("RZCHE")),
            "short_balance": _to_float(row.get("RQYE")),
            "short_sell_volume": _to_float(row.get("RQMCL")),
            "short_repay_volume": _to_float(row.get("RQCHL")),
            "margin_short_balance": _to_float(row.get("RZRQYE")),
            "source": "margin_trading",
        }
        records.append(
            ModuleRecord(
                module="chip_liquidity",
                source="margin_trading",
                data_key=f"{code}-{record_date}-{index}",
                symbol=normalized,
                record_date=record_date,
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row),
            )
        )
    return records


def block_trade(symbol: str, page_size: int = 20, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    fetched_at = datetime.now(UTC)
    rows = eastmoney_datacenter(
        "RPT_DATA_BLOCKTRADE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="TRADE_DATE",
        sort_types="-1",
        client=client,
    )
    records: list[ModuleRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        record_date = _to_date(row.get("TRADE_DATE")) or fetched_at.date().isoformat()
        close = _to_float(row.get("CLOSE_PRICE"))
        deal_price = _to_float(row.get("DEAL_PRICE"))
        premium_pct = round((deal_price / close - 1) * 100, 2) if close and deal_price else None
        payload = {
            "symbol": normalized,
            "date": record_date,
            "price": deal_price,
            "close": close,
            "premium_pct": premium_pct,
            "volume": _to_float(row.get("DEAL_VOLUME")),
            "amount": _to_float(row.get("DEAL_AMT")),
            "buyer": row.get("BUYER_NAME"),
            "seller": row.get("SELLER_NAME"),
            "source": "block_trade",
        }
        records.append(
            ModuleRecord(
                module="chip_liquidity",
                source="block_trade",
                data_key=f"{code}-{record_date}-{index}",
                symbol=normalized,
                record_date=record_date,
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row),
            )
        )
    return records


def holder_num_change(symbol: str, page_size: int = 10, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    fetched_at = datetime.now(UTC)
    rows = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="END_DATE",
        sort_types="-1",
        client=client,
    )
    records: list[ModuleRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        record_date = _to_date(row.get("END_DATE")) or fetched_at.date().isoformat()
        payload = {
            "symbol": normalized,
            "date": record_date,
            "holder_num": _to_float(row.get("HOLDER_NUM")),
            "change_num": _to_float(row.get("HOLDER_NUM_CHANGE")),
            "change_ratio": _to_float(row.get("HOLDER_NUM_RATIO")),
            "avg_shares": _to_float(row.get("AVG_FREE_SHARES")),
            "source": "holder_num_change",
        }
        records.append(
            ModuleRecord(
                module="chip_liquidity",
                source="holder_num_change",
                data_key=f"{code}-{record_date}-{index}",
                symbol=normalized,
                record_date=record_date,
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row),
            )
        )
    return records


def dividend_history(symbol: str, page_size: int = 20, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    fetched_at = datetime.now(UTC)
    rows = eastmoney_datacenter(
        "RPT_SHAREBONUS_DET",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="EX_DIVIDEND_DATE",
        sort_types="-1",
        client=client,
    )
    records: list[ModuleRecord] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        record_date = _to_date(row.get("EX_DIVIDEND_DATE") or row.get("EQUITY_RECORD_DATE")) or fetched_at.date().isoformat()
        payload = {
            "symbol": normalized,
            "date": record_date,
            "bonus_rmb": _to_float(row.get("PRETAX_BONUS_RMB")),
            "transfer_ratio": _to_float(row.get("TRANSFER_RATIO")),
            "bonus_ratio": _to_float(row.get("BONUS_RATIO")),
            "plan": row.get("ASSIGN_PROGRESS"),
            "source": "dividend_history",
        }
        records.append(
            ModuleRecord(
                module="chip_liquidity",
                source="dividend_history",
                data_key=f"{code}-{record_date}-{index}",
                symbol=normalized,
                record_date=record_date,
                payload=payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row),
            )
        )
    return records


def stock_fund_flow_120d(symbol: str, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".")
    market_code = 1 if exchange == "SH" else 0
    params = {
        "secid": f"{market_code}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    response = eastmoney_get(
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
        params=params,
        headers={"Referer": "https://quote.eastmoney.com/", "Origin": "https://quote.eastmoney.com"},
        timeout=15,
        client=client,
    )
    klines = (response.json().get("data") or {}).get("klines") or []
    rows: list[dict[str, Any]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 6:
            continue
        rows.append(
            {
                "symbol": normalized,
                "trade_date": parts[0],
                "main_net_inflow": _to_float(parts[1]),
                "retail_net_inflow": _to_float(parts[2]),
                "mid_net_inflow": _to_float(parts[3]),
                "large_net_inflow": _to_float(parts[4]),
                "super_net_inflow": _to_float(parts[5]),
                "turnover_rate": _to_float(parts[6] if len(parts) > 6 else None),
                "source": "stock_fund_flow_120d",
                "raw_payload_hash": payload_hash(line),
            }
        )
    return rows


def sina_financial_report(symbol: str, report_type: str = "lrb", num: int = 8, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".")
    paper_code = f"{exchange.lower()}{code}"
    fetched_at = datetime.now(UTC)
    params = {"paperCode": paper_code, "source": report_type, "type": "0", "page": "1", "num": str(num)}
    owns_client = client is None
    http_client = client or httpx.Client(timeout=15, headers={"User-Agent": UA})
    try:
        response = http_client.get("https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022", params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AStockSourceError(f"Sina financial report request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    result = payload.get("result") or {}
    data = result.get("data") or {}
    records = data.get("report_list") or data.get("list") or data.get("data") or []
    rows: list[ModuleRecord] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        report_date = _to_date(record.get("report_date") or record.get("date") or record.get("报告期"))
        row_payload = {"symbol": normalized, "statement_type": report_type, **record}
        rows.append(
            ModuleRecord(
                module="fundamentals",
                source="sina_financial_report",
                data_key=f"{report_type}-{report_date or index}",
                symbol=normalized,
                record_date=report_date,
                payload=row_payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row_payload),
            )
        )
    return rows


def _cninfo_ts_to_date(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC).date().isoformat()
    return _to_date(value)


def _cninfo_orgid(code: str, client: httpx.Client | None = None) -> str:
    global _cninfo_orgid_map
    if not _cninfo_orgid_map:
        owns_client = client is None
        http_client = client or httpx.Client(timeout=15, headers={"User-Agent": UA})
        try:
            response = http_client.get("http://www.cninfo.com.cn/new/data/szse_stock.json")
            response.raise_for_status()
            stock_list = response.json().get("stockList") or []
            _cninfo_orgid_map = {str(item["code"]): str(item["orgId"]) for item in stock_list if item.get("code") and item.get("orgId")}
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            _cninfo_orgid_map = {}
        finally:
            if owns_client:
                http_client.close()
    org = _cninfo_orgid_map.get(code)
    if org:
        return org
    if code.startswith("6"):
        return f"gssh0{code}"
    if code.startswith(("8", "4", "9")):
        return f"gsbj0{code}"
    return f"gssz0{code}"


def cninfo_announcements(symbol: str, page_size: int = 30, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    org_id = _cninfo_orgid(code, client=client)
    payload = {
        "stock": f"{code},{org_id}",
        "tabName": "fulltext",
        "pageSize": str(page_size),
        "pageNum": "1",
        "column": "",
        "category": "",
        "plate": "",
        "seDate": "",
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    owns_client = client is None
    http_client = client or httpx.Client(timeout=15, headers={"User-Agent": UA})
    try:
        response = http_client.post(
            "https://www.cninfo.com.cn/new/hisAnnouncement/query",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://www.cninfo.com.cn/new/disclosure", "Origin": "https://www.cninfo.com.cn"},
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AStockSourceError(f"CNINFO announcement request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()
    rows: list[dict[str, Any]] = []
    for item in data.get("announcements") or []:
        announcement_id = str(item.get("announcementId") or payload_hash(item)[:16])
        rows.append(
            {
                "id": f"cninfo-{code}-{announcement_id}",
                "symbol": normalized,
                "title": re.sub(r"<[^>]+>", "", str(item.get("announcementTitle") or "")),
                "published_at": _cninfo_ts_to_date(item.get("announcementTime")) or datetime.now(UTC).date().isoformat(),
                "url": f"https://www.cninfo.com.cn/new/disclosure/detail?announcementId={announcement_id}",
                "source": "cninfo_announcements",
                "raw_payload_hash": payload_hash(item),
            }
        )
    return rows


def cninfo_irm(symbol: str, page_size: int = 30, page_num: int = 1, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".")[0]
    fetched_at = datetime.now(UTC)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=15, headers={"User-Agent": UA})
    try:
        keyboard_response = http_client.post(
            "https://irm.cninfo.com.cn/newircs/index/queryKeyboardInfo",
            data={"keyWord": code},
            headers={"Referer": "https://irm.cninfo.com.cn/", "Origin": "https://irm.cninfo.com.cn"},
        )
        keyboard_response.raise_for_status()
        keyboard_payload = keyboard_response.json()
        candidates = keyboard_payload if isinstance(keyboard_payload, list) else keyboard_payload.get("data") or []
        if not candidates:
            return []
        org_id = str((candidates[0] or {}).get("secid") or "")
        if not org_id:
            return []
        question_response = http_client.post(
            "https://irm.cninfo.com.cn/newircs/company/question",
            params={
                "_t": "1",
                "stockcode": code,
                "orgId": org_id,
                "pageSize": str(page_size),
                "pageNum": str(page_num),
                "keyWord": "",
                "startDay": "",
                "endDay": "",
            },
            headers={"Referer": "https://irm.cninfo.com.cn/", "Origin": "https://irm.cninfo.com.cn"},
        )
        question_response.raise_for_status()
        payload = question_response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AStockSourceError(f"CNINFO IRM request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    rows = payload.get("rows") or payload.get("data") or []
    records: list[ModuleRecord] = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        asked_at = _cninfo_ts_to_datetime(item.get("pubDate") or item.get("questionTime") or item.get("createTime"))
        answer = item.get("attachedContent") or item.get("answerContent") or item.get("replyContent")
        record_payload = {
            "symbol": normalized,
            "code": item.get("stockCode") or code,
            "name": item.get("companyShortName") or item.get("shortName"),
            "question": _clean_text(item.get("mainContent") or item.get("questionContent")),
            "answer": _clean_text(answer),
            "answerer": item.get("attachedAuthor") or item.get("replyAuthor") or item.get("answerer"),
            "asked_at": asked_at,
            "answered": bool(answer),
            "source": "cninfo_irm",
        }
        records.append(
            ModuleRecord(
                module="sentiment",
                source="cninfo_irm",
                data_key=str(item.get("id") or item.get("questionId") or f"{code}-{asked_at or index}"),
                symbol=normalized,
                record_date=_to_date(asked_at) or fetched_at.date().isoformat(),
                payload=record_payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(item),
            )
        )
    return records


def ths_hot_list(period: str = "hour", top: int = 50, client: httpx.Client | None = None) -> list[ModuleRecord]:
    if period not in {"hour", "day"}:
        raise ValueError("10jqka hot list period must be 'hour' or 'day'.")
    fetched_at = datetime.now(UTC)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=15, headers={"User-Agent": UA})
    try:
        response = http_client.get(
            "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock",
            params={"stock_type": "a", "type": period, "list_type": "normal"},
            headers={"Referer": "https://dq.10jqka.com.cn/", "Origin": "https://dq.10jqka.com.cn"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AStockSourceError(f"10jqka hot list request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    stock_list = (payload.get("data") or {}).get("stock_list") or []
    records: list[ModuleRecord] = []
    for index, item in enumerate(stock_list[:top]):
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "")
        symbol_value = _normalize_code_or_none(code)
        tag = item.get("tag") if isinstance(item.get("tag"), dict) else {}
        concepts = tag.get("concept_tag") if isinstance(tag, dict) else None
        record_payload = {
            "rank": _to_int(item.get("order")) or index + 1,
            "symbol": symbol_value,
            "code": code,
            "name": item.get("name"),
            "heat": _to_float(item.get("rate")),
            "change_pct": _to_float(item.get("rise_and_fall")),
            "rank_change": _to_float(item.get("hot_rank_chg")),
            "concepts": _join_tags(concepts),
            "popularity_tag": tag.get("popularity_tag") if isinstance(tag, dict) else None,
            "period": period,
            "scope": "market_wide",
            "source": "ths_hot_list",
        }
        records.append(
            ModuleRecord(
                module="sentiment",
                source="ths_hot_list",
                data_key=f"{period}-{code or index}",
                symbol=symbol_value,
                record_date=fetched_at.date().isoformat(),
                payload=record_payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(item),
            )
        )
    return records


def em_hot_rank(top: int = 50, client: httpx.Client | None = None) -> list[ModuleRecord]:
    fetched_at = datetime.now(UTC)
    body = {**_em_hot_body(), "marketType": "", "pageNo": 1, "pageSize": top}
    response = eastmoney_post_json(
        "https://emappdata.eastmoney.com/stockrank/getAllCurrentList",
        json_payload=body,
        headers={"Referer": "https://emappdata.eastmoney.com/"},
        timeout=15,
        client=client,
    )
    payload = response.json()
    rows = payload.get("data") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    details = _em_hot_rank_details(rows, client=client)
    records: list[ModuleRecord] = []
    for index, item in enumerate(rows[:top]):
        if not isinstance(item, dict):
            continue
        prefixed = str(item.get("sc") or item.get("securityCode") or "")
        code = prefixed[-6:] if len(prefixed) >= 6 else prefixed
        symbol_value = _normalize_prefixed_code(prefixed) or _normalize_code_or_none(code)
        detail = details.get(code) or {}
        record_payload = {
            "rank": _to_int(item.get("rk")) or index + 1,
            "symbol": symbol_value,
            "code": code,
            "name": detail.get("name") or item.get("name"),
            "price": detail.get("price"),
            "change_pct": detail.get("change_pct"),
            "rank_change": _to_float(item.get("hisRc") or item.get("rankChange")),
            "scope": "market_wide",
            "source": "em_hot_rank",
        }
        records.append(
            ModuleRecord(
                module="sentiment",
                source="em_hot_rank",
                data_key=code or str(index),
                symbol=symbol_value,
                record_date=fetched_at.date().isoformat(),
                payload=record_payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(item),
            )
        )
    return records


def em_hot_concept(symbol: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".")
    fetched_at = datetime.now(UTC)
    prefixed = f"{exchange}{code}"
    response = eastmoney_post_json(
        "https://emappdata.eastmoney.com/stockrank/getHotStockRankList",
        json_payload={**_em_hot_body(), "srcSecurityCode": prefixed},
        headers={"Referer": "https://emappdata.eastmoney.com/"},
        timeout=15,
        client=client,
    )
    payload = response.json()
    rows = payload.get("data") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    records: list[ModuleRecord] = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        concept_name = item.get("conceptName") or item.get("name")
        concept_id = item.get("conceptId") or item.get("bk") or item.get("code")
        record_payload = {
            "symbol": normalized,
            "concept": concept_name,
            "bk": concept_id,
            "heat": _to_float(item.get("hitCount") or item.get("heat") or item.get("count")),
            "source": "em_hot_concept",
        }
        records.append(
            ModuleRecord(
                module="sentiment",
                source="em_hot_concept",
                data_key=str(concept_id or concept_name or index),
                symbol=normalized,
                record_date=fetched_at.date().isoformat(),
                payload=record_payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(item),
            )
        )
    return records


def _em_hot_rank_details(rows: list[Any], client: httpx.Client | None = None) -> dict[str, dict[str, Any]]:
    secids: list[str] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        prefixed = str(item.get("sc") or "")
        code = prefixed[-6:] if len(prefixed) >= 6 else prefixed
        market = "1" if prefixed.startswith("SH") or code.startswith("6") else "0"
        if code:
            secids.append(f"{market}.{code}")
    if not secids:
        return {}
    response = eastmoney_get(
        "https://push2.eastmoney.com/api/qt/ulist.np/get",
        params={
            "ut": "f057cbcbce2a86e2866ab8877db1d059",
            "fltt": "2",
            "invt": "2",
            "fields": "f14,f3,f12,f2",
            "secids": ",".join(secids),
        },
        headers={"Referer": "https://quote.eastmoney.com/"},
        timeout=15,
        client=client,
    )
    diff = (response.json().get("data") or {}).get("diff") or []
    items = list(diff.values()) if isinstance(diff, dict) else diff
    details: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("f12") or "")
        details[code] = {
            "name": item.get("f14"),
            "price": _to_float(item.get("f2")),
            "change_pct": _to_float(item.get("f3")),
        }
    return details


def _em_hot_body() -> dict[str, str]:
    return {"appId": "appId01", "globalId": "786e4c21-70dc-435a-93bb-38"}


def _normalize_prefixed_code(value: str) -> str | None:
    if len(value) < 8:
        return None
    prefix = value[:2].upper()
    code = value[-6:]
    if prefix in {"SH", "SZ", "BJ"}:
        return f"{code}.{prefix}"
    return _normalize_code_or_none(code)


def _normalize_code_or_none(code: str) -> str | None:
    if not re.fullmatch(r"\d{6}", str(code)):
        return None
    try:
        return normalize_symbol(str(code))
    except ValueError:
        return None


def _join_tags(value: Any) -> str | None:
    if value in (None, "", "-", "--"):
        return None
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def _clean_text(value: Any) -> str | None:
    if value in (None, "", "-", "--"):
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(value))).strip()


def _cninfo_ts_to_datetime(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
    if value in (None, "", "-", "--"):
        return None
    return str(value)[:19]
