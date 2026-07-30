"""
臺鐵遺失物開放資料分析
-----------------------
File: analyze_extra.py
-----------------------
DESCRIPTION: 這個檔案放三組延伸分析，都只用現有資料、不需要 TDX：
  07 可追回性：能識別失主 vs 匿名，支撐「主動通知」這個建議。
  08 週末效應：每百萬人次的遺失率（用每日進站人流正規化），證明週末掉比較多
     不是單純因為人多。
  09 保管站=車輛基地：車上遺失的保管站前六名，剛好對到臺鐵的整備基地，實證
     「物品隨車到終點/整備點才被清出」這個模型。
（外加一張 10 分級保管情境，估算縮短保管期能降多少庫存。）
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

# 保管站 -> 對應的車輛基地/調車場（公開資訊，來源是維基/臺鐵）。
DEPOT_MAP = {
    "樹林": "樹林調車場",
    "北湖": "富岡車輛基地",
    "新左營": "新左營調車場",
    "潮州": "潮州車輛基地",
    "臺東": "臺東機務段",
    "花蓮": "花蓮機務段",
    "新竹": "新竹（富岡基地轄區）",
}


def fig_recoverability(fact_lost):
    """
    畫可追回性：整體能識別失主的比例，加上各品類的件數（橘=多半可識別）。

    Input:
        fact_lost (DataFrame): 清好的遺失物表。

    Output:
        存 07_recoverability.png，沒有回傳值。
    """
    rec = fact_lost["recoverable"].mean()
    n_rec = int(fact_lost["recoverable"].sum())
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    # 左邊環圈圖：可識別失主 vs 匿名/難追回。
    ax1.pie([rec, 1 - rec],
            labels=[f"可識別失主\n{rec*100:.0f}%（約{n_rec:,}件）",
                    f"匿名/難追回\n{(1-rec)*100:.0f}%"],
            colors=[ORANGE, GREY], startangle=90,
            textprops={"fontsize": 12}, wedgeprops={"width": 0.45})
    ax1.set_title("遺失物本質上能否找到失主（卡證=可識別）")
    # 右邊長條：各品類件數，可識別的塗橘色、其餘灰色。
    cat = fact_lost.groupby("category").agg(
        n=("recoverable", "size"), rec=("recoverable", "mean")).sort_values("n")
    ax2.barh(cat.index, cat["n"],
             color=[ORANGE if r > 0.5 else GREY for r in cat["rec"]])
    ax2.set_title("各品類件數（橘＝可識別失主）")
    ax2.set_xlabel("件數")
    fig.tight_layout()
    fig.savefig(config.FIG / "07_recoverability.png", dpi=130)
    plt.close(fig)


def fig_weekday_rate(fact_lost, fact_ridership):
    """
    畫每百萬人次的遺失率（人均化），證明週末效應不是「人多」的假象。

    Input:
        fact_lost (DataFrame): 清好的遺失物表。
        fact_ridership (DataFrame): 每天每站的人流表。

    Output:
        存 08_weekday_rate.png，沒有回傳值。
    """
    fl = fact_lost.copy()
    fl["pickup_dt"] = pd.to_datetime(fl["pickup_dt"])
    rid = fact_ridership.copy()
    rid["date"] = pd.to_datetime(rid["date"])
    # 人流只取遺失物實際涵蓋的日期範圍，兩邊對齊。
    lo, hi = fl["pickup_dt"].min(), fl["pickup_dt"].max()
    rid = rid[(rid["date"] >= lo) & (rid["date"] <= hi)]
    daily = rid.groupby("date")["in_cnt"].sum().reset_index()
    daily["wd"] = daily["date"].dt.weekday
    fl["wd"] = fl["pickup_dt"].dt.weekday

    # 一到日各算「遺失件數」跟「進站人流」，再相除得每百萬人次遺失率。
    wdn = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    loss = np.array([(fl["wd"] == i).sum() for i in range(7)], dtype=float)
    flow = np.array([daily.loc[daily["wd"] == i, "in_cnt"].sum() for i in range(7)],
                    dtype=float)
    rate = loss / flow * 1e6

    # 比一下週末（六日）跟平日（一到五）的平均率。
    wk_rate, wd_rate = rate[5:7].mean(), rate[0:5].mean()
    print(f"[extra] 週末 vs 平日 每百萬人次遺失率：{wk_rate:.1f} vs {wd_rate:.1f} "
          f"（週末高 {(wk_rate/wd_rate-1)*100:.0f}%）")

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [NAVY] * 5 + [ORANGE] * 2
    bars = ax.bar(wdn, rate, color=colors)
    for b, v in zip(bars, rate):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}",
                ha="center", va="bottom", fontsize=10)
    # 畫一條平日平均的虛線當基準，週末高出多少一目了然。
    ax.axhline(wd_rate, color=GREY, ls="--", lw=1)
    ax.set_title(f"每百萬人次遺失率：週末較平日高 {(wk_rate/wd_rate-1)*100:.0f}%"
                 "（已用每日進站人流正規化）")
    ax.set_ylabel("遺失件數 / 百萬進站人次")
    fig.tight_layout()
    fig.savefig(config.FIG / "08_weekday_rate.png", dpi=130)
    plt.close(fig)


def fig_depot_keep(fact_lost):
    """
    畫車上遺失的保管站前六名，並標出它們對應的車輛整備基地。

    Input:
        fact_lost (DataFrame): 清好的遺失物表。

    Output:
        存 09_depot_keep.png，並印出前六站對應的基地，沒有回傳值。
    """
    tr = fact_lost[fact_lost["channel"] == "車次"]
    keep = tr["keep_sta_name"].value_counts().head(6)
    # 標籤同時放站名跟對應的基地名。
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


def fig_retention_scenarios(fact_lost):
    """
    畫分級保管期的穩態庫存情境（上界估計，假設沒人來領）。

    流入量用臺鐵官方的年均拾獲量 8.6 萬件（2026/3 新制報導）；價值構成用本資料
    集的比例當代理。穩態庫存 ≈ 月流入 × 各級保管月數 的加權。

    法源備註：服務人員拾得的遺留物依鐵路法要招領 1 年（要修法才能縮短）；民眾
    拾得依民法 ≤500 元 15 天 / >500 元或無法判斷 6 個月。國際對照：日本遺失物
    法 2007 年起保管 3 個月；倫敦 TfL 也是 3 個月。

    Input:
        fact_lost (DataFrame): 清好的遺失物表。

    Output:
        存 10_retention_scenarios.png，並印各情境庫存，沒有回傳值。
    """
    OFFICIAL_YEARLY = 86000
    monthly = OFFICIAL_YEARLY / 12
    # 用資料集裡的價值構成當各級的比例。
    s = fact_lost["value_tier"].value_counts(normalize=True)
    s_lo, s_mid, s_hi, s_un = (s.get("低", 0), s.get("中", 0),
                               s.get("高", 0), s.get("未知", 0))
    print(f"[extra] 價值構成（資料集）：低 {s_lo*100:.0f}% / 中 {s_mid*100:.0f}% / "
          f"高 {s_hi*100:.0f}% / 未知 {s_un*100:.0f}%")

    # 三種保管政策下的穩態庫存：月流入 × 平均保管月數。
    scen = pd.Series({
        "現制\n(全品項12個月)": monthly * 12,
        "低價值改3個月\n(其餘12個月)": monthly * (s_lo * 3 + (1 - s_lo) * 12),
        "分級保管\n(低3/中·未知6/高12)": monthly * (s_lo * 3 + (s_mid + s_un) * 6
                                            + s_hi * 12),
    })
    base = scen.iloc[0]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(scen.index, scen.values, color=["#B03A2E", "#2E86C1", "#F08300"])
    for b, v in zip(bars, scen.values):
        lab = f"{v/1000:.0f}K件" + ("" if v == base else f"\n↓{(1-v/base)*100:.0f}%")
        ax.text(b.get_x() + b.get_width() / 2, v, lab, ha="center", va="bottom",
                fontsize=10)
    ax.set_title("分級保管期可大幅降低穩態庫存（上界估計，假設無人領回）\n"
                 "流入量＝官方年均8.6萬件；價值構成＝本資料集比例；縮短保管期涉及修法")
    ax.set_ylabel("穩態庫存（件）")
    ax.margins(y=0.18)
    fig.tight_layout()
    fig.savefig(config.FIG / "10_retention_scenarios.png", dpi=130)
    plt.close(fig)
    for k, v in scen.items():
        print(f"[extra] {k.replace(chr(10),'')}：{v:,.0f} 件"
              + ("" if v == base else f"（↓{(1-v/base)*100:.0f}%）"))


def run(fact_lost, fact_ridership):
    """
    一次跑完這個檔的四張延伸圖。

    Input:
        fact_lost (DataFrame): 清好的遺失物表。
        fact_ridership (DataFrame): 每天每站的人流表。

    Output:
        依序產出 07~10 四張圖，沒有回傳值。
    """
    fig_recoverability(fact_lost)
    fig_weekday_rate(fact_lost, fact_ridership)
    fig_depot_keep(fact_lost)
    fig_retention_scenarios(fact_lost)
    print(f"[extra] 已輸出 07_recoverability / 08_weekday_rate / 09_depot_keep / "
          f"10_retention_scenarios")
