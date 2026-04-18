#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { SkyeyeBackendStack } from '../lib/backend-stack';
import { SkyeyeFrontendStack } from '../lib/frontend-stack';

const app = new cdk.App();

const env: cdk.Environment = {
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  account: process.env.CDK_DEFAULT_ACCOUNT,
};

const backend = new SkyeyeBackendStack(app, 'SkyeyeBackend', { env });
const frontend = new SkyeyeFrontendStack(app, 'SkyeyeFrontend', {
  env,
  apiUrl: backend.apiUrl,
});

frontend.addDependency(backend);
