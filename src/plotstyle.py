"""
臺鐵遺失物開放資料分析
-----------------------
File: plotstyle.py
-----------------------
DESCRIPTION: 這個檔案專門處理 matplotlib 畫中文會變成一堆豆腐方框的問題。
不同作業系統內建的中文字型名字都不一樣（Mac、Windows、Linux 各一套），所以
我列了一串候選字型，讓程式自己去找系統裡實際裝了哪一個，找到就用。這樣同一
份程式在別台電腦上跑，圖上的中文也不會壞掉。
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 各平台常見的中文字型，由上往下試，先找到哪個就用哪個。
_CANDIDATES = [
    "PingFang TC", "PingFang SC", "Heiti TC", "Apple LiGothic", "Arial Unicode MS",  # macOS
    "Microsoft JhengHei", "Microsoft YaHei",                                          # Windows
    "Noto Sans CJK TC", "Noto Sans CJK JP", "Noto Sans CJK HK", "Noto Sans CJK SC",   # Linux
    "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
]


def set_cjk_font():
    """
    幫 matplotlib 設定一個系統裡真的有的中文字型。

    Input:
        沒有參數，直接讀取目前這台電腦裝了哪些字型。

    Output:
        會去改 matplotlib 的全域 rcParams，讓之後畫的圖都用得到中文。

    Returns:
        name (str): 最後選到的字型名字；如果整台電腦都找不到，回傳 None。
    """
    # 先問 matplotlib 目前登記到的字型有哪些，收成一個集合方便查。
    available = {f.name for f in font_manager.fontManager.ttflist}

    # 照候選清單一個一個比對，命中就設定完直接回傳。
    for name in _CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [name, *plt.rcParams.get("font.sans-serif", [])]
            plt.rcParams["axes.unicode_minus"] = False
            return name

    # 如果上面都沒中，改用比較笨的後備做法：直接掃系統的字型檔，
    # 看檔名裡有沒有這些關鍵字，有的話手動註冊進來再用。
    for path in font_manager.findSystemFonts():
        low = path.lower()
        if any(k in low for k in ["pingfang", "heiti", "notosanscjk", "msjh", "msyh", "arialuni", "wqy"]):
            try:
                font_manager.fontManager.addfont(path)
                name = font_manager.FontProperties(fname=path).get_name()
                plt.rcParams["font.family"] = "sans-serif"
                plt.rcParams["font.sans-serif"] = [name, *plt.rcParams.get("font.sans-serif", [])]
                plt.rcParams["axes.unicode_minus"] = False
                return name
            except Exception:
                continue

    # 真的一個中文字型都找不到，至少把負號的顯示修好，然後回 None 讓上層知道。
    plt.rcParams["axes.unicode_minus"] = False
    return None
