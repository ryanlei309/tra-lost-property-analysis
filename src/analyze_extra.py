"""
延伸分析三件組（皆只用既有資料，不需 TDX）：

  07 可追回性：可識別失主 vs 匿名（支撐「主動通知」建議）
  08 週末效應：每百萬人次遺失率（以每日進站人流正規化，證明非人多假象）
  09 保管站=車輛基地：車上遺失的保管站前六名對應臺鐵整備基地
     （實證「物品隨車至終到/整備點被清出」模型）
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config
from .plotstyle import set_cjk_font
set_cjk_font()

ORANGE, NAVY, GREY = "#F08300", "#003E73", "#C9CDD2"

# 保管站 -> 對應車輛基地/調車場（公開資訊，維基/臺鐵）
DEPOT_MAP = {
    "樹林": "樹林調車場",
    "北湖": "富岡車輛基地",
    "新左營": "新左營調車場",
    "潮州": "潮州車輛基地",
    "臺東": "臺東機務段",
    "花蓮": "花蓮機務段",
    "新竹": "新竹（富岡基地轄區）",
}


def fig_recoverability(fact_lost: pd.DataFrame):
    rec = fact_lost["recoverable"].mean()
    n_rec = int(fact_lost["recoverable"].sum())
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.pie([rec, 1 - rec],
            labels=[f"可識別失主\n{rec*100:.0f}%（約{n_rec:,}件）",
                    f"匿名/難追回\n{(1-rec)*100:.0f}%"],
            colors=[ORANGE, GREY], startangle=90,
            textprops={"fontsize": 12}, wedgeprops={"width": 0.45})
    ax1.set_title("遺失物本質上能否找到失主（卡證=可識別）")
    cat = fact_lost.groupby("category").agg(
        n=("recoverable", "size"), rec=("recoverable", "mean")).sort_values("n")
    ax2.barh(cat.index, cat["n"],
             color=[ORANGE if r > 0.5 else GREY for r in cat["rec"]])
    ax2.set_title("各品類件數（橘＝可識別失主）")
    ax2.set_xlabel("件數")
    fig.tight_layout()
    fig.savefig(config.FIG / "07_recoverability.png", dpi=130)
    plt.close(fig)


def fig_weekday_rate(fact_lost: pd.DataFrame, fact_ridership: pd.DataFrame):
    """每百萬人次遺失率（人均化），證明週末效應非人多假象。"""
    fl = fact_lost.copy()
    fl["pickup_dt"] = pd.to_datetime(fl["pickup_dt"])
    rid = fact_ridership.copy()
    rid["date"] = pd.to_datetime(rid["date"])
    lo, hi = fl["pickup_dt"].min(), fl["pickup_dt"].max()
    rid = rid[(rid["date"] >= lo) & (rid["date"] <= hi)]
    daily = rid.groupby("date")["in_cnt"].sum().reset_index()
    daily["wd"] = daily["date"].dt.weekday
    fl["wd"] = fl["pickup_dt"].dt.weekday

    wdn = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    loss = np.array([(fl["wd"] == i).sum() for i in range(7)], dtype=float)
    flow = np.array([daily.loc[daily["wd"] == i, "in_cnt"].sum() for i in range(7)],
                    dtype=float)
    rate = loss / flow * 1e6

    wk_rate, wd_rate = rate[5:7].mean(), rate[0:5].mean()
    print(f"[extra] 週末 vs 平日 每百萬人次遺失率：{wk_rate:.1f} vs {wd_rate:.1f} "
          f"（週末高 {(wk_rate/wd_rate-1)*100:.0f}%）")

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [NAVY] * 5 + [ORANGE] * 2
    bars = ax.bar(wdn, rate, color=colors)
    for b, v in zip(bars, rate):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}",
                ha="center", va="bottom", fontsize=10)
    ax.axhline(wd_rate, color=GREY, ls="--", lw=1)
    ax.set_title(f"每百萬人次遺失率：週末較平日高 {(wk_rate/wd_rate-1)*100:.0f}%"
                 "（已用每日進站人流正規化）")
    ax.set_ylabel("遺失件數 / 百萬進站人次")
    fig.tight_layout()
    fig.savefig(config.FIG / "08_weekday_rate.png", dpi=130)
    plt.close(fig)


def fig_depot_keep(fact_lost: pd.DataFrame):
    """車上遺失的保管站前六名，對應臺鐵車輛基地。"""
    tr = fact_lost[fact_lost["channel"] == "車次"]
    keep = tr["keep_sta_name"].value_counts().head(6)
    labels = [f"{n}\n({DEPOT_MAP.get(n, '—')})" for n in keep.index]
    share = keep / len(tr) * 100

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.barh(labels[::-1], keep.values[::-1], color=NAVY)
    for b, v, s in zip(bars, keep.values[::-1], share.values[::-1]):
        ax.text(v, b.get_y() + b.get_height() / 2, f" {v:,} ({s:.0f}%)",
                va="center", fontsize=10)
    ax.set_title("車上遺失的保管站＝車輛整備基地\n（實證：物品隨車至終到/整備點被清出）")
    ax.set_xlabel("車上遺失保管件數")
    ax.margins(x=0.15)
    fig.tight_layout()
    fig.savefig(config.FIG / "09_depot_keep.png", dpi=130)
    plt.close(fig)
    print("[extra] 保管站=車輛基地 圖已產生（前6站對應：",
          {n: DEPOT_MAP.get(n, "—") for n in keep.index}, "）")


def run(fact_lost: pd.DataFrame, fact_ridership: pd.DataFrame):
    fig_recoverability(fact_lost)
    fig_weekday_rate(fact_lost, fact_ridership)
    fig_depot_keep(fact_lost)
    print(f"[extra] 已輸出 07_recoverability / 08_weekday_rate / 09_depot_keep")
