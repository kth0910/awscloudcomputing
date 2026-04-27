#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { NetworkStack } from '../lib/stacks/network-stack';
import { SecurityStack } from '../lib/stacks/security-stack';
import { DatabaseStack } from '../lib/stacks/database-stack';
import { ComputeStack } from '../lib/stacks/compute-stack';
import { LambdaStack } from '../lib/stacks/lambda-stack';
import { FrontendStack } from '../lib/stacks/frontend-stack';
import { SecretsStack } from '../lib/stacks/secrets-stack';

const app = new cdk.App();

// 공통 환경 설정 — us-east-1 고정
const env: cdk.Environment = {
  account: '510197248070',
  region: 'us-east-1',
};

// ============================================================
// 스택 인스턴스화
// ============================================================

// 1. NetworkStack: VPC, Subnet, NAT Gateway, IGW
const networkStack = new NetworkStack(app, 'NetworkStack', { env });

// 2. SecurityStack: Security Group, IAM Role
//    의존성: NetworkStack (VPC 참조 필요)
const securityStack = new SecurityStack(app, 'SecurityStack', { env });
securityStack.addDependency(networkStack);

// 3. SecretsStack: Secrets Manager (Gemini API Key)
//    독립 스택 — 다른 스택에서 참조됨
const secretsStack = new SecretsStack(app, 'SecretsStack', { env });

// 4. DatabaseStack: RDS PostgreSQL
//    의존성: NetworkStack (Subnet), SecurityStack (SG)
const databaseStack = new DatabaseStack(app, 'DatabaseStack', { env });
databaseStack.addDependency(networkStack);
databaseStack.addDependency(securityStack);

// 5. ComputeStack: EC2, ALB, Target Group
//    의존성: NetworkStack (Subnet), SecurityStack (SG, IAM),
//            DatabaseStack (RDS 엔드포인트), SecretsStack (시크릿 참조)
const computeStack = new ComputeStack(app, 'ComputeStack', { env });
computeStack.addDependency(networkStack);
computeStack.addDependency(securityStack);
computeStack.addDependency(databaseStack);
computeStack.addDependency(secretsStack);

// 6. LambdaStack: Chaos Injector Lambda
//    의존성: NetworkStack (VPC/Subnet), SecurityStack (SG, IAM),
//            SecretsStack (시크릿 참조)
const lambdaStack = new LambdaStack(app, 'LambdaStack', { env });
lambdaStack.addDependency(networkStack);
lambdaStack.addDependency(securityStack);
lambdaStack.addDependency(secretsStack);

// 7. FrontendStack: S3, CloudFront + API proxy
const frontendStack = new FrontendStack(app, 'FrontendStack', { env });
frontendStack.addDependency(computeStack);
