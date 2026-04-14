import * as cdk from 'aws-cdk-lib';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

/**
 * DatabaseStack: RDS PostgreSQL 인스턴스 및 관련 리소스 정의
 *
 * 설계:
 * - 인스턴스 타입: db.t3.micro (Free Tier)
 * - 엔진: PostgreSQL 16
 * - Multi-AZ: 비활성화 (비용 절감)
 * - DB Subnet Group: DB Subnet A (10.0.20.0/24), DB Subnet B (10.0.21.0/24)
 * - Security Group: sg-rds (EC2/Lambda에서 5432 포트만 허용)
 * - 데이터베이스 이름: chaostwin
 * - 포트: 5432
 * - 비밀번호: Secrets Manager에 자동 저장
 *
 * 의존성:
 * - NetworkStack: DB Subnet ID (Fn.importValue)
 * - SecurityStack: RDS Security Group ID (Fn.importValue)
 */
export class DatabaseStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ============================================================
    // 다른 스택에서 내보낸 값 참조
    // ============================================================

    // NetworkStack에서 내보낸 DB Subnet ID
    const dbSubnetAId = cdk.Fn.importValue('ChaosTwin-DbSubnetAId');
    const dbSubnetBId = cdk.Fn.importValue('ChaosTwin-DbSubnetBId');

    // SecurityStack에서 내보낸 RDS Security Group ID
    const rdsSecurityGroupId = cdk.Fn.importValue('ChaosTwin-RdsSecurityGroupId');

    // ============================================================
    // Secrets Manager: RDS 마스터 비밀번호 자동 생성
    // ============================================================
    const dbSecret = new secretsmanager.CfnSecret(this, 'RdsCredentialsSecret', {
      name: 'chaos-twin/rds-credentials',
      description: 'RDS PostgreSQL master user password',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'chaosadmin' }),
        generateStringKey: 'password',
        excludePunctuation: true,
        passwordLength: 30,
      },
    });

    // ============================================================
    // DB Subnet Group: DB Subnet A, B를 묶어서 RDS 배치 대상 지정
    // ============================================================
    const dbSubnetGroup = new rds.CfnDBSubnetGroup(this, 'DbSubnetGroup', {
      dbSubnetGroupDescription: 'Chaos Twin RDS DB Subnet Group (DB Subnet A, B)',
      dbSubnetGroupName: 'chaos-twin-db-subnet-group',
      subnetIds: [dbSubnetAId, dbSubnetBId],
      tags: [{ key: 'Name', value: 'chaos-twin-db-subnet-group' }],
    });

    // ============================================================
    // DB 파라미터 그룹: PostgreSQL 16 기본 설정
    // ============================================================
    const dbParameterGroup = new rds.CfnDBParameterGroup(this, 'DbParameterGroup', {
      family: 'postgres16',
      description: 'Chaos Twin RDS PostgreSQL 16 parameter group',
      parameters: {
        // 로그 설정: 느린 쿼리 로깅 활성화
        'log_min_duration_statement': '1000',
        // 타임존 설정
        'timezone': 'UTC',
      },
      tags: [{ key: 'Name', value: 'chaos-twin-db-params' }],
    });

    // ============================================================
    // RDS PostgreSQL 인스턴스 생성
    // - db.t3.micro (Free Tier)
    // - 단일 AZ (Multi-AZ 비활성화)
    // - Secrets Manager 동적 참조로 비밀번호 설정
    // ============================================================
    const dbInstance = new rds.CfnDBInstance(this, 'RdsInstance', {
      dbInstanceIdentifier: 'chaos-twin-db',
      dbInstanceClass: 'db.t3.micro',
      engine: 'postgres',
      engineVersion: '16',
      allocatedStorage: '20',
      storageType: 'gp2',
      dbName: 'chaostwin',
      port: '5432',
      masterUsername: cdk.Fn.join('', [
        '{{resolve:secretsmanager:',
        dbSecret.ref,
        ':SecretString:username}}',
      ]),
      masterUserPassword: cdk.Fn.join('', [
        '{{resolve:secretsmanager:',
        dbSecret.ref,
        ':SecretString:password}}',
      ]),
      dbSubnetGroupName: dbSubnetGroup.dbSubnetGroupName,
      dbParameterGroupName: dbParameterGroup.ref,
      vpcSecurityGroups: [rdsSecurityGroupId],
      multiAz: false,
      publiclyAccessible: false,
      storageEncrypted: true,
      backupRetentionPeriod: 7,
      deletionProtection: false,
      copyTagsToSnapshot: true,
      tags: [{ key: 'Name', value: 'chaos-twin-rds' }],
    });

    // DB Subnet Group과 파라미터 그룹이 먼저 생성되어야 함
    dbInstance.addDependency(dbSubnetGroup);
    dbInstance.addDependency(dbParameterGroup);

    // ============================================================
    // CloudFormation 출력값 (다른 스택에서 참조용)
    // ============================================================
    new cdk.CfnOutput(this, 'RdsEndpoint', {
      value: dbInstance.attrEndpointAddress,
      description: 'RDS PostgreSQL 엔드포인트 주소',
      exportName: 'ChaosTwin-RdsEndpoint',
    });

    new cdk.CfnOutput(this, 'RdsPort', {
      value: dbInstance.attrEndpointPort,
      description: 'RDS PostgreSQL 포트',
      exportName: 'ChaosTwin-RdsPort',
    });

    new cdk.CfnOutput(this, 'RdsSecretArn', {
      value: dbSecret.ref,
      description: 'RDS 자격 증명 Secrets Manager ARN',
      exportName: 'ChaosTwin-RdsSecretArn',
    });

    new cdk.CfnOutput(this, 'RdsDbName', {
      value: 'chaostwin',
      description: 'RDS 데이터베이스 이름',
      exportName: 'ChaosTwin-RdsDbName',
    });
  }
}
