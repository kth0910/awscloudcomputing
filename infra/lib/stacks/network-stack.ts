import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

/**
 * NetworkStack: VPC, Subnet, NAT Gateway, Internet Gateway 등 네트워크 인프라 정의
 *
 * CIDR 할당:
 * - VPC: 10.0.0.0/16
 * - Public Subnet A: 10.0.1.0/24 (us-east-1a) — ALB, NAT Gateway
 * - Public Subnet B: 10.0.2.0/24 (us-east-1b) — ALB
 * - Private Subnet A: 10.0.10.0/24 (us-east-1a) — EC2 Core Engine, Lambda ENI
 * - Private Subnet B: 10.0.11.0/24 (us-east-1b) — Lambda ENI
 * - DB Subnet A: 10.0.20.0/24 (us-east-1a) — RDS Primary
 * - DB Subnet B: 10.0.21.0/24 (us-east-1b) — RDS Subnet Group (HA 대비)
 *
 * 라우팅:
 * - Public Route Table: 0.0.0.0/0 → Internet Gateway
 * - Private Route Table: 0.0.0.0/0 → NAT Gateway (us-east-1a 단일)
 * - DB Route Table: 로컬 트래픽만 (인터넷 라우팅 없음)
 */
export class NetworkStack extends cdk.Stack {
  // 다른 스택에서 참조할 수 있도록 public readonly 속성으로 노출
  public readonly vpc: ec2.CfnVPC;
  public readonly internetGateway: ec2.CfnInternetGateway;
  public readonly natGateway: ec2.CfnNatGateway;

  // 퍼블릭 서브넷
  public readonly publicSubnetA: ec2.CfnSubnet;
  public readonly publicSubnetB: ec2.CfnSubnet;

  // 프라이빗 서브넷
  public readonly privateSubnetA: ec2.CfnSubnet;
  public readonly privateSubnetB: ec2.CfnSubnet;

  // DB 서브넷
  public readonly dbSubnetA: ec2.CfnSubnet;
  public readonly dbSubnetB: ec2.CfnSubnet;

  // 라우팅 테이블
  public readonly publicRouteTable: ec2.CfnRouteTable;
  public readonly privateRouteTable: ec2.CfnRouteTable;
  public readonly dbRouteTable: ec2.CfnRouteTable;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ============================================================
    // VPC 생성 (10.0.0.0/16)
    // ============================================================
    this.vpc = new ec2.CfnVPC(this, 'ChaosTwinVpc', {
      cidrBlock: '10.0.0.0/16',
      enableDnsSupport: true,
      enableDnsHostnames: true,
      tags: [{ key: 'Name', value: 'chaos-twin-vpc' }],
    });

    // ============================================================
    // Internet Gateway 생성 및 VPC 연결
    // ============================================================
    this.internetGateway = new ec2.CfnInternetGateway(this, 'InternetGateway', {
      tags: [{ key: 'Name', value: 'chaos-twin-igw' }],
    });

    new ec2.CfnVPCGatewayAttachment(this, 'IgwAttachment', {
      vpcId: this.vpc.ref,
      internetGatewayId: this.internetGateway.ref,
    });

    // ============================================================
    // 퍼블릭 서브넷 (ALB, NAT Gateway)
    // ============================================================
    this.publicSubnetA = new ec2.CfnSubnet(this, 'PublicSubnetA', {
      vpcId: this.vpc.ref,
      cidrBlock: '10.0.1.0/24',
      availabilityZone: 'us-east-1a',
      mapPublicIpOnLaunch: true,
      tags: [{ key: 'Name', value: 'chaos-twin-public-a' }],
    });

    this.publicSubnetB = new ec2.CfnSubnet(this, 'PublicSubnetB', {
      vpcId: this.vpc.ref,
      cidrBlock: '10.0.2.0/24',
      availabilityZone: 'us-east-1b',
      mapPublicIpOnLaunch: true,
      tags: [{ key: 'Name', value: 'chaos-twin-public-b' }],
    });

    // ============================================================
    // 프라이빗 서브넷 (EC2 Core Engine, Lambda ENI)
    // ============================================================
    this.privateSubnetA = new ec2.CfnSubnet(this, 'PrivateSubnetA', {
      vpcId: this.vpc.ref,
      cidrBlock: '10.0.10.0/24',
      availabilityZone: 'us-east-1a',
      tags: [{ key: 'Name', value: 'chaos-twin-private-a' }],
    });

    this.privateSubnetB = new ec2.CfnSubnet(this, 'PrivateSubnetB', {
      vpcId: this.vpc.ref,
      cidrBlock: '10.0.11.0/24',
      availabilityZone: 'us-east-1b',
      tags: [{ key: 'Name', value: 'chaos-twin-private-b' }],
    });

    // ============================================================
    // DB 서브넷 (RDS Primary, RDS Subnet Group)
    // ============================================================
    this.dbSubnetA = new ec2.CfnSubnet(this, 'DbSubnetA', {
      vpcId: this.vpc.ref,
      cidrBlock: '10.0.20.0/24',
      availabilityZone: 'us-east-1a',
      tags: [{ key: 'Name', value: 'chaos-twin-db-a' }],
    });

    this.dbSubnetB = new ec2.CfnSubnet(this, 'DbSubnetB', {
      vpcId: this.vpc.ref,
      cidrBlock: '10.0.21.0/24',
      availabilityZone: 'us-east-1b',
      tags: [{ key: 'Name', value: 'chaos-twin-db-b' }],
    });

    // ============================================================
    // NAT Gateway (us-east-1a 단일 — 비용 최적화)
    // ============================================================
    const natEip = new ec2.CfnEIP(this, 'NatEip', {
      domain: 'vpc',
      tags: [{ key: 'Name', value: 'chaos-twin-nat-eip' }],
    });

    this.natGateway = new ec2.CfnNatGateway(this, 'NatGateway', {
      subnetId: this.publicSubnetA.ref,
      allocationId: natEip.attrAllocationId,
      tags: [{ key: 'Name', value: 'chaos-twin-nat-gw' }],
    });

    // ============================================================
    // 퍼블릭 라우팅 테이블: 0.0.0.0/0 → Internet Gateway
    // ============================================================
    this.publicRouteTable = new ec2.CfnRouteTable(this, 'PublicRouteTable', {
      vpcId: this.vpc.ref,
      tags: [{ key: 'Name', value: 'chaos-twin-public-rt' }],
    });

    new ec2.CfnRoute(this, 'PublicDefaultRoute', {
      routeTableId: this.publicRouteTable.ref,
      destinationCidrBlock: '0.0.0.0/0',
      gatewayId: this.internetGateway.ref,
    });

    // 퍼블릭 서브넷에 라우팅 테이블 연결
    new ec2.CfnSubnetRouteTableAssociation(this, 'PublicSubnetARouteAssoc', {
      subnetId: this.publicSubnetA.ref,
      routeTableId: this.publicRouteTable.ref,
    });

    new ec2.CfnSubnetRouteTableAssociation(this, 'PublicSubnetBRouteAssoc', {
      subnetId: this.publicSubnetB.ref,
      routeTableId: this.publicRouteTable.ref,
    });

    // ============================================================
    // 프라이빗 라우팅 테이블: 0.0.0.0/0 → NAT Gateway (us-east-1a)
    // ============================================================
    this.privateRouteTable = new ec2.CfnRouteTable(this, 'PrivateRouteTable', {
      vpcId: this.vpc.ref,
      tags: [{ key: 'Name', value: 'chaos-twin-private-rt' }],
    });

    new ec2.CfnRoute(this, 'PrivateDefaultRoute', {
      routeTableId: this.privateRouteTable.ref,
      destinationCidrBlock: '0.0.0.0/0',
      natGatewayId: this.natGateway.ref,
    });

    // 프라이빗 서브넷에 라우팅 테이블 연결
    new ec2.CfnSubnetRouteTableAssociation(this, 'PrivateSubnetARouteAssoc', {
      subnetId: this.privateSubnetA.ref,
      routeTableId: this.privateRouteTable.ref,
    });

    new ec2.CfnSubnetRouteTableAssociation(this, 'PrivateSubnetBRouteAssoc', {
      subnetId: this.privateSubnetB.ref,
      routeTableId: this.privateRouteTable.ref,
    });

    // ============================================================
    // DB 라우팅 테이블: 로컬 트래픽만 (인터넷 라우팅 없음)
    // ============================================================
    this.dbRouteTable = new ec2.CfnRouteTable(this, 'DbRouteTable', {
      vpcId: this.vpc.ref,
      tags: [{ key: 'Name', value: 'chaos-twin-db-rt' }],
    });

    // DB 서브넷에 라우팅 테이블 연결 (로컬 라우팅만 — 기본 제공)
    new ec2.CfnSubnetRouteTableAssociation(this, 'DbSubnetARouteAssoc', {
      subnetId: this.dbSubnetA.ref,
      routeTableId: this.dbRouteTable.ref,
    });

    new ec2.CfnSubnetRouteTableAssociation(this, 'DbSubnetBRouteAssoc', {
      subnetId: this.dbSubnetB.ref,
      routeTableId: this.dbRouteTable.ref,
    });

    // ============================================================
    // CloudFormation 출력값 (다른 스택에서 참조용)
    // ============================================================
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.ref,
      description: 'Chaos Twin VPC ID',
      exportName: 'ChaosTwin-VpcId',
    });

    new cdk.CfnOutput(this, 'PublicSubnetAId', {
      value: this.publicSubnetA.ref,
      description: 'Public Subnet A ID (us-east-1a)',
      exportName: 'ChaosTwin-PublicSubnetAId',
    });

    new cdk.CfnOutput(this, 'PublicSubnetBId', {
      value: this.publicSubnetB.ref,
      description: 'Public Subnet B ID (us-east-1b)',
      exportName: 'ChaosTwin-PublicSubnetBId',
    });

    new cdk.CfnOutput(this, 'PrivateSubnetAId', {
      value: this.privateSubnetA.ref,
      description: 'Private Subnet A ID (us-east-1a)',
      exportName: 'ChaosTwin-PrivateSubnetAId',
    });

    new cdk.CfnOutput(this, 'PrivateSubnetBId', {
      value: this.privateSubnetB.ref,
      description: 'Private Subnet B ID (us-east-1b)',
      exportName: 'ChaosTwin-PrivateSubnetBId',
    });

    new cdk.CfnOutput(this, 'DbSubnetAId', {
      value: this.dbSubnetA.ref,
      description: 'DB Subnet A ID (us-east-1a)',
      exportName: 'ChaosTwin-DbSubnetAId',
    });

    new cdk.CfnOutput(this, 'DbSubnetBId', {
      value: this.dbSubnetB.ref,
      description: 'DB Subnet B ID (us-east-1b)',
      exportName: 'ChaosTwin-DbSubnetBId',
    });

    new cdk.CfnOutput(this, 'NatGatewayId', {
      value: this.natGateway.ref,
      description: 'NAT Gateway ID (us-east-1a)',
      exportName: 'ChaosTwin-NatGatewayId',
    });
  }
}
