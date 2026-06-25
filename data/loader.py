import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

logger = logging.getLogger("loader")

# Google Sheets API 속도 제한 (분당 60건 → 1.1초 간격으로 분당 54건 이하 보장)
_api_rate_lock = threading.Lock()
_api_last_ts: float = 0.0

def _throttle():
    """API 호출을 직렬화해 할당량 초과 방지."""
    global _api_last_ts
    with _api_rate_lock:
        wait = 1.1 - (time.time() - _api_last_ts)
        if wait > 0:
            time.sleep(wait)
        _api_last_ts = time.time()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_KEY_FILE = Path(__file__).parent.parent / "dx-dashboard-common-721b793872e0.json"
_CREDS_JSON_ENV = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")

_MEM_TTL  = 1800        # 메모리 캐시 30분
_DISK_TTL = 86400 * 35  # 디스크 캐시 35일 (월 마감 데이터 기준)
_CACHE_DIR = Path(__file__).parent.parent / ".sheet_cache"

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


def _cache_path(sheet_info: tuple) -> Path:
    sheet_id, worksheet_name = sheet_info
    safe = worksheet_name.replace("/", "_").replace(" ", "_").replace(".", "_").replace(",", "_")
    return _CACHE_DIR / f"{sheet_id[:10]}_{safe}.pkl"


def _fetch_from_api(sheet_info: tuple) -> pd.DataFrame:
    """Google Sheets API에서 읽기. 호출 전 속도 제한 적용, 429 시 재시도."""
    sheet_id, worksheet_name = sheet_info
    gc = _get_client()

    for attempt in range(4):
        _throttle()  # 매 시도마다 속도 제한 적용
        try:
            ws   = gc.open_by_key(sheet_id).worksheet(worksheet_name)
            data = ws.get_all_values(value_render_option='UNFORMATTED_VALUE')
            break
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429 and attempt < 3:
                wait = 2 ** (attempt + 2)  # 4, 8, 16초
                logger.warning(f"[loader] 429 재시도 {attempt+1}/3, {wait}초 대기: {worksheet_name}")
                time.sleep(wait)
            else:
                raise

    return pd.DataFrame(data[1:], columns=[str(c).strip() for c in data[0]])


def load_sheet(sheet_info: tuple, force_refresh: bool = False) -> pd.DataFrame:
    """(SheetID, 워크시트이름) 튜플로 DataFrame 반환.
    로드 우선순위: 메모리 캐시 → 디스크 캐시(pickle) → Google Sheets API
    pickle 사용으로 타입/컬럼명 제약 없이 DataFrame 그대로 저장.
    """
    now = time.time()

    # 1. 메모리 캐시
    if not force_refresh and sheet_info in _cache:
        df, ts = _cache[sheet_info]
        if now - ts < _MEM_TTL:
            return df

    # 2. 디스크 캐시
    if not force_refresh:
        path = _cache_path(sheet_info)
        if path.exists() and (now - path.stat().st_mtime) < _DISK_TTL:
            logger.info(f"[loader] 디스크 캐시: {sheet_info[1]}")
            df = pd.read_pickle(path)
            _cache[sheet_info] = (df, now)
            return df

    # 3. Google Sheets API 호출
    logger.info(f"[loader] API 읽기: {sheet_info[1]}")
    df = _fetch_from_api(sheet_info)

    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        df.to_pickle(_cache_path(sheet_info))
    except Exception as e:
        logger.warning(f"[loader] 디스크 저장 실패 (메모리 캐시로 동작): {sheet_info[1]} — {e}")

    _cache[sheet_info] = (df, now)
    return df


def refresh_all(sheet_infos: list, max_workers: int = 2):
    """모든 시트를 Google Sheets API에서 강제 재읽기. 월 마감 후 수동 실행용.
    max_workers=2 로 제한해 429 할당량 초과 방지."""
    total = len(sheet_infos)
    logger.info(f"[refresh] 전체 새로고침 시작 ({total}개, workers={max_workers})")
    start = time.time()
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(load_sheet, si, True): si for si in sheet_infos}
        for future in as_completed(futures):
            si = futures[future]
            try:
                future.result()
            except Exception as e:
                failed += 1
                logger.warning(f"[refresh] 실패: {si[1]} — {e}")

    elapsed = time.time() - start
    logger.info(f"[refresh] 완료: {total - failed}/{total}개 성공, {elapsed:.1f}초 소요")


def preload_all(sheet_infos: list, max_workers: int = 8):
    """앱 시작 시 모든 시트를 병렬로 캐시에 올립니다.
    디스크 캐시가 있으면 API 호출 없이 즉시 로드됩니다."""
    total = len(sheet_infos)
    logger.info(f"[preload] 시트 {total}개 로딩 시작")
    start = time.time()
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(load_sheet, si): si for si in sheet_infos}
        for future in as_completed(futures):
            si = futures[future]
            try:
                future.result()
            except Exception as e:
                failed += 1
                logger.warning(f"[preload] 실패: {si[1]} — {e}")

    elapsed = time.time() - start
    logger.info(f"[preload] 완료: {total - failed}/{total}개 성공, {elapsed:.1f}초 소요")
