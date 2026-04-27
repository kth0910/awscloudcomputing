"""
사용자 프로필(Profile) 관련 Pydantic 요청/응답 스키마

ProfileUpdate: 프로필 등록/수정 요청 (AWS 계정 ID, Cross-Account Role ARN, probe_endpoint)
ProfileResponse: 프로필 조회 응답
"""

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 요청 스키마
# ============================================================


class ProfileUpdate(BaseModel):
    """
    프로필 등록/수정 요청 스키마

    aws_account_id: 12자리 AWS 계정 ID
    cross_account_role_arn: ChaosTwin- 접두사를 가진 IAM Role ARN
    probe_endpoint: 선택적 HTTP/HTTPS 프로빙 URL
    """

    # AWS 계정 ID (12자리 숫자)
    aws_account_id: str = Field(
        ...,
        pattern=r"^\d{12}$",
        description="AWS 계정 ID (12자리)",
    )

    # Cross-Account IAM Role ARN (ChaosTwin- 접두사 필수)
    cross_account_role_arn: str = Field(
        ...,
        pattern=r"^arn:aws:iam::\d{12}:role/ChaosTwin-.+$",
        description="Cross-Account IAM Role ARN",
    )

    # 프로빙 대상 엔드포인트 URL (선택)
    probe_endpoint: str | None = Field(
        default=None,
        pattern=r"^https?://.+",
        description="프로빙 대상 HTTP/HTTPS URL",
    )


# ============================================================
# 응답 스키마
# ============================================================


class ProfileResponse(BaseModel):
    """
    프로필 조회 응답 스키마

    user_profiles 테이블의 ORM 모델에서 직접 변환 가능하다.
    """

    model_config = ConfigDict(from_attributes=True)

    # Cognito 사용자 고유 ID
    cognito_sub: str

    # 사용자 이메일
    email: str

    # AWS 계정 ID (12자리)
    aws_account_id: str | None = None

    # Cross-Account IAM Role ARN
    cross_account_role_arn: str | None = None

    # Role 검증 완료 여부
    role_verified: bool = False

    # 프로빙 대상 엔드포인트 URL
    probe_endpoint: str | None = None
