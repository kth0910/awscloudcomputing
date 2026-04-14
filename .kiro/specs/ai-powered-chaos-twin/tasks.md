# 구현 계획: AI-Powered Chaos Twin

## 개요

AWS 인프라에 의도적 장애를 주입하고, Gemini AI 기반 페르소나를 통해 UX 임계점을 추론하는 카오스 엔지니어링 플랫폼을 구현한다. CDK 인프라 스택 → Core Engine(FastAPI) → Chaos Injector(Lambda) → AI Reasoning Engine → Dashboard(Next.js) 순서로 점진적으로 구축하며, 각 단계에서 테스트를 통해 기능을 검증한다.

## Tasks

- [x] 1. CDK 프로젝트 초기화 및 네트워크/보안 스택 구현
  - [x] 1.1 CDK 프로젝트 구조 생성 및 의존성 설정
    - `infra/` 디렉토리에 CDK TypeScript 프로젝트 초기화 (`cdk.json`, `tsconfig.json`, `package.json`)
    - `bin/chaos-twin.ts` 앱 진입점 생성, 모든 스택 인스턴스화 및 의존성 정의
    - _Requirements: 8.1, 11.1_

  - [x] 1.2 NetworkStack 구현
    - VPC (10.0.0.0/16), Public Subnet A/B, Private Subnet A/B, DB Subnet A/B 생성
    - Internet Gateway, NAT Gateway (us-east-1a 단일), 라우팅 테이블 구성
    - `lib/stacks/network-stack.ts` 파일 생성
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 8.3_

  - [x] 1.3 SecurityStack 구현
    - Security Group 4개 생성: sg-alb, sg-ec2, sg-rds, sg-lambda (설계 문서의 인바운드/아웃바운드 규칙 적용)
    - IAM Role 3개 생성: ChaosEngineEC2Role, ChaosInjectorLambdaRole, DashboardCloudFrontRole (최소 권한 원칙)
    - `lib/stacks/security-stack.ts` 파일 생성
    - _Requirements: 1.5, 1.6, 7.2, 7.4_

  - [ ]* 1.4 NetworkStack, SecurityStack IaC 스냅샷 테스트 작성
    - VPC CIDR, Subnet 구성, Security Group 규칙, IAM Role 정책 스냅샷 검증
    - `infra/test/snapshot/` 디렉토리에 테스트 파일 생성
    - _Requirements: 1.1~1.7, 7.4_

- [x] 2. 데이터베이스, 시크릿, 컴퓨트 스택 구현
  - [x] 2.1 SecretsStack 구현
    - Secrets Manager에 `chaos-twin/gemini-api-key` 시크릿 리소스 정의
    - `lib/stacks/secrets-stack.ts` 파일 생성
    - _Requirements: 7.1_

  - [x] 2.2 DatabaseStack 구현
    - RDS PostgreSQL (db.t3.micro, 단일 AZ, Multi-AZ 비활성화) 인스턴스 생성
    - DB Subnet Group, 파라미터 그룹 구성
    - `lib/stacks/database-stack.ts` 파일 생성
    - _Requirements: 1.3, 8.5, 10.1_

  - [x] 2.3 ComputeStack 구현
    - EC2 t2.micro 인스턴스 (Private Subnet A), ALB + Target Group 구성
    - User Data 스크립트로 FastAPI 자동 배포 설정
    - `lib/stacks/compute-stack.ts` 및 `lib/constructs/fastapi-ec2.ts` 파일 생성
    - _Requirements: 5.7, 8.2, 11.2_

  - [x] 2.4 LambdaStack 구현
    - Chaos Injector Lambda 함수 (Python 3.12, 256MB, 900초 타임아웃, Reserved Concurrency 10)
    - VPC 연결 (Private Subnet A/B), 코드 자동 패키징
    - `lib/stacks/lambda-stack.ts` 및 `lib/constructs/chaos-lambda.ts` 파일 생성
    - _Requirements: 1.7, 2.5, 8.4, 11.3_

  - [x] 2.5 FrontendStack 구현
    - S3 버킷 + CloudFront Distribution + OAI 구성
    - `lib/stacks/frontend-stack.ts` 파일 생성
    - _Requirements: 6.4, 11.4_

  - [ ]* 2.6 Database, Compute, Lambda, Frontend, Secrets 스택 스냅샷 테스트 작성
    - RDS 인스턴스 타입, Lambda 메모리/타임아웃/VPC 연결, EC2 인스턴스 타입 스냅샷 검증
    - _Requirements: 8.2, 8.4, 8.5_

- [x] 3. 체크포인트 - CDK 인프라 스택 검증
  - 모든 CDK 스냅샷 테스트 통과 확인, 사용자에게 질문이 있으면 문의하세요.

- [x] 4. Core Engine 프로젝트 구조 및 데이터 모델 구현
  - [x] 4.1 FastAPI 프로젝트 구조 생성
    - `core-engine/` 디렉토리 구조 생성 (app/, routers/, services/, models/, schemas/, db/)
    - `main.py` FastAPI 앱 진입점, CORS 미들웨어, 글로벌 예외 핸들러 구현
    - `config.py` 설정 관리 (환경 변수, Secrets Manager 연동)
    - `requirements.txt` 의존성 정의 (fastapi, uvicorn, sqlalchemy, asyncpg, boto3, httpx, alembic)
    - _Requirements: 5.1, 7.3_

  - [x] 4.2 데이터베이스 연결 및 ORM 모델 구현
    - `db/database.py` SQLAlchemy async 엔진, 세션 팩토리, 연결 풀 구성
    - `models/experiment.py` Experiment ORM 모델 (experiments 테이블)
    - `models/persona_inference.py` PersonaInference ORM 모델 (persona_inferences 테이블)
    - `models/resource_metric.py` ResourceMetric ORM 모델 (resource_metrics 테이블)
    - experiment_results 테이블 ORM 모델 추가
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 4.3 Pydantic 요청/응답 스키마 구현
    - `schemas/experiment.py` ExperimentCreate, RunConfig, ExperimentDetail, ExperimentResult 스키마
    - `schemas/persona.py` PersonaInferenceResult 스키마
    - `schemas/callback.py` ChaosCallback 스키마
    - fault_type, status, persona_type 열거형 검증 포함
    - _Requirements: 5.5, 5.6_

  - [x] 4.4 Alembic 마이그레이션 설정
    - Alembic 초기화 및 DDL 기반 초기 마이그레이션 스크립트 생성
    - 4개 테이블 (experiments, experiment_results, persona_inferences, resource_metrics) + 인덱스 생성
    - _Requirements: 10.1, 10.4, 11.7_

  - [ ]* 4.5 Property 테스트: 실험 파라미터 검증 및 에러 응답
    - **Property 9: 실험 파라미터 검증 및 에러 응답**
    - Hypothesis로 임의 실험 파라미터 생성, 무효한 파라미터에 대해 항상 검증 실패 사유가 포함된 에러 반환 검증
    - **Validates: Requirements 5.5, 5.6**

- [x] 5. Core Engine 실험 관리 API 구현
  - [x] 5.1 실험 CRUD 라우터 구현
    - `routers/experiments.py` GET /api/experiments, POST /api/experiments, GET /api/experiments/{id}, DELETE /api/experiments/{id} 엔드포인트
    - `services/experiment_service.py` 실험 생성, 조회, 삭제 비즈니스 로직
    - _Requirements: 5.1, 5.4_

  - [x] 5.2 실험 실행 엔드포인트 구현
    - POST /api/experiments/{id}/run 엔드포인트 (202 Accepted 반환)
    - 파라미터 검증 (target_resource, fault_type, persona_types) 로직
    - 실험 상태를 "running"으로 업데이트
    - _Requirements: 5.2, 5.5, 5.6_

  - [x] 5.3 결과 및 메트릭 조회 라우터 구현
    - `routers/results.py` GET /api/experiments/{id}/results 엔드포인트
    - `routers/metrics.py` GET /api/experiments/{id}/metrics 엔드포인트
    - `routers/personas.py` GET /api/personas 엔드포인트
    - `routers/health.py` GET /health 헬스 체크 엔드포인트
    - _Requirements: 5.1, 5.4, 11.5_

  - [x] 5.4 Lambda 콜백 수신 라우터 구현
    - `routers/internal.py` POST /api/internal/callback 엔드포인트
    - 콜백 데이터 검증 및 experiment_results 테이블 저장
    - 콜백 수신 후 AI 추론 트리거 연동
    - _Requirements: 2.6, 2.7_

  - [ ]* 5.5 Core Engine API 단위 테스트 작성
    - 실험 CRUD 엔드포인트 테스트, 파라미터 검증 실패 시 400 응답 테스트
    - 헬스 체크 엔드포인트 테스트
    - _Requirements: 5.1, 5.5, 5.6, 11.5_

- [x] 6. 체크포인트 - Core Engine API 검증
  - 모든 테스트 통과 확인, 사용자에게 질문이 있으면 문의하세요.

- [x] 7. Chaos Injector Lambda 구현
  - [x] 7.1 Lambda 핸들러 및 시나리오 기본 구조 구현
    - `chaos-injector/handler.py` Lambda 핸들러 진입점 (이벤트 파싱, 시나리오 디스패치)
    - `chaos-injector/scenarios/base.py` BaseChaosScenario 추상 클래스 (inject, rollback 메서드)
    - `chaos-injector/callback.py` Core Engine 콜백 전송 모듈
    - `chaos-injector/requirements.txt` 의존성 정의
    - _Requirements: 2.1, 2.6_

  - [x] 7.2 EC2 Stop 장애 시나리오 구현
    - `chaos-injector/scenarios/ec2_stop.py` EC2StopScenario 클래스
    - inject: EC2 인스턴스 Stop + 원래 상태(running) 기록
    - rollback: EC2 인스턴스 Start
    - _Requirements: 2.2, 2.8_

  - [x] 7.3 Security Group 수정 장애 시나리오 구현
    - `chaos-injector/scenarios/sg_modify.py` SGModifyScenario 클래스
    - inject: 특정 포트 인바운드 규칙 제거 + 원래 규칙 기록
    - rollback: 원래 Security Group 규칙 복원
    - _Requirements: 2.2, 2.8_

  - [x] 7.4 RDS 연결 지연 시뮬레이션 시나리오 구현
    - `chaos-injector/scenarios/rds_delay.py` RDSDelayScenario 클래스
    - inject: RDS 연결 지연 시뮬레이션 + 원래 상태 기록
    - rollback: 원래 상태 복원
    - _Requirements: 2.2, 2.8_

  - [x] 7.5 자동 롤백 매니저 구현
    - `chaos-injector/rollback.py` RollbackManager 클래스
    - duration_seconds 초과 시 자동 롤백 트리거
    - 롤백 완료 후 Core Engine에 `rollback_completed` 콜백 전송
    - _Requirements: 2.4, 2.8, 9.5_

  - [ ]* 7.6 Property 테스트: 장애 요청 안전 검증
    - **Property 1: 장애 요청 안전 검증**
    - Hypothesis로 임의 fault_type 문자열 및 다중 리소스 목록 생성, 허용 목록 외 요청이 항상 거부되는지 검증
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 7.7 Property 테스트: 예외 시 에러 콜백 생성
    - **Property 2: 예외 시 에러 콜백 생성**
    - Hypothesis로 임의 Exception 유형 생성, 콜백 페이로드에 항상 `status: "failed"`와 비어있지 않은 `error_detail` 포함 검증
    - **Validates: Requirements 2.7**

  - [ ]* 7.8 Property 테스트: 롤백 상태 복원 라운드트립
    - **Property 3: 롤백 상태 복원 라운드트립**
    - Hypothesis로 임의 리소스 상태 dict 생성, inject → rollback 라운드트립 시 올바른 AWS API 호출 생성 검증
    - **Validates: Requirements 2.8**

- [x] 8. Core Engine - Chaos Service 연동 구현
  - [x] 8.1 ChaosService Lambda 비동기 호출 구현
    - `services/chaos_service.py` invoke_chaos_injector 메서드 (boto3 Lambda InvocationType=Event)
    - handle_callback 메서드 (콜백 처리 + 결과 저장 + AI 추론 트리거)
    - _Requirements: 2.1, 5.2_

  - [x] 8.2 SecretService Secrets Manager 연동 구현
    - `services/secret_service.py` Gemini API Key 조회 로직
    - 서비스 시작 시 시크릿 조회 실패 시 시작 중단 로직
    - _Requirements: 3.4, 7.3, 7.5_

- [x] 9. AI Reasoning Engine 구현
  - [x] 9.1 Gemini API 호출 및 재시도 로직 구현
    - `services/ai_reasoning_service.py` AIReasoningService 클래스
    - infer_persona_reaction 메서드: Gemini API 비동기 호출, 지수 백오프 재시도 (1s, 2s, 4s, 최대 3회)
    - 응답 JSON 파싱 (emotion, churn_probability, frustration_index, reasoning)
    - API 지연 시간(api_latency_ms) 측정 및 결과 포함
    - 3회 실패 시 `inference_failed` 상태 저장
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 3.7_

  - [x] 9.2 페르소나 프롬프트 구성 서비스 구현
    - `services/persona_service.py` PersonaService 클래스
    - PERSONA_TEMPLATES 딕셔너리 (impatient, meticulous, casual) 정의
    - build_prompt 메서드: 페르소나 템플릿 + 장애 컨텍스트 결합
    - 다중 페르소나 순차 실행 및 독립 저장 로직
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [x] 9.3 AI 추론 결과 저장 로직 구현
    - persona_inferences 테이블에 각 페르소나별 추론 결과 독립 저장
    - 실험 완료 후 상태를 "completed"로 업데이트
    - _Requirements: 3.3, 4.5_

  - [ ]* 9.4 Property 테스트: Gemini 응답 파싱 및 범위 검증
    - **Property 4: Gemini 응답 파싱 및 범위 검증**
    - Hypothesis로 유효한 JSON 구조 생성, 파싱 결과의 각 필드가 지정 범위 내에 있는지 검증
    - **Validates: Requirements 3.2, 4.4**

  - [ ]* 9.5 Property 테스트: 지수 백오프 재시도 간격
    - **Property 5: 지수 백오프 재시도 간격**
    - Hypothesis로 1~3 범위 정수 생성, n번째 재시도 대기 시간이 `BACKOFF_BASE * 2^(n-1)` 공식을 따르는지 검증
    - **Validates: Requirements 3.5**

  - [ ]* 9.6 Property 테스트: API 지연 시간 측정 양수성
    - **Property 6: API 지연 시간 측정 양수성**
    - Hypothesis로 임의 응답 지연 모킹, 측정된 api_latency_ms가 항상 0보다 큰지 검증
    - **Validates: Requirements 3.7**

  - [ ]* 9.7 Property 테스트: 프롬프트 구성 완전성
    - **Property 7: 프롬프트 구성 완전성**
    - Hypothesis로 임의 페르소나 유형 + 장애 컨텍스트 생성, 프롬프트에 모든 필수 필드(성격 특성, 기술 숙련도, 인내심 수준, 기대 응답 시간, 서비스명, 장애 유형, 지속 시간) 포함 검증
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 9.8 Property 테스트: 다중 페르소나 독립 저장
    - **Property 8: 다중 페르소나 독립 저장**
    - Hypothesis로 임의 페르소나 목록 생성, 저장된 레코드 수가 페르소나 수와 동일하고 각 레코드가 고유한 persona_type을 가지는지 검증
    - **Validates: Requirements 4.5**

- [x] 10. 체크포인트 - Core Engine + Chaos Injector + AI Reasoning 검증
  - 모든 테스트 통과 확인, 사용자에게 질문이 있으면 문의하세요.

- [x] 11. 메트릭 수집 서비스 구현
  - [x] 11.1 CloudWatch 메트릭 수집 서비스 구현
    - `services/metrics_service.py` MetricsService 클래스
    - 장애 주입 전/중/후 CloudWatch 메트릭 수집 (CPU 사용률, 네트워크 트래픽, DB 연결 수)
    - resource_metrics 테이블에 phase(before, during, after) 구분하여 저장
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 11.2 Property 테스트: 메트릭 phase 구분 정확성
    - **Property 10: 메트릭 phase 구분 정확성**
    - Hypothesis로 임의 메트릭 값 + 수집 시점 생성, phase 값이 수집 시점에 대응하는 올바른 값(before, during, after)을 가지는지 검증
    - **Validates: Requirements 9.2**

- [x] 12. Next.js 대시보드 구현
  - [x] 12.1 Next.js 프로젝트 초기화 및 기본 레이아웃 구현
    - `dashboard/` 디렉토리에 Next.js App Router 프로젝트 생성 (Tailwind CSS, Shadcn UI)
    - `next.config.js` output: 'export' 정적 빌드 설정
    - `app/layout.tsx` 루트 레이아웃 (Sidebar + Header)
    - `lib/api-client.ts` Core Engine API 클라이언트 (ALB 엔드포인트 통신)
    - `lib/types.ts` TypeScript 타입 정의
    - _Requirements: 6.4, 6.6_

  - [x] 12.2 실험 관리 페이지 구현
    - `app/page.tsx` 대시보드 홈 (실험 요약)
    - `app/experiments/page.tsx` 실험 목록 페이지
    - `app/experiments/new/page.tsx` 실험 생성 폼 페이지
    - `components/experiment-form.tsx` 실험 생성/편집 폼 컴포넌트
    - `components/experiment-status-badge.tsx` 실험 상태 뱃지 컴포넌트
    - _Requirements: 6.1, 6.2_

  - [x] 12.3 실험 상세 및 결과 페이지 구현
    - `app/experiments/[id]/page.tsx` 실험 상세 정보 페이지
    - `app/experiments/[id]/results/page.tsx` 실험 결과 + AI 추론 비교 페이지
    - `components/persona-comparison-chart.tsx` 페르소나별 비교 차트 컴포넌트
    - 폴링 기반(5초 간격) 실시간 상태 업데이트 구현
    - `components/realtime-status-indicator.tsx` 실시간 상태 표시기 컴포넌트
    - _Requirements: 6.1, 6.3, 6.5_

  - [x] 12.4 메트릭 시각화 및 페르소나 관리 페이지 구현
    - `app/metrics/page.tsx` 메트릭 시계열 차트 페이지
    - `components/metric-timeline-chart.tsx` 메트릭 시계열 차트 컴포넌트
    - `app/personas/page.tsx` 페르소나 관리 페이지
    - _Requirements: 6.3, 9.4_

  - [ ]* 12.5 대시보드 컴포넌트 테스트 작성
    - Jest + React Testing Library로 주요 컴포넌트 렌더링 테스트
    - API 클라이언트 모킹 테스트, 폴링 기반 실시간 업데이트 테스트
    - _Requirements: 6.1, 6.3, 6.5, 6.6_

- [x] 13. 체크포인트 - 대시보드 검증
  - 모든 테스트 통과 확인, 사용자에게 질문이 있으면 문의하세요.

- [x] 14. 전체 통합 및 배포 스크립트 구성
  - [x] 14.1 Core Engine Dockerfile 및 EC2 배포 스크립트 작성
    - `core-engine/Dockerfile` FastAPI 컨테이너 이미지 정의
    - EC2 User Data 스크립트에서 Docker 설치 + 컨테이너 실행 자동화
    - _Requirements: 11.2_

  - [x] 14.2 대시보드 빌드 및 S3 배포 스크립트 작성
    - Next.js 정적 빌드 (`npm run build`) + S3 업로드 + CloudFront 캐시 무효화 스크립트
    - _Requirements: 11.4_

  - [x] 14.3 전체 컴포넌트 연동 및 워크플로우 통합
    - Core Engine → Lambda 비동기 호출 → 콜백 수신 → AI 추론 → 결과 저장 전체 흐름 연결
    - Dashboard → ALB → Core Engine API 통신 연결
    - CDK 스택 간 출력값(ALB DNS, RDS 엔드포인트, Lambda ARN 등) 참조 연결
    - _Requirements: 2.1, 5.2, 5.3, 6.6, 11.1_

  - [ ]* 14.4 통합 테스트 작성
    - Core Engine API CRUD 엔드포인트 통합 테스트
    - Lambda 비동기 호출 트리거 통합 테스트
    - RDS 데이터 저장/조회 라운드트립 통합 테스트
    - _Requirements: 5.1, 5.2, 5.4_

- [x] 15. 최종 체크포인트 - 전체 시스템 검증
  - 모든 테스트 통과 확인, 사용자에게 질문이 있으면 문의하세요.

## Notes

- `*` 표시된 태스크는 선택 사항이며, 빠른 MVP를 위해 건너뛸 수 있습니다.
- 각 태스크는 특정 요구사항을 참조하여 추적 가능합니다.
- 체크포인트에서 점진적 검증을 수행합니다.
- Property 테스트는 설계 문서의 10개 정확성 속성을 Hypothesis 라이브러리로 검증합니다.
- 단위 테스트는 특정 예제와 엣지 케이스를 검증합니다.
- CDK 인프라는 TypeScript, Core Engine과 Chaos Injector는 Python, Dashboard는 TypeScript(Next.js)로 구현합니다.
