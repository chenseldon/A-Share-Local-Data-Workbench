from __future__ import annotations

import hashlib
import json
import math
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx


class MarketDataError(RuntimeError):
    pass


CHINA_TZ = ZoneInfo("Asia/Shanghai")


FREE_STOCKDB_PRESET_CODES: tuple[str, ...] = (
    "000001",
    "000002",
    "000063",
    "000100",
    "000333",
    "000651",
    "000725",
    "000858",
    "002027",
    "002142",
    "002230",
    "002415",
    "002466",
    "002594",
    "002714",
    "002812",
    "300014",
    "300015",
    "300033",
    "300059",
    "300122",
    "300274",
    "300308",
    "300347",
    "300750",
    "300760",
    "300896",
    "510050",
    "510300",
    "510500",
    "512100",
    "512480",
    "512880",
    "513050",
    "588000",
    "588080",
    "600000",
    "600002",
    "600009",
    "600010",
    "600016",
    "600028",
    "600030",
    "600031",
    "600036",
    "600048",
    "600050",
    "600104",
    "600111",
    "600150",
    "600276",
    "600309",
    "600438",
    "600519",
    "600547",
    "600570",
    "600585",
    "600690",
    "600703",
    "600745",
    "600809",
    "600887",
    "601012",
    "601088",
    "601166",
    "601318",
    "601328",
    "601390",
    "601398",
    "601601",
    "601628",
    "601668",
    "601688",
    "601728",
    "601788",
    "601857",
    "601888",
    "601899",
    "601939",
    "601988",
    "601989",
    "603019",
    "603259",
    "603288",
    "603501",
    "603799",
    "603986",
    "605499",
    "688012",
    "688036",
    "688111",
    "688126",
    "688169",
    "688256",
    "688363",
    "688599",
    "920001",
)

FREE_STOCKDB_UNIVERSE_PREFIXES: tuple[str, ...] = (
    "000",
    "001",
    "002",
    "003",
    "300",
    "301",
    "600",
    "601",
    "603",
    "605",
    "688",
    "689",
    "159",
    "160",
    "161",
    "162",
    "163",
    "164",
    "165",
    "166",
    "167",
    "168",
    "169",
    "501",
    "502",
    "506",
    "508",
    "510",
    "511",
    "512",
    "513",
    "515",
    "516",
    "517",
    "518",
    "520",
    "526",
    "530",
    "551",
    "560",
    "561",
    "562",
    "563",
    "588",
    "589",
    "430",
    "830",
    "831",
    "832",
    "833",
    "834",
    "835",
    "836",
    "837",
    "838",
    "839",
    "870",
    "871",
    "872",
    "873",
    "920",
)

FREE_STOCKDB_EXPECTED_SOURCE_COUNT = 7400
FREE_STOCKDB_INDICATOR_CONFIG: dict[str, dict[str, Any]] = {
    "ma": {"name": "ma", "n": "5,10,20"},
    "ema": {"name": "ema", "n": "5,10,20"},
    "sma": {"name": "sma", "n": "5,10,20"},
    "wma": {"name": "wma", "n": "5,10,20"},
    "dma": {"name": "dma", "n": "10"},
    "std": {"name": "std", "n": "20"},
    "sum": {"name": "sum", "n": "20"},
    "hhv": {"name": "hhv", "n": "20"},
    "llv": {"name": "llv", "n": "20"},
    "ref": {"name": "ref", "n": "1"},
    "macd": {"name": "macd", "n": "12,26,9"},
    "kdj": {"name": "kdj", "n": None},
    "rsi": {"name": "rsi", "n": "6,12,24"},
    "wr": {"name": "wr", "n": None},
    "bias": {"name": "bias", "n": None},
    "boll": {"name": "boll", "n": "20"},
    "psy": {"name": "psy", "n": None},
    "cci": {"name": "cci", "n": None},
    "atr": {"name": "atr", "n": None},
    "bbi": {"name": "bbi", "n": None},
    "dmi": {"name": "dmi", "n": None},
    "taq": {"name": "taq", "n": None},
    "ktn": {"name": "ktn", "n": None},
    "trix": {"name": "trix", "n": None},
    "vr": {"name": "vr", "n": None},
    "cr": {"name": "cr", "n": None},
    "emv": {"name": "emv", "n": None},
    "dpo": {"name": "dpo", "n": None},
    "brar": {"name": "brar", "n": None},
    "dfma": {"name": "dfma", "n": None},
    "mtm": {"name": "mtm", "n": None},
    "mass": {"name": "mass", "n": None},
    "roc": {"name": "roc", "n": None},
    "expma": {"name": "expma", "n": None},
    "obv": {"name": "obv", "n": None},
    "mfi": {"name": "mfi", "n": None},
    "asi": {"name": "asi", "n": None},
    "xsii": {"name": "xsii", "n": None},
}


@dataclass(frozen=True)
class ResolvedSecurity:
    symbol: str
    name: str
    exchange: str
    asset_type: str
    sector: str | None
    source: str
    fetched_at: datetime
    raw_payload_hash: str


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price_time: datetime | None
    last_price: float | None
    previous_close: float | None
    open: float | None
    high: float | None
    low: float | None
    volume: float | None
    amount: float | None
    bid1: float | None
    ask1: float | None
    source: str
    fetched_at: datetime
    raw_payload_hash: str
    change_amt: float | None = None
    change_pct: float | None = None
    turnover_pct: float | None = None
    pe_ttm: float | None = None
    amplitude_pct: float | None = None
    total_market_cap: float | None = None
    float_market_cap: float | None = None
    pb: float | None = None
    limit_up: float | None = None
    limit_down: float | None = None
    volume_ratio: float | None = None
    pe_static: float | None = None


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    trade_date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    amount: float | None
    adjustment: str
    source: str
    fetched_at: datetime
    raw_payload_hash: str
    chart_time: int | None = None


@dataclass(frozen=True)
class MarketSnapshot:
    security: ResolvedSecurity
    quote: MarketQuote | None
    bars: tuple[MarketBar, ...]


@dataclass(frozen=True)
class BoardMapping:
    symbol: str
    concepts: list[str]
    sw_l1: list[str]
    sw_l2: list[str]
    sw_l3: list[str]
    source: str
    fetched_at: datetime


def normalize_symbol(raw_symbol: str) -> str:
    value = raw_symbol.strip().upper()
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", value):
        return value
    if not re.fullmatch(r"\d{6}", value):
        raise ValueError(f"Unsupported A-share symbol: {raw_symbol}")

    if value.startswith(("5", "600", "601", "603", "605", "688", "689")):
        return f"{value}.SH"
    if value.startswith(("000", "001", "002", "003", "159", "160", "161", "162", "163", "164", "165", "166", "167", "168", "169", "300", "301")):
        return f"{value}.SZ"
    if value.startswith(("430", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "889", "920")):
        return f"{value}.BJ"
    raise ValueError(f"Cannot infer exchange for A-share symbol: {raw_symbol}")


def tencent_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    code, exchange = normalized.split(".")
    return f"{exchange.lower()}{code}"


def stockdb_code(symbol: str) -> str:
    return normalize_symbol(symbol).split(".")[0]


def exchange_name(symbol: str) -> str:
    exchange = normalize_symbol(symbol).split(".")[1]
    return {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}[exchange]


def infer_asset_type(symbol: str) -> str:
    code = normalize_symbol(symbol).split(".")[0]
    if code.startswith(("5", "159", "160", "161", "162", "163", "164", "165", "166", "167", "168", "169")):
        return "etf"
    return "stock"


def fetch_free_stockdb_security(symbol: str) -> ResolvedSecurity:
    normalized = normalize_symbol(symbol)
    code = stockdb_code(normalized)
    fetched_at = datetime.now(UTC)
    fields = "date,code,name,close"
    try:
        from stock_sdk import StockDBClient
    except ImportError as exc:
        raise MarketDataError("free-stockdb Python SDK is not installed in this Python environment.") from exc
    try:
        client = StockDBClient(host="127.0.0.1", port=7899)
        rows = client.get_data(
            code=code,
            frequency="1d",
            fields=fields,
            fq="qfq",
            as_df=False,
            limit=1,
            desc=True,
        )
    except Exception as exc:
        raise MarketDataError(f"free-stockdb security lookup failed: {exc}") from exc
    if not rows:
        raise MarketDataError(f"free-stockdb has no daily K-line row for {normalized}")
    row = rows[0]
    name = str(row[2]) if isinstance(row, (list, tuple)) and len(row) > 2 and row[2] else normalized
    raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str)
    return ResolvedSecurity(
        symbol=normalized,
        name=name,
        exchange=exchange_name(normalized),
        asset_type=infer_asset_type(normalized),
        sector=None,
        source="free_stockdb_security",
        fetched_at=fetched_at,
        raw_payload_hash=_hash_payload(raw),
    )


def _stockdb_security_from_row(row: Any, fetched_at: datetime, source: str) -> ResolvedSecurity | None:
    if isinstance(row, dict):
        raw_code = row.get("code")
        name = row.get("name")
    elif isinstance(row, (list, tuple)) and len(row) > 2:
        raw_code = row[1]
        name = row[2]
    else:
        return None
    code = str(raw_code).strip().upper().split(".")[0].zfill(6)
    try:
        normalized = normalize_symbol(code)
    except ValueError:
        return None
    raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str)
    return ResolvedSecurity(
        symbol=normalized,
        name=str(name) if name else normalized,
        exchange=exchange_name(normalized),
        asset_type=infer_asset_type(normalized),
        sector=None,
        source=source,
        fetched_at=fetched_at,
        raw_payload_hash=_hash_payload(raw),
    )


def fetch_free_stockdb_security_batch(codes: tuple[str, ...] = FREE_STOCKDB_PRESET_CODES) -> tuple[ResolvedSecurity, ...]:
    if not _tcp_port_open("127.0.0.1", 7899, timeout=0.2):
        return ()
    fetched_at = datetime.now(UTC)
    fields = "date,code,name,close"
    try:
        from stock_sdk import StockDBClient
    except ImportError as exc:
        raise MarketDataError("free-stockdb Python SDK is not installed in this Python environment.") from exc
    try:
        client = StockDBClient(host="127.0.0.1", port=7899)
        rows = client.get_data(
            code=list(codes),
            frequency="1d",
            fields=fields,
            fq="qfq",
            as_df=False,
            limit=1,
            desc=True,
        )
    except Exception as exc:
        raise MarketDataError(f"free-stockdb security preload failed: {exc}") from exc

    securities: list[ResolvedSecurity] = []
    row_iterable: list[Any]
    if isinstance(rows, dict):
        row_iterable = [records[0] for records in rows.values() if records]
    else:
        row_iterable = list(rows or [])
    for row in row_iterable:
        security = _stockdb_security_from_row(row, fetched_at, "free_stockdb_security_preload")
        if security:
            securities.append(security)
    return tuple(securities)


def fetch_free_stockdb_security_universe(chunk_size: int = 500) -> tuple[ResolvedSecurity, ...]:
    if not _tcp_port_open("127.0.0.1", 7899, timeout=0.2):
        raise MarketDataError("free-stockdb service is not reachable at 127.0.0.1:7899.")
    try:
        from stock_sdk import StockDBClient
    except ImportError as exc:
        raise MarketDataError("free-stockdb Python SDK is not installed in this Python environment.") from exc

    client = StockDBClient(host="127.0.0.1", port=7899)
    fetched_at = datetime.now(UTC)
    codes = [f"{prefix}{number:03d}" for prefix in FREE_STOCKDB_UNIVERSE_PREFIXES for number in range(1000)]
    securities: dict[str, ResolvedSecurity] = {}
    fields = "date,code,name,close"
    for offset in range(0, len(codes), chunk_size):
        batch = codes[offset : offset + chunk_size]
        try:
            rows_by_code = client.get_data(
                code=batch,
                frequency="1d",
                fields=fields,
                fq=None,
                as_df=False,
                limit=len(batch),
                desc=True,
            )
        except Exception as exc:
            raise MarketDataError(f"free-stockdb universe scan failed near {batch[0]}: {exc}") from exc
        if not isinstance(rows_by_code, dict):
            continue
        for records in rows_by_code.values():
            if not records:
                continue
            security = _stockdb_security_from_row(records[0], fetched_at, "free_stockdb_universe")
            if security:
                securities[security.symbol] = security
    return tuple(sorted(securities.values(), key=lambda item: item.symbol))


def fetch_free_stockdb_board_mapping(symbol: str) -> BoardMapping:
    normalized = normalize_symbol(symbol)
    code = stockdb_code(normalized)
    if not _tcp_port_open("127.0.0.1", 7899, timeout=0.2):
        raise MarketDataError("free-stockdb service is not reachable at 127.0.0.1:7899.")
    try:
        from zhibiao import bk
    except ImportError as exc:
        raise MarketDataError("free-stockdb zhibiao SDK is not installed in this Python environment.") from exc
    except Exception as exc:
        raise MarketDataError(f"free-stockdb board mapping SDK initialization failed: {exc}") from exc

    try:
        concepts = _string_list(bk.get(code, 0, "name"))
        sw_l1 = _string_list(bk.get(code, 1, "name"))
        sw_l2 = _string_list(bk.get(code, 2, "name"))
        sw_l3 = _string_list(bk.get(code, 3, "name"))
    except Exception as exc:
        raise MarketDataError(f"free-stockdb board mapping request failed: {exc}") from exc
    return BoardMapping(
        symbol=normalized,
        concepts=concepts,
        sw_l1=sw_l1,
        sw_l2=sw_l2,
        sw_l3=sw_l3,
        source="free_stockdb_bk",
        fetched_at=datetime.now(UTC),
    )


def fetch_free_stockdb_indicators(
    symbol: str,
    indicators: tuple[str, ...],
    *,
    start: str | None = None,
    end: str | None = None,
    frequency: str = "1d",
    fq: str | None = "qfq",
) -> dict[str, dict[str, Any]]:
    normalized = normalize_symbol(symbol)
    code = stockdb_code(normalized)
    selected = _normalize_indicator_names(indicators)
    if not selected:
        return {}
    if not _tcp_port_open("127.0.0.1", 7899, timeout=0.2):
        raise MarketDataError("free-stockdb service is not reachable at 127.0.0.1:7899.")
    try:
        from zhibiao import zb
    except ImportError as exc:
        raise MarketDataError("free-stockdb zhibiao SDK is not installed in this Python environment.") from exc

    names = [FREE_STOCKDB_INDICATOR_CONFIG[item]["name"] for item in selected]
    params = [FREE_STOCKDB_INDICATOR_CONFIG[item]["n"] for item in selected]
    try:
        rows = zb.get(
            ",".join(names),
            code,
            start=start,
            end=end,
            frequency=frequency,
            fq=fq,
            n=params if len(params) > 1 else params[0],
            cross=False,
        )
    except Exception as exc:
        raise MarketDataError(f"free-stockdb indicator request failed: {exc}") from exc

    by_date: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date = _format_stockdb_date(row.get("date"))
        if not date:
            continue
        by_date[date] = {
            key: _clean_json_value(value)
            for key, value in row.items()
            if key != "date"
        }
    return by_date


def _normalize_indicator_names(indicators: tuple[str, ...]) -> list[str]:
    selected: list[str] = []
    for item in indicators:
        key = item.strip().lower()
        if not key or key == "volume":
            continue
        if key not in FREE_STOCKDB_INDICATOR_CONFIG:
            raise ValueError(f"Unsupported free-stockdb indicator: {item}")
        if key not in selected:
            selected.append(key)
    return selected


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _clean_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    return value


def _tcp_port_open(host: str, port: int, *, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _hash_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def _to_float(value: str | int | float | None) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_tencent_time(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def fetch_tencent_quote(symbol: str, client: httpx.Client | None = None) -> tuple[ResolvedSecurity, MarketQuote]:
    normalized = normalize_symbol(symbol)
    code = tencent_code(normalized)
    fetched_at = datetime.now(UTC)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=8.0, headers={"User-Agent": "Mozilla/5.0"})
    try:
        response = http_client.get("https://qt.gtimg.cn/q=" + code)
        response.raise_for_status()
        text = response.text.strip()
    except httpx.HTTPError as exc:
        raise MarketDataError(f"Tencent quote request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    match = re.search(r'="(?P<body>.*)";?$', text)
    body = match.group("body") if match else text
    parts = body.split("~")
    if len(parts) < 4 or not parts[1]:
        raise MarketDataError(f"Tencent quote response is not usable for {normalized}")

    payload_hash = _hash_payload(text)
    security = ResolvedSecurity(
        symbol=normalized,
        name=parts[1],
        exchange=exchange_name(normalized),
        asset_type=infer_asset_type(normalized),
        sector=None,
        source="tencent_quote",
        fetched_at=fetched_at,
        raw_payload_hash=payload_hash,
    )
    quote = MarketQuote(
        symbol=normalized,
        price_time=_parse_tencent_time(parts[30] if len(parts) > 30 else None),
        last_price=_to_float(parts[3] if len(parts) > 3 else None),
        previous_close=_to_float(parts[4] if len(parts) > 4 else None),
        open=_to_float(parts[5] if len(parts) > 5 else None),
        high=_to_float(parts[33] if len(parts) > 33 else None),
        low=_to_float(parts[34] if len(parts) > 34 else None),
        volume=_to_float(parts[6] if len(parts) > 6 else None),
        amount=_to_float(parts[37] if len(parts) > 37 else None),
        bid1=_to_float(parts[9] if len(parts) > 9 else None),
        ask1=_to_float(parts[19] if len(parts) > 19 else None),
        change_amt=_to_float(parts[31] if len(parts) > 31 else None),
        change_pct=_to_float(parts[32] if len(parts) > 32 else None),
        turnover_pct=_to_float(parts[38] if len(parts) > 38 else None),
        pe_ttm=_to_float(parts[39] if len(parts) > 39 else None),
        amplitude_pct=_to_float(parts[43] if len(parts) > 43 else None),
        total_market_cap=_to_float(parts[44] if len(parts) > 44 else None),
        float_market_cap=_to_float(parts[45] if len(parts) > 45 else None),
        pb=_to_float(parts[46] if len(parts) > 46 else None),
        limit_up=_to_float(parts[47] if len(parts) > 47 else None),
        limit_down=_to_float(parts[48] if len(parts) > 48 else None),
        volume_ratio=_to_float(parts[49] if len(parts) > 49 else None),
        pe_static=_to_float(parts[52] if len(parts) > 52 else None),
        source="tencent_quote",
        fetched_at=fetched_at,
        raw_payload_hash=payload_hash,
    )
    return security, quote


def fetch_tencent_daily_bars(symbol: str, limit: int = 120, client: httpx.Client | None = None) -> tuple[MarketBar, ...]:
    normalized = normalize_symbol(symbol)
    code = tencent_code(normalized)
    fetched_at = datetime.now(UTC)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=8.0, headers={"User-Agent": "Mozilla/5.0"})
    try:
        response = http_client.get(
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            params={"param": f"{code},day,,,{limit}"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise MarketDataError(f"Tencent K-line request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    node: dict[str, Any] = payload.get("data", {}).get(code, {})
    raw_rows = node.get("day") or node.get("qfqday") or []
    if not isinstance(raw_rows, list):
        raise MarketDataError(f"Tencent K-line response is not usable for {normalized}")

    bars: list[MarketBar] = []
    for row in raw_rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        bars.append(
            MarketBar(
                symbol=normalized,
                trade_date=str(row[0]),
                open=_to_float(row[1]),
                high=_to_float(row[3]),
                low=_to_float(row[4]),
                close=_to_float(row[2]),
                volume=_to_float(row[5]),
                amount=_to_float(row[8] if len(row) > 8 else None),
                adjustment="none",
                source="tencent_kline",
                fetched_at=fetched_at,
                raw_payload_hash=_hash_payload(raw),
            )
        )
    return tuple(bars)


def fetch_baidu_daily_bars(symbol: str, limit: int = 160, client: httpx.Client | None = None) -> tuple[MarketBar, ...]:
    normalized = normalize_symbol(symbol)
    fetched_at = datetime.now(UTC)
    owns_client = client is None
    http_client = client or httpx.Client(
        timeout=10.0,
        headers={
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        response = http_client.get(
            "https://finance.pae.baidu.com/selfselect/getstockquotation",
            params={
                "group": "quotation_kline_ab",
                "finClientType": "pc",
                "code": normalized,
                "ktype": "1",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise MarketDataError(f"Baidu K-line request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    result = payload.get("Result") or payload.get("result") or {}
    market_data = result.get("newMarketData") or result.get("marketData") or {}
    keys = market_data.get("keys") or result.get("keys") or []
    rows = market_data.get("marketData") or market_data.get("data") or result.get("marketData") or []
    if not isinstance(keys, list) or not isinstance(rows, list):
        raise MarketDataError(f"Baidu K-line response is not usable for {normalized}")

    bars: list[MarketBar] = []
    for raw_row in rows[-limit:]:
        values = str(raw_row).split(";")
        row = dict(zip((str(key).lower() for key in keys), values, strict=False))
        trade_date = row.get("date") or row.get("time")
        if not trade_date:
            continue
        raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        bars.append(
            MarketBar(
                symbol=normalized,
                trade_date=str(trade_date)[:10],
                open=_to_float(row.get("open")),
                high=_to_float(row.get("high")),
                low=_to_float(row.get("low")),
                close=_to_float(row.get("close")),
                volume=_to_float(row.get("volume")),
                amount=_to_float(row.get("amount")),
                adjustment="none",
                source="baidu_kline_with_ma",
                fetched_at=fetched_at,
                raw_payload_hash=_hash_payload(raw),
            )
        )
    if not bars:
        raise MarketDataError(f"Baidu K-line returned no rows for {normalized}")
    return tuple(bars)


def fetch_free_stockdb_bars(
    symbol: str,
    *,
    limit: int = 260,
    start: str | None = None,
    end: str | None = None,
    frequency: str = "1d",
    fq: str | None = "qfq",
    host: str = "127.0.0.1",
    port: int = 7899,
) -> tuple[MarketBar, ...]:
    if frequency not in {"1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M"}:
        raise MarketDataError(f"Unsupported free-stockdb K-line frequency: {frequency}")
    normalized = normalize_symbol(symbol)
    code = stockdb_code(normalized)
    now = datetime.now(UTC)
    end_date = end or now.strftime("%Y%m%d%H%M%S" if frequency.endswith("m") else "%Y%m%d")
    start_date = start or (now - _default_frequency_window(frequency)).strftime("%Y%m%d%H%M%S" if frequency.endswith("m") else "%Y%m%d")
    fields = "date,code,name,open,high,low,close,volume,amount,pct_chg"
    try:
        from stock_sdk import StockDBClient
    except ImportError as exc:
        raise MarketDataError("free-stockdb Python SDK is not installed in this Python environment.") from exc

    fetched_at = datetime.now(UTC)
    try:
        client = StockDBClient(host=host, port=port)
        rows = client.get_data(
            code=code,
            start=start_date,
            end=end_date,
            frequency=frequency,
            fields=fields,
            fq=fq,
            as_df=False,
            limit=limit,
            desc=True,
        )
    except Exception as exc:
        raise MarketDataError(f"free-stockdb K-line request failed: {exc}") from exc

    bars = _stockdb_rows_to_market_bars(normalized, rows, fetched_at=fetched_at, adjustment=fq or "none")
    if not bars:
        raise MarketDataError(f"free-stockdb returned no K-line rows for {normalized}")
    return bars


def fetch_free_stockdb_daily_bars(
    symbol: str,
    *,
    limit: int = 260,
    start: str | None = None,
    end: str | None = None,
    fq: str | None = "qfq",
    host: str = "127.0.0.1",
    port: int = 7899,
) -> tuple[MarketBar, ...]:
    return fetch_free_stockdb_bars(
        symbol,
        limit=limit,
        start=start,
        end=end,
        frequency="1d",
        fq=fq,
        host=host,
        port=port,
    )


def _default_frequency_window(frequency: str) -> timedelta:
    if frequency == "1m":
        return timedelta(days=20)
    if frequency == "5m":
        return timedelta(days=100)
    if frequency == "15m":
        return timedelta(days=240)
    if frequency == "30m":
        return timedelta(days=430)
    if frequency == "60m":
        return timedelta(days=850)
    if frequency == "1w":
        return timedelta(days=365 * 28)
    if frequency == "1M":
        return timedelta(days=365 * 28)
    return timedelta(days=365 * 12)


def _stockdb_rows_to_market_bars(
    symbol: str,
    rows: Any,
    *,
    fetched_at: datetime,
    adjustment: str,
) -> tuple[MarketBar, ...]:
    bars: list[MarketBar] = []
    for row in rows or []:
        if isinstance(row, dict):
            raw_date = row.get("date")
            open_value = row.get("open")
            high_value = row.get("high")
            low_value = row.get("low")
            close_value = row.get("close")
            volume_value = row.get("volume")
            amount_value = row.get("amount")
        else:
            if not isinstance(row, (list, tuple)) or len(row) < 9:
                continue
            raw_date, _, _, open_value, high_value, low_value, close_value, volume_value, amount_value = row[:9]
        trade_date = _format_stockdb_date(raw_date)
        if not trade_date:
            continue
        chart_time = _stockdb_chart_time(raw_date)
        raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str)
        bars.append(
            MarketBar(
                symbol=symbol,
                trade_date=trade_date,
                chart_time=chart_time,
                open=_to_float(open_value),
                high=_to_float(high_value),
                low=_to_float(low_value),
                close=_to_float(close_value),
                volume=_to_float(volume_value),
                amount=_to_float(amount_value),
                adjustment=adjustment,
                source="free_stockdb_kline",
                fetched_at=fetched_at,
                raw_payload_hash=_hash_payload(raw),
            )
        )
    return tuple(sorted(bars, key=lambda bar: bar.chart_time or 0))


def _format_stockdb_date(value: Any) -> str | None:
    text = str(value).strip()
    if re.fullmatch(r"\d{14}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}"
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text):
        return text
    return None


def _stockdb_chart_time(value: Any) -> int | None:
    text = str(value).strip()
    try:
        if re.fullmatch(r"\d{14}", text):
            parsed = datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=CHINA_TZ)
            return int(parsed.timestamp())
        if re.fullmatch(r"\d{8}", text):
            parsed = datetime.strptime(text, "%Y%m%d").replace(tzinfo=CHINA_TZ)
            return int(parsed.timestamp())
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            parsed = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=CHINA_TZ)
            return int(parsed.timestamp())
        if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text):
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHINA_TZ)
            return int(parsed.timestamp())
    except ValueError:
        return None
    return None


def fetch_public_market_snapshot(symbol: str) -> MarketSnapshot:
    try:
        security = fetch_free_stockdb_security(symbol)
    except MarketDataError:
        security, _ = fetch_tencent_quote(symbol)
    try:
        _, quote = fetch_tencent_quote(symbol)
    except MarketDataError:
        quote = None
    try:
        bars = fetch_free_stockdb_daily_bars(symbol)
    except MarketDataError:
        bars = ()
    return MarketSnapshot(security=security, quote=quote, bars=bars)
