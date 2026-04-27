"""
메트릭 조회 라우터

실험별 리소스 메트릭(CPU 사용률, 네트워크 트래픽 등)을 조회하는 API를 제공한다.
- GET /api/experiments/{id}/metrics: 실험 메트릭 목록 조회
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.middleware.auth import AuthenticatedUser, get_current_user
from app.schemas.experiment import ResourceMetricResponse
from app.services.experiment_service import ExperimentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiments", tags=["메트릭"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ExperimentService:
    """ExperimentService 의존성 주입 헬퍼"""
    return ExperimentService(db)


# ============================================================
# GET /api/experiments/{experiment_id}/metrics — 실험 메트릭 조회
# ============================================================
@router.get(
    "/{experiment_id}/metrics",
    response_model=list[ResourceMetricResponse],
)
async def get_experiment_metrics(
    experiment_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExperimentService = Depends(_get_service),
):
    """실험의 리소스 메트릭 목록을 수집 시각 순으로 조회한다."""
    metrics = await service.get_experiment_metrics(
        experiment_id, user_id=current_user.cognito_sub
    )
    return metrics
