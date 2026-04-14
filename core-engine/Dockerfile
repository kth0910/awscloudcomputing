# ============================================================
# 멀티스테이지 빌드: 의존성 설치 단계
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# 시스템 빌드 의존성 설치 (asyncpg 등 C 확장 컴파일용)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 의존성 파일만 먼저 복사하여 Docker 캐시 활용
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# 프로덕션 런타임 단계
# ============================================================
FROM python:3.12-slim AS runtime

# libpq는 asyncpg 런타임에 필요
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# 비루트 사용자 생성 (보안 강화)
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# 빌더 단계에서 설치된 Python 패키지 복사
COPY --from=builder /install /usr/local

# 애플리케이션 코드 복사
COPY . .

# 파일 소유권을 비루트 사용자로 변경
RUN chown -R appuser:appuser /app

# 비루트 사용자로 전환
USER appuser

EXPOSE 8000

# 헬스 체크: /health 엔드포인트로 컨테이너 상태 확인
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
