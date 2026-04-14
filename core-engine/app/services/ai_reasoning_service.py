"""
AI Reasoning Service — Gemini API 호출 및 재시도 로직

Google AI SDK(google-generativeai)를 사용하여 Gemini API를 비동기로 호출하고,
페르소나별 심리 상태를 추론한다.
지수 백오프 재시도, 응답 파싱, 지연 시간 측정을 담당한다.

Requirements: 3.1, 3.2, 3.5, 3.6, 3.7
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AIReasoningError
from app.models.persona_inference import PersonaInference
from app.services.persona_service import PersonaService
from app.services.secret_service import get_secret_service

logger = logging.getLogger(__name__)

# Gemini 모델명
_GEMINI_MODEL = "gemini-2.0-flash"


class AIReasoningService:
    """Gemini API 호출 및 페르소나 추론 서비스"""

    # 최대 재시도 횟수 (Req 3.5)
    MAX_RETRIES = 3
    # 지수 백오프 기본 대기 시간 — 초 (Req 3.5: 1s, 2s, 4s)
    BACKOFF_BASE = 1

    def __init__(self, db: AsyncSession):
        self.db = db
        self._persona_service = PersonaService()
        self._secret_service = get_secret_service()
        self._model = None

    # ============================================================
    # Gemini 모델 지연 초기화
    # ============================================================
    def _get_model(self) -> genai.GenerativeModel:
        """
        SecretService에서 API Key를 조회하여 Gemini 모델을 초기화한다.
        한 번 초기화된 모델은 재사용한다. (Req 3.4)
        """
        if self._model is None:
            api_key = self._secret_service.get_gemini_api_key()
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(_GEMINI_MODEL)
        return self._model

    # ============================================================
    # 페르소나 추론 실행 (재시도 포함)
    # ============================================================
    async def infer_persona_reaction(
        self,
        experiment_id: str,
        persona_type: str,
        fault_context: dict[str, Any],
    ) -> PersonaInference:
        """
        Gemini API를 호출하여 페르소나별 심리 상태를 추론한다.

        지수 백오프 재시도 (1초, 2초, 4초, 최대 3회)를 적용한다. (Req 3.5)
        3회 실패 시 inference_failed 상태로 저장한다. (Req 3.6)
        API 지연 시간(api_latency_ms)을 측정하여 결과에 포함한다. (Req 3.7)

        Args:
            experiment_id: 실험 ID (UUID 문자열)
            persona_type: 페르소나 유형 (impatient, meticulous, casual)
            fault_context: 장애 컨텍스트 딕셔너리

        Returns:
            PersonaInference ORM 인스턴스
        """
        # 프롬프트 생성
        prompt = self._persona_service.build_prompt(persona_type, fault_context)
        exp_uuid = uuid.UUID(experiment_id)

        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # API 호출 및 지연 시간 측정 (Req 3.7)
                start_time = time.monotonic()
                response_text = await self._call_gemini(prompt)
                latency_ms = (time.monotonic() - start_time) * 1000

                # 응답 JSON 파싱 (Req 3.2)
                parsed = self._parse_response(response_text)

                # 성공 결과 생성
                inference = PersonaInference(
                    experiment_id=exp_uuid,
                    persona_type=persona_type,
                    emotion=parsed["emotion"],
                    churn_probability=parsed["churn_probability"],
                    frustration_index=parsed["frustration_index"],
                    reasoning=parsed["reasoning"],
                    api_latency_ms=latency_ms,
                    status="completed",
                )

                logger.info(
                    f"페르소나 추론 성공: experiment_id={experiment_id}, "
                    f"persona_type={persona_type}, latency_ms={latency_ms:.1f}"
                )
                return inference

            except (AIReasoningError, Exception) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    # 지수 백오프: 1초, 2초, 4초 (Req 3.5)
                    wait_time = self.BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        f"Gemini API 호출 실패 (시도 {attempt + 1}/{self.MAX_RETRIES}), "
                        f"{wait_time}초 후 재시도: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue

        # 3회 모두 실패 시 inference_failed 상태 저장 (Req 3.6)
        failure_reason = str(last_error) if last_error else "알 수 없는 오류"
        logger.error(
            f"페르소나 추론 실패 (최대 재시도 초과): experiment_id={experiment_id}, "
            f"persona_type={persona_type}, reason={failure_reason}"
        )

        inference = PersonaInference(
            experiment_id=exp_uuid,
            persona_type=persona_type,
            status="inference_failed",
            failure_reason=failure_reason,
        )
        return inference

    # ============================================================
    # Gemini API 호출 (Google AI SDK 비동기)
    # ============================================================
    async def _call_gemini(self, prompt: str) -> str:
        """
        Google AI SDK를 사용하여 Gemini API를 비동기로 호출한다. (Req 3.1)

        Args:
            prompt: Gemini API에 전송할 프롬프트

        Returns:
            Gemini API 응답 텍스트

        Raises:
            AIReasoningError: API 호출 실패 시
        """
        try:
            model = self._get_model()
            # 동기 SDK를 이벤트 루프에서 블로킹 없이 실행
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt),
            )

            # 응답 텍스트 추출
            if not response or not response.text:
                raise AIReasoningError(
                    "Gemini API 응답이 비어있습니다."
                )

            return response.text

        except AIReasoningError:
            raise
        except Exception as e:
            raise AIReasoningError(f"Gemini API 호출 오류: {e}") from e

    # ============================================================
    # Gemini 응답 JSON 파싱 (Req 3.2)
    # ============================================================
    @staticmethod
    def _parse_response(response_text: str) -> dict[str, Any]:
        """
        Gemini API 응답 텍스트를 JSON으로 파싱한다.

        응답에서 JSON 블록을 추출하고 필수 필드를 검증한다.
        emotion, churn_probability, frustration_index, reasoning 필드를 반환한다.

        Args:
            response_text: Gemini API 응답 텍스트

        Returns:
            파싱된 딕셔너리 (emotion, churn_probability, frustration_index, reasoning)

        Raises:
            AIReasoningError: 파싱 실패 또는 필수 필드 누락 시
        """
        # JSON 코드 블록 제거 (```json ... ``` 형식 처리)
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise AIReasoningError(
                f"Gemini 응답 JSON 파싱 실패: {e}. 원본: {response_text[:200]}"
            ) from e

        # 필수 필드 검증
        required_fields = ["emotion", "churn_probability", "frustration_index", "reasoning"]
        for field in required_fields:
            if field not in parsed:
                raise AIReasoningError(
                    f"Gemini 응답에 필수 필드 '{field}'가 없습니다: {parsed}"
                )

        # 값 범위 검증
        churn_prob = float(parsed["churn_probability"])
        if not (0.0 <= churn_prob <= 1.0):
            raise AIReasoningError(
                f"churn_probability 범위 초과: {churn_prob} (0.0~1.0 필요)"
            )

        frustration = int(parsed["frustration_index"])
        if not (1 <= frustration <= 10):
            raise AIReasoningError(
                f"frustration_index 범위 초과: {frustration} (1~10 필요)"
            )

        emotion = str(parsed["emotion"])
        if not emotion.strip():
            raise AIReasoningError("emotion이 비어있습니다.")

        reasoning = str(parsed["reasoning"])
        if not reasoning.strip():
            raise AIReasoningError("reasoning이 비어있습니다.")

        return {
            "emotion": emotion,
            "churn_probability": churn_prob,
            "frustration_index": frustration,
            "reasoning": reasoning,
        }

    # ============================================================
    # 다중 페르소나 순차 실행 및 독립 저장 (Req 4.5, 3.3)
    # ============================================================
    async def run_all_personas(
        self,
        experiment_id: str,
        persona_types: list[str],
        fault_context: dict[str, Any],
    ) -> list[PersonaInference]:
        """
        다중 페르소나를 순차 실행하고 각 결과를 독립적으로 저장한다.

        각 페르소나별 추론 결과를 persona_inferences 테이블에 독립 저장한다. (Req 4.5)

        Args:
            experiment_id: 실험 ID
            persona_types: 페르소나 유형 목록
            fault_context: 장애 컨텍스트

        Returns:
            PersonaInference 목록
        """
        results: list[PersonaInference] = []

        for persona_type in persona_types:
            logger.info(
                f"페르소나 추론 시작: experiment_id={experiment_id}, "
                f"persona_type={persona_type}"
            )

            inference = await self.infer_persona_reaction(
                experiment_id=experiment_id,
                persona_type=persona_type,
                fault_context=fault_context,
            )

            # 각 페르소나 결과를 독립적으로 DB에 저장 (Req 3.3, 4.5)
            self.db.add(inference)
            await self.db.commit()
            await self.db.refresh(inference)

            results.append(inference)
            logger.info(
                f"페르소나 추론 결과 저장: persona_type={persona_type}, "
                f"status={inference.status}"
            )

        return results
