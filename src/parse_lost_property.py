"""
臺鐵遺失物開放資料分析
-----------------------
File: parse_lost_property.py
Name: Ryan Lei
-----------------------
DESCRIPTION: 這個檔案負責把原始的遺失物 XML 清理成一張乾淨的 fact_lost 表。
每一列就是一件遺失物，除了原本的品名，還會多算幾個衍生欄位：品類、價值層級、
能不能追回、是掉在車站還是車上、掉的站碼或車次、以及最後保管在哪一站。品類/
價值/可追回這幾個欄位是呼叫 categorize.py 算出來的。
"""

import re
import json
import xml.etree.ElementTree as ET
import pandas as pd

from . import config
from .categorize import classify, group_of

# pickupLocation 這個欄位有兩種寫法，用兩個正規表示式分別去比對：
#   一種是「車站: 0900-臺北」，一種是「車次: 228」。
_STATION_RE = re.compile(r"車站:\s*(\d+)-(.+)")
_TRAIN_RE = re.compile(r"車次:\s*(\S+)")


def _keep_addr_to_name():
    """
    做一個「保管站地址 -> 站名」的對照字典。

    Input:
        沒有參數，讀 config.STATION_JSON。

    Returns:
        m (dict): key 是去掉空白的地址，value 是站名。之後拿保管站地址來查，
                  就能還原成站名。
    """
    m = {}
    for s in json.load(open(config.STATION_JSON, encoding="utf-8")):
        # 地址裡的空白去掉再當 key，比對時比較不會因為空白差一格就對不到。
        m["".join(s["stationAddrTw"].split())] = s["stationName"]
    return m


def _text(row, tag):
    """
    從一筆 XML 紀錄裡，安全地把某個標籤的文字取出來。

    Input:
        row: 一筆遺失物的 XML element。
        tag (str): 想抓的子標籤名字。

    Returns:
        取出的文字（去頭尾空白）；如果這個標籤不存在或沒內容，就回空字串。
    """
    el = row.find(tag)
    return (el.text or "").strip() if el is not None else ""


def load_fact_lost():
    """
    讀遺失物 XML，清理並加上衍生欄位，回傳 fact_lost 表。

    Input:
        沒有參數，讀 config.LOST_XML。

    Returns:
        df (DataFrame): 每一列一件遺失物，含品類、價值、可追回、遺失管道、
                        站碼/車次、保管站名等欄位；已濾掉解析不出日期、以及
                        2022 年以前的零星雜訊列。
    """
    # 讀進整棵 XML，一筆一筆處理。
    root = ET.parse(config.LOST_XML).getroot()
    records = []
    for r in root:
        # 先看這件是掉在車站還是車上。兩個正規式各試一次。
        loc = _text(r, "pickupLocation")
        sm, tm = _STATION_RE.match(loc), _TRAIN_RE.match(loc)
        if sm:
            # 車站：抓站碼（補零到四位）跟站名，車次留空。
            channel, sta_code, train_no = "車站", sm.group(1).zfill(4), None
        elif tm:
            # 車次：抓車次號，站碼留空。
            channel, sta_code, train_no = "車次", None, tm.group(1)
        else:
            # 兩種都不是就標成未知。
            channel, sta_code, train_no = "未知", None, None

        # 品名拿去分類，一次拿回品類、價值層級、可不可追回。
        name = _text(r, "propertyName")
        cat, tier, recover = classify(name)
        records.append({
            "pickup_dt": _text(r, "pickupDate"),
            "property_name": name,
            "category": cat,
            "category_group": group_of(cat),
            "value_tier": tier,
            "recoverable": recover,
            "channel": channel,           # 車站 / 車次 / 未知
            "loss_sta_code": sta_code,    # 只有「車站」這類才有
            "train_no": train_no,         # 只有「車次」這類才有
            "keep_addr": _text(r, "keepStationAddr"),
            "feature": _text(r, "propertyFeature"),
        })

    # 收成 DataFrame，把日期字串轉成日期，順便切出年份。
    df = pd.DataFrame(records)
    df["pickup_dt"] = pd.to_datetime(df["pickup_dt"], errors="coerce")
    df["pickup_date"] = df["pickup_dt"].dt.date
    df["year"] = df["pickup_dt"].dt.year

    # 用保管站地址查回站名（給 Tableau 做「保管站 → 站內/車上」連動用）。
    addr2name = _keep_addr_to_name()
    df["keep_sta_name"] = df["keep_addr"].map(
        lambda a: addr2name.get("".join(str(a).split())))

    # 清掉兩種雜訊：日期解析不出來的、還有 2022 年以前的零星舊資料
    # （像 2002、2019、2020 那幾筆），這些不在我們的分析期間內。
    before = len(df)
    df = df[df["pickup_dt"].notna() & (df["year"] >= 2022)].copy()
    print(f"[fact_lost] 原始 {before} 列 -> 保留 {len(df)} 列（濾掉 2022 前雜訊）")
    return df


if __name__ == "__main__":
    # 直接執行時，印前幾列跟遺失管道的分布，快速檢查結果。
    d = load_fact_lost()
    print(d.head())
    print(d["channel"].value_counts())
