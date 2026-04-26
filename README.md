# 阿福 Alfred

> 主人您好，我是您的全能管家。

## 核心價值

**阿福不是助理，是管家。**

- 助理 **等你問**
- 管家 **在你問之前就替你想好了**

### 設計三鐵律

1. **零介面** — 沒有選單、沒有儀表板、沒有按鈕。只有對話。介面本身就是阻力。
2. **橋梁不是代理** — 阿福不代替主人做決定，只確保人對人的關心不因忙碌而斷掉。
3. **永遠先行一步** — 不等你說「提醒我」，在你需要之前就出現。

### 阿福問的不是「怎麼讓流程更快」

市面上的工具問「怎麼讓流程更快」。阿福問：

> **哪些人對人的事情，因為忙碌被省略了？**

- 讓承諾不消失（Promise Tracker、EOD Wrap、Thanks Nudge）
- 讓主管看到看不見的（Silence Radar、Timezone Fatigue、Manager Lens、Expertise Finder）
- 讓後勤消失在背景（Room Pulse、Supply Autopilot、Guest Prep、Movement Nudge、Onboarding）

---

## 系統架構

### 後端
- **Server**: `https://YOUR_BACKEND_HOST`
- **Service**: systemd `alfred.service`（crash auto-restart，session 結束不會被 SIGHUP 殺掉）
- **Code**: `/opt/alfred/backend/main.py`（7500+ 行）
- **LLM**: Google Gemini 2.0 Flash（OpenAI-compat 介面）
- **TTS**: ElevenLabs `eleven_multilingual_v2`，VOICE_ID 用 cloned voice "Alfred 阿福"
- **STT**: OpenAI Whisper

### iOS Client
- **位置**: `~/Dropbox/Alfred/Alfred/`（Dropbox-synced）
- **Bundle ID**: `Norika.Alfred`
- **Xcode 26.4** + `PBXFileSystemSynchronizedRootGroup`（檔案放進 `Alfred/Alfred/` 自動加進 target，不用手動編 pbxproj）
- **iOS-only**（SUPPORTED_PLATFORMS 砍掉 macosx/xros）
- **iOS 26.4 Simulator** runtime

### 主要 Swift 結構
```
Alfred/Alfred/
├── AlfredApp.swift              ← @main entry，無登入畫面，直接進 AlfredView
├── Core/
│   ├── AlfredAPI.swift          ← chat/tts/transcribe + deviceLogin
│   ├── AlfredViewModel.swift    ← 對話狀態機 + onboarding mode
│   ├── AudioEngine.swift        ← AVAudioRecorder + AVAudioPlayer
│   ├── AuthManager.swift        ← (legacy) email/password JWT
│   ├── BackgroundManager.swift  ← reminder / family alert / visit polling
│   ├── ConversationLog.swift    ← 對話歷史寫到 Documents/conversation_log/
│   ├── HealthKitManager.swift   ← HealthKit permission + workout sync
│   └── LocationManager.swift    ← CLLocationManager + /api/location/update
├── Features/
│   ├── Auth/LoginView.swift     ← (legacy 不用，保留)
│   ├── Chat/AlfredView.swift    ← 主畫面：頭像 + 文字（僅 onboarding 顯示）
│   ├── Office/                  ← OfficeViewModel + OfficeDashboardView
│   ├── Family/FamilyView.swift
│   ├── Translate/TranslateView.swift
│   └── Attendance/AttendanceView.swift
└── Resources/
    ├── onboarding_greeting.mp3  ← 開機介紹（Michael Caine voice，純介紹段不含啟動語）
    └── voice_bank/              ← 469 個情境預錄 mp3（greet/ack/done/care/...）
```

---

## Onboarding 流程

### 設計原則
- **第一次開機**：阿福介紹自己 → 顯示啟動語給主人念 → 主人按頭像念啟動語 → 認證通過
- 阿福介紹用本地 mp3（離線、Michael Caine 聲音、保證不會變）
- **絕對不能讓阿福念啟動語**（旁人聽到會以為認證已完成 → 安全問題）
- 認證之前所有背景任務（BackgroundManager、HealthKit、Location）都不啟動，避免搶話

### 完整 4 步
1. App 開啟 → `AlfredApp` → `AlfredView` → `vm.onAppear()` → `vm.greet()`
2. `greet()` 偵測 `alfred_onboarded == false`：
   - 立刻 deviceLogin 拿 token
   - 設 `alfredText = "主人您好...啟動語"`（顯示）
   - 播 `Resources/onboarding_greeting.mp3`（不念啟動語）
   - state = `.idle` 等主人按頭像
3. 主人按住頭像念「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」
4. `stopListening` → STT → `sendMessage(transcript)`：
   - **`!wasOnboarded` 走 onboarding mode 不走正常 chat**（避免 `alfredText = ""` 蓋掉啟動語提示）
   - 啟動語比對通過 → set `alfred_onboarded = true` → 確認語 + 啟動 BackgroundManager / HealthKit / Location
   - 啟動語不對 → 提示重念，啟動語文字保留在畫面

---

## 後端 API

### Auth
| Endpoint | 說明 |
|---|---|
| `POST /api/auth/device` | 用 `device_id` (UUID) 換 365 天 JWT，無密碼。同 device 永遠相同 user_id (`dev_<sha256[:32]>`)，首次自動建 user_db |
| `POST /api/auth/register` | (legacy) email + password |
| `POST /api/auth/login` | (legacy) |

### Chat
- `POST /api/chat` — 一次回應（非 stream）
- `POST /api/chat/stream` — SSE，含 `delta` / `thinking` / `done`
- Response 格式：`{"text": str, "card": {...}|null, "action": {"type": "show_xxx", ...}|null}`
- **action.type fallback**：Gemini 2.0 Flash 偶爾把 tool call 當文字 emit `{"type": "show_office"}`，後端在 `chat()` return 前用 regex 抽出來放結構化 `action` field

### TTS / STT
- `POST /api/tts` body `{text}` → mp3 binary
- `POST /api/transcribe` multipart audio → `{transcript}`
- `POST /api/translate/tts` 翻譯 + 該語言 voice 念

### Office / Family / Attendance
全部需要 JWT。`OfficeDashboardView` 開啟時 call 5 個 endpoint 抓資料：
- `/api/office/eod-wrap` — 下班收尾項目清單
- `/api/office/rooms` — 會議室狀態
- `/api/office/thanks-nudge` — 待感謝
- `/api/office/supplies` — 耗材庫存
- `/api/office/colleagues` — 同事狀態

---

## 維護指南

### 後端部署
```bash
# 改 main.py 後
scp /tmp/alfred_backend/main.py root@YOUR_SERVER_IP:/opt/alfred/backend/main.py
ssh root@YOUR_SERVER_IP 'systemctl restart alfred && systemctl is-active alfred'
curl https://YOUR_BACKEND_HOST/alfred/api/greet  # 健康檢查
```

### iOS Build
```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  /Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild \
  -project ~/Dropbox/Alfred/Alfred/Alfred.xcodeproj \
  -scheme Alfred \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -configuration Debug build
```

### Simulator 啟動
```bash
SIMCTL=/Applications/Xcode.app/Contents/Developer/usr/bin/simctl
$SIMCTL boot "iPhone 17 Pro"
$SIMCTL install "iPhone 17 Pro" path/to/Alfred.app
$SIMCTL launch "iPhone 17 Pro" Norika.Alfred
```

### UI Test Mode（自動跑 prompt 不用麥克風）
Launch app 帶 `--prompt`：
```bash
$SIMCTL launch "iPhone 17 Pro" Norika.Alfred --prompt "幫我看辦公室狀況"
```
會自動 set onboarded、跳過 greet、直接 trigger sendMessage。

### Smoke Test
```bash
/usr/bin/python3 -u /tmp/alfred_smoke_test.py 10  # 10 iter × 10 prompt
```

---

## 已知限制

### Simulator
- **iOS Simulator 沒辦法 inject 麥克風 audio stream** — 所以「按住頭像錄音 → STT」必須真機或人工對 Mac 麥克風講話
- **Simulator audio session 有 bug** — 連續 audio.play 切換 `.playAndRecord` ↔ `.playback` 時音量會被削，實機正常

### Voice
- ElevenLabs cloned voice 一旦 source audio 換掉，VOICE_ID 不變但聲音會變（曾經出現「廣東話大嬸」事件）
- 解法：voice bank 預錄 469 個情境 mp3 用真正 Michael Caine voice，client 優先播本地，只有不在 voice bank 範圍才 fallback server TTS（待整合）

### LLM hallucination
- Gemini 偶爾編造家人/同事人名（出現過「小芸」「小雲」）
- 後端 system prompt 已加：`絕對不要編造任何家人、同事、朋友的人名`，用「您家人」「您同事」「對方」通用稱呼

### Push Notifications / Background Modes
- `INFOPLIST_KEY_UIBackgroundModes` Xcode 26 不認得 → 真正背景 polling 需要實體 Info.plist 或 `BGTaskScheduler` framework
- Push Notifications capability 需要 Xcode → Signing & Capabilities → + Capability 手動加 entitlements

---

## 今天的開發歷程（2026-04-26）

### 早上：iOS Project Setup
- 從零（Xcode boilerplate "Hello, world!"）開始
- 抓後端 6 個 Swift 檔（AlfredApp / AlfredView / AlfredViewModel / AlfredAPI / AuthManager / LoginView）
- 把舊 `Office/` folder 搬進 `Features/Office/`
- Stub 4 個 Manager（LocationManager / BackgroundManager / HealthKitManager / AudioEngine）
- 修 Combine import（Xcode 26 嚴格模式 `@Published` 必須顯式 `import Combine`）
- 清理 pbxproj 殭屍 `Office/` group（sync group 接管後不需手動註冊）
- **第一次 Build SUCCESS** ✅

### 中午：辦公室模組 NLU
- 4 句話 NLU 路由：`幫我看辦公室狀況` / `家人現在在哪` / `翻譯模式` / `我的出勤記錄`
- 後端原本 `action: null`，因為 Gemini 2.0 Flash 把 tool call emit 成文字
- 加 fallback：`chat()` return 前用 regex 抽 `{"type": "show_xxx"}`，放結構化 `action` field

### 下午：iOS UI 完整化
- AppIcon 換成黑底金圈禮帽（13 種尺寸 sips 自動 resize）
- 14 個 Apple 權限 usage description（INFOPLIST_KEY 進 build settings）
- 修 SUPPORTED_PLATFORMS（拿掉 macosx/xros，TranslateView 用 iOS-only modifier）
- LocationManager `allowsBackgroundLocationUpdates` Info.plist 沒 capability 會 SIGABRT，加 guard

### 傍晚：Onboarding 設計地獄
- 阿福「自己念完啟動語」事件 → mp3 內容包含啟動語，旁人聽到會以為認證完成
- onboarding 流程從 `await api.tts(intro)` 改 `播本地 onboarding_greeting.mp3`
- BackgroundManager / HealthKit / Location 只在 onboarded 後才啟動（避免搶話）
- sendMessage 加 onboarding mode 分支：對 → 確認 + 認證；錯 → 保留啟動語提示請主人重念
- 啟動語比對寬鬆化（容忍 STT 「妳/你」「處理好/處理」誤差）

### 晚上：Voice 災難
- 後端 ElevenLabs cloned voice 突然變廣東話大嬸（cloned voice source 被換）
- 嘗試 AVSpeechSynthesizer 內建中文，結果 simulator fallback 廣東話更糟
- 用戶測 5 小時要 Michael Caine
- **發現 voice bank**：`alfred_voice_bank.zip` 有 470 個情境預錄 Michael Caine mp3
- iOS 改播本地 voice bank（穩定）+ server TTS fallback（範圍外）

### 夜晚：Device Auth + 自動測試
- 後端加 `/api/auth/device` endpoint（user 自己上線）— device_id 換 365 天 JWT，無密碼
- iOS Client `AlfredAPI.deviceLogin()` 用 UIDevice.identifierForVendor
- 寫 server smoke test：10 iter × 10 prompt 看 LLM tool 命中率 + 延遲
- UI test mode：launch arg `--prompt "..."` 自動 trigger sendMessage 跳過麥克風

---

## Git Commit 歷史

| Hash | 標題 |
|---|---|
| `09efea9` | 補齊 14 個 Apple 權限 usage description |
| `42992d9` | voice bank：470 個 Michael Caine 預錄 mp3 + onboarding 改播本地 |
| `4e0597f` | 完整 onboarding 流程 + 純語音對話介面 |
| `6ead788` | Initial Commit |

要 rollback：`git reset --hard <hash>`

---

## 設計者的話

阿福不是用來「展示功能」的。每一個情境（會議室快超時、太太還沒到家、主管的下屬有事還沒問）都是一件**沒人替你看著的事**。阿福的價值不在於做了多少，而在於**你問之前他就在那**。

零介面是承諾：使用者不應該為了讓阿福做事而學介面。
