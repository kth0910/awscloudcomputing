"""
데이터베이스 연결 관리 모듈

SQLAlchemy 2.0 비동기 엔진, 세션 팩토리, 연결 풀을 구성한다.
FastAPI 의존성 주입을 위한 get_db 함수를 제공한다.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_database_url, get_settings

# 설정에서 데이터베이스 URL 구성
_settings = get_settings()
_database_url = get_database_url(_settings)

# ============================================================
# 비동기 엔진 생성
# 연결 풀 설정: pool_size=5, max_overflow=10, pool_recycle=3600
# ============================================================
engine = create_async_engine(
    _database_url,
    echo=_settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# ============================================================
# 비동기 세션 팩토리
# expire_on_commit=False: 커밋 후에도 객체 속성 접근 가능
# ============================================================
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ============================================================
# ORM 모델 베이스 클래스
# ============================================================
class Base(DeclarativeBase):
    """모든 ORM 모델이 상속하는 선언적 베이스 클래스"""

    pass


# ============================================================
# FastAPI 의존성 주입용 세션 제공 함수
# ============================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    비동기 데이터베이스 세션을 생성하고 반환한다.

    FastAPI의 Depends()를 통해 라우터에서 사용한다.
    요청 처리 완료 후 세션을 자동으로 닫는다.

    Yields:
        AsyncSession: SQLAlchemy 비동기 세션
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
