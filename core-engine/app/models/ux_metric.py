"""
UXMetric ORM 모델

ux_metrics 테이블에 대응하는 SQLAlchemy 2.0 스타일 ORM 모델이다.
probe_endpoint 프로빙을 통해 수집된 UX 메트릭(response_latency_ms, status_code, error_rate)을 저장한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class UXMetric(Base):
    """
    UX 메트릭 테이블

    장애 주입 전(before), 중(during), 후(after) 단계별로
    probe_endpoint에서 수집한 UX 메트릭(응답 지연, 상태 코드, 에러 비율)을 저장한다.
    experiments 테이블과 N:1 관계를 가진다.
    """

    __tablename__ = "ux_metrics"

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

    # 수집 단계: before(장애 주입 전), during(장애 주입 중), after(장애 주입 후)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)

    # 응답 지연 시간 (밀리초)
    response_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # HTTP 상태 코드 (타임아웃 시 0)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)

    # 에러 비율 (0.0 ~ 1.0)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False)

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
    experiment = relationship("Experiment", back_populates="ux_metrics")

    # ============================================================
    # 인덱스 및 CHECK 제약 조건 정의
    # ============================================================
    __table_args__ = (
        Index("idx_ux_metrics_experiment_id", "experiment_id"),
        CheckConstraint(
            "phase IN ('before', 'during', 'after')",
            name="ck_ux_metrics_phase",
        ),
        CheckConstraint(
            "error_rate >= 0.0 AND error_rate <= 1.0",
            name="ck_ux_metrics_error_rate",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UXMetric(id={self.id}, phase='{self.phase}', "
            f"response_latency_ms={self.response_latency_ms}, "
            f"status_code={self.status_code}, error_rate={self.error_rate})>"
        )
