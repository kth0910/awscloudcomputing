"""
장애 시나리오 추상 기본 클래스

모든 장애 시나리오는 이 클래스를 상속하여 inject/rollback 메서드를 구현해야 한다.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseChaosScenario(ABC):
    """장애 시나리오 추상 기본 클래스"""

    @abstractmethod
    def inject(self, target_resource: str, config: dict) -> dict:
        """
        장애 주입. 롤백에 필요한 원래 상태를 반환한다.

        Parameters:
            target_resource: 대상 AWS 리소스 ID
            config: 장애 주입 설정 (시나리오별 추가 파라미터)

        Returns:
            원래 상태 딕셔너리 (롤백 시 사용)
        """
        pass

    @abstractmethod
    def rollback(self, target_resource: str, original_state: dict) -> None:
        """
        원래 상태로 롤백한다.

        Parameters:
            target_resource: 대상 AWS 리소스 ID
            original_state: inject()에서 반환된 원래 상태 딕셔너리
        """
        pass
