"""
CloudWatch 메트릭 수집 서비스

장애 주입 전/중/후 CloudWatch 메트릭을 수집하고
resource_metrics 테이블에 phase 구분하여 저장한다.

수집 대상 메트릭:
- EC2: CPUUtilization, NetworkIn, NetworkOut
- RDS: DatabaseConnections, CPUUtilization
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.resource_metric import ResourceMetric

logger = logging.getLogger(__name__)

# 수집 대상 메트릭 정의
# 각 항목: (네임스페이스, 메트릭 이름, 차원 키, 단위)
EC2_METRICS: list[tuple[str, str, str, str]] = [
    ("AWS/EC2", "CPUUtilization", "InstanceId", "Percent"),
    ("AWS/EC2", "NetworkIn", "InstanceId", "Bytes"),
    ("AWS/EC2", "NetworkOut", "InstanceId", "Bytes"),
]

RDS_METRICS: list[tuple[str, str, str, str]] = [
    ("AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", "Count"),
    ("AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "Percent"),
]

# phase 타입 정의
Phase = Literal["before", "during", "after"]


def _to_naive_utc(value: datetime) -> datetime:
    """DB 저장을 위해 timezone-aware datetime을 naive UTC로 변환한다."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class MetricsService:
    """
    CloudWatch 메트릭 수집 및 저장 서비스

    장애 주입 전(before), 중(during), 후(after) 단계별로
    대상 리소스의 CloudWatch 메트릭을 수집하여 DB에 저장한다.
    """

    # 메트릭 수집 기본 기간 (초)
    DEFAULT_PERIOD_SECONDS: int = 60
    # 메트릭 조회 시간 범위 (분)
    DEFAULT_LOOKBACK_MINUTES: int = 5

    def __init__(self, db: AsyncSession):
        self.db = db
        self._settings = get_settings()
        self._cloudwatch_client = None

    @property
    def cloudwatch_client(self):
        """boto3 CloudWatch 클라이언트를 지연 초기화한다."""
        if self._cloudwatch_client is None:
            self._cloudwatch_client = boto3.client(
                "cloudwatch",
                region_name=self._settings.aws_default_region,
            )
        return self._cloudwatch_client

    # ============================================================
    # 리소스 유형 판별
    # ============================================================
    def _detect_resource_type(self, resource_id: str) -> str:
        """
        리소스 ID로 AWS 리소스 유형을 판별한다.

        Args:
            resource_id: AWS 리소스 ID (예: i-0abc123, mydb-instance)

        Returns:
            리소스 유형 문자열 ("ec2" 또는 "rds")
        """
        if resource_id.startswith("i-"):
            return "ec2"
        return "rds"

    # ============================================================
    # 메트릭 정의 조회
    # ============================================================
    def _get_metric_definitions(
        self, resource_id: str
    ) -> list[tuple[str, str, str, str]]:
        """
        리소스 유형에 따른 수집 대상 메트릭 정의를 반환한다.

        Args:
            resource_id: AWS 리소스 ID

        Returns:
            (네임스페이스, 메트릭명, 차원키, 단위) 튜플 리스트
        """
        resource_type = self._detect_resource_type(resource_id)
        if resource_type == "ec2":
            return EC2_METRICS
        return RDS_METRICS

    # ============================================================
    # CloudWatch get_metric_data 호출
    # ============================================================
    def _build_metric_queries(
        self,
        resource_id: str,
        metric_definitions: list[tuple[str, str, str, str]],
    ) -> list[dict]:
        """
        CloudWatch get_metric_data API용 쿼리 목록을 생성한다.

        Args:
            resource_id: AWS 리소스 ID
            metric_definitions: 메트릭 정의 리스트

        Returns:
            MetricDataQueries 리스트
        """
        queries = []
        for idx, (namespace, metric_name, dimension_key, unit) in enumerate(
            metric_definitions
        ):
            query_id = f"m{idx}"
            queries.append(
                {
                    "Id": query_id,
                    "MetricStat": {
                        "Metric": {
                            "Namespace": namespace,
                            "MetricName": metric_name,
                            "Dimensions": [
                                {
                                    "Name": dimension_key,
                                    "Value": resource_id,
                                }
                            ],
                        },
                        "Period": self.DEFAULT_PERIOD_SECONDS,
                        "Stat": "Average",
                        "Unit": unit,
                    },
                    "ReturnData": True,
                }
            )
        return queries


    def _fetch_metric_data(
        self,
        resource_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """
        CloudWatch에서 지정 기간의 메트릭 데이터를 조회한다.

        Args:
            resource_id: AWS 리소스 ID
            start_time: 조회 시작 시각
            end_time: 조회 종료 시각

        Returns:
            메트릭 결과 리스트. 각 항목은 다음 키를 포함:
            - metric_name: 메트릭 이름
            - value: 메트릭 값 (평균)
            - unit: 단위
            - timestamp: 수집 시각

        Raises:
            ClientError: CloudWatch API 호출 실패 시
        """
        metric_definitions = self._get_metric_definitions(resource_id)
        queries = self._build_metric_queries(resource_id, metric_definitions)

        try:
            response = self.cloudwatch_client.get_metric_data(
                MetricDataQueries=queries,
                StartTime=start_time,
                EndTime=end_time,
            )
        except ClientError as e:
            logger.error(
                f"CloudWatch 메트릭 조회 실패: resource_id={resource_id}, error={e}"
            )
            raise

        # 응답 파싱: 각 메트릭의 최신 데이터 포인트 추출
        results = []
        metric_data_results = response.get("MetricDataResults", [])

        for idx, metric_result in enumerate(metric_data_results):
            if idx >= len(metric_definitions):
                break

            _, metric_name, _, unit = metric_definitions[idx]
            timestamps = metric_result.get("Timestamps", [])
            values = metric_result.get("Values", [])

            if timestamps and values:
                # 가장 최근 데이터 포인트 사용
                latest_idx = 0
                latest_ts = timestamps[0]
                for i, ts in enumerate(timestamps):
                    if ts > latest_ts:
                        latest_ts = ts
                        latest_idx = i

                results.append(
                    {
                        "metric_name": metric_name,
                        "value": values[latest_idx],
                        "unit": unit,
                        "timestamp": _to_naive_utc(timestamps[latest_idx]),
                    }
                )
            else:
                # 데이터 포인트가 없으면 0.0으로 기록
                logger.warning(
                    f"메트릭 데이터 없음: resource_id={resource_id}, "
                    f"metric_name={metric_name}"
                )
                results.append(
                    {
                        "metric_name": metric_name,
                        "value": 0.0,
                        "unit": unit,
                        "timestamp": _to_naive_utc(end_time),
                    }
                )

        return results

    # ============================================================
    # 메트릭 수집 및 DB 저장
    # ============================================================
    async def collect_and_store_metrics(
        self,
        experiment_id: str,
        resource_id: str,
        phase: Phase,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[ResourceMetric]:
        """
        CloudWatch 메트릭을 수집하여 resource_metrics 테이블에 저장한다.

        Args:
            experiment_id: 실험 ID (UUID 문자열)
            resource_id: 대상 AWS 리소스 ID
            phase: 수집 단계 ("before", "during", "after")
            start_time: 조회 시작 시각 (기본: 현재 - 5분)
            end_time: 조회 종료 시각 (기본: 현재)

        Returns:
            저장된 ResourceMetric 레코드 리스트
        """
        now = datetime.utcnow()
        if end_time is None:
            end_time = now
        if start_time is None:
            start_time = end_time - timedelta(
                minutes=self.DEFAULT_LOOKBACK_MINUTES
            )
        start_time = _to_naive_utc(start_time)
        end_time = _to_naive_utc(end_time)
        if start_time >= end_time:
            start_time = end_time - timedelta(seconds=self.DEFAULT_PERIOD_SECONDS)

        exp_uuid = uuid.UUID(experiment_id)

        logger.info(
            f"메트릭 수집 시작: experiment_id={experiment_id}, "
            f"resource_id={resource_id}, phase={phase}, "
            f"start_time={start_time}, end_time={end_time}"
        )

        try:
            metric_data = self._fetch_metric_data(
                resource_id=resource_id,
                start_time=start_time,
                end_time=end_time,
            )
        except ClientError as e:
            logger.error(
                f"메트릭 수집 실패: experiment_id={experiment_id}, "
                f"resource_id={resource_id}, phase={phase}, error={e}"
            )
            return []

        # DB에 메트릭 레코드 저장
        saved_metrics: list[ResourceMetric] = []
        for data in metric_data:
            metric = ResourceMetric(
                experiment_id=exp_uuid,
                metric_name=data["metric_name"],
                resource_id=resource_id,
                value=data["value"],
                unit=data["unit"],
                phase=phase,
                collected_at=data["timestamp"],
            )
            self.db.add(metric)
            saved_metrics.append(metric)

        await self.db.commit()

        # 저장된 레코드 refresh
        for metric in saved_metrics:
            await self.db.refresh(metric)

        logger.info(
            f"메트릭 수집 완료: experiment_id={experiment_id}, "
            f"phase={phase}, count={len(saved_metrics)}"
        )

        return saved_metrics

    # ============================================================
    # 장애 주입 전 메트릭 수집 (편의 메서드)
    # ============================================================
    async def collect_before_metrics(
        self,
        experiment_id: str,
        resource_id: str,
    ) -> list[ResourceMetric]:
        """
        장애 주입 전(before) 메트릭을 수집한다.

        현재 시점 기준 최근 5분간의 메트릭을 수집하여 저장한다.

        Args:
            experiment_id: 실험 ID
            resource_id: 대상 리소스 ID

        Returns:
            저장된 ResourceMetric 레코드 리스트
        """
        return await self.collect_and_store_metrics(
            experiment_id=experiment_id,
            resource_id=resource_id,
            phase="before",
        )

    # ============================================================
    # 장애 주입 중 메트릭 수집 (편의 메서드)
    # ============================================================
    async def collect_during_metrics(
        self,
        experiment_id: str,
        resource_id: str,
        chaos_started_at: datetime,
    ) -> list[ResourceMetric]:
        """
        장애 주입 중(during) 메트릭을 수집한다.

        장애 시작 시각부터 현재까지의 메트릭을 수집하여 저장한다.

        Args:
            experiment_id: 실험 ID
            resource_id: 대상 리소스 ID
            chaos_started_at: 장애 주입 시작 시각

        Returns:
            저장된 ResourceMetric 레코드 리스트
        """
        return await self.collect_and_store_metrics(
            experiment_id=experiment_id,
            resource_id=resource_id,
            phase="during",
            start_time=chaos_started_at,
        )

    # ============================================================
    # 장애 주입 후 메트릭 수집 (편의 메서드)
    # ============================================================
    async def collect_after_metrics(
        self,
        experiment_id: str,
        resource_id: str,
        chaos_ended_at: datetime,
    ) -> list[ResourceMetric]:
        """
        장애 주입 후(after) 메트릭을 수집한다.

        롤백 직후 최근 구간의 메트릭을 수집하여 저장한다.

        콜백은 롤백 직후 도착하므로 chaos_ended_at부터 현재까지 조회하면
        CloudWatch 조회 구간이 0초가 될 수 있다. 따라서 after는 현재 시점
        기준 최근 DEFAULT_LOOKBACK_MINUTES 구간을 스냅샷으로 저장한다.

        Args:
            experiment_id: 실험 ID
            resource_id: 대상 리소스 ID
            chaos_ended_at: 장애 주입 종료 시각

        Returns:
            저장된 ResourceMetric 레코드 리스트
        """
        return await self.collect_and_store_metrics(
            experiment_id=experiment_id,
            resource_id=resource_id,
            phase="after",
        )
