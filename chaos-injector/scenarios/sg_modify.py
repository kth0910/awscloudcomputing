"""
Security Group 수정 장애 시나리오

Security Group에서 특정 포트의 인바운드 규칙을 제거하여 장애를 시뮬레이션하고,
롤백 시 원래 규칙을 복원한다.
"""

import logging

import boto3
from botocore.exceptions import ClientError

from scenarios.base import BaseChaosScenario

logger = logging.getLogger(__name__)


class SGModifyScenario(BaseChaosScenario):
    """Security Group 포트 차단 장애 시나리오"""

    def __init__(self, ec2_client=None):
        """
        Parameters:
            ec2_client: boto3 EC2 클라이언트 (테스트 시 주입 가능)
        """
        self._ec2 = ec2_client or boto3.client("ec2")

    def inject(self, target_resource: str, config: dict) -> dict:
        """
        Security Group에서 특정 포트의 인바운드 규칙을 제거한다.

        Parameters:
            target_resource: Security Group ID (예: sg-0abc123def456)
            config: 추가 설정
                - port: 차단할 포트 번호 (기본: 443)
                - protocol: 프로토콜 (기본: "tcp")

        Returns:
            원래 상태 딕셔너리 (제거된 인바운드 규칙 목록 포함)
        """
        sg_id = target_resource
        port = config.get("port", 443)
        protocol = config.get("protocol", "tcp")

        logger.info("Security Group 규칙 조회: %s (포트: %d)", sg_id, port)

        # 현재 Security Group 규칙 조회
        try:
            response = self._ec2.describe_security_groups(GroupIds=[sg_id])
            security_groups = response.get("SecurityGroups", [])
            if not security_groups:
                raise ValueError(f"Security Group을 찾을 수 없음: {sg_id}")

            sg = security_groups[0]
            ingress_rules = sg.get("IpPermissions", [])
        except ClientError as e:
            raise RuntimeError(f"Security Group 조회 실패: {e}") from e

        # 해당 포트에 매칭되는 인바운드 규칙 필터링
        matching_rules = []
        for rule in ingress_rules:
            from_port = rule.get("FromPort", -1)
            to_port = rule.get("ToPort", -1)
            rule_protocol = rule.get("IpProtocol", "")

            if from_port <= port <= to_port and rule_protocol == protocol:
                matching_rules.append(rule)

        # 원래 상태 기록
        original_state = {
            "security_group_id": sg_id,
            "removed_rules": matching_rules,
            "port": port,
            "protocol": protocol,
        }

        # 매칭되는 규칙 제거
        if matching_rules:
            logger.info(
                "Security Group 인바운드 규칙 제거: %s (포트: %d, 규칙 수: %d)",
                sg_id,
                port,
                len(matching_rules),
            )
            try:
                self._ec2.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=matching_rules,
                )
                logger.info("Security Group 규칙 제거 완료: %s", sg_id)
            except ClientError as e:
                raise RuntimeError(f"Security Group 규칙 제거 실패: {e}") from e
        else:
            logger.warning(
                "포트 %d에 매칭되는 인바운드 규칙 없음: %s", port, sg_id
            )

        return original_state

    def rollback(self, target_resource: str, original_state: dict) -> None:
        """
        제거된 Security Group 인바운드 규칙을 복원한다.

        Parameters:
            target_resource: Security Group ID
            original_state: inject()에서 반환된 원래 상태
        """
        sg_id = original_state.get("security_group_id", target_resource)
        removed_rules = original_state.get("removed_rules", [])

        if not removed_rules:
            logger.info("복원할 규칙 없음: %s", sg_id)
            return

        logger.info(
            "Security Group 규칙 복원 (롤백): %s (규칙 수: %d)",
            sg_id,
            len(removed_rules),
        )
        try:
            self._ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=removed_rules,
            )
            logger.info("Security Group 규칙 복원 완료 (롤백): %s", sg_id)
        except ClientError as e:
            raise RuntimeError(
                f"Security Group 규칙 복원 실패 (롤백): {e}"
            ) from e
