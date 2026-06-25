"""월 마감 후 Google Sheets 데이터를 재읽기하여 디스크 캐시를 갱신합니다.

사용법:
    C:\Users\SeAH\anaconda3\envs\violit_bash\Scripts\python.exe refresh_cache.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from data.config import Sheets
from data.loader import refresh_all

if __name__ == "__main__":
    all_sheets = [v for k, v in vars(Sheets).items()
                  if not k.startswith("_") and isinstance(v, tuple)]
    print(f"총 {len(all_sheets)}개 시트 새로고침 시작...")
    refresh_all(all_sheets, max_workers=2)
    print("완료. 대시보드를 재시작하면 새 데이터가 반영됩니다.")
