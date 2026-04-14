"""
커스텀 예외 클래스 정의

Core Engine에서 사용하는 도메인 특화 예외를 정의한다.
"""


class ExperimentNotFoundError(Exception):
    """실험을 찾을 수 없을 때 발생하는 예외"""

    def __init__(self, experiment_id: str):
        self.experiment_id = experiment_id
        super().__init__(f"실험을 찾을 수 없습니다: {experiment_id}")


class ChaosServiceError(Exception):
    """Chaos 서비스 관련 예외"""
    pass


class AIReasoningError(Exception):
    """AI 추론 엔진 관련 예외"""
    pass
