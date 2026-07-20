from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from .astock_sources import AStockSourceError, ModuleRecord, eastmoney_get, payload_hash, six_digit_code
from .public_market import normalize_symbol

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def eastmoney_stock_news(symbol: str, page_size: int = 20, client: httpx.Client | None = None) -> list[ModuleRecord]:
    normalized = normalize_symbol(symbol)
    code = six_digit_code(normalized)
    fetched_at = datetime.now(UTC)
    callback = "jQuery_news"
    inner_params = json.dumps(
        {
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": page_size,
                    "preTag": "",
                    "postTag": "",
                }
            },
        },
        separators=(",", ":"),
    )
    response = eastmoney_get(
        "https://search-api-web.eastmoney.com/search/jsonp",
        params={"cb": callback, "param": inner_params},
        headers={"Referer": "https://so.eastmoney.com/"},
        timeout=15,
        client=client,
    )
    payload = _parse_jsonp(response.text)
    articles = (payload.get("result") or {}).get("cmsArticleWebOld") or []
    if isinstance(articles, dict):
        articles = articles.get("list") or []
    records: list[ModuleRecord] = []
    for index, article in enumerate(articles):
        if not isinstance(article, dict):
            continue
        news_time = _clean_text(article.get("date")) or fetched_at.isoformat()
        item = {
            "symbol": normalized,
            "title": _clean_text(article.get("title")),
            "summary": _clean_text(article.get("content"))[:200],
            "time": news_time,
            "media": article.get("mediaName"),
            "url": article.get("url"),
            "source": "eastmoney_stock_news",
        }
        records.append(
            ModuleRecord(
                module="news",
                source="eastmoney_stock_news",
                data_key=f"{code}-{payload_hash(article)[:16]}-{index}",
                symbol=normalized,
                record_date=_to_record_date(news_time, fetched_at),
                payload=item,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(article),
            )
        )
    return records


def cls_telegraph(page_size: int = 50, client: httpx.Client | None = None) -> list[ModuleRecord]:
    fetched_at = datetime.now(UTC)
    params = {
        "appName": "CailianpressWeb",
        "os": "web",
        "sv": "7.7.5",
        "last_time": "",
        "refresh_type": "1",
        "rn": str(page_size),
    }
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    sign = hashlib.md5(hashlib.sha1(query.encode()).hexdigest().encode()).hexdigest()
    owns_client = client is None
    http_client = client or httpx.Client(timeout=10, headers={"User-Agent": UA})
    try:
        response = http_client.get(
            f"https://www.cls.cn/v1/roll/get_roll_list?{query}&sign={sign}",
            headers={"Referer": "https://www.cls.cn/"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AStockSourceError(f"CLS telegraph request failed: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()
    if payload.get("errno") not in (None, 0):
        raise AStockSourceError(f"CLS telegraph returned errno={payload.get('errno')}: {payload.get('msg')}")
    items = (payload.get("data") or {}).get("roll_data") or []
    records: list[ModuleRecord] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        article_id = item.get("id")
        timestamp = item.get("ctime")
        news_time = datetime.fromtimestamp(timestamp, tz=UTC).isoformat() if isinstance(timestamp, (int, float)) else fetched_at.isoformat()
        title = item.get("title") or item.get("brief") or ""
        row = {
            "symbol": None,
            "title": _clean_text(title),
            "summary": _clean_text(item.get("content") or item.get("brief"))[:300],
            "time": news_time,
            "media": "CLS",
            "url": f"https://www.cls.cn/detail/{article_id}" if article_id else item.get("url"),
            "source": "cls_telegraph",
        }
        records.append(
            ModuleRecord(
                module="news",
                source="cls_telegraph",
                data_key=str(item.get("id") or item.get("ctime") or f"cls-{index}-{payload_hash(item)[:12]}"),
                symbol=None,
                record_date=_to_record_date(news_time, fetched_at),
                payload=row,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(item),
            )
        )
    return records


def eastmoney_global_news(page_size: int = 50, client: httpx.Client | None = None) -> list[ModuleRecord]:
    fetched_at = datetime.now(UTC)
    response = eastmoney_get(
        "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
        params={
            "client": "web",
            "biz": "web_724",
            "fastColumn": "102",
            "sortEnd": "",
            "pageSize": str(page_size),
            "req_trace": str(uuid.uuid4()),
        },
        headers={"Referer": "https://kuaixun.eastmoney.com/"},
        timeout=10,
        client=client,
    )
    payload = response.json()
    items = (payload.get("data") or {}).get("fastNewsList") or []
    records: list[ModuleRecord] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        news_time = item.get("showTime") or item.get("showtime") or fetched_at.isoformat()
        article_id = item.get("code") or item.get("id")
        row = {
            "symbol": None,
            "title": _clean_text(item.get("title")),
            "summary": _clean_text(item.get("summary") or item.get("digest"))[:300],
            "time": news_time,
            "media": item.get("mediaName") or "Eastmoney",
            "url": item.get("url") or item.get("artUrl") or (f"https://kuaixun.eastmoney.com/detail.html?id={article_id}" if article_id else None),
            "source": "eastmoney_global_news",
        }
        records.append(
            ModuleRecord(
                module="news",
                source="eastmoney_global_news",
                data_key=str(item.get("code") or item.get("id") or f"em-global-{index}-{payload_hash(item)[:12]}"),
                symbol=None,
                record_date=_to_record_date(news_time, fetched_at),
                payload=row,
                fetched_at=fetched_at,
                raw_payload_hash=payload_hash(item),
            )
        )
    return records


def _parse_jsonp(text: str) -> dict[str, Any]:
    try:
        start = text.index("(") + 1
        end = text.rindex(")")
        payload = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        raise AStockSourceError(f"Eastmoney stock news JSONP parse failed: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def _clean_text(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def _to_record_date(value: Any, fallback: datetime) -> str:
    text = str(value or "")
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if text:
        return text[:10]
    return fallback.date().isoformat()
