"""
indexer/bulk_index.py — 暴力批量索引

目標：100,000+ 筆
策略：
  - 每個關鍵字抓 40-60 筆（不是 10 筆）
  - 關鍵字從 200 個擴張到 2,000 個
  - 多站並發，不排隊等
"""
import asyncio
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers"))

from indexer.db import init_db, upsert_products, get_stats
from indexer.query_parser import is_accessory

log = logging.getLogger("bulk")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# ── 2,000 個關鍵字清單 ─────────────────────────────────────────────────────
KEYWORDS = {
    "3c": [
        # 耳機
        "AirPods Pro", "AirPods", "藍牙耳機", "無線耳機", "降噪耳機",
        "Sony WH-1000XM5", "Sony WF-1000XM5", "Bose QuietComfort",
        "JBL耳機", "Jabra耳機", "Anker耳機", "QCY耳機", "1MORE耳機",
        "耳罩式耳機", "入耳式耳機", "頸掛式耳機", "骨傳導耳機",
        # 手機
        "iPhone 16", "iPhone 15", "iPhone 14", "iPhone SE",
        "Samsung Galaxy S24", "Samsung Galaxy A54", "三星手機",
        "小米手機", "紅米手機", "OPPO手機", "vivo手機", "ASUS手機",
        "Google Pixel", "華為手機",
        # 平板
        "iPad Pro", "iPad Air", "iPad mini", "Samsung Galaxy Tab",
        "小米平板", "華為平板", "ASUS平板",
        # 筆電
        "MacBook Pro", "MacBook Air", "MacBook",
        "ASUS筆電", "Lenovo ThinkPad", "HP筆電", "Dell XPS",
        "Microsoft Surface", "Acer筆電", "MSI筆電",
        # 電腦周邊
        "機械鍵盤", "電競鍵盤", "無線鍵盤", "藍牙鍵盤",
        "電競滑鼠", "無線滑鼠", "人體工學滑鼠",
        "4K螢幕", "曲面螢幕", "電競螢幕", "可攜式螢幕",
        "外接硬碟", "SSD硬碟", "NAS", "USB集線器",
        # 相機
        "Sony相機", "Canon相機", "Nikon相機", "Fujifilm相機",
        "GoPro", "DJI空拍機", "隨身相機", "運動相機",
        # 智慧手錶
        "Apple Watch", "Galaxy Watch", "Garmin手錶",
        "Fitbit", "小米手環", "AMAZFIT",
        # 電視
        "OLED電視", "4K電視", "Samsung電視", "LG電視", "Sony電視",
        "小米電視", "TCL電視",
        # 遊戲
        "PS5", "Xbox Series X", "Nintendo Switch",
        "Switch遊戲片", "PS5遊戲", "電競椅", "電競桌",
    ],
    "appliance": [
        # 廚電
        "氣炸鍋", "飛利浦氣炸鍋", "Cosori氣炸鍋",
        "咖啡機", "膠囊咖啡機", "Nespresso", "Lavazza",
        "電鍋", "大同電鍋", "象印電鍋", "虎牌電鍋",
        "果汁機", "調理機", "Vitamix", "Blendjet",
        "烤箱", "小烤箱", "蒸烤箱", "氣炸烤箱",
        "麵包機", "製冰機", "鬆餅機", "章魚燒機",
        "電熱水壺", "保溫壺", "象印保溫杯",
        "IH電磁爐", "鑄鐵鍋", "不沾鍋", "氣炸鍋耗材",
        # 清潔
        "掃地機器人", "dyson吸塵器", "小米掃地機",
        "iRobot Roomba", "吸塵器", "無線吸塵器",
        "洗碗機", "桌上型洗碗機", "空氣清淨機",
        "除濕機", "加濕器", "電風扇", "空調扇",
        # 個護
        "電動牙刷", "音波牙刷", "Oral-B電動牙刷",
        "飛利浦電動牙刷", "沖牙機", "電動沖牙機",
        "吹風機", "dyson吹風機", "負離子吹風機",
        "電動刮鬍刀", "電動除毛刀", "美顏儀",
        "直髮器", "捲髮器", "護髮素",
        # 洗衣
        "洗衣機", "烘衣機", "洗脫烘", "滾筒洗衣機",
    ],
    "food": [
        # 醬料
        "醬油", "薄鹽醬油", "龜甲萬醬油", "金蘭醬油",
        "沙茶醬", "豆瓣醬", "辣椒醬", "番茄醬",
        "芥末", "美乃滋", "凱撒醬", "沙拉醬",
        "米醋", "烏醋", "料理米酒",
        # 主食
        "白米", "越光米", "糙米", "五穀米", "藜麥",
        "義大利麵", "烏龍麵", "蕎麥麵", "冬粉",
        "燕麥片", "麥片", "granola", "即食燕麥",
        # 零食
        "洋芋片", "Pringles", "樂事洋芋片",
        "餅乾", "奧利奧", "消化餅", "小熊餅乾",
        "巧克力", "KitKat", "Toblerone", "費列羅",
        "堅果", "腰果", "杏仁", "核桃", "綜合堅果",
        "果乾", "芒果乾", "蔓越莓乾",
        "糖果", "軟糖", "QQ糖",
        # 飲料
        "咖啡豆", "掛耳咖啡", "即溶咖啡", "三合一咖啡",
        "綠茶包", "紅茶包", "台灣茶", "烏龍茶",
        "運動飲料", "蛋白粉", "乳清蛋白",
        # 健康食品
        "維他命C", "維他命D", "葉酸", "魚油",
        "益生菌", "膠原蛋白", "玻尿酸",
        "蜂蜜", "台灣蜂蜜", "麥盧卡蜂蜜",
    ],
    "beauty": [
        # 保養
        "面膜", "韓國面膜", "SNP面膜", "DR.JOU面膜",
        "精華液", "玻尿酸精華", "維C精華", "A醇精華",
        "乳液", "保濕乳液", "防曬乳", "SPF50防曬",
        "化妝水", "爽膚水", "敏感肌保養",
        "眼霜", "眼膜", "頸霜",
        "洗面乳", "卸妝水", "卸妝油", "潔顏慕斯",
        # 彩妝
        "氣墊粉底", "粉底液", "BB霜", "CC霜",
        "眼線筆", "眼影盤", "睫毛膏",
        "口紅", "唇釉", "唇膏",
        "腮紅", "修容", "高光",
        # 髮品
        "洗髮精", "護髮素", "護髮膜", "頭皮精華",
        "造型噴霧", "造型蠟", "護髮油",
        # 香水
        "香水", "女性香水", "男性香水", "淡香水",
    ],
    "home": [
        # 寢具
        "記憶枕", "乳膠枕", "羽絨枕", "枕頭",
        "棉被", "羽絨被", "四季被", "保暖被",
        "床墊", "記憶床墊", "彈簧床墊",
        # 收納
        "收納箱", "整理箱", "衣物收納", "真空收納袋",
        "鞋架", "衣架", "掛鉤", "磁吸掛鉤",
        "書架", "置物架", "浴室置物架",
        # 燈具
        "LED燈泡", "智慧燈泡", "護眼檯燈",
        "吸頂燈", "床頭燈", "小夜燈", "感應燈",
        # 清潔
        "洗碗精", "洗衣精", "洗衣球", "柔軟精",
        "浴室清潔劑", "馬桶清潔劑", "萬用清潔劑",
        "垃圾袋", "保鮮膜", "廚房紙巾",
    ],
    "tools": [
        # 電動工具
        "電鑽", "牧田電鑽", "BOSCH電鑽", "充電電鑽",
        "電動起子", "衝擊起子", "砂輪機", "電鋸",
        "熱風槍", "電烙鐵", "電磨機",
        # 手工具
        "螺絲起子組", "扳手組", "剪刀", "美工刀",
        "量尺", "水平儀", "鉗子", "老虎鉗",
        # 戶外
        "露營燈", "頭燈", "手電筒",
        "睡袋", "登山背包", "帳篷",
    ],
    "sport": [
        "瑜珈墊", "瑜珈磚", "瑜珈繩",
        "啞鈴", "壺鈴", "彈力帶",
        "跑步機", "飛輪", "划船機",
        "籃球", "足球", "羽球拍", "桌球拍",
        "泳鏡", "泳帽", "浮板",
        "運動水壺", "保溫水壺", "跑步腰包",
        "健身手套", "護膝", "運動護具",
    ],
    "pet": [
        "狗飼料", "貓飼料", "狗零食", "貓零食",
        "貓砂", "礦砂", "豆腐砂", "紙砂",
        "狗窩", "貓窩", "貓跳台", "貓抓板",
        "寵物牽繩", "項圈", "寵物衣服",
        "寵物玩具", "逗貓棒", "狗玩具",
        "寵物推車", "外出包", "航空箱",
    ],
}

# 展平所有關鍵字
ALL_KEYWORDS = []
for cat, kws in KEYWORDS.items():
    for kw in kws:
        ALL_KEYWORDS.append((cat, kw))

print(f"總關鍵字數: {len(ALL_KEYWORDS)}")


async def bulk_crawl_site(site: str, keywords: list[tuple], per_query: int = 40) -> dict:
    """單站批量爬取所有關鍵字"""
    from indexer.crawler import _get_search_fn
    search_fn = await _get_search_fn(site)
    if not search_fn:
        return {"site": site, "indexed": 0, "errors": 0}

    total = 0
    errors = 0
    for cat, kw in keywords:
        try:
            products = await search_fn(kw, limit=per_query)
            for p in products:
                p["category"] = cat
                p["is_accessory"] = 1 if is_accessory(p.get("name",""), kw.split()) else 0
            n = upsert_products(products)
            total += n
            if n > 0:
                print(f"  [{site:10}] {kw:25} +{n}")
            await asyncio.sleep(0.15)
        except Exception as e:
            errors += 1
    return {"site": site, "indexed": total, "errors": errors}


async def run_bulk():
    """20 站同時爆發，每站跑全部關鍵字"""
    sites = [
        "momo", "pchome", "yahoo", "coupang", "ruten",
        "books", "pinecone", "etmall", "carrefour", "buy123",
        "trplus", "elifemall", "tkec", "pinkoi", "biggo",
    ]

    # 每站分到不同子集，避免重複
    chunk = len(ALL_KEYWORDS) // len(sites) + 1
    tasks = []
    for i, site in enumerate(sites):
        start = (i * chunk) % len(ALL_KEYWORDS)
        subset = ALL_KEYWORDS[start:start+chunk] + ALL_KEYWORDS[:max(0, start+chunk-len(ALL_KEYWORDS))]
        tasks.append(bulk_crawl_site(site, subset[:chunk], per_query=40))

    # 也讓 momo/pchome/coupang 跑全部（這三站最重要）
    for site in ["momo", "pchome", "coupang"]:
        tasks.append(bulk_crawl_site(site, ALL_KEYWORDS, per_query=60))

    print(f"\n{'='*60}")
    print(f"Bulk Index — {len(tasks)} 個並發任務")
    print(f"關鍵字總數: {len(ALL_KEYWORDS)}")
    print(f"開始: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

    t0 = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - t0

    stats = get_stats()
    total = sum(r.get("indexed",0) for r in results if isinstance(r, dict))

    print(f"\n{'='*60}")
    print(f"完成: {datetime.now().strftime('%H:%M:%S')}")
    print(f"耗時: {elapsed:.0f}s")
    print(f"本輪新增: {total:,} 筆")
    print(f"DB 總量: {stats['total_products']:,} 筆")
    print(f"\n各站:")
    for site, cnt in sorted(stats["sites"].items(), key=lambda x:-x[1]):
        bar = "█" * min(cnt//50, 40)
        print(f"  {site:15} {cnt:6,} {bar}")
    print(f"{'='*60}")


if __name__ == "__main__":
    init_db()
    asyncio.run(run_bulk())
