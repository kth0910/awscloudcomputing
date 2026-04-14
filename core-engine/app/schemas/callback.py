"""
Lambda 콜백(Callback) 관련 Pydantic 요청 스키마

ChaosCallback: Chaos Injector Lambda가 Core Engine에 전송하는 콜백 페이로드
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChaosCallback(BaseModel):
    """
    Chaos Injector Lambda 콜백 스키마

    장애 주입 완료/실패/롤백 완료 시 Core Engine에 전송되는 페이로드이다.
    status는 허용된 3가지 상태만 허용한다.
    """

    # 실험 ID (UUID 문자열)
    experiment_id: str = Field(..., description="실험 ID")

    # 콜백 상태: success, failed, rollback_completed
    status: Literal["success", "failed", "rollback_completed"] = Field(
        ..., description="장애 주입 결과 상태"
    )

    # 장애 주입 시작 시각
    started_at: datetime = Field(..., description="장애 주입 시작 시각")

    # 장애 주입 종료 시각
    ended_at: datetime = Field(..., description="장애 주입 종료 시각")

    # 대상 리소스 ID
    target_resource: str = Field(..., description="대상 AWS 리소스 ID")

    # 장애 유형
    fault_type: str = Field(..., description="장애 유형")

    # 오류 상세 정보 (실패 시)
    error_detail: str | None = Field(default=None, description="오류 상세 정보")

    # 원래 리소스 상태 (롤백에 사용)
    original_state: dict | None = Field(default=None, description="원래 리소스 상태")
