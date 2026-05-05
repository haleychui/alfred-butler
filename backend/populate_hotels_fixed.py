#!/usr/bin/env python3
"""Fixed hotel insert — no name_en in main tuple, update separately."""
import sqlite3

DB = "/opt/alfred/data/alfred.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

# Clear any partial hotels from previous run
c.execute("DELETE FROM travel_hotels")

# (country, city, name, style, price_level, audience, description, highlights, tips, tags, lat, lng)
hotels = [
    # ── 台北 ──
    ("台灣","台北","W台北","luxury",4,"couple,business","信義區時尚設計旅館，屋頂泳池夜景超美","屋頂WET BAR夜景、泳池、SPA","周五六假日較貴，平日划算","W飯店,設計,信義,奢華",25.0373,121.5653),
    ("台灣","台北","台北君悅大飯店","luxury",4,"business,couple","信義區五星，緊鄰世貿中心","健身房、泳池、多家餐廳","捷運信義安和步行5分","君悅,五星,信義",25.0301,121.5690),
    ("台灣","台北","寒舍艾美酒店","luxury",3,"couple,business","信義商圈五星，設計感強","艾美藝廊展覽、頂樓景觀餐廳","週末早鳥優惠","艾美,五星,信義",25.0360,121.5672),
    ("台灣","台北","老爺行旅 The Place Taipei","boutique",3,"couple","中山北路精品旅館，台灣設計感","台灣設計師作品裝潢、健身房","中山捷運站步行3分","精品,設計,中山",25.0521,121.5238),
    ("台灣","台北","背包客棧 Star Hostel Taipei","budget",1,"backpacker","台北最佳青年旅舍，中正紀念堂旁","公共廚房、免費早餐、旅遊資訊","提前3天訂","青旅,背包客,台北",25.0346,121.5208),
    ("台灣","台北","福華大飯店","business",2,"business,family","仁愛路老字號商務飯店","台北最有歷史感的五星","政治商業人士必住","福華,商務,仁愛路",25.0402,121.5494),
    ("台灣","台北","台北文華東方酒店","luxury",4,"couple,business","敦化北路五星，全台最頂級酒店之一","室內泳池、SPA、多家米其林級餐廳","外帶早餐值得","文華東方,台北,頂級",25.0471,121.5501),

    # ── 台中 ──
    ("台灣","台中","日月千禧酒店 Millennium","luxury",3,"business,couple","台中七期豪宅商圈","頂樓Sky Bar、台中夜景","七期市政府捷運站旁","千禧,五星,台中",24.1633,120.6458),
    ("台灣","台中","台中亞緻大飯店","business",2,"business","中心商圈老字號","近逢甲、商業區","逢甲夜市步行10分","亞緻,台中",24.1541,120.6720),

    # ── 高雄 ──
    ("台灣","高雄","漢來大飯店","luxury",3,"business,family","高雄最大五星，漢神百貨旁","全台最大Buffet 漢來海港、頂樓泳池","漢神巨蛋旁","漢來,五星,高雄",22.6695,120.3008),
    ("台灣","高雄","高雄君鴻國際酒店","luxury",4,"couple,business","85大樓全台最高酒店","85樓景觀餐廳、全高雄最高住宿","夜景無敵","君鴻,85樓,高雄",22.6283,120.3014),
    ("台灣","高雄","寒軒國際大飯店","luxury",3,"business","高雄五星，靠近高雄車站","健身房、多家餐廳","高雄車站步行10分","寒軒,高雄,五星",22.6407,120.3001),

    # ── 台南 ──
    ("台灣","台南","台南大員皇冠假日酒店","luxury",3,"couple,family","安平港旁，台南最美海景酒店","港景泳池、安平古堡步行","周末早早訂","皇冠假日,台南,海景",22.9929,120.1635),
    ("台灣","台南","台南晶英酒店","luxury",3,"couple","台南火車站旁五星","頂樓泳池、台南故事館展覽","台南車站步行3分","晶英,台南,五星",22.9972,120.2016),

    # ── 日本 東京 ──
    ("日本","東京","安縵東京 Aman Tokyo","luxury",4,"couple","大手町天空中的絕美和風酒店","日式枯山水、頂樓泳池、城下俯瞰","開館前一年訂位","安縵,超奢華,東京",35.6855,139.7635),
    ("日本","東京","東京柏悅 Park Hyatt Tokyo","luxury",4,"couple,business","《迷失東京》電影場景，新宿52F起","Peak Bar夜景、頂樓泳池","新宿捷運步行","柏悅,新宿,迷失東京",35.6866,139.6904),
    ("日本","東京","星野集團東京 HOSHINOYA","luxury",4,"couple","日本橋水上和風旅宿","划船入住、日本料理、和式SPA","完全和式體驗","星野,和風,東京",35.6861,139.7759),
    ("日本","東京","BnA Alter Museum","boutique",2,"backpacker,couple","秋葉原藝術家設計旅館","每間房間是獨立藝術品","秋葉原步行3分","藝術旅館,設計,秋葉原",35.7026,139.7750),
    ("日本","東京","The Millennials Shibuya","budget",1,"backpacker","澀谷設計青旅，免費晚間啤酒","躺椅式床架、設計感強","澀谷捷運步行3分","青旅,澀谷,設計",35.6624,139.6962),

    # ── 日本 京都 ──
    ("日本","京都","俵屋旅館 Tawaraya","luxury",4,"couple","300年京都最古老旅館，待過名人無數","日本最高端旅館体驗、茶道、庭園","超難訂位，提前3個月","俵屋,京都旅館,頂級",35.0113,135.7614),
    ("日本","京都","星野集團 ROKU KYOTO","luxury",4,"couple","鷹峯嵐山腳下，設計和風旅館","茶道、陶藝體驗、嵐山景","嵐山地區","星野,嵐山,京都",35.0355,135.7163),
    ("日本","京都","京都町家民宿","boutique",2,"couple,backpacker","京町家改建，體驗本地生活","傳統格局、共用廚房","二條城步行","町家,京都,文化",35.0156,135.7535),

    # ── 日本 大阪 ──
    ("日本","大阪","The St. Regis Osaka","luxury",4,"couple,business","御堂筋大阪最豪華酒店","管家服務、頂層Il Cielo意式餐廳","本町捷運旁","瑞吉,大阪,豪華",34.6912,135.4980),
    ("日本","大阪","CROSS HOTEL Osaka","budget",1,"backpacker","難波心齋橋旁設計平價旅館","位置絕佳","心齋橋步行5分","平價,大阪,心齋橋",34.6707,135.4997),

    # ── 日本 沖繩 ──
    ("日本","沖繩","萬麗度假村 Renaissance Okinawa","resort",3,"family","恩納村海灘度假村","私人海灘、浮潛、珊瑚礁、海豚互動","夏天需提前預訂","沖繩,度假村,海灘",26.4350,127.7960),
    ("日本","沖繩","Halekulani Okinawa","luxury",4,"couple","恩納村全球頂級度假村","無邊際泳池俯瞰海洋、老爺車接送","含早餐","頂級,沖繩,海景",26.5200,127.8300),

    # ── 韓國 首爾 ──
    ("韓國","首爾","新羅酒店 The Shilla Seoul","luxury",4,"couple,business","首爾最高端酒店之一","頂樓泳池、新羅免稅店直連","韓國總統常宴客地","新羅,首爾,頂級",37.5573,126.9977),
    ("韓國","首爾","樂天飯店首爾","luxury",3,"business,family","樂天百貨頂部酒店","直通樂天百貨購物、中心地點","明洞旁","樂天,首爾,百貨",37.5640,126.9834),
    ("韓國","首爾","Ryse Autograph Collection","boutique",3,"couple","弘大藝術風格設計酒店","每層不同藝術家設計","弘大步行5分","弘大,設計,首爾",37.5566,126.9238),
    ("韓國","首爾","Gravity Seoul Pangyeo","boutique",2,"couple","江南設計酒店","屋頂酒吧夜景","盆唐線旁","江南,設計,首爾",37.3944,127.1234),

    # ── 東南亞 峇里島 ──
    ("東南亞","峇里島","Four Seasons Resort Bali at Sayan","resort",4,"couple","烏布叢林河谷度假村，全球最美酒店之一","無邊際泳池、熱帶雨林、瑜珈","提前1個月訂","四季,峇里島,叢林",8.5114,115.2593),
    ("東南亞","峇里島","COMO Uma Ubud","resort",3,"couple","烏布山景精品酒店","有機料理、溫泉SPA、yoga課","靜謐，無孩童","精品,烏布,SPA",8.5068,115.2554),
    ("東南亞","峇里島","Potato Head Beach Club","boutique",2,"backpacker,couple","水明漾海灘酒店兼夜店","泳池趴、海景Bar、DJ","Seminyak最in地點","時尚,海灘,酒吧",8.6886,115.1616),
    ("東南亞","峇里島","Alaya Resort Ubud","boutique",2,"couple","烏布中心精品酒店","無邊際泳池、下午茶","走路到烏布皇宮","精品,烏布,泳池",8.5073,115.2621),

    # ── 泰國 曼谷 ──
    ("東南亞","曼谷","曼谷半島酒店","luxury",4,"couple,business","昭披耶河畔最頂級酒店","直升機停機坪、河景無邊際泳池","BTS Saphan Taksin下","半島,曼谷,河景",13.7222,100.5112),
    ("東南亞","曼谷","137 Pillars Suites Bangkok","boutique",3,"couple","中心商圈精品全套房酒店","每間獨立套房、主廚早餐","NANA BTS旁","精品套房,曼谷",13.7445,100.5636),
    ("東南亞","曼谷","Lub d Bangkok Silom","budget",1,"backpacker","曼谷最佳設計青旅","泳池、酒吧、早餐自助","BTS Surasak旁","青旅,曼谷,設計",13.7249,100.5218),

    # ── 泰國 清邁 ──
    ("東南亞","清邁","Four Seasons Chiang Mai","resort",4,"couple","稻田中的度假村，全球最美之一","私人稻田、水牛體驗、無邊際泳池","Mae Rim Valley","四季,清邁,稻田",18.8735,98.9528),
    ("東南亞","清邁","Rachamankha","boutique",3,"couple","古城內蘭納風格精品酒店","庭院游泳池、古蹟景觀","古城步行到寺廟","精品,清邁,古城",18.7871,98.9843),

    # ── 泰國 普吉 ──
    ("東南亞","普吉島","Sri Panwa","resort",4,"couple","普吉東岸半島私人度假村","無邊際泳池別墅、私人碼頭","需開車到普吉市區","普吉,別墅,海景",7.8651,98.4340),
    ("東南亞","普吉島","Trisara Phuket","resort",4,"couple","普吉北岸私人海灣奢華別墅","私人泳池別墅、直達海灘","包車40分","奢華,普吉,私人泳池",8.1160,98.2795),

    # ── 越南 ──
    ("東南亞","河內","Sofitel Legend Metropole Hanoi","luxury",4,"couple,business","1901年建法殖民地飯店，河內最著名","歷史建築、戰時地下室、Charlie Chaplin住過","法國殖民風格","索菲特,河內,歷史",21.0259,105.8530),
    ("東南亞","胡志明市","Park Hyatt Saigon","luxury",3,"couple,business","歌劇院廣場旁，西貢頂級飯店","法式花園庭院、頂樓游泳池","Dong Khoi旁","柏悅,西貢,法式",10.7793,106.7030),
    ("東南亞","會安","Four Seasons The Nam Hai","resort",4,"couple","會安南海四季，全球最美沙灘度假村","私人沙灘、無邊際泳池","距古城15分車","四季,會安,沙灘",15.9155,108.3500),

    # ── 杜拜 ──
    ("中東","杜拜","帆船飯店 Burj Al Arab","luxury",4,"couple","全球唯一7星級，帆形地標","直升機抵達、金色室內、水下餐廳","下午茶入場費約300 AED","帆船飯店,七星,杜拜",25.1412,55.1853),
    ("中東","杜拜","亞特蘭蒂斯棕梠島","resort",3,"family","棕梠島海洋主題度假村","Aquaventure水上樂園、海底水族館套房","家庭首選","亞特蘭蒂斯,棕梠島,水上樂園",25.1300,55.1172),
    ("中東","杜拜","One&Only One Za'abeel","luxury",4,"couple","哈里發塔旁，世界最高懸浮大廳","頂層餐廳、無邊際泳池、城市景觀","哈里發塔步行","頂級,杜拜,設計",25.2014,55.2773),

    # ── 法國 巴黎 ──
    ("歐洲","巴黎","麗思飯店 Hôtel Ritz Paris","luxury",4,"couple","全球最頂級飯店，凡登廣場旁","Hemingway Bar、Coco Chanel套房、頂級SPA","凡登廣場","麗思,巴黎,頂級",48.8679,2.3299),
    ("歐洲","巴黎","莫里斯酒店 Le Meurice","luxury",4,"couple","杜樂麗花園旁，達利最愛酒店","米其林三星餐廳、凡爾賽宮式裝潢","對面杜樂麗花園","莫里斯,巴黎,頂級",48.8649,2.3278),
    ("歐洲","巴黎","Generator Paris","budget",1,"backpacker","巴黎最佳設計青旅，11區","屋頂Bar、共用空間超美","République Metro旁","青旅,設計,巴黎",48.8638,2.3735),
    ("歐洲","巴黎","Hôtel Plaza Athénée","luxury",4,"couple","艾菲爾鐵塔景觀飯店，蒙田大道","酒紅色頂棚、Alain Ducasse三星餐廳","騎腳踏車到艾菲爾鐵塔","頂級,巴黎,艾菲爾景觀",48.8664,2.3062),

    # ── 英國 倫敦 ──
    ("歐洲","倫敦","The Savoy","luxury",4,"couple,business","泰晤士河畔百年老飯店，1889年","下午茶、美國酒吧、Art Deco裝潢","柯芬園旁","莎芙,倫敦,頂級",51.5104,-0.1208),
    ("歐洲","倫敦","Claridge's","luxury",4,"couple,business","梅菲爾Art Deco酒店，皇室最愛","下午茶、Gordon Ramsay餐廳","Bond St旁","Claridges,倫敦,頂級",51.5143,-0.1476),
    ("歐洲","倫敦","Generator London","budget",1,"backpacker","倫敦最佳青旅，Bloomsbury區","大英博物館走路5分","Goodge St Metro旁","青旅,設計,倫敦",51.5231,-0.1329),

    # ── 義大利 羅馬 ──
    ("歐洲","羅馬","Hotel Hassler Roma","luxury",4,"couple","西班牙廣場頂端，羅馬最佳景觀","俯瞰羅馬全景、Imàgo米其林餐廳","西班牙廣場步行","哈斯勒,羅馬,頂級",41.9059,12.4824),
    ("歐洲","羅馬","Hotel de Russie","luxury",4,"couple,business","波波洛廣場旁，義大利名人最愛","花園Stravinskij Bar、SPA","波波洛廣場","頂級,羅馬,花園",41.9096,12.4775),

    # ── 西班牙 巴塞隆納 ──
    ("歐洲","巴塞隆納","Hotel Arts Barcelona","luxury",4,"couple","海岸高塔酒店，奧運港旁","無邊際泳池海景、Michelin餐廳","Barceloneta步行","高塔,巴塞隆納,海景",41.3884,2.1996),
    ("歐洲","巴塞隆納","Casa Camper Barcelona","boutique",2,"couple,backpacker","老城精品設計酒店","24小時免費小吃、頂層露台","Raval區，哥德區步行","設計,巴塞隆納,精品",41.3814,2.1697),

    # ── 美國 ──
    ("美國","紐約","The Plaza Hotel","luxury",4,"couple","中央公園旁，《小鬼當家》飯店","玫瑰酒吧、Palm Court下午茶","第五大道旁","Plaza,紐約,百年飯店",40.7647,-73.9748),
    ("美國","紐約","The Standard High Line","boutique",3,"couple","肉品加工區High Line旁，落地窗設計","可見哈德遜河、設計感強","Chelsea，步行High Line","Standard,紐約,設計",40.7401,-74.0077),
    ("美國","紐約","HI NYC Hostel","budget",1,"backpacker","紐約最大青旅，上西區","中央公園步行5分","86 St地鐵旁","青旅,紐約,上西區",40.7823,-73.9796),
    ("美國","夏威夷","Halekulani","luxury",4,"couple","威基基最頂級度假村","無邊際泳池、蘭花海景、La Mer餐廳","威基基海灘正對","哈利庫拉尼,夏威夷,度假",21.2812,-157.8346),
    ("美國","夏威夷","Turtle Bay Resort","resort",3,"family","歐胡島北岸衝浪海灘度假村","衝浪課、馬術、海豚灣","北岸45分車","衝浪,北岸,夏威夷",21.6786,-158.0123),
    ("美國","拉斯維加斯","百樂宮 Bellagio","luxury",3,"couple","噴泉秀正對面，Strip中心","噴泉景觀房、賭場、SPA、美食","噴泉景觀房加錢值得","百樂宮,拉斯維加斯,噴泉",36.1126,-115.1767),

    # ── 印度 ──
    ("印度","阿格拉","Oberoi Amarvilas","luxury",4,"couple","泰姬瑪哈陵直視景觀酒店，距200m","每間房都看得到泰姬、無邊際泳池","全球最佳景觀酒店之一","奧貝羅伊,阿格拉,泰姬瑪哈陵",27.1707,78.0451),
    ("印度","孟買","Taj Mahal Palace Mumbai","luxury",4,"business,couple","1903年老飯店，孟買最象徵","印度門景觀、下午茶","印度門旁","泰姬,孟買,頂級",18.9217,72.8330),
    ("印度","新德里","The Imperial New Delhi","luxury",3,"couple,business","殖民地時代白色宮殿，康諾特廣場旁","1931年建築、下午茶儀式","康諾特廣場步行","帝國飯店,德里,殖民",28.6270,77.2173),
]

c.executemany("""INSERT INTO travel_hotels
    (country,city,name,style,price_level,audience,description,highlights,tips,tags,lat,lng)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", hotels)
print(f"Inserted {len(hotels)} hotels")

# Update Michelin stars for existing restaurants
michelin_map = {
    "祥雲龍吟": 3, "RAW": 2, "態芮 tàimo": 2, "山海樓": 1,
    "鼎泰豐（信義店）": 1, "林東芳牛肉麵": 1, "金峰魯肉飯": 1,
    "瓢亭": 3, "一蘭拉麵": 1, "添好運": 1, "鏞記酒家": 1,
    "L'Ambroisie": 3, "Dishoom": 1, "Jay Fai": 1,
    "Locavore": 1, "Peter Luger Steak House": 1, "Joël Robuchon": 3,
    "陳玉華 一隻雞": 1, "欣葉台菜（中山北路）": 1,
    "Per Se": 3, "Le Bernardin": 3, "Eleven Madison Park": 3,
    "El Celler de Can Roca": 3,
    "菊乃井 本店": 3, "鮨 さいとう": 3,
    "龍景軒 L'Atelier de Joël Robuchon": 3, "唐閣": 3,
    "Alain Ducasse au Plaza Athénée": 3, "Arpège": 3, "Le Cinq": 3,
}
for name, stars in michelin_map.items():
    c.execute("UPDATE travel_restaurants SET michelin_stars=? WHERE name=?", (stars, name))
print(f"Updated Michelin stars")

conn.commit()
conn.close()
print("Done!")
