# 中国区 API 暴露方案（www 子域名直连）

> 本文是**架构方案**（为什么用 `www` 子域名直连）。运维排障（403/CORS/路径/证书/DNS 等踩坑）见
> [中国区部署踩坑与排查手册.md](中国区部署踩坑与排查手册.md)。
>
> ⚠️ 后续修正：下文"根因"一节曾判断 execute-api 默认域名被中国区平台封锁而 403。**这一判断已被推翻**——
> 真正的 403 根因是 API Gateway `api` stage 服务了陈旧的部署快照（详见排查手册"坑 1"）。
> 重新发布 stage 后，execute-api 默认域名也能正常返回 200。但**生产仍应走自定义域名**
> `www.ruianwy.site`（备案合规 + 路径干净），本方案的架构结论不变。

## 问题根因（历史判断，已被排查手册"坑 1"修正）

打开 CN 站点 `https://ruianwy.site`，页面能加载，但所有数据请求 403。逐层排查：

| 检查项 | 结果 |
|---|---|
| CN Lambda 应用 | ✅ 正常（直连 invoke 返回 `200 healthy`） |
| API Gateway stage / 方法 / 集成 / Lambda 权限 | ✅ 全部正确 |
| 前端调用 execute-api 默认域名 | ❌ 被平台 403 拦截 |

**根因**：AWS 中国区**禁止**通过 `xxx.execute-api.cn-northwest-1.amazonaws.com.cn`
默认域名对外服务，任何来源（含 CloudFront 回源）都返回 `403 AccessDeniedException`。
实测：非默认 Host 访问返回的是 API Gateway 的 `{"message":"Forbidden"}`（不同错误），
证明**封锁只针对默认 execute-api 域名字面量**——绑一个自定义域名即可绕过。

## 为什么不走 CloudFront /api/*（已否决）

设想让 `ruianwy.site/api/*` 经 CloudFront 回源到 API Gateway custom domain。
但 **CloudFront 不允许覆盖回源的 Host 头**，而 API Gateway custom domain 靠 Host 匹配，
所以回源永远匹配不上 —— 此路不通。

## 最终方案：API 用 www 子域名，浏览器直连

```
ruianwy.site       → CloudFront（IAM 证书） → S3 前端       （不变）
www.ruianwy.site   → API Gateway 自定义域名（ACM 证书） → Lambda   （新增）
```

- 前端 `VITE_API_URL = https://www.ruianwy.site`，浏览器直接调 `www.ruianwy.site/api/...`
- `www.ruianwy.site` 是 API Gateway 的 custom domain，Host 匹配 → 正常路由，不触发默认域名封锁
- 页面 `ruianwy.site` → API `www.ruianwy.site` 属跨域，但后端 `allow_origins=["*"]` 已允许
  （与 Global 版前端调 execute-api 的跨域模式一致，已验证可用）
- 证书 SAN 覆盖 `ruianwy.site` + `www.ruianwy.site`，两个域名共用同一张证书
- 中国区 ICP 备案按主域名，`www` 子域名自动包含，无需单独备案

### 路径映射

API Gateway custom domain 的 base path mapping 映射到 `api` stage（base path 为空）。
FastAPI 路由前缀是 `/api/xxx`，Mangum 不把 stage 计入路径，所以：
```
www.ruianwy.site/api/projects → 域名根映射到 api stage → FastAPI /api/projects ✅
```
（注意：直连自定义域名**不再有**execute-api 那种 `/api/api/...` 双前缀）

## 证书要求（关键）

- API Gateway Regional custom domain **必须用 ACM 证书**，且**与 API 同区域**（cn-northwest-1）。
- 不能用 IAM 证书（IAM 证书只有 CloudFront/ELB 能用）。
- 前端 CloudFront 仍用 IAM 证书（CN CloudFront 的要求），两者是不同的证书体系。
- 同一张 `ruianwy.site`(+www) 证书需要**导入两处**：IAM（给 CloudFront）+ ACM cn-northwest-1（给 API）。

## CDK 改动（已实现）

- **backend-stack**：当传入 `apiCustomDomain` + `apiCertArn` 时，创建 API Gateway
  Regional custom domain（ACM 证书，TLS_1_2）+ base path mapping 到 api stage；
  输出 `ApiCustomDomainTarget`（DNS CNAME 目标）和 `ApiCustomDomainUrl`。
- **frontend-stack**：移除走不通的 `/api/*` CloudFront 行为；保留前端自定义域名
  （alias + IAM 证书，CDK 拥有，redeploy 不再被抹）。
- **deploy.sh**：改用环境变量配置中国区；`SKYEYE_API_DOMAIN` 设置时，前端以
  `VITE_API_URL=https://<api-domain>` 构建，直连 API 自定义域名。

## 部署命令（China）

```bash
SKYEYE_SITE_DOMAIN=ruianwy.site \
SKYEYE_SITE_IAM_CERT_ID=ASCARF4GALIVNP3ZRZS2J \
SKYEYE_API_DOMAIN=www.ruianwy.site \
SKYEYE_API_CERT_ARN=arn:aws-cn:acm:cn-northwest-1:081348549162:certificate/b8904700-70cf-4d14-9b2c-6a46c5c7bd99 \
./deploy.sh skyeye cn-northwest-1
```

## 你需要在控制台/DNS 完成的事

1. **证书**：`ruianwy.site`(+www) 证书已导入 ACM **cn-northwest-1**
   （ARN `...certificate/b8904700-...`）。✅
2. **DNS**：部署后取输出 `ApiCustomDomainTarget`（形如 `d-xxxx.execute-api.cn-northwest-1.amazonaws.com.cn`），
   在域名解析处给 `www.ruianwy.site` 加一条 **CNAME** 指向它。
3. 等 DNS 生效 + CloudFront/域名传播（几分钟到几十分钟）。

## 验证清单

- [ ] `curl https://www.ruianwy.site/api/health` → `{"status":"healthy"}`
- [ ] `curl https://www.ruianwy.site/api/api/projects` → 401/403（正常，缺 token；注意直连是单 /api）
      —— 修正：直连自定义域名是 `curl https://www.ruianwy.site/api/projects`
- [ ] 浏览器登录 `ruianwy.site` → Network 里请求打到 `www.ruianwy.site/api/...` 且成功
- [ ] 附件上传/下载正常（presigned URL 指向 CN S3 桶）
