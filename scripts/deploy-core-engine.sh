#!/bin/bash
# ============================================================
# Core Engine EC2 배포 스크립트
# EC2 인스턴스에 SSH 접속하여 Docker 이미지를 업데이트합니다.
#
# 사용법:
#   ./scripts/deploy-core-engine.sh [--instance-id <id>] [--key-file <pem>]
#
# CDK 출력값에서 인스턴스 ID를 자동으로 가져오거나,
# 인자로 직접 지정할 수 있습니다.
# ============================================================
set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 프로젝트 루트 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo -e "${GREEN}[Core Engine 배포]${NC} 시작..."

# ============================================================
# 인자 파싱
# ============================================================
INSTANCE_ID=""
KEY_FILE=""
REGION="us-east-1"

while [[ $# -gt 0 ]]; do
    case $1 in
        --instance-id) INSTANCE_ID="$2"; shift 2 ;;
        --key-file) KEY_FILE="$2"; shift 2 ;;
        --region) REGION="$2"; shift 2 ;;
        *) echo -e "${RED}[오류]${NC} 알 수 없는 인자: $1"; exit 1 ;;
    esac
done

# ============================================================
# CDK 출력값에서 인스턴스 ID 조회 (인자 미지정 시)
# ============================================================
if [ -z "$INSTANCE_ID" ]; then
    echo -e "${YELLOW}[정보]${NC} CDK 출력값에서 EC2 인스턴스 ID를 조회합니다..."
    INSTANCE_ID=$(aws cloudformation describe-stacks \
        --stack-name ComputeStack \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?ExportName=='ChaosTwin-CoreEngineInstanceId'].OutputValue" \
        --output text 2>/dev/null || true)

    if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = "None" ]; then
        echo -e "${RED}[오류]${NC} EC2 인스턴스 ID를 찾을 수 없습니다."
        echo "  --instance-id 옵션으로 직접 지정하거나, CDK 배포를 먼저 실행하세요."
        exit 1
    fi
fi

echo -e "${GREEN}[정보]${NC} 대상 EC2 인스턴스: ${INSTANCE_ID}"

# ============================================================
# 방법 1: SSM Session Manager를 통한 원격 명령 실행 (권장)
# SSH 키 없이 IAM 기반으로 접근 가능
# ============================================================
echo -e "${GREEN}[1/4]${NC} Core Engine 소스 코드를 압축합니다..."
cd "$PROJECT_ROOT"
tar -czf /tmp/core-engine.tar.gz \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='tests' \
    --exclude='*.pyc' \
    -C core-engine .

echo -e "${GREEN}[2/4]${NC} S3를 통해 소스 코드를 전송합니다..."
# 임시 S3 경로에 업로드
DEPLOY_BUCKET="chaos-twin-deploy-${REGION}"
DEPLOY_KEY="core-engine/core-engine-$(date +%Y%m%d%H%M%S).tar.gz"

# 배포용 S3 버킷이 없으면 생성
aws s3 mb "s3://${DEPLOY_BUCKET}" --region "$REGION" 2>/dev/null || true
aws s3 cp /tmp/core-engine.tar.gz "s3://${DEPLOY_BUCKET}/${DEPLOY_KEY}" --region "$REGION"

echo -e "${GREEN}[3/4]${NC} EC2에서 Docker 이미지를 업데이트합니다..."
# SSM Run Command로 원격 실행
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --region "$REGION" \
    --parameters "commands=[
        'set -euxo pipefail',
        'cd /opt/chaos-twin',
        'aws s3 cp s3://${DEPLOY_BUCKET}/${DEPLOY_KEY} /tmp/core-engine.tar.gz --region ${REGION}',
        'rm -rf /opt/chaos-twin/app/*',
        'tar -xzf /tmp/core-engine.tar.gz -C /opt/chaos-twin/',
        'docker build -t chaos-twin-core-engine .',
        'docker stop chaos-twin-core-engine || true',
        'docker rm chaos-twin-core-engine || true',
        'docker run -d --name chaos-twin-core-engine --restart=always --env-file /opt/chaos-twin/.env -p 8000:8000 chaos-twin-core-engine',
        'echo Core Engine 배포 완료'
    ]" \
    --query "Command.CommandId" \
    --output text)

echo -e "${YELLOW}[정보]${NC} SSM Command ID: ${COMMAND_ID}"

# 명령 실행 완료 대기 (최대 120초)
echo -e "${GREEN}[4/4]${NC} 배포 완료를 대기합니다..."
aws ssm wait command-executed \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" 2>/dev/null || true

# 실행 결과 확인
STATUS=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query "Status" \
    --output text 2>/dev/null || echo "Unknown")

if [ "$STATUS" = "Success" ]; then
    echo -e "${GREEN}[완료]${NC} Core Engine 배포가 성공적으로 완료되었습니다!"
else
    echo -e "${RED}[오류]${NC} 배포 상태: ${STATUS}"
    echo "  SSM 콘솔에서 상세 로그를 확인하세요."
    echo "  Command ID: ${COMMAND_ID}"
    exit 1
fi

# 임시 파일 정리
rm -f /tmp/core-engine.tar.gz
echo -e "${GREEN}[정리]${NC} 임시 파일을 삭제했습니다."
