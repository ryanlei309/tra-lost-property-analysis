"""
臺鐵遺失物開放資料分析
-----------------------
File: run_prototype.py
-----------------------
DESCRIPTION: 這是整條管線的主程式，照架構圖由上而下把每一層串起來：載入清理
→ 建核心表 → 分析與離群 → 產圖產表，最後把乾淨的資料表存出來（之後可以餵給
Tableau）。

用法（在專案根目錄）：
    python -m src.run_prototype
或者在 VS Code 直接執行這個檔也可以。
"""

from . import config
from .parse_lost_property import load_fact_lost
from .parse_ridership import load_dim_station, load_fact_ridership
from .build_tables import build_agg_station
from . import analyze


def _check_inputs():
    """
    開跑前先確認四個原始資料檔都在，缺檔就給清楚的提示再結束。

    Input:
        沒有參數，檢查 config 裡設定的四個原始檔路徑。

    Output:
        沒有回傳值；如果有缺檔，印出缺哪些之後 raise SystemExit(1)。
    """
    need = [config.LOST_XML, config.STATION_JSON,
            config.RIDERSHIP_CSV["2022"], config.RIDERSHIP_CSV["2023"]]
    missing = [p for p in need if not p.exists()]
    if missing:
        print("缺少原始資料檔，請放進 data/raw/（檔名需一致）：")
        for p in missing:
            print("   -", p.name)
        print("這些是 data.gov.tw 下載的開放資料，因 .gitignore 不入庫，需自行放置。")
        raise SystemExit(1)


def main():
    # 先確認資料齊全再開始。
    _check_inputs()
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

    # 做一份「站址 -> 站名」的對照，流向圖跟保管站圖判斷保管站要用。
    import json
    addr2name = {"".join(s["stationAddrTw"].split()): s["stationName"]
                 for s in json.load(open(config.STATION_JSON, encoding="utf-8"))}
    analyze.fig_reverse_logistics(fact_lost, addr2name)
    analyze.fig_channel_flow(fact_lost, addr2name)

    from . import map_viz
    map_viz.static_map(agg)
    map_viz.interactive_map(agg)

    # 車上遺失分析：只有在有 TDX 的 dim_train.csv 時才會真的跑。
    from . import analyze_train
    analyze_train.run_if_available(fact_lost, dim_station)

    # 延伸三件組：可追回性 / 週末人均率 / 保管站=車輛基地（外加分級保管情境）。
    from . import analyze_extra
    analyze_extra.run(fact_lost, fact_ridership)

    # 把清好的資料表存出來，之後可以餵給 Tableau。
    fact_lost.to_csv(config.PROCESSED / "fact_lost.csv", index=False, encoding="utf-8-sig")
    # dim_station 併上每站人流，Tableau 才算得出「某品類在某站的遺失率」。
    dim_out = dim_station.merge(
        agg[["sta_code", "throughput_window"]], on="sta_code", how="left")
    dim_out.to_csv(config.PROCESSED / "dim_station.csv", index=False, encoding="utf-8-sig")
    agg.to_csv(config.PROCESSED / "agg_station.csv", index=False, encoding="utf-8-sig")
    outliers[["sta_code", "sta_name", "lost_count", "throughput_window",
              "loss_rate_per_100k", "high_value_share", "residual"]].to_csv(
        config.TBL / "station_loss_outliers.csv", index=False, encoding="utf-8-sig")

    # 最後印一份文字摘要，順便告訴使用者圖跟表放在哪。
    print()
    analyze.summary(fact_lost, agg, outliers)
    print(f"\n圖檔: {config.FIG}\n表檔: {config.TBL} / {config.PROCESSED}")


if __name__ == "__main__":
    main()
