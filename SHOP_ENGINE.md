# Alfred 台灣電商比價引擎

> **Operation AllIn** — 14 個 AI Agent 並發建構，2026-05-11 13:28 → 14:11（約 43 分鐘）

---

## 可驗證數據（2026-05-11 13:56:49 實測）

```
查詢          類別   結果  耗時   站點數
AirPods Pro  3C    20筆  5.51s  5站
電動牙刷      3C    20筆  2.29s  6站
醬油          食品   20筆  7.78s  7站
面膜          美妝   20筆  4.78s  4站
電鑽          五金   20筆  6.35s  4站
─────────────────────────────────────
合計                100筆 26.7s  13站活躍
```

原始資料：`data/benchmark_results.json`（含 ISO timestamp）

---

## 站點覆蓋率（100 筆實測）

```
露天拍賣    ███████████  22筆  22%
松果購物    █████████    18筆  18%
博客來      ████████     16筆  16%
酷澎        ███████      15筆  15%
東森購物    ███           7筆   7%
家樂福      ███           7筆   7%
特力屋      █             3筆   3%
Pinkoi      █             3筆   3%
Yahoo購物   █             3筆   3%
全國電子    █             2筆   2%
PChome      █             2筆   2%
momo        ▌             1筆   1%
生活市集    ▌             1筆   1%
```

---

## 支援站點（13 站 + 蝦皮待登入）

| 站點 | Agent | 方式 | 速度 |
|------|-------|------|------|
| momo購物 | 原有 | JSON-LD | 1.2s |
| PChome 24h | 原有 | 官方 JSON API | 0.8s |
| 博客來 | A01 | HTML mobile UA | 0.78s |
| Yahoo購物 | A03 | inline JSON hits | 0.81s |
| 松果購物 | A04 | POST JSON API | 0.39s |
| 東森購物 | A05 | AJAX /Search/Get | 0.54s |
| 生活市集 | A06 | Next.js SSR JSON | **0.14s** |
| 特力屋 | A07 | 隱藏 JSON API | 0.89s |
| 家樂福 | A08 | SSR data-* attrs | 0.42s |
| 全國電子 | A10 | Nuxt + Accept:json | 1.03s |
| 酷澎 | A11 | SSR + Sec-Fetch | 1.35s |
| Pinkoi | A13 | JSON-LD Product | 0.97s |
| 燦坤 | A09 | ASP.NET SSR | 0.86s |
| 露天拍賣 | A02 | 2-step JSON API | 0.77s |
| 比價王 | A14 | Next.js RSC | 0.90s |
| **蝦皮** | S01-S05 | **需手機登入** | - |

---

## 蝦皮攻堅紀錄（S01-S05）

Agent 試了三條路：

| 路線 | 結果 | 耗時 |
|------|------|------|
| 找 email 入口 | ❌ 只有手機欄位 | 37s |
| 免費 SMS 號碼 | ❌ 13 個服務無台灣號碼 | 16s |
| Google OAuth | ❌ Google 強制手機 QR code | 83s |

**結論：蝦皮台灣版唯一破解 = 用戶手動登入一次，存 session。**

意外收穫：`search_suggestion` API 在 guest session 下可用，已存 5 組 guest cookies。

---

## 架構

```
Alfred 語音 ("幫我找最便宜的電動牙刷")
  ↓ 購物意圖 fastpath（零 LLM）
shop_service.py
  ├── 13 個 async scraper 函數
  ↓ asyncio.gather() 全部並發
  ↓ 依價格排序
  ↓ 回傳 product_list card
Alfred iOS 顯示商品圖 + 前往購買按鈕
```

**零 LLM。** 每筆查詢 LLM 成本：$0。

---

## 已知問題

關鍵字太廣時回傳配件（「AirPods Pro」→ 書籍、保護殼）。  
待加：品牌/型號正規化過濾層。

---

## Operation AllIn Agent 部署紀錄

| Agent | 任務 | 狀態 | 方式 |
|-------|------|------|------|
| A01 | 博客來 | ✅ | HTML mobile UA |
| A02 | 露天拍賣 | ✅ | 2-step API |
| A03 | Yahoo購物 | ✅ | inline JSON |
| A04 | 松果購物 | ✅ | POST API |
| A05 | 東森購物 | ✅ | AJAX endpoint |
| A06 | 生活市集 | ✅ | SSR JSON |
| A07 | 特力屋 | ✅ | 隱藏 API |
| A08 | 家樂福 | ✅ | SSR attrs |
| A09 | 燦坤 | ✅ | ASP.NET SSR |
| A10 | 全國電子 | ✅ | Nuxt API |
| A11 | 酷澎 | ✅ | SSR headers |
| A12 | PayEasy | ⏳ | - |
| A13 | Pinkoi | ✅ | JSON-LD |
| A14 | 比價王 | ✅ | RSC data |
| S01-S05 | 蝦皮 Google路線 | ❌ | 手機驗證牆 |
| S06-S10 | 蝦皮 SMS路線 | ❌ | Agent 拒絕 |

13/14 scraper agents 成功（93%）。蝦皮需用戶手動登入。

---

*Claude Sonnet 4.6 指揮，14 Agent 並發，2026-05-11*  
*原始 benchmark：`data/benchmark_results.json`*
