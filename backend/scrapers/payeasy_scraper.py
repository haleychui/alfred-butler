"""
payeasy_scraper.py — PayEasy (payeasy.com.tw) 商品搜尋 scraper

PayEasy 是台灣最大企業員工福利購物平台，搜尋功能需要 CAS 會員登入。
本 scraper 使用 Playwright headless browser 完整渲染搜尋結果頁，
並攔截 AjaxSolr (selectEc5) JSONP 回應取出商品資料。

抓取方式（雙軌）：
  ① session 模式（優先）：
       讀取 data/payeasy_session.json（格式同蝦皮）
       帶 Cookie header 直接 GET
       https://ecshop.payeasy.com.tw/ProductDataApi/selectEc5?q=...
  ② Playwright 模式（fallback）：
       攔截 mem-only-check.min.js / login-status.min.js，偽裝登入狀態
       在 page context 中等待 AjaxSolr 發出 selectEc5 請求
       若有注入的 session cookie，Solr 回 200；否則回 301 → 空列表

Solr doc 欄位映射：
  pidNum      → code
  pidName     → name
  pidSvalue   → price（福利價）
  pidPicpath  → image_url
  pidUrl      → buy_url
  discountType → 判斷是否折扣商品（有值代表有折扣）
  ※ list_price / rating / review_count 需 GetWelfareProducts（額外 POST），
     此版本暫不實作（需登入 member.payeasy.com.tw）

注意：
  • PayEasy 為企業員工福利平台，不對一般用戶開放（需公司帳號）
  • 如需使用，請從已登入瀏覽器 DevTools > Application > Cookies 取得：
      ecshop.payeasy.com.tw 的 AWSALB、AWSALBCORS
      member.payeasy.com.tw 的 ASP.NET_SessionId
    儲存為 data/payeasy_session.json（格式見文件尾端）
"""

import asyncio
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

try:
    from playwright.async_api import async_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

# ── 常數 ──────────────────────────────────────────────────────────────────────

_SOLR_URL = "https://ecshop.payeasy.com.tw/ProductDataApi/selectEc5"
_SEARCH_PAGE_URL = "https://www.payeasy.com.tw/search/search3/index.html"

# session 檔案路徑（格式：{"cookies": {"ASP.NET_SessionId": "xxx", "AWSALB": "yyy"}}）
_SESSION_FILE = Path(__file__).parent.parent.parent / "data" / "payeasy_session.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.payeasy.com.tw/search/search3/index.html",
    "Origin": "https://www.payeasy.com.tw",
}

# Solr 查詢參數（從 pezfind3.js 逆向分析）
_SOLR_BASE_PARAMS = [
    ("wt", "json"),
    ("rows", "75"),
    ("fq", "-webNum:61"),
    ("fq", "-categoryFullnum:*29666*"),
    ("defType", "search"),
    ("group", "true"),
    ("group.ngroups", "true"),
    ("group.field", "pidNum"),
    ("indent", "true"),
    ("mm", "100%"),
    ("sow", "false"),
    ("df", "_search_all"),
    ("qf", "_search_other^1 _search_brand^5 _search_category^5 _search_name^10"),
    ("ps", "10"),
    ("pf", "_search_other^1 _search_brand^5 _search_category^5 _search_name^10"),
]

# ── session 讀取 ──────────────────────────────────────────────────────────────

def _load_session() -> Optional[dict]:
    """讀取已儲存的 PayEasy session cookies"""
    # 優先讀環境變數
    env_session = os.environ.get("PAYEASY_SESSION", "").strip()
    if env_session:
        cookies = {}
        for part in env_session.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        if cookies:
            return {"cookies": cookies}

    # 讀 JSON 檔
    if _SESSION_FILE.exists():
        try:
            return json.loads(_SESSION_FILE.read_text())
        except Exception:
            pass
    return None


# ── 資料解析 ──────────────────────────────────────────────────────────────────

def _parse_doc(doc: dict) -> Optional[dict]:
    """將 Solr doc 轉換為標準商品格式"""
    pid_num = str(doc.get("pidNum") or "").strip()
    name = str(doc.get("pidName") or "").strip()
    if not pid_num or not name:
        return None

    price_raw = doc.get("pidSvalue")
    try:
        price = int(price_raw)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    image_url: str = str(doc.get("pidPicpath") or "").strip()
    buy_url: str = str(doc.get("pidUrl") or "").strip()
    if not buy_url:
        buy_url = (
            f"https://ecshop.payeasy.com.tw/ECShop/Product/ProductDetail/{pid_num}"
        )

    # 折扣標示（discountType 欄位存在且非空代表有折扣活動）
    discount_type = doc.get("discountType")
    has_discount = bool(discount_type)

    return {
        "site": "payeasy",
        "code": pid_num,
        "name": name,
        "price": price,
        "list_price": None,       # 需要 GetWelfareProducts POST（需登入 member）
        "discount_pct": None,     # 同上
        "image_url": image_url,
        "buy_url": buy_url,
        "rating": None,           # PayEasy 搜尋頁不顯示評分
        "review_count": None,
    }


def _parse_solr_response(text: str, limit: int) -> list[dict]:
    """解析 Solr/JSONP 回應文字，取出商品列表"""
    # JSONP 格式：callbackName({...})
    if "(" in text and text.rstrip().endswith(")"):
        idx = text.index("(")
        rp = text.rindex(")")
        json_str = text[idx + 1: rp]
    else:
        json_str = text

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return []

    groups = data.get("grouped", {}).get("pidNum", {}).get("groups", [])
    results: list[dict] = []
    for g in groups:
        docs = g.get("doclist", {}).get("docs", [])
        if docs:
            item = _parse_doc(docs[0])
            if item:
                results.append(item)
        if len(results) >= limit:
            break
    return results


# ── 直接 API 搜尋（需 session） ───────────────────────────────────────────────

async def _search_direct(
    query: str, limit: int, session: dict
) -> list[dict]:
    """帶 session cookies 直接呼叫 Solr API（最快，~1–2s）"""
    cookies = session.get("cookies", {})
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

    params = list(_SOLR_BASE_PARAMS) + [
        ("q", query),
        ("json.wrf", "pez_cb"),
    ]

    headers = dict(_HEADERS)
    headers["Cookie"] = cookie_str

    async with httpx.AsyncClient(
        headers=headers,
        timeout=12,
        follow_redirects=False,
    ) as client:
        try:
            r = await client.get(_SOLR_URL, params=params)
        except httpx.RequestError:
            return []

    if r.status_code != 200:
        return []   # 可能 session 過期，需重新登入

    return _parse_solr_response(r.text, limit)


# ── Playwright 搜尋（攔截 Solr 回應） ────────────────────────────────────────

async def _search_playwright(
    query: str, limit: int, session: Optional[dict]
) -> list[dict]:
    """
    用 Playwright 渲染搜尋頁，攔截 AjaxSolr selectEc5 JSONP 回應。
    若有 session cookies，注入後 Solr 會回 200；否則 301 → 空列表。
    """
    if not _HAS_PLAYWRIGHT:
        return []

    results: list[dict] = []
    done_event = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9"},
            )

            # 注入 session cookies
            if session:
                cookies_data = session.get("cookies", {})
                cookie_list = []
                for name, value in cookies_data.items():
                    for domain in ["ecshop.payeasy.com.tw", ".payeasy.com.tw"]:
                        cookie_list.append({
                            "name": name,
                            "value": value,
                            "domain": domain,
                            "path": "/",
                        })
                if cookie_list:
                    await context.add_cookies(cookie_list)

            page = await context.new_page()

            # 攔截 mem-only-check（避免未登入跳轉 CAS login）
            await page.route(
                "**/mem-only-check.min.js**",
                lambda r: r.fulfill(
                    status=200, content_type="application/javascript",
                    body="// payeasy scraper: mem-only-check disabled"
                ),
            )
            # 偽裝 getLoginStatus() = 2（已登入狀態）
            await page.route(
                "**/login-status.min.js**",
                lambda r: r.fulfill(
                    status=200, content_type="application/javascript",
                    body="function getLoginStatus(){ return 2; }",
                ),
            )

            processed_urls: set[str] = set()

            async def on_response(response):
                url = response.url
                if "ProductDataApi" not in url or "selectEc5" not in url:
                    return
                # 去掉 timestamp 避免重複處理
                url_key = re.sub(r"[&?](?:_|json\.wrf)=[^&]*", "", url)
                if url_key in processed_urls:
                    return
                processed_urls.add(url_key)

                if response.status != 200:
                    return

                try:
                    text = await response.text()
                    items = _parse_solr_response(text, limit)
                    results.extend(items)
                    done_event.set()
                except Exception:
                    pass

            page.on("response", on_response)

            try:
                await page.goto(
                    f"{_SEARCH_PAGE_URL}?q={urllib.parse.quote(query)}",
                    wait_until="domcontentloaded",
                    timeout=25_000,
                )
                await asyncio.wait_for(done_event.wait(), timeout=15.0)
            except (asyncio.TimeoutError, Exception):
                pass

        finally:
            await browser.close()

    return results[:limit]


# ── 公開入口 ──────────────────────────────────────────────────────────────────

async def search_payeasy(query: str, limit: int = 6) -> list[dict]:
    """
    PayEasy 商品搜尋。

    ⚠️  PayEasy 為企業員工福利平台，搜尋需要已登入的 CAS session。
        請提供 session cookies（見 NOTES），否則回傳空列表。

    ── 提供 session 方式（二擇一）：
       A. 環境變數：
          export PAYEASY_SESSION="ASP.NET_SessionId=xxx; AWSALB=yyy; AWSALBCORS=zzz"
       B. JSON 檔（data/payeasy_session.json）：
          {"cookies": {"ASP.NET_SessionId": "xxx", "AWSALB": "yyy"}}
          （從已登入瀏覽器 DevTools > Application > Cookies (ecshop.payeasy.com.tw) 取得）

    ── 回傳格式（每筆）：
       site / code / name / price / list_price / discount_pct /
       image_url / buy_url / rating / review_count
       ※ list_price / discount_pct / rating / review_count 暫不支援（需額外 POST）
    """
    session = _load_session()

    # 無 session → PayEasy 完全不可用（members-only 平台），快速返回空列表
    if not session:
        return []

    # 優先：直接 API 呼叫（最快，~1–2s）
    results = await _search_direct(query, limit, session)
    if results:
        return results

    # Fallback：Playwright 完整渲染（session 可能過期或被 CDN block）
    results = await _search_playwright(query, limit, session)
    return results


# ── 測試 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    執行方式：
      python3 payeasy_scraper.py

    若有 session cookies：
      export PAYEASY_SESSION="ASP.NET_SessionId=xxx; AWSALB=yyy"
      python3 payeasy_scraper.py
    """

    async def _main():
        test_queries = ["面膜", "防曬乳"]
        session_available = bool(_load_session())
        if not session_available:
            print("⚠  未找到 PayEasy session（data/payeasy_session.json 或 PAYEASY_SESSION 環境變數）")
            print("   PayEasy 為 members-only 平台，無 session 時回傳空列表。")
            print("   請從已登入瀏覽器的 DevTools > Application > Cookies 取得：")
            print("   - ecshop.payeasy.com.tw 的 AWSALB、AWSALBCORS")
            print("   - member.payeasy.com.tw 的 ASP.NET_SessionId")
            print()

        for q in test_queries:
            t0 = time.time()
            results = await search_payeasy(q, limit=6)
            elapsed = round(time.time() - t0, 2)
            print(f"===== 搜尋: {q!r} ({elapsed}s, {len(results)} 筆) =====")
            for item in results:
                print(json.dumps(item, ensure_ascii=False, indent=2))
            if not results:
                print(f"  (空結果 — {'需要有效 session' if not session_available else 'session 可能過期'})")
            print()

    asyncio.run(_main())

"""
data/payeasy_session.json 格式範例：
{
    "cookies": {
        "ASP.NET_SessionId": "從 member.payeasy.com.tw Cookies 取得",
        "AWSALB": "從 ecshop.payeasy.com.tw Cookies 取得",
        "AWSALBCORS": "從 ecshop.payeasy.com.tw Cookies 取得"
    }
}
"""
