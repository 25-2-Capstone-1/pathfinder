# 1. Python 베이스 이미지 선택
FROM python:3.10-slim

# 2. 작업 디렉토리 설정 (프로젝트 루트)
WORKDIR /app

# 3. 의존성 복사 & 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 4. 앱 코드 복사
COPY . .

# 5. 환경변수 설정
ENV PYTHONPATH="/app"
ENV FLASK_RUN_HOST=0.0.0.0
ENV PORT=5000

# 6. Gunicorn 실행 (Flask 객체: app/app.py 안의 app)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "-w", "4", "app.app:app"]
