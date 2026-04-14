"""
설정 관리 모듈

환경 변수 기반 설정 관리 및 AWS Secrets Manager 연동을 담당한다.
pydantic-settings의 BaseSettings를 사용하여 환경 변수를 자동으로 로드한다.
"""

import json
import logging
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    애플리케이션 설정

    환경 변수에서 자동으로 값을 로드한다.
    EC2 User Data에서 .env 파일로 주입되는 값들을 포함한다.
    """

    # 애플리케이션 기본 설정
    app_name: str = "Chaos Twin Core Engine"
    debug: bool = False

    # RDS 연결 정보
    rds_endpoint: str = "localhost"
    rds_port: str = "5432"
    rds_db_name: str = "chaostwin"
    rds_secret_arn: str = ""

    # Gemini API Key Secrets Manager ARN
    gemini_api_key_secret_arn: str = ""

    # Chaos Injector Lambda 함수 이름
    chaos_lambda_function_name: str = ""

    # 콜백 베이스 URL (ALB 내부 DNS)
    callback_base_url: str = "http://localhost:8000"

    # AWS 리전
    aws_default_region: str = "us-east-1"

    # CORS 허용 오리진 (CloudFront 도메인)
    cors_allowed_origins: str = "*"

    # Secrets Manager 시크릿 이름 (런타임 조회용)
    secret_name: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_secret(secret_arn: str, region: str = "us-east-1") -> dict:
    """
    AWS Secrets Manager에서 시크릿 값을 조회한다.

    Args:
        secret_arn: 시크릿 ARN 또는 이름
        region: AWS 리전

    Returns:
        시크릿 값 딕셔너리

    Raises:
        RuntimeError: 시크릿 조회 실패 시
    """
    if not secret_arn:
        raise RuntimeError("시크릿 ARN이 설정되지 않았습니다.")

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_arn)
        secret_string = response.get("SecretString", "{}")
        return json.loads(secret_string)
    except ClientError as e:
        logger.error(f"Secrets Manager 조회 실패: {e}")
        raise RuntimeError(f"시크릿 조회 실패: {secret_arn}") from e
    except json.JSONDecodeError as e:
        logger.error(f"시크릿 JSON 파싱 실패: {e}")
        raise RuntimeError(f"시크릿 JSON 파싱 실패: {secret_arn}") from e


def get_database_url(settings: Settings) -> str:
    """
    RDS 연결 URL을 생성한다.

    Secrets Manager에서 RDS 자격 증명을 조회하여 비동기 PostgreSQL 연결 URL을 구성한다.
    시크릿 ARN이 비어있으면 기본 로컬 개발용 URL을 반환한다.

    Args:
        settings: 애플리케이션 설정

    Returns:
        SQLAlchemy 비동기 데이터베이스 URL
    """
    if settings.rds_secret_arn:
        try:
            secret = get_secret(settings.rds_secret_arn, settings.aws_default_region)
            username = secret.get("username", "postgres")
            password = secret.get("password", "")
            return (
                f"postgresql+asyncpg://{username}:{password}"
                f"@{settings.rds_endpoint}:{settings.rds_port}"
                f"/{settings.rds_db_name}"
            )
        except RuntimeError:
            logger.warning("RDS 시크릿 조회 실패, 기본 URL 사용")

    # 로컬 개발 환경용 기본 URL
    return (
        f"postgresql+asyncpg://postgres:postgres"
        f"@{settings.rds_endpoint}:{settings.rds_port}"
        f"/{settings.rds_db_name}"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    설정 싱글톤 인스턴스를 반환한다.

    lru_cache를 사용하여 애플리케이션 수명 동안 단일 인스턴스를 유지한다.
    """
    return Settings()
