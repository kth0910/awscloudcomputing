"""
자동 롤백 매니저

장애 주입 후 duration_seconds 대기 → 자동 롤백 → Core Engine 콜백 전송을 관리한다.
"""

import logging
import time
from datetime import datetime, timezone

from callback import build_error_callback_payload, send_callback
from scenarios.base import BaseChaosScenario

logger = logging.getLogger(__name__)


class RollbackManager:
    """
    자동 롤백 매니저

    장애 주입 → 대기 → 롤백 → 콜백 전송의 전체 라이프사이클을 관리한다.
    duration_seconds 초과 시 자동으로 롤백을 트리거한다.
    """

    def __init__(
        self,
        scenario: BaseChaosScenario,
        experiment_id: str,
        target_resource: str,
        fault_type: str,
        duration_seconds: int = 300,
        callback_url: str = "",
        config: dict | None = None,
    ):
        """
        Parameters:
            scenario: 장애 시나리오 인스턴스
            experiment_id: 실험 UUID
            target_resource: 대상 AWS 리소스 ID
            fault_type: 장애 유형
            duration_seconds: 장애 지속 시간 (초)
            callback_url: Core Engine 콜백 URL
            config: 시나리오 추가 설정
        """
        self._scenario = scenario
        self._experiment_id = experiment_id
        self._target_resource = target_resource
        self._fault_type = fault_type
        self._duration_seconds = duration_seconds
        self._callback_url = callback_url
        self._config = config or {}

    def execute(self) -> dict:
        """
        장애 주입 → 대기 → 롤백 → 콜백 전송 전체 흐름을 실행한다.

        Returns:
            실행 결과 딕셔너리
        """
        started_at = datetime.now(timezone.utc)
        original_state = None

        try:
            # 1단계: 장애 주입
            logger.info(
                "장애 주입 시작: experiment=%s, type=%s, target=%s",
                self._experiment_id,
                self._fault_type,
                self._target_resource,
            )
            original_state = self._scenario.inject(
                self._target_resource, self._config
            )
            logger.info("장애 주입 완료. 원래 상태: %s", original_state)

            # 성공 콜백 전송
            inject_ended_at = datetime.now(timezone.utc)
            send_callback(
                callback_url=self._callback_url,
                experiment_id=self._experiment_id,
                status="success",
                started_at=started_at,
                ended_at=inject_ended_at,
                target_resource=self._target_resource,
                fault_type=self._fault_type,
                original_state=original_state,
            )

            # 2단계: duration_seconds 동안 대기
            logger.info(
                "장애 지속 대기: %d초 (experiment=%s)",
                self._duration_seconds,
                self._experiment_id,
            )
            time.sleep(self._duration_seconds)

            # 3단계: 자동 롤백
            logger.info(
                "자동 롤백 시작: experiment=%s, target=%s",
                self._experiment_id,
                self._target_resource,
            )
            self._scenario.rollback(self._target_resource, original_state)
            rollback_ended_at = datetime.now(timezone.utc)
            logger.info("자동 롤백 완료: experiment=%s", self._experiment_id)

            # 롤백 완료 콜백 전송
            send_callback(
                callback_url=self._callback_url,
                experiment_id=self._experiment_id,
                status="rollback_completed",
                started_at=started_at,
                ended_at=rollback_ended_at,
                target_resource=self._target_resource,
                fault_type=self._fault_type,
                original_state=original_state,
            )

            return {
                "experiment_id": self._experiment_id,
                "status": "rollback_completed",
                "fault_type": self._fault_type,
                "target_resource": self._target_resource,
                "duration_seconds": self._duration_seconds,
                "started_at": started_at.isoformat(),
                "ended_at": rollback_ended_at.isoformat(),
            }

        except Exception as e:
            logger.error(
                "실행 중 예외 발생: experiment=%s, error=%s",
                self._experiment_id,
                str(e),
                exc_info=True,
            )

            # 예외 발생 시 롤백 시도
            if original_state:
                try:
                    logger.info("예외 후 긴급 롤백 시도: experiment=%s", self._experiment_id)
                    self._scenario.rollback(self._target_resource, original_state)
                    logger.info("긴급 롤백 완료: experiment=%s", self._experiment_id)
                except Exception as rollback_error:
                    logger.error(
                        "긴급 롤백 실패: experiment=%s, error=%s",
                        self._experiment_id,
                        str(rollback_error),
                    )

            # 실패 콜백 전송 (Property 2: status="failed" + error_detail)
            error_payload = build_error_callback_payload(
                experiment_id=self._experiment_id,
                target_resource=self._target_resource,
                fault_type=self._fault_type,
                error=e,
                started_at=started_at,
            )
            send_callback(callback_url=self._callback_url, **error_payload)

            # 예외를 다시 발생시켜 handler에서 처리
            raise
