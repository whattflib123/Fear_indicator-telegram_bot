# Fear Indicator Telegram Bot (BTC)

[English README](README_EN.md)

這是一個會自動抓取 BTC 市場情緒資料、生成圖表，並推送到 Telegram 的小工具。

## Telegram 訊息格式

程式會輸出：

```text
📊 BTC 市場情緒更新
🧭 最新指數：52（中性 😐）
🔁 與前次相比：+3
🕒 時間：2026-02-14 12:00 UTC
🔗 spearman相關性:0.32（偏弱，正相關 📈）
```
![BTC Fear and Greed Last 6 Months](docs/sample_chart.png)


## 為什麼要看 Fear & Greed 指數？

加密市場常被情緒主導。Fear & Greed Index 可把市場心理量化成 `0 ~ 100`：
- `0~19`: 極度恐懼
- `20~39`: 恐懼
- `40~59`: 中性
- `60~79`: 貪婪
- `80~100`: 極度貪婪

用途重點：
- 協助判斷市場是否過度恐慌或過度樂觀
- 避免只憑主觀感覺追高殺低
- 搭配價格與風險控管，作為「輔助指標」而非單一買賣依據

## 為什麼這裡用 Spearman 相關性？

本專案計算的是：
- BTC `1日報酬率`
- Fear & Greed 指數 `1日報酬率`

再用 Spearman 相關性評估兩者在近 6 個月的「同向/反向關係」。

選 Spearman 的原因：
- 對非線性但單調關係更穩健
- 對極端值相較於 Pearson 更不敏感
- 適合金融時間序列常見的噪音和異常波動

注意：相關性不代表因果關係，只是描述關係強弱與方向。

## 功能

- 抓取 Alternative.me 的 Crypto Fear & Greed Index
- 抓取 CoinGecko 的 BTC 日價格
- 產生近 6 個月圖表
- 計算近 6 個月 Spearman 相關性（缺值以前一天補值）
- 發送「中文摘要 + 圖片」到 Telegram


## 專案結構

```text
.
├─ src/
│  └─ fear_indicator.py
├─ docs/
│  └─ sample_chart.png
├─ output/
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ README.md
└─ README_EN.md
```

## 安裝與執行

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

建立 `.env`：

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

執行：

```bash
python src/fear_indicator.py
```

可自訂圖檔輸出路徑：

```bash
python src/fear_indicator.py --chart-path output/fear_greed_last_6_months.png
```


## Notes

- 本工具提供市場關係觀察，不構成投資建議
- 相關性不代表因果關係
- 建議透過排程每天執行一次，方便持續監控市場情緒變化
