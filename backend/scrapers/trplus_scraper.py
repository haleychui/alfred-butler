"""
trplus_scraper.py — 特力屋 (trplus.com.tw) 商品搜尋 scraper
方式：JSON API（/search/getSearchProductData），無需 HTML parse
"""

import re
import asyncio
import time
from typing import Optional

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.trplus.com.tw/",
}

_SEARCH_URL = "https://www.trplus.com.tw/search/getSearchProductData"
_BASE_URL = "https://www.trplus.com.tw"


def _parse_price(price_str: Optional[str]) -> Optional[int]:
    """將 '$2,880' 格式轉成 int 2880，None/空字串 → None"""
    if not price_str:
        return None
    cleaned = re.sub(r"[^0-9]", "", price_str)
    return int(cleaned) if cleaned else None


def _best_image(img_list: list) -> str:
    """從 imgList 取第一張，優先選 650x650 尺寸"""
    if not img_list:
        return ""
    for url in img_list:
        if "650x650" in url:
            return url
    return img_list[0]


def _parse_products(raw: list[dict], limit: int) -> list[dict]:
    products = []

    for item in raw[:limit]:
        sku = item.get("sku", "")
        if not sku:
            continue

        name = (item.get("name") or "").strip()
        if not name:
            continue

        # 售價（實際付款金額）
        price = _parse_price(item.get("addToCartPrice") or item.get("salePrice"))
        if not price:
            continue

        # 定價（劃線原價）
        list_price = _parse_price(item.get("listPrice"))
        # 若 listPrice 與 salePrice 相同，視為無折扣
        if list_price == price:
            list_price = price

        # 折扣百分比
        discount_pct: Optional[int] = None
        if list_price and list_price > price:
            discount_pct = round((1 - price / list_price) * 100)

        # 圖片
        image_url = _best_image(item.get("imgList") or [])

        # 購買連結
        link = item.get("link", "")
        buy_url = f"{_BASE_URL}{link}" if link.startswith("/") else link

        products.append({
            "site": "trplus",
            "code": sku,
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": buy_url,
            "rating": None,       # 搜尋頁 API 無評分欄位
            "review_count": None,
        })

    return products


async def search_trplus(query: str, limit: int = 6) -> list[dict]:
    """
    特力屋商品搜尋。
    回傳最多 limit 筆，每筆格式：
        site / code / name / price / list_price / discount_pct /
        image_url / buy_url / rating / review_count
    """
    params = {
        "q": query,
        "page": 0,
        "sort": "relevance",
    }

    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=15,
        follow_redirects=True,
    ) as client:
        r = await client.get(_SEARCH_URL, params=params)
        r.raise_for_status()

    data = r.json()

    # API 回傳結構：{"code": "", "status": ..., "data": {"products": [...], ...}}
    if data.get("code") != "" and data.get("status") not in (None, 200, "200", "OK", ""):
        return []

    products_raw = (data.get("data") or {}).get("products") or []
    if not products_raw:
        return []

    return _parse_products(products_raw, limit)


# ── 測試 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    async def main():
        queries = ["電鑽", "LED燈泡"]
        for q in queries:
            t0 = time.time()
            results = await search_trplus(q, limit=6)
            elapsed = round(time.time() - t0, 2)
            print(f"\n===== 搜尋: {q} ({elapsed}s, {len(results)} 筆) =====")
            for item in results:
                print(json.dumps(item, ensure_ascii=False, indent=2))

    asyncio.run(main())
