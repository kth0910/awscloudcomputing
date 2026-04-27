import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * FrontendStack: S3 버킷 + CloudFront Distribution + OAI 구성
 *
 * Next.js 정적 빌드 결과물을 S3에 배포하고,
 * CloudFront를 통해 서비스한다.
 * OAI(Origin Access Identity)를 사용하여 S3 직접 접근을 차단한다.
 *
 * 구성 요소:
 * - S3 버킷: chaos-twin-dashboard-{accountId} (고유 이름)
 * - CloudFront Distribution: S3 Origin + OAI
 * - S3 버킷 정책: OAI에서만 GetObject 허용
 * - 기본 문서: index.html
 * - 에러 문서: index.html (SPA 라우팅 지원)
 */
export class FrontendStack extends cdk.Stack {
  // CloudFront Distribution (외부 참조용)
  public readonly distribution: cloudfront.CloudFrontWebDistribution;
  // S3 대시보드 버킷 (외부 참조용)
  public readonly dashboardBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const albDnsName = cdk.Fn.importValue('ChaosTwin-AlbDnsName');

    // ============================================================
    // S3 버킷: Next.js 정적 자산 저장소
    // ============================================================
    // 버킷 이름에 accountId를 포함하여 글로벌 고유성 보장
    this.dashboardBucket = new s3.Bucket(this, 'DashboardBucket', {
      bucketName: `chaos-twin-dashboard-${cdk.Aws.ACCOUNT_ID}`,
      // CloudFront OAI를 통해서만 접근하므로 퍼블릭 액세스 차단
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      // 스택 삭제 시 버킷도 함께 삭제 (개발 환경 편의)
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      // 정적 웹사이트 호스팅은 CloudFront에서 처리하므로 비활성화
      encryption: s3.BucketEncryption.S3_MANAGED,
    });

    // ============================================================
    // CloudFront Origin Access Identity (OAI)
    // S3 버킷에 대한 CloudFront 전용 접근 ID
    // ============================================================
    const oai = new cloudfront.OriginAccessIdentity(this, 'DashboardOAI', {
      comment: 'Chaos Twin 대시보드 S3 버킷 접근용 OAI',
    });

    // ============================================================
    // S3 버킷 정책: OAI에서만 GetObject 허용
    // ============================================================
    this.dashboardBucket.addToResourcePolicy(new iam.PolicyStatement({
      sid: 'AllowCloudFrontOAIRead',
      effect: iam.Effect.ALLOW,
      principals: [oai.grantPrincipal],
      actions: ['s3:GetObject'],
      resources: [this.dashboardBucket.arnForObjects('*')],
    }));

    // ============================================================
    // CloudFront Distribution: S3 Origin + OAI
    // ============================================================
    this.distribution = new cloudfront.CloudFrontWebDistribution(this, 'DashboardDistribution', {
      // S3 Origin 설정
      originConfigs: [
        {
          s3OriginSource: {
            s3BucketSource: this.dashboardBucket,
            originAccessIdentity: oai,
          },
          behaviors: [
            {
              isDefaultBehavior: true,
              // 정적 자산이므로 GET/HEAD만 허용
              allowedMethods: cloudfront.CloudFrontAllowedMethods.GET_HEAD,
              // 캐시 최적화를 위해 압축 활성화
              compress: true,
              viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            },
          ],
        },
        {
          customOriginSource: {
            domainName: albDnsName,
            originProtocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            httpPort: 80,
          },
          behaviors: [
            {
              pathPattern: '/api/*',
              allowedMethods: cloudfront.CloudFrontAllowedMethods.ALL,
              forwardedValues: {
                queryString: true,
                headers: ['Authorization', 'Content-Type'],
              },
              defaultTtl: cdk.Duration.seconds(0),
              maxTtl: cdk.Duration.seconds(0),
              minTtl: cdk.Duration.seconds(0),
              viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            },
          ],
        },
      ],
      // 기본 루트 문서: index.html
      defaultRootObject: 'index.html',
      // SPA 라우팅 지원: 404 에러 시 index.html로 리다이렉트
      errorConfigurations: [
        {
          errorCode: 403,
          responseCode: 200,
          responsePagePath: '/index.html',
          errorCachingMinTtl: 10,
        },
        {
          errorCode: 404,
          responseCode: 200,
          responsePagePath: '/index.html',
          errorCachingMinTtl: 10,
        },
      ],
      // 비용 최적화: 북미/유럽만 사용
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      comment: 'Chaos Twin 대시보드 CloudFront Distribution',
    });

    // ============================================================
    // CloudFormation 출력값
    // ============================================================
    new cdk.CfnOutput(this, 'DashboardBucketName', {
      value: this.dashboardBucket.bucketName,
      description: '대시보드 S3 버킷 이름',
      exportName: 'ChaosTwin-DashboardBucketName',
    });

    new cdk.CfnOutput(this, 'DashboardDistributionDomainName', {
      value: this.distribution.distributionDomainName,
      description: 'CloudFront Distribution 도메인 이름',
      exportName: 'ChaosTwin-DashboardDistributionDomainName',
    });

    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: '대시보드 접속 URL',
      exportName: 'ChaosTwin-DashboardUrl',
    });
  }
}
