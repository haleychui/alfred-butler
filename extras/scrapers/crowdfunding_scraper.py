"""
scrapers/crowdfunding_scraper.py

領先指標爬蟲：wabay + flyingV
高募資倍數的產品 → 3-12 個月後出現在 momo/pchome/淘寶
"""
import asyncio, httpx, re, json, logging
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept": "text/html,*/*",
}

# ── wabay (挖貝) ───────────────────────────────────────────────────────────────
WABAY_CATEGORIES = {
    "33": "運動", "28": "文化", "38": "影視", "41": "空間",
    "49": "身心靈", "27": "公益", "32": "議題", "48": "飲食",
    "34": "出版", "30": "地方創生", "29": "環境保育", "31": "動物",
}

async def scrape_wabay(client: httpx.AsyncClient) -> list[dict]:
    results = []
    # 抓所有分類 + 主頁
    urls = ["https://wabay.tw/projects?locale=zh-TW&filter=all"]
    for cat_id in WABAY_CATEGORIES:
        urls.append(f"https://wabay.tw/projects?category_id={cat_id}&locale=zh-TW")

    seen_slugs = set()
    for url in urls:
        try:
            r = await client.get(url, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            for article in soup.find_all("article"):
                proj = _parse_wabay_card(article)
                if proj and proj["slug"] not in seen_slugs:
                    seen_slugs.add(proj["slug"])
                    results.append(proj)

            await asyncio.sleep(0.5)
        except Exception as e:
            log.warning(f"wabay {url}: {e}")

    log.info(f"wabay: {len(results)} projects")
    return results


def _parse_wabay_card(article) -> dict | None:
    a = article.find("a", href=re.compile(r"/projects/"))
    if not a:
        return None

    href = a.get("href", "")
    slug = href.split("/projects/")[1].split("?")[0]
    title = a.get("title") or a.get_text(strip=True)
    if not title or len(title) < 4:
        return None

    # 募資進度
    pct_tag = article.find(title=re.compile(r"集資進度"))
    funded_pct = None
    if pct_tag:
        m = re.search(r"(\d+)%", pct_tag.get("title", ""))
        if m:
            funded_pct = int(m.group(1))

    # 文字節點：倒數天數、標籤
    texts = [t.strip() for t in article.stripped_strings]
    days_left = None
    tags = []
    for t in texts:
        m = re.match(r"倒數\s*(\d+)\s*天", t)
        if m:
            days_left = int(m.group(1))
        if t.startswith("#"):
            tags.append(t.lstrip("#"))

    img = article.find("img")

    return {
        "platform": "wabay",
        "slug": slug,
        "title": title,
        "category": tags[0] if tags else None,
        "tags": tags,
        "funded_pct": funded_pct,
        "days_left": days_left,
        "image_url": img.get("src", "") if img else "",
        "project_url": f"https://wabay.tw/projects/{slug}",
    }


# ── flyingV ───────────────────────────────────────────────────────────────────
FLYINGV_CATEGORIES = ["product", "life", "music", "art", "community", "publishing"]

async def scrape_flyingv(client: httpx.AsyncClient) -> list[dict]:
    results = []
    seen = set()

    for cat in FLYINGV_CATEGORIES:
        for page in range(1, 5):   # 最多 4 頁
            url = f"https://www.flyingv.cc/projects?category={cat}&page={page}"
            try:
                r = await client.get(url, timeout=12)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                cards = _parse_flyingv_page(soup, cat)
                if not cards:
                    break
                new = [c for c in cards if c["slug"] not in seen]
                if not new:
                    break
                for c in new:
                    seen.add(c["slug"])
                    results.append(c)
                await asyncio.sleep(0.4)
            except Exception as e:
                log.warning(f"flyingV {url}: {e}")
                break

    log.info(f"flyingV: {len(results)} projects")
    return results


def _parse_flyingv_page(soup, category: str) -> list[dict]:
    projects = []

    # flyingV 專案卡片
    for card in soup.find_all(["div", "article"], class_=re.compile(r"project|card", re.I)):
        a = card.find("a", href=re.compile(r"/projects/\d+"))
        if not a:
            continue

        href = a.get("href", "")
        m = re.search(r"/projects/(\d+)", href)
        if not m:
            continue
        slug = m.group(1)

        # 標題
        title_tag = card.find(["h2", "h3", "p"], class_=re.compile(r"title|name", re.I))
        title = (title_tag.get_text(strip=True) if title_tag
                 else card.get_text(separator=" ", strip=True)[:60])

        # 進度百分比
        pct_tag = card.find(class_=re.compile(r"percent|progress|funded", re.I))
        funded_pct = None
        if pct_tag:
            m2 = re.search(r"(\d+)", pct_tag.get_text())
            if m2:
                funded_pct = int(m2.group(1))

        # 從文字找百分比
        if funded_pct is None:
            all_text = card.get_text()
            m3 = re.search(r"(\d+)\s*%", all_text)
            if m3:
                funded_pct = int(m3.group(1))

        # 金額
        amounts = re.findall(r"NT\$\s*([\d,]+)", card.get_text())

        # 天數
        days_m = re.search(r"(\d+)\s*天", card.get_text())
        days_left = int(days_m.group(1)) if days_m else None

        img = card.find("img")

        if len(title) > 3:
            projects.append({
                "platform": "flyingv",
                "slug": slug,
                "title": title,
                "category": category,
                "tags": [category],
                "funded_pct": funded_pct,
                "days_left": days_left,
                "min_price": int(amounts[0].replace(",", "")) if amounts else None,
                "image_url": img.get("src", "") if img else "",
                "project_url": f"https://www.flyingv.cc/projects/{slug}",
            })

    return projects


# ── 寫入 PostgreSQL ───────────────────────────────────────────────────────────
def upsert_crowdfunding(projects: list[dict]) -> int:
    if not projects:
        return 0
    import psycopg2, psycopg2.extras, os
    dsn = os.environ.get("ALFRED_PG_DSN",
                         "host=localhost dbname=alfred_products user=alfred password=alfred_pw")
    conn = psycopg2.connect(dsn)
    n = 0
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, """
                INSERT INTO crowdfunding_projects
                    (platform, slug, title, category, funded_pct,
                     days_left, min_price, image_url, project_url, tags,
                     last_updated_at)
                VALUES (%(platform)s, %(slug)s, %(title)s, %(category)s,
                        %(funded_pct)s, %(days_left)s, %(min_price)s,
                        %(image_url)s, %(project_url)s, %(tags)s, NOW())
                ON CONFLICT(platform, slug) DO UPDATE SET
                    funded_pct      = EXCLUDED.funded_pct,
                    days_left       = EXCLUDED.days_left,
                    min_price       = EXCLUDED.min_price,
                    last_updated_at = NOW(),
                    status = CASE
                        WHEN EXCLUDED.days_left = 0 THEN 'ended'
                        WHEN EXCLUDED.funded_pct >= 100 THEN 'successful'
                        ELSE 'active'
                    END
            """, [{
                "platform":  p["platform"],
                "slug":      p["slug"],
                "title":     p["title"],
                "category":  p.get("category"),
                "funded_pct": p.get("funded_pct"),
                "days_left": p.get("days_left"),
                "min_price": p.get("min_price"),
                "image_url": p.get("image_url", ""),
                "project_url": p["project_url"],
                "tags":      p.get("tags", []),
            } for p in projects])
            n = len(projects)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
    return n


async def run_all() -> dict:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        wabay = await scrape_wabay(client)
        flyingv = await scrape_flyingv(client)

    all_projects = wabay + flyingv
    n = upsert_crowdfunding(all_projects)

    return {
        "wabay": len(wabay),
        "flyingv": len(flyingv),
        "total_upserted": n,
        "hot_200pct_plus": len([p for p in all_projects if (p.get("funded_pct") or 0) >= 200]),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = asyncio.run(run_all())
    print(f"\n=== 群募爬蟲完成 ===")
    print(f"wabay:   {result['wabay']} 個專案")
    print(f"flyingV: {result['flyingv']} 個專案")
    print(f"寫入 DB: {result['total_upserted']} 筆")
    print(f"200%+ 爆款: {result['hot_200pct_plus']} 個 ← 這些是領先指標")

    # 印出爆款清單
    import psycopg2, os
    conn = psycopg2.connect(os.environ.get("ALFRED_PG_DSN",
        "host=localhost dbname=alfred_products user=alfred password=alfred_pw"))
    cur = conn.cursor()
    cur.execute("""
        SELECT platform, funded_pct, title, days_left, min_price
        FROM hot_crowdfunding ORDER BY funded_pct DESC LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()
    if rows:
        print(f"\n🔥 爆款領先指標清單（200%+）：")
        for row in rows:
            platform, pct, title, days, price = row
            price_str = f"NT${price:,}" if price else "?"
            days_str = f"剩 {days}天" if days else "已結束"
            print(f"  [{platform}] {pct}% | {title[:45]} | {price_str} | {days_str}")
