#!/usr/bin/env python3
import json, statistics, sys
from collections import defaultdict

with open(sys.argv[1]) as f:
    data = json.load(f)
results = data["results"]

cat_stats = defaultdict(lambda: {"total":0, "ok":0, "fail":0, "latencies":[]})
for r in results:
    s = cat_stats[r["cat"]]
    s["total"] += 1
    if r["ok"]:
        s["ok"] += 1
        s["latencies"].append(r["latency_ms"])
    else:
        s["fail"] += 1

print("=== 各類通過率 + 延遲 ===")
print("{:<10} {:>4} {:>4} {:>4} {:>8} {:>8} {:>8} {:>8}".format(
    "category", "total", "ok", "fail", "pass%", "p50", "p95", "max"))
for cat, s in cat_stats.items():
    rate = s["ok"]/s["total"]*100
    lat = s["latencies"]
    p50 = int(statistics.median(lat)) if lat else 0
    idx95 = max(0, int(len(lat)*0.95)-1)
    p95 = sorted(lat)[idx95] if lat else 0
    mx = max(lat) if lat else 0
    print("{:<10} {:>4} {:>4} {:>4} {:>7.1f}% {:>6}ms {:>6}ms {:>6}ms".format(
        cat, s["total"], s["ok"], s["fail"], rate, p50, p95, mx))

print()
print("=== 失敗詳情 ===")
for r in results:
    if not r["ok"]:
        print("#{} [{}] {}".format(r["i"], r["cat"], r["prompt"]))
        print("   latency={}ms len={} status={}".format(
            r["latency_ms"], r["response_len"], r.get("status_code","?")))
        if r.get("error"):
            print("   error: " + r["error"][:200])
        if r.get("response_preview"):
            print("   preview: " + r["response_preview"][:200])
        print()

print("=== 整體 ===")
all_lat = [r["latency_ms"] for r in results if r["ok"]]
ok_count = sum(1 for r in results if r["ok"])
print("總: {} | OK: {} | FAIL: {} | 通過率: {:.1f}%".format(
    len(results), ok_count, len(results)-ok_count, ok_count/len(results)*100))
print("延遲：mean={}ms p50={}ms p95={}ms max={}ms min={}ms".format(
    int(statistics.mean(all_lat)),
    int(statistics.median(all_lat)),
    sorted(all_lat)[max(0, int(len(all_lat)*0.95)-1)],
    max(all_lat), min(all_lat)))

print()
print("=== 最慢 5 ===")
for r in sorted([r for r in results if r["ok"]], key=lambda x: -x["latency_ms"])[:5]:
    print("  #{} [{}] {} -> {}ms".format(r["i"], r["cat"], r["prompt"][:55], r["latency_ms"]))

print()
print("=== 最快 5 ===")
for r in sorted([r for r in results if r["ok"]], key=lambda x: x["latency_ms"])[:5]:
    print("  #{} [{}] {} -> {}ms".format(r["i"], r["cat"], r["prompt"][:55], r["latency_ms"]))

print()
print("=== response 長度分布 ===")
lens = [r["response_len"] for r in results if r["ok"]]
print("mean={} median={} max={} | 短回應(<20 chars): {}".format(
    int(statistics.mean(lens)), int(statistics.median(lens)), max(lens),
    len([x for x in lens if x<20])))
short = [r for r in results if r["ok"] and r["response_len"] < 20]
for r in short[:5]:
    print("  #{} [{}] {} -> '{}'".format(
        r["i"], r["cat"], r["prompt"][:40], r["response_preview"]))
