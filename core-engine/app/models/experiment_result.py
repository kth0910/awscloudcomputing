"""
ExperimentResult ORM 모델

experiment_results 테이블에 대응하는 SQLAlchemy 2.0 스타일 ORM 모델이다.
Chaos 장애 주입의 실행 결과(성공/실패/롤백 완료, 시작/종료 시각 등)를 저장한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ExperimentResult(Base):
    """
    장애 주입 결과 테이블

    Chaos Injector Lambda의 콜백으로 전달된 실험 결과를 저장한다.
    experiments 테이블과 N:1 관계를 가진다.
    """

    __tablename__ = "experiment_results"

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

    # 결과 상태: success, failed, rollback_completed
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # 장애 주입 시작/종료 시각
    chaos_started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    chaos_ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # 장애 유형
    fault_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # 대상 리소스 ID
    target_resource: Mapped[str] = mapped_column(String(255), nullable=False)

    # 오류 상세 정보 (실패 시)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 원래 리소스 상태 (JSONB, 롤백에 사용)
    original_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 롤백 후 리소스 상태 (JSONB)
    rollback_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 레코드 생성 시각
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    # ============================================================
    # 관계 정의 (N:1)
    # ============================================================
    experiment = relationship("Experiment", back_populates="results")

    # ============================================================
    # 인덱스 정의
    # ============================================================
    __table_args__ = (
        Index("idx_experiment_results_experiment_id", "experiment_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExperimentResult(id={self.id}, experiment_id={self.experiment_id}, "
            f"status='{self.status}')>"
        )
