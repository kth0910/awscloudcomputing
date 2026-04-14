"""
페르소나(Persona) 관련 Pydantic 응답 스키마

PersonaInferenceResponse: AI 페르소나 추론 결과 응답
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PersonaInferenceResponse(BaseModel):
    """
    AI 페르소나 추론 결과 응답 스키마

    persona_inferences 테이블의 ORM 모델에서 직접 변환 가능하다.
    """

    model_config = ConfigDict(from_attributes=True)

    # 기본 키
    id: uuid.UUID

    # 외래 키: 실험 ID
    experiment_id: uuid.UUID

    # 페르소나 유형: impatient, meticulous, casual
    persona_type: Literal["impatient", "meticulous", "casual"]

    # 감정 상태 (한국어 문자열)
    emotion: str | None = None

    # 이탈 확률 (0.0 ~ 1.0)
    churn_probability: float | None = Field(default=None, ge=0.0, le=1.0)

    # 불만 지수 (1 ~ 10)
    frustration_index: int | None = Field(default=None, ge=1, le=10)

    # 추론 근거 (한국어 텍스트)
    reasoning: str | None = None

    # Gemini API 응답 지연 시간 (밀리초)
    api_latency_ms: float | None = None

    # 추론 상태: completed, inference_failed
    status: Literal["completed", "inference_failed"]

    # 실패 사유
    failure_reason: str | None = None

    # 레코드 생성 시각
    created_at: datetime
