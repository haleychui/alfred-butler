## ⭐ 開發進度表(自動生成 — last: 2026-05-13 22:47)

> **這份是必讀。Alfred 整個進度都在這。**
> 由 `scripts/generate_status.py` 掃 codebase 自動生成,**不要手動改這段(`<!-- BEGIN/END AUTO_STATUS -->` 之間)**。
> 質化的「65 技能對應現況」+「呵護的是 X」請看 [`docs/ALFRED.md`](docs/ALFRED.md) 第 4 章。

### 規模

| 維度 | 數量 |
|---|---:|
| `backend/main.py` 行數 | 14,890 |
| API endpoints(`@app.*`)| 144 |
| LLM tools | 68 |
| Fastpath 函數(zero LLM)| 13 |
| DB tables(`CREATE TABLE`)| 70 |
| Backend service modules | 9 |
| Populate seed scripts | 5 |
| Scrapers in tree | 11 |
| iOS Swift 檔 | 26 個,共 4,991 行 |
| voice_bank 預錄 mp3 | 3,061 個 |
| `alfred.db` 大小 | 232 MB |
| 主人上傳分析過的檔案 | 41 |

### Fastpath 函數(zero LLM 秒答)

| 函數 | 用途 |
|---|---|
| `_maybe_handle_liveness_fastpath` | ⭐ 你還在嗎 / 你好 / 早安(2026-05-13 加,從 24s → 0.7s) |
| `_maybe_handle_ambient_command_fastpath` | 聆聽錄音指令 |
| `_maybe_handle_iphone_photo_fastpath` | iPhone 相簿請求 |
| `_maybe_handle_meeting_record_fastpath` | 會議記錄查詢 |
| `_maybe_handle_integration_link_fastpath` | 通訊連結(LINE / Telegram / WhatsApp) |
| `_maybe_handle_attendance_fastpath` | 出勤記錄 |
| `_maybe_handle_google_auth_status_fastpath` | Google 授權狀態 |
| `_maybe_handle_quick_lists_fastpath` | 快速列表(todo / expense / ...) |
| `_maybe_handle_math_fastpath` | 純數學(BUTLER_BRAIN 第 13 鐵則) |
| `_maybe_handle_shopping_fastpath` | 比價(The Commerce Crack) |
| `_maybe_handle_travel_fastpath` | 旅遊規劃(populate_travel.py DB 接上時) |
| `_maybe_handle_restaurant_fastpath` | 餐廳搜尋 |
| `_maybe_handle_file_search_fastpath` | 檔案搜尋(vault + drive + mac) |

### voice_bank 類別(共 3,061 個 mp3)

| 類別 | 數量 | 對應技能 |
|---|---:|---|
| `travel_mode` | 150 | 出國 / 旅遊場景 |
| `family_safety` | 150 | 家人關係 / family_alerts / arrivals |
| `mood_care` | 150 | 情緒感知 / emotional/care(妳的初衷) |
| `health_monitoring` | 120 | 健康日常 / log_workout / medication |
| `ack_butler` | 101 | ⭐ 你還在嗎 / liveness fastpath |
| `proactive_check` | 101 | 主動關心 / health_status 久坐 |
| `file_search` | 100 | 檔案搜尋 |
| `document_review` | 100 | 文件分析 / analyze_contract |
| `promise_tracking` | 100 | 承諾追蹤 / note_promise |
| `weather_general` | 100 | 天氣編織 / get_weather |
| `calendar` | 100 | create_calendar_event |
| `approval_gate` | 100 | 草擬等主人 OK |
| `error_recovery` | 80 | 失敗回應 |
| `ack_anticipate` | 80 | anticipatory extras |
| `destructive_warn` | 80 | 不可逆動作警告 |
| `emergency` | 80 | 生命安全 / health_anomaly |
| `food_restaurant` | 80 | save_food_record / 訂餐廳 |
| `mode_action` | 79 | 場景模式動作 |
| `ack_short` | 62 | 短答(我在 / 收到 / 好的) |
| `mode_enter` | 60 | 場景進入語(work/home/travel) |
| `casual_humor` | 60 | 英式幽默點到為止 |
| `office_manager` | 60 | manager_lens / silence_radar |
| `office_expertise` | 50 | expertise_finder |
| `greet_time` | 50 | ⭐ 早安 / 午安 / 晚安 / liveness fastpath |
| `money_expense` | 50 | record_expense |
| `office_thanks` | 40 | thanks_nudge |
| `filler_thinking` | 40 | 思考中(< 1s 等待填充) |
| `office_eod` | 31 | office/eod-wrap |
| `office_supply` | 30 | 辦公耗材 |
| `office_room` | 30 | office/rooms / room-pulse |

### iOS Swift 檔案地圖

| 檔案 | 行數 | 角色 |
|---|---:|---|
| `Alfred/AlfredApp.swift` | 60 | App 入口 + consent gate |
| `Alfred/Core/AfuBrainGate.swift` | 213 | MASL gate,destructive action 本地擋 |
| `Alfred/Core/AlfredAPI.swift` | 551 | 後端 API client(含 SSE stream) |
| `Alfred/Core/AlfredViewModel.swift` | 759 | 主 ViewModel,狀態機,action dispatch |
| `Alfred/Core/AliceFastpath.swift` | 288 | 時間/日期/數學/單位/早安謝謝 zero-LLM(待補 liveness) |
| `Alfred/Core/AmbientRecorder.swift` | 161 | 被動環境錄音,120s chunk |
| `Alfred/Core/AudioEngine.swift` | 104 | AVAudioRecorder + AVAudioPlayer |
| `Alfred/Core/AuthManager.swift` | 177 | JWT + Keychain(原 legacy 名,實際多處使用) |
| `Alfred/Core/BackgroundManager.swift` | 172 | reminder / family alert / visit prep 輪詢 |
| `Alfred/Core/ConversationLog.swift` | 44 | 對話歷史寫到 Documents/ |
| `Alfred/Core/HealthKitManager.swift` | 138 | HealthKit + workout sync |
| `Alfred/Core/LocationManager.swift` | 75 | CLLocationManager + /api/location/update |
| `Alfred/Core/PermissionCascade.swift` | 145 | 漸進式權限請求 |
| `Alfred/Core/PhotosManager.swift` | 91 | iOS Photos 權限 + 選圖 |
| `Alfred/Core/VoiceBankPlayer.swift` | 90 | 🔴 卸下待補 — 預錄 mp3 抽取播放(0 引用) |
| `Alfred/Features/Ambient/AmbientButton.swift` | 104 | 金色環,長按啟動 ambient |
| `Alfred/Features/Attendance/AttendanceView.swift` | 231 | 出勤記錄 view |
| `Alfred/Features/Auth/ConsentView.swift` | 171 | 第三方 AI 同意聲明(首次啟動) |
| `Alfred/Features/Auth/LoginView.swift` | 133 | 🔴 legacy email 登入,平時不顯示 |
| `Alfred/Features/Chat/AlfredView.swift` | 388 | 主畫面,語音按鈕 + AmbientButton overlay |
| `Alfred/Features/Family/FamilyView.swift` | 173 | 家人狀態 view |
| `Alfred/Features/Office/OfficeDashboardView.swift` | 247 | Office dashboard(eod/rooms/...) |
| `Alfred/Features/Office/OfficeViewModel.swift` | 111 | Office API client |
| `Alfred/Features/Photos/PhotoGridView.swift` | 173 | 相片格狀瀏覽 sheet |
| `Alfred/Features/Photos/PhotoPickerRequest.swift` | 31 | PHPickerViewController wrapper |
| `Alfred/Features/Translate/TranslateView.swift` | 161 | 即時翻譯大字 view |

### Backend Python 檔案地圖

| 檔案 | 角色 |
|---|---|
| `backend/main.py` | FastAPI app entry — 所有 endpoint + tool + chat handler + fastpath chain |
| `backend/call_service.py` | Twilio 通話 / TwiML |
| `backend/drive_service.py` | Google Drive index + search(含共用雲端硬碟) |
| `backend/gcal_service.py` | Google Calendar 多帳號 OAuth + events |
| `backend/gmail_service.py` | Gmail 收發 / 草擬 |
| `backend/line_service.py` | LINE webhook + 主動推送 |
| `backend/office_service.py` | 辦公室 dashboard 邏輯(eod/rooms/supplies/colleagues) |
| `backend/search_service.py` | 語意檔案搜尋(vault + drive + mac) |
| `backend/shop_service.py` | 13 站並發比價引擎(The Commerce Crack) |
| `backend/telegram_service.py` | Telegram bot |
| `backend/populate_global.py` | 🟡 待補(第六視窗卸下)— 全球景點 seed |
| `backend/populate_hotels_fixed.py` | 🟡 待補 — 飯店 seed |
| `backend/populate_michelin_hotels.py` | 🟡 待補 — 米其林飯店 seed |
| `backend/populate_taiwan_restaurants.py` | 🟡 待補 — 台灣餐廳 seed |
| `backend/populate_travel.py` | 🟡 待補 — 旅遊行程 seed(BUTLER_BRAIN 第 4 經典案例) |

### Backend Scrapers

| 檔案 | 平台 / 狀態 |
|---|---|
| `backend/scrapers/biggo_scraper.py` | 🔴 未接線 — Biggo 比價 |
| `backend/scrapers/books_scraper.py` | 博客來 |
| `backend/scrapers/buy123_scraper.py` | 東森購物 buy123 |
| `backend/scrapers/carrefour_scraper.py` | 家樂福 |
| `backend/scrapers/coupang_scraper.py` | 酷澎 |
| `backend/scrapers/elifemall_scraper.py` | 東森購物 ETMall |
| `backend/scrapers/payeasy_scraper.py` | 🔴 未接線 — PayEasy 會員爬蟲 |
| `backend/scrapers/pinkoi_scraper.py` | Pinkoi |
| `backend/scrapers/tkec_scraper.py` | 燦坤 |
| `backend/scrapers/trplus_scraper.py` | 特力屋 |
| `backend/scrapers/yahoo_scraper.py` | Yahoo 購物 |

### Extras(scale-up tooling,目前未綁進主程式)

- `extras/indexer/`: auto_crawl.sh, bulk_index.py, mega_crawl.py, migrate_to_pg.py, pg_schema.sql, wide_worker.py, wide_worker2.py, worker.py
- `extras/scrapers/`: crowdfunding_scraper.py, taobao_scraper.py

### 倖存證據(2026-05-13 規則:不准刪)

妳被改爛時的還原網。任何 Claude 視窗看到這些**一律保留,不准建議清**。

| 類別 | 數量 / 內容 |
|---|---|
| `*.bak*` 檔案 | 102 個 |
| 備份資料夾 | ResourceBackups |
| 舊快照 | ios_latest.zip, ios_app, ios |

### 最近活動

**最近 20 commits**:

```
7cf7970 第七視窗整合 — 修速度 / 接 travel_hotels / emotional 主動鏈 / 進度自動化
523594e feat: extras/ — scale-up indexer tools + scrapers
2f1c513 auto: update README.md
e1c03ae auto: update README.md
0054ed0 docs: add BUTLER_BRAIN.md + ALFRED_SCENARIOS.md (Alfred design DNA) (#1)
6badec9 docs: WTF.md — 完整雙 Phase 報告，可驗證數字
f1e3bad feat(index): Phase 2 — 20 Agent 商品索引引擎
5c8c4da Add PayEasy scraper (members-only, session-required)
1d6cdb6 docs: PRICE_HUNT.md — 用戶導向完整產品說明文件
18e002b docs: rewrite SHOP_ENGINE.md — Commerce Crack methodology + WOW narrative
52f36cd docs: Operation AllIn 完整紀錄 + 可驗證 benchmark 數據
16ec33b feat(shop): Operation AllIn 完成 — 15站並發比價引擎 + 比價王聚合
66c3b22 Add Ruten (露天) scraper to shop price engine
c357753 Add biggo scraper for multi-store price comparison
8eed232 feat(shop): 12站並發比價引擎完成 — 博客來/松果/東森/Yahoo/家樂福/生活市集/特力屋/全國電子/酷澎/Pinkoi
17f8684 Add tkec (燦坤) product search scraper
1955157 Add Coupang Taiwan product search scraper
b32e945 Add Pinkoi scraper for price comparison engine
62785a8 Add 松果購物 (pcone.com.tw) scraper to price comparison engine
f6dc8ae Add elifemall scraper for Alfred price comparison engine
```

**rollback tags**(最近 10):

```
post_biggo_and_care_push_20260513
pre_scrapers_and_care_push_20260513
post_a_and_b_20260513
post_ack_fix_20260513
post_auto_status_20260513
post_travel_hotels_20260513
pre_ack_fix_20260513
pre_liveness_fastpath_20260513
pre_monitor_fix_20260513
pre_travel_hotels_20260513
```

### 順藤摸瓜 — 我是新接手的人,該怎麼讀?

1. **先讀 doctrine**:[`docs/ALFRED.md`](docs/ALFRED.md) 第 0-2 章(產品核心價值 + 第一原理 + 真正的架構)
2. **再讀技能劇本**:[`docs/ALFRED_SCENARIOS.md`](docs/ALFRED_SCENARIOS.md)(65 技能 × 「呵護的是 X」)
3. **碰 code 前必讀**:[`docs/BUTLER_BRAIN.md`](docs/BUTLER_BRAIN.md)(5 經典範例 + 設計判斷 Q1-Q5)
4. **看這份進度表**(上面)了解 backend / iOS / voice_bank 實況
5. **碰任何「未接線」的程式**前先問主人,不要叫死碼

---

*由 `scripts/generate_status.py` 自動產生 — 改 codebase 後跑一次即更新。*