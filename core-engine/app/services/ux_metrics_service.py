"""
UX 메트릭 수집 서비스

probe_endpoint에 HTTP GET 요청을 보내 UX 메트릭(response_latency_ms, status_code, error_rate)을 수집한다.
각 단계(before, during, after)에서 3회 프로빙 후 중앙값을 대표 값으로 사용한다.
"""

import logging
import time
import uuid
from datetime import datetime

import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ux_metric import UXMetric

logger = logging.getLogger(__name__)

PROBES_PER_PHASE = 3


class ProbeResponse(BaseModel):
    """단일 프로빙 결과"""

    response_latency_ms: float
    status_code: int


class UXMetricsService:
    """probe_endpoint 기반 UX 메트릭 수집"""

    def __init__(
        self,
        db: AsyncSession,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.db = db
        self._http_client = http_client

    async def single_probe(
        self, url: str, timeout: float = 5.0
    ) -> ProbeResponse:
        """
        단일 HTTP GET 프로빙.

        url에 HTTP GET 요청을 전송하고 응답 지연 시간과 상태 코드를 반환한다.
        타임아웃 시 status_code=0으로 기록한다.

        Args:
            url: 프로빙 대상 URL
            timeout: 타임아웃 (초, 기본 5.0)

        Returns:
            ProbeResponse: response_latency_ms, status_code
        """
        start = time.monotonic()
        try:
            if self._http_client is not None:
                response = await self._http_client.get(url, timeout=timeout)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=timeout)
            elapsed_ms = (time.monotonic() - start) * 1000
            return ProbeResponse(
                response_latency_ms=elapsed_ms,
                status_code=response.status_code,
            )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError, Exception):
            elapsed_ms = (time.monotonic() - start) * 1000
            return ProbeResponse(
                response_latency_ms=elapsed_ms,
                status_code=0,
            )

    async def collect_phase_metrics(
        self,
        probe_endpoint: str,
        phase: str,
        experiment_id: str,
    ) -> UXMetric:
        """
        단계별 3회 프로빙 → 중앙값 계산 → DB 저장.

        probe_endpoint에 3회 HTTP GET 요청을 전송하고,
        response_latency_ms와 status_code의 중앙값, error_rate를 계산하여
        UXMetric 레코드를 DB에 저장한다.

        Args:
            probe_endpoint: 프로빙 대상 URL
            phase: 수집 단계 ("before", "during", "after")
            experiment_id: 실험 ID (UUID 문자열)

        Returns:
            UXMetric: 저장된 UX 메트릭 레코드
        """
        probes: list[ProbeResponse] = []
        for _ in range(PROBES_PER_PHASE):
            result = await self.single_probe(probe_endpoint)
            probes.append(result)

        # 중앙값 계산 (3개 값 정렬 후 가운데 값)
        latencies = sorted(p.response_latency_ms for p in probes)
        status_codes = sorted(p.status_code for p in probes)
        median_latency = latencies[1]
        median_status_code = status_codes[1]

        # error_rate: 4xx/5xx/timeout(0) 비율
        error_count = sum(
            1
            for p in probes
            if p.status_code == 0 or p.status_code >= 400
        )
        error_rate = error_count / PROBES_PER_PHASE

        exp_uuid = uuid.UUID(experiment_id)
        metric = UXMetric(
            experiment_id=exp_uuid,
            phase=phase,
            response_latency_ms=median_latency,
            status_code=median_status_code,
            error_rate=error_rate,
            collected_at=datetime.utcnow(),
        )
        self.db.add(metric)
        await self.db.commit()
        await self.db.refresh(metric)

        logger.info(
            f"UX 메트릭 수집 완료: experiment_id={experiment_id}, "
            f"phase={phase}, latency={median_latency:.1f}ms, "
            f"status={median_status_code}, error_rate={error_rate:.2f}"
        )

        return metric
