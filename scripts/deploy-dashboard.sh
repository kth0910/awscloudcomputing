#!/bin/bash
# ============================================================
# 대시보드 빌드 및 S3 배포 스크립트
# Next.js 정적 빌드 → S3 업로드 → CloudFront 캐시 무효화
#
# 사용법:
#   ./scripts/deploy-dashboard.sh [--bucket <name>] [--distribution-id <id>]
#
# CDK 출력값에서 버킷 이름과 Distribution ID를 자동으로 가져오거나,
# 인자로 직접 지정할 수 있습니다.
# ============================================================
set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 프로젝트 루트 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DASHBOARD_DIR="${PROJECT_ROOT}/dashboard"

echo -e "${GREEN}[대시보드 배포]${NC} 시작..."

# ============================================================
# 인자 파싱
# ============================================================
BUCKET_NAME=""
DISTRIBUTION_ID=""
REGION="us-east-1"
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket) BUCKET_NAME="$2"; shift 2 ;;
        --distribution-id) DISTRIBUTION_ID="$2"; shift 2 ;;
        --region) REGION="$2"; shift 2 ;;
        --skip-build) SKIP_BUILD=true; shift ;;
        *) echo -e "${RED}[오류]${NC} 알 수 없는 인자: $1"; exit 1 ;;
    esac
done

# ============================================================
# CDK 출력값에서 S3 버킷 이름 조회 (인자 미지정 시)
# ============================================================
if [ -z "$BUCKET_NAME" ]; then
    echo -e "${YELLOW}[정보]${NC} CDK 출력값에서 S3 버킷 이름을 조회합니다..."
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name FrontendStack \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-DashboardBucketName'].OutputValue" \
        --output text 2>/dev/null || true)

    if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" = "None" ]; then
        echo -e "${RED}[오류]${NC} S3 버킷 이름을 찾을 수 없습니다."
        echo "  --bucket 옵션으로 직접 지정하거나, CDK 배포를 먼저 실행하세요."
        exit 1
    fi
fi

# ============================================================
# CDK 출력값에서 CloudFront Distribution ID 조회 (인자 미지정 시)
# CloudFront Distribution ID는 CDK 출력에 직접 없으므로,
# Distribution 도메인 이름으로 ID를 조회합니다.
# ============================================================
if [ -z "$DISTRIBUTION_ID" ]; then
    echo -e "${YELLOW}[정보]${NC} CloudFront Distribution ID를 조회합니다..."

    # FrontendStack에서 도메인 이름 가져오기
    CF_DOMAIN=$(aws cloudformation describe-stacks \
        --stack-name FrontendStack \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-DashboardDistributionDomainName'].OutputValue" \
        --output text 2>/dev/null || true)

    if [ -n "$CF_DOMAIN" ] && [ "$CF_DOMAIN" != "None" ]; then
        # 도메인 이름으로 Distribution ID 조회
        DISTRIBUTION_ID=$(aws cloudfront list-distributions \
            --query "DistributionList.Items[?DomainName=='${CF_DOMAIN}'].Id" \
            --output text 2>/dev/null || true)
    fi

    if [ -z "$DISTRIBUTION_ID" ] || [ "$DISTRIBUTION_ID" = "None" ]; then
        echo -e "${YELLOW}[경고]${NC} CloudFront Distribution ID를 찾을 수 없습니다."
        echo "  캐시 무효화를 건너뜁니다. --distribution-id 옵션으로 직접 지정할 수 있습니다."
    fi
fi

echo -e "${GREEN}[정보]${NC} S3 버킷: ${BUCKET_NAME}"
echo -e "${GREEN}[정보]${NC} CloudFront Distribution: ${DISTRIBUTION_ID:-미지정}"

# ============================================================
# 1단계: Next.js 정적 빌드
# ============================================================
if [ "$SKIP_BUILD" = false ]; then
    echo -e "${GREEN}[1/3]${NC} Next.js 정적 빌드를 실행합니다..."

    cd "$DASHBOARD_DIR"

    # 의존성 설치 (node_modules가 없는 경우)
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}[정보]${NC} npm 의존성을 설치합니다..."
        npm ci
    fi

    # ALB URL을 환경 변수로 설정 (빌드 시 포함)
    ALB_URL=$(aws cloudformation describe-stacks \
        --stack-name ComputeStack \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-AlbUrl'].OutputValue" \
        --output text 2>/dev/null || echo "")

    if [ -n "$ALB_URL" ] && [ "$ALB_URL" != "None" ]; then
        export NEXT_PUBLIC_API_URL="$ALB_URL"
        echo -e "${GREEN}[정보]${NC} API URL: ${ALB_URL}"
    else
        echo -e "${YELLOW}[경고]${NC} ALB URL을 찾을 수 없습니다. NEXT_PUBLIC_API_URL이 설정되지 않습니다."
    fi

    # Next.js 빌드 (output: 'export' → out/ 디렉토리에 정적 파일 생성)
    npm run build

    echo -e "${GREEN}[정보]${NC} 빌드 완료. 출력 디렉토리: ${DASHBOARD_DIR}/out/"
else
    echo -e "${YELLOW}[정보]${NC} 빌드를 건너뜁니다 (--skip-build)."
fi

# ============================================================
# 2단계: S3에 정적 파일 업로드
# ============================================================
echo -e "${GREEN}[2/3]${NC} S3에 정적 파일을 업로드합니다..."

BUILD_DIR="${DASHBOARD_DIR}/out"

if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}[오류]${NC} 빌드 출력 디렉토리가 없습니다: ${BUILD_DIR}"
    echo "  먼저 빌드를 실행하세요: cd dashboard && npm run build"
    exit 1
fi

# S3 동기화 (삭제 포함 — 이전 파일 정리)
aws s3 sync "$BUILD_DIR" "s3://${BUCKET_NAME}" \
    --delete \
    --region "$REGION" \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "*.html"

# HTML 파일은 캐시 시간을 짧게 설정 (SPA 라우팅 지원)
aws s3 sync "$BUILD_DIR" "s3://${BUCKET_NAME}" \
    --region "$REGION" \
    --include "*.html" \
    --cache-control "public, max-age=0, must-revalidate"

echo -e "${GREEN}[정보]${NC} S3 업로드 완료."

# ============================================================
# 3단계: CloudFront 캐시 무효화
# ============================================================
if [ -n "$DISTRIBUTION_ID" ] && [ "$DISTRIBUTION_ID" != "None" ]; then
    echo -e "${GREEN}[3/3]${NC} CloudFront 캐시를 무효화합니다..."

    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --query "Invalidation.Id" \
        --output text)

    echo -e "${GREEN}[정보]${NC} 캐시 무효화 요청 완료. Invalidation ID: ${INVALIDATION_ID}"
    echo -e "${YELLOW}[정보]${NC} 캐시 무효화는 수 분이 소요될 수 있습니다."
else
    echo -e "${YELLOW}[3/3]${NC} CloudFront Distribution ID가 없어 캐시 무효화를 건너뜁니다."
fi

# ============================================================
# 배포 결과 요약
# ============================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} 대시보드 배포 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  S3 버킷: ${BUCKET_NAME}"

if [ -n "$DISTRIBUTION_ID" ] && [ "$DISTRIBUTION_ID" != "None" ]; then
    CF_URL=$(aws cloudformation describe-stacks \
        --stack-name FrontendStack \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-DashboardUrl'].OutputValue" \
        --output text 2>/dev/null || echo "")
    if [ -n "$CF_URL" ] && [ "$CF_URL" != "None" ]; then
        echo -e "  대시보드 URL: ${CF_URL}"
    fi
fi
echo ""
