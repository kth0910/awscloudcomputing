"""
Chaos Service — Lambda 비동기 호출 및 콜백 처리

Chaos Injector Lambda를 비동기로 호출하고,
콜백 수신 시 결과 저장 + AI 추론 트리거를 담당한다.
"""

import json
import logging
import uuid

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import ChaosServiceError
from app.schemas.callback import ChaosCallback
from app.services.experiment_service import ExperimentService

logger = logging.getLogger(__name__)


class ChaosService:
    """Lambda 비동기 호출 및 콜백 처리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._settings = get_settings()
        self._lambda_client = None

    @property
    def lambda_client(self):
        """boto3 Lambda 클라이언트를 지연 초기화한다."""
        if self._lambda_client is None:
            self._lambda_client = boto3.client(
                "lambda",
                region_name=self._settings.aws_default_region,
            )
        return self._lambda_client

    # ============================================================
    # Lambda 비동기 호출
    # ============================================================
    async def invoke_chaos_injector(
        self,
        experiment_id: str,
        target_resource: str,
        fault_type: str,
        duration_seconds: int = 300,
    ) -> str:
        """
        Chaos Injector Lambda를 비동기(Event)로 호출한다.

        Args:
            experiment_id: 실험 ID (UUID 문자열)
            target_resource: 대상 AWS 리소스 ID
            fault_type: 장애 유형 (ec2_stop, sg_port_block, rds_delay)
            duration_seconds: 장애 지속 시간 (초)

        Returns:
            invocation_id: 호출 추적용 고유 ID

        Raises:
            ChaosServiceError: Lambda 호출 실패 시
        """
        function_name = self._settings.chaos_lambda_function_name
        if not function_name:
            raise ChaosServiceError(
                "CHAOS_LAMBDA_FUNCTION_NAME 환경 변수가 설정되지 않았습니다."
            )

        # 콜백 URL 구성
        callback_base = self._settings.callback_base_url
        callback_url = f"{callback_base}/api/internal/callback"

        # 호출 추적용 고유 ID 생성
        invocation_id = str(uuid.uuid4())

        # Lambda 페이로드 구성
        payload = {
            "experiment_id": experiment_id,
            "target_resource": target_resource,
            "fault_type": fault_type,
            "duration_seconds": duration_seconds,
            "callback_url": callback_url,
            "invocation_id": invocation_id,
        }

        try:
            # Lambda 비동기 호출 (InvocationType=Event → 202 반환)
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="Event",
                Payload=json.dumps(payload).encode("utf-8"),
            )

            status_code = response.get("StatusCode", 0)
            if status_code != 202:
                raise ChaosServiceError(
                    f"Lambda 비동기 호출 실패: StatusCode={status_code}"
                )

            logger.info(
                f"Lambda 비동기 호출 성공: experiment_id={experiment_id}, "
                f"invocation_id={invocation_id}, function={function_name}"
            )
            return invocation_id

        except ClientError as e:
            error_msg = f"Lambda 호출 중 AWS 오류 발생: {e}"
            logger.error(error_msg)
            raise ChaosServiceError(error_msg) from e

    # ============================================================
    # 콜백 처리 (결과 저장 + AI 추론 트리거)
    # ============================================================
    async def handle_callback(self, callback: ChaosCallback) -> None:
        """
        Lambda 콜백을 처리한다.

        1. 콜백 데이터를 experiment_results 테이블에 저장
        2. AI 추론 트리거 (태스크 9에서 구현)

        Args:
            callback: Lambda 콜백 스키마
        """
        experiment_service = ExperimentService(self.db)

        # 1. 콜백 결과 저장
        result = await experiment_service.save_callback_result(
            experiment_id=callback.experiment_id,
            status=callback.status,
            started_at=callback.started_at,
            ended_at=callback.ended_at,
            target_resource=callback.target_resource,
            fault_type=callback.fault_type,
            error_detail=callback.error_detail,
            original_state=callback.original_state,
        )

        logger.info(
            f"콜백 결과 저장 완료: result_id={result.id}, "
            f"experiment_id={callback.experiment_id}, status={callback.status}"
        )

        # 2. AI 추론 트리거 (성공 콜백인 경우에만)
        if callback.status == "success":
            try:
                await self._trigger_ai_reasoning(callback)
            except Exception as e:
                logger.error(
                    f"AI 추론 트리거 실패: experiment_id={callback.experiment_id}, "
                    f"error={e}"
                )

    # ============================================================
    # AI 추론 트리거
    # ============================================================
    async def _trigger_ai_reasoning(self, callback: ChaosCallback) -> None:
        """
        AI 추론을 트리거한다.

        실험의 페르소나 목록을 조회하여 각 페르소나에 대해
        Gemini API 추론을 순차 실행하고 결과를 저장한다.
        모든 추론 완료 후 실험 상태를 "completed"로 업데이트한다.

        Args:
            callback: Lambda 콜백 스키마
        """
        import json as _json
        from datetime import datetime

        from sqlalchemy import select

        from app.models.experiment import Experiment
        from app.services.ai_reasoning_service import AIReasoningService

        experiment_id = callback.experiment_id

        # 실험 조회하여 페르소나 목록 가져오기
        exp_uuid = uuid.UUID(experiment_id)
        stmt = select(Experiment).where(Experiment.id == exp_uuid)
        result = await self.db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if not experiment:
            logger.error(f"AI 추론 트리거 실패: 실험을 찾을 수 없음 ({experiment_id})")
            return

        # 페르소나 유형 목록 파싱
        persona_types = _json.loads(experiment.persona_types_json)

        # 장애 컨텍스트 구성
        fault_context = {
            "service_name": callback.target_resource,
            "fault_type": callback.fault_type,
            "fault_duration": experiment.duration_seconds,
            "impact_scope": f"{callback.target_resource} ({callback.fault_type})",
        }

        # AI 추론 서비스로 다중 페르소나 순차 실행 및 독립 저장
        ai_service = AIReasoningService(self.db)
        inferences = await ai_service.run_all_personas(
            experiment_id=experiment_id,
            persona_types=persona_types,
            fault_context=fault_context,
        )

        # 실험 상태를 "completed"로 업데이트
        experiment.status = "completed"
        experiment.ended_at = datetime.utcnow()
        await self.db.commit()

        logger.info(
            f"AI 추론 완료: experiment_id={experiment_id}, "
            f"persona_count={len(inferences)}, "
            f"completed={sum(1 for i in inferences if i.status == 'completed')}, "
            f"failed={sum(1 for i in inferences if i.status == 'inference_failed')}"
        )
