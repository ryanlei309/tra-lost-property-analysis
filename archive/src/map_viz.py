"""第四層延伸：全臺站別遺失率地圖。

顏色=站內遺失率（每十萬人次遺失件數），點大小=遺失件數。
只用「車站」遺失（37%），與 build_tables 一致。
輸出：
  outputs/figures/05_loss_rate_map.png   靜態
  outputs/figures/05_loss_rate_map.html  互動（folium，可滑鼠查看）
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config

from .plotstyle import set_cjk_font
set_cjk_font()


def _prep(agg):
    d = agg[(agg["lat"].notna()) & (agg["lost_count"] > 0) &
            (agg["throughput_window"] > 0)].copy()
    # 顏色用遺失率，但極端值會壓縮色階 -> 取 95 百分位上限
    cap = d["loss_rate_per_100k"].quantile(0.95)
    d["rate_clip"] = d["loss_rate_per_100k"].clip(upper=cap)
    return d, cap


def static_map(agg):
    d, cap = _prep(agg)
    fig, ax = plt.subplots(figsize=(7, 9))
    sc = ax.scatter(d["lon"], d["lat"], c=d["rate_clip"], cmap="YlOrRd",
                    s=np.sqrt(d["lost_count"]) * 9, alpha=0.85,
                    edgecolor="#555", linewidth=0.4)
    # 標註遺失率最高的幾站（且件數達門檻，避免雜訊）
    top = d[d["lost_count"] >= config.MIN_LOSS_COUNT].nlargest(6, "loss_rate_per_100k")
    for _, r in top.iterrows():
        ax.annotate(f"{r['sta_name']}站", (r["lon"], r["lat"]),
                    fontsize=9,
                    xytext=(5, 0), textcoords="offset points")
    cb = fig.colorbar(sc, ax=ax, shrink=0.6)
    cb.set_label("站內遺失率（每十萬人次，色階上限為95百分位）")
    ax.set_title("全臺站別遺失率地圖\n（點大小=遺失件數，顏色越紅=每人次掉得越多）")
    ax.set_xlabel("經度"); ax.set_ylabel("緯度")
    ax.set_aspect(1.05)
    fig.tight_layout()
    fig.savefig(config.FIG / "05_loss_rate_map.png", dpi=130)
    plt.close(fig)


def interactive_map(agg):
    try:
        import folium
    except ImportError:
        print("[map] 未安裝 folium，略過互動地圖")
        return
    d, cap = _prep(agg)
    m = folium.Map(location=[23.7, 121.0], zoom_start=7, tiles="CartoDB positron")
    def color(rate):
        if rate >= cap * 0.8: return "#bd0026"
        if rate >= cap * 0.5: return "#f03b20"
        if rate >= cap * 0.25: return "#fd8d3c"
        return "#fed976"
    for _, r in d.iterrows():
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=float(np.sqrt(r["lost_count"]) * 1.1 + 2),
            color=color(r["loss_rate_per_100k"]), fill=True,
            fill_color=color(r["loss_rate_per_100k"]), fill_opacity=0.75, weight=1,
            popup=folium.Popup(
                f"<b>{r['sta_name']}站</b><br>遺失件數：{int(r['lost_count'])}<br>"
                f"遺失率：{r['loss_rate_per_100k']:.1f} /十萬人次<br>"
                f"高價值佔比：{(r['high_value_share'] or 0)*100:.0f}%", max_width=220),
        ).add_to(m)
    out = config.FIG / "05_loss_rate_map.html"
    m.save(str(out))
    print(f"[map] 互動地圖已存：{out}")
