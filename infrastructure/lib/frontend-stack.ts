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

    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(siteBucket, {
          originAccessIdentity: oai,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      defaultRootObject: 'index.html',
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
