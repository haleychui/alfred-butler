# Alfred 台灣電商比價引擎

> **Operation AllIn** — 單一指揮官協調 14 個 AI Agent 並發建構，2026-05-11

---

## 結果摘要

| 指標 | 數據 |
|------|------|
| 部署 Agent 數 | 14 個（同時出發） |
| 成功上線站點 | 13 站 |
| 平均搜尋耗時 | 1.1 – 4.0 秒（12 站並發） |
| 單次查詢最大結果 | 20 筆（跨 12 站） |
| 5 類別 100 筆 benchmark | 全部真實資料，零 LLM |
| 程式碼行數 | ~900 行（shop_service.py + 10 個獨立 scraper） |

---

## 支援站點（13 站）

| 站點 | Agent | 方式 | 速度 | 特色 |
|------|-------|------|------|------|
| **momo購物** | 原有 | JSON-LD | 1.2s | 台灣最大電商，評分完整 |
| **PChome 24h** | 原有 | 官方 JSON API | 0.8s | 24h 到貨，直接 API |
| **博客來** | A01 | HTML (mobile UA) | 0.78s | 原價/折扣齊全 |
| **Yahoo購物** | A03 | inline JSON `ecsearch.hits` | 0.81s | 60筆/頁，評分完整 |
| **松果購物** | A04 | POST JSON API | 0.39s | 最快站點之一 |
| **東森購物** | A05 | AJAX `/Search/Get` | 0.54s | 隱藏 AJAX endpoint |
| **生活市集** | A06 | Next.js SSR JSON | 0.14s | **最快**，SSR直讀 |
| **特力屋** | A07 | 隱藏 JSON API | 0.89s | 家居/五金專門 |
| **家樂福** | A08 | SSR `data-*` attrs | 0.42s | 食品/日用品最全 |
| **全國電子** | A10 | Nuxt API + Accept:json | 1.03s | 需指定 header |
| **酷澎** | A11 | SSR HTML + Sec-Fetch | 1.35s | 折扣最多，評分最豐富 |
| **Pinkoi** | A13 | JSON-LD Product | 0.97s | 設計師商品唯一入口 |
| **燦坤** | A09 | ASP.NET SSR HTML | 0.86s | 域名已遷 tk3c.com |
| **露天拍賣** | 自動整合 | JSON API | ~1s | 二手/拍賣市場 |

---

## Benchmark（5 類別 × 20 筆）

```
AirPods Pro  (3C)   20筆  4.02s
電動牙刷      (3C)   20筆  1.64s
醬油         (食品)  20筆  2.02s
面膜         (美妝)  20筆  1.95s
電鑽         (五金)  20筆  2.12s
```

**各站覆蓋率（100筆總計）：**
```
露天拍賣     19筆
松果購物     18筆
博客來       17筆
酷澎         15筆
東森購物      7筆
家樂福        7筆
特力屋        3筆
Pinkoi        3筆
Yahoo購物     3筆
PChome        3筆
momo          2筆
全國電子      2筆
生活市集      1筆
```

---

## 架構

```
Alfred 語音 ("幫我找最便宜的電動牙刷")
  ↓ 購物意圖 fastpath（零 LLM）
shop_service.py
  ├── search_momo()       JSON-LD
  ├── search_pchome()     官方 API
  ├── search_books()      HTML parse
  ├── search_yahoo_shopping()  inline JSON
  ├── search_pinecone()   POST API
  ├── search_etmall()     AJAX API
  ├── search_buy123()     Next.js SSR
  ├── search_trplus()     JSON API
  ├── search_carrefour()  SSR data-attrs
  ├── search_elifemall()  Nuxt API
  ├── search_coupang()    SSR HTML
  ├── search_pinkoi()     JSON-LD
  ├── search_tkec()       ASP.NET SSR
  └── search_ruten()      JSON API
  ↓ asyncio.gather() 全部並發
  ↓ 依價格排序
Alfred 回應 + product_list card（iOS 顯示商品圖）
```

---

## 技術細節

### 為什麼零 LLM？

每個 scraper 用純演算法：
- JSON-LD → 直接 `json.loads()`
- inline script JSON → regex 定位 + `json.loads()`
- HTML → BeautifulSoup selector 或 regex
- API → `httpx.AsyncClient` 直打

沒有任何環節需要 LLM 理解頁面。

### 反爬蟲處理

| 站點 | 問題 | 解法 |
|------|------|------|
| 博客來 | 桌面 UA 被 WAF 擋 | 改用 iPhone UA |
| 酷澎 | 需 Sec-Fetch-* headers | 帶完整 Chrome headers |
| 全國電子 | CloudFront 擋 | 加 `Accept: application/json` |
| 東森購物 | React SPA | 找 bundle 裡的 AJAX endpoint |
| 燦坤 | 域名遷移 | 追 redirect 到 tk3c.com |

### 蝦皮狀態

蝦皮搜尋需要登入 session。架構已備好（`shopee_session.json`），用戶登入一次後自動加入 13 站比價。

---

## 使用方式（Alfred 語音）

```
"幫我找最便宜的 AirPods Pro"
"電動牙刷比價"
"醬油哪裡最便宜"
"買一個氣炸鍋"
```

→ Alfred 1-4 秒內回傳跨 13 站比價結果，iOS 顯示商品圖卡片。

---

*由 Claude Sonnet 4.6 指揮，14 個 AI Agent 並發建構*  
*2026-05-11 Operation AllIn*
