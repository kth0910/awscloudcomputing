"""
사용자 프로필 라우터

프로필 조회 및 등록/수정 API 엔드포인트를 제공한다.
- GET /api/profile: 현재 사용자 프로필 조회
- PUT /api/profile: 프로필 등록/수정 (AWS 계정 ID, Cross-Account Role ARN, probe_endpoint)
"""

import logging

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.middleware.auth import AuthenticatedUser, get_current_user
from app.models.user_profile import UserProfile
from app.schemas.profile import ProfileResponse, ProfileUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["프로필 관리"])


# ============================================================
# GET /api/profile — 현재 사용자 프로필 조회
# ============================================================
@router.get("", response_model=ProfileResponse)
async def get_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 인증된 사용자의 프로필을 조회한다."""
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.cognito_sub == current_user.cognito_sub
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        # 프로필이 없으면 기본 프로필 반환
        return ProfileResponse(
            cognito_sub=current_user.cognito_sub,
            email=current_user.email,
        )

    return ProfileResponse.model_validate(profile)


# ============================================================
# PUT /api/profile — 프로필 등록/수정
# ============================================================
@router.put("", response_model=ProfileResponse)
async def update_profile(
    data: ProfileUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    프로필을 등록하거나 수정한다.

    Role ARN 형식은 Pydantic 스키마에서 검증한다.
    STS AssumeRole dry-run으로 trust policy 설정을 검증한다.
    """
    # STS AssumeRole dry-run 검증
    settings = get_settings()
    role_verified = False

    try:
        sts_client = boto3.client(
            "sts", region_name=settings.aws_default_region
        )
        sts_client.assume_role(
            RoleArn=data.cross_account_role_arn,
            RoleSessionName="ChaosTwin-dry-run",
            DurationSeconds=900,
        )
        role_verified = True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_failed",
                    "message": "trust policy에 Chaos Injector Lambda Role ARN을 추가해주세요",
                },
            )
        else:
            logger.error(f"STS AssumeRole dry-run 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "internal_error",
                    "message": "Role 검증 중 오류가 발생했습니다",
                },
            )
    except Exception as e:
        logger.error(f"STS AssumeRole dry-run 중 예외 발생: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Role 검증 중 오류가 발생했습니다",
            },
        )

    # 기존 프로필 조회
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.cognito_sub == current_user.cognito_sub
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        # 신규 프로필 생성
        profile = UserProfile(
            cognito_sub=current_user.cognito_sub,
            email=current_user.email,
            aws_account_id=data.aws_account_id,
            cross_account_role_arn=data.cross_account_role_arn,
            role_verified=role_verified,
            probe_endpoint=data.probe_endpoint,
        )
        db.add(profile)
    else:
        # 기존 프로필 수정
        profile.email = current_user.email
        profile.aws_account_id = data.aws_account_id
        profile.cross_account_role_arn = data.cross_account_role_arn
        profile.role_verified = role_verified
        profile.probe_endpoint = data.probe_endpoint

    await db.commit()
    await db.refresh(profile)

    return ProfileResponse.model_validate(profile)
