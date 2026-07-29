"""
臺鐵遺失物開放資料分析
-----------------------
File: config.py
Name: Ryan Lei
-----------------------
DESCRIPTION: 這個檔案把整個專案會用到的路徑跟參數集中放在同一個地方。其他
模組都從這裡 import，所以之後如果資料夾搬家、或是換一批新的資料檔，只要改這
一個檔就好，不用一個一個模組去翻。
"""

from pathlib import Path

# 專案的最外層資料夾。這個檔案本身在 src/ 底下，所以往上兩層才是根目錄。
ROOT = Path(__file__).resolve().parent.parent

# 四個常用的資料夾：原始資料、清理後的中繼資料、圖、表。
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIG = ROOT / "outputs" / "figures"
TBL = ROOT / "outputs" / "tables"

# 產出用的資料夾如果還沒建，先幫忙建起來，免得之後存檔的時候噴錯。
for d in (PROCESSED, FIG, TBL):
    d.mkdir(parents=True, exist_ok=True)

# 四個原始檔的檔名，都要放在 data/raw/ 底下。
LOST_XML = RAW / "遺失物資料集.xml"
STATION_JSON = RAW / "車站基本資料集.json"
RIDERSHIP_CSV = {
    "2022": RAW / "每日各站進出站人數2022.csv",
    "2023": RAW / "每日各站進出站人數2023.csv",
}

# 分析期間。遺失物資料其實只集中在 2022-01 到 2023-07-17 這段。
# 算遺失率的時候，如果分子（遺失件數）只有 18 個月、分母（人流）卻用了
# 整整 24 個月，比例就會被稀釋，比較起來不公平。所以這裡先把共同的時間
# 視窗定出來，等一下 build_tables.py 在算人流分母時，只取這一段。
ANALYSIS_START = "2022-01-01"
ANALYSIS_END = "2023-07-17"

# 離群分析的最低件數門檻。件數太少的站，殘差很容易只是雜訊。
# 我實際測過，件數 ≥10 結論就滿穩定了，這裡取 20 只是想再保守一點。
MIN_LOSS_COUNT = 20
