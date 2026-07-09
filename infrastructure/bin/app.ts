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

// Frontend CloudFront custom domain + IAM cert (the ICP-filed domain, e.g.
// ruianwy.site). CDK owns them so a redeploy no longer wipes a manual alias.
const siteDomainName = process.env.SKYEYE_SITE_DOMAIN || undefined;
const siteIamCertId = process.env.SKYEYE_SITE_IAM_CERT_ID || undefined;

// API Gateway custom domain + ACM cert (e.g. www.ruianwy.site). Required in
// China: the SPA calls this instead of the blocked execute-api endpoint.
const apiCustomDomain = process.env.SKYEYE_API_DOMAIN || undefined;
const apiCertArn = process.env.SKYEYE_API_CERT_ARN || undefined;

const backend = new SkyeyeBackendStack(app, 'SkyeyeBackend', {
  env,
  isChina,
  apiCustomDomain,
  apiCertArn,
});
const frontend = new SkyeyeFrontendStack(app, 'SkyeyeFrontend', {
  env,
  apiUrl: backend.apiUrl,
  isChina,
  domainName: siteDomainName,
  iamCertId: siteIamCertId,
});

frontend.addDependency(backend);
