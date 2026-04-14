"""
Core Engine 콜백 전송 모듈

장애 주입 결과를 Core Engine에 HTTP POST로 전송한다.
"""

import json
import logging
import os
from datetime import datetime, timezone

import urllib3

logger = logging.getLogger(__name__)

# Core Engine 콜백 기본 URL (환경 변수에서 구성)
CALLBACK_BASE_URL = os.environ.get("CALLBACK_BASE_URL", "")


def send_callback(
    callback_url: str,
    experiment_id: str,
    status: str,
    started_at: datetime,
    ended_at: datetime,
    target_resource: str,
    fault_type: str,
    error_detail: str | None = None,
    original_state: dict | None = None,
) -> bool:
    """
    Core Engine에 콜백을 전송한다.

    Parameters:
        callback_url: 콜백 수신 URL
        experiment_id: 실험 UUID
        status: 실행 상태 ("success", "failed", "rollback_completed")
        started_at: 실행 시작 시간
        ended_at: 실행 종료 시간
        target_resource: 대상 리소스 ID
        fault_type: 장애 유형
        error_detail: 오류 상세 정보 (실패 시)
        original_state: 원래 상태 딕셔너리

    Returns:
        전송 성공 여부
    """
    # 콜백 URL 결정: 이벤트에 포함된 URL 우선, 없으면 환경 변수 사용
    url = callback_url or CALLBACK_BASE_URL
    if not url:
        logger.warning("콜백 URL이 설정되지 않음. 콜백 전송 건너뜀.")
        return False

    payload = {
        "experiment_id": experiment_id,
        "status": status,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "target_resource": target_resource,
        "fault_type": fault_type,
    }

    if error_detail:
        payload["error_detail"] = error_detail

    if original_state:
        payload["original_state"] = original_state

    try:
        http = urllib3.PoolManager()
        response = http.request(
            "POST",
            url,
            body=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        logger.info(
            "콜백 전송 완료: status=%s, response_status=%d",
            status,
            response.status,
        )
        return 200 <= response.status < 300
    except Exception as e:
        logger.error("콜백 전송 실패: %s", str(e))
        return False


def build_error_callback_payload(
    experiment_id: str,
    target_resource: str,
    fault_type: str,
    error: Exception,
    started_at: datetime,
) -> dict:
    """
    예외 발생 시 에러 콜백 페이로드를 생성한다.

    Parameters:
        experiment_id: 실험 UUID
        target_resource: 대상 리소스 ID
        fault_type: 장애 유형
        error: 발생한 예외
        started_at: 실행 시작 시간

    Returns:
        에러 콜백 페이로드 딕셔너리 (status="failed", error_detail 포함)
    """
    ended_at = datetime.now(timezone.utc)
    error_detail = f"{type(error).__name__}: {str(error)}"

    # error_detail이 비어있지 않도록 보장 (Property 2)
    if not error_detail.strip():
        error_detail = f"Unknown error: {type(error).__name__}"

    return {
        "experiment_id": experiment_id,
        "status": "failed",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "target_resource": target_resource,
        "fault_type": fault_type,
        "error_detail": error_detail,
    }
