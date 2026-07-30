"""
臺鐵遺失物開放資料分析
-----------------------
File: fetch_tdx.py
-----------------------
DESCRIPTION: 這個檔案負責去 TDX 平台抓臺鐵的列車時刻，做出一張車次對照表
dim_train。遺失物裡有大約 63% 是「車次: 228」這種車上遺失，光看車次號看不出
是什麼車、開去哪，所以要靠這張表把車次對應到車種（自強／區間…）、起訖站、以
及停靠站清單，之後的車上遺失分析才做得下去。

為什麼抓「定期時刻表」而不是「每日時刻表」：
  我們的遺失物是 2022–2023 的舊資料，可是 TDX 的「每日」時刻只有近期的日期，
  抓不到兩三年前。車次跟它的路線／車種其實大致穩定，所以改抓
  GeneralTrainTimetable（定期車次時刻表，跟日期無關）當作代理。這是已知的近
  似，報告裡要註明「以現行定期時刻表近似當年車次路線」。

憑證千萬不要寫死在程式裡，改用環境變數：
  macOS/Linux:  export TDX_CLIENT_ID=xxx ; export TDX_CLIENT_SECRET=yyy
  或放在專案根目錄的 .env（已經被 .gitignore 擋掉）：
      TDX_CLIENT_ID=xxx
      TDX_CLIENT_SECRET=yyy

執行方式：
  python -m src.fetch_tdx            # 抓下來並輸出 dim_train.csv
  python -m src.fetch_tdx --inspect  # 先印回傳結構，確認欄位名再正式跑
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
# 定期車次時刻表（v3）。如果你的金鑰只開通 v2，把這行改成 /v2/Rail/TRA/GeneralTrainTimetable
ENDPOINT = "/v3/Rail/TRA/GeneralTrainTimetable"

RAW_JSON = config.RAW / "tdx_general_timetable.json"
DIM_TRAIN = config.PROCESSED / "dim_train.csv"


def _load_dotenv():
    """
    如果專案根目錄有 .env，就把裡面的設定簡單讀進環境變數。

    Input:
        沒有參數，找的是 config.ROOT 底下的 .env。

    Output:
        用 setdefault 寫進 os.environ；本來就設好的環境變數不會被覆蓋。
        故意自己刻一個小讀取器，不想為了這個多裝外部套件。
    """
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            # 跳過空行跟註解，其餘照 key=value 拆一次。
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def get_token():
    """
    用 client credentials 向 TDX 換一組 access token。

    Input:
        沒有參數，讀環境變數 TDX_CLIENT_ID / TDX_CLIENT_SECRET。

    Returns:
        access_token 字串。如果找不到憑證，直接 sys.exit 提醒要先設定。
    """
    cid = os.environ.get("TDX_CLIENT_ID")
    secret = os.environ.get("TDX_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("找不到 TDX_CLIENT_ID / TDX_CLIENT_SECRET，請先設環境變數或建立 .env")
    # 照 OAuth2 的格式把三個欄位編碼成 form data。
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": secret,
    }).encode()
    req = urllib.request.Request(AUTH_URL, data=data,
                                 headers={"content-type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]


def api_get(path, token):
    """
    帶著 token 去打一個 TDX API，回傳解析後的 JSON。

    Input:
        path (str): API 路徑，例如 ENDPOINT。
        token (str): 上面 get_token() 拿到的 access token。

    Returns:
        解析好的 JSON（dict 或 list）。回應如果是 gzip 壓縮的會先解壓。
    """
    url = API_BASE + path
    # 補上 $format=JSON。網址本來有沒有問號，決定要接 & 還是 ?。
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}$format=JSON"
    req = urllib.request.Request(url, headers={
        "authorization": f"Bearer {token}",
        "accept-encoding": "gzip",
        "user-agent": "tra-lost-property-analysis/1.0",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        # 有壓縮就先解開再丟給 json。
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw)


def _zh(val):
    """
    把 TDX 的名稱欄位統一取成中文字串。

    Input:
        val: v3 是 {'Zh_tw': '...', 'En': '...'} 這種 dict；v2 是純字串。

    Returns:
        中文名稱字串。兩種格式都吃，取不到就回空字串。
    """
    if isinstance(val, dict):
        return val.get("Zh_tw") or val.get("zh_tw") or ""
    return val or ""


def to_dim_train(payload):
    """
    把 TDX 回傳的時刻表整理成 dim_train（車次對照表）。

    Input:
        payload: api_get 拿回來的 JSON。

    Returns:
        一個 DataFrame，每一列一個車次，含車種、方向、起訖站、停靠站數、
        以及用「|」串起來的停靠站代碼；重複車次會去掉。
    """
    # v3 的結構長這樣：{'TrainTimetables': [{'TrainInfo': {...}, 'StopTimes': [...]}]}
    # 這裡也順手相容 v2 的欄位名跟直接就是 list 的情況。
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
            "stop_ids": "|".join(stop_ids),     # 停靠站代碼，跟 dim_station.sta_code 同一套編碼
        })
    return pd.DataFrame(rows).drop_duplicates("train_no")


def main():
    # 先讀 .env、換 token，再打 API 把時刻表抓回來。
    _load_dotenv()
    token = get_token()
    print("[tdx] token 取得成功")
    payload = api_get(ENDPOINT, token)

    # --inspect 模式：先別存檔，把筆數跟第一筆結構印出來，確認欄位名對不對。
    if "--inspect" in sys.argv:
        items = payload.get("TrainTimetables") or payload
        print("[tdx] 回傳筆數：", len(items))
        print("[tdx] 第一筆結構：")
        print(json.dumps(items[0], ensure_ascii=False, indent=2)[:1500])
        return

    # 正式模式：原始 JSON 留一份備查，整理成 dim_train 存成 CSV。
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
