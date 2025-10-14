# 1. Python 베이스 이미지 선택
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 의존성 복사 & 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 앱 코드 복사
COPY . .

# 5. 환경변수 설정
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV PORT=5000

# 6. Gunicorn 실행 명령 (프로덕션 준비)
# --pythonpath . 옵션을 제거하고 PYTHONPATH 환경 변수에 의존
CMD gunicorn --bind 0.0.0.0:$PORT -w 4 app:app
