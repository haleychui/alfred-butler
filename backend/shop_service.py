"""
shop_service.py — 台灣電商比價引擎
純演算法，零 LLM。抓商品名稱、價格、折扣、規格、一張圖。
目前支援：momo、PChome 24h、蝦皮（需登入 cookies）、松果購物 (pcone.com.tw)、博客來、東森購物 (etmall)、Yahoo 奇摩購物、家樂福
"""
import re
import json
import asyncio
import httpx
from typing import Optional
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from scrapers.books_scraper import search_books
from scrapers.yahoo_scraper import search_yahoo_shopping
from scrapers.carrefour_scraper import search_carrefour
from scrapers.buy123_scraper import search_buy123
from scrapers.trplus_scraper import search_trplus
from scrapers.elifemall_scraper import search_elifemall
from scrapers.coupang_scraper import search_coupang
from scrapers.pinkoi_scraper import search_pinkoi
from scrapers.tkec_scraper import search_tkec
from scrapers.biggo_scraper import search_biggo

# 蝦皮 session cookies 存放路徑（登入後由 /api/shop/shopee-login 寫入）
_SHOPEE_COOKIE_FILE = Path(__file__).parent.parent / "data" / "shopee_session.json"

_HEADERS_MOBILE = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_HEADERS_DESKTOP = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://24h.pchome.com.tw/",
}

_PCHOME_IMG_BASE = "https://cs-b.ecimg.tw"


# ── momo ──────────────────────────────────────────────────────────────────────

def _extract_momo_products(html: str, limit: int = 6) -> list[dict]:
    m = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    graph = data if isinstance(data, list) else data.get("@graph", [data])
    items = []
    for node in graph:
        if node.get("@type") == "ItemList":
            items = node.get("itemListElement", [])
            break

    products = []
    for item in items[:limit]:
        name = item.get("name", "")
        image_url = item.get("image", "")
        buy_url = item.get("url", "")
        price = int(item.get("offers", {}).get("price", 0))
        rating = item.get("aggregateRating", {})

        code_m = re.search(r"i_code=(\d+)", buy_url)
        code = code_m.group(1) if code_m else ""
        canonical_url = f"https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={code}" if code else buy_url

        list_price = _extract_momo_list_price(html, code) if code else None
        discount_pct = None
        if list_price and list_price > price:
            discount_pct = round((1 - price / list_price) * 100)

        if not price or not name:
            continue

        products.append({
            "site": "momo",
            "code": code,
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": canonical_url,
            "rating": rating.get("ratingValue"),
            "review_count": rating.get("reviewCount"),
        })
    return products


def _extract_momo_list_price(html: str, code: str) -> Optional[int]:
    m = re.search(
        rf'\\\\?"goodsCode\\\\?":\\\\?"0*{code}\\\\?".*?\\\\?"listPrice\\\\?":\\\\?"([^"\\\\]+)',
        html
    )
    if m:
        digits = re.sub(r"[^0-9]", "", m.group(1))
        return int(digits) if digits else None
    return None


async def search_momo(query: str, limit: int = 6) -> list[dict]:
    params = httpx.QueryParams({"keyword": query, "searchType": "1", "ent": "k", "curPage": "1"})
    url = f"https://www.momoshop.com.tw/search/searchShop.jsp?{params}"
    async with httpx.AsyncClient(headers=_HEADERS_MOBILE, timeout=15, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
    return _extract_momo_products(r.text, limit)


# ── PChome 24h ────────────────────────────────────────────────────────────────

def _pchome_image_url(pic_path: str) -> str:
    if not pic_path:
        return ""
    if pic_path.startswith("http"):
        return pic_path
    return f"{_PCHOME_IMG_BASE}{pic_path}"


def _extract_pchome_products(data: dict, limit: int = 6) -> list[dict]:
    prods = data.get("prods", [])
    products = []
    for p in prods[:limit]:
        pid = p.get("Id", "")
        name = p.get("name", "")
        price = int(p.get("price", 0))
        origin_price = int(p.get("originPrice", 0))
        pic = _pchome_image_url(p.get("picS", ""))

        if not price or not name:
            continue

        discount_pct = None
        if origin_price and origin_price > price:
            discount_pct = round((1 - price / origin_price) * 100)

        products.append({
            "site": "pchome",
            "code": pid,
            "name": name,
            "price": price,
            "list_price": origin_price if origin_price != price else None,
            "discount_pct": discount_pct,
            "image_url": pic,
            "buy_url": f"https://24h.pchome.com.tw/prod/{pid}",
            "rating": None,
            "review_count": None,
        })
    return products


async def search_pchome(query: str, limit: int = 6) -> list[dict]:
    url = (
        "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
        f"?q={httpx.QueryParams({'q': query}).get('q', query)}&page=1&sort=rnk/dc"
    )
    async with httpx.AsyncClient(headers=_HEADERS_DESKTOP, timeout=12) as client:
        r = await client.get(url)
        r.raise_for_status()
    return _extract_pchome_products(r.json(), limit)


# ── 蝦皮 ──────────────────────────────────────────────────────────────────────

def _load_shopee_cookies() -> Optional[dict]:
    """讀取已儲存的蝦皮 session cookies"""
    try:
        if _SHOPEE_COOKIE_FILE.exists():
            return json.loads(_SHOPEE_COOKIE_FILE.read_text())
    except Exception:
        pass
    return None


def _extract_shopee_products(items: list, limit: int = 6) -> list[dict]:
    products = []
    for item in items[:limit]:
        b = item.get("item_basic", item)
        name = b.get("name", "")
        # 蝦皮價格單位是 /100000
        raw_price = b.get("price") or b.get("price_min") or 0
        price = int(raw_price / 100000) if raw_price > 10000 else int(raw_price)
        raw_list = b.get("price_before_discount") or 0
        list_price = int(raw_list / 100000) if raw_list > 10000 else None

        discount_pct = None
        if list_price and list_price > price:
            discount_pct = round((1 - price / list_price) * 100)

        images = b.get("images", [])
        img_hash = images[0] if images else ""
        image_url = f"https://down-tw.img.susercontent.com/file/{img_hash}" if img_hash else ""

        shopid = b.get("shopid", "")
        itemid = b.get("itemid", "")
        buy_url = f"https://shopee.tw/product/{shopid}/{itemid}" if shopid and itemid else ""

        rating = b.get("item_rating", {})
        rating_val = rating.get("rating_star", None)

        if not price or not name:
            continue

        products.append({
            "site": "shopee",
            "code": str(itemid),
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": buy_url,
            "rating": f"{rating_val:.1f}" if rating_val else None,
            "review_count": str(b.get("sold", "")),
        })
    return products


async def search_shopee(query: str, limit: int = 6) -> list[dict]:
    """蝦皮搜尋，需要已儲存的 session cookies"""
    session = _load_shopee_cookies()
    if not session:
        return []  # 尚未登入，靜默略過

    cookie_str = "; ".join(f"{k}={v}" for k, v in session.get("cookies", {}).items())
    csrf = session.get("csrftoken", "")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "zh-TW,zh;q=0.9",
        "Referer": f"https://shopee.tw/search?keyword={query}",
        "x-csrftoken": csrf,
        "Cookie": cookie_str,
    }
    url = (
        "https://shopee.tw/api/v4/search/search_items"
        f"?by=relevancy&keyword={httpx.QueryParams({'q': query}).get('q', query)}"
        "&limit=10&newest=0&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2"
    )
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            return []
        d = r.json()
        if d.get("error"):
            return []
        return _extract_shopee_products(d.get("items", []), limit)


# ── 東森購物 (ETMall) ──────────────────────────────────────────────────────────

_ETMALL_BASE = "https://www.etmall.com.tw"
_ETMALL_IMG_BASE = "https://media.etmall.com.tw"

_ETMALL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.etmall.com.tw/",
}


async def search_etmall(query: str, limit: int = 6) -> list[dict]:
    """東森購物搜尋，使用 /Search/Get JSON API。

    API 回傳欄位：
      id, title, finalPrice, marketingPrice, DiscountRate, imageUrl, pageLink
    """
    url = f"{_ETMALL_BASE}/Search/Get"
    params = {
        "Keyword": query,
        "SortType": 0,
        "PageSize": min(limit * 2, 20),  # 多拿一點以防缺貨品
        "PageIndex": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(url, params=params, headers=_ETMALL_HEADERS)
            if r.status_code != 200:
                return []
            d = r.json()
    except Exception:
        return []

    raw = d.get("SearchProductResult", {}).get("products", [])
    products = []
    for item in raw:
        if not item.get("purchasable") or not item.get("haveStocks"):
            continue

        product_id = str(item.get("id", ""))
        name = (item.get("title") or "").strip()
        if not product_id or not name:
            continue

        # 價格：finalPrice / marketingPrice 是字串
        try:
            final_price = int(item.get("finalPrice") or 0)
            market_price = int(item.get("marketingPrice") or 0)
        except (ValueError, TypeError):
            continue
        if final_price <= 0:
            continue

        # 折扣百分比：API DiscountRate 有時為 0，自行計算
        if market_price and market_price > final_price:
            discount_pct = round((1 - final_price / market_price) * 100)
        else:
            discount_pct = 0
            market_price = market_price if market_price >= final_price else None

        # 圖片 URL（補齊 scheme）
        img = item.get("imageUrl") or ""
        if img.startswith("//"):
            img = "https:" + img
        elif img and not img.startswith("http"):
            img = _ETMALL_IMG_BASE + img

        buy_url = f"{_ETMALL_BASE}{item.get('pageLink', '')}" if item.get("pageLink") else ""

        products.append({
            "site": "etmall",
            "code": product_id,
            "name": name,
            "price": final_price,
            "list_price": market_price,
            "discount_pct": discount_pct if discount_pct > 0 else None,
            "image_url": img or None,
            "buy_url": buy_url or None,
            "rating": None,
            "review_count": None,
        })

        if len(products) >= limit:
            break

    return products



# ── 松果購物 (pcone.com.tw) ───────────────────────────────────────────────────

_PINECONE_API_BASE = "https://webapi.pcone.com.tw"
_PINECONE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Origin": "https://pcone.com.tw",
    "Referer": "https://pcone.com.tw/",
}


def _parse_pinecone_price(price_str) -> int:
    """把 '4,190' 或 165 轉成 int"""
    try:
        return int(re.sub(r"[^0-9]", "", str(price_str)))
    except (ValueError, TypeError):
        return 0


def _extract_pinecone_products(data: dict, limit: int = 6) -> list[dict]:
    """解析 /api/products/search 回傳的 data.products 陣列"""
    inner = data.get("data") or {}
    products_raw = inner.get("products", [])
    products = []
    for p in products_raw[:limit]:
        name = p.get("name", "")
        display_id = p.get("display_id", "")
        link_url = p.get("link_url") or f"https://pcone.com.tw/product/info/{display_id}"
        image_url = p.get("image_url", "")
        price = _parse_pinecone_price(p.get("price", 0))
        # orginal_price 是市價（API 欄位拼錯但沿用原 key）
        list_price_raw = p.get("orginal_price")
        list_price = _parse_pinecone_price(list_price_raw) if list_price_raw else None
        # discount 欄位是「幾折」(例如 38 = 38折)，換算成「省多少%」
        discount_raw = p.get("discount")
        discount_pct = None
        if discount_raw is not None:
            try:
                d = int(discount_raw)
                if 0 < d < 100:
                    discount_pct = 100 - d
            except (ValueError, TypeError):
                pass
        # list_price 不存在時用折扣反推
        if list_price is None and discount_pct is not None and price > 0:
            list_price = round(price / (1 - discount_pct / 100))

        if not price or not name:
            continue

        products.append({
            "site": "pinecone",
            "code": display_id,
            "name": name,
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "image_url": image_url,
            "buy_url": link_url,
            "rating": None,
            "review_count": None,
        })
    return products


async def search_pinecone(query: str, limit: int = 6) -> list[dict]:
    """
    松果購物商品搜尋。

    呼叫 pcone.com.tw 前端所使用的官方 REST API（非 HTML scraping，純 JSON）。
    API endpoint: POST https://webapi.pcone.com.tw/api/products/search
    body: {"count": N, "page": 1, "seed": null, "kw": "查詢字"}

    rating / review_count 松果 API 不提供，固定為 None。

    Args:
        query: 搜尋關鍵字，例如 "AirPods Pro"
        limit: 最多回傳幾筆，預設 6

    Returns:
        list of dict，每筆包含:
            site, code, name, price, list_price, discount_pct,
            image_url, buy_url, rating, review_count
    """
    url = f"{_PINECONE_API_BASE}/api/products/search"
    payload = {
        "count": max(limit, 6),  # API 最小回傳 6 筆
        "page": 1,
        "seed": None,
        "kw": query,
    }
    from urllib.parse import quote
    headers = {**_PINECONE_HEADERS, "Referer": f"https://pcone.com.tw/search/?q={quote(query)}"}

    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()

    data = r.json()
    if data.get("status") != "SUCCESS":
        return []

    return _extract_pinecone_products(data, limit)


# ── 露天市集 (ruten.com.tw) ───────────────────────────────────────────────────

_RUTEN_SEARCH_URL = "https://rtapi.ruten.com.tw/api/search/v4/index.php/core/prod"
_RUTEN_ITEMS_URL  = "https://rapi.ruten.com.tw/api/items/v2/list"
_RUTEN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.ruten.com.tw/",
    "Origin": "https://www.ruten.com.tw",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}

# 露天商品價格上限（超過視為異常標價，過濾掉）
_RUTEN_PRICE_MAX = 9_000_000


async def search_ruten(query: str, limit: int = 6) -> list[dict]:
    """露天市集商品搜尋。

    兩步驟：
    1. rtapi.ruten.com.tw/api/search/v4 取得商品 ID 清單（rnk/dc 相關性排序）
    2. rapi.ruten.com.tw/api/items/v2/list 批次取商品詳情（名稱/價格/圖片）

    注意：
    - sort 只支援 rnk/dc | prc/ac | prc/dc | ords/dc | new/dc（不能用 /asc）
    - offset=0 會觸發 400，預設不傳 offset
    - 含「異常標價」(99999999) 的結果以 _RUTEN_PRICE_MAX 過濾

    Args:
        query: 搜尋關鍵字，例如 "AirPods Pro"
        limit: 最多回傳幾筆，預設 6

    Returns:
        list of dict，每筆包含:
            site, code, name, price, list_price, discount_pct,
            image_url, buy_url, rating, review_count
    """
    from urllib.parse import quote as _quote

    fetch_count = min(limit + 4, 20)  # 多拿一點供過濾用
    search_url = (
        f"{_RUTEN_SEARCH_URL}"
        f"?q={_quote(query)}&limit={fetch_count}&sort=rnk%2Fdc"
    )

    try:
        async with httpx.AsyncClient(
            headers=_RUTEN_HEADERS, timeout=12, follow_redirects=True
        ) as client:
            # Step 1: 取 ID 清單
            r1 = await client.get(search_url)
            if r1.status_code != 200:
                return []
            rows = r1.json().get("Rows", [])
            ids = [row["Id"] for row in rows if row.get("Id")]
            if not ids:
                return []

            # Step 2: 批次取商品詳情
            r2 = await client.get(
                _RUTEN_ITEMS_URL,
                params={"gno": ",".join(ids[:fetch_count])},
            )
            if r2.status_code != 200:
                return []
            items_raw = r2.json().get("data", [])
    except Exception:
        return []

    products = []
    for item in items_raw:
        # 跳過下架或無庫存
        if not item.get("available") or item.get("stock_status", 0) == 0:
            continue

        gno  = str(item.get("id", ""))
        name = (item.get("name") or "").strip()
        if not gno or not name:
            continue

        price = int(item.get("goods_price") or 0)
        if price <= 0 or price > _RUTEN_PRICE_MAX:
            continue

        ori_price = int(item.get("goods_ori_price") or 0)
        list_price = ori_price if ori_price > price else None
        discount_pct = (
            round((1 - price / ori_price) * 100)
            if list_price and ori_price > 0
            else None
        )

        img_urls = item.get("images", {}).get("url", [])
        image_url = img_urls[0] if img_urls else ""

        products.append({
            "site":         "ruten",
            "code":         gno,
            "name":         name,
            "price":        price,
            "list_price":   list_price,
            "discount_pct": discount_pct,
            "image_url":    image_url,
            "buy_url":      f"https://www.ruten.com.tw/item/show?{gno}",
            "rating":       None,
            "review_count": None,
        })

        if len(products) >= limit:
            break

    return products


# ── 跨站整合 ──────────────────────────────────────────────────────────────────

async def search_products(query: str, sites: Optional[list[str]] = None, limit: int = 6) -> list[dict]:
    """跨平台搜尋，13 站並發，依價格排序。蝦皮需 session。"""
    if sites is None:
        sites = ["momo", "pchome", "books", "pinecone", "etmall", "yahoo", "carrefour", "buy123", "trplus", "elifemall", "coupang", "pinkoi", "tkec", "ruten", "biggo"]
        if _load_shopee_cookies():
            sites.append("shopee")
    tasks = []
    if "momo" in sites:
        tasks.append(search_momo(query, limit))
    if "pchome" in sites:
        tasks.append(search_pchome(query, limit))
    if "books" in sites:
        tasks.append(search_books(query, limit))
    if "etmall" in sites:
        tasks.append(search_etmall(query, limit))
    if "yahoo" in sites:
        tasks.append(search_yahoo_shopping(query, limit))
    if "pinecone" in sites:
        tasks.append(search_pinecone(query, limit))
    if "carrefour" in sites:
        tasks.append(search_carrefour(query, limit))
    if "buy123" in sites:
        tasks.append(search_buy123(query, limit))
    if "trplus" in sites:
        tasks.append(search_trplus(query, limit))
    if "elifemall" in sites:
        tasks.append(search_elifemall(query, limit))
    if "coupang" in sites:
        tasks.append(search_coupang(query, limit))
    if "pinkoi" in sites:
        tasks.append(search_pinkoi(query, limit))
    if "tkec" in sites:
        tasks.append(search_tkec(query, limit))
    if "ruten" in sites:
        tasks.append(search_ruten(query, limit))
    if "biggo" in sites:
        tasks.append(search_biggo(query, limit))
    if "shopee" in sites:
        tasks.append(search_shopee(query, limit))

    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    all_products = []
    for r in results_nested:
        if isinstance(r, list):
            all_products.extend(r)

    all_products.sort(key=lambda x: x["price"])
    return all_products[:limit]


def format_for_alfred(products: list[dict]) -> str:
    if not products:
        return "找不到相關商品，換個關鍵字試試。"
    lines = []
    for i, p in enumerate(products[:3], 1):
        disc = f"，省{p['discount_pct']}%" if p.get("discount_pct") else ""
        rating = f" ⭐{p['rating']}" if p.get("rating") else ""
        lines.append(f"{i}. [{p['site']}] {p['name'][:26]}　{p['price']:,}元{disc}{rating}")
    return "\n".join(lines)
