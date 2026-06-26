"""Prototype 主程式：依架構圖由上而下串起整條管線並輸出結果。

用法（在專案根目錄）：
    python -m src.run_prototype
或在 VS Code 直接執行本檔。
"""
from . import config
from .parse_lost_property import load_fact_lost
from .parse_ridership import load_dim_station, load_fact_ridership
from .build_tables import build_agg_station
from . import analyze


def main():
    print(">> 第一/二層：載入與清理")
    fact_lost = load_fact_lost()
    dim_station = load_dim_station()
    fact_ridership = load_fact_ridership()

    print("\n>> 第三層：建核心資料表")
    agg = build_agg_station(fact_lost, fact_ridership, dim_station)

    print("\n>> 第四層：分析與離群")
    outliers = analyze.loss_rate_outliers(agg)

    print("\n>> 產圖與表")
    analyze.fig_loss_scatter(outliers)
    analyze.fig_category(fact_lost)
    analyze.fig_reverse_logistics(fact_lost)

    # 站址 -> 站名 對照（給流向圖判斷保管站）
    import json
    addr2name = {"".join(s["stationAddrTw"].split()): s["stationName"]
                 for s in json.load(open(config.STATION_JSON, encoding="utf-8"))}
    analyze.fig_channel_flow(fact_lost, addr2name)

    # 存乾淨資料表（之後可餵給 Tableau）
    fact_lost.to_csv(config.PROCESSED / "fact_lost.csv", index=False, encoding="utf-8-sig")
    agg.to_csv(config.PROCESSED / "agg_station.csv", index=False, encoding="utf-8-sig")
    outliers[["sta_code", "sta_name", "lost_count", "throughput_window",
              "loss_rate_per_100k", "high_value_share", "residual"]].to_csv(
        config.TBL / "station_loss_outliers.csv", index=False, encoding="utf-8-sig")

    print()
    analyze.summary(fact_lost, agg, outliers)
    print(f"\n圖檔: {config.FIG}\n表檔: {config.TBL} / {config.PROCESSED}")


if __name__ == "__main__":
    main()
