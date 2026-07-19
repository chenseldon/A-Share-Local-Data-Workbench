from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
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


def _to_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
