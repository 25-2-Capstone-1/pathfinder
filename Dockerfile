# 1. Python 베이스 이미지 선택
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app_service

# 3. 의존성 복사 & 설치
# Gunicorn이 requirements.txt에 포함되어 있어야 합니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 앱 코드 복사
COPY . .

# 5. 환경변수 설정 (Gunicorn 사용 시 대부분 불필요하지만 유지)
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# PORT 환경변수는 Gunicorn 명령어에서 사용됩니다.
ENV PORT=5000

# 6. Gunicorn 실행 명령 (프로덕션 준비)
# Gunicorn은 'app:app' 구문을 사용하여 app.py 파일에서 'app'이라는 Flask 인스턴스를 찾습니다.
# --bind 0.0.0.0:5000으로 모든 외부 접속을 허용합니다.
# -w 4는 4개의 워커 프로세스를 사용하여 성능을 향상시킵니다.
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT}", "-w", "4", "app:app"]
