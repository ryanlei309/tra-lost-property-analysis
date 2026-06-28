# 臺鐵遺失物營運分析 — Prototype

> TRA Lost-Property Operational Analysis. Linking ~24k lost-item records (2022–2023) with
> daily station ridership and the station master to surface where items are lost, what is lost,
> and the "reclaim friction" created by centralised storage. Python data pipeline; Tableau for the final viz.

本專案以臺鐵公開資料，分析「遺失物」的營運樣態。這是 prototype 階段，用來驗證資料能否
串接、分析方向是否成立。

## 分析三條主線
1. **遺失率與離群站**：以 `每萬人次遺失件數` 正規化，找出「掉得比人流預期多/少」的車站。
2. **品類與價值側寫**：遺失物以關鍵字分類，並標註價值層級與是否可追回失主。
3. **逆物流 / 領回摩擦**：遺失物最終集中保管的地點 vs 實際遺失地點。

## 資料管線架構（程式依此分層）
```
來源        遺失物XML │ 進出站CSV(2022-23) │ 車站基本資料JSON │ TDX時刻表API(待接)
              │              │                  │
解析清理   parse_lost_property / parse_ridership  ── 站碼補零、車次/車站拆分、品類標註
              │
核心表      dim_station │ fact_lost │ fact_ridership   (build_tables)
              │
分析指標    遺失率離群 │ 品類價值 │ 逆物流            (analyze)
              │
呈現        Tableau（讀 data/processed 的乾淨表）
```

## 專案結構
```
src/
  config.py              路徑與分析期間常數
  categorize.py          ★ 品類/價值/可追回 分類規則（分析核心，需人工檢視）
  parse_lost_property.py 遺失物 XML -> fact_lost
  parse_ridership.py     人流 CSV -> fact_ridership；車站 JSON -> dim_station
  build_tables.py        組 agg_station（含方法論護欄）
  analyze.py             分析指標 + 產圖
  run_prototype.py       主程式（串起整條管線）
data/raw/                原始資料（.gitignore，需自行放入）
data/processed/          產出的乾淨表（.gitignore，可重建）
outputs/figures/         分析圖
outputs/tables/          分析表
```

## 執行方式
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 把四份原始資料放進 data/raw/，檔名見 config.py
python -m src.run_prototype
```

## 資料來源
- 遺失物資料集、每日各站進出站人數、車站基本資料集：政府資料開放平臺 data.gov.tw
- 列車時刻：TDX 運輸資料流通服務平臺 API（`src/fetch_tdx.py`）

## TDX 時刻表抓取
1. 在專案根目錄建立 `.env`（參考 `.env.example`），填入 `TDX_CLIENT_ID` / `TDX_CLIENT_SECRET`。
2. 先確認回傳格式：`python -m src.fetch_tdx --inspect`
3. 正式抓取並輸出 `data/processed/dim_train.csv`：`python -m src.fetch_tdx`
   - 使用「定期車次時刻表」近似當年車次路線（已知近似，報告須註明）。
   - `dim_train.stop_ids` 為停靠站代碼，可對應 `dim_station.sta_code`。

## 已知限制（誠實揭露）
- 遺失物約 **63%** 只記到「車次」、不知掉在哪一站；站別遺失率僅用「車站」紀錄計算。
- 遺失物期間為 2022-01 ~ 2023-07，**2023 僅上半年**，做月份/季節分析時須留意。
- 價值層級為主觀分類（見 `categorize.py`，v2，提供細類與大類兩層），仍可再精修。
- 離群分析已設最低件數門檻（`config.MIN_LOSS_COUNT`，預設 20）以排除低件數雜訊。
- 資料僅含「被拾獲登記」的物品，無法反映從未被尋獲、或被私自取走的遺失物。

## 主要產出（outputs/figures）
- `01_loss_rate_outliers.png`：遺失件數 vs 人流，離群站
- `02_category_value.png`：品類與價值層級分布
- `03_reverse_logistics.png`：保管站集中度
- `04_channel_flow.png`：站內 vs 車上遺失的流向（Sankey）
- `05_loss_rate_map.png` / `.html`：全臺站別遺失率地圖（含互動版）

## 備註
本 repo 為個人作品集用途。若用於競賽投稿，請注意投稿文件需匿名，
**勿將含個人資訊的本 repo 連結放入投稿 PDF**。
