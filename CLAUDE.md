# ⛔ PREFLIGHT — 動 code 前必讀（30 秒）

**新 Claude session 在這個目錄開啟時，第一個動作不是 grep code，是先讀 `docs/ALFRED.md` 第 0 章（入口須知 0.1-0.4，共 60 行）。**

回答這三題，答得出來才能動 code：

1. **step 1 / step 2** — 主人這次說的事是 step 1，阿福多做的是 step 2。
   - 兩步都到 = 阿福 / 只到 step 1 = ChatGPT
2. **這個情境對應 BUTLER_BRAIN 哪個鐵案例？**
   - pet_care（被動推論）/ health_anomaly+emergency（救命）/ location（家人偏離）/ 旅遊對話流 / 餐廳 anticipatory extras
3. **STATUS.md 看現況** — 我要動的技能在 ✅/🟡/🔴/⚪ 哪一格？這個 endpoint / handler / nudge 已經有沒有？

答不出第 1 題 = **還沒抓到管家味，重讀 `docs/BUTLER_BRAIN.md` 5 鐵案例再來**。

## 三條鐵律（壓在一切之上）

- **0.2 看到「沒接線」的 code 一律保留不准刪** — 102 個 `.bak`、`ResourceBackups/`、`populate_*.py`、`VoiceBankPlayer.swift` 都是倖存證據，主人 6 個視窗的還原網
- **永遠不製造恐慌** — 越緊急語氣越沉穩，不用「危險/緊急/立刻/馬上」
- **每動一刀先建 git tag 還原點** — `pre_xxx_YYYYMMDD` / `post_xxx_YYYYMMDD`

## 同步 SOP

開工 `git pull`、收工 `git push`。詳見 [SYNC.md](SYNC.md)。  
出問題救命表：[ROLLBACK.md](ROLLBACK.md)。

完整 doctrine 路標：
- `docs/ALFRED.md` ← 主人手冊（第七視窗整合版，**source of truth**）
- `docs/BUTLER_BRAIN.md` ← 5 鐵案例 + 設計判斷 Q1-Q5
- `docs/ALFRED_SCENARIOS.md` ← 65 技能 × 「呵護的是 X」
- `STATUS.md` ← 自動生成的進度地圖（main.py 行數、API、tool、DB、voice_bank）

---

# Alfred 阿福 — 開發入口

**描述：** 零介面語音管家 App
**Service：** `alfred.service`
**Port：** `9001`（只動阿福，不碰其他服務）
**後端：** `/opt/alfred/backend/main.py`
**iOS 專案：** `Alfred.xcodeproj`（此 repo 根目錄）

## ⚠️ 開工前必讀

1. `CRITICAL_README.md` — 強制規則
2. `ALFRED_SOUL.md` — 阿福人格、語氣、零介面哲學
3. `HANDOFF.md` — 後端 API / VPS 架構
4. `SCENARIOS.md` — 家管、辦公室、寵物、運動等北極星情境

## 核心鐵律

### 1. 零介面
阿福不是聊天 App。平常只有語音，不顯示文字對話流。
只有主人必須「看」內容時才出現介面：文件、合約、圖片、翻譯大字、授權。

### 2. 管家邏輯
先理解、先生成草案，再問主人是否要下一步。不要把生活規劃一開始就變成授權流程。

### 3. 不重複問授權
Google 已授權時，先查連線狀態，不要反覆推 OAuth。

### 4. 不幻覺
只能引用工具實際查到的結果。找不到就說找不到。

### 5. 程式改動沙盒原則
所有改動在 git worktree 裡進行，測試確認後才 merge 回 main。

## 後端維護

```bash
systemctl restart alfred
systemctl status alfred --no-pager -l
curl -sS http://127.0.0.1:9001/health
```

不要 kill 其他 port/process。`8000` = 股市交易所，`9001` = 阿福。

## 場景模式
- 辦公室 GPS → `mode=work`，優先會議、文件、行程、待辦
- 家中 → `mode=home`，優先家人安全、寵物照顧
- 海外 → `mode=travel`，優先翻譯、交通、安全
