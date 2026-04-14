import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { ChaosLambda } from '../constructs/chaos-lambda';

/**
 * LambdaStack: Chaos Injector Lambda 함수 정의
 *
 * 설계:
 * - Chaos Injector Lambda (Python 3.12, 256MB, 900초 타임아웃)
 * - Reserved Concurrency: 10 (동시 실행 제한)
 * - VPC 연결: Private Subnet A, B (ENI 생성)
 * - 코드: chaos-injector/ 디렉토리에서 자동 패키징
 *
 * 의존성 (Fn.importValue 사용):
 * - NetworkStack: VPC ID, Private Subnet A/B ID
 * - SecurityStack: Lambda Security Group ID, ChaosInjectorLambdaRole ARN
 * - ComputeStack: ALB DNS 이름 (콜백 URL 구성용)
 */
export class LambdaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ============================================================
    // 다른 스택에서 내보낸 값 참조 (Fn.importValue)
    // ============================================================

    // NetworkStack 참조
    const vpcId = cdk.Fn.importValue('ChaosTwin-VpcId');
    const privateSubnetAId = cdk.Fn.importValue('ChaosTwin-PrivateSubnetAId');
    const privateSubnetBId = cdk.Fn.importValue('ChaosTwin-PrivateSubnetBId');

    // SecurityStack 참조
    const securityGroupId = cdk.Fn.importValue('ChaosTwin-LambdaSecurityGroupId');
    const lambdaRoleArn = cdk.Fn.importValue('ChaosTwin-ChaosInjectorLambdaRoleArn');

    // ComputeStack 참조 — Lambda 환경변수로 CALLBACK_BASE_URL 설정
    const albDnsName = cdk.Fn.importValue('ChaosTwin-AlbDnsName');

    // ============================================================
    // Chaos Injector Lambda 생성 (커스텀 Construct 사용)
    // ============================================================
    const chaosLambda = new ChaosLambda(this, 'ChaosLambda', {
      privateSubnetAId,
      privateSubnetBId,
      securityGroupId,
      lambdaRoleArn,
      vpcId,
      albDnsName,
    });

    // ============================================================
    // CloudFormation 출력값 (다른 스택에서 참조용)
    // ============================================================

    // Lambda 함수 ARN — ComputeStack의 EC2에서 Lambda 호출 시 사용
    new cdk.CfnOutput(this, 'ChaosInjectorLambdaArn', {
      value: chaosLambda.lambdaFunction.functionArn,
      description: 'Chaos Injector Lambda 함수 ARN',
      exportName: 'ChaosTwin-ChaosInjectorLambdaArn',
    });

    // Lambda 함수 이름 — 모니터링 및 디버깅용
    new cdk.CfnOutput(this, 'ChaosInjectorLambdaName', {
      value: chaosLambda.lambdaFunction.functionName,
      description: 'Chaos Injector Lambda 함수 이름',
      exportName: 'ChaosTwin-ChaosInjectorLambdaName',
    });
  }
}
