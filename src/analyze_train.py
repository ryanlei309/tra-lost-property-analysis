"""
車上遺失分析（需先有 TDX 的 dim_train.csv）

把「車次」遺失物接上 TDX 路線，做三件事：
  1. join 覆蓋率：多少車上遺失能對到 TDX 車次。
  2. 車種分布：哪種車（自強/區間快/區間…）最會掉東西。
  3. 領回友善度（摩擦）：用路線「重心」到保管站的距離當『旅客領回距離』的代理值，
     再用 件數 × 距離 = 總領回負擔。

⚠ 已知近似（報告須註明）：
  - 我們不知道東西掉在路線的哪一段，只能用「路線重心」當旅客位置的代理。
  - 車次路線以『現行定期時刻表』近似 2022–23 當年路線。
  所以這是『估計的摩擦』，不是精確距離——這點要誠實寫出來。
"""
import json
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config

from .plotstyle import set_cjk_font
set_cjk_font()

DIM_TRAIN = config.PROCESSED / "dim_train.csv"


def _haversine(la1, lo1, la2, lo2):
    R = 6371
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = (math.sin(dp / 2) ** 2 +
         math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def _clean_train_type(t):
    """把 TDX 雜亂的車種名稱正規化成短標籤。順序有意義（特定在前）。"""
    if pd.isna(t):
        return None
    t = str(t)
    if "3000" in t:   return "自強3000"
    if "推拉" in t:   return "推拉式自強"
    if "普悠瑪" in t: return "普悠瑪"
    if "太魯閣" in t: return "太魯閣"
    if "莒光" in t:   return "莒光"
    if "復興" in t:   return "復興"
    if "區間快" in t: return "區間快"
    if "區間" in t:   return "區間慢"
    if "自強" in t:   return "自強"
    return t or "其他"


def _station_lookups(dim_station):
    gps = {r.sta_code: (r.lat, r.lon) for r in dim_station.itertuples() if pd.notna(r.lat)}
    region = {r.sta_code: r.region for r in dim_station.itertuples()}
    # keep_addr -> gps（用車站基本資料的地址）
    addr_gps = {}
    for s in json.load(open(config.STATION_JSON, encoding="utf-8")):
        g = str(s.get("gps", "")).split()
        if len(g) == 2:
            try:
                addr_gps["".join(s["stationAddrTw"].split())] = (float(g[0]), float(g[1]))
            except ValueError:
                pass
    return gps, region, addr_gps


def _route_geometry(stop_ids, gps, region):
    pts = [gps[c] for c in stop_ids if c in gps]
    if not pts:
        return None
    lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
    regions = {region.get(c) for c in stop_ids if region.get(c)}
    south_lat = min(lats)  # 緯度越小越南
    return {
        "centroid": (float(np.mean(lats)), float(np.mean(lons))),
        "southernmost_lat": south_lat,
        "regions": regions,
        "reaches_south": "南" in regions,
        "southmost_region": "南" if "南" in regions else ("中" if "中" in regions else
                            ("東" if "東" in regions else "北")),
    }


def build_train_loss(fact_lost, dim_train, dim_station):
    gps, region, addr_gps = _station_lookups(dim_station)
    dim_train = dim_train.copy()
    dim_train["train_no"] = dim_train["train_no"].astype(str)

    # 預先算每個車次的路線幾何
    geom = {}
    for r in dim_train.itertuples():
        stop_ids = str(r.stop_ids).split("|") if pd.notna(r.stop_ids) else []
        g = _route_geometry(stop_ids, gps, region)
        if g:
            geom[r.train_no] = g
    ttype = dict(zip(dim_train["train_no"], dim_train["train_type"]))

    tr = fact_lost[fact_lost["channel"] == "車次"].copy()
    tr["train_no"] = tr["train_no"].astype(str)
    tr["train_type"] = tr["train_no"].map(ttype)
    tr["train_type_clean"] = tr["train_type"].map(_clean_train_type)
    matched = tr["train_no"].isin(geom)
    print(f"[train] 車上遺失 {len(tr)} 件，對到 TDX 路線 {matched.sum()} 件 "
          f"({matched.mean()*100:.1f}%)")

    m = tr[matched].copy()
    m["keep_gps"] = m["keep_addr"].map(lambda a: addr_gps.get("".join(str(a).split())))
    m["route_centroid"] = m["train_no"].map(lambda t: geom[t]["centroid"])
    m["reaches_south"] = m["train_no"].map(lambda t: geom[t]["reaches_south"])
    m["southmost_region"] = m["train_no"].map(lambda t: geom[t]["southmost_region"])
    m = m[m["keep_gps"].notna()].copy()
    m["est_dist_km"] = m.apply(
        lambda r: _haversine(r["route_centroid"][0], r["route_centroid"][1],
                             r["keep_gps"][0], r["keep_gps"][1]), axis=1)
    return tr, m


def report(tr, m):
    print("\n[train] 車種分布（車上遺失件數）：")
    print(tr["train_type_clean"].value_counts().head(8).to_string())
    print("\n[train] 領回友善度（依路線最南到達區域）：")
    g = m.groupby("southmost_region").agg(
        件數=("est_dist_km", "size"),
        平均估計距離km=("est_dist_km", "mean"),
        總領回負擔=("est_dist_km", "sum")).round(0)
    g["佔總負擔%"] = (g["總領回負擔"] / g["總領回負擔"].sum() * 100).round(1)
    print(g.reindex(["北", "中", "南", "東"]).dropna(how="all").to_string())
    south = m[m["reaches_south"]]
    if len(south):
        print(f"\n[train] 行經南部的車上遺失 {len(south)} 件，"
              f"估計領回距離中位數 {south['est_dist_km'].median():.0f} km")


def fig_train(tr, m):
    from matplotlib.ticker import FuncFormatter
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    tr["train_type_clean"].value_counts().head(7).sort_values().plot.barh(
        ax=ax1, color="#003E73")
    ax1.set_title("車上遺失：各車種件數"); ax1.set_xlabel("件數"); ax1.set_ylabel("")
    g = m.groupby("southmost_region")["est_dist_km"].sum().reindex(
        ["北", "中", "南", "東"]).dropna()
    g.plot.bar(ax=ax2, color="#F08300")
    ax2.set_title("領回總負擔（件數×估計距離）依路線最南到達區域")
    ax2.set_ylabel("總人-公里（估計）"); ax2.set_xlabel("")
    ax2.tick_params(axis="x", rotation=0)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1000:.0f}K"))
    fig.tight_layout()
    fig.savefig(config.FIG / "06_train_friction.png", dpi=130)
    plt.close(fig)


def run_if_available(fact_lost, dim_station):
    if not DIM_TRAIN.exists():
        print("[train] 找不到 dim_train.csv，略過車上遺失分析（先跑 fetch_tdx）")
        return
    dim_train = pd.read_csv(DIM_TRAIN, dtype=str)
    tr, m = build_train_loss(fact_lost, dim_train, dim_station)
    report(tr, m)
    fig_train(tr, m)
    m.drop(columns=["keep_gps", "route_centroid"]).to_csv(
        config.PROCESSED / "fact_train_loss.csv", index=False, encoding="utf-8-sig")
    print(f"[train] 已輸出 fact_train_loss.csv 與 06_train_friction.png")
