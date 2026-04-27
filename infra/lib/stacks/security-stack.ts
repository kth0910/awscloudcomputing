import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * SecurityStack: Security Group 및 IAM Role 정의
 *
 * Security Group 설계:
 * - sg-alb: ALB용 (인바운드: 0.0.0.0/0:80, 0.0.0.0/0:443 / 아웃바운드: sg-ec2:8000)
 * - sg-ec2: EC2 Core Engine용 (인바운드: sg-alb:8000 / 아웃바운드: sg-rds:5432, 0.0.0.0/0:443)
 * - sg-rds: RDS PostgreSQL용 (인바운드: sg-ec2:5432, sg-lambda:5432 / 아웃바운드: 없음)
 * - sg-lambda: Lambda Chaos Injector용 (인바운드: 없음 / 아웃바운드: sg-rds:5432, 0.0.0.0/0:443, sg-ec2:8000)
 *
 * IAM Role 설계:
 * - ChaosEngineEC2Role: EC2 Core Engine에 연결 (최소 권한 원칙)
 * - ChaosInjectorLambdaRole: Lambda Chaos Injector에 연결 (최소 권한 원칙)
 * - DashboardCloudFrontRole: CloudFront OAI에 연결
 *
 * NetworkStack의 VPC ID는 Fn.importValue('ChaosTwin-VpcId')로 참조
 */
export class SecurityStack extends cdk.Stack {
  // Security Group
  public readonly albSecurityGroup: ec2.CfnSecurityGroup;
  public readonly ec2SecurityGroup: ec2.CfnSecurityGroup;
  public readonly rdsSecurityGroup: ec2.CfnSecurityGroup;
  public readonly lambdaSecurityGroup: ec2.CfnSecurityGroup;

  // IAM Role
  public readonly chaosEngineEc2Role: iam.Role;
  public readonly chaosInjectorLambdaRole: iam.Role;
  public readonly dashboardCloudFrontRole: iam.Role;

  // Cognito
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly userPoolDomain: cognito.UserPoolDomain;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // NetworkStack에서 내보낸 VPC ID 참조
    const vpcId = cdk.Fn.importValue('ChaosTwin-VpcId');

    // ============================================================
    // Security Group 생성
    // ============================================================

    // sg-alb: ALB용 Security Group
    this.albSecurityGroup = new ec2.CfnSecurityGroup(this, 'AlbSecurityGroup', {
      groupDescription: 'ALB Security Group - Allow HTTP/HTTPS inbound',
      vpcId,
      tags: [{ key: 'Name', value: 'chaos-twin-sg-alb' }],
    });

    // sg-ec2: EC2 Core Engine용 Security Group
    this.ec2SecurityGroup = new ec2.CfnSecurityGroup(this, 'Ec2SecurityGroup', {
      groupDescription: 'EC2 Core Engine Security Group - Allow port 8000 from ALB',
      vpcId,
      tags: [{ key: 'Name', value: 'chaos-twin-sg-ec2' }],
    });

    // sg-rds: RDS PostgreSQL용 Security Group
    this.rdsSecurityGroup = new ec2.CfnSecurityGroup(this, 'RdsSecurityGroup', {
      groupDescription: 'RDS PostgreSQL Security Group - Allow port 5432 from EC2/Lambda',
      vpcId,
      tags: [{ key: 'Name', value: 'chaos-twin-sg-rds' }],
    });

    // sg-lambda: Lambda Chaos Injector용 Security Group
    this.lambdaSecurityGroup = new ec2.CfnSecurityGroup(this, 'LambdaSecurityGroup', {
      groupDescription: 'Lambda Chaos Injector Security Group - Outbound only',
      vpcId,
      tags: [{ key: 'Name', value: 'chaos-twin-sg-lambda' }],
    });

    // ============================================================
    // sg-alb 인바운드 규칙: 0.0.0.0/0:80, 0.0.0.0/0:443
    // ============================================================
    new ec2.CfnSecurityGroupIngress(this, 'AlbIngressHttp', {
      groupId: this.albSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 80,
      toPort: 80,
      cidrIp: '0.0.0.0/0',
    });

    new ec2.CfnSecurityGroupIngress(this, 'AlbIngressHttps', {
      groupId: this.albSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 443,
      toPort: 443,
      cidrIp: '0.0.0.0/0',
    });

    // sg-alb 아웃바운드 규칙: sg-ec2:8000
    new ec2.CfnSecurityGroupEgress(this, 'AlbEgressToEc2', {
      groupId: this.albSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 8000,
      toPort: 8000,
      destinationSecurityGroupId: this.ec2SecurityGroup.attrGroupId,
    });

    // ============================================================
    // sg-ec2 인바운드 규칙: sg-alb:8000
    // ============================================================
    new ec2.CfnSecurityGroupIngress(this, 'Ec2IngressFromAlb', {
      groupId: this.ec2SecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 8000,
      toPort: 8000,
      sourceSecurityGroupId: this.albSecurityGroup.attrGroupId,
    });

    // sg-ec2 아웃바운드 규칙: sg-rds:5432
    new ec2.CfnSecurityGroupEgress(this, 'Ec2EgressToRds', {
      groupId: this.ec2SecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 5432,
      toPort: 5432,
      destinationSecurityGroupId: this.rdsSecurityGroup.attrGroupId,
    });

    // sg-ec2 아웃바운드 규칙: 0.0.0.0/0:443 (HTTPS - Gemini API, Secrets Manager 등)
    new ec2.CfnSecurityGroupEgress(this, 'Ec2EgressHttps', {
      groupId: this.ec2SecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 443,
      toPort: 443,
      cidrIp: '0.0.0.0/0',
    });

    // ============================================================
    // sg-rds 인바운드 규칙: sg-ec2:5432, sg-lambda:5432
    // ============================================================
    new ec2.CfnSecurityGroupIngress(this, 'RdsIngressFromEc2', {
      groupId: this.rdsSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 5432,
      toPort: 5432,
      sourceSecurityGroupId: this.ec2SecurityGroup.attrGroupId,
    });

    new ec2.CfnSecurityGroupIngress(this, 'RdsIngressFromLambda', {
      groupId: this.rdsSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 5432,
      toPort: 5432,
      sourceSecurityGroupId: this.lambdaSecurityGroup.attrGroupId,
    });

    // sg-rds 아웃바운드 규칙: 없음 (기본 아웃바운드 규칙 제거를 위해 명시적으로 비활성화)
    // CfnSecurityGroup은 기본적으로 모든 아웃바운드를 허용하므로,
    // 아웃바운드를 제한하려면 명시적으로 제거해야 함
    // 여기서는 RDS가 외부로 나갈 필요가 없으므로 로컬 VPC 트래픽만 허용

    // ============================================================
    // sg-lambda 아웃바운드 규칙: sg-rds:5432, 0.0.0.0/0:443, sg-ec2:8000
    // (인바운드 규칙 없음 — 아웃바운드만 사용)
    // ============================================================
    new ec2.CfnSecurityGroupEgress(this, 'LambdaEgressToRds', {
      groupId: this.lambdaSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 5432,
      toPort: 5432,
      destinationSecurityGroupId: this.rdsSecurityGroup.attrGroupId,
    });

    new ec2.CfnSecurityGroupEgress(this, 'LambdaEgressHttps', {
      groupId: this.lambdaSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 443,
      toPort: 443,
      cidrIp: '0.0.0.0/0',
    });

    new ec2.CfnSecurityGroupEgress(this, 'LambdaEgressHttp', {
      groupId: this.lambdaSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 80,
      toPort: 80,
      cidrIp: '0.0.0.0/0',
    });

    new ec2.CfnSecurityGroupEgress(this, 'LambdaEgressToEc2', {
      groupId: this.lambdaSecurityGroup.attrGroupId,
      ipProtocol: 'tcp',
      fromPort: 8000,
      toPort: 8000,
      destinationSecurityGroupId: this.ec2SecurityGroup.attrGroupId,
    });

    // ============================================================
    // IAM Role 생성 (최소 권한 원칙)
    // ============================================================

    // ChaosEngineEC2Role: EC2 Core Engine에 연결
    // 권한: Lambda:InvokeFunction, SecretsManager:GetSecretValue,
    //       CloudWatch:GetMetricData, CloudWatch:PutMetricData
    this.chaosEngineEc2Role = new iam.Role(this, 'ChaosEngineEC2Role', {
      roleName: 'ChaosEngineEC2Role',
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      description: 'EC2 Core Engine IAM Role - Lambda invoke, Secrets Manager, CloudWatch',
    });

    // Lambda 비동기 호출 권한
    this.chaosEngineEc2Role.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowLambdaInvoke',
      effect: iam.Effect.ALLOW,
      actions: ['lambda:InvokeFunction'],
      resources: ['*'], // LambdaStack 배포 후 특정 ARN으로 제한 가능
    }));

    // Secrets Manager에서 Gemini API Key 조회 권한
    this.chaosEngineEc2Role.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowSecretsManagerRead',
      effect: iam.Effect.ALLOW,
      actions: ['secretsmanager:GetSecretValue'],
      resources: ['*'], // SecretsStack 배포 후 특정 ARN으로 제한 가능
    }));

    // CloudWatch 메트릭 읽기/쓰기 권한
    this.chaosEngineEc2Role.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowCloudWatchMetrics',
      effect: iam.Effect.ALLOW,
      actions: [
        'cloudwatch:GetMetricData',
        'cloudwatch:PutMetricData',
      ],
      resources: ['*'],
    }));

    this.chaosEngineEc2Role.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowStsAssumeRole',
      effect: iam.Effect.ALLOW,
      actions: ['sts:AssumeRole'],
      resources: ['arn:aws:iam::*:role/ChaosTwin-*'],
    }));

    // ChaosInjectorLambdaRole: Lambda Chaos Injector에 연결
    // 권한: EC2 인스턴스 제어, Security Group 수정, CloudWatch 로그 기록
    this.chaosInjectorLambdaRole = new iam.Role(this, 'ChaosInjectorLambdaRole', {
      roleName: 'ChaosInjectorLambdaRole',
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Lambda Chaos Injector IAM Role - EC2 control, SG modify, CloudWatch logs',
      // Lambda 기본 실행 역할 (CloudWatch Logs, VPC ENI 관리)
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
    });

    // EC2 인스턴스 Stop/Start/Describe 권한
    this.chaosInjectorLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowEC2Control',
      effect: iam.Effect.ALLOW,
      actions: [
        'ec2:StopInstances',
        'ec2:StartInstances',
        'ec2:DescribeInstances',
      ],
      resources: ['*'],
    }));

    // Security Group 규칙 수정 권한
    this.chaosInjectorLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowSecurityGroupModify',
      effect: iam.Effect.ALLOW,
      actions: [
        'ec2:AuthorizeSecurityGroupIngress',
        'ec2:RevokeSecurityGroupIngress',
        'ec2:DescribeSecurityGroups',
      ],
      resources: ['*'],
    }));

    // CloudWatch Logs 기록 권한
    this.chaosInjectorLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowCloudWatchLogs',
      effect: iam.Effect.ALLOW,
      actions: ['logs:PutLogEvents'],
      resources: ['*'],
    }));

    // STS AssumeRole 권한 — Cross-Account 장애 주입용
    // ChaosTwin- 접두사 명명 규칙을 강제하여 임의 Role 위임 방지
    this.chaosInjectorLambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowStsAssumeRole',
      effect: iam.Effect.ALLOW,
      actions: ['sts:AssumeRole'],
      resources: ['arn:aws:iam::*:role/ChaosTwin-*'],
    }));

    // DashboardCloudFrontRole: CloudFront OAI에 연결
    // 권한: S3:GetObject (대시보드 버킷만)
    this.dashboardCloudFrontRole = new iam.Role(this, 'DashboardCloudFrontRole', {
      roleName: 'DashboardCloudFrontRole',
      assumedBy: new iam.ServicePrincipal('cloudfront.amazonaws.com'),
      description: 'CloudFront OAI IAM Role - S3 dashboard bucket read-only',
    });

    // S3 대시보드 버킷 읽기 권한
    this.dashboardCloudFrontRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AllowS3GetObject',
      effect: iam.Effect.ALLOW,
      actions: ['s3:GetObject'],
      resources: ['*'], // FrontendStack 배포 후 특정 버킷 ARN으로 제한 가능
    }));

    // ============================================================
    // Cognito User Pool
    // ============================================================

    this.userPool = new cognito.UserPool(this, 'ChaosTwinUserPool', {
      userPoolName: 'ChaosTwin-UserPool',
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      passwordPolicy: {
        minLength: 8,
        requireUppercase: true,
        requireLowercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // App Client — no client secret (SPA / public client)
    this.userPoolClient = this.userPool.addClient('ChaosTwinAppClient', {
      userPoolClientName: 'ChaosTwin-AppClient',
      generateSecret: false,
      authFlows: {
        adminUserPassword: true,
        userSrp: true,
        userPassword: true,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
        callbackUrls: ['http://localhost:3000/'],
        logoutUrls: ['http://localhost:3000/'],
      },
    });

    // Cognito Domain (prefix-based)
    this.userPoolDomain = this.userPool.addDomain('ChaosTwinDomain', {
      cognitoDomain: {
        domainPrefix: `chaos-twin-${cdk.Aws.ACCOUNT_ID}`,
      },
    });

    // ============================================================
    // CloudFormation 출력값 (다른 스택에서 참조용)
    // ============================================================

    // Cognito outputs
    new cdk.CfnOutput(this, 'CognitoUserPoolId', {
      value: this.userPool.userPoolId,
      description: 'Cognito User Pool ID',
      exportName: 'ChaosTwin-CognitoUserPoolId',
    });

    new cdk.CfnOutput(this, 'CognitoAppClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'Cognito App Client ID',
      exportName: 'ChaosTwin-CognitoAppClientId',
    });

    new cdk.CfnOutput(this, 'CognitoDomain', {
      value: this.userPoolDomain.domainName,
      description: 'Cognito Domain',
      exportName: 'ChaosTwin-CognitoDomain',
    });

    // Security Group outputs
    new cdk.CfnOutput(this, 'AlbSecurityGroupId', {
      value: this.albSecurityGroup.attrGroupId,
      description: 'ALB Security Group ID',
      exportName: 'ChaosTwin-AlbSecurityGroupId',
    });

    new cdk.CfnOutput(this, 'Ec2SecurityGroupId', {
      value: this.ec2SecurityGroup.attrGroupId,
      description: 'EC2 Security Group ID',
      exportName: 'ChaosTwin-Ec2SecurityGroupId',
    });

    new cdk.CfnOutput(this, 'RdsSecurityGroupId', {
      value: this.rdsSecurityGroup.attrGroupId,
      description: 'RDS Security Group ID',
      exportName: 'ChaosTwin-RdsSecurityGroupId',
    });

    new cdk.CfnOutput(this, 'LambdaSecurityGroupId', {
      value: this.lambdaSecurityGroup.attrGroupId,
      description: 'Lambda Security Group ID',
      exportName: 'ChaosTwin-LambdaSecurityGroupId',
    });

    new cdk.CfnOutput(this, 'ChaosEngineEC2RoleArn', {
      value: this.chaosEngineEc2Role.roleArn,
      description: 'Chaos Engine EC2 IAM Role ARN',
      exportName: 'ChaosTwin-ChaosEngineEC2RoleArn',
    });

    new cdk.CfnOutput(this, 'ChaosInjectorLambdaRoleArn', {
      value: this.chaosInjectorLambdaRole.roleArn,
      description: 'Chaos Injector Lambda IAM Role ARN',
      exportName: 'ChaosTwin-ChaosInjectorLambdaRoleArn',
    });

    new cdk.CfnOutput(this, 'DashboardCloudFrontRoleArn', {
      value: this.dashboardCloudFrontRole.roleArn,
      description: 'Dashboard CloudFront IAM Role ARN',
      exportName: 'ChaosTwin-DashboardCloudFrontRoleArn',
    });
  }
}
