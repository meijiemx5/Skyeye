#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { SkyeyeBackendStack } from '../lib/backend-stack';
import { SkyeyeFrontendStack } from '../lib/frontend-stack';

const app = new cdk.App();

// CDK CLI sets CDK_DEFAULT_REGION from the profile, but we also accept
// SKYEYE_REGION as explicit override for China region detection
const region = process.env.SKYEYE_REGION || process.env.CDK_DEFAULT_REGION || 'us-east-1';
const env: cdk.Environment = {
  region,
  account: process.env.CDK_DEFAULT_ACCOUNT,
};

// Detect China region for conditional resource configuration
const isChina = region.startsWith('cn-');

// Optional custom domain + IAM cert for the frontend CloudFront (e.g. the
// ICP-filed domain required in China). Provided via env so CDK owns them and
// a redeploy no longer wipes a manually-attached alias/cert.
const siteDomainName = process.env.SKYEYE_SITE_DOMAIN || undefined;
const siteIamCertId = process.env.SKYEYE_SITE_IAM_CERT_ID || undefined;

const backend = new SkyeyeBackendStack(app, 'SkyeyeBackend', { env, isChina });
const frontend = new SkyeyeFrontendStack(app, 'SkyeyeFrontend', {
  env,
  apiUrl: backend.apiUrl,
  apiDomain: backend.apiDomain,
  apiStage: backend.apiStage,
  isChina,
  domainName: siteDomainName,
  iamCertId: siteIamCertId,
});

frontend.addDependency(backend);
