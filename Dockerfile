FROM python:3.11-slim AS base

# 보안: non-root 유저 생성
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# 의존성 설치 (레이어 캐싱 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 소스코드 복사
COPY . .

# static 파일 수집
RUN SECRET_KEY=build-placeholder python manage.py collectstatic --noinput 2>/dev/null || true

# 미디어 디렉토리 생성 및 권한 설정
RUN mkdir -p /app/media /app/posts && chown -R appuser:appuser /app

# non-root 유저로 전환
USER appuser

EXPOSE 8000

# gunicorn으로 프로덕션 서빙
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
