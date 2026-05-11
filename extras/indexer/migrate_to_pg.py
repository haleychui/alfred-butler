"""SQLite → PostgreSQL 遷移，同時建立第一筆 price_history"""
import sqlite3, psycopg2, sys
from datetime import datetime

SQLITE_PATH = "/opt/alfred/data/product_index.db"
PG_DSN = "host=localhost dbname=alfred_products user=alfred password=alfred_pw"

def migrate():
    sq = sqlite3.connect(SQLITE_PATH)
    sq.row_factory = sqlite3.Row
    pg = psycopg2.connect(PG_DSN)
    cur = pg.cursor()

    rows = sq.execute("SELECT * FROM products WHERE is_active=1").fetchall()
    print(f"遷移 {len(rows):,} 筆...")

    batch, n = [], 0
    for r in rows:
        batch.append((
            r["site"], r["code"], r["name"], r["brand"], r["category"],
            r["price"] or 0, r["list_price"], r["discount_pct"],
            r["image_url"], r["buy_url"], r["rating"], r["review_count"],
            bool(r["is_accessory"]), bool(r["is_active"]),
        ))
        if len(batch) >= 500:
            cur.executemany("""
                INSERT INTO products
                    (site,code,name,brand,category,price,list_price,discount_pct,
                     image_url,buy_url,rating,review_count,is_accessory,is_active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(site,code) DO UPDATE SET
                    price=EXCLUDED.price, name=EXCLUDED.name,
                    price_updated_at=NOW()
            """, batch)
            pg.commit()
            n += len(batch)
            print(f"  {n:,} 筆寫入...", flush=True)
            batch = []

    if batch:
        cur.executemany("""
            INSERT INTO products
                (site,code,name,brand,category,price,list_price,discount_pct,
                 image_url,buy_url,rating,review_count,is_accessory,is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(site,code) DO UPDATE SET
                price=EXCLUDED.price, name=EXCLUDED.name,
                price_updated_at=NOW()
        """, batch)
        pg.commit()
        n += len(batch)

    total = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]  # type: ignore
    history = cur.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]  # type: ignore
    print(f"\n完成：{n:,} 筆遷移")
    print(f"PG products: {total:,}")
    print(f"PG price_history（第一筆）: {history:,}")
    pg.close()
    sq.close()

if __name__ == "__main__":
    migrate()
