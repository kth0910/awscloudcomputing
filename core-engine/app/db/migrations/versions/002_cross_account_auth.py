"""Cross-Account Auth 스키마 변경

user_profiles, ux_metrics 테이블 생성 및 experiments 테이블에 user_id 컬럼 추가.
experiments.status CHECK 제약 조건에 'probe_failed' 값 추가.

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# 리비전 식별자
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    마이그레이션 업그레이드: Cross-Account Auth 스키마 변경

    - user_profiles 테이블: 사용자 프로필 (Cognito sub, AWS 계정 ID, Role ARN 등)
    - ux_metrics 테이블: UX 메트릭 (probe_endpoint 프로빙 결과)
    - experiments 테이블: user_id 컬럼 추가, status CHECK 제약 조건 변경
    """

    # ============================================================
    # 1. user_profiles 테이블: 사용자 프로필 정보
    # ============================================================
    op.create_table(
        "user_profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cognito_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("aws_account_id", sa.String(12), nullable=True),
        sa.Column("cross_account_role_arn", sa.String(2048), nullable=True),
        sa.Column(
            "role_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("probe_endpoint", sa.String(2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # user_profiles 인덱스
    op.create_index("idx_user_profiles_cognito_sub", "user_profiles", ["cognito_sub"])

    # ============================================================
    # 2. ux_metrics 테이블: UX 메트릭 (프로빙 결과)
    # ============================================================
    op.create_table(
        "ux_metrics",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("experiment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("response_latency_ms", sa.Float(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("error_rate", sa.Float(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
            name="fk_ux_metrics_experiment_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "phase IN ('before', 'during', 'after')",
            name="ck_ux_metrics_phase",
        ),
        sa.CheckConstraint(
            "error_rate >= 0.0 AND error_rate <= 1.0",
            name="ck_ux_metrics_error_rate",
        ),
    )

    # ux_metrics 인덱스
    op.create_index("idx_ux_metrics_experiment_id", "ux_metrics", ["experiment_id"])

    # ============================================================
    # 3. experiments 테이블 변경: user_id 컬럼 추가, status CHECK 변경
    # ============================================================

    # user_id 컬럼 추가 (기존 데이터 호환을 위해 DEFAULT '' 설정)
    op.add_column(
        "experiments",
        sa.Column("user_id", sa.String(255), nullable=False, server_default=""),
    )

    # 기존 status CHECK 제약 조건 삭제
    op.drop_constraint("ck_experiments_status", "experiments", type_="check")

    # 새 status CHECK 제약 조건 추가 ('probe_failed' 포함)
    op.create_check_constraint(
        "ck_experiments_status",
        "experiments",
        "status IN ('created', 'running', 'completed', 'failed', 'cancelled', 'probe_failed')",
    )

    # experiments.user_id 인덱스
    op.create_index("idx_experiments_user_id", "experiments", ["user_id"])


def downgrade() -> None:
    """
    마이그레이션 다운그레이드: Cross-Account Auth 스키마 롤백

    experiments 테이블 변경 복원, ux_metrics 및 user_profiles 테이블 삭제.
    """
    # experiments 테이블 변경 복원
    op.drop_index("idx_experiments_user_id", table_name="experiments")
    op.drop_constraint("ck_experiments_status", "experiments", type_="check")
    op.create_check_constraint(
        "ck_experiments_status",
        "experiments",
        "status IN ('created', 'running', 'completed', 'failed', 'cancelled')",
    )
    op.drop_column("experiments", "user_id")

    # ux_metrics 테이블 삭제
    op.drop_index("idx_ux_metrics_experiment_id", table_name="ux_metrics")
    op.drop_table("ux_metrics")

    # user_profiles 테이블 삭제
    op.drop_index("idx_user_profiles_cognito_sub", table_name="user_profiles")
    op.drop_table("user_profiles")
