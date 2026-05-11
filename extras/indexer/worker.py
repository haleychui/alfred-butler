"""
indexer/worker.py — 20-Agent 並發爬蟲（正確版）
用法: python3 worker.py <worker_id 0-19>

架構：
  - Worker 0-13: Ruten 翻頁（search v4 + items v2，每關鍵字最多 10,000 筆）
  - Worker 14-17: 現有 scrapers（momo/pchome/coupang/yahoo）擴充關鍵字
  - Worker 18-19: 現有 scrapers（carrefour/etmall/books/trplus 等）
"""
import asyncio, httpx, sys, time, logging
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent))
from indexer.db import upsert_products, init_db

logging.basicConfig(level=logging.WARNING)  # 關掉 httpx debug

RUTEN_SEARCH = "https://rtapi.ruten.com.tw/api/search/v4/index.php/core/prod"
RUTEN_ITEMS  = "https://rapi.ruten.com.tw/api/items/v2/list"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.ruten.com.tw/",
}
PRICE_MAX = 9_000_000


async def crawl_ruten_paged(keyword: str, category: str, worker_id: int) -> int:
    """Ruten 翻頁爬蟲：search v4 取 ID → items v2 取詳情，offset 100-9900"""
    total = 0
    async with httpx.AsyncClient(headers=HEADERS, timeout=15) as cli:
        for start in range(100, 10001, 100):
            try:
                # Step 1: 搜尋取 ID
                r1 = await cli.get(
                    f"{RUTEN_SEARCH}?q={quote(keyword)}&limit=100&sort=prc%2Fac&start={start}"
                )
                if r1.status_code != 200:
                    break
                rows = r1.json().get("Rows", [])
                if not rows:
                    break
                ids = [row["Id"] for row in rows if row.get("Id")]
                if not ids:
                    break

                # Step 2: 批次取詳情
                r2 = await cli.get(RUTEN_ITEMS, params={"gno": ",".join(ids)})
                if r2.status_code != 200:
                    await asyncio.sleep(2)
                    continue
                items = r2.json().get("data", [])

                products = []
                for item in items:
                    if not item.get("available") or item.get("stock_status", 0) == 0:
                        continue
                    gno  = str(item.get("id", ""))
                    name = (item.get("name") or "").strip()
                    if not gno or not name:
                        continue
                    price = int(item.get("goods_price") or 0)
                    if price <= 0 or price > PRICE_MAX:
                        continue
                    ori  = int(item.get("goods_ori_price") or 0)
                    imgs = item.get("images", {}).get("url", [])
                    products.append({
                        "site":         "ruten",
                        "code":         gno,
                        "name":         name,
                        "category":     category,
                        "price":        price,
                        "list_price":   ori if ori > price else None,
                        "discount_pct": round((1 - price/ori)*100) if ori > price else None,
                        "image_url":    imgs[0] if imgs else "",
                        "buy_url":      f"https://www.ruten.com.tw/item/show?{gno}",
                    })

                added = upsert_products(products)
                total += added
                print(f"[W{worker_id}] ruten/{keyword} @{start} → {len(products)} 筆 (新增 {added}, 累計 {total})", flush=True)
                await asyncio.sleep(0.35)

            except Exception as e:
                print(f"[W{worker_id}] ERROR ruten/{keyword} @{start}: {e}", flush=True)
                await asyncio.sleep(3)
    return total


async def crawl_via_scraper(site: str, keywords: list[str], worker_id: int) -> int:
    """用現有 scrapers 擴充關鍵字廣度爬取"""
    from indexer.db import upsert_products
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    if site == "momo":
        from shop_service import search_momo as fn
    elif site == "pchome":
        from shop_service import search_pchome as fn
    elif site == "coupang":
        from scrapers.coupang_scraper import search_coupang as fn
    elif site == "yahoo":
        from scrapers.yahoo_scraper import search_yahoo_shopping as fn
    elif site == "carrefour":
        from scrapers.carrefour_scraper import search_carrefour as fn
    elif site == "etmall":
        from shop_service import search_etmall as fn
    elif site == "books":
        from scrapers.books_scraper import search_books as fn
    elif site == "trplus":
        from scrapers.trplus_scraper import search_trplus as fn
    elif site == "buy123":
        from scrapers.buy123_scraper import search_buy123 as fn
    elif site == "tkec":
        from scrapers.tkec_scraper import search_tkec as fn
    elif site == "pinkoi":
        from scrapers.pinkoi_scraper import search_pinkoi as fn
    else:
        print(f"[W{worker_id}] unknown site {site}", flush=True)
        return 0

    total = 0
    for kw in keywords:
        try:
            products = await fn(kw, limit=20)
            added = upsert_products(products)
            total += added
            print(f"[W{worker_id}] {site}/{kw} → {len(products)} 筆 (新增 {added})", flush=True)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[W{worker_id}] ERROR {site}/{kw}: {e}", flush=True)
            await asyncio.sleep(2)
    return total


# ─── 20 Worker 任務表 ─────────────────────────────────────────────────────────
# (type, keyword/site, category, worker_id)
TASKS = {
    # 露天翻頁 x14（每關鍵字最多 9,900 筆）
    0:  ("ruten", "AirPods",      "3C耳機"),
    1:  ("ruten", "藍牙耳機",      "3C耳機"),
    2:  ("ruten", "機械鍵盤",      "電腦外設"),
    3:  ("ruten", "電競滑鼠",      "電腦外設"),
    4:  ("ruten", "行動電源",      "3C周邊"),
    5:  ("ruten", "手機殼",        "手機配件"),
    6:  ("ruten", "掃地機器人",    "家電"),
    7:  ("ruten", "氣炸鍋",        "廚房家電"),
    8:  ("ruten", "智慧手錶",      "穿戴裝置"),
    9:  ("ruten", "顯示卡",        "電腦零件"),
    10: ("ruten", "SSD",           "儲存設備"),
    11: ("ruten", "LED燈",         "照明"),
    12: ("ruten", "洗髮精",        "美髮"),
    13: ("ruten", "保養品",        "美妝"),
    # 現有 scrapers × 多關鍵字
    14: ("scraper", "momo", ["AirPods Pro","藍牙耳機","機械鍵盤","電競滑鼠",
                              "掃地機器人","氣炸鍋","空氣清淨機","除濕機",
                              "智慧手錶","行動電源","iPad","Switch",
                              "電動牙刷","吹風機","咖啡機","烤箱",
                              "面膜","防曬乳","白米","狗飼料"]),
    15: ("scraper", "pchome", ["AirPods Pro","Galaxy S24","MacBook Air","ASUS筆電",
                                "iPad","Switch","PS5","電競滑鼠","機械鍵盤",
                                "掃地機器人","氣炸鍋","空氣清淨機","除濕機",
                                "電動牙刷","吹風機","咖啡機","行動電源",
                                "藍牙耳機","智慧手錶","顯示器"]),
    16: ("scraper", "coupang", ["headphone","keyboard","mouse","powerbank",
                                 "smart watch","robot vacuum","air purifier",
                                 "coffee maker","laptop","tablet"]),
    17: ("scraper", "yahoo", ["AirPods","藍牙耳機","機械鍵盤","滑鼠","行動電源",
                               "掃地機器人","氣炸鍋","除濕機","智慧手錶","iPad"]),
    18: ("scraper", "carrefour", ["洗髮精","沐浴乳","洗碗精","衛生紙","牛奶",
                                   "咖啡","茶葉","洋芋片","巧克力","餅乾",
                                   "電動牙刷","吹風機","空氣清淨機","電飯鍋","烤箱"]),
    19: ("scraper", "etmall", ["電動牙刷","氣炸鍋","掃地機器人","空氣清淨機",
                                "除濕機","吹風機","咖啡機","洗碗機",
                                "AirPods","藍牙耳機","行動電源","智慧手錶"]),
}


async def main(worker_id: int):
    init_db()
    task = TASKS.get(worker_id)
    if not task:
        print(f"[W{worker_id}] no task", flush=True)
        return

    t0 = time.time()
    kind = task[0]

    if kind == "ruten":
        _, kw, cat = task
        print(f"[W{worker_id}] START ruten/{kw}", flush=True)
        total = await crawl_ruten_paged(kw, cat, worker_id)
    elif kind == "scraper":
        _, site, keywords = task
        print(f"[W{worker_id}] START scraper/{site} ({len(keywords)} kw)", flush=True)
        total = await crawl_via_scraper(site, keywords, worker_id)
    else:
        return

    print(f"[W{worker_id}] DONE +{total} 新增 耗時 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    wid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(main(wid))
