"""
Alembic 환경 설정 모듈

비동기 SQLAlchemy 엔진을 사용하여 마이그레이션을 실행한다.
app.db.database의 Base.metadata를 target_metadata로 설정하고,
app.models의 모든 모델을 import하여 메타데이터에 등록한다.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_database_url, get_settings

# ORM 모델을 import하여 Base.metadata에 등록
# 이 import가 없으면 Alembic이 테이블 정보를 인식하지 못한다.
from app.models import Experiment, ExperimentResult, PersonaInference, ResourceMetric  # noqa: F401
from app.db.database import Base

# Alembic Config 객체 (alembic.ini 값에 접근)
config = context.config

# 로깅 설정 (alembic.ini의 [loggers] 섹션 사용)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 마이그레이션 대상 메타데이터 (모든 ORM 모델의 테이블 정보 포함)
target_metadata = Base.metadata


def get_url() -> str:
    """
    데이터베이스 URL을 반환한다.

    config.py의 get_database_url()을 사용하여 동적으로 URL을 구성한다.
    비동기 드라이버(asyncpg)를 사용하는 URL을 반환한다.
    """
    settings = get_settings()
    return get_database_url(settings)


def run_migrations_offline() -> None:
    """
    오프라인 모드에서 마이그레이션을 실행한다.

    DB 연결 없이 SQL 스크립트만 생성하는 모드이다.
    'alembic upgrade head --sql' 명령으로 사용한다.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    동기 연결을 사용하여 마이그레이션을 실행한다.

    async 엔진에서 run_sync()를 통해 호출된다.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    비동기 엔진을 사용하여 마이그레이션을 실행한다.

    asyncpg 드라이버를 사용하는 비동기 엔진을 생성하고,
    run_sync()를 통해 동기 마이그레이션 함수를 실행한다.
    """
    # alembic.ini의 sqlalchemy. 접두사 설정을 가져와서 URL을 오버라이드
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    온라인 모드에서 마이그레이션을 실행한다.

    비동기 엔진을 사용하여 실제 DB에 마이그레이션을 적용한다.
    asyncio.run()을 통해 비동기 마이그레이션을 실행한다.
    """
    asyncio.run(run_async_migrations())


# 실행 모드에 따라 적절한 함수를 호출
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
