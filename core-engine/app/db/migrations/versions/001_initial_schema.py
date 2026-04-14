"""초기 스키마 생성

4개 테이블(experiments, experiment_results, persona_inferences, resource_metrics)과
인덱스, CHECK 제약 조건, 외래 키 제약 조건을 생성한다.
설계 문서의 DDL을 기반으로 수동 작성되었다.

Revision ID: 001
Revises: None
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# 리비전 식별자
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    마이그레이션 업그레이드: 초기 스키마 생성

    - experiments 테이블: Chaos 실험 정보
    - experiment_results 테이블: 장애 주입 결과
    - persona_inferences 테이블: AI 페르소나 추론 결과
    - resource_metrics 테이블: 리소스 메트릭
    - 각 테이블에 CHECK 제약 조건, 인덱스, 외래 키 적용
    """

    # ============================================================
    # 1. experiments 테이블: Chaos 실험 정보
    # ============================================================
    op.create_table(
        "experiments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_resource", sa.String(255), nullable=False),
        sa.Column(
            "fault_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="created",
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column(
            "persona_types_json",
            sa.Text(),
            nullable=False,
            server_default='["impatient","meticulous","casual"]',
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "fault_type IN ('ec2_stop', 'sg_port_block', 'rds_delay')",
            name="ck_experiments_fault_type",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_experiments_status",
        ),
    )

    # experiments 인덱스
    op.create_index("idx_experiments_status", "experiments", ["status"])
    op.create_index("idx_experiments_created_at", "experiments", [sa.text("created_at DESC")])

    # ============================================================
    # 2. experiment_results 테이블: 장애 주입 결과
    # ============================================================
    op.create_table(
        "experiment_results",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("experiment_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("chaos_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chaos_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fault_type", sa.String(50), nullable=False),
        sa.Column("target_resource", sa.String(255), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("original_state", JSONB(), nullable=True),
        sa.Column("rollback_state", JSONB(), nullable=True),
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
            name="fk_experiment_results_experiment_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'rollback_completed')",
            name="ck_experiment_results_status",
        ),
    )

    # experiment_results 인덱스
    op.create_index("idx_experiment_results_experiment_id", "experiment_results", ["experiment_id"])

    # ============================================================
    # 3. persona_inferences 테이블: AI 페르소나 추론 결과
    # ============================================================
    op.create_table(
        "persona_inferences",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("experiment_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "persona_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("emotion", sa.String(100), nullable=True),
        sa.Column("churn_probability", sa.Float(), nullable=True),
        sa.Column("frustration_index", sa.Integer(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("api_latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
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
            name="fk_persona_inferences_experiment_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "persona_type IN ('impatient', 'meticulous', 'casual')",
            name="ck_persona_inferences_persona_type",
        ),
        sa.CheckConstraint(
            "churn_probability >= 0.0 AND churn_probability <= 1.0",
            name="ck_persona_inferences_churn_probability",
        ),
        sa.CheckConstraint(
            "frustration_index >= 1 AND frustration_index <= 10",
            name="ck_persona_inferences_frustration_index",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'inference_failed')",
            name="ck_persona_inferences_status",
        ),
    )

    # persona_inferences 인덱스
    op.create_index("idx_persona_inferences_experiment_id", "persona_inferences", ["experiment_id"])
    op.create_index("idx_persona_inferences_persona_type", "persona_inferences", ["persona_type"])

    # ============================================================
    # 4. resource_metrics 테이블: 리소스 메트릭
    # ============================================================
    op.create_table(
        "resource_metrics",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("experiment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column(
            "phase",
            sa.String(20),
            nullable=False,
        ),
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
            name="fk_resource_metrics_experiment_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "phase IN ('before', 'during', 'after')",
            name="ck_resource_metrics_phase",
        ),
    )

    # resource_metrics 인덱스
    op.create_index("idx_resource_metrics_experiment_id", "resource_metrics", ["experiment_id"])
    op.create_index("idx_resource_metrics_collected_at", "resource_metrics", ["collected_at"])


def downgrade() -> None:
    """
    마이그레이션 다운그레이드: 초기 스키마 롤백

    생성된 4개 테이블과 인덱스를 역순으로 삭제한다.
    외래 키 의존성 순서를 고려하여 자식 테이블부터 삭제한다.
    """
    # 인덱스 삭제 (테이블 삭제 시 자동 삭제되지만 명시적으로 기술)
    op.drop_index("idx_resource_metrics_collected_at", table_name="resource_metrics")
    op.drop_index("idx_resource_metrics_experiment_id", table_name="resource_metrics")
    op.drop_table("resource_metrics")

    op.drop_index("idx_persona_inferences_persona_type", table_name="persona_inferences")
    op.drop_index("idx_persona_inferences_experiment_id", table_name="persona_inferences")
    op.drop_table("persona_inferences")

    op.drop_index("idx_experiment_results_experiment_id", table_name="experiment_results")
    op.drop_table("experiment_results")

    op.drop_index("idx_experiments_created_at", table_name="experiments")
    op.drop_index("idx_experiments_status", table_name="experiments")
    op.drop_table("experiments")
