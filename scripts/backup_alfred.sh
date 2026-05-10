#!/bin/bash
# Alfred 每日 DB 備份
# 設計：保留 7 天，老的自動清除；alfred.db 用 sqlite3 .backup（在線安全）
# 若 .backup 失敗則 fallback 短暫停 service
set -e
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/opt/alfred/backups
mkdir -p "$BACKUP_DIR"

# 1. alfred.db (主 DB) - 先試 .backup（在線）
if sqlite3 /opt/alfred/data/alfred.db ".backup $BACKUP_DIR/alfred_${TS}.db" 2>/dev/null; then
  echo "[$(date)] alfred.db online backup OK"
else
  # fallback: 停 service 1 秒做 cp
  echo "[$(date)] online backup locked, fallback to cold copy"
  systemctl stop alfred
  sleep 1
  cp /opt/alfred/data/alfred.db "$BACKUP_DIR/alfred_${TS}.db"
  sync
  systemctl start alfred
  echo "[$(date)] cold backup OK, service restarted"
fi

# 2. auth.db
sqlite3 /opt/alfred/data/auth.db ".backup $BACKUP_DIR/auth_${TS}.db" 2>/dev/null \
  || cp /opt/alfred/data/auth.db "$BACKUP_DIR/auth_${TS}.db"

# 3. users/ (per-user DBs) - tar.gz 壓縮
tar czf "$BACKUP_DIR/users_${TS}.tar.gz" -C /opt/alfred/data users 2>/dev/null

# 4. 完整性驗證
INTEGRITY=$(sqlite3 -readonly "$BACKUP_DIR/alfred_${TS}.db" "PRAGMA integrity_check;" 2>&1 | head -1)
if [ "$INTEGRITY" != "ok" ]; then
  echo "[$(date)] WARNING: alfred backup integrity = $INTEGRITY"
fi

# 5. 清掉 7 天前的備份
find "$BACKUP_DIR" -name "alfred_*.db" -mtime +7 -delete 2>/dev/null
find "$BACKUP_DIR" -name "auth_*.db" -mtime +7 -delete 2>/dev/null
find "$BACKUP_DIR" -name "users_*.tar.gz" -mtime +7 -delete 2>/dev/null

# 6. 寫 log
echo "[$(date)] backup OK: alfred=$(ls -la $BACKUP_DIR/alfred_${TS}.db | awk '{print $5}') auth=$(ls -la $BACKUP_DIR/auth_${TS}.db 2>/dev/null | awk '{print $5}') users=$(ls -la $BACKUP_DIR/users_${TS}.tar.gz 2>/dev/null | awk '{print $5}')" >> /var/log/alfred_backup.log
