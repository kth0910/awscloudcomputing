"""
Experiment ORM 모델

experiments 테이블에 대응하는 SQLAlchemy 2.0 스타일 ORM 모델이다.
Chaos 실험의 기본 정보(이름, 대상 리소스, 장애 유형, 상태 등)를 저장한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Experiment(Base):
    """
    Chaos 실험 정보 테이블

    실험 생성, 실행, 완료까지의 수명 주기를 관리한다.
    experiment_results, persona_inferences, resource_metrics와 1:N 관계를 가진다.
    """

    __tablename__ = "experiments"

    # 기본 키: UUID (PostgreSQL에서 gen_random_uuid() 사용)
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )

    # 실험 이름
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 대상 AWS 리소스 ID (예: i-0abc123def456)
    target_resource: Mapped[str] = mapped_column(String(255), nullable=False)

    # 장애 유형: ec2_stop, sg_port_block, rds_delay
    fault_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # 실험 상태: created, running, completed, failed, cancelled
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="created", server_default="created"
    )

    # 장애 지속 시간 (초, 기본 300초 = 5분)
    duration_seconds: Mapped[int] = mapped_column(
        nullable=False, default=300, server_default="300"
    )

    # 페르소나 유형 목록 (JSON 텍스트)
    persona_types_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default='["impatient","meticulous","casual"]',
        server_default='["impatient","meticulous","casual"]',
    )

    # 생성 시각
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    # 실험 시작 시각 (실행 전에는 NULL)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # 실험 종료 시각 (완료 전에는 NULL)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # 실험 소유자 (Cognito sub)
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default=""
    )

    # ============================================================
    # 관계 정의 (1:N)
    # ============================================================
    results = relationship(
        "ExperimentResult", back_populates="experiment", cascade="all, delete-orphan"
    )
    persona_inferences = relationship(
        "PersonaInference", back_populates="experiment", cascade="all, delete-orphan"
    )
    resource_metrics = relationship(
        "ResourceMetric", back_populates="experiment", cascade="all, delete-orphan"
    )
    ux_metrics = relationship(
        "UXMetric", back_populates="experiment", cascade="all, delete-orphan"
    )

    # ============================================================
    # 인덱스 정의
    # ============================================================
    __table_args__ = (
        Index("idx_experiments_status", "status"),
        Index("idx_experiments_created_at", created_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<Experiment(id={self.id}, name='{self.name}', status='{self.status}')>"
