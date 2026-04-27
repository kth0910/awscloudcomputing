"""
FastAPI 앱 진입점

Core Engine의 메인 애플리케이션 모듈이다.
CORS 미들웨어, 글로벌 예외 핸들러, 라우터 등록을 담당한다.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from fastapi import Depends

from app.config import get_settings
from app.exceptions import ExperimentNotFoundError
from app.middleware.auth import get_current_user
from app.routers import experiments, health, internal, metrics, personas, profile, results
from app.services.secret_service import validate_secrets_on_startup

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 설정 로드
settings = get_settings()


# ============================================================
# 앱 수명 주기 이벤트 핸들러
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행되는 수명 주기 핸들러"""
    logger.info(f"{settings.app_name} 시작")
    logger.info(f"RDS 엔드포인트: {settings.rds_endpoint}:{settings.rds_port}")

    # 서비스 시작 시 시크릿 검증 (실패 시 RuntimeError → 시작 중단)
    try:
        validate_secrets_on_startup()
    except RuntimeError as e:
        logger.error(f"시크릿 검증 실패로 서비스 시작 중단: {e}")
        raise

    yield
    logger.info(f"{settings.app_name} 종료")


# ============================================================
# FastAPI 앱 인스턴스 생성
# ============================================================
app = FastAPI(
    title=settings.app_name,
    description="AWS 인프라 카오스 엔지니어링 플랫폼 Core Engine API",
    version="0.1.0",
    lifespan=lifespan,
)

# ============================================================
# CORS 미들웨어 설정
# CloudFront 도메인에서의 요청을 허용한다.
# ============================================================
cors_origins = [
    origin.strip()
    for origin in settings.cors_allowed_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 글로벌 예외 핸들러
# ============================================================
@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Pydantic 검증 실패 시 400 응답 반환"""
    return JSONResponse(
        status_code=400,
        content={"error": "validation_failed", "details": exc.errors()},
    )


@app.exception_handler(ExperimentNotFoundError)
async def not_found_handler(request: Request, exc: ExperimentNotFoundError):
    """실험을 찾을 수 없을 때 404 응답 반환"""
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """처리되지 않은 예외에 대한 500 응답 반환"""
    logger.error(f"처리되지 않은 오류: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "예상치 못한 오류가 발생했습니다",
        },
    )


# ============================================================
# 라우터 등록
# ============================================================
# 인증 불필요 라우터
app.include_router(health.router)
app.include_router(internal.router)

# 인증 필요 라우터 — get_current_user 의존성 적용
_auth_deps = [Depends(get_current_user)]
app.include_router(experiments.router, dependencies=_auth_deps)
app.include_router(results.router, dependencies=_auth_deps)
app.include_router(personas.router, dependencies=_auth_deps)
app.include_router(metrics.router, dependencies=_auth_deps)
app.include_router(profile.router, dependencies=_auth_deps)
