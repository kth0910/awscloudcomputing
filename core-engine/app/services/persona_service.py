"""
페르소나 프롬프트 구성 서비스

페르소나 유형별 프롬프트 템플릿을 관리하고,
장애 컨텍스트와 결합하여 Gemini API 요청용 프롬프트를 생성한다.
다중 페르소나 순차 실행 및 독립 저장 로직을 지원한다.

Requirements: 4.1, 4.2, 4.3, 4.5
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================
# 페르소나 프롬프트 템플릿 딕셔너리 (Req 4.1, 4.2)
# 3가지 페르소나: impatient, meticulous, casual
# 각 페르소나는 고유한 성격 특성, 기술 숙련도, 인내심 수준, 기대 응답 시간을 포함
# ============================================================
PERSONA_TEMPLATES: dict[str, dict[str, str]] = {
    "impatient": {
        "name": "성격 급한 유저",
        "traits": "매우 참을성이 없고, 즉각적인 응답을 기대함",
        "tech_level": "중급",
        "patience_level": "매우 낮음 (3초 이상 대기 시 불만)",
        "expected_response_time": "1초 이내",
    },
    "meticulous": {
        "name": "꼼꼼한 유저",
        "traits": "체계적이고 세밀하며, 오류 메시지를 꼼꼼히 읽음",
        "tech_level": "고급",
        "patience_level": "보통 (10초까지 대기 가능)",
        "expected_response_time": "5초 이내",
    },
    "casual": {
        "name": "일반 유저",
        "traits": "가볍게 서비스를 이용하며, 기술적 세부사항에 관심 없음",
        "tech_level": "초급",
        "patience_level": "보통 (5초까지 대기 가능)",
        "expected_response_time": "3초 이내",
    },
}

# 프롬프트 템플릿 (모든 페르소나 공통 구조, Req 4.2, 4.3)
# 페르소나 속성(성격 특성, 기술 숙련도, 인내심 수준, 기대 응답 시간)과
# 장애 컨텍스트(서비스명, 장애 유형, 지속 시간, 영향 범위)를 결합
_PROMPT_TEMPLATE = """당신은 {name}입니다.
성격 특성: {traits}
기술 숙련도: {tech_level}
인내심 수준: {patience_level}
기대 응답 시간: {expected_response_time}

현재 상황:
- 서비스: {service_name}
- 장애 유형: {fault_type}
- 장애 지속 시간: {fault_duration}초
- 영향 범위: {impact_scope}

위 장애 상황에서 이 사용자의 심리 상태를 분석하세요.
반드시 다음 JSON 형식으로 응답하세요:
{{"emotion": "감정 상태 (한국어)", "churn_probability": 0.0~1.0, "frustration_index": 1~10, "reasoning": "추론 근거 (한국어, 2~3문장)"}}"""


class PersonaService:
    """페르소나 프롬프트 구성 서비스 (Req 4.1, 4.2, 4.3)"""

    def build_prompt(self, persona_type: str, fault_context: dict[str, Any]) -> str:
        """
        페르소나 템플릿과 장애 컨텍스트를 결합하여 프롬프트를 생성한다. (Req 4.3)

        페르소나의 성격 특성, 기술 숙련도, 인내심 수준, 기대 응답 시간과
        장애 컨텍스트의 서비스명, 장애 유형, 지속 시간을 모두 포함한다.

        Args:
            persona_type: 페르소나 유형 (impatient, meticulous, casual)
            fault_context: 장애 컨텍스트 딕셔너리
                - service_name: 서비스명
                - fault_type: 장애 유형
                - fault_duration: 장애 지속 시간 (초)
                - impact_scope: 영향 범위

        Returns:
            Gemini API 요청용 프롬프트 문자열

        Raises:
            ValueError: 지원하지 않는 페르소나 유형인 경우
        """
        if persona_type not in PERSONA_TEMPLATES:
            raise ValueError(
                f"지원하지 않는 페르소나 유형입니다: {persona_type}. "
                f"허용 유형: {list(PERSONA_TEMPLATES.keys())}"
            )

        template = PERSONA_TEMPLATES[persona_type]

        # 페르소나 속성 + 장애 컨텍스트를 결합하여 프롬프트 생성
        prompt = _PROMPT_TEMPLATE.format(
            name=template["name"],
            traits=template["traits"],
            tech_level=template["tech_level"],
            patience_level=template["patience_level"],
            expected_response_time=template["expected_response_time"],
            service_name=fault_context.get("service_name", "알 수 없는 서비스"),
            fault_type=fault_context.get("fault_type", "알 수 없는 장애"),
            fault_duration=fault_context.get("fault_duration", 0),
            impact_scope=fault_context.get("impact_scope", "알 수 없음"),
        )

        logger.debug(
            f"프롬프트 생성 완료: persona_type={persona_type}, "
            f"prompt_length={len(prompt)}"
        )
        return prompt

    @staticmethod
    def get_available_personas() -> list[str]:
        """사용 가능한 페르소나 유형 목록을 반환한다. (Req 4.1)"""
        return list(PERSONA_TEMPLATES.keys())
