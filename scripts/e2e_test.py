#!/usr/bin/env python3
"""阿福 e2e 200 次瀏覽器測試
- Headless Chromium → https://YOUR_BACKEND_HOST/alfred/
- 200 prompts 涵蓋 chat / calendar / drive / office / family / memory / translate
- 每個測試：寫 input → 觸發 sendMsg → 等 /chat/stream 結束 → 紀錄
- 結果寫 /opt/alfred/data/e2e_results_<TS>.json + 每 10 個寫進度到 /tmp/e2e_progress.log
"""
import asyncio, json, time, sys, os
from datetime import datetime
from playwright.async_api import async_playwright

URL = "https://YOUR_BACKEND_HOST/alfred/"
TIMEOUT_PER_TEST = 25_000  # ms
RELOAD_EVERY = 25  # 每 25 次重新 reload 避免 history 太肥
DELAY_BETWEEN = 0.4  # sec

# ── 200 PROMPTS（依類別）────────────────────────────────────────────────────
PROMPTS = []

LIGHT = [  # 60: 簡短日常
    "你好", "嗨阿福", "你在嗎", "今天幾號", "現在幾點", "天氣怎麼樣", "今天會下雨嗎",
    "今天台北氣溫", "週末天氣", "現在是上午還是下午", "明天禮拜幾", "這週剩幾天",
    "謝謝", "辛苦了", "晚安", "早安", "午安", "我餓了", "推薦一道菜",
    "中午吃什麼好", "想喝咖啡", "有什麼台北早餐推薦", "現在哪間便利商店有開",
    "我累了", "幫我打氣", "心情有點悶", "說個笑話", "說個冷笑話", "你最喜歡的顏色",
    "你會什麼", "你能幫我做什麼", "你會說英文嗎", "你會日文嗎", "1 加 1 等於多少",
    "100 元打 8 折是多少", "300 公克水的體積是多少 cc", "公斤跟磅怎麼換算",
    "1 美元等於多少台幣", "歐元現在匯率", "比特幣價格", "今天股市開嗎",
    "台積電股價", "美國總統現在誰", "今年是西元幾年", "民國幾年",
    "光速多快", "太陽距離地球多遠", "月亮為什麼會有陰晴圓缺", "彩虹幾種顏色",
    "白雪公主有幾個小矮人", "圓周率前 10 位", "DNA 全名", "RGB 是什麼",
    "iPhone 最新型號", "蘋果總部在哪", "OpenAI 創辦人是誰", "WiFi 怎麼設密碼安全",
    "USB-C 跟 Lightning 差別", "藍牙耳機怎麼配對", "怎麼截圖 iPhone",
]
PROMPTS.extend([("light", p) for p in LIGHT[:60]])

HEAVY = [  # 40: 推理 / 規劃 / 多步
    "幫我想一個三天兩夜京都行程，含交通、必吃、預算 4 萬台幣",
    "我要寫一封婉拒供應商提案的信，他們報價太高但合作多年，幫我擬",
    "我有 3 個下屬一個摸魚一個強勢一個內向，幫我設計三人不同的對談方式",
    "解釋一下為什麼 SOP 寫太細反而拖慢執行",
    "我想申請 Open Phil 的 AI safety 研究經費，怎麼定位才有機會",
    "幫我看這段 SQL 哪裡有問題：SELECT name FROM users WHERE age > 18 ORDER",
    "我新創失敗 3 次，下一次怎麼避免重複錯誤",
    "幫我分析做 SaaS 跟做硬體的優劣",
    "我要在 LinkedIn 寫一篇關於 AI agent 的長文，給我大綱",
    "我有一份 50 頁合約要看，重點怎麼抓",
    "把昨天會議重點整理成 3 段，每段 2 句",
    "為什麼大多數人忌妒成功者，請從演化心理學分析",
    "解釋 Bayes 定理用直覺方式",
    "比較 Stripe 跟 IAP 的優缺點，給創業者建議",
    "為什麼台灣硬體強軟體弱",
    "如果用戶投訴功能不好用，怎麼分辨他是真的還是不會用",
    "你會推薦哪本書讀懂創業思維",
    "AI 真的會取代設計師嗎",
    "如果我只剩 6 個月跑道怎麼分配時間",
    "我同時有 3 個產品在做，怎麼決定砍哪個",
    "幫我寫一段對 VC 自我介紹，30 秒口頭版",
    "我要說服技術合夥人留下，他覺得方向不對，怎麼開",
    "這週要跑完三個提案，每天怎麼排",
    "如何在 30 天內驗證一個產品想法",
    "我團隊溝通成本太高，常常重工，怎麼修",
    "比較 GPT-4o 跟 Gemini 2.5 Flash 的強項",
    "Tesla 跟 BYD 的長期競爭，誰會贏",
    "幫我用一句話定位「個人 AI 管家」",
    "我的客戶說不需要 AI 助理，怎麼回",
    "資本寒冬下，募資該講大故事還是小現金流",
    "為什麼 0 到 1 比 1 到 100 難",
    "AI 訓練資料用名人的照片合理嗎",
    "我想轉型做研究員，背景是 GM，怎麼定位",
    "今晚加班還是回家陪家人，給我一個原則",
    "Manifund 跟 SFF 適合什麼類型的研究",
    "ChatGPT 寫的東西怎麼一眼看出來",
    "為什麼 founder mode 在台灣很難複製",
    "怎麼判斷自己是不是該放棄一個方向",
    "AI agent 跟 AI assistant 差別",
    "如果阿福要進 App Store，你建議怎麼定價",
]
PROMPTS.extend([("heavy", p) for p in HEAVY[:40]])

CALENDAR = [  # 20
    "我明天有什麼會", "下週的行程", "我今天有什麼待辦",
    "幫我新增一個會議：明天下午 3 點，跟 PM 討論",
    "週四的下午有空嗎", "下週五我要出差，幫我提醒",
    "把週五會議改到週四", "今天下午有什麼安排",
    "我答應大雞要回他訊息，幫我提醒", "把這週的會議列出來",
    "看一下我的 Google 行事曆", "今天結束前還剩幾件事",
    "明天有什麼還沒回的", "下個月 3 號我有什麼",
    "幫我看下個禮拜空檔最多哪天", "我跟設計師約幾點",
    "1 月 15 日我有什麼", "上次跟採購開會是哪一天",
    "下個月有沒有客戶會議", "今年農曆過年是幾月幾號",
]
PROMPTS.extend([("calendar", p) for p in CALENDAR[:20]])

DRIVE = [  # 20
    "幫我找合約檔案", "上次的提案在哪", "采妍合約",
    "幫我找紀香顧問合約", "PLSTW 那份保密合約",
    "上週的會議筆記", "找我給客戶的報價單",
    "顧問合約 V2 在哪", "幫我找 Q3 報告",
    "找一下昨天上傳的那個檔案", "找有 budget 字眼的檔案",
    "Drive 裡 5 月之後的合約", "找關於 OAuth 的所有文件",
    "尋找產品藍圖", "找上次跟 RD 開會的紀錄",
    "幫我找 Pandoronia 那份", "查詢上次 EP9 改過哪裡",
    "找 Battlenix SPEC v2", "找 Lobster Observatory 設計文件",
    "Mac 裡有沒有阿福開發筆記",
]
PROMPTS.extend([("drive", p) for p in DRIVE[:20]])

OFFICE = [  # 20
    "辦公室現在誰在", "會議室訂滿了嗎",
    "今天誰請假", "RD 那邊最近忙嗎",
    "下個月誰生日", "誰擅長品牌設計",
    "誰跟過國際客戶", "我跟下屬有什麼承諾還沒兌現",
    "團隊裡誰最近沉默太久", "有人被排太多深夜會議嗎",
    "辦公室耗材還夠嗎", "影印紙快沒了嗎",
    "今天該感謝誰", "上週誰幫過我",
    "下屬本週進度怎樣", "幫我看 PM 那邊的狀況",
    "新人 onboarding 進度", "我答應 Marketing 的事還沒做",
    "預訂一間明天 14 點的會議室", "釋放剛剛我訂但沒去的會議室",
]
PROMPTS.extend([("office", p) for p in OFFICE[:20]])

FAMILY = [  # 15
    "媽媽現在在哪", "家裡有人嗎", "老公到家了沒",
    "我家小孩放學了嗎", "今天家人都到家了嗎",
    "家裡誰還在外面", "媽媽今天身體狀況",
    "家人最近有沒有發警報", "家裡電費繳了嗎",
    "今天家人位置摘要", "幫我設定家庭群組通知",
    "我老婆生日是哪一天", "下週是誰的紀念日",
    "家裡寵物多久沒被遛", "家人最近有人打給我嗎",
]
PROMPTS.extend([("family", p) for p in FAMILY[:15]])

MEMORY = [  # 15
    "我之前說過要做的那件事是什麼", "我上次提過 V121 那份土地",
    "我說過要買的東西", "上週阿福你怎麼幫我處理那件事",
    "我們聊過 Manifund 對吧", "我說過幾個小孩",
    "我老闆是誰", "我上次答應採購什麼",
    "把這個記下來：6 月 15 日要交報告", "幫我記得：明天買牛奶",
    "我有提過想學西班牙文", "我之前答應大雞要送嬰兒推車",
    "我說過下個月去日本", "上次說過的那個顧問建議是什麼",
    "我幾月幾號開始用阿福",
]
PROMPTS.extend([("memory", p) for p in MEMORY[:15]])

TRANSLATE = [  # 10
    "把「明天下午三點來開會」翻成英文",
    "翻成日文：謝謝您的合作",
    "Hello 在德文怎麼說", "我喜歡你 翻成韓文",
    "Bon appétit 中文意思", "請告訴我泰文的「不好意思」",
    "西班牙文「再見」怎麼說", "幫我說一句法文「我餓了」",
    "中翻英：阿福是我的個人 AI 管家",
    "Translate '下一站 台北 101' to English",
]
PROMPTS.extend([("translate", p) for p in TRANSLATE[:10]])

assert len(PROMPTS) == 200, f"prompts 數量錯誤：{len(PROMPTS)}"

PROGRESS_LOG = "/tmp/e2e_progress.log"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULTS_PATH = f"/opt/alfred/data/e2e_results_{TS}.json"

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(PROGRESS_LOG, "a") as f:
        f.write(line + "\n")

async def run():
    open(PROGRESS_LOG, "w").close()
    log(f"開始 e2e 測試，目標 200 次。結果寫到 {RESULTS_PATH}")
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 抓所有 console error
        page.on("console", lambda msg: log(f"console.{msg.type}: {msg.text[:120]}") if msg.type in ("error","warning") else None)

        await page.goto(URL, timeout=15000)
        await page.wait_for_timeout(2500)

        # 確認 auth ready
        ready = await page.evaluate("""
            ({hasInput: !!document.getElementById('txt-input'),
              token: !!localStorage.getItem('alfred_token'),
              sendFn: typeof window.sendMsg})
        """)
        log(f"page ready: {ready}")
        if not (ready['hasInput'] and ready['sendFn'] == 'function' and ready['token']):
            log("✗ page 未就緒，中止")
            await browser.close()
            return

        for i, (cat, prompt) in enumerate(PROMPTS, 1):
            t0 = time.time()
            entry = {"i": i, "cat": cat, "prompt": prompt, "ok": False, "latency_ms": None,
                     "response_len": 0, "response_preview": None, "error": None}

            try:
                # reload 每 25 次（清 history、避免 ctx 過大）
                if (i - 1) % RELOAD_EVERY == 0 and i > 1:
                    await page.reload()
                    await page.wait_for_timeout(2200)

                # 等 /chat/stream 回應
                async with page.expect_response(
                    lambda r: '/chat/stream' in r.url,
                    timeout=TIMEOUT_PER_TEST
                ) as resp_info:
                    # 透過 window.sendMsg 觸發（跟 voice / 文字輸入路徑一致）
                    await page.evaluate(f"window.sendMsg({json.dumps(prompt)})")
                resp = await resp_info.value
                # 讀完整 SSE body
                body = await resp.body()
                text = body.decode('utf-8', errors='replace')
                # 抽出所有 delta 拼成回應文字
                response_text_parts = []
                for line in text.split('\n'):
                    line = line.strip()
                    if line.startswith('data: '):
                        try:
                            obj = json.loads(line[6:])
                            if 'delta' in obj and obj['delta']:
                                response_text_parts.append(obj['delta'])
                        except Exception:
                            pass
                response_text = ''.join(response_text_parts)
                entry["ok"] = bool(response_text and resp.status == 200)
                entry["latency_ms"] = int((time.time() - t0) * 1000)
                entry["response_len"] = len(response_text)
                entry["response_preview"] = response_text[:200]
                entry["status_code"] = resp.status

            except Exception as e:
                entry["error"] = str(e)[:300]
                entry["latency_ms"] = int((time.time() - t0) * 1000)

            results.append(entry)

            # 進度（每 5 個一行）
            if i % 5 == 0 or i == len(PROMPTS):
                ok_count = sum(1 for r in results if r["ok"])
                log(f"  進度 {i}/200 | OK {ok_count} | latest: [{cat}] {prompt[:30]}... → {entry['latency_ms']}ms ok={entry['ok']}")

            # 階段性存檔
            if i % 20 == 0:
                with open(RESULTS_PATH, "w") as f:
                    json.dump({"completed": i, "total": 200, "results": results}, f, ensure_ascii=False, indent=2)

            await asyncio.sleep(DELAY_BETWEEN)

        await browser.close()

    # 最終寫檔
    with open(RESULTS_PATH, "w") as f:
        json.dump({"completed": 200, "total": 200, "results": results}, f, ensure_ascii=False, indent=2)
    log(f"完成。結果在 {RESULTS_PATH}")

if __name__ == "__main__":
    asyncio.run(run())
