"""第四層（分析指標）+ 圖：驗證三條分析線可行性。

產出：
  1. 遺失率離群分析（lost ~ throughput 線性迴歸殘差，找出掉得異常多/少的站）
  2. 品類 / 價值層級結構
  3. 逆物流：保管站集中度（領回摩擦）
  4. 遺失管道：車上 vs 站內
圖存到 outputs/figures/，表存到 outputs/tables/。
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Noto Sans CJK HK", "Noto Sans CJK JP"]
plt.rcParams["axes.unicode_minus"] = False


def loss_rate_outliers(agg: pd.DataFrame, min_count: int = None) -> pd.DataFrame:
    """用 log(throughput) 對 lost_count 做線性迴歸，殘差為正=掉得比人流預期多。
    迴歸用所有有遺失的站擬合；但只回報件數達門檻的站，避免低件數雜訊。"""
    if min_count is None:
        min_count = config.MIN_LOSS_COUNT
    d = agg[(agg["lost_count"] > 0) & (agg["throughput_window"] > 0)].copy()
    x = np.log10(d["throughput_window"])
    y = np.log10(d["lost_count"])
    b, a = np.polyfit(x, y, 1)            # y = b*x + a
    d["expected_log"] = b * x + a
    d["residual"] = (y - d["expected_log"]).round(3)
    d["fit_b"], d["fit_a"] = b, a
    d = d[d["lost_count"] >= min_count]
    return d.sort_values("residual", ascending=False)


def fig_loss_scatter(d: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(d["throughput_window"], d["lost_count"], s=28, alpha=0.6,
               color="#1D9E75", edgecolor="white", linewidth=0.5)
    xs = np.logspace(np.log10(d["throughput_window"].min()),
                     np.log10(d["throughput_window"].max()), 50)
    b, a = d["fit_b"].iloc[0], d["fit_a"].iloc[0]
    ax.plot(xs, 10 ** (b * np.log10(xs) + a), "--", color="#993C1D",
            lw=1.5, label="迴歸趨勢線")
    for _, r in pd.concat([d.head(5), d.tail(3)]).iterrows():
        ax.annotate(r["sta_name"], (r["throughput_window"], r["lost_count"]),
                    fontsize=9, xytext=(4, 3), textcoords="offset points")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("分析期間總人流（進+出，對數）")
    ax.set_ylabel("站內遺失件數（對數）")
    ax.set_title("各站遺失件數 vs 人流：趨勢線上方=掉得比預期多")
    ax.legend(); fig.tight_layout()
    fig.savefig(config.FIG / "01_loss_rate_outliers.png", dpi=130)
    plt.close(fig)


def fig_category(fact_lost: pd.DataFrame):
    cat = fact_lost["category"].value_counts()
    tier = fact_lost["value_tier"].value_counts().reindex(["高", "中", "低", "未知"]).dropna()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    cat.sort_values().plot.barh(ax=ax1, color="#378ADD")
    ax1.set_title("遺失物品類分布"); ax1.set_xlabel("件數")
    tier.plot.bar(ax=ax2, color=["#993C1D", "#EF9F27", "#1D9E75", "#888780"][:len(tier)])
    ax2.set_title("價值層級分布（v2 分類）"); ax2.set_ylabel("件數")
    ax2.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(config.FIG / "02_category_value.png", dpi=130)
    plt.close(fig)


def fig_reverse_logistics(fact_lost: pd.DataFrame):
    keep = fact_lost["keep_addr"].replace("", np.nan).dropna().value_counts().head(8)
    # 取地址前段當標籤
    labels = [a[:11] + "…" if len(a) > 11 else a for a in keep.index]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(range(len(keep)), keep.values, color="#534AB7")
    ax.set_yticks(range(len(keep))); ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_title("保管站集中度：遺失物最終存放地（逆物流/領回摩擦）")
    ax.set_xlabel("保管件數")
    for i, v in enumerate(keep.values):
        ax.text(v, i, f" {v} ({v/len(fact_lost)*100:.0f}%)", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(config.FIG / "03_reverse_logistics.png", dpi=130)
    plt.close(fig)


def _bezier_ribbon(ax, x0, y0a, y0b, x1, y1a, y1b, color, alpha=0.55):
    """畫一條兩端等寬的流向緞帶（上下邊各一條三次貝茲曲線）。"""
    from matplotlib.path import Path
    import matplotlib.patches as patches
    mx = (x0 + x1) / 2
    verts = [(x0, y0a), (mx, y0a), (mx, y1a), (x1, y1a),
             (x1, y1b), (mx, y1b), (mx, y0b), (x0, y0b), (x0, y0a)]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.CLOSEPOLY]
    ax.add_patch(patches.PathPatch(Path(verts, codes), facecolor=color,
                                   edgecolor="none", alpha=alpha))


def fig_channel_flow(fact_lost: pd.DataFrame, addr2name: dict, top_n=5):
    """Sankey：站內遺失 / 車上遺失  ->  最終保管站。寬度=件數。"""
    df = fact_lost.copy()
    df["keep_name"] = df["keep_addr"].map(lambda a: addr2name.get("".join(str(a).split())))
    df = df[df["channel"].isin(["車站", "車次"]) & df["keep_name"].notna()]
    src_label = {"車站": "站內遺失", "車次": "車上遺失"}

    dests = list(df["keep_name"].value_counts().head(top_n).index)
    def dkey(n): return n if n in dests else "其他/分散"
    df["dest"] = df["keep_name"].map(dkey)
    dest_order = dests + ["其他/分散"]

    flows = df.groupby(["channel", "dest"]).size().reset_index(name="n")
    sources = ["車站", "車次"]
    total = len(df)
    gap = total * 0.04

    # 左右節點的垂直堆疊位置
    src_sizes = df["channel"].value_counts().reindex(sources)
    dst_sizes = df["dest"].value_counts().reindex(dest_order)

    def stack(sizes):
        pos = {}; y = 0
        for k, v in sizes.items():
            pos[k] = (y, y + v); y += v + gap
        return pos, y
    spos, sh = stack(src_sizes)
    dpos, dh = stack(dst_sizes)

    palette = ["#534AB7", "#1D9E75", "#378ADD", "#EF9F27", "#D85A30", "#888780", "#D4537E"]
    dcolor = {d: palette[i % len(palette)] for i, d in enumerate(dest_order)}

    fig, ax = plt.subplots(figsize=(11, 7))
    x0, x1, w = 0.0, 1.0, 0.05
    # 各節點內部依 dest 順序分配緞帶起訖位置
    s_cursor = {s: spos[s][0] for s in sources}
    d_cursor = {d: dpos[d][0] for d in dest_order}
    for s in sources:
        for d in dest_order:
            row = flows[(flows["channel"] == s) & (flows["dest"] == d)]
            if row.empty:
                continue
            n = int(row["n"].iloc[0])
            y0a = s_cursor[s]; y0b = y0a + n; s_cursor[s] = y0b
            y1a = d_cursor[d]; y1b = y1a + n; d_cursor[d] = y1b
            _bezier_ribbon(ax, x0 + w, y0a, y0b, x1, y1a, y1b, dcolor[d])
    # 節點長條
    import matplotlib.patches as patches
    for s in sources:
        y0, y1 = spos[s]
        ax.add_patch(patches.Rectangle((x0, y0), w, y1 - y0, color="#3C3489"))
        ax.text(x0 - 0.02, (y0 + y1) / 2, f"{src_label[s]}\n{int(src_sizes[s]):,}件",
                ha="right", va="center", fontsize=11)
    for d in dest_order:
        y0, y1 = dpos[d]
        ax.add_patch(patches.Rectangle((x1, y0), w, y1 - y0, color=dcolor[d]))
        ax.text(x1 + w + 0.02, (y0 + y1) / 2,
                f"{d}  {int(dst_sizes[d]):,}", ha="left", va="center", fontsize=10)
    ax.set_xlim(-0.35, 1.45); ax.set_ylim(-gap, max(sh, dh)); ax.invert_yaxis()
    ax.axis("off")
    ax.set_title("遺失物流向：站內遺失 vs 車上遺失，最終存到哪一站", fontsize=13)
    fig.tight_layout()
    fig.savefig(config.FIG / "04_channel_flow.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def summary(fact_lost, agg, outliers):
    lines = []
    P = lines.append
    P("=" * 60); P("PROTOTYPE 結果摘要"); P("=" * 60)
    P(f"遺失物總件數（2022-2023H1）：{len(fact_lost):,}")
    ch = fact_lost["channel"].value_counts()
    P(f"  遺失管道：車上 {ch.get('車次',0):,} / 站內 {ch.get('車站',0):,}")
    P(f"  品類覆蓋：其他(未分類) {(fact_lost['category']=='其他').mean()*100:.1f}%")
    P("")
    P("【掉得比人流預期『多』的前5站】(殘差↑)")
    for _, r in outliers.head(5).iterrows():
        P(f"  {r['sta_name']:>4}  遺失{int(r['lost_count']):>4} 人流{int(r['throughput_window']):>10,} 殘差{r['residual']:+.2f}")
    P("【掉得比人流預期『少』的後3站】(殘差↓)")
    for _, r in outliers.tail(3).iterrows():
        P(f"  {r['sta_name']:>4}  遺失{int(r['lost_count']):>4} 人流{int(r['throughput_window']):>10,} 殘差{r['residual']:+.2f}")
    P("")
    keep = fact_lost["keep_addr"].replace("", np.nan).dropna().value_counts()
    top = keep.head(1)
    P(f"【逆物流】最大保管點佔比：{top.values[0]/len(fact_lost)*100:.0f}%  ({top.index[0][:14]})")
    txt = "\n".join(lines)
    print(txt)
    (config.TBL / "prototype_summary.txt").write_text(txt, encoding="utf-8")
