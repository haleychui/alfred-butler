# extras/ — Scale-Up Tooling

These files are **not required to run the core engine** (`backend/indexer/` + `backend/scrapers/`).  
They are the tools built to push the index from thousands to **100,000+ products**.

---

## extras/indexer/

Tools for large-scale index building. Use these when the standard 30-minute crawler cycle isn't fast enough.

| File | What it does |
|------|-------------|
| `worker.py` | 20-agent concurrent crawler (correct version). Worker 0–13 hit Ruten pagination (up to 10,000 results per keyword), Worker 14–19 extend existing scrapers with more keywords. Run as: `python3 worker.py <worker_id 0-19>` |
| `wide_worker.py` | Breadth-first crawler (first batch). Ruten API caps at ~200 results per keyword offset, so strategy is 500+ keywords × 200 each = 100,000+. 20 workers, each handles 25 keywords. Run as: `python3 wide_worker.py <worker_id 0-19>` |
| `wide_worker2.py` | Second batch of breadth crawl (1,000+ keywords). First batch yields ~35,000 products; this adds another 65,000+ to hit the 100K target. Run as: `python3 wide_worker2.py <worker_id 0-19>` |
| `bulk_index.py` | Brute-force batch indexer. Fetches 40–60 products per keyword (vs the standard 10), expands keyword list from 200 to 2,000, runs multi-site concurrent without queuing. Target: 100,000+ in a single run. |
| `mega_crawl.py` | Pagination-based mass indexer. PChome alone yields 25,013 results per keyword across 100 pages. 20 categories × 50 pages × 3 platforms = 60,000+ per run. |
| `migrate_to_pg.py` | One-time migration: SQLite → PostgreSQL. Also seeds the first `price_history` row for every product. Run once when scaling to multi-user or high-write workloads. |
| `pg_schema.sql` | PostgreSQL schema. Adds what SQLite FTS5 can't do: `price_history` table (full price change tracking), JSONB extension fields, native `tsvector` full-text search with GIN index. Use this when you need price history or multi-instance deployments. |
| `auto_crawl.sh` | Daily auto-crawl script. Launches all 20 `wide_worker.py` workers in parallel, logs to `/opt/alfred/logs/auto_crawl_YYYYMMDD.log`. Drop into cron for fully autonomous index updates: `0 3 * * * /opt/alfred/extras/indexer/auto_crawl.sh` |

### When to use these

| Scenario | Tool |
|----------|------|
| First time building a large index | `bulk_index.py` then `wide_worker.py` × 20 |
| Daily autonomous updates | `auto_crawl.sh` via cron |
| Need price history tracking | `pg_schema.sql` + `migrate_to_pg.py` |
| Index stale, need full rebuild fast | `mega_crawl.py` |

---

## extras/scrapers/

Scrapers for non-standard platforms — experimental or requires extra setup.

| File | What it does |
|------|-------------|
| `crowdfunding_scraper.py` | **Leading indicator crawler** for wabay + flyingV (Taiwan crowdfunding platforms). Products with high funding multiples tend to appear on momo/pchome/Taobao 3–12 months later. Use this to predict trending products before they hit mainstream e-commerce. |
| `taobao_scraper.py` | Taobao price + sales data via three paths: (1) `taobao.tbk.item.info.get` — product ID → price/sales/title, (2) `taobao.tbk.shop.get` — keyword → shop list, (3) search page scrape for product IDs (no auth required). Requires env vars: `TAOBAO_APP_KEY`, `TAOBAO_APP_SECRET`. |

---

## Quick Start (scale up from scratch)

```bash
# Step 1: initialise DB
python3 backend/indexer/search.py --init

# Step 2: run 20 wide workers in parallel
for i in $(seq 0 19); do
  python3 extras/indexer/wide_worker.py $i &
done
wait
echo "Done. Check product count:"
sqlite3 data/product_index.db "SELECT COUNT(*) FROM products WHERE is_active=1"

# Step 3: set up daily auto-update
echo "0 3 * * * /opt/alfred/extras/indexer/auto_crawl.sh" | crontab -
```
