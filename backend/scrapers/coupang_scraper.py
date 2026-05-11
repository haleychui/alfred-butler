"""
coupang_scraper.py — 酷澎台灣 (www.tw.coupang.com) 商品搜尋 scraper

抓取方式：
  直接 GET /np/search?q=<query>，帶完整瀏覽器 headers 避開 403。
  HTML 解析：ul#productList > li.search-product
  原價：<del class="base-price">
  售價：<strong class="price-value">
  評分：<em class="rating">
  評論數：<span class="rating-total-count">
"""

import asyncio
import gzip
import re
import time
import urllib.parse
import urllib.request
from typing import Optional

import httpx
from bs4 import BeautifulSoup

# ── 常數 ──────────────────────────────────────────────────────────────────────

_BASE_URL = "https://www.tw.coupang.com"
_SEARCH_URL = f"{_BASE_URL}/np/search"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


# ── 解析輔助 ──────────────────────────────────────────────────────────────────

def _int_price(text: str) -> Optional[int]:
    """將 '7,490' / '$6,690' 等格式轉成整數，失敗回傳 None"""
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None


def _parse_li(li) -> Optional[dict]:
    """解析單個 <li class='search-product'> 為標準 dict"""

    # 跳過廣告標籤
    if li.find(class_="search-product__ad-badge"):
        return None

    product_id: str = li.get("data-product-id", "") or li.get("id", "")

    # 商品連結
    link = li.find("a", class_="search-product-link")
    href: str = ""
    if link:
        raw_href = link.get("href", "")
        href = (
            _BASE_URL + raw_href
            if raw_href and not raw_href.startswith("http")
            else raw_href
        )

    # 商品名稱
    name_el = li.find(class_="name")
    name: str = name_el.get_text(strip=True) if name_el else ""
    if not name:
        return None

    # 圖片 URL
    img_el = li.find("img", class_="search-product-wrap-img")
    image_url: str = ""
    if img_el:
        src = img_el.get("src", "")
        if src and not src.startswith("data:"):
            image_url = "https:" + src if src.startswith("//") else src

    # 售價（必要）
    price_el = li.find("strong", class_="price-value")
    if not price_el:
        return None
    price = _int_price(price_el.get_text(strip=True))
    if price is None:
        return None

    # 原價（有折扣才有 <del class="base-price">）
    list_price: Optional[int] = None
    base_el = li.find("del", class_="base-price")
    if base_el:
        lp = _int_price(base_el.get_text(strip=True))
        if lp and lp > price:
            list_price = lp

    # 折扣百分比
    discount_pct: Optional[int] = None
    if list_price and list_price > price:
        discount_pct = round((1 - price / list_price) * 100)

    # 評分（style="width:XX%" 對應 1–5 星；直接取文字 "4.5"）
    rating: Optional[str] = None
    rating_el = li.find("em", class_="rating")
    if rating_el:
        rt = rating_el.get_text(strip=True)
        rating = rt if rt else None

    # 評論數（去掉括號）
    review_count: Optional[str] = None
    review_el = li.find("span", class_="rating-total-count")
    if review_el:
        rc = review_el.get_text(strip=True).strip("()")
        review_count = rc if rc else None

    return {
        "site": "coupang",
        "code": product_id,
        "name": name,
        "price": price,
        "list_price": list_price,
        "discount_pct": discount_pct,
        "image_url": image_url,
        "buy_url": href,
        "rating": rating,
        "review_count": review_count,
    }


def _parse_html(html: str, limit: int) -> list[dict]:
    """從搜尋頁 HTML 解析商品列表"""
    soup = BeautifulSoup(html, "html.parser")
    product_list = soup.find("ul", id="productList")
    if not product_list:
        return []

    results: list[dict] = []
    for li in product_list.find_all("li", class_="search-product"):
        item = _parse_li(li)
        if item:
            results.append(item)
        if len(results) >= limit:
            break

    return results


# ── 主要函數 ──────────────────────────────────────────────────────────────────

async def search_coupang(query: str, limit: int = 6) -> list[dict]:
    """
    酷澎台灣商品搜尋。

    Args:
        query: 搜尋關鍵字（中英文皆可）
        limit: 最多回傳幾筆，預設 6

    Returns:
        list[dict]，每筆格式：
        {
            "site": "coupang",
            "code": "商品ID（數字字串）",
            "name": "商品名稱",
            "price": 6690,
            "list_price": 7490,        # 原價，無折扣時 None
            "discount_pct": 11,        # 折扣%，無折扣時 None
            "image_url": "https://thumbnail.coupangcdn.com/...",
            "buy_url": "https://www.tw.coupang.com/vp/products/...",
            "rating": "5.0",           # 無評分時 None
            "review_count": "565",     # 無評論時 None
        }
    """
    params = {"q": query}
    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=15,
        follow_redirects=True,
    ) as client:
        resp = await client.get(_SEARCH_URL, params=params)
        resp.raise_for_status()
        html = resp.text

    return _parse_html(html, limit)


# ── 快速測試 ──────────────────────────────────────────────────────────────────

async def _run_tests():
    queries = ["AirPods Pro", "電動牙刷"]
    for q in queries:
        t0 = time.perf_counter()
        results = await search_coupang(q, limit=6)
        elapsed = time.perf_counter() - t0
        print(f"\n=== {q} ({len(results)} 筆, {elapsed:.2f}s) ===")
        for p in results:
            disc = f"  省{p['discount_pct']}%" if p.get("discount_pct") else ""
            rating = f"  ⭐{p['rating']}({p['review_count']})" if p.get("rating") else ""
            print(f"  [{p['code']}] {p['name'][:45]}  NT${p['price']:,}{disc}{rating}")
            print(f"         img: {p['image_url'][:70]}")
            print(f"         url: {p['buy_url'][:70]}")


if __name__ == "__main__":
    asyncio.run(_run_tests())
