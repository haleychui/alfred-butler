"""
yahoo_scraper.py — Yahoo 奇摩購物 (tw.buy.yahoo.com) 商品搜尋 scraper
方式：抓搜尋頁 HTML，解析最大 inline JSON 裡的 search.ecsearch.hits
"""

import re
import json
import asyncio
import time
from typing import Optional

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

_SEARCH_URL = "https://tw.buy.yahoo.com/search/product"


def _extract_hits(html: str) -> list[dict]:
    """從最大 inline script 取出 search.ecsearch.hits"""
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    # 找最大的 inline JSON script（通常 >200KB）
    for s in sorted(scripts, key=len, reverse=True):
        if len(s) < 10000:
            break
        try:
            d = json.loads(s)
        except Exception:
            continue
        hits = (
            d.get("search", {})
            .get("ecsearch", {})
            .get("hits", [])
        )
        if hits:
            return hits
    return []


def _parse_hit(hit: dict) -> Optional[dict]:
    """把單筆 hit 轉成標準格式"""
    name = hit.get("ec_title", "").strip()
    price_raw = hit.get("ec_price")
    if not name or not price_raw:
        return None

    try:
        price = int(float(price_raw))
    except (TypeError, ValueError):
        return None

    list_price_raw = hit.get("ec_listprice")
    list_price: Optional[int] = None
    if list_price_raw:
        try:
            lp = int(float(list_price_raw))
            list_price = lp if lp > price else None
        except (TypeError, ValueError):
            pass

    discount_pct: Optional[int] = None
    if list_price and list_price > price:
        discount_pct = round((1 - price / list_price) * 100)

    # 商品 ID：ec_productid（可能是 "11875206" 或 "c742769"）
    code = str(hit.get("ec_productid", ""))

    # 圖片
    image_url = hit.get("ec_image", "") or ""
    if not image_url:
        multi = hit.get("ec_multi_images", [])
        if multi and isinstance(multi, list) and multi[0]:
            image_url = multi[0].get("url_large", "")

    # 商品頁 URL
    buy_url = hit.get("ec_item_url", "") or ""
    if not buy_url and code:
        if code.startswith("c"):
            buy_url = f"https://tw.buy.yahoo.com/gdsale/gdinfo.asp?gdid={code}"
        else:
            buy_url = f"https://tw.buy.yahoo.com/gdsale/gdinfo.asp?gdid={code}"

    # 評分
    rating_raw = hit.get("ec_global_rating")
    rating: Optional[float] = None
    if rating_raw:
        try:
            rating = float(rating_raw)
        except (TypeError, ValueError):
            pass

    review_count_raw = hit.get("ec_rating_count")
    review_count: Optional[int] = None
    if review_count_raw:
        try:
            review_count = int(review_count_raw)
        except (TypeError, ValueError):
            pass

    return {
        "site": "yahoo",
        "code": code,
        "name": name,
        "price": price,
        "list_price": list_price,
        "discount_pct": discount_pct,
        "image_url": image_url,
        "buy_url": buy_url,
        "rating": rating,
        "review_count": review_count,
    }


async def search_yahoo_shopping(query: str, limit: int = 6) -> list[dict]:
    """
    Yahoo 奇摩購物商品搜尋。

    Args:
        query: 搜尋關鍵字（中英文皆可）
        limit: 最多回傳幾筆，預設 6

    Returns:
        list[dict]，每筆格式：
        {
            "site": "yahoo",
            "code": "商品ID",
            "name": "商品名稱",
            "price": 123,
            "list_price": 150,        # 原價，無折扣時 None
            "discount_pct": 18,       # 折扣百分比，無折扣時 None
            "image_url": "https://...",
            "buy_url": "https://...",
            "rating": 4.8,            # 無評分時 None
            "review_count": 17,       # 無評論數時 None
        }
    """
    params = {"p": query}
    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=15, follow_redirects=True
    ) as client:
        r = await client.get(_SEARCH_URL, params=params)
        r.raise_for_status()

    hits = _extract_hits(r.text)
    products = []
    for hit in hits:
        p = _parse_hit(hit)
        if p:
            products.append(p)
        if len(products) >= limit:
            break

    return products


# ── 快速測試 ──────────────────────────────────────────────────────────────────

async def _run_tests():
    queries = ["AirPods Pro", "電動牙刷"]
    for q in queries:
        t0 = time.perf_counter()
        results = await search_yahoo_shopping(q, limit=6)
        elapsed = time.perf_counter() - t0
        print(f"\n=== {q} ({len(results)} 筆, {elapsed:.2f}s) ===")
        for p in results:
            disc = f"  省{p['discount_pct']}%" if p.get("discount_pct") else ""
            rating = f"  ⭐{p['rating']}({p['review_count']})" if p.get("rating") else ""
            print(f"  [{p['code']}] {p['name'][:40]}  NT${p['price']:,}{disc}{rating}")
            print(f"         img: {p['image_url'][:60]}")
            print(f"         url: {p['buy_url'][:70]}")


if __name__ == "__main__":
    asyncio.run(_run_tests())
