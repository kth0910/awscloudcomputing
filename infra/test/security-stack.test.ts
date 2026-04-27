import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { SecurityStack } from '../lib/stacks/security-stack';

describe('SecurityStack', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();

    // SecurityStack imports VpcId from NetworkStack via Fn.importValue.
    // We don't need NetworkStack deployed — CDK synth resolves it as a token.
    const stack = new SecurityStack(app, 'TestSecurityStack', {
      env: { account: '123456789012', region: 'us-east-1' },
    });

    template = Template.fromStack(stack);
  });

  // -------------------------------------------------------
  // Cognito User Pool — Requirement 10.1
  // -------------------------------------------------------
  test('creates Cognito User Pool with email auto-verify and password policy', () => {
    template.hasResourceProperties('AWS::Cognito::UserPool', {
      AutoVerifiedAttributes: ['email'],
      Policies: {
        PasswordPolicy: {
          MinimumLength: 8,
          RequireUppercase: true,
          RequireLowercase: true,
          RequireNumbers: true,
          RequireSymbols: true,
        },
      },
    });
  });

  // -------------------------------------------------------
  // Cognito App Client — Requirements 10.2, 10.3
  // -------------------------------------------------------
  test('creates App Client with no client secret', () => {
    template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
      GenerateSecret: false,
    });
  });

  // -------------------------------------------------------
  // IAM Policy: sts:AssumeRole — Requirements 8.1, 8.2
  // -------------------------------------------------------
  test('ChaosInjectorLambdaRole has sts:AssumeRole policy with ChaosTwin-* resource pattern', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: 'sts:AssumeRole',
            Effect: 'Allow',
            Resource: 'arn:aws:iam::*:role/ChaosTwin-*',
          }),
        ]),
      },
    });
  });

  // -------------------------------------------------------
  // CloudFormation Outputs — Requirement 10.4
  // -------------------------------------------------------
  test('exports Cognito User Pool ID output', () => {
    template.hasOutput('CognitoUserPoolId', {
      Export: { Name: 'ChaosTwin-CognitoUserPoolId' },
    });
  });

  test('exports Cognito App Client ID output', () => {
    template.hasOutput('CognitoAppClientId', {
      Export: { Name: 'ChaosTwin-CognitoAppClientId' },
    });
  });
});
