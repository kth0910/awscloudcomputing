"""
Chaos Injector Lambda 핸들러 진입점

이벤트를 파싱하고, fault_type에 따라 적절한 장애 시나리오를 디스패치한다.
장애 주입 후 자동 롤백을 수행하고, Core Engine에 콜백을 전송한다.
"""

import json
import logging
from datetime import datetime, timezone

from callback import build_error_callback_payload, send_callback
from rollback import RollbackManager
from scenarios.ec2_stop import EC2StopScenario
from scenarios.rds_delay import RDSDelayScenario
from scenarios.sg_modify import SGModifyScenario
from sts_manager import STSCredentialManager

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 허용된 장애 유형 목록 (Property 1: 허용 목록 외 요청 거부)
ALLOWED_FAULT_TYPES = {"ec2_stop", "sg_port_block", "rds_delay"}

# fault_type → 시나리오 클래스 매핑
SCENARIO_MAP = {
    "ec2_stop": EC2StopScenario,
    "sg_port_block": SGModifyScenario,
    "rds_delay": RDSDelayScenario,
}


def validate_event(event: dict) -> dict | None:
    """
    이벤트 페이로드를 검증한다.

    Parameters:
        event: Lambda 이벤트 페이로드

    Returns:
        검증 실패 시 에러 딕셔너리, 성공 시 None
    """
    required_fields = ["experiment_id", "target_resource", "fault_type"]
    for field in required_fields:
        if field not in event or not event[field]:
            return {"error": f"필수 필드 누락: {field}"}

    fault_type = event["fault_type"]
    if fault_type not in ALLOWED_FAULT_TYPES:
        return {
            "error": f"허용되지 않은 장애 유형: {fault_type}. "
            f"허용 목록: {sorted(ALLOWED_FAULT_TYPES)}"
        }

    return None


def handler(event: dict, context) -> dict:
    """
    Lambda 핸들러 진입점

    Parameters:
        event: Lambda 이벤트 페이로드
            - experiment_id: 실험 UUID
            - target_resource: 대상 AWS 리소스 ID
            - fault_type: 장애 유형 (ec2_stop | sg_port_block | rds_delay)
            - duration_seconds: 장애 지속 시간 (기본 300초)
            - callback_url: Core Engine 콜백 URL
            - rollback_config: 롤백 설정
        context: Lambda 실행 컨텍스트

    Returns:
        실행 결과 딕셔너리
    """
    logger.info("Chaos Injector 실행 시작: %s", json.dumps(event, ensure_ascii=False))

    # 이벤트 필드 추출
    experiment_id = event.get("experiment_id", "unknown")
    target_resource = event.get("target_resource", "unknown")
    fault_type = event.get("fault_type", "unknown")
    duration_seconds = event.get("duration_seconds", 300)
    callback_url = event.get("callback_url", "")
    rollback_config = event.get("rollback_config", {})
    cross_account_role_arn = event.get("cross_account_role_arn") or ""

    started_at = datetime.now(timezone.utc)

    # 1. 이벤트 검증 (Property 1: 허용 목록 외 fault_type 거부)
    validation_error = validate_event(event)
    if validation_error:
        logger.error("이벤트 검증 실패: %s", validation_error["error"])
        error_payload = build_error_callback_payload(
            experiment_id=experiment_id,
            target_resource=target_resource,
            fault_type=fault_type,
            error=ValueError(validation_error["error"]),
            started_at=started_at,
        )
        send_callback(callback_url=callback_url, **error_payload)
        return {
            "statusCode": 400,
            "body": json.dumps(validation_error, ensure_ascii=False),
        }

    # 2. Cross-Account 자격 증명 처리
    sts_manager = None
    credentials = None
    if cross_account_role_arn:
        try:
            sts_manager = STSCredentialManager()
            session_name = f"ChaosTwin-{experiment_id}"
            credentials = sts_manager.assume_role(
                role_arn=cross_account_role_arn,
                session_name=session_name,
                duration_seconds=duration_seconds,
            )
            logger.info("Cross-Account AssumeRole 성공: %s", cross_account_role_arn)
        except Exception as e:
            logger.error("Cross-Account AssumeRole 실패: %s", str(e))
            error_payload = build_error_callback_payload(
                experiment_id=experiment_id,
                target_resource=target_resource,
                fault_type=fault_type,
                error=e,
                started_at=started_at,
            )
            send_callback(callback_url=callback_url, **error_payload)
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {"error": str(e), "experiment_id": experiment_id},
                    ensure_ascii=False,
                ),
            }

    # 3. 시나리오 인스턴스 생성 (Cross-Account 클라이언트 주입)
    scenario_class = SCENARIO_MAP[fault_type]
    if credentials and sts_manager:
        if fault_type == "ec2_stop":
            ec2_client = sts_manager.create_client("ec2", credentials)
            scenario = scenario_class(ec2_client=ec2_client)
        elif fault_type == "sg_port_block":
            ec2_client = sts_manager.create_client("ec2", credentials)
            scenario = scenario_class(ec2_client=ec2_client)
        elif fault_type == "rds_delay":
            ec2_client = sts_manager.create_client("ec2", credentials)
            rds_client = sts_manager.create_client("rds", credentials)
            scenario = scenario_class(ec2_client=ec2_client, rds_client=rds_client)
        else:
            scenario = scenario_class()
    else:
        scenario = scenario_class()

    # 4. RollbackManager를 통해 장애 주입 + 자동 롤백 실행
    rollback_manager = RollbackManager(
        scenario=scenario,
        experiment_id=experiment_id,
        target_resource=target_resource,
        fault_type=fault_type,
        duration_seconds=duration_seconds,
        callback_url=callback_url,
        config=rollback_config,
        sts_manager=sts_manager,
        role_arn=cross_account_role_arn,
    )

    try:
        result = rollback_manager.execute()
        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False, default=str),
        }
    except Exception as e:
        # 예외 발생 시 에러 콜백 전송 (Property 2)
        logger.error("Chaos Injector 실행 중 예외 발생: %s", str(e), exc_info=True)
        error_payload = build_error_callback_payload(
            experiment_id=experiment_id,
            target_resource=target_resource,
            fault_type=fault_type,
            error=e,
            started_at=started_at,
        )
        send_callback(callback_url=callback_url, **error_payload)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": str(e), "experiment_id": experiment_id},
                ensure_ascii=False,
            ),
        }
