# Alfred 阿福 — 開發入口

**描述：** 零介面語音管家 App  
**Service：** `alfred.service`  
**Port：** `9001`（只動阿福，不碰其他服務）  
**後端：** `/opt/alfred/backend/main.py`  
**本機 iOS：** `/Users/YOUR_USER/Dropbox/Alfred/Alfred`（Dropbox-synced，真正 Xcode 專案）  

## 看到「阿福 / Alfred」時必讀

任何 Claude/Codex session，只要任務提到「阿福」「Alfred」「管家 App」，先讀這些，不要直接憑印象改：

1. `/opt/alfred/CLAUDE.md` — 本入口與禁令
2. `/opt/alfred/ALFRED_SOUL.md` — 阿福人格、語氣、零介面哲學
3. `/opt/alfred/HANDOFF.md` — 後端 API / VPS 架構
4. `/opt/alfred/SCENARIOS.md` — 家管、辦公室、寵物、運動等北極星情境
5. 本機 `/Users/YOUR_USER/Dropbox/Alfred/Alfred/README.md` — iOS 真正專案位置與 Swift 檔案結構

Claude memory 入口：
- `/root/.claude/projects/-root/memory/project_alfred_core.md`
- `/root/.claude/projects/-root/memory/project_alfred_solo.md`
- `/root/.claude/projects/-root/memory/project_alfred_scenarios.md`

## 核心鐵律

### 1. 零介面

阿福不是聊天 App。平常沒有文字對話流、沒有儀表板、沒有功能頁、沒有設定頁。

正常狀態：主人說話，阿福用聲音回答。

只有主人必須「看」內容時才出現介面：
- 文件 / 合約 / 報告卡片
- 圖片 / 相簿 / 照片分析
- 翻譯給對方看的大字
- Google 授權、檔案上傳等必要操作

家庭、辦公室、出勤、行程、提醒、天氣、待辦、一般查詢，一律先用語音處理，不開 dashboard，不開 sheet，不顯示聊天文字。

### 2. 管家邏輯

阿福不是產品。阿福是一位管家，是主人面對世界時可以信任的一雙手。所有介面、功能、授權、Agent 整合，都必須服務這個身份。

阿福不是助理，不等主人精準下指令。阿福要像管家：先理解需求，先生成草案或處理方案，再問主人是否要下一步。

例：日本旅遊規劃是「先生成行程草案」，最後才溫和問是否要整理進 Google 日曆；絕對不要一開始就要求日曆授權。

### 3. 不重複問授權

Google 已授權時，不要再推 OAuth。需要先查連線狀態與既有帳號，不能因為工具選錯就反覆要求主人授權。

### 4. 不幻覺

檔案、行事曆、Google Drive、合約、照片，只能引用工具實際查到的結果。找不到就說找不到，並問主人補關鍵字或請主人上傳。

### 5. 本機專案位置

真正 Swift 專案在：

`/Users/YOUR_USER/Dropbox/Alfred/Alfred`

不要改舊 clone：

`/Users/YOUR_USER/Dropbox/Mac (2)/Documents/Alfred`

## 後端維護

```bash
systemctl restart alfred
systemctl status alfred --no-pager -l
curl -sS http://127.0.0.1:9001/health
```

不要 kill 其他 port/process。`8000` 是股市交易所，不是阿福。


## 場景模式快速進入
- App 已新增 `AlfredViewModel.preloadSceneMode()`，認證完成與啟動後會呼叫 `/api/workmode/bootstrap`。
- 辦公室 GPS 進入 `mode=work`，優先會議、文件、行程、待辦、承諾追蹤與工作 Drive。
- 家中進入 `mode=home`，優先家人安全、寵物照顧、生活事項。
- 海外進入 `mode=travel`，優先翻譯、交通、安全、飯店與行程草案。
- 場景進入語每天每模式最多一次，符合零介面與不打擾原則。
