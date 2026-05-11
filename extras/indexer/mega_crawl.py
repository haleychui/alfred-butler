"""
indexer/mega_crawl.py — 翻頁式大量索引

PChome 單一關鍵字 25,013 筆 × 100 頁
每個類別關鍵字翻 50 頁 × 20 筆 = 1,000 筆
20 個類別 × 3 站 = 60,000 筆起跳
"""
import asyncio, httpx, sys, time, json, re, logging
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from indexer.db import init_db, upsert_products, get_stats
from indexer.query_parser import is_accessory

log = logging.getLogger("mega")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

PCHOME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://24h.pchome.com.tw/",
}
MOMO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Accept-Language": "zh-TW,zh;q=0.9",
}
COUPANG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# 類別關鍵字（每個跑 50 頁 × 20 筆 = 1,000 筆）
MEGA_KEYWORDS = [
    # 3C
    ("3c", "耳機"), ("3c", "手機"), ("3c", "筆電"), ("3c", "平板"),
    ("3c", "螢幕"), ("3c", "鍵盤"), ("3c", "滑鼠"), ("3c", "相機"),
    ("3c", "電視"), ("3c", "音響"), ("3c", "充電"), ("3c", "硬碟"),
    # 家電
    ("appliance", "氣炸鍋"), ("appliance", "吸塵器"), ("appliance", "咖啡機"),
    ("appliance", "電鍋"), ("appliance", "冷氣"), ("appliance", "洗衣機"),
    ("appliance", "電動牙刷"), ("appliance", "吹風機"), ("appliance", "烤箱"),
    # 食品
    ("food", "醬油"), ("food", "零食"), ("food", "咖啡"), ("food", "茶葉"),
    ("food", "泡麵"), ("food", "餅乾"), ("food", "巧克力"), ("food", "米"),
    # 美妝
    ("beauty", "面膜"), ("beauty", "精華液"), ("beauty", "防曬"), ("beauty", "乳液"),
    ("beauty", "洗髮精"), ("beauty", "口紅"), ("beauty", "香水"),
    # 家居
    ("home", "燈泡"), ("home", "收納"), ("home", "枕頭"), ("home", "床墊"),
    ("home", "洗碗精"), ("home", "垃圾袋"),
    # 工具
    ("tools", "電鑽"), ("tools", "螺絲起子"), ("tools", "露營"),
    # 運動
    ("sport", "瑜珈"), ("sport", "啞鈴"), ("sport", "水壺"), ("sport", "跑步機"),
    # 寵物
    ("pet", "貓砂"), ("pet", "狗飼料"), ("pet", "貓飼料"), ("pet", "寵物玩具"),
    # 書籍
    ("book", "程式設計"), ("book", "商業"), ("book", "食譜"), ("book", "小說"),
]

_PCHOME_IMG = "https://cs-b.ecimg.tw"


async def crawl_pchome_pages(keyword: str, category: str, max_pages: int = 50) -> int:
    """PChome 翻頁爬取，每頁 20 筆"""
    total = 0
    async with httpx.AsyncClient(headers=PCHOME_HEADERS, timeout=12) as client:
        for page in range(1, max_pages + 1):
            try:
                r = await client.get(
                    f"https://ecshweb.pchome.com.tw/search/v3.3/all/results"
                    f"?q={keyword}&page={page}&sort=rnk/dc"
                )
                if r.status_code != 200:
                    break
                d = r.json()
                prods = d.get("prods", [])
                if not prods:
                    break
                batch = []
                for p in prods:
                    name = p.get("name", "")
                    price = int(p.get("price", 0))
                    pid = p.get("Id", "")
                    if not price or not name or not pid:
                        continue
                    orig = int(p.get("originPrice", 0))
                    disc = round((1-price/orig)*100) if orig and orig > price else None
                    pic = p.get("picS","")
                    img = f"{_PCHOME_IMG}{pic}" if pic and not pic.startswith("http") else pic
                    batch.append({
                        "site": "pchome", "code": pid, "name": name,
                        "category": category, "price": price,
                        "list_price": orig if orig != price else None,
                        "discount_pct": disc,
                        "image_url": img,
                        "buy_url": f"https://24h.pchome.com.tw/prod/{pid}",
                        "rating": None, "review_count": None,
                        "is_accessory": 1 if is_accessory(name, keyword.split()) else 0,
                    })
                n = upsert_products(batch)
                total += n
                if page % 10 == 0:
                    log.info(f"  PChome [{keyword}] p{page} cumul={total}")
                # 最後一頁
                if page >= d.get("totalPage", 1):
                    break
                await asyncio.sleep(0.1)
            except Exception as e:
                log.warning(f"PChome [{keyword}] p{page}: {e}")
                break
    return total


async def crawl_coupang_pages(keyword: str, category: str, max_pages: int = 20) -> int:
    """酷澎翻頁爬取"""
    total = 0
    async with httpx.AsyncClient(headers=COUPANG_HEADERS, timeout=15, follow_redirects=True) as client:
        for page in range(1, max_pages + 1):
            try:
                r = await client.get(
                    f"https://www.tw.coupang.com/np/search?q={keyword}&page={page}"
                )
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "lxml")
                items = soup.select("ul#productList > li.search-product")
                if not items:
                    break
                batch = []
                for li in items:
                    if li.select_one(".search-product__ad-badge"):
                        continue
                    name_el = li.select_one(".name")
                    price_el = li.select_one("strong.price-value")
                    orig_el = li.select_one("del.base-price")
                    img_el = li.select_one("img.product-image")
                    pid = li.get("data-product-id","")
                    if not name_el or not price_el or not pid:
                        continue
                    name = name_el.get_text(strip=True)
                    price = int(re.sub(r"[^0-9]","", price_el.get_text()))
                    orig = int(re.sub(r"[^0-9]","", orig_el.get_text())) if orig_el else None
                    disc = round((1-price/orig)*100) if orig and orig > price else None
                    img = img_el.get("src","") if img_el else ""
                    batch.append({
                        "site": "coupang", "code": pid, "name": name,
                        "category": category, "price": price,
                        "list_price": orig, "discount_pct": disc,
                        "image_url": img,
                        "buy_url": f"https://www.tw.coupang.com/vp/products/{pid}",
                        "rating": None, "review_count": None,
                        "is_accessory": 1 if is_accessory(name, keyword.split()) else 0,
                    })
                n = upsert_products(batch)
                total += n
                if not items or len(items) < 10:
                    break
                await asyncio.sleep(0.2)
            except Exception as e:
                log.warning(f"Coupang [{keyword}] p{page}: {e}")
                break
    return total


async def run_mega():
    init_db()
    t0 = time.time()
    stats_before = get_stats()

    print(f"\n{'='*60}")
    print(f"MEGA CRAWL 開始 {datetime.now().strftime('%H:%M:%S')}")
    print(f"目前索引: {stats_before['total_products']:,} 筆")
    print(f"關鍵字數: {len(MEGA_KEYWORDS)} 個")
    print(f"策略: PChome 翻50頁 + 酷澎翻20頁 = 每關鍵字最多 1,400 筆")
    print(f"預估上限: {len(MEGA_KEYWORDS) * 1400:,} 筆")
    print(f"{'='*60}\n")

    # 並發執行所有關鍵字（PChome + 酷澎）
    tasks = []
    for cat, kw in MEGA_KEYWORDS:
        tasks.append(crawl_pchome_pages(kw, cat, max_pages=50))
        tasks.append(crawl_coupang_pages(kw, cat, max_pages=20))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - t0
    stats = get_stats()
    total_new = stats['total_products'] - stats_before['total_products']

    print(f"\n{'='*60}")
    print(f"完成: {datetime.now().strftime('%H:%M:%S')}")
    print(f"耗時: {elapsed:.0f}s ({elapsed/60:.1f} 分鐘)")
    print(f"索引總量: {stats['total_products']:,} 筆")
    print(f"本輪新增: {total_new:,} 筆")
    print(f"\n各站商品數:")
    for site, cnt in sorted(stats["sites"].items(), key=lambda x:-x[1]):
        bar = "█" * min(cnt//200, 50)
        print(f"  {site:15} {cnt:7,} {bar}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(run_mega())
