"""第一/二層：人流 CSV -> fact_ridership，車站基本資料 JSON -> dim_station。

注意兩個 join 地雷（已處理）：
  1. CSV 的 staCode 沒有前置零（存成 900），dim/遺失物是 0900 -> 一律 zfill(4)。
  2. GPS 在 JSON 是 "25.13191 121.73837" 的字串 -> 拆成 lat / lon。
"""
import json
import pandas as pd

from . import config


def load_dim_station() -> pd.DataFrame:
    rows = json.load(open(config.STATION_JSON, encoding="utf-8"))
    df = pd.DataFrame(rows)
    df["sta_code"] = df["stationCode"].astype(str).str.zfill(4)
    gps = df["gps"].str.split(" ", expand=True)
    df["lat"] = pd.to_numeric(gps[0], errors="coerce")
    df["lon"] = pd.to_numeric(gps[1], errors="coerce")
    df["city"] = df["stationAddrTw"].str.extract(r"^(.{2,3}[縣市])")
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
    out = df[["sta_code", "stationName", "stationEName", "lat", "lon", "city", "region"]].rename(
        columns={"stationName": "sta_name", "stationEName": "sta_ename"})
    print(f"[dim_station] {len(out)} 站，含 GPS {out['lat'].notna().sum()} 站")
    return out


def load_fact_ridership() -> pd.DataFrame:
    parts = []
    for year, path in config.RIDERSHIP_CSV.items():
        d = pd.read_csv(path, dtype=str)
        d["sta_code"] = d["staCode"].astype(str).str.zfill(4)
        d["date"] = pd.to_datetime(d["trnOpDate"], format="%Y%m%d", errors="coerce")
        d["in_cnt"] = pd.to_numeric(d["gateInComingCnt"], errors="coerce").fillna(0)
        d["out_cnt"] = pd.to_numeric(d["gateOutGoingCnt"], errors="coerce").fillna(0)
        parts.append(d[["date", "sta_code", "in_cnt", "out_cnt"]])
    df = pd.concat(parts, ignore_index=True)
    df["throughput"] = df["in_cnt"] + df["out_cnt"]
    print(f"[fact_ridership] {len(df)} 列，{df['date'].min().date()}..{df['date'].max().date()}")
    return df


if __name__ == "__main__":
    print(load_dim_station().head())
    print(load_fact_ridership().head())
