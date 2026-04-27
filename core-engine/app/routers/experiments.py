"""
실험 관리 라우터

실험 CRUD 및 실행 API 엔드포인트를 제공한다.
- GET /api/experiments: 실험 목록 조회
- POST /api/experiments: 실험 생성
- GET /api/experiments/{id}: 실험 상세 조회
- DELETE /api/experiments/{id}: 실험 삭제
- POST /api/experiments/{id}/run: 실험 실행 (202 Accepted)
"""

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.middleware.auth import AuthenticatedUser, get_current_user
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentDetail,
    ExperimentResponse,
    RunConfig,
)
from app.services.experiment_service import ExperimentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiments", tags=["실험 관리"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ExperimentService:
    """ExperimentService 의존성 주입 헬퍼"""
    return ExperimentService(db)


# ============================================================
# GET /api/experiments — 실험 목록 조회
# ============================================================
@router.get("", response_model=list[ExperimentResponse])
async def list_experiments(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExperimentService = Depends(_get_service),
):
    """실험 목록을 생성일 역순으로 조회한다. 현재 사용자의 실험만 반환한다."""
    experiments = await service.list_experiments(user_id=current_user.cognito_sub)
    return experiments


# ============================================================
# POST /api/experiments — 실험 생성
# ============================================================
@router.post(
    "",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    data: ExperimentCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExperimentService = Depends(_get_service),
):
    """새 실험을 생성한다. persona_types는 JSON 문자열로 변환하여 저장한다."""
    experiment = await service.create_experiment(
        data, user_id=current_user.cognito_sub
    )
    return experiment


# ============================================================
# GET /api/experiments/{experiment_id} — 실험 상세 조회
# ============================================================
@router.get("/{experiment_id}", response_model=ExperimentDetail)
async def get_experiment(
    experiment_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExperimentService = Depends(_get_service),
):
    """실험 상세 정보를 조회한다. results, persona_inferences를 포함한다."""
    experiment = await service.get_experiment_detail(
        experiment_id, user_id=current_user.cognito_sub
    )
    return experiment


# ============================================================
# DELETE /api/experiments/{experiment_id} — 실험 삭제
# ============================================================
@router.delete(
    "/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_experiment(
    experiment_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExperimentService = Depends(_get_service),
):
    """실험을 삭제한다. CASCADE로 관련 데이터도 함께 삭제된다."""
    await service.delete_experiment(
        experiment_id, user_id=current_user.cognito_sub
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# POST /api/experiments/{experiment_id}/run — 실험 실행
# ============================================================
@router.post(
    "/{experiment_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_experiment(
    experiment_id: str,
    config: RunConfig | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExperimentService = Depends(_get_service),
):
    """
    실험을 실행한다.

    프로빙 → Lambda 비동기 호출 → UX 메트릭 수집 흐름을 수행한다.
    """
    experiment = await service.run_experiment(
        experiment_id, user_id=current_user.cognito_sub
    )
    return {
        "message": "실험이 시작되었습니다",
        "experiment_id": str(experiment.id),
        "status": experiment.status,
    }
