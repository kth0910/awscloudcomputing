import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { Construct } from 'constructs';
import { FastApiEc2 } from '../constructs/fastapi-ec2';

/**
 * ComputeStack: EC2 인스턴스, ALB, Target Group 등 컴퓨트 리소스 정의
 *
 * 설계:
 * - EC2 t2.micro (Private Subnet A) — FastAPI Core Engine
 * - ALB (Public Subnet A, B) — 외부 트래픽 수신
 * - Target Group (포트 8000) — ALB → EC2 라우팅
 * - ALB Listener (HTTP:80) → Target Group 포워딩
 *
 * 의존성 (Fn.importValue 사용):
 * - NetworkStack: VPC ID, Public Subnet A/B ID, Private Subnet A ID
 * - SecurityStack: ALB Security Group ID, EC2 Security Group ID, ChaosEngineEC2Role ARN
 * - DatabaseStack: RDS 엔드포인트, 포트, Secret ARN, DB 이름
 * - SecretsStack: Gemini API Key Secret ARN
 */
export class ComputeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ============================================================
    // 다른 스택에서 내보낸 값 참조 (Fn.importValue)
    // ============================================================

    // NetworkStack 참조
    const vpcId = cdk.Fn.importValue('ChaosTwin-VpcId');
    const publicSubnetAId = cdk.Fn.importValue('ChaosTwin-PublicSubnetAId');
    const publicSubnetBId = cdk.Fn.importValue('ChaosTwin-PublicSubnetBId');
    const privateSubnetAId = cdk.Fn.importValue('ChaosTwin-PrivateSubnetAId');

    // SecurityStack 참조
    const albSecurityGroupId = cdk.Fn.importValue('ChaosTwin-AlbSecurityGroupId');
    const ec2SecurityGroupId = cdk.Fn.importValue('ChaosTwin-Ec2SecurityGroupId');
    const ec2RoleArn = cdk.Fn.importValue('ChaosTwin-ChaosEngineEC2RoleArn');

    // DatabaseStack 참조
    const rdsEndpoint = cdk.Fn.importValue('ChaosTwin-RdsEndpoint');
    const rdsPort = cdk.Fn.importValue('ChaosTwin-RdsPort');
    const rdsSecretArn = cdk.Fn.importValue('ChaosTwin-RdsSecretArn');
    const rdsDbName = cdk.Fn.importValue('ChaosTwin-RdsDbName');

    // SecretsStack 참조
    const geminiApiKeySecretArn = cdk.Fn.importValue('ChaosTwin-GeminiApiKeySecretArn');

    // ============================================================
    // FastAPI EC2 인스턴스 생성 (커스텀 Construct 사용)
    // - t2.micro, Private Subnet A, Docker + FastAPI 자동 배포
    // ============================================================
    const fastApiEc2 = new FastApiEc2(this, 'FastApiEc2', {
      subnetId: privateSubnetAId,
      securityGroupId: ec2SecurityGroupId,
      ec2RoleArn,
      rdsEndpoint,
      rdsPort,
      rdsSecretArn,
      rdsDbName,
      geminiApiKeySecretArn,
    });

    // ============================================================
    // Application Load Balancer (ALB) 생성
    // - Public Subnet A, B에 배치
    // - sg-alb Security Group 적용
    // - internet-facing (외부 트래픽 수신)
    // ============================================================
    const alb = new elbv2.CfnLoadBalancer(this, 'CoreEngineAlb', {
      name: 'chaos-twin-alb',
      type: 'application',
      scheme: 'internet-facing',
      securityGroups: [albSecurityGroupId],
      subnets: [publicSubnetAId, publicSubnetBId],
      tags: [{ key: 'Name', value: 'chaos-twin-alb' }],
    });

    // ============================================================
    // Target Group 생성
    // - 포트 8000 (FastAPI)
    // - 헬스 체크: /health 엔드포인트
    // - 프로토콜: HTTP
    // ============================================================
    const targetGroup = new elbv2.CfnTargetGroup(this, 'CoreEngineTargetGroup', {
      name: 'chaos-twin-tg',
      port: 8000,
      protocol: 'HTTP',
      vpcId,
      targetType: 'instance',
      healthCheckEnabled: true,
      healthCheckPath: '/health',
      healthCheckProtocol: 'HTTP',
      healthCheckPort: '8000',
      healthCheckIntervalSeconds: 30,
      healthCheckTimeoutSeconds: 10,
      healthyThresholdCount: 3,
      unhealthyThresholdCount: 3,
      // EC2 인스턴스를 Target으로 등록
      targets: [
        {
          id: fastApiEc2.instance.ref,
          port: 8000,
        },
      ],
      tags: [{ key: 'Name', value: 'chaos-twin-tg' }],
    });

    // ============================================================
    // ALB Listener 생성
    // - HTTP:80 → Target Group 포워딩
    // - 프로덕션 환경에서는 HTTPS:443 + ACM 인증서 사용 권장
    // ============================================================
    const listener = new elbv2.CfnListener(this, 'CoreEngineListener', {
      loadBalancerArn: alb.ref,
      port: 80,
      protocol: 'HTTP',
      defaultActions: [
        {
          type: 'forward',
          targetGroupArn: targetGroup.ref,
        },
      ],
    });

    // ============================================================
    // CloudFormation 출력값 (다른 스택 및 Dashboard에서 참조용)
    // ============================================================

    // ALB DNS 이름 — Dashboard와 Lambda에서 Core Engine API 호출 시 사용
    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: alb.attrDnsName,
      description: 'ALB DNS 이름 (Core Engine API 엔드포인트)',
      exportName: 'ChaosTwin-AlbDnsName',
    });

    // ALB 전체 URL — HTTP 프로토콜 포함
    new cdk.CfnOutput(this, 'AlbUrl', {
      value: cdk.Fn.join('', ['http://', alb.attrDnsName]),
      description: 'ALB 전체 URL (HTTP)',
      exportName: 'ChaosTwin-AlbUrl',
    });

    // EC2 인스턴스 ID — Chaos 실험 대상 리소스로 사용 가능
    new cdk.CfnOutput(this, 'CoreEngineInstanceId', {
      value: fastApiEc2.instance.ref,
      description: 'Core Engine EC2 인스턴스 ID',
      exportName: 'ChaosTwin-CoreEngineInstanceId',
    });
  }
}
