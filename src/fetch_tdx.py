"""
TDX 列車時刻抓取  ->  dim_train（車次對照表）

用途：把遺失物裡「車次: 228」那 63% 的車上遺失，對應到
      車種（自強/區間…）、起訖站、停靠站清單，供後續車上遺失分析。

【為什麼抓「定期時刻表」而不是「每日時刻表」】
  我們的遺失物是 2022–2023 的舊資料，但 TDX 的『每日』時刻只涵蓋近期日期，
  抓不到兩三年前的歷史。車次與其路線/車種大致穩定，所以改用
  GeneralTrainTimetable（定期車次時刻表，與日期無關）建一張對照表當代理。
  → 這是已知近似：報告中需註明「以現行定期時刻表近似當年車次路線」。

【憑證】不要寫進程式！用環境變數：
  macOS/Linux:  export TDX_CLIENT_ID=xxx ; export TDX_CLIENT_SECRET=yyy
  或放在專案根目錄 .env（已被 .gitignore 擋住）：
      TDX_CLIENT_ID=xxx
      TDX_CLIENT_SECRET=yyy

執行：
  python -m src.fetch_tdx            # 抓取並輸出 dim_train.csv
  python -m src.fetch_tdx --inspect  # 先印出回傳結構，確認欄位名再正式跑
"""
import os
import sys
import json
import gzip
import urllib.parse
import urllib.request

import pandas as pd

from . import config

AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
API_BASE = "https://tdx.transportdata.tw/api/basic"
# 定期車次時刻表（v3）。若你的金鑰僅開通 v2，改成 /v2/Rail/TRA/GeneralTrainTimetable
ENDPOINT = "/v3/Rail/TRA/GeneralTrainTimetable"

RAW_JSON = config.RAW / "tdx_general_timetable.json"
DIM_TRAIN = config.PROCESSED / "dim_train.csv"


def _load_dotenv():
    """若根目錄有 .env，簡單讀進環境變數（不依賴外部套件）。"""
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def get_token() -> str:
    cid = os.environ.get("TDX_CLIENT_ID")
    secret = os.environ.get("TDX_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("找不到 TDX_CLIENT_ID / TDX_CLIENT_SECRET，請先設環境變數或建立 .env")
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": secret,
    }).encode()
    req = urllib.request.Request(AUTH_URL, data=data,
                                 headers={"content-type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]


def api_get(path: str, token: str):
    url = API_BASE + path
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}$format=JSON"
    req = urllib.request.Request(url, headers={
        "authorization": f"Bearer {token}",
        "accept-encoding": "gzip",
        "user-agent": "tra-lost-property-analysis/1.0",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw)


def _zh(val):
    """TDX v3 名稱是 {'Zh_tw': '...', 'En': '...'}；v2 是純字串。兩種都吃。"""
    if isinstance(val, dict):
        return val.get("Zh_tw") or val.get("zh_tw") or ""
    return val or ""


def to_dim_train(payload) -> pd.DataFrame:
    # v3: {'TrainTimetables': [{'TrainInfo': {...}, 'StopTimes': [...]}]}
    items = payload.get("TrainTimetables") or payload.get("TrainTimetable") or payload
    rows = []
    for tt in items:
        info = tt.get("TrainInfo", tt)
        stops = tt.get("StopTimes", [])
        stop_ids = [str(s.get("StationID", "")) for s in stops]
        rows.append({
            "train_no": str(info.get("TrainNo", "")),
            "train_type": _zh(info.get("TrainTypeName")),
            "direction": info.get("Direction"),
            "start_id": str(info.get("StartingStationID", "")),
            "start_name": _zh(info.get("StartingStationName")),
            "end_id": str(info.get("EndingStationID", "")),
            "end_name": _zh(info.get("EndingStationName")),
            "n_stops": len(stop_ids),
            "stop_ids": "|".join(stop_ids),     # 停靠站代碼（與 dim_station.sta_code 同制）
        })
    return pd.DataFrame(rows).drop_duplicates("train_no")


def main():
    _load_dotenv()
    token = get_token()
    print("[tdx] token 取得成功")
    payload = api_get(ENDPOINT, token)

    if "--inspect" in sys.argv:
        items = payload.get("TrainTimetables") or payload
        print("[tdx] 回傳筆數：", len(items))
        print("[tdx] 第一筆結構：")
        print(json.dumps(items[0], ensure_ascii=False, indent=2)[:1500])
        return

    RAW_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    dim = to_dim_train(payload)
    dim.to_csv(DIM_TRAIN, index=False, encoding="utf-8-sig")
    print(f"[tdx] 車次數：{len(dim)}")
    print(f"[tdx] 車種分布：{dim['train_type'].value_counts().head(8).to_dict()}")
    print(f"[tdx] 已輸出：{DIM_TRAIN}")
    print("[tdx] 提醒：stop_ids 內是車站代碼，可與 dim_station.sta_code 對應；"
          "請抽查一筆確認格式一致。")


if __name__ == "__main__":
    main()
