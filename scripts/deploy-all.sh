#!/bin/bash
# ============================================================
# 전체 시스템 배포 스크립트
# CDK 인프라 배포 → Core Engine 배포 → Dashboard 배포 → 헬스 체크
#
# 사용법:
#   ./scripts/deploy-all.sh [--region <region>] [--skip-infra] [--skip-core] [--skip-dashboard]
#
# 배포 순서:
#   1. CDK 전체 인프라 배포 (NetworkStack → SecurityStack → ... → FrontendStack)
#   2. CDK 출력값 조회 (ALB DNS, S3 버킷, CloudFront Distribution ID 등)
#   3. Core Engine Docker 이미지 업데이트 (deploy-core-engine.sh)
#   4. Dashboard 빌드 및 S3 배포 (deploy-dashboard.sh)
#   5. 헬스 체크 확인
# ============================================================
set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 프로젝트 루트 디렉토리
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ============================================================
# 인자 파싱
# ============================================================
REGION="us-east-1"
SKIP_INFRA=false
SKIP_CORE=false
SKIP_DASHBOARD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --region) REGION="$2"; shift 2 ;;
        --skip-infra) SKIP_INFRA=true; shift ;;
        --skip-core) SKIP_CORE=true; shift ;;
        --skip-dashboard) SKIP_DASHBOARD=true; shift ;;
        --help)
            echo "사용법: $0 [옵션]"
            echo ""
            echo "옵션:"
            echo "  --region <region>    AWS 리전 (기본값: us-east-1)"
            echo "  --skip-infra         CDK 인프라 배포 건너뛰기"
            echo "  --skip-core          Core Engine 배포 건너뛰기"
            echo "  --skip-dashboard     Dashboard 배포 건너뛰기"
            echo "  --help               도움말 표시"
            exit 0
            ;;
        *) echo -e "${RED}[오류]${NC} 알 수 없는 인자: $1"; exit 1 ;;
    esac
done

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN} AI-Powered Chaos Twin 전체 배포${NC}"
echo -e "${CYAN} 리전: ${REGION}${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# 배포 시작 시간 기록
DEPLOY_START=$(date +%s)

# ============================================================
# 1단계: CDK 전체 인프라 배포
# 스택 의존성 순서: Network → Security → Secrets → Database
#                   → Compute → Lambda → Frontend
# ============================================================
if [ "$SKIP_INFRA" = false ]; then
    echo -e "${GREEN}[1/5]${NC} CDK 전체 인프라를 배포합니다..."
    echo -e "${YELLOW}[정보]${NC} 스택 배포 순서: Network → Security → Secrets → Database → Compute → Lambda → Frontend"

    cd "${PROJECT_ROOT}/infra"

    # CDK 부트스트랩 (최초 1회만 필요, 이미 완료된 경우 건너뜀)
    echo -e "${YELLOW}[정보]${NC} CDK 부트스트랩을 확인합니다..."
    npx cdk bootstrap "aws://$(aws sts get-caller-identity --query Account --output text)/${REGION}" \
        --region "$REGION" 2>/dev/null || true

    # 전체 스택 배포 (--require-approval never: 수동 승인 없이 자동 배포)
    npx cdk deploy --all \
        --require-approval never \
        --region "$REGION" \
        --outputs-file "${PROJECT_ROOT}/cdk-outputs.json"

    echo -e "${GREEN}[정보]${NC} CDK 인프라 배포 완료."
    cd "$PROJECT_ROOT"
else
    echo -e "${YELLOW}[1/5]${NC} CDK 인프라 배포를 건너뜁니다 (--skip-infra)."
fi

# ============================================================
# 2단계: CDK 출력값 조회
# 각 스택의 CloudFormation 출력값을 조회하여 변수에 저장
# ============================================================
echo -e "${GREEN}[2/5]${NC} CDK 출력값을 조회합니다..."

# ComputeStack 출력값
ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name ComputeStack \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-AlbDnsName'].OutputValue" \
    --output text 2>/dev/null || echo "")

ALB_URL=$(aws cloudformation describe-stacks \
    --stack-name ComputeStack \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-AlbUrl'].OutputValue" \
    --output text 2>/dev/null || echo "")

INSTANCE_ID=$(aws cloudformation describe-stacks \
    --stack-name ComputeStack \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-CoreEngineInstanceId'].OutputValue" \
    --output text 2>/dev/null || echo "")

# DatabaseStack 출력값
RDS_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name DatabaseStack \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-RdsEndpoint'].OutputValue" \
    --output text 2>/dev/null || echo "")

# LambdaStack 출력값
LAMBDA_ARN=$(aws cloudformation describe-stacks \
    --stack-name LambdaStack \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-ChaosInjectorLambdaArn'].OutputValue" \
    --output text 2>/dev/null || echo "")

# FrontendStack 출력값
DASHBOARD_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name FrontendStack \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-DashboardBucketName'].OutputValue" \
    --output text 2>/dev/null || echo "")

DASHBOARD_URL=$(aws cloudformation describe-stacks \
    --stack-name FrontendStack \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-DashboardUrl'].OutputValue" \
    --output text 2>/dev/null || echo "")

# 출력값 요약
echo -e "${CYAN}--- CDK 출력값 요약 ---${NC}"
echo -e "  ALB DNS:          ${ALB_DNS:-미확인}"
echo -e "  ALB URL:          ${ALB_URL:-미확인}"
echo -e "  EC2 Instance ID:  ${INSTANCE_ID:-미확인}"
echo -e "  RDS Endpoint:     ${RDS_ENDPOINT:-미확인}"
echo -e "  Lambda ARN:       ${LAMBDA_ARN:-미확인}"
echo -e "  Dashboard Bucket: ${DASHBOARD_BUCKET:-미확인}"
echo -e "  Dashboard URL:    ${DASHBOARD_URL:-미확인}"
echo ""

# ============================================================
# 3단계: Core Engine 배포
# EC2 인스턴스에 최신 Docker 이미지 배포
# ============================================================
if [ "$SKIP_CORE" = false ]; then
    echo -e "${GREEN}[3/5]${NC} Core Engine을 배포합니다..."

    if [ -n "$INSTANCE_ID" ] && [ "$INSTANCE_ID" != "None" ]; then
        bash "${SCRIPT_DIR}/deploy-core-engine.sh" \
            --instance-id "$INSTANCE_ID" \
            --region "$REGION"
    else
        echo -e "${YELLOW}[경고]${NC} EC2 인스턴스 ID를 찾을 수 없어 Core Engine 배포를 건너뜁니다."
        echo "  EC2 User Data가 초기 배포를 처리합니다."
    fi
else
    echo -e "${YELLOW}[3/5]${NC} Core Engine 배포를 건너뜁니다 (--skip-core)."
fi

# ============================================================
# 4단계: Dashboard 빌드 및 S3 배포
# Next.js 정적 빌드 → S3 업로드 → CloudFront 캐시 무효화
# ============================================================
if [ "$SKIP_DASHBOARD" = false ]; then
    echo -e "${GREEN}[4/5]${NC} Dashboard를 빌드하고 배포합니다..."

    bash "${SCRIPT_DIR}/deploy-dashboard.sh" --region "$REGION"
else
    echo -e "${YELLOW}[4/5]${NC} Dashboard 배포를 건너뜁니다 (--skip-dashboard)."
fi

# ============================================================
# 5단계: 헬스 체크 확인
# ALB를 통해 Core Engine /health 엔드포인트 확인
# ============================================================
echo -e "${GREEN}[5/5]${NC} 헬스 체크를 수행합니다..."

if [ -n "$ALB_DNS" ] && [ "$ALB_DNS" != "None" ]; then
    HEALTH_URL="http://${ALB_DNS}/health"
    echo -e "${YELLOW}[정보]${NC} 헬스 체크 URL: ${HEALTH_URL}"

    # 최대 5회 재시도 (EC2 부팅 및 컨테이너 시작 대기)
    MAX_RETRIES=5
    RETRY_INTERVAL=15

    for i in $(seq 1 $MAX_RETRIES); do
        echo -e "${YELLOW}[정보]${NC} 헬스 체크 시도 ${i}/${MAX_RETRIES}..."

        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            --connect-timeout 10 \
            --max-time 15 \
            "$HEALTH_URL" 2>/dev/null || echo "000")

        if [ "$HTTP_STATUS" = "200" ]; then
            HEALTH_RESPONSE=$(curl -s --max-time 10 "$HEALTH_URL" 2>/dev/null || echo "{}")
            echo -e "${GREEN}[성공]${NC} 헬스 체크 통과! (HTTP ${HTTP_STATUS})"
            echo -e "  응답: ${HEALTH_RESPONSE}"
            break
        else
            echo -e "${YELLOW}[정보]${NC} HTTP ${HTTP_STATUS} — ${RETRY_INTERVAL}초 후 재시도..."
            if [ "$i" -lt "$MAX_RETRIES" ]; then
                sleep "$RETRY_INTERVAL"
            fi
        fi
    done

    if [ "$HTTP_STATUS" != "200" ]; then
        echo -e "${RED}[경고]${NC} 헬스 체크 실패. Core Engine이 아직 시작 중일 수 있습니다."
        echo "  수동으로 확인하세요: curl ${HEALTH_URL}"
    fi
else
    echo -e "${YELLOW}[경고]${NC} ALB DNS를 찾을 수 없어 헬스 체크를 건너뜁니다."
fi

# ============================================================
# 배포 결과 요약
# ============================================================
DEPLOY_END=$(date +%s)
DEPLOY_DURATION=$((DEPLOY_END - DEPLOY_START))

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN} 배포 완료! (소요 시간: ${DEPLOY_DURATION}초)${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "  ${GREEN}Core Engine API:${NC}  ${ALB_URL:-미확인}"
echo -e "  ${GREEN}Dashboard:${NC}        ${DASHBOARD_URL:-미확인}"
echo -e "  ${GREEN}RDS Endpoint:${NC}     ${RDS_ENDPOINT:-미확인}"
echo -e "  ${GREEN}Lambda ARN:${NC}       ${LAMBDA_ARN:-미확인}"
echo ""
echo -e "${YELLOW}[참고]${NC} CloudFront 캐시 무효화는 수 분이 소요될 수 있습니다."
echo -e "${YELLOW}[참고]${NC} EC2 초기 부팅 시 Docker 이미지 빌드에 2~3분이 소요됩니다."
echo ""
