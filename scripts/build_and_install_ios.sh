#!/bin/bash
# Alfred iOS build + install 自動化腳本
# 用法：
#   bash ~/Documents/alfred/scripts/build_and_install_ios.sh
#
# 前提：
#   - Xcode 已裝在 /Applications/Xcode.app
#   - iPhone 已用 USB 連到 Mac 且解鎖
#   - 已信任過開發者憑證

set -e
echo "=== Alfred iOS Build & Install ==="
echo

# 0. 設 DEVELOPER_DIR
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
if [ ! -d "$DEVELOPER_DIR" ]; then
    echo "✗ Xcode not found at /Applications/Xcode.app — 請先從 App Store 裝 Xcode"
    exit 1
fi

# 0.5 切 xcode-select（first time setup）
echo "--- 切 xcode-select 到 Xcode app ---"
sudo xcode-select -s "$DEVELOPER_DIR" || true

# 0.6 接受 license（first time）
echo "--- 確認 license 已接受 ---"
sudo xcodebuild -license accept 2>&1 | head -3 || true

# 0.7 first-time install components (simulator runtime etc)
xcodebuild -runFirstLaunch 2>&1 | head -3 || true

# 1. 找連接的 iPhone
echo
echo "--- 列連接的 device ---"
DEVICE_INFO=$(xcrun devicectl list devices 2>&1)
echo "$DEVICE_INFO"

# 從 list 抓 connected + iPhone 的 device id
DEVICE_ID=$(xcrun devicectl list devices 2>&1 | grep -i "iPhone" | grep -iE "available|connected" | head -1 | awk -F'\\s{2,}' '{for(i=1;i<=NF;i++) if($i ~ /^[A-F0-9]{8}-/) print $i; for(i=1;i<=NF;i++) if($i ~ /^[A-F0-9]{40}$/) print $i; for(i=1;i<=NF;i++) if($i ~ /^[0-9A-F-]{25,}$/) print $i}' | head -1)

if [ -z "$DEVICE_ID" ]; then
    echo
    echo "✗ 找不到連接的 iPhone。請確認："
    echo "  1. iPhone 已用 USB 連到 Mac"
    echo "  2. iPhone 已解鎖 + 信任這台 Mac"
    echo "  3. 從 Finder 側欄看得到 iPhone"
    echo
    echo "拿到 device id 後手動執行："
    echo "  bash $0 <device-id>"
    exit 1
fi

# 也接受 device-id 作為 $1 覆寫
DEVICE_ID="${1:-$DEVICE_ID}"
echo "device id: $DEVICE_ID"

# 2. xcodebuild
echo
echo "--- xcodebuild Debug for iOS ---"
cd ~/Documents/alfred
xcodebuild \
    -project Alfred.xcodeproj \
    -scheme Alfred \
    -destination 'generic/platform=iOS' \
    -configuration Debug \
    build 2>&1 | tail -30

# 找 .app 路徑
APP_PATH=$(ls -td ~/Library/Developer/Xcode/DerivedData/Alfred-*/Build/Products/Debug-iphoneos/Alfred.app 2>/dev/null | head -1)
if [ ! -d "$APP_PATH" ]; then
    echo "✗ 沒找到 build 完的 Alfred.app（DerivedData 內找不到）"
    exit 1
fi
echo "✓ Build OK: $APP_PATH"

# 3. install
echo
echo "--- install 到 iPhone ($DEVICE_ID) ---"
xcrun devicectl device install app --device "$DEVICE_ID" "$APP_PATH"

echo
echo "=== ✓ DONE ==="
echo "iPhone 上應該已經有新版 Alfred app，請開啟測試"
echo "TTS 雜音應該已修復（AudioEngine 三個 player 統一 AVAudioSession 設定）"
