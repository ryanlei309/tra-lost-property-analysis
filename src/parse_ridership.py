"""
臺鐵遺失物開放資料分析
-----------------------
File: parse_ridership.py
Name: Ryan Lei
-----------------------
DESCRIPTION: 這個檔案負責讀兩份資料：一份是車站基本資料（JSON），整理成
dim_station（每一站的站名、經緯度、縣市、北中南東分區）；另一份是每日各站
進出站人數（CSV），整理成 fact_ridership（每天每站的進站、出站、總人次）。

處理過程中有兩個 join 的地雷，我都先在這裡踩掉了：
  1. CSV 裡的站碼沒有補前面的零（會存成 900），可是車站/遺失物那邊是 0900，
     不補零就對不起來，所以一律用 zfill(4) 補成四位。
  2. 經緯度在 JSON 裡是「25.13191 121.73837」這種一整串字串，要先用空白
     拆成 lat 跟 lon 兩個數字。
"""

import json
import pandas as pd

from . import config


def load_dim_station():
    """
    讀車站基本資料 JSON，整理成每一站一列的維度表 dim_station。

    Input:
        沒有參數，檔案路徑固定從 config.STATION_JSON 拿。

    Returns:
        out (DataFrame): 欄位有 sta_code、sta_name、sta_ename、lat、lon、
                         city、region，每一站一列。
    """
    # 把整份 JSON 讀進來，轉成 DataFrame。
    rows = json.load(open(config.STATION_JSON, encoding="utf-8"))
    df = pd.DataFrame(rows)

    # 站碼補零補到四位，之後才能跟人流、遺失物對得起來。
    df["sta_code"] = df["stationCode"].astype(str).str.zfill(4)

    # gps 是「緯度 經度」黏在一起的字串，用空白拆開，各自轉成數字。
    gps = df["gps"].str.split(" ", expand=True)
    df["lat"] = pd.to_numeric(gps[0], errors="coerce")
    df["lon"] = pd.to_numeric(gps[1], errors="coerce")

    # 從地址開頭抓出縣市（兩到三個字加上「縣」或「市」）。
    df["city"] = df["stationAddrTw"].str.extract(r"^(.{2,3}[縣市])")

    # 把縣市歸到北、中、南、東四區，等一下區域層級的分析會用到。
    _NORTH = ["臺北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣", "宜蘭縣"]
    _CENTRAL = ["苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣"]
    _SOUTH = ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣"]
    _EAST = ["花蓮縣", "臺東縣"]
    def _region(c):
        if c in _NORTH: return "北"
        if c in _CENTRAL: return "中"
        if c in _SOUTH: return "南"
        if c in _EAST: return "東"
        return "其他"
    df["region"] = df["city"].map(_region)

    # 只留下之後會用到的欄位，順便把兩個站名欄位改成好記的名字。
    out = df[["sta_code", "stationName", "stationEName", "lat", "lon", "city", "region"]].rename(
        columns={"stationName": "sta_name", "stationEName": "sta_ename"})
    print(f"[dim_station] {len(out)} 站，含 GPS {out['lat'].notna().sum()} 站")
    return out


def load_fact_ridership():
    """
    讀 2022、2023 兩年的每日進出站人數 CSV，合併成一張長表 fact_ridership。

    Input:
        沒有參數，兩個檔的路徑固定從 config.RIDERSHIP_CSV 拿。

    Returns:
        df (DataFrame): 欄位有 date、sta_code、in_cnt、out_cnt、throughput，
                        每天每站一列。throughput = 進站 + 出站。
    """
    # 兩年各讀一次，讀完先各自整理好，最後再接起來。
    parts = []
    for year, path in config.RIDERSHIP_CSV.items():
        d = pd.read_csv(path, dtype=str)
        # 站碼一樣補零到四位。
        d["sta_code"] = d["staCode"].astype(str).str.zfill(4)
        # 日期是 20220101 這種格式，轉成真正的日期型別。
        d["date"] = pd.to_datetime(d["trnOpDate"], format="%Y%m%d", errors="coerce")
        # 進站、出站人數轉數字，缺的補 0。
        d["in_cnt"] = pd.to_numeric(d["gateInComingCnt"], errors="coerce").fillna(0)
        d["out_cnt"] = pd.to_numeric(d["gateOutGoingCnt"], errors="coerce").fillna(0)
        parts.append(d[["date", "sta_code", "in_cnt", "out_cnt"]])

    # 兩年接成一張，再算總人次。
    df = pd.concat(parts, ignore_index=True)
    df["throughput"] = df["in_cnt"] + df["out_cnt"]
    print(f"[fact_ridership] {len(df)} 列，{df['date'].min().date()}..{df['date'].max().date()}")
    return df


if __name__ == "__main__":
    # 直接執行時，各印前幾列出來看看整理得對不對。
    print(load_dim_station().head())
    print(load_fact_ridership().head())
