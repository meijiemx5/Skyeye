import * as path from 'path';
import * as fs from 'fs';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';

interface SkyeyeFrontendStackProps extends cdk.StackProps {
  apiUrl: string;
  /** API Gateway execute-api host (no scheme/path) */
  apiDomain: string;
  /** API Gateway stage name (becomes the API origin path) */
  apiStage: string;
  isChina: boolean;
  /** Optional custom domain (ICP-filed) to serve the site from, e.g. ruianwy.site */
  domainName?: string;
  /** IAM server-certificate id for the custom domain (China CloudFront uses IAM certs) */
  iamCertId?: string;
}

export class SkyeyeFrontendStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: SkyeyeFrontendStackProps) {
    super(scope, id, props);

    // ============================================================
    // S3 Bucket for Frontend Static Files
    // ============================================================
    const siteBucket = new s3.Bucket(this, 'SiteBucket', {
      bucketName: `skyeye-frontend-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // ============================================================
    // CloudFront Distribution
    // ============================================================
    const oai = new cloudfront.OriginAccessIdentity(this, 'OAI');
    siteBucket.grantRead(oai);

    // China region compatibility flags
    const isChina = props.isChina;

    // API Gateway origin. originPath = the stage ('/api'), so a request to
    // /api/projects reaches API GW as /api/api/projects, which Mangum strips
    // the stage from -> FastAPI sees /api/projects. Serving the API under the
    // same (ICP-filed) CloudFront domain both bypasses the China execute-api
    // block and makes the frontend same-origin (no CORS).
    const apiOrigin = new origins.HttpOrigin(props.apiDomain, {
      originPath: `/${props.apiStage}`,
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
    });

    // The API must not be cached and must forward the Authorization header
    // (JWT) and query strings. In China, managed cache/origin-request policies
    // are unavailable, so caching/forwarding is handled by the legacy
    // ForwardedValues override applied further below.
    const apiBehavior: cloudfront.BehaviorOptions = {
      origin: apiOrigin,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      ...(!isChina
        ? { originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER }
        : {}),
    };

    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(siteBucket, {
          originAccessIdentity: oai,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        ...(!isChina ? { cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED } : {}),
      },
      additionalBehaviors: {
        '/api/*': apiBehavior,
      },
      defaultRootObject: 'index.html',
      enableIpv6: !isChina,
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
    });

    // China regions do not support managed CachePolicyId/OriginRequestPolicyId -
    // replace them with the legacy ForwardedValues on both behaviors.
    if (isChina) {
      const cfnDist = distribution.node.defaultChild as cloudfront.CfnDistribution;

      // Default behavior (S3 static site): no forwarding needed.
      cfnDist.addPropertyDeletionOverride('DistributionConfig.DefaultCacheBehavior.CachePolicyId');
      cfnDist.addPropertyOverride('DistributionConfig.DefaultCacheBehavior.ForwardedValues', {
        QueryString: false,
      });

      // /api/* behavior (index 0): must not cache and must forward the JWT
      // Authorization header + query strings, or every API call would 401.
      cfnDist.addPropertyDeletionOverride('DistributionConfig.CacheBehaviors.0.CachePolicyId');
      cfnDist.addPropertyDeletionOverride('DistributionConfig.CacheBehaviors.0.OriginRequestPolicyId');
      cfnDist.addPropertyOverride('DistributionConfig.CacheBehaviors.0.ForwardedValues', {
        QueryString: true,
        Headers: ['Authorization'],
      });
      cfnDist.addPropertyOverride('DistributionConfig.CacheBehaviors.0.MinTTL', 0);
      cfnDist.addPropertyOverride('DistributionConfig.CacheBehaviors.0.DefaultTTL', 0);
      cfnDist.addPropertyOverride('DistributionConfig.CacheBehaviors.0.MaxTTL', 0);
    }

    // Custom domain + IAM certificate (e.g. the ICP-filed domain in China).
    // Declaring them here means CDK owns the alias/cert, so a redeploy no
    // longer wipes a manually-attached one. China CloudFront uses IAM server
    // certificates (referenced by id), applied via a low-level override.
    if (props.domainName && props.iamCertId) {
      const cfnDist = distribution.node.defaultChild as cloudfront.CfnDistribution;
      cfnDist.addPropertyOverride('DistributionConfig.Aliases', [props.domainName]);
      cfnDist.addPropertyOverride('DistributionConfig.ViewerCertificate', {
        IamCertificateId: props.iamCertId,
        SslSupportMethod: 'sni-only',
        MinimumProtocolVersion: 'TLSv1.2_2021',
      });
    }

    // ============================================================
    // Deploy Frontend Build (if dist exists)
    // ============================================================
    const frontendBuildPath = path.join(__dirname, '..', '..', 'frontend', 'dist');

    if (fs.existsSync(frontendBuildPath)) {
      new s3deploy.BucketDeployment(this, 'DeploySite', {
        sources: [s3deploy.Source.asset(frontendBuildPath)],
        destinationBucket: siteBucket,
        distribution,
        distributionPaths: ['/*'],
      });
    }

    // ============================================================
    // Outputs
    // ============================================================
    new cdk.CfnOutput(this, 'SiteUrl', {
      value: `https://${distribution.distributionDomainName}`,
      description: 'CloudFront Distribution URL',
    });

    new cdk.CfnOutput(this, 'BucketName', {
      value: siteBucket.bucketName,
      description: 'Frontend S3 Bucket Name',
    });

    new cdk.CfnOutput(this, 'DistributionId', {
      value: distribution.distributionId,
      description: 'CloudFront Distribution ID',
    });

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: props.apiUrl,
      description: 'Backend API URL',
    });
  }
}
