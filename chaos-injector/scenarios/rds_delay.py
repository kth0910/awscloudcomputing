"""
RDS 연결 지연 시뮬레이션 장애 시나리오

RDS 인스턴스에 연결된 Security Group에서 5432 포트를 차단하여
연결 지연/실패를 시뮬레이션하고, 롤백 시 원래 상태를 복원한다.
"""

import logging

import boto3
from botocore.exceptions import ClientError

from scenarios.base import BaseChaosScenario

logger = logging.getLogger(__name__)


class RDSDelayScenario(BaseChaosScenario):
    """RDS 연결 지연 시뮬레이션 장애 시나리오"""

    def __init__(self, ec2_client=None, rds_client=None):
        """
        Parameters:
            ec2_client: boto3 EC2 클라이언트 (테스트 시 주입 가능)
            rds_client: boto3 RDS 클라이언트 (테스트 시 주입 가능)
        """
        self._ec2 = ec2_client or boto3.client("ec2")
        self._rds = rds_client or boto3.client("rds")

    def inject(self, target_resource: str, config: dict) -> dict:
        """
        RDS Security Group에서 5432 포트를 차단하여 연결 지연을 시뮬레이션한다.

        Parameters:
            target_resource: RDS 인스턴스 식별자 또는 Security Group ID
                - RDS 인스턴스 ID인 경우: 연결된 SG를 자동 조회
                - Security Group ID인 경우: 직접 사용
            config: 추가 설정
                - port: 차단할 포트 (기본: 5432)

        Returns:
            원래 상태 딕셔너리 (차단된 SG 규칙 포함)
        """
        port = config.get("port", 5432)

        # target_resource가 SG ID인지 RDS 인스턴스 ID인지 판별
        if target_resource.startswith("sg-"):
            sg_id = target_resource
            logger.info("Security Group ID 직접 사용: %s", sg_id)
        else:
            # RDS 인스턴스에서 Security Group 조회
            sg_id = self._get_rds_security_group(target_resource)
            logger.info(
                "RDS 인스턴스 %s의 Security Group: %s",
                target_resource,
                sg_id,
            )

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

        # 5432 포트에 매칭되는 인바운드 규칙 필터링
        matching_rules = []
        for rule in ingress_rules:
            from_port = rule.get("FromPort", -1)
            to_port = rule.get("ToPort", -1)

            if from_port <= port <= to_port:
                matching_rules.append(rule)

        # 원래 상태 기록
        original_state = {
            "security_group_id": sg_id,
            "rds_instance_id": target_resource,
            "removed_rules": matching_rules,
            "port": port,
        }

        # 매칭되는 규칙 제거 (포트 차단)
        if matching_rules:
            logger.info(
                "RDS Security Group 포트 차단: %s (포트: %d, 규칙 수: %d)",
                sg_id,
                port,
                len(matching_rules),
            )
            try:
                self._ec2.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=matching_rules,
                )
                logger.info("RDS 포트 차단 완료: %s", sg_id)
            except ClientError as e:
                raise RuntimeError(f"RDS 포트 차단 실패: {e}") from e
        else:
            logger.warning(
                "포트 %d에 매칭되는 인바운드 규칙 없음: %s", port, sg_id
            )

        return original_state

    def rollback(self, target_resource: str, original_state: dict) -> None:
        """
        차단된 RDS Security Group 규칙을 복원한다.

        Parameters:
            target_resource: RDS 인스턴스 식별자 또는 Security Group ID
            original_state: inject()에서 반환된 원래 상태
        """
        sg_id = original_state.get("security_group_id", "")
        removed_rules = original_state.get("removed_rules", [])

        if not sg_id:
            logger.warning("복원할 Security Group ID가 없음")
            return

        if not removed_rules:
            logger.info("복원할 규칙 없음: %s", sg_id)
            return

        logger.info(
            "RDS Security Group 규칙 복원 (롤백): %s (규칙 수: %d)",
            sg_id,
            len(removed_rules),
        )
        try:
            self._ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=removed_rules,
            )
            logger.info("RDS Security Group 규칙 복원 완료 (롤백): %s", sg_id)
        except ClientError as e:
            raise RuntimeError(
                f"RDS Security Group 규칙 복원 실패 (롤백): {e}"
            ) from e

    def _get_rds_security_group(self, rds_instance_id: str) -> str:
        """
        RDS 인스턴스에 연결된 VPC Security Group ID를 조회한다.

        Parameters:
            rds_instance_id: RDS 인스턴스 식별자

        Returns:
            첫 번째 VPC Security Group ID
        """
        try:
            response = self._rds.describe_db_instances(
                DBInstanceIdentifier=rds_instance_id
            )
            instances = response.get("DBInstances", [])
            if not instances:
                raise ValueError(
                    f"RDS 인스턴스를 찾을 수 없음: {rds_instance_id}"
                )

            vpc_sgs = instances[0].get("VpcSecurityGroups", [])
            if not vpc_sgs:
                raise ValueError(
                    f"RDS 인스턴스에 VPC Security Group이 없음: {rds_instance_id}"
                )

            return vpc_sgs[0]["VpcSecurityGroupId"]
        except ClientError as e:
            raise RuntimeError(
                f"RDS 인스턴스 조회 실패: {e}"
            ) from e
