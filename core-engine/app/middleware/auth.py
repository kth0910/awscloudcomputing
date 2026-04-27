"""
Cognito JWT 인증 미들웨어

Cognito User Pool의 JWKS를 사용하여 JWT 토큰을 검증하고,
인증된 사용자 정보를 FastAPI 의존성으로 제공한다.
"""

import logging
import time

import httpx
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from pydantic import BaseModel

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# 인증 제외 경로
EXCLUDED_PATHS = {
    "/api/health",
    "/api/internal/callback",
    "/docs",
    "/openapi.json",
}


class AuthenticatedUser(BaseModel):
    """인증된 사용자 컨텍스트"""

    cognito_sub: str
    email: str


class CognitoJWTAuth:
    """Cognito JWT 검증 클래스. JWKS 캐싱 및 토큰 검증을 담당한다."""

    def __init__(self, user_pool_id: str, region: str):
        self.user_pool_id = user_pool_id
        self.region = region
        self.issuer = (
            f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        )
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self._jwks_cache: dict | None = None
        self._jwks_cache_time: float = 0
        self.JWKS_CACHE_TTL = 3600  # 1시간

    async def _get_jwks(self) -> dict:
        """JWKS를 가져온다. TTL 기반 캐싱을 사용한다."""
        now = time.time()
        if (
            self._jwks_cache is not None
            and (now - self._jwks_cache_time) < self.JWKS_CACHE_TTL
        ):
            return self._jwks_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = now
                return self._jwks_cache
        except httpx.HTTPError as e:
            logger.error(f"JWKS 조회 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "internal_error",
                    "message": "인증 서비스 오류",
                },
            ) from e

    async def verify_token(self, token: str) -> AuthenticatedUser:
        """JWT 토큰을 검증하고 AuthenticatedUser를 반환한다."""
        jwks = await self._get_jwks()

        try:
            # 헤더에서 kid 추출
            unverified_header = jwt.get_unverified_header(token)
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "unauthorized",
                    "message": "유효하지 않은 토큰입니다",
                },
            )

        # kid에 매칭되는 키 찾기
        rsa_key = {}
        kid = unverified_header.get("kid")
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "unauthorized",
                    "message": "유효하지 않은 토큰입니다",
                },
            )

        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={
                    "verify_aud": False,
                    "verify_exp": True,
                    "verify_iss": True,
                },
            )
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "unauthorized",
                    "message": "토큰이 만료되었습니다",
                },
            )
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "unauthorized",
                    "message": "유효하지 않은 토큰입니다",
                },
            )

        cognito_sub = payload.get("sub")
        email = payload.get("email", "")

        if not cognito_sub:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "unauthorized",
                    "message": "유효하지 않은 토큰입니다",
                },
            )

        return AuthenticatedUser(cognito_sub=cognito_sub, email=email)


# 모듈 레벨 싱글톤 인스턴스
_auth_instance: CognitoJWTAuth | None = None


def _get_auth(settings: Settings | None = None) -> CognitoJWTAuth:
    """CognitoJWTAuth 싱글톤 인스턴스를 반환한다."""
    global _auth_instance
    if _auth_instance is None:
        if settings is None:
            settings = get_settings()
        _auth_instance = CognitoJWTAuth(
            user_pool_id=settings.cognito_user_pool_id,
            region=settings.cognito_region,
        )
    return _auth_instance


async def get_current_user(request: Request) -> AuthenticatedUser:
    """
    FastAPI 의존성: Bearer 토큰을 추출하고 검증하여 AuthenticatedUser를 반환한다.

    인증 제외 경로는 이 의존성을 사용하지 않는 라우터에 등록한다.
    제외 경로: /api/health, /api/internal/callback, /docs, /openapi.json
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Authorization 헤더가 필요합니다",
            },
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Bearer 토큰 형식이 아닙니다",
            },
        )

    token = parts[1]
    auth = _get_auth()
    return await auth.verify_token(token)
