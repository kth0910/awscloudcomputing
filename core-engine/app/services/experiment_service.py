"""
실험 비즈니스 로직 서비스

실험 생성, 조회, 삭제, 실행 등 핵심 비즈니스 로직을 담당한다.
라우터에서 DB 세션을 주입받아 사용한다.
"""

import json
import logging
import re
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import ExperimentNotFoundError
from app.models.experiment import Experiment
from app.models.experiment_result import ExperimentResult
from app.models.resource_metric import ResourceMetric
from app.models.user_profile import UserProfile
from app.schemas.experiment import ExperimentCreate

logger = logging.getLogger(__name__)

# AWS 계정 ID 추출 정규식 (ARN 또는 12자리 숫자 포함 리소스 ID)
_AWS_ACCOUNT_RE = re.compile(r"arn:aws:[^:]*:[^:]*:(\d{12}):")


class ExperimentService:
    """실험 CRUD 및 실행 비즈니스 로직"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # 실험 목록 조회
    # ============================================================
    async def list_experiments(self, user_id: str | None = None) -> list[Experiment]:
        """사용자의 실험을 생성일 역순으로 조회한다."""
        stmt = select(Experiment).order_by(Experiment.created_at.desc())
        if user_id is not None:
            stmt = stmt.where(Experiment.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ============================================================
    # 실험 생성
    # ============================================================
    async def create_experiment(
        self, data: ExperimentCreate, user_id: str | None = None
    ) -> Experiment:
        """
        새 실험을 생성한다.

        persona_types 리스트를 JSON 문자열로 변환하여 저장한다.
        user_id가 제공되면 target_resource의 계정 ID와 사용자 등록 계정 ID를 비교한다.
        """
        # 계정 ID 검증 (user_id가 제공된 경우)
        if user_id is not None:
            await self._validate_account_id(data.target_resource, user_id)

        experiment = Experiment(
            name=data.name,
            target_resource=data.target_resource,
            fault_type=data.fault_type,
            duration_seconds=data.duration_seconds,
            persona_types_json=json.dumps(data.persona_types),
            user_id=user_id or "",
        )
        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)
        logger.info(f"실험 생성 완료: {experiment.id} ({experiment.name})")
        return experiment

    # ============================================================
    # 계정 ID 검증
    # ============================================================
    async def _validate_account_id(self, target_resource: str, user_id: str) -> None:
        """
        target_resource에서 AWS 계정 ID를 추출하고,
        사용자의 등록된 aws_account_id와 비교한다.
        불일치 시 403을 반환한다.
        """
        match = _AWS_ACCOUNT_RE.search(target_resource)
        if not match:
            # ARN 형식이 아니면 계정 ID 검증을 건너뜀
            return

        resource_account_id = match.group(1)

        # 사용자 프로필에서 등록된 계정 ID 조회
        stmt = select(UserProfile).where(UserProfile.cognito_sub == user_id)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile is None or profile.aws_account_id is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "message": "등록되지 않은 AWS 계정입니다",
                },
            )

        if resource_account_id != profile.aws_account_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "message": "등록되지 않은 AWS 계정입니다",
                },
            )

    # ============================================================
    # 실험 단건 조회 (기본)
    # ============================================================
    async def get_experiment(
        self, experiment_id: str, user_id: str | None = None
    ) -> Experiment:
        """
        실험 ID로 단건 조회한다.

        user_id가 제공되면 소유권을 검증한다.
        존재하지 않거나 소유권 불일치 시 ExperimentNotFoundError를 발생시킨다.
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

        # 소유권 검증
        if user_id is not None and experiment.user_id != user_id:
            raise ExperimentNotFoundError(experiment_id)

        return experiment

    # ============================================================
    # 실험 상세 조회 (results, persona_inferences 포함)
    # ============================================================
    async def get_experiment_detail(
        self, experiment_id: str, user_id: str | None = None
    ) -> Experiment:
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

        # 소유권 검증
        if user_id is not None and experiment.user_id != user_id:
            raise ExperimentNotFoundError(experiment_id)

        return experiment

    # ============================================================
    # 실험 삭제
    # ============================================================
    async def delete_experiment(
        self, experiment_id: str, user_id: str | None = None
    ) -> None:
        """
        실험을 삭제한다.

        CASCADE 설정으로 관련 results, persona_inferences, resource_metrics도 함께 삭제된다.
        """
        experiment = await self.get_experiment(experiment_id, user_id=user_id)
        await self.db.delete(experiment)
        await self.db.commit()
        logger.info(f"실험 삭제 완료: {experiment_id}")

    # ============================================================
    # 실험 실행 (상태를 running으로 변경)
    # ============================================================
    async def run_experiment(
        self, experiment_id: str, user_id: str | None = None
    ) -> Experiment:
        """
        실험을 실행 상태로 변경한다.

        1. 사용자 프로필 조회 → cross_account_role_arn, probe_endpoint 확인
        2. ProbingService로 사전 연결 테스트 수행
        3. probe_endpoint가 등록된 경우 before 단계 UX 메트릭 수집
        4. Lambda 비동기 호출 (cross_account_role_arn 전달)
        5. probe_endpoint가 등록된 경우 during/after 단계 UX 메트릭 수집
        """
        experiment = await self.get_experiment(experiment_id, user_id=user_id)

        # 사용자 프로필 조회
        profile = None
        if user_id:
            stmt = select(UserProfile).where(UserProfile.cognito_sub == user_id)
            result = await self.db.execute(stmt)
            profile = result.scalar_one_or_none()

        cross_account_role_arn = ""
        probe_endpoint = None
        if profile:
            cross_account_role_arn = profile.cross_account_role_arn or ""
            probe_endpoint = profile.probe_endpoint

        # 프로빙 (cross_account_role_arn이 있는 경우)
        if cross_account_role_arn:
            from app.services.probing_service import ProbingService

            probing_service = ProbingService()
            probe_result = await probing_service.run_pre_experiment_probes(
                role_arn=cross_account_role_arn,
                probe_endpoint=probe_endpoint,
            )
            if not probe_result.success:
                experiment.status = "probe_failed"
                await self.db.commit()
                await self.db.refresh(experiment)
                logger.warning(
                    f"프로빙 실패: experiment_id={experiment_id}, "
                    f"error={probe_result.error_message}"
                )
                return experiment

        # 상태를 running으로 변경
        experiment.status = "running"
        experiment.started_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(experiment)
        logger.info(f"실험 실행 시작: {experiment_id}")

        # CloudWatch 리소스 메트릭 수집: before 단계
        try:
            from app.services.metrics_service import MetricsService

            metrics_service = MetricsService(self.db)
            await metrics_service.collect_before_metrics(
                experiment_id=str(experiment.id),
                resource_id=experiment.target_resource,
            )
        except Exception as e:
            await self.db.rollback()
            await self.db.refresh(experiment)
            logger.error(f"리소스 메트릭 수집 실패 (before): {e}")

        # UX 메트릭 수집: before 단계
        if probe_endpoint:
            try:
                from app.services.ux_metrics_service import UXMetricsService

                ux_service = UXMetricsService(self.db)
                await ux_service.collect_phase_metrics(
                    probe_endpoint=probe_endpoint,
                    phase="before",
                    experiment_id=str(experiment.id),
                )
            except Exception as e:
                await self.db.rollback()
                logger.error(f"UX 메트릭 수집 실패 (before): {e}")

        # Lambda 비동기 호출 (ChaosService 연동)
        from app.config import get_settings

        settings = get_settings()
        lambda_invoked = False
        if settings.chaos_lambda_function_name:
            try:
                from app.services.chaos_service import ChaosService

                chaos_service = ChaosService(self.db)
                invocation_id = await chaos_service.invoke_chaos_injector(
                    experiment_id=str(experiment.id),
                    target_resource=experiment.target_resource,
                    fault_type=experiment.fault_type,
                    duration_seconds=experiment.duration_seconds,
                    cross_account_role_arn=cross_account_role_arn,
                )
                lambda_invoked = True
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

        # UX 메트릭 수집: during 단계 (Lambda 호출 직후)
        if probe_endpoint and lambda_invoked:
            try:
                from app.services.ux_metrics_service import UXMetricsService

                ux_service = UXMetricsService(self.db)
                await ux_service.collect_phase_metrics(
                    probe_endpoint=probe_endpoint,
                    phase="during",
                    experiment_id=str(experiment.id),
                )
            except Exception as e:
                await self.db.rollback()
                logger.error(f"UX 메트릭 수집 실패 (during): {e}")

        # UX 메트릭 수집: after 단계 (during 수집 직후)
        if probe_endpoint and lambda_invoked:
            try:
                from app.services.ux_metrics_service import UXMetricsService

                ux_service = UXMetricsService(self.db)
                await ux_service.collect_phase_metrics(
                    probe_endpoint=probe_endpoint,
                    phase="after",
                    experiment_id=str(experiment.id),
                )
            except Exception as e:
                await self.db.rollback()
                logger.error(f"UX 메트릭 수집 실패 (after): {e}")

        return experiment

    # ============================================================
    # 콜백 단계별 리소스 메트릭 수집
    # ============================================================
    async def collect_callback_metrics(
        self,
        experiment_id: str,
        status: str,
        target_resource: str,
        chaos_started_at: datetime | None,
        chaos_ended_at: datetime | None,
    ) -> None:
        """
        Lambda 콜백 상태에 맞춰 CloudWatch 리소스 메트릭을 수집한다.

        - success: 장애가 실제로 발생한 구간을 during으로 저장
        - rollback_completed: 롤백 이후 구간을 after로 저장
        """
        if status not in {"success", "rollback_completed"}:
            return

        try:
            from app.services.metrics_service import MetricsService

            metrics_service = MetricsService(self.db)
            if status == "success":
                await metrics_service.collect_during_metrics(
                    experiment_id=experiment_id,
                    resource_id=target_resource,
                    chaos_started_at=chaos_started_at or datetime.utcnow(),
                )
            elif status == "rollback_completed":
                await metrics_service.collect_after_metrics(
                    experiment_id=experiment_id,
                    resource_id=target_resource,
                    chaos_ended_at=chaos_ended_at or datetime.utcnow(),
                )
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"리소스 메트릭 수집 실패 ({status}): "
                f"experiment_id={experiment_id}, error={e}"
            )

    # ============================================================
    # 실험 결과 조회
    # ============================================================
    async def get_experiment_results(
        self, experiment_id: str, user_id: str | None = None
    ) -> list[ExperimentResult]:
        """실험의 장애 주입 결과 목록을 조회한다."""
        # 실험 존재 여부 및 소유권 확인
        await self.get_experiment(experiment_id, user_id=user_id)

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
    async def get_experiment_metrics(
        self, experiment_id: str, user_id: str | None = None
    ) -> list[ResourceMetric]:
        """실험의 리소스 메트릭 목록을 조회한다."""
        # 실험 존재 여부 및 소유권 확인
        await self.get_experiment(experiment_id, user_id=user_id)

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
