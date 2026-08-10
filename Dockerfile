# 1. 파이썬 베이스 이미지 선택 (원하는 버전에 맞춰 수정 가능)
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 요구사항 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 앱 소스코드 전체 복사
COPY . .

# 5. Cloud Run 환경에 맞춰 앱 실행 (main2.py 실행)
CMD ["python", "main2.py"]