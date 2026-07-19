from __future__ import annotations

import json

import httpx

from app.connectors.news_sources import cls_telegraph, eastmoney_global_news, eastmoney_stock_news


def test_eastmoney_stock_news_parses_jsonp_and_cleans_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/jsonp"
        payload = {
            "result": {
                "cmsArticleWebOld": {
                    "list": [
                        {
                            "title": "<em>Mock</em> stock news",
                            "content": "<p>Mock summary</p>",
                            "date": "2026-07-15 09:30:00",
                            "mediaName": "Eastmoney",
                            "url": "https://finance.eastmoney.com/a/mock.html",
                        }
                    ]
                }
            }
        }
        return httpx.Response(200, text=f"jQuery_news({json.dumps(payload)})")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records = eastmoney_stock_news("600519.SH", client=client)

    assert len(records) == 1
    record = records[0]
    assert record.module == "news"
    assert record.source == "eastmoney_stock_news"
    assert record.symbol == "600519.SH"
    assert record.record_date == "2026-07-15"
    assert record.payload["title"] == "Mock stock news"
    assert record.payload["summary"] == "Mock summary"
    assert record.payload["url"] == "https://finance.eastmoney.com/a/mock.html"
    assert record.raw_payload_hash


def test_cls_telegraph_uses_signed_v1_query_and_market_wide_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        query = dict(request.url.params)
        assert request.url.path == "/v1/roll/get_roll_list"
        assert query["appName"] == "CailianpressWeb"
        assert "sign" in query
        return httpx.Response(
            200,
            json={
                "errno": 0,
                "data": {
                    "roll_data": [
                        {
                            "id": "cls-1",
                            "ctime": 1784165400,
                            "title": "CLS title",
                            "content": "CLS content",
                            "shareurl": "https://www.cls.cn/detail/cls-1",
                        }
                    ]
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records = cls_telegraph(client=client)

    assert len(records) == 1
    assert records[0].source == "cls_telegraph"
    assert records[0].symbol is None
    assert records[0].payload["title"] == "CLS title"
    assert records[0].payload["media"] == "CLS"
    assert records[0].payload["url"] == "https://www.cls.cn/detail/cls-1"


def test_eastmoney_global_news_parses_fast_news_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        query = dict(request.url.params)
        assert request.url.path == "/comm/web/getFastNewsList"
        assert query["req_trace"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "fastNewsList": [
                        {
                            "code": "global-1",
                            "title": "Global title",
                            "summary": "Global summary",
                            "showTime": "2026-07-15 08:00:00",
                            "mediaName": "Eastmoney",
                            "url": "https://kuaixun.eastmoney.com/a/global-1.html",
                        }
                    ]
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records = eastmoney_global_news(client=client)

    assert len(records) == 1
    assert records[0].source == "eastmoney_global_news"
    assert records[0].symbol is None
    assert records[0].record_date == "2026-07-15"
    assert records[0].payload["summary"] == "Global summary"
    assert records[0].payload["url"] == "https://kuaixun.eastmoney.com/a/global-1.html"
