# 臺鐵遺失物開放資料分析

以臺鐵三項政府開放資料與 TDX 列車時刻，建立可重複執行的資料管線，分析遺失物
「掉在哪、掉了什麼、如何流動、為何難以領回」，並提出低成本的管理改善建議。

## 資料來源
- 遺失物資料集、每日各站進出站人數、車站基本資料集（政府資料開放平臺 data.gov.tw）
- 列車時刻：TDX 運輸資料流通服務平臺 API

## 環境需求
- Python 3.10+
- `pip install -r requirements.txt`

## 資料放置（原始資料不入庫，需自行下載）
將四個原始檔放入 `data/raw/`（因 `.gitignore` 排除，故 clone 後需自行放置）：
- `遺失物資料集.xml`
- `車站基本資料集.json`
- `每日各站進出站人數2022.csv`、`每日各站進出站人數2023.csv`

TDX 金鑰請放專案根目錄 `.env`（格式見 `.env.example`）：
```
TDX_CLIENT_ID=你的ID
TDX_CLIENT_SECRET=你的SECRET
```

## 執行流程
```bash
# (選) 先抓 TDX 列車時刻，產生 data/processed/dim_train.csv
python -m src.fetch_tdx

# 主流程：清理→建表→產出各分析表與圖 01–10
python -m src.run_prototype

# (選) 分類規則人工抽樣稽核
python -m src.audit_sample          # 產生 100 件樣本
python -m src.audit_sample --score  # 填完 Y/N 後計算正確率
```

## 程式模組
| 模組 | 說明 |
|---|---|
| `config.py` | 路徑與參數（含離群門檻 `MIN_LOSS_COUNT`） |
| `parse_lost_property.py` | 解析遺失物 XML、車站/車次拆分、品類分類、保管站名 → `fact_lost` |
| `parse_ridership.py` | 站碼補零、人流彙總、北中南東區域劃分 → `dim_station`、`fact_ridership` |
| `categorize.py` | 品名關鍵字分類（16 類＋其他）、價值層級、可追回性（規則 v3） |
| `build_tables.py` | 每十萬人次遺失率、對數迴歸離群殘差、高價值佔比 → `agg_station` |
| `fetch_tdx.py` | TDX 定期時刻表 → 車次/車種/停靠站 `dim_train` |
| `analyze.py` | 圖1 離群、圖2 品類價值、圖4 流向（Sankey） |
| `map_viz.py` | 圖3 全臺遺失率地圖（靜態 PNG ＋ 互動 HTML） |
| `analyze_train.py` | 車上遺失：車種、終點站→保管站 三情境逆物流 → 圖6 |
| `analyze_extra.py` | 圖5 保管站=車輛基地、圖7 可追回性、圖8 週末人均率、圖9 分級保管情境 |
| `audit_sample.py` | 分類規則人工抽樣稽核工具 |
| `plotstyle.py` | 跨平台中文字型自動偵測 |
| `run_prototype.py` | 主流程，串接整條管線 |

## 產出圖表（outputs/figures）
01 離群分析、02 品類與價值、03 逆物流（保管站集中度，舊版）、04 流向 Sankey、
05 地圖、06 車種與三情境逆物流、07 可追回性、08 週末人均率、
09 保管站=車輛基地、10 分級保管情境。

## 已知限制
- 本資料集為「公開招領子集」（18 個月 23,903 件，約官方年拾獲 7.3–9 萬件之兩成），總量以官方統計為準。
- 車上遺失約 63% 僅記錄車次、無中途交付站；逆物流以「終點站」為清出點，屬上界估計。
- 距離以直線（Haversine）計算，東部因中央山脈阻隔遭低估。
- 品類與價值為規則式判定，具主觀性，另以抽樣稽核控管。
- 缺乏「領回結果」資料，領回相關推論以結構與國際經驗為主。

## 隱私與匿名
`.env`（金鑰）與 `data/`（原始與中繼資料）均已被 `.gitignore` 排除、不入庫。
本 repo 為個人作品集用途；若用於競賽投稿，投稿文件須匿名，勿放入個人 GitHub/Tableau 連結。
