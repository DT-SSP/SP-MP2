import json
import os
import time
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_KEY_FILE = Path(__file__).parent.parent / "ssp-kpiapp-2dc176438fd1.json"
_CREDS_JSON_ENV = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")

_CACHE_TTL = 1800  # 30분
_cache: dict[tuple, tuple] = {}  # sheet_info -> (DataFrame, timestamp)
_client = None
_client_ts = 0


def _get_client():
    global _client, _client_ts
    if _client is None or time.time() - _client_ts > 3600:
        if _CREDS_JSON_ENV:
            creds = Credentials.from_service_account_info(
                json.loads(_CREDS_JSON_ENV), scopes=SCOPES
            )
        else:
            creds = Credentials.from_service_account_file(str(_KEY_FILE), scopes=SCOPES)
        _client = gspread.authorize(creds)
        _client_ts = time.time()
    return _client


def load_sheet(sheet_info: tuple) -> pd.DataFrame:
    """(SheetID, 워크시트이름) 튜플로 DataFrame 반환 (5분 캐시).
    429 Quota 에러 시 지수 백오프로 최대 4회 재시도."""
    now = time.time()
    if sheet_info in _cache:
        df, ts = _cache[sheet_info]
        if now - ts < _CACHE_TTL:
            return df

    sheet_id, worksheet_name = sheet_info
    gc = _get_client()

    for attempt in range(5):
        try:
            ws   = gc.open_by_key(sheet_id).worksheet(worksheet_name)
            data = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
            break
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429 and attempt < 4:
                time.sleep(2 ** (attempt + 1))  # 2, 4, 8, 16초
            else:
                raise

    df = pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])
    _cache[sheet_info] = (df, now)
    return df
