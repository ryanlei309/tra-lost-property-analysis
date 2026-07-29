"""
臺鐵遺失物開放資料分析
-----------------------
File: build_tables.py
Name: Ryan Lei
-----------------------
DESCRIPTION: 這個檔案負責把前面清好的三張表兜成核心的 agg_station——每一站一
列，帶著遺失件數、分析期間的人流、還有算出來的遺失率跟高價值佔比。

這裡有兩個方法論上的護欄很重要，是我特別小心處理的地方：
  1. 遺失率的「分子」只算掉在車站的紀錄（大約佔 37%）。掉在車上的遺失物根本
     不知道是掉在哪一站，如果把它們也算進某站的分子，可是分母又用該站的站人
     流，分子分母的意義就對不起來了。所以車上遺失另外用車種去分析。
  2. 遺失率的「分母」人流，只取分析視窗（2022-01 ~ 2023-07-17）的加總，跟遺失
     物的期間對齊，避免分子 18 個月、分母 24 個月造成的偏誤。
"""

import pandas as pd

from . import config


def build_agg_station(fact_lost, fact_ridership, dim_station):
    """
    把遺失物、人流、車站三張表合成每站一列的 agg_station。

    Input:
        fact_lost (DataFrame): 清好的遺失物表。
        fact_ridership (DataFrame): 每天每站的人流表。
        dim_station (DataFrame): 車站維度表（站名、經緯度、分區等）。

    Returns:
        agg (DataFrame): 每站一列，含 lost_count、lost_high、throughput_window、
                         loss_rate_per_100k、high_value_share，依遺失件數由多到少排序。
    """
    # 分子：只取掉在車站的遺失，按站別數件數。
    station_lost = fact_lost[fact_lost["channel"] == "車站"]
    lost_cnt = (station_lost.groupby("loss_sta_code").size()
                .rename("lost_count").reset_index()
                .rename(columns={"loss_sta_code": "sta_code"}))

    # 順便算每站的高價值遺失件數，之後做價值側寫會用到。
    hi = (station_lost[station_lost["value_tier"] == "高"]
          .groupby("loss_sta_code").size().rename("lost_high").reset_index()
          .rename(columns={"loss_sta_code": "sta_code"}))

    # 分母：只加總分析視窗內的人流，跟遺失物期間對齊。
    mask = ((fact_ridership["date"] >= config.ANALYSIS_START) &
            (fact_ridership["date"] <= config.ANALYSIS_END))
    thru = (fact_ridership[mask].groupby("sta_code")["throughput"]
            .sum().rename("throughput_window").reset_index())

    # 以車站維度表為底，把件數、高價值件數、人流三個都 left join 進來。
    agg = (dim_station
           .merge(lost_cnt, on="sta_code", how="left")
           .merge(hi, on="sta_code", how="left")
           .merge(thru, on="sta_code", how="left"))
    # 沒對到的站件數會是 NaN，補 0 再轉整數。
    agg["lost_count"] = agg["lost_count"].fillna(0).astype(int)
    agg["lost_high"] = agg["lost_high"].fillna(0).astype(int)

    # 遺失率：每十萬人次掉幾件。throughput 本身已經是進+出，所以是人次。
    agg["loss_rate_per_100k"] = (agg["lost_count"] /
                                 agg["throughput_window"] * 1e5).round(2)
    # 高價值佔比：這站的高價值件數 佔 這站總件數 多少。件數 0 的站避免除以 0。
    agg["high_value_share"] = (
        (agg["lost_high"] / agg["lost_count"].where(agg["lost_count"] > 0))
        .round(3))
    return agg.sort_values("lost_count", ascending=False)


if __name__ == "__main__":
    # 直接執行時，自己把三張表載進來組一次，印前 10 名看看。
    from .parse_lost_property import load_fact_lost
    from .parse_ridership import load_dim_station, load_fact_ridership
    agg = build_agg_station(load_fact_lost(), load_fact_ridership(), load_dim_station())
    print(agg.head(10).to_string())
