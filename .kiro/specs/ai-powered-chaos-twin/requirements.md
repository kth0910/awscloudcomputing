# 요구사항 문서

## 소개

AI-Powered Chaos Twin은 AWS 인프라에 의도적 장애를 주입하고, Gemini API 기반의 AI 페르소나를 통해 시스템 복원력과 사용자 경험(UX) 임계점을 테스트하는 카오스 엔지니어링 도구이다. 3-Tier + Serverless 아키텍처를 기반으로 하며, FastAPI 코어 엔진, Lambda 기반 Chaos Injector, Gemini AI 추론 엔진, Next.js 대시보드로 구성된다.

## 용어 사전

- **Core_Engine**: Python FastAPI 기반의 핵심 애플리케이션 서버. Amazon EC2(Private Subnet)에서 실행되며, Chaos 실험 관리, AI 페르소나 오케스트레이션, API 제공을 담당한다.
- **Chaos_Injector**: AWS Lambda(Python 3.12) 기반의 장애 주입 함수. EC2 Stop/Start, Security Group 수정, RDS 연결 차단 등의 장애 시나리오를 실행한다.
- **AI_Reasoning_Engine**: Gemini 3.1 Flash Lite Preview 모델을 활용하여 장애 상황에서의 사용자 심리 상태를 추론하는 모듈이다.
- **Dashboard**: Next.js(App Router) + Tailwind CSS + Shadcn UI 기반의 프론트엔드 대시보드. S3 + CloudFront에 호스팅된다.
- **Chaos_Experiment**: 특정 AWS 리소스에 대해 정의된 장애 시나리오의 단일 실행 단위이다.
- **AI_Persona**: Gemini API를 통해 시뮬레이션되는 가상 사용자 유형. 각 페르소나는 고유한 성격 특성과 반응 패턴을 가진다.
- **UX_Threshold**: 장애 상황에서 사용자 경험이 허용 불가능한 수준으로 저하되는 임계점이다.
- **Experiment_Result**: Chaos 실험의 실행 결과와 AI 추론 결과를 포함하는 데이터 레코드이다.
- **VPC_Network**: Public Subnet(ALB, NAT Gateway)과 Private Subnet(EC2, RDS)으로 분리된 AWS 네트워크 환경이다.
- **Secret_Store**: AWS Secrets Manager 또는 Parameter Store를 통해 Gemini API Key 및 AWS 자격 증명을 안전하게 관리하는 저장소이다.

## 요구사항

### 요구사항 1: VPC 네트워크 인프라 구성

**사용자 스토리:** 인프라 엔지니어로서, Public/Private Subnet이 분리된 VPC 환경을 구성하고 싶다. 이를 통해 보안이 강화된 네트워크에서 Chaos 실험을 안전하게 수행할 수 있다.

#### 인수 조건

1. THE VPC_Network SHALL Public Subnet과 Private Subnet을 최소 2개의 가용 영역(us-east-1a, us-east-1b)에 걸쳐 생성한다.
2. THE VPC_Network SHALL Public Subnet에 ALB와 NAT Gateway를 배치한다.
3. THE VPC_Network SHALL Private Subnet에 Core_Engine EC2 인스턴스와 RDS PostgreSQL 인스턴스를 배치한다.
4. THE VPC_Network SHALL Private Subnet의 인터넷 아웃바운드 트래픽을 NAT Gateway를 통해서만 허용한다.
5. THE VPC_Network SHALL ALB에서 Core_Engine EC2로의 인바운드 트래픽을 포트 8000(FastAPI)으로만 제한하는 Security Group 규칙을 적용한다.
6. THE VPC_Network SHALL Core_Engine EC2에서 RDS로의 인바운드 트래픽을 포트 5432(PostgreSQL)로만 제한하는 Security Group 규칙을 적용한다.
7. THE VPC_Network SHALL Chaos_Injector Lambda가 Private Subnet 내 리소스에 접근할 수 있도록 VPC 연결을 구성한다.

### 요구사항 2: Chaos Injector Lambda 함수

**사용자 스토리:** 카오스 엔지니어로서, Lambda 기반의 장애 주입 함수를 통해 다양한 AWS 리소스에 의도적 장애를 주입하고 싶다. 이를 통해 시스템 복원력을 체계적으로 테스트할 수 있다.

#### 인수 조건

1. WHEN Core_Engine이 Chaos 실험 시작을 요청하면, THE Chaos_Injector SHALL 비동기적으로 지정된 장애 시나리오를 실행한다.
2. THE Chaos_Injector SHALL 실제 운영 환경에서 발생 가능한 현실적인 장애 시나리오만 지원한다. 지원 범위는 다음과 같다: EC2 인스턴스 Stop/Start, Security Group 규칙 수정을 통한 특정 포트 차단, RDS 연결 지연 시뮬레이션.
3. THE Chaos_Injector SHALL 극단적 장애(리소스 영구 삭제, 전체 VPC 차단, 다중 AZ 동시 장애 등)를 실행하지 않으며, 모든 장애는 단일 리소스 단위로 제한한다.
4. THE Chaos_Injector SHALL 각 장애 시나리오에 최대 지속 시간(기본 5분)을 설정하여, 지속 시간 초과 시 자동으로 원래 상태로 롤백한다.
5. WHILE Chaos_Injector의 동시 실행 수가 10개에 도달한 상태에서, THE Chaos_Injector SHALL 새로운 실행 요청을 대기열에 추가하고 순차적으로 처리한다.
6. WHEN Chaos 실험이 완료되면, THE Chaos_Injector SHALL 실험 결과(시작 시간, 종료 시간, 대상 리소스, 장애 유형, 성공 여부)를 Core_Engine에 콜백으로 전달한다.
7. IF Chaos_Injector 실행 중 예외가 발생하면, THEN THE Chaos_Injector SHALL 오류 상세 정보를 CloudWatch Logs에 기록하고 Core_Engine에 실패 상태를 전달한다.
8. THE Chaos_Injector SHALL 각 장애 시나리오에 대해 자동 롤백 메커니즘을 구현하여, 실험 종료 후 원래 상태로 복원한다.

### 요구사항 3: Gemini AI 추론 엔진 연동

**사용자 스토리:** 제품 관리자로서, 장애 상황에서 다양한 사용자 유형의 심리 상태를 AI로 추론하고 싶다. 이를 통해 UX 임계점을 정량적으로 파악할 수 있다.

#### 인수 조건

1. WHEN Chaos 실험이 실행되면, THE AI_Reasoning_Engine SHALL Gemini 3.1 Flash Lite Preview 모델에 사용자 심리 상태 추론 요청을 비동기적으로 전송한다.
2. THE AI_Reasoning_Engine SHALL Gemini API 응답을 JSON 형식으로 파싱하여 구조화된 데이터로 변환한다.
3. THE AI_Reasoning_Engine SHALL 추론 결과를 RDS PostgreSQL에 다음 스키마로 저장한다: 실험 ID, 페르소나 유형, 감정 상태, 이탈 확률, 불만 지수, 추론 근거, 타임스탬프.
4. THE AI_Reasoning_Engine SHALL Gemini API Key를 Secret_Store에서 런타임에 조회하여 사용한다.
5. IF Gemini API 호출이 실패하면, THEN THE AI_Reasoning_Engine SHALL 최대 3회까지 지수 백오프(1초, 2초, 4초) 방식으로 재시도한다.
6. IF 재시도 후에도 Gemini API 호출이 실패하면, THEN THE AI_Reasoning_Engine SHALL 실패 사유를 기록하고 해당 추론 결과를 "추론 불가" 상태로 저장한다.
7. WHEN Gemini API 응답을 수신하면, THE AI_Reasoning_Engine SHALL 응답 지연 시간을 측정하여 Experiment_Result에 포함한다.

### 요구사항 4: AI 페르소나 시스템

**사용자 스토리:** UX 연구원으로서, 최소 3가지 유형의 가상 사용자 페르소나를 통해 장애 상황에서의 다양한 사용자 반응을 시뮬레이션하고 싶다. 이를 통해 사용자 유형별 UX 임계점을 비교 분석할 수 있다.

#### 인수 조건

1. THE AI_Persona SHALL 최소 3가지 페르소나 유형을 제공한다: "성격 급한 유저"(Impatient), "꼼꼼한 유저"(Meticulous), "일반 유저"(Casual).
2. THE AI_Persona SHALL 각 페르소나에 대해 고유한 프롬프트 템플릿을 정의한다. 프롬프트 템플릿은 성격 특성, 기술 숙련도, 인내심 수준, 기대 응답 시간을 포함한다.
3. WHEN Chaos 실험이 실행되면, THE AI_Persona SHALL 선택된 페르소나의 프롬프트 템플릿을 장애 컨텍스트와 결합하여 Gemini API 요청을 구성한다.
4. THE AI_Persona SHALL 각 페르소나의 추론 결과에 이탈 확률(0.0~1.0), 불만 지수(1~10), 감정 상태(문자열)를 포함한다.
5. WHEN 동일한 Chaos 실험에 대해 복수의 페르소나가 실행되면, THE AI_Persona SHALL 각 페르소나의 결과를 독립적으로 저장하고 비교 가능한 형태로 제공한다.

### 요구사항 5: Core Engine API 서버

**사용자 스토리:** 개발자로서, FastAPI 기반의 관리형 API 서버를 통해 Chaos 실험을 생성, 실행, 모니터링하고 싶다. 이를 통해 체계적인 카오스 엔지니어링 워크플로우를 운영할 수 있다.

#### 인수 조건

1. THE Core_Engine SHALL Chaos 실험 생성, 조회, 실행, 삭제를 위한 RESTful API 엔드포인트를 제공한다.
2. THE Core_Engine SHALL Chaos 실험 실행 시 Chaos_Injector Lambda를 비동기적으로 호출한다.
3. THE Core_Engine SHALL Chaos 실험 실행 후 AI_Reasoning_Engine을 통해 각 AI_Persona의 심리 상태 추론을 트리거한다.
4. THE Core_Engine SHALL 실험 결과를 RDS PostgreSQL에 저장하고 조회 API를 제공한다.
5. WHEN 실험 실행 요청을 수신하면, THE Core_Engine SHALL 요청 파라미터(대상 리소스, 장애 유형, 페르소나 목록)를 검증한 후 실행한다.
6. IF 요청 파라미터 검증에 실패하면, THEN THE Core_Engine SHALL HTTP 400 응답과 함께 구체적인 검증 실패 사유를 반환한다.
7. THE Core_Engine SHALL ALB를 통해서만 외부 트래픽을 수신하며, Private Subnet 내에서 실행된다.

### 요구사항 6: 프론트엔드 대시보드

**사용자 스토리:** 운영자로서, 웹 대시보드를 통해 Chaos 실험을 관리하고 결과를 시각적으로 확인하고 싶다. 이를 통해 시스템 복원력 상태를 직관적으로 파악할 수 있다.

#### 인수 조건

1. THE Dashboard SHALL Chaos 실험 목록, 상세 정보, 실행 이력을 표시하는 화면을 제공한다.
2. THE Dashboard SHALL 새로운 Chaos 실험을 생성하고 실행할 수 있는 폼 인터페이스를 제공한다.
3. THE Dashboard SHALL AI 페르소나별 추론 결과(이탈 확률, 불만 지수, 감정 상태)를 비교 차트로 시각화한다.
4. THE Dashboard SHALL S3에 정적 자산으로 배포되고 CloudFront를 통해 서비스된다.
5. WHEN Chaos 실험이 진행 중일 때, THE Dashboard SHALL 실험 상태를 실시간으로 업데이트하여 표시한다.
6. THE Dashboard SHALL Core_Engine API와 ALB를 통해 통신한다.

### 요구사항 7: 보안 및 비밀 관리

**사용자 스토리:** 보안 엔지니어로서, 모든 민감한 자격 증명을 안전하게 관리하고 싶다. 이를 통해 보안 사고를 예방할 수 있다.

#### 인수 조건

1. THE Secret_Store SHALL Gemini API Key를 AWS Secrets Manager 또는 Parameter Store(SecureString)에 저장한다.
2. THE Secret_Store SHALL AWS 자격 증명을 IAM Role 기반으로 관리하며, 하드코딩된 자격 증명 사용을 금지한다.
3. THE Core_Engine SHALL Secret_Store에서 런타임에 비밀 값을 조회하며, 환경 변수에 평문으로 저장하지 않는다.
4. THE Chaos_Injector SHALL 장애 주입에 필요한 최소 권한만 부여받은 IAM Role을 사용한다.
5. IF Secret_Store에서 비밀 값 조회에 실패하면, THEN THE Core_Engine SHALL 서비스 시작을 중단하고 오류를 로깅한다.

### 요구사항 8: 인프라 코드 및 비용 최적화

**사용자 스토리:** DevOps 엔지니어로서, IaC(Infrastructure as Code)로 전체 인프라를 관리하고 비용을 최적화하고 싶다. 이를 통해 재현 가능하고 비용 효율적인 환경을 유지할 수 있다.

#### 인수 조건

1. THE VPC_Network SHALL AWS CDK(TypeScript) 또는 Terraform을 사용하여 전체 인프라를 코드로 정의한다.
2. THE Core_Engine SHALL EC2 인스턴스 유형으로 t2.micro 이상을 사용하며, AWS Free Tier 적용 가능한 리소스를 우선 선택한다.
3. THE VPC_Network SHALL NAT Gateway 비용을 최소화하기 위해 단일 NAT Gateway 구성을 기본으로 한다.
4. THE Chaos_Injector SHALL Lambda 함수의 메모리를 128MB~256MB 범위로 설정하여 비용을 최적화한다.
5. THE VPC_Network SHALL RDS 인스턴스로 db.t3.micro 또는 db.t4g.micro를 사용하며, Multi-AZ 배포를 비활성화하여 비용을 절감한다.

### 요구사항 9: 모니터링 및 상태 추적

**사용자 스토리:** SRE 엔지니어로서, Chaos 실험 중 AWS 리소스의 상태 변화를 실시간으로 모니터링하고 싶다. 이를 통해 장애 주입의 영향을 정확히 측정할 수 있다.

#### 인수 조건

1. WHEN Chaos 실험이 실행되면, THE Core_Engine SHALL 대상 리소스의 CloudWatch 메트릭(CPU 사용률, 네트워크 트래픽, DB 연결 수)을 수집한다.
2. THE Core_Engine SHALL 장애 주입 전후의 메트릭 변화를 Experiment_Result에 기록한다.
3. WHEN 장애 주입으로 인해 대상 리소스의 상태가 변경되면, THE Core_Engine SHALL 상태 변경 이벤트를 타임라인 형태로 기록한다.
4. THE Dashboard SHALL 실험별 메트릭 변화를 시계열 차트로 시각화한다.
5. IF 장애 주입 후 리소스가 지정된 시간(기본 5분) 내에 정상 상태로 복구되지 않으면, THEN THE Core_Engine SHALL 경고 알림을 생성하고 자동 롤백을 트리거한다.

### 요구사항 10: 데이터 스키마 및 저장

**사용자 스토리:** 데이터 엔지니어로서, Chaos 실험 결과와 AI 추론 데이터를 체계적으로 저장하고 싶다. 이를 통해 실험 데이터를 분석하고 이력을 관리할 수 있다.

#### 인수 조건

1. THE Core_Engine SHALL RDS PostgreSQL에 다음 테이블을 생성한다: experiments(실험 정보), experiment_results(실험 결과), persona_inferences(AI 추론 결과), resource_metrics(리소스 메트릭).
2. THE Core_Engine SHALL experiments 테이블에 실험 ID, 실험 이름, 대상 리소스, 장애 유형, 상태, 생성 시간, 실행 시간, 종료 시간을 저장한다.
3. THE Core_Engine SHALL persona_inferences 테이블에 실험 ID, 페르소나 유형, 감정 상태, 이탈 확률, 불만 지수, 추론 근거, Gemini 응답 지연 시간, 타임스탬프를 저장한다.
4. THE Core_Engine SHALL 모든 테이블에 적절한 인덱스를 생성하여 조회 성능을 최적화한다.
5. WHEN 실험 데이터가 저장되면, THE Core_Engine SHALL 데이터 무결성을 보장하기 위해 외래 키 제약 조건을 적용한다.

### 요구사항 11: 배포 파이프라인

**사용자 스토리:** DevOps 엔지니어로서, 전체 시스템을 AWS 환경에 자동으로 배포하고 싶다. 이를 통해 일관된 환경을 빠르게 프로비저닝하고 업데이트할 수 있다.

#### 인수 조건

1. THE VPC_Network SHALL IaC(CDK 또는 Terraform)를 통해 단일 명령으로 전체 인프라(VPC, Subnet, ALB, NAT Gateway, EC2, RDS, Lambda, S3, CloudFront)를 프로비저닝한다.
2. THE Core_Engine SHALL EC2 인스턴스에 FastAPI 애플리케이션을 자동으로 배포하는 스크립트(User Data 또는 CodeDeploy)를 포함한다.
3. THE Chaos_Injector SHALL Lambda 함수 코드를 IaC 배포 과정에서 자동으로 패키징하고 배포한다.
4. THE Dashboard SHALL Next.js 빌드 결과물을 S3에 업로드하고 CloudFront 캐시를 무효화하는 배포 스크립트를 포함한다.
5. WHEN 배포가 완료되면, THE Core_Engine SHALL 헬스 체크 엔드포인트(/health)를 통해 서비스 정상 동작을 확인한다.
6. IF 배포 중 오류가 발생하면, THEN THE VPC_Network SHALL CloudFormation 롤백을 통해 이전 안정 상태로 복원한다.
7. THE VPC_Network SHALL 배포 시 RDS 데이터베이스 마이그레이션(테이블 생성, 스키마 업데이트)을 자동으로 실행한다.
