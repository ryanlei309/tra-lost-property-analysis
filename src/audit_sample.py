"""
分類規則人工稽核工具。

用途：從 fact_lost 隨機抽 100 件，輸出 audit_sample.csv，
     由「人」逐筆判斷分類對不對（這一步必須人工做，是報告可信度的來源）。

步驟：
  1) python -m src.audit_sample            # 產生 data/processed/audit_sample.csv
  2) 用 Excel 開啟，逐筆在「人工判定是否正確」欄填 Y 或 N
     （若 N，可在「備註」寫正確類別）
  3) python -m src.audit_sample --score    # 計算正確率，寫進企劃書方法章
"""
import sys
import pandas as pd

from . import config

OUT = config.PROCESSED / "audit_sample.csv"
N = 100
SEED = 42  # 固定亂數種子，抽樣可重現


def make_sample():
    fl = pd.read_csv(config.PROCESSED / "fact_lost.csv")
    s = fl.sample(N, random_state=SEED)[
        ["property_name", "category", "category_group", "value_tier"]].copy()
    s["人工判定是否正確"] = ""
    s["備註"] = ""
    s.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"已輸出 {OUT}（{N} 件，seed={SEED}）")
    print("請用 Excel 開啟，逐筆在「人工判定是否正確」填 Y/N，存檔後執行 --score")


def score():
    s = pd.read_csv(OUT)
    done = s["人工判定是否正確"].astype(str).str.upper().isin(["Y", "N"])
    if done.sum() == 0:
        print("尚未填寫任何 Y/N。")
        return
    ok = (s.loc[done, "人工判定是否正確"].astype(str).str.upper() == "Y").mean()
    print(f"已稽核 {done.sum()} 件，分類正確率：{ok*100:.1f}%")
    print("→ 企劃書方法章可寫：『隨機抽樣 100 件人工稽核，分類正確率約 XX%』")


if __name__ == "__main__":
    score() if "--score" in sys.argv else make_sample()
