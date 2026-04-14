import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

/**
 * FastApiEc2 커스텀 구성 속성
 */
export interface FastApiEc2Props {
  /** EC2가 배치될 Private Subnet ID */
  readonly subnetId: string;
  /** EC2 Security Group ID */
  readonly securityGroupId: string;
  /** ChaosEngineEC2Role ARN (Instance Profile 생성용) */
  readonly ec2RoleArn: string;
  /** RDS 엔드포인트 주소 */
  readonly rdsEndpoint: string;
  /** RDS 포트 */
  readonly rdsPort: string;
  /** RDS 자격 증명 Secrets Manager ARN */
  readonly rdsSecretArn: string;
  /** RDS 데이터베이스 이름 */
  readonly rdsDbName: string;
  /** Gemini API Key Secrets Manager ARN */
  readonly geminiApiKeySecretArn: string;
}

/**
 * FastApiEc2: EC2 인스턴스 + User Data 커스텀 구성
 *
 * - Amazon Linux 2023 AMI (SSM Parameter로 최신 AMI 조회)
 * - t2.micro 인스턴스 (Free Tier)
 * - Private Subnet A에 배치
 * - ChaosEngineEC2Role을 Instance Profile로 연결
 * - User Data: Docker 설치 → FastAPI 컨테이너 실행 자동화
 */
export class FastApiEc2 extends Construct {
  /** 생성된 EC2 인스턴스 */
  public readonly instance: ec2.CfnInstance;

  constructor(scope: Construct, id: string, props: FastApiEc2Props) {
    super(scope, id);

    // ============================================================
    // Amazon Linux 2023 최신 AMI 조회 (SSM Parameter)
    // ============================================================
    const al2023AmiId = ssm.StringParameter.valueForStringParameter(
      this,
      '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64',
    );

    // ============================================================
    // IAM Instance Profile 생성
    // ChaosEngineEC2Role을 EC2 인스턴스에 연결하기 위한 프로필
    // ============================================================
    const instanceProfile = new iam.CfnInstanceProfile(this, 'Ec2InstanceProfile', {
      roles: [
        // ARN에서 Role 이름 추출: arn:aws:iam::ACCOUNT:role/ROLE_NAME → ROLE_NAME
        cdk.Fn.select(1, cdk.Fn.split('role/', props.ec2RoleArn)),
      ],
      instanceProfileName: 'ChaosEngineEC2InstanceProfile',
    });

    // ============================================================
    // User Data 스크립트: Docker 설치 + FastAPI 컨테이너 실행
    // ============================================================
    const userData = this.buildUserData(props);

    // ============================================================
    // EC2 인스턴스 생성 (CfnInstance)
    // - t2.micro (Free Tier)
    // - Private Subnet A에 배치
    // - sg-ec2 Security Group 적용
    // ============================================================
    this.instance = new ec2.CfnInstance(this, 'FastApiInstance', {
      instanceType: 't2.micro',
      imageId: al2023AmiId,
      subnetId: props.subnetId,
      securityGroupIds: [props.securityGroupId],
      iamInstanceProfile: instanceProfile.ref,
      userData: cdk.Fn.base64(userData),
      tags: [{ key: 'Name', value: 'chaos-twin-core-engine' }],
    });

    // Instance Profile이 먼저 생성되어야 함
    this.instance.addDependency(instanceProfile);
  }

  /**
   * User Data 스크립트 생성
   * - Docker 설치 및 서비스 시작
   * - FastAPI 컨테이너 실행에 필요한 환경 변수 설정
   * - 컨테이너 자동 재시작 설정
   */
  private buildUserData(props: FastApiEc2Props): string {
    return [
      '#!/bin/bash',
      'set -euxo pipefail',
      '',
      '# ============================================================',
      '# 시스템 업데이트 및 Docker 설치',
      '# ============================================================',
      'dnf update -y',
      'dnf install -y docker',
      '',
      '# Docker 서비스 시작 및 부팅 시 자동 시작 설정',
      'systemctl start docker',
      'systemctl enable docker',
      '',
      '# ec2-user를 docker 그룹에 추가',
      'usermod -aG docker ec2-user',
      '',
      '# ============================================================',
      '# 환경 변수 설정 파일 생성',
      '# RDS 연결 정보 및 Secrets Manager ARN을 컨테이너에 전달',
      '# ============================================================',
      'mkdir -p /opt/chaos-twin',
      'cat > /opt/chaos-twin/.env << EOF',
      `RDS_ENDPOINT=${props.rdsEndpoint}`,
      `RDS_PORT=${props.rdsPort}`,
      `RDS_SECRET_ARN=${props.rdsSecretArn}`,
      `RDS_DB_NAME=${props.rdsDbName}`,
      `GEMINI_API_KEY_SECRET_ARN=${props.geminiApiKeySecretArn}`,
      `AWS_DEFAULT_REGION=${cdk.Aws.REGION}`,
      'EOF',
      '',
      '# ============================================================',
      '# FastAPI 애플리케이션 Dockerfile 생성',
      '# 실제 배포 시 ECR에서 이미지를 가져오거나,',
      '# CodeDeploy를 통해 소스 코드를 배포할 수 있음',
      '# ============================================================',
      'cat > /opt/chaos-twin/Dockerfile << \'DOCKERFILE\'',
      'FROM python:3.12-slim',
      'WORKDIR /app',
      'COPY requirements.txt .',
      'RUN pip install --no-cache-dir -r requirements.txt',
      'COPY . .',
      'EXPOSE 8000',
      'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]',
      'DOCKERFILE',
      '',
      '# ============================================================',
      '# 기본 requirements.txt 생성 (초기 배포용)',
      '# ============================================================',
      'cat > /opt/chaos-twin/requirements.txt << \'REQUIREMENTS\'',
      'fastapi>=0.104.0',
      'uvicorn[standard]>=0.24.0',
      'sqlalchemy[asyncio]>=2.0.0',
      'asyncpg>=0.29.0',
      'boto3>=1.34.0',
      'httpx>=0.25.0',
      'alembic>=1.13.0',
      'pydantic>=2.5.0',
      'pydantic-settings>=2.1.0',
      'REQUIREMENTS',
      '',
      '# ============================================================',
      '# 기본 FastAPI 헬스 체크 앱 생성 (초기 배포용)',
      '# 실제 Core Engine 코드가 배포되기 전까지 사용',
      '# ============================================================',
      'mkdir -p /opt/chaos-twin/app',
      'cat > /opt/chaos-twin/app/__init__.py << \'INIT\'',
      'INIT',
      '',
      'cat > /opt/chaos-twin/app/main.py << \'MAINPY\'',
      'from fastapi import FastAPI',
      '',
      'app = FastAPI(title="Chaos Twin Core Engine")',
      '',
      '@app.get("/health")',
      'async def health_check():',
      '    return {"status": "ok"}',
      'MAINPY',
      '',
      '# ============================================================',
      '# Docker 이미지 빌드 및 컨테이너 실행',
      '# --restart=always: 컨테이너 비정상 종료 시 자동 재시작',
      '# --env-file: 환경 변수 파일 전달',
      '# -p 8000:8000: 호스트 포트 8000 → 컨테이너 포트 8000 매핑',
      '# ============================================================',
      'cd /opt/chaos-twin',
      'docker build -t chaos-twin-core-engine .',
      'docker run -d \\',
      '  --name chaos-twin-core-engine \\',
      '  --restart=always \\',
      '  --env-file /opt/chaos-twin/.env \\',
      '  -p 8000:8000 \\',
      '  chaos-twin-core-engine',
      '',
      '# ============================================================',
      '# 배포 완료 로그',
      '# ============================================================',
      'echo "FastAPI Core Engine 컨테이너 배포 완료" >> /var/log/chaos-twin-deploy.log',
    ].join('\n');
  }
}
