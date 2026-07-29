"""
臺鐵遺失物開放資料分析
-----------------------
File: audit_sample.py
Name: Ryan Lei
-----------------------
DESCRIPTION: 這個檔案是分類規則的人工稽核工具。品類/價值是規則式判定，多少帶
主觀，所以要抽一批出來由「人」逐筆檢查對不對，算出正確率寫進報告——這一步是
整份分析可信度的來源，不能省。

用法：
  1) python -m src.audit_sample            # 產生 data/processed/audit_sample.csv
  2) 用 Excel 打開，逐筆在「人工判定是否正確」欄填 Y 或 N
     （如果填 N，可以在「備註」寫正確的類別）
  3) python -m src.audit_sample --score    # 算正確率，寫進企劃書方法章
"""

import sys
import pandas as pd

from . import config

OUT = config.PROCESSED / "audit_sample.csv"
N = 100
SEED = 42  # 固定亂數種子，這樣抽出來的樣本可以重現


def make_sample():
    """
    從 fact_lost 隨機抽 N 件，輸出成待稽核的 CSV。

    Input:
        沒有參數，讀 processed/fact_lost.csv。

    Output:
        寫出 audit_sample.csv（含兩個待人工填的欄位），沒有回傳值。
    """
    fl = pd.read_csv(config.PROCESSED / "fact_lost.csv")
    # 抽樣時只留下判斷會用到的欄位，另外開兩個空欄給人填。
    s = fl.sample(N, random_state=SEED)[
        ["property_name", "category", "category_group", "value_tier"]].copy()
    s["人工判定是否正確"] = ""
    s["備註"] = ""
    # 用 utf-8-sig，Excel 打開中文才不會亂碼。
    s.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"已輸出 {OUT}（{N} 件，seed={SEED}）")
    print("請用 Excel 開啟，逐筆在「人工判定是否正確」填 Y/N，存檔後執行 --score")


def score():
    """
    讀回填好的 CSV，算出分類正確率。

    Input:
        沒有參數，讀上面產生的 audit_sample.csv。

    Output:
        印出已稽核件數與正確率；如果都還沒填就提醒一下，沒有回傳值。
    """
    s = pd.read_csv(OUT)
    # 只算有填 Y 或 N 的列。
    done = s["人工判定是否正確"].astype(str).str.upper().isin(["Y", "N"])
    if done.sum() == 0:
        print("尚未填寫任何 Y/N。")
        return
    # 正確率 = 填 Y 的比例。
    ok = (s.loc[done, "人工判定是否正確"].astype(str).str.upper() == "Y").mean()
    print(f"已稽核 {done.sum()} 件，分類正確率：{ok*100:.1f}%")
    print("→ 企劃書方法章可寫：『隨機抽樣 100 件人工稽核，分類正確率約 XX%』")


if __name__ == "__main__":
    # 有帶 --score 就算分，否則就是產生新樣本。
    score() if "--score" in sys.argv else make_sample()
