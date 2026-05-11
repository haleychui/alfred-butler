"""
carrefour_scraper.py — 家樂福線上購物 (online.carrefour.com.tw) 商品搜尋 scraper

方式：抓搜尋頁 HTML，解析商品連結 anchor 的 data-* 屬性
  - data-pid       → code
  - data-name      → name
  - data-price     → price（促銷價）
  - data-baseprice → baseprice（未必等於定價）
  - .original-price → list_price（頁面顯示的劃掉定價）
  - .current-price  → 確認 price
  - img.m_lazyload  → image_url

家樂福搜尋入口：https://online.carrefour.com.tw/zh/search/?q=<keyword>
後端是 Salesforce Commerce Cloud (Demandware)，商品在 SSR HTML 裡，無需 JS。
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
}

_SEARCH_URL = "https://online.carrefour.com.tw/zh/search/"

# 商品連結 anchor：包含所有 data-* 欄位及 anchor 內容（用於取圖片）
_TILE_RE = re.compile(
    r'class="gtm-product-alink"[^>]*'
    r'href="(/zh/[^"]+\.html)"[^>]*'
    r'data-pid="(\d+)"[^>]*'
    r'data-price="([\d.]+)"[^>]*'
    r'data-baseprice="([\d.]+)"[^>]*'
    r'(?:data-category="[^"]*"[^>]*)?'
    r'(?:data-brand="[^"]*"[^>]*)?'
    r'(?:data-quantity="[^"]*"[^>]*)?'
    r'(?:data-variant="[^"]*"[^>]*)?'
    r'data-name="([^"]+)"[^>]*'
    r'(?:data-ifavailable="[^"]*")?[^>]*>'
    r'(.*?)</a>',           # anchor 內容（含圖片）
    re.DOTALL,
)

# m_lazyload 商品圖片（在 anchor 內）
_IMG_RE = re.compile(r'<img class="m_lazyload" src="([^"]+)"')

# 定價（劃掉）：`<div class="original-price"><i>$ 130</i></div>`
_LIST_PRICE_RE = re.compile(
    r'<div class="original-price"><i>\$?\s*([\d,]+)\s*</i></div>'
)

# 促銷價（顯示）：`<div class="current-price"><em>$109</em>`
_CURR_PRICE_RE = re.compile(
    r'<div class="current-price"><em>\$([\d,]+)</em>'
)


def _parse_tiles(page_html: str, limit: int) -> list[dict]:
    """從搜尋結果 HTML 解析商品清單。"""
    results: list[dict] = []

    for m in _TILE_RE.finditer(page_html):
        if len(results) >= limit:
            break

        href, pid, price_raw, baseprice_raw, name_raw, body = m.groups()

        # 商品名稱（HTML entity decode）
        name = _html.unescape(name_raw).strip()
        if not name:
            continue

        # 價格（data-price 是促銷價）
        try:
            price = int(float(price_raw))
        except (ValueError, TypeError):
            continue

        # 定價（原價）：在 anchor 之後的 price block 裡
        #   找 .original-price，位置在 anchor 結束後 ~1000 chars
        anchor_end = m.end()
        price_block = page_html[anchor_end: anchor_end + 1500]

        list_price: Optional[int] = None
        lp_m = _LIST_PRICE_RE.search(price_block)
        if lp_m:
            try:
                lp = int(lp_m.group(1).replace(",", ""))
                list_price = lp if lp > price else None
            except (ValueError, TypeError):
                pass

        # .current-price 確認（有時與 data-price 略有差異，以頁面顯示為準）
        cp_m = _CURR_PRICE_RE.search(price_block)
        if cp_m:
            try:
                price = int(cp_m.group(1).replace(",", ""))
            except (ValueError, TypeError):
                pass

        # list_price 最終值
        effective_list = list_price if list_price and list_price > price else None
        discount_pct: Optional[int] = None
        if effective_list:
            discount_pct = round((effective_list - price) / effective_list * 100)

        # 圖片：在 anchor 內容（body）找 m_lazyload
        img_url = ""
        img_m = _IMG_RE.search(body)
        if img_m:
            img_url = _html.unescape(img_m.group(1))

        buy_url = f"https://online.carrefour.com.tw{href}"

        results.append({
            "site": "carrefour",
            "code": pid,
            "name": name,
            "price": price,
            "list_price": effective_list,
            "discount_pct": discount_pct,
            "image_url": img_url,
            "buy_url": buy_url,
            "rating": None,
            "review_count": None,
        })

    return results


async def search_carrefour(query: str, limit: int = 6) -> list[dict]:
    """
    家樂福線上購物商品搜尋。

    Args:
        query: 搜尋關鍵字（中英文皆可）
        limit: 最多回傳幾筆，預設 6

    Returns:
        list[dict]，每筆格式：
        {
            "site": "carrefour",
            "code": "商品ID",
            "name": "商品名稱",
            "price": 123,
            "list_price": 150,        # 原價，無折扣時 None
            "discount_pct": 18,       # 折扣百分比，無折扣時 None
            "image_url": "https://...",
            "buy_url": "https://...",
            "rating": None,           # 家樂福搜尋頁無評分資料
            "review_count": None,
        }
    """
    params = {"q": query}
    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=20, follow_redirects=True
    ) as client:
        r = await client.get(_SEARCH_URL, params=params)
        r.raise_for_status()

    return _parse_tiles(r.text, limit)


# ── 快速測試 ──────────────────────────────────────────────────────────────────

async def _run_tests():
    queries = ["醬油", "洗碗精"]
    for q in queries:
        t0 = time.perf_counter()
        results = await search_carrefour(q, limit=6)
        elapsed = time.perf_counter() - t0
        print(f"\n=== {q} ({len(results)} 筆, {elapsed:.2f}s) ===")
        for p in results:
            disc = f"  省{p['discount_pct']}%" if p.get("discount_pct") else ""
            print(f"  [{p['code']}] {p['name'][:40]}  NT${p['price']:,}{disc}")
            print(f"         list: {p['list_price']}")
            print(f"         img: {(p['image_url'] or '')[:80]}")
            print(f"         url: {p['buy_url'][:80]}")


if __name__ == "__main__":
    asyncio.run(_run_tests())
