"""
실험(Experiment) 관련 Pydantic 요청/응답 스키마

ExperimentCreate: 실험 생성 요청
RunConfig: 실험 실행 설정 (페르소나 오버라이드)
ExperimentResponse: 실험 조회 응답
ExperimentResultResponse: 장애 주입 결과 응답
ExperimentDetail: 실험 상세 응답 (결과 + 페르소나 추론 포함)
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.persona import PersonaInferenceResponse


# ============================================================
# 요청 스키마
# ============================================================


class ExperimentCreate(BaseModel):
    """
    실험 생성 요청 스키마

    fault_type은 허용된 3가지 장애 유형만 허용한다.
    persona_types는 허용된 3가지 페르소나 유형만 허용한다.
    """

    # 실험 이름
    name: str = Field(..., min_length=1, max_length=255, description="실험 이름")

    # 대상 AWS 리소스 ID (예: i-0abc123)
    target_resource: str = Field(
        ..., min_length=1, max_length=255, description="대상 AWS 리소스 ID"
    )

    # 장애 유형: ec2_stop, sg_port_block, rds_delay
    fault_type: Literal["ec2_stop", "sg_port_block", "rds_delay"] = Field(
        ..., description="장애 유형"
    )

    # 장애 지속 시간 (초, 기본 300초 = 5분)
    duration_seconds: int = Field(
        default=300, ge=1, le=3600, description="장애 지속 시간 (초)"
    )

    # 페르소나 유형 목록
    persona_types: list[Literal["impatient", "meticulous", "casual"]] = Field(
        default=["impatient", "meticulous", "casual"],
        min_length=1,
        description="AI 페르소나 유형 목록",
    )


class RunConfig(BaseModel):
    """
    실험 실행 설정 스키마

    실행 시 페르소나 유형을 오버라이드할 수 있다.
    None이면 실험 생성 시 설정된 페르소나를 사용한다.
    """

    # 페르소나 유형 오버라이드 (None이면 기본값 사용)
    persona_types: list[str] | None = Field(
        default=None, description="페르소나 유형 오버라이드 목록"
    )


# ============================================================
# 응답 스키마
# ============================================================


class ExperimentResultResponse(BaseModel):
    """
    장애 주입 결과 응답 스키마

    experiment_results 테이블의 ORM 모델에서 직접 변환 가능하다.
    """

    model_config = ConfigDict(from_attributes=True)

    # 기본 키
    id: uuid.UUID

    # 외래 키: 실험 ID
    experiment_id: uuid.UUID

    # 결과 상태: success, failed, rollback_completed
    status: Literal["success", "failed", "rollback_completed"]

    # 장애 주입 시작/종료 시각
    chaos_started_at: datetime | None = None
    chaos_ended_at: datetime | None = None

    # 장애 유형
    fault_type: str

    # 대상 리소스 ID
    target_resource: str

    # 오류 상세 정보
    error_detail: str | None = None

    # 원래 리소스 상태
    original_state: dict | None = None

    # 롤백 후 리소스 상태
    rollback_state: dict | None = None

    # 레코드 생성 시각
    created_at: datetime


class ResourceMetricResponse(BaseModel):
    """
    리소스 메트릭 응답 스키마

    resource_metrics 테이블의 ORM 모델에서 직접 변환 가능하다.
    """

    model_config = ConfigDict(from_attributes=True)

    # 기본 키
    id: uuid.UUID

    # 외래 키: 실험 ID
    experiment_id: uuid.UUID

    # 메트릭 이름 (예: CPUUtilization)
    metric_name: str

    # 리소스 ID
    resource_id: str

    # 메트릭 값
    value: float

    # 메트릭 단위 (예: Percent, Bytes)
    unit: str

    # 수집 단계: before, during, after
    phase: Literal["before", "during", "after"]

    # 메트릭 수집 시각
    collected_at: datetime

    # 레코드 생성 시각
    created_at: datetime


class ExperimentResponse(BaseModel):
    """
    실험 조회 응답 스키마

    experiments 테이블의 ORM 모델에서 직접 변환 가능하다.
    실험 목록 조회 등에서 사용된다.
    """

    model_config = ConfigDict(from_attributes=True)

    # 기본 키
    id: uuid.UUID

    # 실험 이름
    name: str

    # 대상 AWS 리소스 ID
    target_resource: str

    # 장애 유형: ec2_stop, sg_port_block, rds_delay
    fault_type: Literal["ec2_stop", "sg_port_block", "rds_delay"]

    # 실험 상태: created, running, completed, failed, cancelled, probe_failed
    status: Literal["created", "running", "completed", "failed", "cancelled", "probe_failed"]

    # 장애 지속 시간 (초)
    duration_seconds: int

    # 페르소나 유형 목록 (JSON 텍스트)
    persona_types_json: str

    # 생성 시각
    created_at: datetime

    # 실험 시작 시각
    started_at: datetime | None = None

    # 실험 종료 시각
    ended_at: datetime | None = None


class ExperimentDetail(ExperimentResponse):
    """
    실험 상세 응답 스키마

    ExperimentResponse를 상속하며, 장애 주입 결과와 페르소나 추론 결과를 포함한다.
    실험 상세 조회(GET /api/experiments/{id})에서 사용된다.
    """

    # 장애 주입 결과 목록
    results: list[ExperimentResultResponse] = Field(default_factory=list)

    # AI 페르소나 추론 결과 목록
    persona_inferences: list[PersonaInferenceResponse] = Field(default_factory=list)
