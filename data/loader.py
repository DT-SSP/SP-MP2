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
from google.cloud import storage

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

# 👉 1. 환경변수에서 버킷 이름을 가져오고, GCS 클라이언트 생성
# 클라우드 런 배포 시 GCS_BUCKET_NAME 환경변수를 설정해 줍니다.
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "sp-mp-dashboard-cache") 
_storage_client = None

def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        # Cloud Run 환경에서는 자동으로 기본 서비스 계정 권한을 사용합니다.
        _storage_client = storage.Client()
    return _storage_client

def _get_gcs_blob(sheet_info: tuple):
    """GCS Blob 객체와 Pandas용 gs:// 경로를 반환합니다."""
    sheet_id, worksheet_name = sheet_info
    safe = worksheet_name.replace("/", "_").replace(" ", "_").replace(".", "_").replace(",", "_")
    blob_name = f"sheet_cache/{sheet_id[:10]}_{safe}.pkl"
    
    client = _get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_name)
    gs_path = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
    
    return blob, gs_path

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


def _fetch_from_api(sheet_info: tuple) -> pd.DataFrame:
    sheet_id, worksheet_name = sheet_info
    gc = _get_client()

    for attempt in range(4):
        _throttle()
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

    # === 💡 수정된 부분: 컬럼명 중복 방지 로직 추가 ===
    raw_columns = [str(c).strip() for c in data[0]]
    deduplicated_cols = []
    seen = {}
    
    for col in raw_columns:
        if col in seen:
            seen[col] += 1
            deduplicated_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            deduplicated_cols.append(col)

    return pd.DataFrame(data[1:], columns=deduplicated_cols)


def load_sheet(sheet_info: tuple, force_refresh: bool = False) -> pd.DataFrame:
    now = time.time()
    
    # 👉 2. 기존 Path 객체 대신 GCS blob 객체와 경로를 가져옴
    blob, gs_path = _get_gcs_blob(sheet_info) 

    # 0. 강제 새로고침 시 API 호출 전에 캐시 선제적 삭제
    if force_refresh:
        _cache.pop(sheet_info, None)
        if blob.exists():
            try:
                blob.delete()
                logger.info(f"[loader] GCS 캐시 삭제 완료: {sheet_info[1]}")
            except Exception as e:
                logger.warning(f"[loader] GCS 캐시 삭제 실패: {sheet_info[1]} — {e}")

    # 1. 메모리 캐시 (기존 동일)
    if not force_refresh and sheet_info in _cache:
        df, ts = _cache[sheet_info]
        if now - ts < _MEM_TTL:
            return df.copy()

    # 2. GCS 디스크 캐시 확인
    if not force_refresh:
        if blob.exists():
            blob.reload() # 최신 메타데이터 불러오기
            mtime = blob.updated.timestamp()
            if (now - mtime) < _DISK_TTL:
                logger.info(f"[loader] GCS 캐시 읽기: {sheet_info[1]}")
                # pandas가 gcsfs를 사용해 gs:// 경로에서 바로 피클을 읽습니다.
                df = pd.read_pickle(gs_path) 
                _cache[sheet_info] = (df, now)
                return df.copy()

    # 3. Google Sheets API 호출 (기존 동일)
    logger.info(f"[loader] API 읽기: {sheet_info[1]}")
    df = _fetch_from_api(sheet_info)

    # 4. GCS에 저장
    try:
        # pandas가 gcsfs를 사용해 gs:// 경로로 바로 피클을 저장합니다.
        df.to_pickle(gs_path)
    except Exception as e:
        logger.warning(f"[loader] GCS 저장 실패 (메모리 캐시로 동작): {sheet_info[1]} — {e}")

    _cache[sheet_info] = (df, now)
    return df.copy()


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
