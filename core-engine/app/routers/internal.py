"""
내부 API 라우터

Lambda Chaos Injector로부터의 콜백 수신 엔드포인트를 제공한다.
외부에 노출되지 않는 내부 전용 API이다.
- POST /api/internal/callback: Lambda 콜백 수신 및 결과 저장
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.callback import ChaosCallback
from app.services.chaos_service import ChaosService
from app.services.experiment_service import ExperimentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["내부 API"])


def _get_experiment_service(db: AsyncSession = Depends(get_db)) -> ExperimentService:
    """ExperimentService 의존성 주입 헬퍼"""
    return ExperimentService(db)


def _get_chaos_service(db: AsyncSession = Depends(get_db)) -> ChaosService:
    """ChaosService 의존성 주입 헬퍼"""
    return ChaosService(db)


# ============================================================
# POST /api/internal/callback — Lambda 콜백 수신
# ============================================================
@router.post("/callback")
async def receive_callback(
    callback: ChaosCallback,
    chaos_service: ChaosService = Depends(_get_chaos_service),
):
    """
    Chaos Injector Lambda로부터 콜백을 수신한다.

    ChaosService.handle_callback()을 통해 결과 저장 + AI 추론 트리거를 처리한다.
    """
    logger.info(
        f"콜백 수신: experiment_id={callback.experiment_id}, status={callback.status}"
    )

    await chaos_service.handle_callback(callback)

    return {
        "message": "콜백 처리 완료",
        "experiment_id": callback.experiment_id,
        "status": callback.status,
    }
