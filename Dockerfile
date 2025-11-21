# 1. Python 베이스 이미지
FROM python:3.10-slim

# 2. 작업 디렉토리
WORKDIR /app

# 3. 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 앱 코드 복사
COPY . .

# 5. 환경 변수 설정
ENV FLASK_RUN_HOST=0.0.0.0
ENV PORT=5000
ENV PYTHONPATH="/app"

# 6. Gunicorn 실행
# app.py → main.py로 변경됨
CMD ["gunicorn", "--chdir", "/app", "--bind", "0.0.0.0:5000", "-w", "4", "app:main"]
