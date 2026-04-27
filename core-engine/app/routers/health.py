"""
헬스 체크 라우터

서비스 정상 동작 확인을 위한 헬스 체크 엔드포인트를 제공한다.
ALB Target Group 헬스 체크 및 배포 후 서비스 상태 확인에 사용된다.
"""

from fastapi import APIRouter

router = APIRouter(tags=["헬스 체크"])


@router.get("/health")
@router.get("/api/health")
async def health_check():
    """
    헬스 체크 엔드포인트

    Returns:
        서비스 상태 정보
    """
    return {"status": "ok"}
