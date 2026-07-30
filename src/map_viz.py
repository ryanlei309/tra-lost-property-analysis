"""
臺鐵遺失物開放資料分析
-----------------------
File: map_viz.py
-----------------------
DESCRIPTION: 這個檔案畫全臺各站的遺失率地圖。點的顏色代表站內遺失率（每十萬
人次掉幾件），點的大小代表遺失件數。跟 build_tables 一致，只用掉在車站的遺失
（約 37%）。會輸出兩個版本：
  outputs/figures/05_loss_rate_map.png   靜態圖
  outputs/figures/05_loss_rate_map.html  互動地圖（folium，可以用滑鼠點站看細節）
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
    """
    畫圖前的共同前處理：留下有座標、有遺失、有人流的站，並把色階上限壓一下。

    Input:
        agg (DataFrame): build_agg_station 產出的每站彙總表。

    Returns:
        d (DataFrame): 篩選後、且多了 rate_clip 欄位的表。
        cap (float): 遺失率的 95 百分位，拿來當色階上限。
    """
    d = agg[(agg["lat"].notna()) & (agg["lost_count"] > 0) &
            (agg["throughput_window"] > 0)].copy()
    # 顏色用遺失率，但少數幾個極端值會把整個色階壓扁，
    # 所以取 95 百分位當上限，超過的都夾到上限，讓顏色差異看得出來。
    cap = d["loss_rate_per_100k"].quantile(0.95)
    d["rate_clip"] = d["loss_rate_per_100k"].clip(upper=cap)
    return d, cap


def static_map(agg):
    """
    畫靜態版的遺失率地圖，存成 05_loss_rate_map.png。

    Input:
        agg (DataFrame): 每站彙總表。

    Output:
        存一張 PNG 到 outputs/figures，沒有回傳值。
    """
    d, cap = _prep(agg)
    fig, ax = plt.subplots(figsize=(7, 9))
    # 用經緯度當座標散點，顏色是遺失率、大小是遺失件數開根號（避免大站太誇張）。
    sc = ax.scatter(d["lon"], d["lat"], c=d["rate_clip"], cmap="YlOrRd",
                    s=np.sqrt(d["lost_count"]) * 9, alpha=0.85,
                    edgecolor="#555", linewidth=0.4)
    # 標出遺失率最高的幾站，但要件數達門檻才標，免得標到雜訊小站。
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
    """
    畫互動版的遺失率地圖（folium），存成 05_loss_rate_map.html。

    Input:
        agg (DataFrame): 每站彙總表。

    Output:
        存一個 HTML 到 outputs/figures。如果沒裝 folium，就印個訊息跳過，
        不會讓整條管線掛掉。
    """
    # folium 是選用套件，沒裝就跳過互動地圖，靜態圖還是有。
    try:
        import folium
    except ImportError:
        print("[map] 未安裝 folium，略過互動地圖")
        return
    d, cap = _prep(agg)
    m = folium.Map(location=[23.7, 121.0], zoom_start=7, tiles="CartoDB positron")
    # 依遺失率高低分四段上色（越紅越嚴重）。
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
            # 滑鼠點下去會跳出這個站的件數、遺失率、高價值佔比。
            popup=folium.Popup(
                f"<b>{r['sta_name']}站</b><br>遺失件數：{int(r['lost_count'])}<br>"
                f"遺失率：{r['loss_rate_per_100k']:.1f} /十萬人次<br>"
                f"高價值佔比：{(r['high_value_share'] or 0)*100:.0f}%", max_width=220),
        ).add_to(m)
    out = config.FIG / "05_loss_rate_map.html"
    m.save(str(out))
    print(f"[map] 互動地圖已存：{out}")
