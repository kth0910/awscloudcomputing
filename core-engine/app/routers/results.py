"""
실험 결과 조회 라우터

실험의 장애 주입 결과를 조회하는 API를 제공한다.
- GET /api/experiments/{id}/results: 실험 결과 목록 조회
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.middleware.auth import AuthenticatedUser, get_current_user
from app.schemas.experiment import ExperimentResultResponse
from app.services.experiment_service import ExperimentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiments", tags=["실험 결과"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ExperimentService:
    """ExperimentService 의존성 주입 헬퍼"""
    return ExperimentService(db)


# ============================================================
# GET /api/experiments/{experiment_id}/results — 실험 결과 조회
# ============================================================
@router.get(
    "/{experiment_id}/results",
    response_model=list[ExperimentResultResponse],
)
async def get_experiment_results(
    experiment_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExperimentService = Depends(_get_service),
):
    """실험의 장애 주입 결과 목록을 조회한다."""
    results = await service.get_experiment_results(
        experiment_id, user_id=current_user.cognito_sub
    )
    return results
