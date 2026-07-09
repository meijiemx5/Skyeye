# 中国区 API 通过 CloudFront 暴露方案

## 问题根因

打开 CN 站点 `https://ruianwy.site`,页面能加载(CloudFront + 备案域名 + IAM 证书正常),
但所有数据请求 403 失败。逐层排查结论:

| 检查项 | 结果 |
|---|---|
| CN Lambda 应用 | ✅ 正常(直连 invoke 返回 `200 healthy`) |
| API Gateway stage(`api`)/ 方法(`ANY`)/ 集成 URI | ✅ 全部正确 |
| Lambda 的 API Gateway invoke 权限 | ✅ 已授权 |
| API Gateway 资源策略 | ✅ 无限制(None) |
| API Gateway 自定义域名 | ❌ **未配置** |
| 前端调用方式 | ❌ 直接访问 `execute-api` 默认域名 |

**根因**:AWS 中国区**不允许**通过 `xxx.execute-api.cn-northwest-1.amazonaws.com.cn`
默认域名对外提供公网服务(未备案),一律返回 `403 AccessDeniedException`。
必须像前端 CloudFront 一样,让 API 走**已 ICP 备案的域名**。

证据:CN `execute-api` 默认域名任何路径都返回
```
x-amzn-errortype: AccessDeniedException
{"Message":null}
```
而直连 Lambda 返回 `200 {"status":"healthy"}`——应用和数据都在,是入口被挡。

## 方案:CloudFront 统一入口(同源)

复用现有的 `ruianwy.site` CloudFront(已备案、已绑 IAM 证书),
新增一个 API Gateway origin 和一条 `/api/*` behavior:

```
用户 → https://ruianwy.site/            → CloudFront 默认 behavior → S3(前端静态页)
用户 → https://ruianwy.site/api/xxx     → CloudFront "/api/*" behavior → API Gateway → Lambda
```

前端 `VITE_API_URL` 改为 `https://ruianwy.site`(同源),
`client.ts` 再拼 `/api/projects` 等 → 请求 `https://ruianwy.site/api/projects`。

好处:
- API 不再暴露被拒的 execute-api 默认域名 → 绕过 `AccessDeniedException`。
- 前端与 API 同源 → **CORS 问题一并消失**。
- 只用一个备案域名、一张证书。

### 路径映射(关键，避免 404)

- FastAPI 路由前缀是 `/api/xxx`(如 `/api/projects`)。
- API Gateway stage 名是 `api`;Mangum 不把 stage 计入应用路径。
- execute-api 完整路径 = `/{stage}/{app_path}` = `/api` + `/api/projects` = `/api/api/projects`
  （截图里看到的"双 api"是**正确**的，不是 bug）。

因此 CloudFront 的 API origin 必须设 **origin path = `/api`**（补上 stage），
behavior 匹配 `/api/*` 并把原路径 `/api/projects` 追加上去：

```
浏览器  ruianwy.site/api/projects
  → CF behavior "/api/*"  origin=API GW  originPath="/api"
  → API GW 收到 /api/api/projects
  → Mangum 去掉 stage → FastAPI 收到 /api/projects  ✅
```

## CDK 改动（infrastructure/lib/frontend-stack.ts）

给 `SkyeyeFrontendStack` 增加:
1. 一个 API Gateway origin（`origins.HttpOrigin`），域名 = `<apiId>.execute-api.cn-northwest-1.amazonaws.com.cn`，`originPath: '/api'`。
2. 一条 `additionalBehaviors['/api/*']`：
   - `origin`: 上面的 API origin
   - `viewerProtocolPolicy: REDIRECT_TO_HTTPS`
   - `allowedMethods: ALLOW_ALL`（API 需要 POST/PUT/DELETE）
   - `cachePolicy: CACHING_DISABLED`（API 响应不缓存；CN 区用 legacy ForwardedValues 关缓存并转发 Authorization 头）
   - 必须转发 `Authorization` 头，否则 JWT 丢失 → 401。

需要把 `apiId`（或完整 execute-api 域名）作为 prop 传入 frontend-stack。
backend-stack 已 export `apiUrl`，可从中解析出域名。

## deploy.sh 改动（已实现）

新增第 3 个可选参数 `site_origin`：
```bash
./deploy.sh skyeye cn-northwest-1 https://ruianwy.site
```
- 给了 `site_origin`（中国区）：前端 `VITE_API_URL` = 该备案域名（裸 origin，不带 /api/）。
  客户端自己拼 `/api/xxx` → 请求 `https://ruianwy.site/api/xxx`（同源，走 CloudFront /api/*）。
- 不给（Global）：`VITE_API_URL` = API Gateway 直连地址（结尾已带 /api/），行为不变。

## 需要你在控制台/本地完成的事（我无法代做的部分）

1. **确认 `ruianwy.site` 的 ICP 备案覆盖 API 用法**（同域名 `/api/*` 路径通常无需额外备案，因为域名本身已备案）。
2. CDK 重新部署 CN 前端栈：`./deploy.sh skyeye cn-northwest-1`（改造后）。
3. 部署后 CloudFront 需要几分钟传播；用
   `curl https://ruianwy.site/api/health` 验证返回 `200 healthy`。
4. 数据迁移（`./migrate_to_cn.sh`）可在 API 打通后再做，或先做也行（数据与入口无关）。

## 验证清单

- [ ] `curl https://ruianwy.site/api/health` → `{"status":"healthy"}`
- [ ] `curl https://ruianwy.site/api/api/projects` → 401/403（正常，缺 token）
- [ ] 浏览器登录 CN 站点 → 能看到数据、Network 里请求打到 `ruianwy.site/api/...`
- [ ] 上传/下载附件正常（presigned URL 指向 CN S3 桶）
