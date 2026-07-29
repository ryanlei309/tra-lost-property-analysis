"""跨平台中文字型設定：自動挑選系統可用的 CJK 字型（Mac/Windows/Linux 通用）。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

_CANDIDATES = [
    "PingFang TC", "PingFang SC", "Heiti TC", "Apple LiGothic", "Arial Unicode MS",  # macOS
    "Microsoft JhengHei", "Microsoft YaHei",                                          # Windows
    "Noto Sans CJK TC", "Noto Sans CJK JP", "Noto Sans CJK HK", "Noto Sans CJK SC",   # Linux
    "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
]

def set_cjk_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [name, *plt.rcParams.get("font.sans-serif", [])]
            plt.rcParams["axes.unicode_minus"] = False
            return name
    # 後備：直接掃字型檔註冊
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
    plt.rcParams["axes.unicode_minus"] = False
    return None