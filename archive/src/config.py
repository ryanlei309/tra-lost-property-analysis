"""集中管理路徑與常數。所有模組都從這裡取得路徑，方便日後搬移或換資料。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIG = ROOT / "outputs" / "figures"
TBL = ROOT / "outputs" / "tables"
for d in (PROCESSED, FIG, TBL):
    d.mkdir(parents=True, exist_ok=True)

# --- 原始檔名（放在 data/raw/）---
LOST_XML = RAW / "遺失物資料集.xml"
STATION_JSON = RAW / "車站基本資料集.json"
RIDERSHIP_CSV = {
    "2022": RAW / "每日各站進出站人數2022.csv",
    "2023": RAW / "每日各站進出站人數2023.csv",
}

# --- 分析期間：遺失物資料實際集中在 2022-01 ~ 2023-07-17 ---
# 為避免「分子用 18 個月、分母用 24 個月」的偏誤，計算遺失率時
# 人流分母只取這個共同視窗（見 build_tables.py）。
ANALYSIS_START = "2022-01-01"
ANALYSIS_END = "2023-07-17"

# 離群分析最低件數門檻：實測 ≥10 件結論即穩定，取 20 更保守。
MIN_LOSS_COUNT = 20
