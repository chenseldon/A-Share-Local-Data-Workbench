from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx


class MarketDataError(RuntimeError):
    pass


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


@dataclass(frozen=True)
class MarketSnapshot:
    security: ResolvedSecurity
    quote: MarketQuote | None
    bars: tuple[MarketBar, ...]


def normalize_symbol(raw_symbol: str) -> str:
    value = raw_symbol.strip().upper()
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", value):
        return value
    if not re.fullmatch(r"\d{6}", value):
        raise ValueError(f"Unsupported A-share symbol: {raw_symbol}")

    if value.startswith(("600", "601", "603", "605", "688", "689", "510", "511", "512", "513", "515", "516", "517", "518", "588")):
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


def exchange_name(symbol: str) -> str:
    exchange = normalize_symbol(symbol).split(".")[1]
    return {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}[exchange]


def infer_asset_type(symbol: str) -> str:
    code = normalize_symbol(symbol).split(".")[0]
    if code.startswith(("510", "511", "512", "513", "515", "516", "517", "518", "588", "159")):
        return "etf"
    return "stock"


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


def fetch_public_market_snapshot(symbol: str) -> MarketSnapshot:
    security, quote = fetch_tencent_quote(symbol)
    try:
        bars = fetch_baidu_daily_bars(symbol)
    except MarketDataError:
        try:
            bars = fetch_tencent_daily_bars(symbol)
        except MarketDataError:
            bars = ()
    return MarketSnapshot(security=security, quote=quote, bars=bars)
