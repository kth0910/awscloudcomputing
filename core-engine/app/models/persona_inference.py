"""
PersonaInference ORM 모델

persona_inferences 테이블에 대응하는 SQLAlchemy 2.0 스타일 ORM 모델이다.
Gemini AI 페르소나별 심리 상태 추론 결과를 저장한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PersonaInference(Base):
    """
    AI 페르소나 추론 결과 테이블

    Gemini API를 통해 추론된 페르소나별 심리 상태(감정, 이탈 확률, 불만 지수 등)를 저장한다.
    experiments 테이블과 N:1 관계를 가진다.
    """

    __tablename__ = "persona_inferences"

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

    # 페르소나 유형: impatient, meticulous, casual
    persona_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # 감정 상태 (한국어 문자열, 예: "극도의 분노")
    emotion: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 이탈 확률 (0.0 ~ 1.0)
    churn_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 불만 지수 (1 ~ 10)
    frustration_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 추론 근거 (한국어 텍스트)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gemini API 응답 지연 시간 (밀리초)
    api_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 추론 상태: completed, inference_failed
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="completed",
        server_default="completed",
    )

    # 실패 사유 (inference_failed 상태일 때)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 레코드 생성 시각
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
    )

    # ============================================================
    # 관계 정의 (N:1)
    # ============================================================
    experiment = relationship("Experiment", back_populates="persona_inferences")

    # ============================================================
    # 인덱스 정의
    # ============================================================
    __table_args__ = (
        Index("idx_persona_inferences_experiment_id", "experiment_id"),
        Index("idx_persona_inferences_persona_type", "persona_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<PersonaInference(id={self.id}, persona_type='{self.persona_type}', "
            f"status='{self.status}')>"
        )
