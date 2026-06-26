"""第二層（解析清理）：遺失物 XML -> 乾淨的 fact_lost。

每一列 = 一件遺失物，帶上衍生欄位：品類、價值層級、可追回、遺失管道、站碼/車次。
"""
import re
import xml.etree.ElementTree as ET
import pandas as pd

from . import config
from .categorize import classify, group_of

# 從 pickupLocation 解析的兩種格式
_STATION_RE = re.compile(r"車站:\s*(\d+)-(.+)")
_TRAIN_RE = re.compile(r"車次:\s*(\S+)")


def _text(row, tag):
    el = row.find(tag)
    return (el.text or "").strip() if el is not None else ""


def load_fact_lost() -> pd.DataFrame:
    root = ET.parse(config.LOST_XML).getroot()
    records = []
    for r in root:
        loc = _text(r, "pickupLocation")
        sm, tm = _STATION_RE.match(loc), _TRAIN_RE.match(loc)
        if sm:
            channel, sta_code, train_no = "車站", sm.group(1).zfill(4), None
        elif tm:
            channel, sta_code, train_no = "車次", None, tm.group(1)
        else:
            channel, sta_code, train_no = "未知", None, None

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
            "loss_sta_code": sta_code,    # 僅「車站」紀錄有
            "train_no": train_no,         # 僅「車次」紀錄有
            "keep_addr": _text(r, "keepStationAddr"),
            "feature": _text(r, "propertyFeature"),
        })

    df = pd.DataFrame(records)
    df["pickup_dt"] = pd.to_datetime(df["pickup_dt"], errors="coerce")
    df["pickup_date"] = df["pickup_dt"].dt.date
    df["year"] = df["pickup_dt"].dt.year

    # 清掉解析不出日期、以及 2022 年以前的零星雜訊列（2002/2019/2020）
    before = len(df)
    df = df[df["pickup_dt"].notna() & (df["year"] >= 2022)].copy()
    print(f"[fact_lost] 原始 {before} 列 -> 保留 {len(df)} 列（濾掉 2022 前雜訊）")
    return df


if __name__ == "__main__":
    d = load_fact_lost()
    print(d.head())
    print(d["channel"].value_counts())
