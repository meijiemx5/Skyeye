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

const backend = new SkyeyeBackendStack(app, 'SkyeyeBackend', { env, isChina });
const frontend = new SkyeyeFrontendStack(app, 'SkyeyeFrontend', {
  env,
  apiUrl: backend.apiUrl,
  isChina,
});

frontend.addDependency(backend);
