"""
페르소나 관리 라우터

AI 페르소나 목록 조회 API를 제공한다.
- GET /api/personas: 지원되는 페르소나 유형 목록 조회
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/personas", tags=["페르소나 관리"])

# ============================================================
# 지원되는 페르소나 정의
# ============================================================
PERSONAS = [
    {
        "type": "impatient",
        "name": "성격 급한 유저",
        "traits": "매우 참을성이 없고, 즉각적인 응답을 기대함",
        "tech_level": "중급",
        "patience_level": "매우 낮음 (3초 이상 대기 시 불만)",
        "expected_response_time": "1초 이내",
    },
    {
        "type": "meticulous",
        "name": "꼼꼼한 유저",
        "traits": "체계적이고 세밀하며, 오류 메시지를 꼼꼼히 읽음",
        "tech_level": "고급",
        "patience_level": "보통 (10초까지 대기 가능)",
        "expected_response_time": "5초 이내",
    },
    {
        "type": "casual",
        "name": "일반 유저",
        "traits": "가볍게 서비스를 이용하며, 기술적 세부사항에 관심 없음",
        "tech_level": "초급",
        "patience_level": "보통 (5초까지 대기 가능)",
        "expected_response_time": "3초 이내",
    },
]


# ============================================================
# GET /api/personas — 페르소나 목록 조회
# ============================================================
@router.get("")
async def list_personas():
    """지원되는 AI 페르소나 유형 목록을 반환한다."""
    return PERSONAS
