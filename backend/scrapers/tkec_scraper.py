"""
tkec_scraper.py — 燦坤線上購物 (www.tk3c.com) 商品搜尋 scraper

方式：抓搜尋頁 HTML (search.aspx?q=<keyword>)，解析 .prod_item1512 商品區塊
  - href ../product/<id>   → code / buy_url
  - img alt=""             → name
  - img src=""             → image_url
  - .price > span          → price（網路價）
  - list_price / discount  → 搜尋頁無原價資訊，故 None

入口：https://www.tk3c.com/search.aspx?q=<keyword>
注意：https://www.tkec.com.tw → 301 → https://www.tk3c.com（已統一用新域名）
"""

import re
import html as _html
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
    "Referer": "https://www.tk3c.com/",
}

_BASE_URL = "https://www.tk3c.com"
_SEARCH_URL = f"{_BASE_URL}/search.aspx"

# 商品區塊 pattern：
#   <div class="prod_item1512 colBox">
#     <a ... href="../product/<id>?..."><img ... src="<img_url>" alt="<name>" .../></a>
#     ...
#     <div class="price">網路價<span>$<price></span></div>
#   </div>
_ITEM_RE = re.compile(
    r'<div class="prod_item1512 colBox">\s*'
    r'<a[^>]+href="\.\./product/(\d+)[^"]*"[^>]*>'   # group1: product_id
    r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)"[^>]*/></a>'  # group2: img, group3: name
    r'.*?'
    r'<div class="price">[^<]*<span>\$(\d+)</span>',  # group4: price
    re.DOTALL,
)


def _parse_items(page_html: str, limit: int) -> list[dict]:
    """從搜尋結果 HTML 解析商品清單。"""
    results: list[dict] = []

    for m in _ITEM_RE.finditer(page_html):
        if len(results) >= limit:
            break

        pid, img_url, name_raw, price_raw = m.groups()

        name = _html.unescape(name_raw).strip()
        if not name:
            continue

        try:
            price = int(price_raw)
        except (ValueError, TypeError):
            continue

        # 搜尋頁僅顯示「網路價」，無原價資訊
        list_price: Optional[int] = None
        discount_pct: Optional[int] = None

        # 圖片 URL：由 cdn-tkec.tw 提供，直接使用
        image_url = _html.unescape(img_url.strip())

        buy_url = f"{_BASE_URL}/product/{pid}"

        results.append({
            "site": "tkec",
            "code": pid,
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": buy_url,
            "rating": None,
            "review_count": None,
        })

    return results


async def search_tkec(query: str, limit: int = 6) -> list[dict]:
    """
    燦坤線上購物商品搜尋。

    Args:
        query: 搜尋關鍵字（中英文皆可）
        limit: 最多回傳幾筆，預設 6

    Returns:
        list[dict]，每筆格式：
        {
            "site": "tkec",
            "code": "商品ID",
            "name": "商品名稱",
            "price": 6890,
            "list_price": None,       # 搜尋頁無原價，僅顯示網路價
            "discount_pct": None,
            "image_url": "https://...",
            "buy_url": "https://www.tk3c.com/product/<id>",
            "rating": None,           # 搜尋頁無評分資料
            "review_count": None,
        }
    """
    params = {"q": query}
    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=20, follow_redirects=True
    ) as client:
        r = await client.get(_SEARCH_URL, params=params)
        r.raise_for_status()

    return _parse_items(r.text, limit)


# ── 快速測試 ──────────────────────────────────────────────────────────────────

async def _run_tests():
    queries = ["AirPods Pro", "電動牙刷"]
    for q in queries:
        t0 = time.perf_counter()
        results = await search_tkec(q, limit=6)
        elapsed = time.perf_counter() - t0
        print(f"\n=== {q} ({len(results)} 筆, {elapsed:.2f}s) ===")
        for p in results:
            disc = f"  省{p['discount_pct']}%" if p.get("discount_pct") else ""
            print(f"  [{p['code']}] {p['name'][:45]}  NT${p['price']:,}{disc}")
            print(f"         img: {(p['image_url'] or '')[:80]}")
            print(f"         url: {p['buy_url']}")


if __name__ == "__main__":
    asyncio.run(_run_tests())
