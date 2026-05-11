"""
indexer/wide_worker.py — 廣度爬蟲（正確策略）

真相：Ruten API offset 超過 ~200 就循環，每個關鍵字上限約 200 筆
策略：500+ 關鍵字 × 每個 200 筆 = 10 萬+
分工：20 Workers，每個負責 25 個關鍵字

用法: python3 wide_worker.py <worker_id 0-19>
"""
import asyncio, httpx, sys, time, logging
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent))
from indexer.db import upsert_products, init_db

logging.basicConfig(level=logging.WARNING)

RUTEN_SEARCH = "https://rtapi.ruten.com.tw/api/search/v4/index.php/core/prod"
RUTEN_ITEMS  = "https://rapi.ruten.com.tw/api/items/v2/list"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.ruten.com.tw/",
}
PRICE_MAX = 9_000_000

# 500 個關鍵字，覆蓋所有品類
ALL_KEYWORDS = [
    # ── 3C 電子 ──────────────────────────────────────
    "AirPods Pro", "AirPods 4", "Sony WH-1000XM5", "Jabra Elite", "Bose QuietComfort",
    "藍牙耳機 入耳式", "有線耳機 遊戲", "降噪耳機", "耳掛耳機", "運動藍牙耳機",
    "iPhone 15 殼", "iPhone 16 殼", "Samsung S24 殼", "手機保護殼", "手機鏡頭貼",
    "iPhone 充電線", "USB-C 線", "MagSafe 充電器", "Type-C 充電頭", "GaN充電器",
    "行動電源 10000", "行動電源 20000", "MagSafe 行動電源", "快充行動電源",
    "Apple Watch 錶帶", "Galaxy Watch 7", "Garmin Vivoactive", "小米手環 8",
    "機械鍵盤 青軸", "機械鍵盤 紅軸", "無線鍵盤 矮軸", "靜音鍵盤", "87鍵鍵盤",
    "電競滑鼠 有線", "電競滑鼠 無線", "靜音滑鼠", "人體工學滑鼠", "軌跡球滑鼠",
    "記憶卡 256G", "記憶卡 512G", "記憶卡 讀卡機", "隨身碟 512G", "隨身碟 USB-C",
    "SSD 1TB", "SSD 2TB", "NVMe SSD", "外接硬碟 1TB", "外接硬碟 2TB",
    "顯示卡 4070", "顯示卡 4060", "RTX 4090", "顯示卡 二手", "CPU Intel i9",
    "筆電包 15吋", "筆電包 14吋", "後背包 防盜", "電腦桌 電競", "電腦椅 人體工學",
    "USB集線器 7孔", "HDMI 轉接線", "DP 顯示線", "Switch 充電座", "Switch 保護殼",
    "網路攝影機 1080P", "網路攝影機 4K", "麥克風 USB", "聲卡 外接", "直播設備",
    "路由器 WiFi6", "Mesh 路由器", "網路交換器", "網路線 Cat6", "PoE 交換器",
    # ── 家電 ──────────────────────────────────────────
    "掃地機器人 自動集塵", "掃地機器人 掃拖", "吸塵器 無線", "吸塵器 車用",
    "氣炸鍋 5L", "氣炸鍋 烤箱", "多功能烤箱", "微波爐 變頻", "電磁爐",
    "電飯鍋 IH", "電飯鍋 壓力", "熱水壺 快煮", "咖啡機 全自動", "膠囊咖啡機",
    "豆漿機", "果汁機 隨行杯", "食物調理機", "氣泡水機", "製冰機 家用",
    "空氣清淨機 HEPA", "空氣清淨機 Dyson", "除濕機 20L", "除濕機 商用",
    "電風扇 DC", "電風扇 循環扇", "暖風機", "電暖器 油汀", "空調 移動式",
    "洗碗機 桌上型", "烘碗機 落地", "洗衣機 滾筒", "乾燥機 熱泵", "洗脫烘 合一",
    "電動牙刷 音波", "電動牙刷 替換頭", "沖牙機 無線", "電動刮鬍刀", "電動鼻毛刀",
    "吹風機 Dyson", "吹風機 負離子", "直髮夾 離子", "捲髮棒 無線",
    "體脂計 藍牙", "血壓計 手腕", "額溫槍", "血氧機",
    # ── 美妝保養 ──────────────────────────────────────
    "面膜 保濕", "面膜 美白", "面膜 玻尿酸", "DR.JOU 面膜", "我的美麗日記",
    "防曬乳 SPF50", "防曬乳 隱形", "防曬噴霧", "卸妝水", "卸妝油",
    "精華液 玻尿酸", "精華液 維他命C", "乳液 保濕", "乳霜 修護", "眼霜 抗皺",
    "洗面乳 胺基酸", "洗面乳 水楊酸", "角質調理", "毛孔緊緻", "痘痘修護",
    "化妝水 化妝棉", "噴霧 定妝", "隔離霜", "BB霜", "CC霜",
    "洗髮精 蓬鬆", "洗髮精 控油", "護髮素 受損", "護髮油", "生髮液",
    "沐浴乳 玫瑰", "沐浴乳 胺基酸", "身體乳液", "磨砂膏 去角質", "沐浴球",
    "香水 女性", "香水 男性", "淡香水 清新", "體香劑", "乾洗手",
    # ── 食品飲料 ──────────────────────────────────────
    "白米 有機", "糙米 五穀", "燕麥片 桂格", "藜麥", "義大利麵",
    "泡麵 辛拉麵", "泡麵 日清", "泡麵 韓國", "米粉 乾", "冬粉",
    "醬油 龜甲萬", "醬油膏", "辣椒醬 是拉差", "番茄醬", "蠔油",
    "橄欖油 特級初榨", "椰子油", "葵花油", "花生醬", "芝麻醬",
    "黑咖啡 濾掛", "咖啡豆 單品", "奶茶 KRAK", "抹茶粉", "可可粉",
    "蜂蜜 台灣", "楓糖漿", "黑糖", "代糖 赤藻糖醇", "寡糖",
    "洋芋片 品客", "洋芋片 樂事", "餅乾 奧利奧", "巧克力 72%", "瑪德蓮",
    "堅果 綜合", "杏仁 無調味", "腰果", "南瓜籽", "夏威夷果",
    "果乾 芒果", "果乾 鳳梨", "蔓越莓乾", "枸杞", "黑棗",
    "蛋白粉 乳清", "BCAA", "肌酸", "膠原蛋白", "玻尿酸 口服",
    "維他命C 高單位", "魚油 Omega3", "維他命D3", "益生菌", "葉黃素",
    # ── 居家生活 ──────────────────────────────────────
    "收納盒 透明", "收納箱 折疊", "衣物收納袋", "真空壓縮袋", "鞋盒 透明",
    "置物架 廚房", "置物架 浴室", "三層架", "書架 收納", "牆上置物架",
    "掛鉤 無痕", "魔術貼 掛鉤", "S型掛鉤", "門後掛架",
    "窗簾 遮光", "窗簾 薄紗", "捲簾 防水", "蜂巢簾",
    "LED燈泡 E27", "LED燈管 T8", "吸頂燈 客廳", "床頭燈", "閱讀燈",
    "床墊 記憶泡棉", "乳膠床墊", "枕頭 記憶棉", "涼感枕頭", "羽絨被",
    "防水噴霧 鞋", "除味噴霧", "消臭劑", "芳香劑 車用", "擴香石",
    "保鮮盒 玻璃", "保鮮盒 不鏽鋼", "真空保鮮盒", "便當盒", "保溫杯",
    "砧板 抗菌", "廚刀 不鏽鋼", "削皮刀", "開罐器", "廚房剪刀",
    # ── 寵物 ──────────────────────────────────────────
    "狗飼料 成犬", "狗飼料 幼犬", "狗零食 潔牙棒", "狗零食 雞肉",
    "貓飼料 成貓", "貓飼料 老貓", "貓零食 凍乾", "貓砂 礦砂",
    "貓砂 豆腐砂", "貓砂盆 封閉式", "貓抓板", "貓爬架",
    "狗牽繩 伸縮", "狗胸背帶", "貓項圈", "寵物外出包",
    "寵物沐浴乳", "寵物梳子", "除蚤項圈", "寵物驅蟲",
    # ── 運動戶外 ──────────────────────────────────────
    "瑜珈墊 10mm", "瑜珈磚", "瑜珈繩", "健身滾筒", "筋膜球",
    "啞鈴 可調式", "啞鈴 固定式", "槓片", "彈力帶 套組", "TRX 懸吊",
    "跳繩 速跳", "跳繩 計數", "呼拉圈 加重", "踏步機 家用",
    "登山杖", "登山包 40L", "露營椅 折疊", "露營桌 折疊", "睡袋 戶外",
    "運動水壺 700ml", "保冷袋", "運動毛巾", "護腕", "護膝 加壓",
    # ── 文具書籍 ──────────────────────────────────────
    "鋼筆 入門", "鋼筆 墨水", "原子筆 慕娜美", "油性筆 麥克筆", "螢光筆",
    "筆記本 A5", "手帳 2025", "子彈筆記", "便利貼 3M", "膠帶 紙膠帶",
    "剪刀 文具", "美工刀", "切割墊 A4", "打孔機", "釘書機",
    # ── 工具五金 ──────────────────────────────────────
    "電鑽 無線", "電動起子 充電式", "砂輪機", "電鋸 線鋸機", "熱風槍",
    "螺絲起子 套組", "扳手 套組", "鉗子 套組", "水平儀 雷射", "捲尺",
    "膠帶 封箱", "泡棉膠帶", "魔鬼氈", "束帶 尼龍", "熱縮管",
    # ── 嬰幼兒 ──────────────────────────────────────
    "尿布 M號", "尿布 L號", "濕紙巾 嬰兒", "嬰兒洗髮精", "嬰兒乳液",
    "奶瓶 玻璃", "安撫奶嘴", "學習杯", "嬰兒餐椅", "推車 輕便",
    # ── 汽車機車 ──────────────────────────────────────
    "行車記錄器 4K", "行車記錄器 前後", "汽車香氛", "車用充電器",
    "安全帽 半罩", "安全帽 全罩", "機車手套", "機車坐墊套",
    # ── 遊戲 ──────────────────────────────────────────
    "任天堂 Switch 遊戲", "PS5 手把", "Xbox 手把", "遊戲手把 PC",
    "桌遊 台灣", "撲克牌 塑膠", "麻將 旅行", "積木 樂高",
]


async def crawl_ruten_keyword(keyword: str, worker_id: int) -> int:
    """每個關鍵字只抓前 3 頁（200-300 筆），避免循環重複"""
    products_all = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=15) as cli:
        # start=0 會 400，從 start=100 開始，只需 3 頁就能覆蓋真實不重複結果
        for start in [100, 200, 300]:
            try:
                r1 = await cli.get(
                    f"{RUTEN_SEARCH}?q={quote(keyword)}&limit=100&sort=prc%2Fac&start={start}"
                )
                if r1.status_code != 200:
                    break
                rows = r1.json().get("Rows", [])
                if not rows:
                    break
                ids = [row["Id"] for row in rows if row.get("Id")]
                if not ids:
                    break

                r2 = await cli.get(RUTEN_ITEMS, params={"gno": ",".join(ids)})
                if r2.status_code != 200:
                    await asyncio.sleep(1)
                    continue
                items = r2.json().get("data", [])

                for item in items:
                    if not item.get("available") or item.get("stock_status", 0) == 0:
                        continue
                    gno  = str(item.get("id", ""))
                    name = (item.get("name") or "").strip()
                    if not gno or not name:
                        continue
                    price = int(item.get("goods_price") or 0)
                    if price <= 0 or price > PRICE_MAX:
                        continue
                    ori  = int(item.get("goods_ori_price") or 0)
                    imgs = item.get("images", {}).get("url", [])
                    products_all.append({
                        "site":         "ruten",
                        "code":         gno,
                        "name":         name,
                        "category":     keyword,
                        "price":        price,
                        "list_price":   ori if ori > price else None,
                        "discount_pct": round((1 - price/ori)*100) if ori > price else None,
                        "image_url":    imgs[0] if imgs else "",
                        "buy_url":      f"https://www.ruten.com.tw/item/show?{gno}",
                    })
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"[W{worker_id}] ERR ruten/{keyword}: {e}", flush=True)
                await asyncio.sleep(1)

    # 去重後批量寫入
    seen = set()
    uniq = []
    for p in products_all:
        if p["code"] not in seen:
            seen.add(p["code"])
            uniq.append(p)
    added = upsert_products(uniq)
    return added


async def main(worker_id: int):
    init_db()
    # 每個 worker 負責約 25 個關鍵字
    chunk = len(ALL_KEYWORDS) // 20
    start_idx = worker_id * chunk
    end_idx = start_idx + chunk if worker_id < 19 else len(ALL_KEYWORDS)
    my_keywords = ALL_KEYWORDS[start_idx:end_idx]

    print(f"[W{worker_id}] START {len(my_keywords)} 關鍵字 ({my_keywords[0]}...{my_keywords[-1]})", flush=True)
    t0 = time.time()
    total = 0

    for kw in my_keywords:
        n = await crawl_ruten_keyword(kw, worker_id)
        total += n
        print(f"[W{worker_id}] {kw[:20]:20} → +{n} 筆 (累計 {total})", flush=True)

    print(f"[W{worker_id}] DONE +{total} 新增 耗時 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    wid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(main(wid))
