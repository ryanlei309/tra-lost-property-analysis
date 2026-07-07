"""
車上遺失分析（需先有 TDX 的 dim_train.csv）

做三件事：
  1. join 覆蓋率：多少車上遺失能對到 TDX 車次。
  2. 車種分布：哪種車最會掉東西。
  3. 逆物流成本與三情境比較。

【逆物流成本的定義（重要，報告須照此措辭）】
  衡量的不是「旅客領回要跑多遠」，而是「一件未被立即認領的車上遺失物，
  在系統內被搬運的距離」。假設：物品隨車走到『終點站』才被清出（比照 JR/航空
  在終點站掃車），因此以『終點站』為清出點。
  三情境（每件的搬運距離）：
    - 現況：終點站 -> 實際保管站（資料中的 keep 站，多為樹林）
    - 終點站在地保管：終點站 -> 終點站 = 0
    - 區域中心：終點站 -> 最近的區域中心（樹林/臺中/新左營/花蓮）
  逆物流成本 = Σ 件數 × 搬運距離。

⚠ 已知限制（報告須寫）：
  - 非每件都真的走到終點（部分中途站就被交出/領回），故此為「上界估計」。
  - 車次路線以現行定期時刻表近似當年路線。
"""
import json
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from . import config
from .plotstyle import set_cjk_font
set_cjk_font()

DIM_TRAIN = config.PROCESSED / "dim_train.csv"

# 區域中心候選（北/中/南/東），用站名對應
CENTER_NAMES = ["樹林", "臺中", "新左營", "花蓮"]
TWO_CENTER_NAMES = ["樹林", "新左營"]   # 南北兩中心
HV_HUB_NAMES = ["新左營", "臺中", "花蓮"]  # 高價值品分流樞紐（南/中/東）
HUB_NAME = "樹林"  # 現行主要集中保管站


def _haversine(la1, lo1, la2, lo2):
    R = 6371
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = (math.sin(dp / 2) ** 2 +
         math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def _clean_train_type(t):
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


def _lookups(dim_station):
    gps = {str(r.sta_code).zfill(4): (r.lat, r.lon)
           for r in dim_station.itertuples() if pd.notna(r.lat)}
    region = {str(r.sta_code).zfill(4): r.region for r in dim_station.itertuples()}
    name_gps = {r.sta_name: (r.lat, r.lon)
                for r in dim_station.itertuples() if pd.notna(r.lat)}
    # keep_addr -> gps
    addr_gps = {}
    for s in json.load(open(config.STATION_JSON, encoding="utf-8")):
        g = str(s.get("gps", "")).split()
        if len(g) == 2:
            try:
                addr_gps["".join(s["stationAddrTw"].split())] = (float(g[0]), float(g[1]))
            except ValueError:
                pass
    return gps, region, name_gps, addr_gps


def _nearest_center(pt, centers):
    return min(_haversine(pt[0], pt[1], c[0], c[1]) for c in centers)


def _delta(v, base):
    """相對現況的增減標籤（正確處理『增加』）。"""
    d = (1 - v / base) * 100
    return f"↓{d:.0f}%" if d >= 0 else f"↑{-d:.0f}%（增加）"


def build_train_loss(fact_lost, dim_train, dim_station):
    gps, region, name_gps, addr_gps = _lookups(dim_station)

    centers = [name_gps[n] for n in CENTER_NAMES if n in name_gps]
    two_centers = [name_gps[n] for n in TWO_CENTER_NAMES if n in name_gps]
    hv_hubs = [(n, name_gps[n]) for n in HV_HUB_NAMES if n in name_gps]
    hub = name_gps.get(HUB_NAME)
    if hub is None or not centers:
        print("[train] 警告：找不到樹林或區域中心站的座標，請確認 dim_station 站名。")

    dim_train = dim_train.copy()
    dim_train["train_no"] = dim_train["train_no"].astype(str)
    # 終點站代碼與座標
    end_id = {r.train_no: str(r.end_id).zfill(4) for r in dim_train.itertuples()}
    end_name = {r.train_no: r.end_name for r in dim_train.itertuples()}
    ttype = dict(zip(dim_train["train_no"], dim_train["train_type"]))

    tr = fact_lost[fact_lost["channel"] == "車次"].copy()
    tr["train_no"] = tr["train_no"].astype(str)
    tr["train_type"] = tr["train_no"].map(ttype)
    tr["train_type_clean"] = tr["train_type"].map(_clean_train_type)

    # 能對到、且終點站有座標的
    tr["end_id"] = tr["train_no"].map(end_id)
    tr["term_gps"] = tr["end_id"].map(lambda c: gps.get(c) if pd.notna(c) else None)
    matched = tr["term_gps"].notna()
    print(f"[train] 車上遺失 {len(tr)} 件，對到 TDX 終點站 {matched.sum()} 件 "
          f"({matched.mean()*100:.1f}%)")

    m = tr[matched].copy()
    m["terminus_name"] = m["train_no"].map(end_name)
    m["terminus_region"] = m["end_id"].map(region)
    m["keep_gps"] = m["keep_addr"].map(lambda a: addr_gps.get("".join(str(a).split())))
    m = m[m["keep_gps"].notna()].copy()

    # 三情境每件搬運距離
    m["現況_km"] = m.apply(lambda r: _haversine(*r["term_gps"], *r["keep_gps"]), axis=1)
    m["南北兩中心_km"] = m["term_gps"].map(lambda p: _nearest_center(p, two_centers))
    m["區域中心_km"] = m["term_gps"].map(lambda p: _nearest_center(p, centers))

    # 高價值分流：終點站 -> 最近的高價值樞紐（南/中/東）
    def _assign_hv(p):
        name, gp = min(hv_hubs, key=lambda h: _haversine(p[0], p[1], h[1][0], h[1][1]))
        return name, _haversine(p[0], p[1], gp[0], gp[1])
    hv = m["term_gps"].map(_assign_hv)
    m["高價值樞紐"] = hv.map(lambda x: x[0])
    m["高價值樞紐_km"] = hv.map(lambda x: x[1])
    return tr, m


def report(tr, m):
    print("\n[train] 車種分布（車上遺失件數）：")
    print(tr["train_type_clean"].value_counts().head(8).to_string())

    tot = {
        "現況（送實際保管站）": m["現況_km"].sum(),
        "南北兩中心（樹林/新左營）": m["南北兩中心_km"].sum(),
        "區域四中心（樹林/臺中/新左營/花蓮）": m["區域中心_km"].sum(),
    }
    base = tot["現況（送實際保管站）"]
    print("\n[train] 三情境『逆物流成本』（總搬運人-公里；終點站在地保管理論下限=0）：")
    for k, v in tot.items():
        cut = "" if k.startswith("現況") else f"（較現況{_delta(v, base)}）"
        print(f"   {k}：{v:,.0f} km {cut}")

    print("\n[train] 現況逆物流成本『依終點站區域』拆解（看是誰造成的）：")
    g = m.groupby("terminus_region").agg(
        件數=("現況_km", "size"),
        總搬運km=("現況_km", "sum"),
        平均km=("現況_km", "mean")).round(0)
    g["佔總成本%"] = (g["總搬運km"] / g["總搬運km"].sum() * 100).round(1)
    print(g.reindex(["北", "中", "南", "東"]).dropna(how="all").to_string())


def high_value_report(m):
    hv = m[m["value_tier"] == "高"].copy()
    if hv.empty:
        return
    print(f"\n[train] === 高價值品分流分析（value_tier=高，共 {len(hv)} 件）===")
    print("[train] 高價值品終點站區域分布：",
          hv["terminus_region"].value_counts().to_dict())
    cur = hv["現況_km"].sum()
    div = hv["高價值樞紐_km"].sum()
    print(f"[train] 高價值品逆物流：現況(送實際保管站) {cur:,.0f} km "
          f"→ 分流南/中/東樞紐 {div:,.0f} km （{_delta(div, cur)}）")
    print("[train] 各分流樞紐承接件數（看管理負荷）：",
          hv["高價值樞紐"].value_counts().to_dict())
    print("[train] 高價值品類組成：", hv["category"].value_counts().head(6).to_dict())


def fig_train(tr, m):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    tr["train_type_clean"].value_counts().head(7).sort_values().plot.barh(
        ax=ax1, color="#003E73")
    ax1.set_title("車上遺失：各車種件數"); ax1.set_xlabel("件數"); ax1.set_ylabel("")

    scen = pd.Series({
        "現況\n(送實際保管站)": m["現況_km"].sum(),
        "南北兩中心\n(樹林/新左營)": m["南北兩中心_km"].sum(),
        "區域四中心\n(樹林/臺中/\n新左營/花蓮)": m["區域中心_km"].sum(),
    })
    bars = ax2.bar(scen.index, scen.values,
                   color=["#B03A2E", "#2E86C1", "#F08300"])
    ax2.set_title("三情境『逆物流成本』（終點站→保管站 總搬運）")
    ax2.set_ylabel("總搬運人-公里（上界估計）"); ax2.set_xlabel("")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1000:.0f}K"))
    base = scen.iloc[0]
    for b, v in zip(bars, scen.values):
        lab = f"{v/1000:.0f}K" + ("" if v == base else f"\n{_delta(v, base)}")
        ax2.text(b.get_x()+b.get_width()/2, v, lab, ha="center", va="bottom", fontsize=9)
    ax2.margins(y=0.15)
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
    high_value_report(m)
    fig_train(tr, m)
    m.drop(columns=["term_gps", "keep_gps"]).to_csv(
        config.PROCESSED / "fact_train_loss.csv", index=False, encoding="utf-8-sig")
    print("[train] 已輸出 fact_train_loss.csv 與 06_train_friction.png")
