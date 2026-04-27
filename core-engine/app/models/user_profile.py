"""
UserProfile ORM 모델

user_profiles 테이블에 대응하는 SQLAlchemy 2.0 스타일 ORM 모델이다.
Cognito 인증 사용자의 프로필 정보(AWS 계정 ID, Cross-Account Role ARN, probe_endpoint 등)를 저장한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserProfile(Base):
    """
    사용자 프로필 정보 테이블

    Cognito 인증 사용자의 AWS 계정 정보, Cross-Account Role ARN,
    probe_endpoint 등을 관리한다.
    """

    __tablename__ = "user_profiles"

    # 기본 키: UUID (PostgreSQL에서 gen_random_uuid() 사용)
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )

    # Cognito 사용자 고유 ID (unique)
    cognito_sub: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )

    # 사용자 이메일
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    # AWS 계정 ID (12자리, 선택)
    aws_account_id: Mapped[str | None] = mapped_column(
        String(12), nullable=True
    )

    # Cross-Account IAM Role ARN (선택)
    cross_account_role_arn: Mapped[str | None] = mapped_column(
        String(2048), nullable=True
    )

    # Role 검증 완료 여부 (기본 False)
    role_verified: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )

    # 프로빙 대상 엔드포인트 URL (선택)
    probe_endpoint: Mapped[str | None] = mapped_column(
        String(2048), nullable=True
    )

    # 생성 시각
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    # 수정 시각 (업데이트 시 자동 갱신)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default="now()",
    )

    # ============================================================
    # 인덱스 정의
    # ============================================================
    __table_args__ = (
        Index("idx_user_profiles_cognito_sub", "cognito_sub"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserProfile(id={self.id}, cognito_sub='{self.cognito_sub}', "
            f"email='{self.email}', role_verified={self.role_verified})>"
        )
