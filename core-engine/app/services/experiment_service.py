"""
실험 비즈니스 로직 서비스

실험 생성, 조회, 삭제, 실행 등 핵심 비즈니스 로직을 담당한다.
라우터에서 DB 세션을 주입받아 사용한다.
"""

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ExperimentNotFoundError
from app.models.experiment import Experiment
from app.models.experiment_result import ExperimentResult
from app.models.resource_metric import ResourceMetric
from app.schemas.experiment import ExperimentCreate

logger = logging.getLogger(__name__)


class ExperimentService:
    """실험 CRUD 및 실행 비즈니스 로직"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 실험 목록 조회
    # ============================================================
    async def list_experiments(self) -> list[Experiment]:
        """모든 실험을 생성일 역순으로 조회한다."""
        stmt = select(Experiment).order_by(Experiment.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ============================================================
    # 실험 생성
    # ============================================================
    async def create_experiment(self, data: ExperimentCreate) -> Experiment:
        """
        새 실험을 생성한다.

        persona_types 리스트를 JSON 문자열로 변환하여 저장한다.
        """
        experiment = Experiment(
            name=data.name,
            target_resource=data.target_resource,
            fault_type=data.fault_type,
            duration_seconds=data.duration_seconds,
            persona_types_json=json.dumps(data.persona_types),
        )
        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)
        logger.info(f"실험 생성 완료: {experiment.id} ({experiment.name})")
        return experiment

    # ============================================================
    # 실험 단건 조회 (기본)
    # ============================================================
    async def get_experiment(self, experiment_id: str) -> Experiment:
        """
        실험 ID로 단건 조회한다.

        존재하지 않으면 ExperimentNotFoundError를 발생시킨다.
        """
        try:
            exp_uuid = uuid.UUID(experiment_id)
        except ValueError:
            raise ExperimentNotFoundError(experiment_id)

        stmt = select(Experiment).where(Experiment.id == exp_uuid)
        result = await self.db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if experiment is None:
            raise ExperimentNotFoundError(experiment_id)

        return experiment

    # ============================================================
    # 실험 상세 조회 (results, persona_inferences 포함)
    # ============================================================
    async def get_experiment_detail(self, experiment_id: str) -> Experiment:
        """
        실험 상세 정보를 조회한다.

        results, persona_inferences 관계를 eagerly 로드한다.
        """
        try:
            exp_uuid = uuid.UUID(experiment_id)
        except ValueError:
            raise ExperimentNotFoundError(experiment_id)

        stmt = (
            select(Experiment)
            .where(Experiment.id == exp_uuid)
            .options(
                selectinload(Experiment.results),
                selectinload(Experiment.persona_inferences),
            )
        )
        result = await self.db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if experiment is None:
            raise ExperimentNotFoundError(experiment_id)

        return experiment

    # ============================================================
    # 실험 삭제
    # ============================================================
    async def delete_experiment(self, experiment_id: str) -> None:
        """
        실험을 삭제한다.

        CASCADE 설정으로 관련 results, persona_inferences, resource_metrics도 함께 삭제된다.
        """
        experiment = await self.get_experiment(experiment_id)
        await self.db.delete(experiment)
        await self.db.commit()
        logger.info(f"실험 삭제 완료: {experiment_id}")

    # ============================================================
    # 실험 실행 (상태를 running으로 변경)
    # ============================================================
    async def run_experiment(self, experiment_id: str) -> Experiment:
        """
        실험을 실행 상태로 변경한다.

        상태를 'running'으로 업데이트하고 started_at을 기록한다.
        Lambda 호출은 placeholder로 남겨둔다 (태스크 8에서 구현).
        """
        experiment = await self.get_experiment(experiment_id)
        experiment.status = "running"
        experiment.started_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(experiment)
        logger.info(f"실험 실행 시작: {experiment_id}")

        # Lambda 비동기 호출 (ChaosService 연동)
        # chaos_lambda_function_name이 설정된 경우에만 호출
        from app.config import get_settings
        settings = get_settings()
        if settings.chaos_lambda_function_name:
            try:
                from app.services.chaos_service import ChaosService

                chaos_service = ChaosService(self.db)
                invocation_id = await chaos_service.invoke_chaos_injector(
                    experiment_id=str(experiment.id),
                    target_resource=experiment.target_resource,
                    fault_type=experiment.fault_type,
                    duration_seconds=experiment.duration_seconds,
                )
                logger.info(
                    f"Lambda 호출 완료: experiment_id={experiment_id}, "
                    f"invocation_id={invocation_id}"
                )
            except Exception as e:
                logger.error(f"Lambda 호출 실패: {e}")
                experiment.status = "failed"
                experiment.ended_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(experiment)
        else:
            logger.info("Lambda 함수 이름 미설정 — Lambda 호출 건너뜀 (로컬/테스트 환경)")

        return experiment

    # ============================================================
    # 실험 결과 조회
    # ============================================================
    async def get_experiment_results(self, experiment_id: str) -> list[ExperimentResult]:
        """실험의 장애 주입 결과 목록을 조회한다."""
        # 실험 존재 여부 확인
        await self.get_experiment(experiment_id)

        exp_uuid = uuid.UUID(experiment_id)
        stmt = (
            select(ExperimentResult)
            .where(ExperimentResult.experiment_id == exp_uuid)
            .order_by(ExperimentResult.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ============================================================
    # 실험 메트릭 조회
    # ============================================================
    async def get_experiment_metrics(self, experiment_id: str) -> list[ResourceMetric]:
        """실험의 리소스 메트릭 목록을 조회한다."""
        # 실험 존재 여부 확인
        await self.get_experiment(experiment_id)

        exp_uuid = uuid.UUID(experiment_id)
        stmt = (
            select(ResourceMetric)
            .where(ResourceMetric.experiment_id == exp_uuid)
            .order_by(ResourceMetric.collected_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ============================================================
    # 콜백 결과 저장
    # ============================================================
    async def save_callback_result(
        self,
        experiment_id: str,
        status: str,
        started_at: datetime,
        ended_at: datetime,
        target_resource: str,
        fault_type: str,
        error_detail: str | None = None,
        original_state: dict | None = None,
    ) -> ExperimentResult:
        """
        Lambda 콜백 데이터를 experiment_results 테이블에 저장한다.

        콜백 수신 후 AI 추론 트리거는 placeholder로 남겨둔다 (태스크 9에서 구현).
        """
        exp_uuid = uuid.UUID(experiment_id)

        # timezone-aware datetime을 naive로 변환 (PostgreSQL TIMESTAMP 호환)
        if started_at and started_at.tzinfo is not None:
            started_at = started_at.replace(tzinfo=None)
        if ended_at and ended_at.tzinfo is not None:
            ended_at = ended_at.replace(tzinfo=None)

        experiment_result = ExperimentResult(
            experiment_id=exp_uuid,
            status=status,
            chaos_started_at=started_at,
            chaos_ended_at=ended_at,
            fault_type=fault_type,
            target_resource=target_resource,
            error_detail=error_detail,
            original_state=original_state,
        )
        self.db.add(experiment_result)

        # 실험 상태 업데이트: 콜백 상태에 따라 completed 또는 failed
        stmt = select(Experiment).where(Experiment.id == exp_uuid)
        result = await self.db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if experiment:
            if status == "success":
                # AI 추론이 완료된 후 chaos_service에서 "completed"로 업데이트하므로
                # 여기서는 "running" 상태를 유지한다.
                pass
            elif status == "failed":
                experiment.status = "failed"
                experiment.ended_at = ended_at
            # rollback_completed는 상태를 변경하지 않음 (이미 completed/failed)

        await self.db.commit()
        await self.db.refresh(experiment_result)
        logger.info(f"콜백 결과 저장 완료: experiment_id={experiment_id}, status={status}")

        return experiment_result
