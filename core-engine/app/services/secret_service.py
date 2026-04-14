"""
Secret Service — AWS Secrets Manager 연동

Gemini API Key를 Secrets Manager에서 조회하고 캐싱한다.
조회 실패 시 RuntimeError를 발생시켜 서비스 시작을 중단한다.
"""

import json
import logging

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)

# 시크릿 이름 기본값
_DEFAULT_SECRET_NAME = "chaos-twin/gemini-api-key"


class SecretService:
    """Secrets Manager 조회 서비스 (싱글톤 캐싱)"""

    def __init__(self):
        self._settings = get_settings()
        self._cached_api_key: str | None = None
        self._client = None

    @property
    def _secrets_client(self):
        """boto3 Secrets Manager 클라이언트를 지연 초기화한다."""
        if self._client is None:
            self._client = boto3.client(
                "secretsmanager",
                region_name=self._settings.aws_default_region,
            )
        return self._client

    def _get_secret_id(self) -> str:
        """시크릿 ARN 또는 기본 시크릿 이름을 반환한다."""
        if self._settings.gemini_api_key_secret_arn:
            return self._settings.gemini_api_key_secret_arn
        return _DEFAULT_SECRET_NAME

    def get_gemini_api_key(self) -> str:
        """
        Gemini API Key를 Secrets Manager에서 조회한다.

        캐싱된 값이 있으면 재사용하고, 없으면 Secrets Manager에서 조회한다.
        조회 실패 시 RuntimeError를 발생시킨다.

        Returns:
            Gemini API Key 문자열

        Raises:
            RuntimeError: 시크릿 조회 또는 파싱 실패 시
        """
        # 캐싱된 값이 있으면 반환
        if self._cached_api_key is not None:
            return self._cached_api_key

        secret_id = self._get_secret_id()
        logger.info(f"Secrets Manager에서 Gemini API Key 조회 중: {secret_id}")

        try:
            response = self._secrets_client.get_secret_value(SecretId=secret_id)
            secret_string = response.get("SecretString")

            if not secret_string:
                raise RuntimeError(
                    f"시크릿 값이 비어있습니다: {secret_id}"
                )

            # JSON 파싱: {"api_key": "실제_키_값"}
            secret_data = json.loads(secret_string)
            api_key = secret_data.get("api_key")

            if not api_key:
                raise RuntimeError(
                    f"시크릿에 'api_key' 필드가 없습니다: {secret_id}"
                )

            # 캐싱
            self._cached_api_key = api_key
            logger.info("Gemini API Key 조회 및 캐싱 완료")
            return api_key

        except ClientError as e:
            error_msg = f"Secrets Manager 조회 실패: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        except json.JSONDecodeError as e:
            error_msg = f"시크릿 JSON 파싱 실패: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def clear_cache(self) -> None:
        """캐싱된 API Key를 초기화한다. (테스트 또는 키 갱신 시 사용)"""
        self._cached_api_key = None
        logger.info("Gemini API Key 캐시 초기화 완료")


# ============================================================
# 모듈 레벨 싱글톤 인스턴스
# ============================================================
_secret_service_instance: SecretService | None = None


def get_secret_service() -> SecretService:
    """SecretService 싱글톤 인스턴스를 반환한다."""
    global _secret_service_instance
    if _secret_service_instance is None:
        _secret_service_instance = SecretService()
    return _secret_service_instance


def validate_secrets_on_startup() -> None:
    """
    서비스 시작 시 시크릿 조회를 검증한다.

    Gemini API Key 조회에 실패하면 RuntimeError를 발생시켜
    서비스 시작을 중단한다.

    Raises:
        RuntimeError: 시크릿 조회 실패 시
    """
    settings = get_settings()

    # 시크릿 ARN이 설정되지 않은 경우 (로컬 개발 환경) 건너뛰기
    if not settings.gemini_api_key_secret_arn:
        logger.warning(
            "GEMINI_API_KEY_SECRET_ARN이 설정되지 않았습니다. "
            "시크릿 검증을 건너뜁니다. (로컬 개발 환경)"
        )
        return

    service = get_secret_service()
    service.get_gemini_api_key()
    logger.info("서비스 시작 시 시크릿 검증 완료")
