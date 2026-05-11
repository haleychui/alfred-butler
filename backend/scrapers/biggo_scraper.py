"""
biggo_scraper.py — 比價王 (biggo.com.tw) 商品搜尋 scraper
方式：抓 /s/<query> 頁面 HTML，解析 Next.js RSC inline 資料（__next_f.push）
優勢：一次搜尋涵蓋 momo、Yahoo、PChome、Coupang、蝦皮等多台灣電商，
     每筆都有 source_store 欄位標示來源店家。
"""

import re
import json
import asyncio
import time
from typing import Optional
from urllib.parse import quote

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

_BASE_URL = "https://biggo.com.tw/s/"


# ── nindex → 店家中文名稱對照（補充 store.name 為空時的 fallback）──────────
_NINDEX_NAME: dict[str, str] = {
    "tw_pec_ybuy":        "Yahoo購物中心",
    "tw_pec_momoshop":    "momo購物網",
    "tw_pec_pchome":      "PChome 24h購物",
    "tw_pec_coupang":     "酷澎 Coupang",
    "tw_pec_globalmall":  "環球Online",
    "tw_mall_shopeemall": "蝦皮商城",
    "tw_pec_rakuten":     "樂天市場",
    "tw_pmall_rakuten":   "樂天市場",
    "tw_pec_etmall":      "東森購物",
    "tw_pec_books":       "博客來",
    "tw_pec_3c3c":        "小蔡電器",
    "tw_pec_myfone":      "myPhone",
    "tw_pec_hktvmall":    "HKTVmall",
    "tw_pec_cht_ecmall":  "中華電信",
    "tw_pec_fnkpie":      "法雅客",
    "tw_pec_jh":          "JH鑽石珠寶",
}


def _find_ssrData(obj) -> Optional[dict]:
    """遞迴搜尋 ssrData 物件"""
    if isinstance(obj, dict):
        if "ssrData" in obj:
            return obj["ssrData"]
        for v in obj.values():
            r = _find_ssrData(v)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = _find_ssrData(item)
            if r is not None:
                return r
    return None


def _extract_list(html: str) -> list[dict]:
    """
    從 biggo /s/<query> 頁面的 HTML 中取出商品列表。

    biggo 使用 Next.js App Router，SSR 資料以 RSC（React Server Components）
    格式嵌入：
        self.__next_f.push([1, "1c:[...,{ssrData:{...,list:[...]}}]"])
    最大的 push 字串即為產品資料區塊。
    """
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)

    # 找最大且符合 __next_f.push([1, ...]) 格式的 script
    candidates = [
        s for s in scripts
        if s.startswith('self.__next_f.push([1,') and len(s) > 10000
    ]
    if not candidates:
        return []

    largest = max(candidates, key=len)

    # 提取引號內的 JSON 編碼字串
    m = re.match(r'self\.__next_f\.push\(\[1,"(.*)"\]\)\s*$', largest, re.DOTALL)
    if not m:
        return []

    try:
        unescaped: str = json.loads('"' + m.group(1) + '"')
    except json.JSONDecodeError:
        return []

    # RSC 格式以 "1c:" 開頭的行包含完整資料樹
    idx = unescaped.find("1c:")
    if idx == -1:
        return []

    try:
        data = json.loads(unescaped[idx + 3:])
    except json.JSONDecodeError:
        return []

    ssrData = _find_ssrData(data)
    if not ssrData:
        return []

    return ssrData.get("list", [])


def _parse_item(item: dict) -> Optional[dict]:
    """把單筆 biggo list item 轉成標準格式"""
    title = (item.get("title") or "").strip()
    price_raw = item.get("price")
    if not title or price_raw is None:
        return None

    # 跳過下架 / 已過期 / 成人 商品
    if item.get("is_offline") or item.get("is_expired") or item.get("is_adult"):
        return None

    try:
        price = int(float(price_raw))
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    nindex: str = item.get("nindex", "")
    oid: str = str(item.get("oid", ""))

    # 店家名稱：優先 store.name，其次 nindex 對照表
    store_info: dict = item.get("store") or {}
    source_store: str = (
        store_info.get("name")
        or _NINDEX_NAME.get(nindex, nindex)
    )

    # site 欄位：用 nindex 派生，區分多店
    site_tag = nindex if nindex else "biggo"

    # 商品直連 URL（purl 是原店家頁；affurl 是帶 biggo 聯盟碼的中轉）
    purl: str = item.get("purl") or ""
    buy_url = purl if purl else f"https://biggo.com.tw/r/?i={nindex}&id={oid}"

    # 圖片：優先 origin_image（高解析度），其次 image（縮圖）
    image_url: str = item.get("origin_image") or item.get("image") or ""

    return {
        "site": site_tag,
        "code": oid,
        "name": title,
        "price": price,
        "list_price": None,       # biggo 搜尋頁不提供原價
        "discount_pct": None,
        "image_url": image_url,
        "buy_url": buy_url,
        "rating": None,           # biggo 搜尋頁不提供評分
        "review_count": None,
        "source_store": source_store,
    }


async def search_biggo(query: str, limit: int = 6) -> list[dict]:
    """
    比價王多店家商品搜尋。

    一次搜尋即可獲得來自 momo、Yahoo購物中心、PChome、酷澎 Coupang、
    蝦皮商城、環球Online 等多台灣電商的商品資料。

    Args:
        query: 搜尋關鍵字（中英文皆可）
        limit: 最多回傳幾筆，預設 6

    Returns:
        list[dict]，每筆格式：
        {
            "site":         "tw_pec_momoshop",   # nindex（區分來源）
            "code":         "商品ID",
            "name":         "商品名稱",
            "price":        123,
            "list_price":   None,
            "discount_pct": None,
            "image_url":    "https://...",
            "buy_url":      "https://...",        # 直連原店家商品頁
            "rating":       None,
            "review_count": None,
            "source_store": "momo購物網",         # 人類可讀的店家名稱
        }
    """
    url = _BASE_URL + quote(query, safe="")
    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=20, follow_redirects=True
    ) as client:
        r = await client.get(url)
        r.raise_for_status()

    raw_items = _extract_list(r.text)

    products: list[dict] = []
    for item in raw_items:
        p = _parse_item(item)
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
        results = await search_biggo(q, limit=8)
        elapsed = time.perf_counter() - t0
        print(f"\n=== {q} ({len(results)} 筆, {elapsed:.2f}s) ===")
        for p in results:
            print(
                f"  [{p['source_store']:15s}] "
                f"NT${p['price']:>7,}  "
                f"{p['name'][:45]}"
            )
            print(f"         img: {p['image_url'][:70]}")
            print(f"         url: {p['buy_url'][:80]}")


if __name__ == "__main__":
    asyncio.run(_run_tests())
