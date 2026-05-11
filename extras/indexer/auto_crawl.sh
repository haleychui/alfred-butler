#!/bin/bash
# Alfred 自動索引爬蟲 — 每天自動跑，不需要人介入
# Agent 的工作，不是 Claude 的工作

LOGFILE="/opt/alfred/logs/auto_crawl_$(date +%Y%m%d).log"
mkdir -p /opt/alfred/logs

echo "[$(date)] AUTO CRAWL START" >> "$LOGFILE"

cd /opt/alfred/backend

# 20 Workers 並發
for i in $(seq 0 19); do
  python3 indexer/wide_worker.py $i >> "$LOGFILE" 2>&1 &
done
wait

for i in $(seq 0 19); do
  python3 indexer/wide_worker2.py $i >> "$LOGFILE" 2>&1 &
done
wait

# 統計
python3 -c "
import sys; sys.path.insert(0, '/opt/alfred/backend')
from indexer.db import get_stats
s = get_stats()
print(f'[AUTO] 完成 總計: {s[\"total_products\"]:,} 筆 ruten: {s[\"sites\"].get(\"ruten\",0):,}')
" >> "$LOGFILE" 2>&1

echo "[$(date)] AUTO CRAWL DONE" >> "$LOGFILE"
