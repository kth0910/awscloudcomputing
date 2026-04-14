// ============================================================
// TypeScript 타입 정의
// Core Engine API 응답 스키마에 대응하는 프론트엔드 타입
// ============================================================

/** 장애 유형 */
export type FaultType = 'ec2_stop' | 'sg_port_block' | 'rds_delay';

/** 실험 상태 */
export type ExperimentStatus = 'created' | 'running' | 'completed' | 'failed' | 'cancelled';

/** 페르소나 유형 */
export type PersonaType = 'impatient' | 'meticulous' | 'casual';

/** 추론 상태 */
export type InferenceStatus = 'completed' | 'inference_failed';

/** 메트릭 수집 단계 */
export type MetricPhase = 'before' | 'during' | 'after';

/** 장애 주입 결과 상태 */
export type ResultStatus = 'success' | 'failed' | 'rollback_completed';

// ============================================================
// 요청 타입
// ============================================================

/** 실험 생성 요청 */
export interface ExperimentCreate {
  name: string;
  target_resource: string;
  fault_type: FaultType;
  duration_seconds?: number;
  persona_types?: PersonaType[];
}

/** 실험 실행 설정 */
export interface RunConfig {
  persona_types?: string[];
}

// ============================================================
// 응답 타입
// ============================================================

/** 실험 응답 */
export interface Experiment {
  id: string;
  name: string;
  target_resource: string;
  fault_type: FaultType;
  status: ExperimentStatus;
  duration_seconds: number;
  persona_types_json: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
}

/** 장애 주입 결과 응답 */
export interface ExperimentResult {
  id: string;
  experiment_id: string;
  status: ResultStatus;
  chaos_started_at: string | null;
  chaos_ended_at: string | null;
  fault_type: string;
  target_resource: string;
  error_detail: string | null;
  original_state: Record<string, unknown> | null;
  rollback_state: Record<string, unknown> | null;
  created_at: string;
}

/** AI 페르소나 추론 결과 응답 */
export interface PersonaInference {
  id: string;
  experiment_id: string;
  persona_type: PersonaType;
  emotion: string | null;
  churn_probability: number | null;
  frustration_index: number | null;
  reasoning: string | null;
  api_latency_ms: number | null;
  status: InferenceStatus;
  failure_reason: string | null;
  created_at: string;
}

/** 실험 상세 응답 (결과 + 추론 포함) */
export interface ExperimentDetail extends Experiment {
  results: ExperimentResult[];
  persona_inferences: PersonaInference[];
}

/** 리소스 메트릭 응답 */
export interface ResourceMetric {
  id: string;
  experiment_id: string;
  metric_name: string;
  resource_id: string;
  value: number;
  unit: string;
  phase: MetricPhase;
  collected_at: string;
  created_at: string;
}

/** 페르소나 정보 */
export interface Persona {
  type: PersonaType;
  name: string;
  traits: string;
  tech_level: string;
  patience_level: string;
  expected_response_time: string;
}

// ============================================================
// 유틸리티
// ============================================================

/** 장애 유형 한국어 라벨 */
export const FAULT_TYPE_LABELS: Record<FaultType, string> = {
  ec2_stop: 'EC2 인스턴스 중지',
  sg_port_block: 'Security Group 포트 차단',
  rds_delay: 'RDS 연결 지연',
};

/** 실험 상태 한국어 라벨 */
export const STATUS_LABELS: Record<ExperimentStatus, string> = {
  created: '생성됨',
  running: '실행 중',
  completed: '완료',
  failed: '실패',
  cancelled: '취소됨',
};

/** 페르소나 유형 한국어 라벨 */
export const PERSONA_LABELS: Record<PersonaType, string> = {
  impatient: '성격 급한 유저',
  meticulous: '꼼꼼한 유저',
  casual: '일반 유저',
};
