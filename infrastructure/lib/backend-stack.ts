import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';

export class SkyeyeBackendStack extends cdk.Stack {
  /** API Gateway URL - exposed for frontend stack */
  public readonly apiUrl: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ============================================================
    // DynamoDB Table - Single Table Design
    // ============================================================
    const table = new dynamodb.Table(this, 'SkyeyeTable', {
      tableName: 'skyeye-dev',
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: false,
    });

    // GSI1
    table.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'GSI1SK', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI2
    table.addGlobalSecondaryIndex({
      indexName: 'GSI2',
      partitionKey: { name: 'GSI2PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'GSI2SK', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ============================================================
    // S3 Bucket for Attachments
    // ============================================================
    const attachmentsBucket = new s3.Bucket(this, 'AttachmentsBucket', {
      bucketName: `skyeye-attachments-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.PUT, s3.HttpMethods.POST],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(90),
        },
      ],
    });

    // ============================================================
    // Lambda Function
    // ============================================================
    const backendPath = path.join(__dirname, '..', '..', 'backend');

    const apiLambda = new lambda.Function(this, 'ApiFunction', {
      functionName: 'skyeye-api',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'lambda_handler.handler',
      code: lambda.Code.fromAsset(backendPath, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
          local: {
            tryBundle(outputDir: string) {
              const { execSync } = require('child_process');
              try {
                execSync(`pip3 install -r ${backendPath}/requirements.txt -t ${outputDir} --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all:`, { stdio: 'inherit' });
                execSync(`cp -r ${backendPath}/app ${outputDir}/app`);
                execSync(`cp ${backendPath}/lambda_handler.py ${outputDir}/lambda_handler.py`);
                return true;
              } catch (e) {
                console.error('Local bundling failed:', e);
                return false;
              }
            },
          },
        },
      }),
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        DYNAMODB_TABLE_NAME: table.tableName,
        S3_BUCKET_NAME: attachmentsBucket.bucketName,
        AWS_REGION_NAME: this.region,
        JWT_SECRET_KEY: 'skyeye-jwt-secret-change-in-production-2024',
        APP_ENV: 'dev',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant permissions
    table.grantReadWriteData(apiLambda);
    attachmentsBucket.grantReadWrite(apiLambda);

    // ============================================================
    // API Gateway
    // ============================================================
    const api = new apigw.LambdaRestApi(this, 'SkyeyeApi', {
      restApiName: 'skyeye-api',
      handler: apiLambda,
      proxy: true,
      deployOptions: {
        stageName: 'api',
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigw.Cors.ALL_ORIGINS,
        allowMethods: apigw.Cors.ALL_METHODS,
        allowHeaders: ['*'],
      },
    });

    // Store API URL
    this.apiUrl = api.url;

    // ============================================================
    // Outputs
    // ============================================================
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
      description: 'API Gateway URL',
    });

    new cdk.CfnOutput(this, 'TableName', {
      value: table.tableName,
      description: 'DynamoDB Table Name',
    });

    new cdk.CfnOutput(this, 'BucketName', {
      value: attachmentsBucket.bucketName,
      description: 'S3 Attachments Bucket',
    });

    new cdk.CfnOutput(this, 'LambdaArn', {
      value: apiLambda.functionArn,
      description: 'Lambda Function ARN',
    });
  }
}
