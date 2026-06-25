"""第三層（核心資料表）：組出 agg_station —— 每站一列，含遺失件數、人流、遺失率。

★ 兩個方法論護欄（很重要，避免邏輯錯誤）：
  1. 站遺失率的「分子」只算 channel=='車站' 的紀錄（約 37%）。
     車上(車次)遺失物不知道掉在哪一站，不能混進站別分子，否則分母用站人流、
     分子卻含跨站的車上遺失，意義不一致。車上遺失物另外用車種分析（需 TDX）。
  2. 「分母」人流只取分析視窗（2022-01 ~ 2023-07-17）的加總，與遺失物期間一致，
     避免分子 18 個月、分母 24 個月造成的偏誤。
"""
import pandas as pd

from . import config


def build_agg_station(fact_lost: pd.DataFrame,
                      fact_ridership: pd.DataFrame,
                      dim_station: pd.DataFrame) -> pd.DataFrame:
    # 分子：只取站別遺失
    station_lost = fact_lost[fact_lost["channel"] == "車站"]
    lost_cnt = (station_lost.groupby("loss_sta_code").size()
                .rename("lost_count").reset_index()
                .rename(columns={"loss_sta_code": "sta_code"}))

    # 高價值遺失件數（用於後續價值側寫）
    hi = (station_lost[station_lost["value_tier"] == "高"]
          .groupby("loss_sta_code").size().rename("lost_high").reset_index()
          .rename(columns={"loss_sta_code": "sta_code"}))

    # 分母：分析視窗內的人流加總
    mask = ((fact_ridership["date"] >= config.ANALYSIS_START) &
            (fact_ridership["date"] <= config.ANALYSIS_END))
    thru = (fact_ridership[mask].groupby("sta_code")["throughput"]
            .sum().rename("throughput_window").reset_index())

    agg = (dim_station
           .merge(lost_cnt, on="sta_code", how="left")
           .merge(hi, on="sta_code", how="left")
           .merge(thru, on="sta_code", how="left"))
    agg["lost_count"] = agg["lost_count"].fillna(0).astype(int)
    agg["lost_high"] = agg["lost_high"].fillna(0).astype(int)

    # 遺失率：每十萬人次掉幾件（throughput 已是 進+出，故為人次）
    agg["loss_rate_per_100k"] = (agg["lost_count"] /
                                 agg["throughput_window"] * 1e5).round(2)
    agg["high_value_share"] = (
        (agg["lost_high"] / agg["lost_count"].where(agg["lost_count"] > 0))
        .round(3))
    return agg.sort_values("lost_count", ascending=False)


if __name__ == "__main__":
    from .parse_lost_property import load_fact_lost
    from .parse_ridership import load_dim_station, load_fact_ridership
    agg = build_agg_station(load_fact_lost(), load_fact_ridership(), load_dim_station())
    print(agg.head(10).to_string())
