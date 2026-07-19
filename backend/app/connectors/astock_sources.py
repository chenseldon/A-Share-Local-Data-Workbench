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
ZTB_UT = "7eea3edcaed734bea9cbfc24409ed989"
SINA_OPTION_HEADERS = {"Referer": "https://stock.finance.sina.com.cn/"}
SINA_OPTION_UNDERLYINGS = {
    "510050": "50ETF",
    "510300": "300ETF",
    "588000": "科创50ETF",
    "510500": "500ETF",
}


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


def _to_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _format_limit_time(value: Any) -> str | None:
    if value in (None, "", "-", "--", 0, "0"):
        return None
    text = str(value).split(".")[0].zfill(6)
    return f"{text[0:2]}:{text[2:4]}:{text[4:6]}"


def _normalize_trade_date(value: str | None) -> str:
    if not value:
        return datetime.now(UTC).date().strftime("%Y%m%d")
    text = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text.replace("-", "")
    if re.fullmatch(r"\d{8}", text):
        return text
    raise AStockSourceError("Limit-up trade_date must use YYYYMMDD or YYYY-MM-DD.")


def _record_date_from_yyyymmdd(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def _limit_symbol(code: Any) -> str | None:
    if code in (None, ""):
        return None
    try:
        return normalize_symbol(str(code).zfill(6))
    except ValueError:
        return None


def _sina_option_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 12.0,
    client: httpx.Client | None = None,
) -> httpx.Response:
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    try:
        response = http_client.get(url, params=params, headers={"User-Agent": UA, **SINA_OPTION_HEADERS}, timeout=timeout)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise AStockSourceError(f"Sina option request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()


def _sina_option_list(param: str, client: httpx.Client | None = None) -> list[str]:
    response = _sina_option_get(f"https://hq.sinajs.cn/list={param}", client=client)
    text = response.content.decode("gbk", errors="replace")
    return text.split('"')[1].split(",") if '"' in text else []


def _option_float(value: Any) -> float | None:
    number = _to_float(value)
    return number if number is not None else None


def option_underlying_code(symbol: str | None = None) -> str:
    if not symbol:
        return "510050"
    code = normalize_symbol(symbol).split(".")[0]
    return code if code in SINA_OPTION_UNDERLYINGS else "510050"


def sina_option_codes(
    underlying: str = "510050",
    call: bool = True,
    client: httpx.Client | None = None,
) -> dict[str, list[str]]:
    code = option_underlying_code(underlying)
    cate = SINA_OPTION_UNDERLYINGS[code]
    response = _sina_option_get(
        "https://stock.finance.sina.com.cn/futures/api/openapi.php/StockOptionService.getStockName",
        params={"exchange": "null", "cate": cate},
        client=client,
    )
    try:
        months_raw = response.json()["result"]["data"]["contractMonth"]
    except (KeyError, TypeError, ValueError) as exc:
        raise AStockSourceError("Sina option contract months response schema changed.") from exc
    months: list[str] = []
    for value in months_raw or []:
        text = str(value)
        if re.fullmatch(r"\d{4}-\d{2}", text):
            months.append(text.replace("-", "")[2:])
        elif re.fullmatch(r"\d{4}", text):
            months.append(text)
    flag = "OP_UP_" if call else "OP_DOWN_"
    contracts: dict[str, list[str]] = {}
    for month in months:
        codes = [
            item.replace("CON_OP_", "")
            for item in _sina_option_list(f"{flag}{code}{month}", client=client)
            if item.startswith("CON_OP_")
        ]
        if codes:
            contracts[month] = codes
    return contracts


def sina_option_tquote(code: str, client: httpx.Client | None = None) -> dict[str, Any]:
    values = _sina_option_list(f"CON_OP_{code}", client=client)
    if len(values) < 43:
        raise AStockSourceError(f"Sina option T-quote returned {len(values)} fields for {code}.")
    return {
        "contract_code": code,
        "bid_vol": _option_float(values[0]),
        "bid": _option_float(values[1]),
        "last": _option_float(values[2]),
        "ask": _option_float(values[3]),
        "ask_vol": _option_float(values[4]),
        "open_interest": _option_float(values[5]),
        "pct": _option_float(values[6]),
        "strike": _option_float(values[7]),
        "prev_close": _option_float(values[8]),
        "open": _option_float(values[9]),
        "limit_up": _option_float(values[10]),
        "limit_down": _option_float(values[11]),
        "name": values[37],
        "amplitude": _option_float(values[38]),
        "high": _option_float(values[39]),
        "low": _option_float(values[40]),
        "volume": _option_float(values[41]),
        "amount": _option_float(values[42]),
    }


def sina_option_greeks(code: str, client: httpx.Client | None = None) -> dict[str, Any]:
    raw = _sina_option_list(f"CON_SO_{code}", client=client)
    if len(raw) < 16:
        raise AStockSourceError(f"Sina option Greeks returned {len(raw)} fields for {code}.")
    values = [raw[0]] + raw[4:]
    if len(values) < 13:
        raise AStockSourceError(f"Sina option Greeks normalized field count is too short for {code}.")
    return {
        "contract_code": code,
        "name": values[0],
        "volume": _option_float(values[1]),
        "delta": _option_float(values[2]),
        "gamma": _option_float(values[3]),
        "theta": _option_float(values[4]),
        "vega": _option_float(values[5]),
        "iv": _option_float(values[6]),
        "high": _option_float(values[7]),
        "low": _option_float(values[8]),
        "trade_code": values[9],
        "strike": _option_float(values[10]),
        "last": _option_float(values[11]),
        "theory": _option_float(values[12]),
    }


def sina_etf_option_records(
    symbol: str | None = None,
    *,
    max_contracts_per_side: int = 40,
    client: httpx.Client | None = None,
) -> list[ModuleRecord]:
    underlying = option_underlying_code(symbol)
    normalized_symbol = f"{underlying}.SH"
    fetched_at = datetime.now(UTC)
    records: list[ModuleRecord] = []
    contract_maps: dict[str, dict[str, list[str]]] = {}
    for side, is_call in (("call", True), ("put", False)):
        contracts = sina_option_codes(underlying, call=is_call, client=client)
        contract_maps[side] = contracts
        for month, codes in contracts.items():
            for index, contract_code in enumerate(codes):
                payload = {
                    "underlying": normalized_symbol,
                    "underlying_code": underlying,
                    "underlying_name": SINA_OPTION_UNDERLYINGS[underlying],
                    "month": month,
                    "side": side,
                    "contract_code": contract_code,
                    "rank": index + 1,
                    "source": "sina_option_codes",
                }
                records.append(
                    ModuleRecord(
                        module="etf_options",
                        source="sina_option_codes",
                        data_key=f"{underlying}-{side}-{month}-{contract_code}",
                        symbol=normalized_symbol,
                        record_date=fetched_at.date().isoformat(),
                        payload=payload,
                        fetched_at=fetched_at,
                        raw_payload_hash=payload_hash(payload),
                    )
                )

    near_codes: list[tuple[str, str, str]] = []
    for side, contracts in contract_maps.items():
        near_month = sorted(contracts)[0] if contracts else None
        if not near_month:
            continue
        for contract_code in contracts[near_month][:max_contracts_per_side]:
            near_codes.append((side, near_month, contract_code))

    for side, month, contract_code in near_codes:
        try:
            quote = {
                **sina_option_tquote(contract_code, client=client),
                "underlying": normalized_symbol,
                "underlying_code": underlying,
                "month": month,
                "side": side,
                "source": "sina_option_tquote",
            }
            records.append(
                ModuleRecord(
                    module="etf_options",
                    source="sina_option_tquote",
                    data_key=f"{underlying}-{side}-{month}-{contract_code}",
                    symbol=normalized_symbol,
                    record_date=fetched_at.date().isoformat(),
                    payload=quote,
                    fetched_at=fetched_at,
                    raw_payload_hash=payload_hash(quote),
                )
            )
        except AStockSourceError:
            continue
        try:
            greeks = {
                **sina_option_greeks(contract_code, client=client),
                "underlying": normalized_symbol,
                "underlying_code": underlying,
                "month": month,
                "side": side,
                "source": "sina_option_greeks",
            }
            records.append(
                ModuleRecord(
                    module="etf_options",
                    source="sina_option_greeks",
                    data_key=f"{underlying}-{side}-{month}-{contract_code}",
                    symbol=normalized_symbol,
                    record_date=fetched_at.date().isoformat(),
                    payload=greeks,
                    fetched_at=fetched_at,
                    raw_payload_hash=payload_hash(greeks),
                )
            )
        except AStockSourceError:
            continue
    return records


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


def normalize_eastmoney_stock_profile(symbol: str, info: dict[str, Any], fetched_at: datetime) -> ModuleRecord:
    normalized = normalize_symbol(symbol)
    payload = {
        "symbol": normalized,
        "code": info.get("code") or six_digit_code(normalized),
        "name": info.get("name") or normalized,
        "industry": info.get("industry"),
        "list_date": info.get("list_date"),
        "total_shares": info.get("total_shares"),
        "float_shares": info.get("float_shares"),
        "total_market_cap": info.get("mcap"),
        "float_market_cap": info.get("float_mcap"),
        "price": info.get("price"),
        "data_source": "eastmoney_stock_info",
    }
    return ModuleRecord(
        module="fundamentals",
        source="eastmoney_stock_profile",
        data_key=normalized,
        symbol=normalized,
        record_date=payload["list_date"] or fetched_at.date().isoformat(),
        payload=payload,
        fetched_at=fetched_at,
        raw_payload_hash=payload_hash(info),
    )


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


def _em_limit_pool_api(endpoint: str, sort: str, trade_date: str, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    normalized_date = _normalize_trade_date(trade_date)
    response = eastmoney_get(
        f"https://push2ex.eastmoney.com/{endpoint}",
        params={
            "ut": ZTB_UT,
            "dpt": "wz.ztzt",
            "Pageindex": "0",
            "pagesize": "10000",
            "sort": sort,
            "date": normalized_date,
        },
        headers={"Referer": "https://quote.eastmoney.com/"},
        timeout=15,
        client=client,
    )
    rows = (response.json().get("data") or {}).get("pool") or []
    return rows if isinstance(rows, list) else []


def _limit_record(
    *,
    source: str,
    trade_date: str,
    raw: dict[str, Any],
    data_key_suffix: str = "",
    payload: dict[str, Any],
    fetched_at: datetime,
) -> ModuleRecord | None:
    code = raw.get("c") or raw.get("code") or payload.get("code")
    symbol = _limit_symbol(code)
    if not symbol:
        return None
    data_key = f"{trade_date}-{symbol}{data_key_suffix}"
    payload = {"symbol": symbol, **payload, "source": source}
    return ModuleRecord(
        module="limit_up",
        source=source,
        data_key=data_key,
        symbol=symbol,
        record_date=_record_date_from_yyyymmdd(trade_date),
        payload=payload,
        fetched_at=fetched_at,
        raw_payload_hash=payload_hash(raw),
    )


def em_zt_pool(trade_date: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized_date = _normalize_trade_date(trade_date)
    fetched_at = datetime.now(UTC)
    records: list[ModuleRecord] = []
    for raw in _em_limit_pool_api("getTopicZTPool", "fbt:asc", normalized_date, client=client):
        stat = raw.get("zttj") or {}
        price = _to_float(raw.get("p"))
        payload = {
            "pool": "limit_up",
            "code": raw.get("c"),
            "name": raw.get("n"),
            "price": price / 1000 if price is not None else None,
            "pct": _to_float(raw.get("zdp")),
            "amount": _to_float(raw.get("amount")),
            "float_cap": _to_float(raw.get("ltsz")),
            "turnover": _to_float(raw.get("hs")),
            "limit_days": raw.get("lbc"),
            "first_seal": _format_limit_time(raw.get("fbt")),
            "last_seal": _format_limit_time(raw.get("lbt")),
            "seal_fund": _to_float(raw.get("fund")),
            "break_times": raw.get("zbc"),
            "industry": raw.get("hybk") or "",
            "zt_stat": f"{stat.get('days', '?')}d{stat.get('ct', '?')}b",
        }
        record = _limit_record(source="em_zt_pool", trade_date=normalized_date, raw=raw, payload=payload, fetched_at=fetched_at)
        if record:
            records.append(record)
    return records


def em_zb_pool(trade_date: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized_date = _normalize_trade_date(trade_date)
    fetched_at = datetime.now(UTC)
    records: list[ModuleRecord] = []
    for raw in _em_limit_pool_api("getTopicZBPool", "fbt:asc", normalized_date, client=client):
        stat = raw.get("zttj") or {}
        price = _to_float(raw.get("p"))
        limit_price = _to_float(raw.get("ztp"))
        payload = {
            "pool": "broken_board",
            "code": raw.get("c"),
            "name": raw.get("n"),
            "price": price / 1000 if price is not None else None,
            "limit_price": limit_price / 1000 if limit_price is not None else None,
            "pct": _to_float(raw.get("zdp")),
            "turnover": _to_float(raw.get("hs")),
            "first_seal": _format_limit_time(raw.get("fbt")),
            "break_times": raw.get("zbc"),
            "amplitude": _to_float(raw.get("zf")),
            "speed": _to_float(raw.get("zs")),
            "industry": raw.get("hybk") or "",
            "zt_stat": f"{stat.get('days', '?')}d{stat.get('ct', '?')}b",
        }
        record = _limit_record(source="em_zb_pool", trade_date=normalized_date, raw=raw, payload=payload, fetched_at=fetched_at)
        if record:
            records.append(record)
    return records


def em_dt_pool(trade_date: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized_date = _normalize_trade_date(trade_date)
    fetched_at = datetime.now(UTC)
    records: list[ModuleRecord] = []
    for raw in _em_limit_pool_api("getTopicDTPool", "fund:asc", normalized_date, client=client):
        price = _to_float(raw.get("p"))
        payload = {
            "pool": "limit_down",
            "code": raw.get("c"),
            "name": raw.get("n"),
            "price": price / 1000 if price is not None else None,
            "pct": _to_float(raw.get("zdp")),
            "turnover": _to_float(raw.get("hs")),
            "pe": _to_float(raw.get("pe")),
            "seal_fund": _to_float(raw.get("fund")),
            "last_seal": _format_limit_time(raw.get("lbt")),
            "board_amount": _to_float(raw.get("fba")),
            "dt_days": raw.get("days"),
            "open_times": raw.get("oc"),
            "industry": raw.get("hybk") or "",
        }
        record = _limit_record(source="em_dt_pool", trade_date=normalized_date, raw=raw, payload=payload, fetched_at=fetched_at)
        if record:
            records.append(record)
    return records


def em_yzt_pool(trade_date: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized_date = _normalize_trade_date(trade_date)
    fetched_at = datetime.now(UTC)
    records: list[ModuleRecord] = []
    for raw in _em_limit_pool_api("getYesterdayZTPool", "zs:desc", normalized_date, client=client):
        stat = raw.get("zttj") or {}
        price = _to_float(raw.get("p"))
        payload = {
            "pool": "yesterday_limit_up",
            "code": raw.get("c"),
            "name": raw.get("n"),
            "price": price / 1000 if price is not None else None,
            "pct": _to_float(raw.get("zdp")),
            "turnover": _to_float(raw.get("hs")),
            "amplitude": _to_float(raw.get("zf")),
            "speed": _to_float(raw.get("zs")),
            "y_first_seal": _format_limit_time(raw.get("yfbt")),
            "y_limit_days": raw.get("ylbc"),
            "industry": raw.get("hybk") or "",
            "zt_stat": f"{stat.get('days', '?')}d{stat.get('ct', '?')}b",
        }
        record = _limit_record(source="em_yzt_pool", trade_date=normalized_date, raw=raw, payload=payload, fetched_at=fetched_at)
        if record:
            records.append(record)
    return records


def ths_limit_up_pool(trade_date: str, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized_date = _normalize_trade_date(trade_date)
    fetched_at = datetime.now(UTC)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=15)
    try:
        response = http_client.get(
            "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool",
            params={
                "page": "1",
                "limit": "200",
                "field": "199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004",
                "filter": "HS,GEM2STAR",
                "order_field": "330324",
                "order_type": "0",
                "date": normalized_date,
            },
            headers={"User-Agent": UA, "Referer": "https://data.10jqka.com.cn/"},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AStockSourceError(f"10jqka limit-up request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    info = ((response.json().get("data") or {}).get("info") or [])
    rows = info if isinstance(info, list) else []
    records: list[ModuleRecord] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        first_time = None
        raw_first = raw.get("first_limit_up_time")
        if raw_first not in (None, "", "-", "--"):
            try:
                first_time = datetime.fromtimestamp(int(raw_first)).strftime("%H:%M:%S")
            except (TypeError, ValueError, OSError):
                first_time = None
        payload = {
            "pool": "ths_limit_up_reason",
            "code": raw.get("code"),
            "name": raw.get("name"),
            "price": _to_float(raw.get("latest")),
            "pct": _to_float(raw.get("change_rate")),
            "reason": raw.get("reason_type") or "",
            "board_type": raw.get("limit_up_type") or "",
            "seal_rate": _to_float(raw.get("limit_up_suc_rate")),
            "break_times": raw.get("open_num") or 0,
            "seal_amount": _to_float(raw.get("order_amount")),
            "high_days": raw.get("high_days") or "",
            "first_time": first_time,
            "is_again": raw.get("is_again_limit"),
        }
        record = _limit_record(source="ths_limit_up_pool", trade_date=normalized_date, raw=raw, payload=payload, fetched_at=fetched_at)
        if record:
            records.append(record)
    return records


def limit_up_sentiment(
    trade_date: str,
    limit_up_rows: list[ModuleRecord],
    broken_rows: list[ModuleRecord],
    down_rows: list[ModuleRecord],
    yesterday_rows: list[ModuleRecord],
) -> ModuleRecord:
    normalized_date = _normalize_trade_date(trade_date)
    ladder: dict[int, int] = {}
    for record in limit_up_rows:
        limit_days = record.payload.get("limit_days")
        if isinstance(limit_days, int):
            ladder[limit_days] = ladder.get(limit_days, 0) + 1
    limit_count = len(limit_up_rows)
    broken_count = len(broken_rows)
    down_count = len(down_rows)
    yesterday_count = len(yesterday_rows)
    promoted_count = sum(1 for record in yesterday_rows if (_to_float(record.payload.get("pct")) or 0) >= 9.8)
    payload = {
        "date": _record_date_from_yyyymmdd(normalized_date),
        "limit_up_count": limit_count,
        "broken_board_count": broken_count,
        "limit_down_count": down_count,
        "yesterday_limit_up_count": yesterday_count,
        "break_rate": round(broken_count / (limit_count + broken_count) * 100, 1) if (limit_count + broken_count) else 0,
        "max_height": max(ladder.keys(), default=0),
        "promotion_rate": round(promoted_count / yesterday_count * 100, 1) if yesterday_count else None,
        "ladder": dict(sorted(ladder.items())),
        "source": "limit_up_sentiment",
    }
    fetched_at = datetime.now(UTC)
    return ModuleRecord(
        module="limit_up",
        source="limit_up_sentiment",
        data_key=normalized_date,
        symbol=None,
        record_date=_record_date_from_yyyymmdd(normalized_date),
        payload=payload,
        fetched_at=fetched_at,
        raw_payload_hash=payload_hash(payload),
    )


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
    return _normalize_sina_financial_reports(normalized, report_type, data, fetched_at)


def _normalize_sina_financial_reports(
    normalized_symbol: str,
    report_type: str,
    data: dict[str, Any],
    fetched_at: datetime,
) -> list[ModuleRecord]:
    report_list = data.get("report_list")
    rows: list[ModuleRecord] = []
    if isinstance(report_list, dict):
        periods = list(report_list.items())[:8]
        for index, (period, period_payload) in enumerate(periods):
            if not isinstance(period_payload, dict):
                continue
            items = period_payload.get("data") or []
            report_date = _to_date(period)
            row_payload = _sina_statement_payload(normalized_symbol, report_type, report_date, items)
            rows.append(
                ModuleRecord(
                    module="fundamentals",
                    source="sina_financial_report",
                    data_key=f"{report_type}-{report_date or index}",
                    symbol=normalized_symbol,
                    record_date=report_date,
                    payload=row_payload,
                    fetched_at=fetched_at,
                    raw_payload_hash=payload_hash(row_payload),
                )
            )
        return rows

    records = report_list or data.get("list") or data.get("data") or []
    if isinstance(records, dict):
        records = list(records.values())
    for index, record in enumerate(records if isinstance(records, list) else []):
        if not isinstance(record, dict):
            continue
        report_date = _to_date(record.get("report_date") or record.get("date") or record.get("reportDate"))
        row_payload = {"symbol": normalized_symbol, "statement_type": report_type, "report_period": report_date, **record}
        rows.append(
            ModuleRecord(
                module="fundamentals",
                source="sina_financial_report",
                data_key=f"{report_type}-{report_date or index}",
                symbol=normalized_symbol,
                record_date=report_date,
                payload=row_payload,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(row_payload),
            )
        )
    return rows


def _sina_statement_payload(symbol: str, statement_type: str, report_date: str | None, items: Any) -> dict[str, Any]:
    item_map: dict[str, Any] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("item_title") or item.get("title") or item.get("name") or "").strip()
            if not title:
                continue
            item_map[title] = item.get("item_value") or item.get("value")
            yoy = item.get("yoy") or item.get("同比") or item.get("item_yoy")
            if yoy not in (None, ""):
                item_map[f"{title}_yoy"] = yoy
    return {
        "symbol": symbol,
        "statement_type": statement_type,
        "report_period": report_date,
        "revenue": _pick_statement_item(item_map, ("营业总收入", "营业收入")),
        "net_profit": _pick_statement_item(item_map, ("归属于母公司所有者的净利润", "净利润")),
        "eps": _pick_statement_item(item_map, ("基本每股收益", "每股收益")),
        "total_assets": _pick_statement_item(item_map, ("资产总计",)),
        "total_liabilities": _pick_statement_item(item_map, ("负债合计",)),
        "shareholder_equity": _pick_statement_item(item_map, ("所有者权益", "股东权益")),
        "operating_cash_flow": _pick_statement_item(item_map, ("经营活动产生的现金流量净额",)),
        "cash_change": _pick_statement_item(item_map, ("现金及现金等价物净增加额",)),
        "items": item_map,
        "source": "sina_financial_report",
    }


def _pick_statement_item(item_map: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    for candidate in candidates:
        for key, value in item_map.items():
            if candidate in key:
                return value
    return None


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
