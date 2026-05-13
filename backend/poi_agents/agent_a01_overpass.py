#!/usr/bin/env python3
"""POI Crack Agent A01 — OpenStreetMap Overpass

策略:對台灣分 5 個 bbox 區塊跑 Overpass,各拉 amenity=restaurant 餐廳。
每個區塊 ~10-30 秒,total ~2-3 分鐘。

之後 A02+ 派去 Foodpanda / 食記 / Google Maps 等補 phone/hours/rating。

Schema(pois 表):
  osm_id (UNIQUE) — dedup on re-runs
  amenity, name, name_en, name_zh, cuisine, brand
  phone, hours, addr, city, district
  lat, lng (必須)
  rating, tags, source('osm'), source_url, updated_at
"""
import urllib.request, urllib.parse, json, time, sqlite3, sys
from datetime import datetime

DB = "/opt/alfred/data/alfred.db"
ENDPOINT = "https://overpass-api.de/api/interpreter"
UA = "Alfred-POI-Crack/1.0 (alfred@charenix.com)"

# 5 個 bbox 區塊 cover 全台(+ 主要離島)
# (south, west, north, east, label)
REGIONS = [
    (24.85, 120.85, 25.40, 122.05, "北部(雙北基桃竹苗北)"),
    (23.80, 120.10, 24.85, 121.50, "中部(苗台彰投雲)"),
    (22.40, 120.05, 23.80, 121.10, "南部(嘉南高屏)"),
    (22.50, 121.10, 25.05, 122.05, "東部(宜花東)"),
    (21.85, 120.65, 22.50, 121.10, "離島東南(墾丁綠島蘭嶼)"),
]


def fetch_region(south, west, north, east, label):
    q = (
        f"[out:json][timeout:120];"
        f"(node[amenity=restaurant]({south},{west},{north},{east});"
        f" way[amenity=restaurant]({south},{west},{north},{east}););"
        f"out center tags;"
    )
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        body = r.read()
    j = json.loads(body)
    els = j.get("elements", [])
    print(f"  [{label}] {len(els):>5d} restaurants in {time.time()-t0:>4.0f}s "
          f"(payload {len(body)//1024:>4d} KB)")
    return els


def normalize(el):
    """OSM element → pois row dict."""
    tags = el.get("tags", {})
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lng = el.get("lon") or el.get("center", {}).get("lon")
    if lat is None or lng is None:
        return None

    osm_id = el.get("id")
    if not osm_id:
        return None

    name = tags.get("name") or tags.get("name:zh") or tags.get("name:en")
    if not name:
        return None  # 沒名字 skip

    addr_parts = [
        tags.get("addr:postcode", ""),
        tags.get("addr:city", ""),
        tags.get("addr:district", ""),
        tags.get("addr:street", ""),
        tags.get("addr:housenumber", ""),
    ]
    addr = "".join(p for p in addr_parts if p) or tags.get("addr:full", "")

    extra_tags = []
    if tags.get("wheelchair") == "yes":
        extra_tags.append("無障礙")
    if tags.get("outdoor_seating") == "yes":
        extra_tags.append("戶外座位")
    if tags.get("wifi") == "yes" or tags.get("internet_access") == "wlan":
        extra_tags.append("wifi")
    if tags.get("smoking") == "no":
        extra_tags.append("禁菸")
    if "24/7" in (tags.get("opening_hours") or ""):
        extra_tags.append("24h")

    return {
        "osm_id": osm_id,
        "amenity": "restaurant",
        "name": name,
        "name_en": tags.get("name:en"),
        "name_zh": tags.get("name:zh"),
        "cuisine": tags.get("cuisine"),
        "brand": tags.get("brand"),
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "hours": tags.get("opening_hours"),
        "addr": addr,
        "city": tags.get("addr:city"),
        "district": tags.get("addr:district"),
        "lat": float(lat),
        "lng": float(lng),
        "rating": None,
        "tags": ",".join(extra_tags) if extra_tags else None,
        "source": "osm",
        "source_url": f"https://www.openstreetmap.org/{el.get('type','node')}/{osm_id}",
    }


def main():
    print(f"= POI Crack Agent A01 (OSM Overpass) =")
    print(f"  endpoint: {ENDPOINT}")
    print(f"  target db: {DB}")
    print(f"  regions: {len(REGIONS)}")
    print()

    all_normalized = []
    t_total = time.time()
    for region in REGIONS:
        s, w, n, e, label = region
        try:
            els = fetch_region(s, w, n, e, label)
        except Exception as ex:
            print(f"  [{label}] FAIL: {ex}")
            continue
        for el in els:
            norm = normalize(el)
            if norm:
                all_normalized.append(norm)

    print(f"\n  total fetched: {len(all_normalized)} normalized POIs")
    print(f"  total time:    {time.time()-t_total:.0f}s")

    if not all_normalized:
        print("nothing to insert")
        return

    # Dedup by osm_id(在記憶體 dedup)
    seen = set()
    unique = []
    for r in all_normalized:
        if r["osm_id"] in seen:
            continue
        seen.add(r["osm_id"])
        unique.append(r)
    print(f"  after in-memory dedup: {len(unique)}")

    # INSERT OR REPLACE (osm_id UNIQUE)
    conn = sqlite3.connect(DB, timeout=60)
    c = conn.cursor()
    now = datetime.now().isoformat()

    cols = ["osm_id", "amenity", "name", "name_en", "name_zh", "cuisine", "brand",
            "phone", "hours", "addr", "city", "district", "lat", "lng",
            "rating", "tags", "source", "source_url", "updated_at"]
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT OR REPLACE INTO pois ({','.join(cols)}) VALUES ({placeholders})"

    inserted = 0
    for r in unique:
        try:
            c.execute(sql, [
                r["osm_id"], r["amenity"], r["name"], r["name_en"], r["name_zh"],
                r["cuisine"], r["brand"], r["phone"], r["hours"], r["addr"],
                r["city"], r["district"], r["lat"], r["lng"],
                r["rating"], r["tags"], r["source"], r["source_url"], now,
            ])
            inserted += 1
        except Exception as ex:
            print(f"  INSERT fail (osm_id={r['osm_id']}): {ex}")

    conn.commit()
    conn.close()
    print(f"\n  INSERTED / REPLACED: {inserted}")
    print(f"\n  Done.")


if __name__ == "__main__":
    main()
