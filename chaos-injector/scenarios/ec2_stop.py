"""
EC2 Stop 장애 시나리오

EC2 인스턴스를 중지(Stop)하여 장애를 시뮬레이션하고,
롤백 시 원래 상태(running)로 복원한다.
"""

import logging
import time

import boto3
from botocore.exceptions import ClientError

from scenarios.base import BaseChaosScenario

logger = logging.getLogger(__name__)

# EC2 상태 변경 대기 최대 시간 (초)
WAIT_TIMEOUT = 120
POLL_INTERVAL = 5


class EC2StopScenario(BaseChaosScenario):
    """EC2 인스턴스 Stop/Start 장애 시나리오"""

    def __init__(self, ec2_client=None):
        """
        Parameters:
            ec2_client: boto3 EC2 클라이언트 (테스트 시 주입 가능)
        """
        self._ec2 = ec2_client or boto3.client("ec2")

    def inject(self, target_resource: str, config: dict) -> dict:
        """
        EC2 인스턴스를 Stop한다. 원래 상태(running)를 기록하여 반환한다.

        Parameters:
            target_resource: EC2 인스턴스 ID (예: i-0abc123def456)
            config: 추가 설정 (현재 미사용)

        Returns:
            원래 상태 딕셔너리 {"instance_id": ..., "original_state": "running"}
        """
        instance_id = target_resource
        logger.info("EC2 인스턴스 상태 조회: %s", instance_id)

        # 현재 인스턴스 상태 조회
        try:
            response = self._ec2.describe_instances(InstanceIds=[instance_id])
            reservations = response.get("Reservations", [])
            if not reservations or not reservations[0].get("Instances"):
                raise ValueError(f"EC2 인스턴스를 찾을 수 없음: {instance_id}")

            instance = reservations[0]["Instances"][0]
            current_state = instance["State"]["Name"]
            logger.info("EC2 인스턴스 현재 상태: %s = %s", instance_id, current_state)
        except ClientError as e:
            raise RuntimeError(f"EC2 인스턴스 상태 조회 실패: {e}") from e

        # 원래 상태 기록
        original_state = {
            "instance_id": instance_id,
            "original_state": current_state,
        }

        # 인스턴스 중지
        if current_state == "running":
            logger.info("EC2 인스턴스 중지 시작: %s", instance_id)
            try:
                self._ec2.stop_instances(InstanceIds=[instance_id])
                self._wait_for_state(instance_id, "stopped")
                logger.info("EC2 인스턴스 중지 완료: %s", instance_id)
            except ClientError as e:
                raise RuntimeError(f"EC2 인스턴스 중지 실패: {e}") from e
        else:
            logger.warning(
                "EC2 인스턴스가 running 상태가 아님: %s (현재: %s). 중지 건너뜀.",
                instance_id,
                current_state,
            )

        return original_state

    def rollback(self, target_resource: str, original_state: dict) -> None:
        """
        EC2 인스턴스를 원래 상태로 복원한다 (Start).

        Parameters:
            target_resource: EC2 인스턴스 ID
            original_state: inject()에서 반환된 원래 상태
        """
        instance_id = original_state.get("instance_id", target_resource)
        prev_state = original_state.get("original_state", "running")

        # 원래 상태가 running이었으면 다시 시작
        if prev_state == "running":
            logger.info("EC2 인스턴스 시작 (롤백): %s", instance_id)
            try:
                self._ec2.start_instances(InstanceIds=[instance_id])
                self._wait_for_state(instance_id, "running")
                logger.info("EC2 인스턴스 시작 완료 (롤백): %s", instance_id)
            except ClientError as e:
                raise RuntimeError(f"EC2 인스턴스 시작 실패 (롤백): {e}") from e
        else:
            logger.info(
                "원래 상태가 running이 아님 (%s). 롤백 건너뜀.", prev_state
            )

    def _wait_for_state(self, instance_id: str, desired_state: str) -> None:
        """
        EC2 인스턴스가 원하는 상태에 도달할 때까지 대기한다.

        Parameters:
            instance_id: EC2 인스턴스 ID
            desired_state: 대기할 상태 (예: "stopped", "running")
        """
        elapsed = 0
        while elapsed < WAIT_TIMEOUT:
            try:
                response = self._ec2.describe_instances(InstanceIds=[instance_id])
                current_state = (
                    response["Reservations"][0]["Instances"][0]["State"]["Name"]
                )
                if current_state == desired_state:
                    return
                logger.info(
                    "EC2 상태 대기 중: %s (현재: %s, 목표: %s)",
                    instance_id,
                    current_state,
                    desired_state,
                )
            except ClientError:
                pass
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        logger.warning(
            "EC2 상태 대기 타임아웃: %s (목표: %s, %d초 경과)",
            instance_id,
            desired_state,
            WAIT_TIMEOUT,
        )
