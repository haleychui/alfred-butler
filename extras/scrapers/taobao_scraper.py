"""
scrapers/taobao_scraper.py

API 1: taobao.tbk.item.info.get  (docId=24518)  — 商品ID → 價格/銷量/標題
API 2: taobao.tbk.shop.get       (docId=24521)  — 關鍵字 → 店鋪列表
API 3: 搜尋頁抓商品ID            (無需授權)    — 關鍵字 → 商品ID 清單

環境變數:
  TAOBAO_APP_KEY    = 你的 app_key
  TAOBAO_APP_SECRET = 你的 app_secret
"""
import asyncio, hashlib, httpx, json, os, re, time, logging
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
log = logging.getLogger(__name__)

API_URL    = "https://eco.taobao.com/router/rest"
APP_KEY    = os.environ.get("TAOBAO_APP_KEY", "")
APP_SECRET = os.environ.get("TAOBAO_APP_SECRET", "")
CNY_TO_TWD = 4.42   # 每日更新，先固定

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ── 簽名 ──────────────────────────────────────────────────────────────────────
def _sign(params: dict, secret: str) -> str:
    """secret + sorted(key+value) + secret → MD5 大寫"""
    raw = secret + "".join(f"{k}{v}" for k, v in sorted(params.items())) + secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def _build(method: str, extra: dict) -> dict:
    p = {
        "method":      method,
        "app_key":     APP_KEY,
        "format":      "json",
        "v":           "2.0",
        "sign_method": "md5",
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    p.update(extra)
    p["sign"] = _sign(p, APP_SECRET)
    return p


# ── API 1: taobao.tbk.item.info.get ──────────────────────────────────────────
async def get_item_info(num_iids: list[str]) -> list[dict]:
    """
    輸入: 商品ID清單（最多40個）
    輸出: [{num_iid, title, price_cny, reserve_price, volume, shop, url, image}]
    """
    if not num_iids:
        return []

    params = _build("taobao.tbk.item.info.get", {
        "num_iids": ",".join(num_iids[:40]),
        "platform": "2",        # 1=PC, 2=無線（手機）
    })

    async with httpx.AsyncClient(timeout=15) as cli:
        r = await cli.post(API_URL, data=params)

    data = r.json()
    if "error_response" in data:
        err = data["error_response"]
        log.error(f"[item.info.get] code={err.get('code')} {err.get('sub_msg') or err.get('msg')}")
        return []

    items_raw = (data
        .get("tbk_item_info_get_response", {})
        .get("results", {})
        .get("n_tbk_item", []))

    results = []
    for item in items_raw:
        price_cny = float(item.get("zk_final_price") or item.get("reserve_price") or 0)
        ori_cny   = float(item.get("reserve_price") or price_cny)
        results.append({
            "source":        "taobao",
            "item_id":       str(item.get("num_iid", "")),
            "name":          item.get("title", ""),
            "shop":          item.get("nick", ""),
            "category":      item.get("cat_name", ""),
            "price_cny":     price_cny,
            "original_cny":  ori_cny,
            "price_twd":     round(price_cny * CNY_TO_TWD),
            "sales":         int(item.get("volume") or 0),
            "image_url":     "https:" + (item.get("pict_url") or "").lstrip(":"),
            "url":           item.get("item_url") or f"https://item.taobao.com/item.htm?id={item.get('num_iid','')}",
            "free_ship":     item.get("free_shipment", False),
            "provcity":      item.get("provcity", ""),
        })
    return results


# ── API 2: taobao.tbk.shop.get ────────────────────────────────────────────────
async def search_shops(keyword: str, page: int = 1, page_size: int = 20) -> list[dict]:
    """
    關鍵字搜索店鋪
    輸出: [{seller_nick, shop_title, shop_type, shop_url, pict_url, user_id}]
    """
    params = _build("taobao.tbk.shop.get", {
        "q":         keyword,
        "page_no":   str(page),
        "page_size": str(page_size),
        "fields":    "user_id,shop_title,shop_type,seller_nick,pict_url,shop_url",
        "platform":  "2",
        "sort":      "total_auction_des",   # 依商品數量降序
    })

    async with httpx.AsyncClient(timeout=15) as cli:
        r = await cli.post(API_URL, data=params)

    data = r.json()
    if "error_response" in data:
        err = data["error_response"]
        log.error(f"[shop.get] code={err.get('code')} {err.get('sub_msg') or err.get('msg')}")
        return []

    shops_raw = (data
        .get("tbk_shop_get_response", {})
        .get("results", {})
        .get("n_tbk_shop", []))

    return [{
        "user_id":    str(s.get("user_id", "")),
        "shop_title": s.get("shop_title", ""),
        "shop_type":  s.get("shop_type", ""),  # B=天猫, C=淘宝
        "seller_nick":s.get("seller_nick", ""),
        "shop_url":   s.get("shop_url", ""),
        "pict_url":   s.get("pict_url", ""),
    } for s in shops_raw]


# ── 搜尋頁抓商品ID（無需授權，補足關鍵字→ID缺口）─────────────────────────────
async def get_item_ids_from_search(keyword: str, max_ids: int = 40) -> list[str]:
    """
    淘寶搜尋頁抓商品ID（解決「關鍵字→商品ID」的缺口）
    不需 API key，直接從搜尋結果頁 HTML 解析
    """
    url = f"https://s.taobao.com/search?q={keyword}&sort=sale-desc&style=list"
    async with httpx.AsyncClient(headers=HEADERS, timeout=12, follow_redirects=True) as cli:
        r = await cli.get(url)

    # 多種 pattern 抓 ID
    patterns = [
        r'"nid"\s*:\s*"(\d{10,})"',
        r'"item_id"\s*:\s*"?(\d{10,})"?',
        r'id=(\d{10,})[&"\'&]',
        r'taobao\.com/item\.htm\?id=(\d{10,})',
        r'"num_iid"\s*:\s*"?(\d{10,})"?',
    ]
    ids = set()
    for p in patterns:
        found = re.findall(p, r.text)
        ids.update(found)
        if len(ids) >= max_ids:
            break

    return list(ids)[:max_ids]


# ── 核心：關鍵字 → 完整商品資料 ───────────────────────────────────────────────
async def search_products_by_keyword(keyword: str, max_items: int = 40) -> list[dict]:
    """
    主入口：關鍵字 → 淘寶商品清單（含價格/銷量/圖片）

    流程：
      1. 從搜尋頁抓商品ID（無需授權）
      2. 用 taobao.tbk.item.info.get 查詢完整資料（需 app_key）
    """
    log.info(f"搜尋 [{keyword}] ...")

    # Step 1: 取得商品 ID
    ids = await get_item_ids_from_search(keyword, max_items)
    log.info(f"  從搜尋頁抓到 {len(ids)} 個商品ID")

    if not ids:
        return []

    # Step 2: 用 API 查詳情
    products = await get_item_info(ids)
    log.info(f"  API 回傳 {len(products)} 筆商品資料")

    return products


# ── 寫入 PostgreSQL ───────────────────────────────────────────────────────────
def store(products: list[dict]) -> int:
    if not products:
        return 0
    import psycopg2, psycopg2.extras
    dsn = os.environ.get("ALFRED_PG_DSN",
                         "host=localhost dbname=alfred_products user=alfred password=alfred_pw")
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, """
                INSERT INTO taobao_products
                    (item_id, name, shop_title, price_cny, original_cny,
                     price_twd, sales, image_url, url, category, updated_at)
                VALUES (%(item_id)s, %(name)s, %(shop)s, %(price_cny)s,
                        %(original_cny)s, %(price_twd)s, %(sales)s,
                        %(image_url)s, %(url)s, %(category)s, NOW())
                ON CONFLICT(item_id) DO UPDATE SET
                    price_cny  = EXCLUDED.price_cny,
                    price_twd  = EXCLUDED.price_twd,
                    sales      = EXCLUDED.sales,
                    updated_at = NOW()
            """, products)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(products)


# ── 比價：台灣 vs 淘寶 ────────────────────────────────────────────────────────
def compare(tw_name: str, tw_price: int) -> dict:
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(os.environ.get("ALFRED_PG_DSN",
        "host=localhost dbname=alfred_products user=alfred password=alfred_pw"))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT item_id, name, price_cny, price_twd, sales, url
        FROM taobao_products
        WHERE search_vector @@ plainto_tsquery('simple', %s)
          AND price_twd > 0
        ORDER BY price_twd ASC LIMIT 3
    """, (tw_name,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {"status": "no_match"}

    tb = rows[0]
    markup = round(tw_price / tb["price_twd"], 1) if tb["price_twd"] else 0
    return {
        "status":       "found",
        "tw_name":      tw_name,
        "tw_price":     tw_price,
        "tb_name":      tb["name"],
        "tb_price_cny": float(tb["price_cny"]),
        "tb_price_twd": tb["price_twd"],
        "tb_sales":     tb["sales"],
        "tb_url":       tb["url"],
        "markup":       markup,
        "verdict": (
            "正常（含運費稅金）"    if markup <= 2   else
            "⚠️ 高度溢價"          if markup <= 5   else
            "🚨 嚴重溢價 — 可能是仿品高價賣"
        ),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
async def _main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", nargs="+",
        default=["藍牙耳機", "掃地機器人", "氣炸鍋", "機械鍵盤", "空氣清淨機"])
    parser.add_argument("--test-ids", nargs="*", help="直接測試指定商品ID")
    args = parser.parse_args()

    if not APP_KEY:
        print("❌ 未設定 TAOBAO_APP_KEY / TAOBAO_APP_SECRET")
        print("   export TAOBAO_APP_KEY=你的key")
        print("   export TAOBAO_APP_SECRET=你的secret")
        return

    # 測試模式：直接用商品ID
    if args.test_ids:
        print(f"測試 {len(args.test_ids)} 個商品ID ...")
        products = await get_item_info(args.test_ids)
        for p in products:
            print(f"  ¥{p['price_cny']} (NT${p['price_twd']:,}) 銷量:{p['sales']:,} | {p['name'][:50]}")
        return

    # 正常模式：關鍵字搜尋
    all_products = []
    for kw in args.keywords:
        products = await search_products_by_keyword(kw)
        all_products.extend(products)
        await asyncio.sleep(0.5)

    n = store(all_products)
    print(f"\n✅ 完成：{len(all_products)} 筆 → DB {n} 筆")
    print(f"匯率：¥1 = NT${CNY_TO_TWD}")
    print()

    # 印比價樣本
    if all_products:
        print("=== 價格樣本 ===")
        for p in sorted(all_products, key=lambda x: x['sales'], reverse=True)[:8]:
            print(f"  ¥{p['price_cny']:>8.1f}  NT${p['price_twd']:>6,}  銷{p['sales']:>5}  {p['name'][:40]}")


if __name__ == "__main__":
    asyncio.run(_main())
