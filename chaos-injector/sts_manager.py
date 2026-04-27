"""
STS AssumeRole 기반 임시 자격 증명 관리

Cross-Account 장애 주입을 위해 STS AssumeRole로 임시 자격 증명을 발급받고,
해당 자격 증명으로 boto3 클라이언트를 생성한다.
"""

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError, ConnectTimeoutError, EndpointConnectionError

logger = logging.getLogger(__name__)

# 재시도 가능한 에러 (타임아웃/네트워크 에러)
_RETRYABLE_EXCEPTIONS = (ConnectTimeoutError, EndpointConnectionError, ConnectionError)

MAX_RETRIES = 2


class STSCredentialManager:
    """STS AssumeRole 기반 임시 자격 증명 관리"""

    def __init__(self, sts_client=None):
        self._sts = sts_client or boto3.client("sts")

    def assume_role(
        self, role_arn: str, session_name: str, duration_seconds: int
    ) -> dict:
        """
        STS AssumeRole을 호출하여 임시 자격 증명을 발급받는다.

        타임아웃/네트워크 에러 시 최대 2회 재시도한다.
        AccessDenied 에러 시 즉시 실패하며 콜백용 설명 메시지를 포함한 예외를 발생시킨다.

        Parameters:
            role_arn: 위임할 IAM Role ARN
            session_name: RoleSessionName (experiment_id를 포함해야 함)
            duration_seconds: 장애 지속 시간 (실제 DurationSeconds는 +300초)

        Returns:
            임시 자격 증명 딕셔너리:
                - AccessKeyId
                - SecretAccessKey
                - SessionToken
                - Expiration

        Raises:
            RuntimeError: AccessDenied 에러 시 (설명 메시지 포함)
            RuntimeError: 재시도 초과 시
        """
        actual_duration = max(900, duration_seconds + 300)

        last_error = None
        for attempt in range(1 + MAX_RETRIES):
            try:
                response = self._sts.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName=session_name,
                    DurationSeconds=actual_duration,
                )
                credentials = response["Credentials"]
                logger.info(
                    "AssumeRole 성공: role_arn=%s, session=%s, attempt=%d",
                    role_arn,
                    session_name,
                    attempt + 1,
                )
                return {
                    "AccessKeyId": credentials["AccessKeyId"],
                    "SecretAccessKey": credentials["SecretAccessKey"],
                    "SessionToken": credentials["SessionToken"],
                    "Expiration": credentials["Expiration"],
                }
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "AccessDenied":
                    msg = (
                        "Cross-Account Role 위임 실패: trust policy에 "
                        "Chaos Injector Lambda Role ARN이 포함되어 있는지 확인하세요"
                    )
                    logger.error(
                        "AssumeRole AccessDenied: role_arn=%s, session=%s",
                        role_arn,
                        session_name,
                    )
                    raise RuntimeError(msg) from e
                # 그 외 ClientError는 재시도 대상이 아님
                raise
            except _RETRYABLE_EXCEPTIONS as e:
                last_error = e
                logger.warning(
                    "AssumeRole 재시도 가능 에러 (attempt %d/%d): %s",
                    attempt + 1,
                    1 + MAX_RETRIES,
                    str(e),
                )
                continue

        msg = (
            f"AssumeRole 호출 실패: {1 + MAX_RETRIES}회 시도 후에도 "
            f"연결할 수 없습니다 (role_arn={role_arn})"
        )
        logger.error(msg)
        raise RuntimeError(msg) from last_error

    def create_client(
        self, service_name: str, credentials: dict, region: str = "us-east-1"
    ) -> Any:
        """
        임시 자격 증명으로 boto3 클라이언트를 생성한다.

        Parameters:
            service_name: AWS 서비스 이름 (예: "ec2", "rds")
            credentials: assume_role()에서 반환된 자격 증명 딕셔너리
            region: AWS 리전

        Returns:
            boto3 서비스 클라이언트
        """
        return boto3.client(
            service_name,
            region_name=region,
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
