"""
buy123_scraper.py — 生活市集 (buy123.com.tw) 商品搜尋 scraper
方式：解析 Next.js __NEXT_DATA__ JSON（搜尋結果頁內嵌，無需額外 API）
"""

import json
import re
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
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

_SEARCH_URL = "https://www.buy123.com.tw/site/search"

# 從 wordings.display_original_price 取原價，格式如 "$7900"
_PRICE_RE = re.compile(r"[\$,]")


def _parse_price(raw: Optional[str]) -> Optional[int]:
    """將 '$7,900' 或 '7900' 轉成 int，None 或空字串回傳 None。"""
    if not raw:
        return None
    cleaned = _PRICE_RE.sub("", raw).strip()
    return int(cleaned) if cleaned.isdigit() else None


def _extract_products(html: str, limit: int) -> list[dict]:
    """從 HTML 裡的 Next.js __NEXT_DATA__ JSON 解析商品清單。"""
    # 找包含 commodities 的 <script> block（即 __NEXT_DATA__）
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    data: Optional[dict] = None
    for s in scripts:
        if '"commodities"' in s and '"price"' in s:
            try:
                data = json.loads(s)
                break
            except json.JSONDecodeError:
                continue

    if data is None:
        return []

    try:
        commodities: list[dict] = (
            data["props"]["pageProps"]["searchCommodities"]["commodities"]
        )
    except (KeyError, TypeError):
        return []

    products: list[dict] = []
    for c in commodities[:limit]:
        display_id: str = c.get("display_id", "") or c.get("id", "")
        name: str = c.get("name", "").strip()
        if not name or not display_id:
            continue

        # 售價
        price = _parse_price(c.get("price"))
        if not price:
            continue

        # 原價：從 wordings.display_original_price 取，
        # 若無則從 wordings.primary.display_price_original 取（部分商品）
        wordings = c.get("wordings") or {}
        list_price = _parse_price(wordings.get("display_original_price"))

        # 若 list_price 小於等於 price（資料問題），當作無折扣
        if list_price and list_price <= price:
            list_price = None

        # 折扣百分比
        discount_pct: Optional[int] = None
        if list_price and list_price > price:
            discount_pct = round((1 - price / list_price) * 100)

        # 圖片：優先用無背景版，fallback 縮圖
        images = c.get("images") or {}
        image_url: str = images.get("bgless") or images.get("small") or ""

        # 評分
        reviews = c.get("reviews_info") or {}
        avg_str = reviews.get("avg", "0") or "0"
        count_str = reviews.get("count", "0") or "0"
        try:
            rating: Optional[float] = float(avg_str) if float(avg_str) > 0 else None
            review_count: Optional[int] = int(count_str) if int(count_str) > 0 else None
        except (ValueError, TypeError):
            rating = None
            review_count = None

        buy_url = f"https://www.buy123.com.tw/site/sku/{display_id}"

        products.append({
            "site": "buy123",
            "code": display_id,
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": buy_url,
            "rating": rating,
            "review_count": review_count,
        })

    return products


async def search_buy123(query: str, limit: int = 6) -> list[dict]:
    """
    生活市集商品搜尋。
    方式：GET /site/search?q=<query> 解析頁面內嵌 Next.js JSON。
    回傳最多 limit 筆，每筆格式：
        site / code / name / price / list_price / discount_pct /
        image_url / buy_url / rating / review_count
    """
    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=15,
        follow_redirects=True,
    ) as client:
        r = await client.get(_SEARCH_URL, params={"q": query})
        r.raise_for_status()

    # 若頁面被攔截（內容過短）
    if len(r.text) < 10_000:
        return []

    return _extract_products(r.text, limit)


# ── 測試 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    async def main():
        queries = ["AirPods Pro", "電動牙刷"]
        for q in queries:
            t0 = time.time()
            results = await search_buy123(q, limit=6)
            elapsed = round(time.time() - t0, 2)
            print(f"\n===== 搜尋: {q} ({elapsed}s, {len(results)} 筆) =====")
            for item in results:
                print(json.dumps(item, ensure_ascii=False, indent=2))

    asyncio.run(main())
