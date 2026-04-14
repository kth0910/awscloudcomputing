# AI-Powered Chaos Twin

AWS 인프라에 의도적 장애를 주입하고, Gemini AI 기반 가상 사용자 페르소나를 통해 시스템 복원력과 UX 임계점을 테스트하는 카오스 엔지니어링 플랫폼입니다.

## 한 줄 소개

> AWS 리소스에 장애를 주입한 뒤, AI가 "성격 급한 유저", "꼼꼼한 유저", "일반 유저" 관점에서 사용자 심리 상태(이탈 확률, 불만 지수, 감정)를 추론하여 UX 임계점을 정량적으로 분석하는 도구입니다.

## 아키텍처

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CloudFront (HTTPS)                            │
│   /static/* → S3          /api/* → ALB                               │
└──────┬───────────────────────┬───────────────────────────────────────┘
       │                       │
       ▼                       ▼
┌──────────────┐    ┌─────────────────────┐
│  S3 Bucket   │ -> │  ALB (Public Subnet) │
│  Next.js     │    └──────────┬──────────┘
│  Dashboard   │               │ :8000
└──────────────┘               ▼
                    ┌─────────────────────┐
                    │  EC2 (Private Sub.)  │
                    │  FastAPI Core Engine │
                    └──┬───────┬───────┬──┘
                       │       │       │
            Lambda     │       │       │  Secrets
            invoke     │       │       │  Manager
                       ▼       ▼       ▼
              ┌─────────┐ ┌────────┐ ┌──────────┐
              │ Lambda   │ │  RDS   │ │ Gemini   │
              │ Chaos    │ │ Postgre│ │ AI API   │
              │ Injector │ │ SQL    │ │ (Google) │
              └─────────┘ └────────┘ └──────────┘
              (Private Sub.) (DB Sub.)  (External)
```

## 사용한 AWS 리소스

| 리소스 | 용도 | 스펙 |
|--------|------|------|
| **VPC** | 네트워크 격리 (10.0.0.0/16) | Public/Private/DB 서브넷 × 2 AZ |
| **EC2** | FastAPI Core Engine 서버 | t2.micro (Private Subnet) |
| **ALB** | API 트래픽 로드밸런싱 | Public Subnet, HTTP:80 → EC2:8000 |
| **RDS PostgreSQL** | 실험 데이터 저장 | db.t3.micro, 단일 AZ |
| **Lambda** | Chaos Injector (장애 주입) | Python 3.12, 256MB, 15분 타임아웃 |
| **S3** | Next.js 대시보드 정적 호스팅 | CloudFront OAI 연동 |
| **CloudFront** | HTTPS 서빙 + API 프록시 | S3 오리진 + ALB 오리진 (/api/*) |
| **Secrets Manager** | Gemini API Key, RDS 비밀번호 관리 | 런타임 조회 |
| **NAT Gateway** | Private Subnet 인터넷 아웃바운드 | 단일 (us-east-1a, 비용 최적화) |
| **IAM** | 최소 권한 역할 3개 | EC2 Role, Lambda Role, CloudFront Role |

## 외부 서비스

| 서비스 | 용도 |
|--------|------|
| **Google Gemini API** (gemini-2.0-flash) | AI 페르소나 심리 상태 추론 |

## 프로젝트 구조

```
├── infra/                  # AWS CDK (TypeScript) — 인프라 코드
│   ├── bin/chaos-twin.ts   # CDK 앱 진입점 (7개 스택)
│   └── lib/stacks/         # NetworkStack, SecurityStack, DatabaseStack,
│                           # ComputeStack, LambdaStack, FrontendStack, SecretsStack
├── core-engine/            # FastAPI (Python) — Core Engine API 서버
│   ├── app/
│   │   ├── routers/        # 실험 CRUD, 결과 조회, 콜백 수신
│   │   ├── services/       # 비즈니스 로직 (실험, AI 추론, 메트릭, 시크릿)
│   │   ├── models/         # SQLAlchemy ORM 모델 (4개 테이블)
│   │   └── schemas/        # Pydantic 요청/응답 스키마
│   └── Dockerfile
├── chaos-injector/         # Lambda (Python) — 장애 주입 함수
│   ├── handler.py          # Lambda 핸들러
│   ├── scenarios/          # EC2 Stop, SG 수정, RDS 지연 시나리오
│   └── rollback.py         # 자동 롤백 매니저
├── dashboard/              # Next.js (TypeScript) — 웹 대시보드
│   ├── app/                # 페이지 (대시보드, 실험 관리, 결과, 메트릭, 페르소나)
│   ├── components/         # UI 컴포넌트 (차트, 폼, 뱃지)
│   └── lib/                # API 클라이언트, 타입 정의
└── scripts/                # 배포 스크립트
    ├── deploy-all.sh       # 전체 배포 (CDK + Core Engine + Dashboard)
    ├── deploy-core-engine.sh
    └── deploy-dashboard.sh
```

## 사전 요구사항

- **AWS CLI** v2 (프로필 설정 완료)
- **AWS CDK CLI** (`npm install -g aws-cdk`)
- **Node.js** 18+
- **Python** 3.11+
- **Docker** (EC2 User Data에서 사용)
- **Gemini API Key** ([Google AI Studio](https://aistudio.google.com/)에서 발급)

## 실행 방법

### 1. Gemini API Key 등록

```bash
aws secretsmanager create-secret \
  --name chaos-twin/gemini-api-key \
  --secret-string '{"api_key": "YOUR_GEMINI_API_KEY"}' \
  --region us-east-1
```

### 2. CDK 의존성 설치

```bash
cd infra && npm install
```

### 3. 전체 배포 (CDK 인프라 + Dashboard)

```bash
bash scripts/deploy-all.sh
```

또는 단계별로:

```bash
# CDK 부트스트랩 (최초 1회)
cd infra && npx cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1

# 전체 인프라 배포 (약 15분 소요)
npx cdk deploy --all --require-approval never

# 대시보드 빌드 및 S3 배포
cd ../dashboard && npm install && npm run build
aws s3 sync out/ s3://chaos-twin-dashboard-YOUR_ACCOUNT_ID --delete --region us-east-1
```

### 4. 접속

배포 완료 후 CloudFormation 출력값에서 URL을 확인합니다:

```bash
# 대시보드 URL
aws cloudformation describe-stacks --stack-name FrontendStack \
  --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-DashboardUrl'].OutputValue" --output text

# API 헬스 체크
aws cloudformation describe-stacks --stack-name ComputeStack \
  --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-AlbUrl'].OutputValue" --output text
```

## 테스트 방법

### 대시보드에서 실험 실행

1. 대시보드 접속 → **+ 새 실험 생성** 클릭
2. 실험 이름, 대상 리소스 ID, 장애 유형, 페르소나 선택
3. **실험 실행** 버튼 클릭
4. 실시간 상태 업데이트 확인 (5초 폴링)
5. 완료 후 **AI 추론 결과 보기**에서 페르소나별 비교 차트 확인

### API로 직접 테스트

```bash
# 대시보드 URL (CloudFront)
DASHBOARD_URL="https://YOUR_CLOUDFRONT_DOMAIN.cloudfront.net"

# 실험 생성
curl -X POST "$DASHBOARD_URL/api/experiments" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "EC2 중지 테스트",
    "target_resource": "i-YOUR_INSTANCE_ID",
    "fault_type": "ec2_stop",
    "duration_seconds": 60,
    "persona_types": ["impatient", "meticulous", "casual"]
  }'

# 실험 목록 조회
curl "$DASHBOARD_URL/api/experiments"

# 헬스 체크
curl "$DASHBOARD_URL/api/health"
```

### 샘플 데이터

| 항목 | 값 |
|------|-----|
| 장애 유형 | `ec2_stop` (EC2 중지), `sg_port_block` (포트 차단), `rds_delay` (DB 지연) |
| 페르소나 | `impatient` (성격 급한 유저), `meticulous` (꼼꼼한 유저), `casual` (일반 유저) |
| 대상 리소스 예시 | EC2: `i-0ff614591a2fd5605`, SG: `sg-07bb3bf249ffa0c8b` |
| 장애 지속 시간 | 60~300초 (기본 300초) |

### 주의사항

- EC2 Stop 실험은 **Core Engine 자체를 중지**시킬 수 있으므로, 다른 EC2 인스턴스를 대상으로 테스트하세요
- 장애 주입 후 자동 롤백이 실행되지만, 수동 확인을 권장합니다
- Lambda 동시 실행 쿼터가 10개이므로 동시에 많은 실험을 실행하면 대기열에 쌓입니다
- RDS 생성에 5~10분, EC2 Docker 빌드에 2~3분 소요됩니다

## 리소스 정리

```bash
# 전체 인프라 삭제
cd infra && npx cdk destroy --all

# Secrets Manager 시크릿 삭제
aws secretsmanager delete-secret --secret-id chaos-twin/gemini-api-key --force-delete-without-recovery --region us-east-1
```

## 배포된 환경 정보

| 항목 | 값 |
|------|-----|
| 리전 | us-east-1 |
| 대시보드 | https://d33q8g22n2hung.cloudfront.net |
| API (ALB) | http://chaos-twin-alb-2049673832.us-east-1.elb.amazonaws.com |
| EC2 인스턴스 | i-0ff614591a2fd5605 |
| RDS 엔드포인트 | chaos-twin-db.cmvo0uu8g0p5.us-east-1.rds.amazonaws.com |
| Lambda 함수 | chaos-twin-chaos-injector |
| S3 버킷 | chaos-twin-dashboard-510197248070 |
