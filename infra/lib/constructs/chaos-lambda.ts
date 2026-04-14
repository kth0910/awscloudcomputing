import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import * as path from 'path';

/**
 * ChaosLambda 커스텀 구성 속성
 */
export interface ChaosLambdaProps {
  /** Lambda가 배치될 Private Subnet A ID */
  readonly privateSubnetAId: string;
  /** Lambda가 배치될 Private Subnet B ID */
  readonly privateSubnetBId: string;
  /** Lambda Security Group ID */
  readonly securityGroupId: string;
  /** ChaosInjectorLambdaRole ARN */
  readonly lambdaRoleArn: string;
  /** VPC ID (Lambda VPC 연결용) */
  readonly vpcId: string;
  /** Core Engine ALB DNS 이름 (콜백 URL 구성용) */
  readonly albDnsName: string;
}

/**
 * ChaosLambda: Chaos Injector Lambda 함수 + 코드 패키징 커스텀 구성
 *
 * - Python 3.12 런타임
 * - 256MB 메모리
 * - 900초 (15분) 타임아웃 — 롤백 시간 포함
 * - Reserved Concurrency: 10 — 동시 실행 제한
 * - VPC 연결: Private Subnet A, B (ENI 생성)
 * - 코드: chaos-injector/ 디렉토리에서 자동 패키징
 */
export class ChaosLambda extends Construct {
  /** 생성된 Lambda 함수 */
  public readonly lambdaFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ChaosLambdaProps) {
    super(scope, id);

    // ============================================================
    // 기존 VPC 및 서브넷 참조 (Fn.importValue로 전달받은 ID 사용)
    // ============================================================
    const vpc = ec2.Vpc.fromVpcAttributes(this, 'ImportedVpc', {
      vpcId: props.vpcId,
      availabilityZones: ['us-east-1a', 'us-east-1b'],
      privateSubnetIds: [props.privateSubnetAId, props.privateSubnetBId],
    });

    // 기존 Security Group 참조
    const securityGroup = ec2.SecurityGroup.fromSecurityGroupId(
      this,
      'ImportedLambdaSg',
      props.securityGroupId,
    );

    // 기존 IAM Role 참조
    const lambdaRole = iam.Role.fromRoleArn(
      this,
      'ImportedLambdaRole',
      props.lambdaRoleArn,
    );

    // ============================================================
    // Chaos Injector Lambda 함수 생성
    // - chaos-injector/ 디렉토리에서 코드 자동 패키징
    // - Python 3.12 런타임
    // - 256MB 메모리, 900초 타임아웃
    // - Reserved Concurrency: 10
    // ============================================================
    this.lambdaFunction = new lambda.Function(this, 'ChaosInjectorFunction', {
      functionName: 'chaos-twin-chaos-injector',
      description: 'Chaos Injector — AWS 리소스에 장애를 주입하고 자동 롤백하는 Lambda 함수',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', '..', '..', 'chaos-injector')),
      memorySize: 256,
      timeout: cdk.Duration.seconds(900),
      // reservedConcurrentExecutions 제거 — 계정 쿼터 10개로 reserved 설정 불가
      role: lambdaRole,
      vpc,
      vpcSubnets: {
        subnets: vpc.privateSubnets,
      },
      securityGroups: [securityGroup],
      environment: {
        // Core Engine 콜백 URL (ALB DNS 기반)
        CALLBACK_BASE_URL: `http://${props.albDnsName}:8000`,
        // 기본 장애 지속 시간 (초)
        DEFAULT_DURATION_SECONDS: '300',
        // 로그 레벨
        LOG_LEVEL: 'INFO',
      },
    });
  }
}
