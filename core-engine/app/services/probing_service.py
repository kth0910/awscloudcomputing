"""
프로빙(사전 연결 테스트) 서비스

실험 실행 전 STS AssumeRole 가능 여부와 probe_endpoint 연결 가능 여부를 확인한다.
프로빙 실패 시 실험 상태를 probe_failed로 설정하고 Lambda 호출을 차단한다.
"""

import logging

import boto3
import httpx
from botocore.exceptions import ClientError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProbingResult(BaseModel):
    """프로빙 결과"""

    success: bool
    error_message: str | None = None


class ProbingService:
    """프로빙(사전 연결 테스트) 서비스"""

    def __init__(self, sts_client=None, http_client: httpx.AsyncClient | None = None):
        self._sts_client = sts_client
        self._http_client = http_client

    @property
    def sts_client(self):
        """boto3 STS 클라이언트를 지연 초기화한다."""
        if self._sts_client is None:
            self._sts_client = boto3.client("sts")
        return self._sts_client

    async def probe_assume_role(self, role_arn: str) -> ProbingResult:
        """
        STS AssumeRole 프로빙.

        DurationSeconds=900으로 AssumeRole을 시도하여
        Cross-Account Role 위임 가능 여부를 확인한다.

        Args:
            role_arn: Cross-Account Role ARN

        Returns:
            ProbingResult: 성공/실패 결과
        """
        try:
            self.sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="chaos-twin-probe",
                DurationSeconds=900,
            )
            logger.info(f"STS AssumeRole 프로빙 성공: {role_arn}")
            return ProbingResult(success=True)
        except (ClientError, Exception) as e:
            error_msg = "프로빙 실패: Cross-Account Role 위임에 실패했습니다. trust policy를 확인하세요"
            logger.warning(f"STS AssumeRole 프로빙 실패: {role_arn}, error={e}")
            return ProbingResult(success=False, error_message=error_msg)

    async def probe_endpoint(self, url: str, timeout: float = 5.0) -> ProbingResult:
        """
        HTTP GET 프로빙.

        probe_endpoint에 HTTP GET 요청을 전송하여 연결 가능 여부를 확인한다.
        5초 타임아웃, 연결 거부, DNS 해석 실패 모두 실패로 처리한다.

        Args:
            url: probe_endpoint URL
            timeout: 타임아웃 (초, 기본 5.0)

        Returns:
            ProbingResult: 성공/실패 결과
        """
        try:
            if self._http_client is not None:
                response = await self._http_client.get(url, timeout=timeout)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=timeout)
            logger.info(f"Endpoint 프로빙 성공: {url}, status={response.status_code}")
            return ProbingResult(success=True)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError, Exception) as e:
            error_msg = "프로빙 실패: probe_endpoint에 연결할 수 없습니다"
            logger.warning(f"Endpoint 프로빙 실패: {url}, error={e}")
            return ProbingResult(success=False, error_message=error_msg)

    async def run_pre_experiment_probes(
        self, role_arn: str, probe_endpoint: str | None
    ) -> ProbingResult:
        """
        실험 실행 전 전체 프로빙.

        1. STS AssumeRole 프로빙 실행
        2. probe_endpoint가 등록된 경우 HTTP GET 프로빙 실행
        3. 하나라도 실패하면 probe_failed 결과 반환

        Args:
            role_arn: Cross-Account Role ARN
            probe_endpoint: probe_endpoint URL (None이면 건너뜀)

        Returns:
            ProbingResult: 통합 프로빙 결과
        """
        # 1. STS AssumeRole 프로빙
        sts_result = await self.probe_assume_role(role_arn)
        if not sts_result.success:
            return sts_result

        # 2. probe_endpoint 프로빙 (등록된 경우에만)
        if probe_endpoint is not None:
            endpoint_result = await self.probe_endpoint(probe_endpoint)
            if not endpoint_result.success:
                return endpoint_result

        # 모든 프로빙 성공
        return ProbingResult(success=True)
