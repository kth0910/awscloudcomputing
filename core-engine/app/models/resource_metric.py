"""
ResourceMetric ORM 모델

resource_metrics 테이블에 대응하는 SQLAlchemy 2.0 스타일 ORM 모델이다.
장애 주입 전/중/후의 CloudWatch 리소스 메트릭을 저장한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ResourceMetric(Base):
    """
    리소스 메트릭 테이블

    장애 주입 전(before), 중(during), 후(after) 단계별로
    CloudWatch에서 수집한 메트릭(CPU 사용률, 네트워크 트래픽 등)을 저장한다.
    experiments 테이블과 N:1 관계를 가진다.
    """

    __tablename__ = "resource_metrics"

    # 기본 키: UUID
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )

    # 외래 키: experiments(id) ON DELETE CASCADE
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 메트릭 이름 (예: CPUUtilization, NetworkIn)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 리소스 ID (예: i-0abc123def456)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # 메트릭 값
    value: Mapped[float] = mapped_column(Float, nullable=False)

    # 메트릭 단위 (예: Percent, Bytes)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # 수집 단계: before(장애 주입 전), during(장애 주입 중), after(장애 주입 후)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)

    # 메트릭 수집 시각
    collected_at: Mapped[datetime] = mapped_column(nullable=False)

    # 레코드 생성 시각
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    # ============================================================
    # 관계 정의 (N:1)
    # ============================================================
    experiment = relationship("Experiment", back_populates="resource_metrics")

    # ============================================================
    # 인덱스 정의
    # ============================================================
    __table_args__ = (
        Index("idx_resource_metrics_experiment_id", "experiment_id"),
        Index("idx_resource_metrics_collected_at", "collected_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ResourceMetric(id={self.id}, metric_name='{self.metric_name}', "
            f"phase='{self.phase}', value={self.value})>"
        )
