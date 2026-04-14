import * as cdk from 'aws-cdk-lib';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

/**
 * SecretsStack: AWS Secrets Manager 시크릿 참조 정의
 *
 * 이 스택은 이미 AWS 콘솔에서 수동으로 생성된 시크릿을 참조(lookup)한다.
 * CDK에서 새로 생성하지 않고, 기존 시크릿의 ARN을 다른 스택에서 사용할 수 있도록 내보낸다.
 *
 * 시크릿 구성:
 * - Secret Name: chaos-twin/gemini-api-key
 * - Secret Value: {"api_key": "<GEMINI_API_KEY>"}
 * - Rotation: 수동 (필요 시)
 * - Access: ChaosEngineEC2Role만 GetSecretValue 허용 (SecurityStack에서 정의)
 */
export class SecretsStack extends cdk.Stack {
  // 다른 스택에서 참조할 수 있도록 public readonly 속성으로 노출
  public readonly geminiApiKeySecret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ============================================================
    // 기존 Secrets Manager 시크릿 참조 (lookup)
    // 이미 AWS에 수동으로 생성된 시크릿을 CDK에서 참조한다.
    // 새로 생성하면 이름 충돌이 발생하므로 fromSecretNameV2를 사용한다.
    // ============================================================
    this.geminiApiKeySecret = secretsmanager.Secret.fromSecretNameV2(
      this,
      'GeminiApiKeySecret',
      'chaos-twin/gemini-api-key',
    );

    // ============================================================
    // CloudFormation 출력값 (다른 스택에서 참조용)
    // ============================================================
    new cdk.CfnOutput(this, 'GeminiApiKeySecretArn', {
      value: this.geminiApiKeySecret.secretArn,
      description: 'Gemini API Key 시크릿 ARN',
      exportName: 'ChaosTwin-GeminiApiKeySecretArn',
    });

    new cdk.CfnOutput(this, 'GeminiApiKeySecretName', {
      value: this.geminiApiKeySecret.secretName,
      description: 'Gemini API Key 시크릿 이름',
      exportName: 'ChaosTwin-GeminiApiKeySecretName',
    });
  }
}
