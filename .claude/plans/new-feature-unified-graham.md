# Skyeye 新功能实施计划（new_feature.md）

## Context

`docs/new_feature.md` 中提出 5 项产品改进，覆盖附件、报销类型、报销搜索、库存入库、项目分析合并。当前代码已具备完整的报销/库存/项目/合同/附件基础能力（FastAPI + PynamoDB 单表 + S3 预签名直传 + React/AntD/Recharts），需在现有结构上做增量扩展，不大改架构。

**目标**：
1. 附件全局展示上传时间，并在上传按钮处提示大小限制（**50 MB**），并由前端做硬性拦截。
2. 报销类型支持后台两级（大类 → 子类）自定义管理，新建 DynamoDB 实体存储；前端报销表单改为级联选择。
3. 报销列表新增按项目、按报销人过滤 + 关键词搜索。
4. 库存入库流程：入库时先选项目 → 联动该项目的合同列表选合同 → 物料下拉同时显示 名称/规格/单价；将 `project_id + project_name + contract_id + contract_no` 一并写入 `StockRecord`。
5. 移除独立 `/analysis` 顶级菜单，新增 `/projects/:id` 项目详情页（多 Tab：基本信息 / 关联合同 / 报销 / 出库 / 成本分析图表），从项目列表点击进入。

---

## Backend 改动

### 1. 报销类型实体（新增模型 + 路由）

**新增文件** [backend/app/models/reimburse_category.py](backend/app/models/reimburse_category.py)
```
ReimburseCategoryModel(BaseModel)
  PK: REIMBURSE_CAT#{category_id}, SK: META
  GSI1PK: REIMBURSE_CAT_PARENT#{parent_id}  # 用 "ROOT" 表示一级类
  GSI1SK: SORT#{sort_order:04d}#{category_id}
  字段: category_id, name, parent_id (None=一级), level (1|2),
       sort_order: int, is_active: bool, code: Optional[str]
  staticmethods: make_pk / make_sk / make_gsi1pk
```

**新增** [backend/app/schemas/reimburse_category.py](backend/app/schemas/reimburse_category.py)：
- `CategoryCreate { name, parent_id?, sort_order?, code? }`
- `CategoryUpdate { name?, sort_order?, is_active?, code? }`
- `CategoryOut { category_id, name, parent_id, level, sort_order, is_active, code, children?: [CategoryOut] }`

**新增路由** [backend/app/routers/reimburse_categories.py](backend/app/routers/reimburse_categories.py)：
- `GET /api/reimburse-categories` — 全部用户可读，返回树形结构（一次扫描，按 parent_id 分组、sort_order 排序）。
- `GET /api/reimburse-categories/flat` — 平铺列表，便于管理界面。
- `POST /api/reimburse-categories` — admin 限权；若有 parent_id，校验父级存在且 level=1，子级 level=2（最多两级）。
- `PUT /api/reimburse-categories/{id}` — admin 限权。
- `DELETE /api/reimburse-categories/{id}` — admin 限权；若有子级或被报销引用则报 400（扫描 ReimbursementModel 看 expense_type 是否引用该 id）。

**注册** [backend/app/main.py](backend/app/main.py) 行 8/36 — 引入 `reimburse_categories`，`app.include_router(reimburse_categories.router)`。

**启动种子**（在 [main.py](backend/app/main.py) `startup_event` 末尾追加）：若 `ReimburseCategoryModel` 为空，写入 4 个一级默认（material/travel/equipment_rental/other）+ 几个示例子级，保证升级用户开箱可用。

**Reimbursement 字段调整** [backend/app/models/reimbursement.py](backend/app/models/reimbursement.py)：
- `expense_type`：保留为字符串，存子级 `category_id`（向后兼容已有"material"等字符串值，前端做映射回退）。
- 新增可选字段 `expense_category_id`（一级 id）`expense_subcategory_id`（二级 id），在 [routers/reimbursements.py](backend/app/routers/reimbursements.py) 的 `_reimburse_to_dict` 与 create/update 中写入读出，**保持 `expense_type` 兼容老数据**（若新字段为空则透传旧值）。
- [schemas/reimbursement.py](backend/app/schemas/reimbursement.py) `ReimbursementCreate/Update/Out` 均加上两个新字段（Optional）。

### 2. 报销列表过滤（已基本支持，仅前端调用）

[routers/reimbursements.py:61-88](backend/app/routers/reimbursements.py#L61-L88) 已支持 `status`、`project_id`、`expense_type` 查询参数。新增：
- `applicant_id: Optional[str]` 过滤报销人。
- `keyword: Optional[str]` 在 `description / project_name / applicant_name` 上做包含匹配。

### 3. 库存入库绑定项目+合同

[backend/app/schemas/inventory.py](backend/app/schemas/inventory.py) `StockInCreate` 行 55-60 增加：
```python
project_id: Optional[str] = None
project_name: Optional[str] = None
contract_id: Optional[str] = None
contract_no: Optional[str] = None
```

[backend/app/models/inventory.py](backend/app/models/inventory.py) `StockRecordModel` 增加字段：
```python
contract_id = UnicodeAttribute(null=True)
contract_no = UnicodeAttribute(null=True)
```
（`project_id/project_name` 已存在。）

[backend/app/routers/inventory.py:208-245](backend/app/routers/inventory.py#L208-L245) `stock_in` 函数：
- 写入 `r.project_id / r.project_name / r.contract_id / r.contract_no`。
- 若提供 `project_id`，设置 `r.GSI2PK = make_gsi2pk(project_id)`、`r.GSI2SK = STOCK#{record_id}`，与 stock_out 一致，便于按项目聚合查询。

[_record_to_dict](backend/app/routers/inventory.py#L29-L42)：把 `contract_id / contract_no` 加入返回。

**项目分析改动**（[routers/analysis.py](backend/app/routers/analysis.py) 第 32 行）：当前 `material_cost` 只统计 `record_type=="out"`；改为同时统计**入库已绑定到该项目的记录**（即 `record_type in ("in","out")` 且 `project_id == pid`），避免因业务从"出库扣减"切到"入库直接采购计入项目"导致成本漏算。

### 4. 项目详情聚合接口（复用现有 analysis 接口）

无需新增接口，前端 `/projects/:id` 页面直接：
- `projectApi.get(id)` — 项目主信息
- `contractApi.list({ project_id })` — 合同列表
- `reimbursementApi.list({ project_id })` — 报销列表
- `inventoryApi.listRecords({ project_id })` — **需补**入库/出库记录（[routers/inventory.py:192-205](backend/app/routers/inventory.py#L192-L205) 增加 `project_id` 过滤）
- `analysisApi.projectAnalysis(id)` — 利润、成本构成

[routers/inventory.py:192-205](backend/app/routers/inventory.py#L192-L205) `list_stock_records` 增加 `project_id: Optional[str]` 查询参数。

### 5. 上传体积限制（后端零变更）

预签名 URL 不限制大小；前端在上传前用 `file.size` 拒绝 > 50 MB。S3 桶若有更严限制可后续在 CDK 层添加 bucket policy，本期不做。

---

## Frontend 改动

### 1. FileUpload 组件 [frontend/src/components/FileUpload.tsx](frontend/src/components/FileUpload.tsx)

- 顶部新增常量 `const MAX_FILE_SIZE = 50 * 1024 * 1024;`
- `handleUpload`（行 29）开头加：若 `file.size > MAX_FILE_SIZE` → `message.error('文件大小不能超过 50 MB')` 并 `onError` 中止。
- 上传按钮（行 113）label 改为：`{uploading ? '上传中...' : '上传附件 (单个文件 ≤ 50MB)'}`，并保留尾部 hint。
- 列表渲染（行 122-128）每条增加上传时间显示：用 dayjs 格式化为 `YYYY-MM-DD HH:mm`，灰色小字与文件大小同行。

```tsx
import dayjs from 'dayjs';
// ...
<span style={{ fontSize: 12, color: '#999' }}>
  {(file.file_size / 1024).toFixed(1)} KB
</span>
{file.upload_time && (
  <span style={{ fontSize: 12, color: '#999' }}>
    · {dayjs(file.upload_time).format('YYYY-MM-DD HH:mm')}
  </span>
)}
```

[frontend/src/components/FileManager.tsx](frontend/src/components/FileManager.tsx) 自动受益（其内部就是包了 FileUpload）。

### 2. 报销类型 API 客户端 [frontend/src/api/client.ts](frontend/src/api/client.ts)

新增导出：
```ts
export const reimburseCategoryApi = {
  tree: () => client.get('/api/reimburse-categories'),
  list: () => client.get('/api/reimburse-categories/flat'),
  create: (data: any) => client.post('/api/reimburse-categories', data),
  update: (id: string, data: any) => client.put(`/api/reimburse-categories/${id}`, data),
  delete: (id: string) => client.delete(`/api/reimburse-categories/${id}`),
};
```

### 3. 报销分类管理页（admin only）

新建 [frontend/src/pages/ReimburseCategories.tsx](frontend/src/pages/ReimburseCategories.tsx)：
- AntD `Tree` 展示树形分类，支持展开/折叠。
- 工具栏：「新增大类」「新增子类（选中大类后启用）」。
- 节点 hover 操作：编辑、启用/禁用、删除。
- 编辑弹窗：name、sort_order、code（可选）、is_active。

App.tsx 与 MainLayout.tsx 接入：
- [App.tsx](frontend/src/App.tsx) 行 47 后增加 `<Route path="reimburse-categories" element={<ReimburseCategories />} />`。
- [MainLayout.tsx:77-80](frontend/src/components/MainLayout.tsx#L77-L80) admin 子菜单中插入：`{ key: '/reimburse-categories', icon: <TagsOutlined />, label: '报销类型管理' }`，并在 `pageTitles`(行 32) 增加映射。

### 4. 报销列表升级 [frontend/src/pages/Reimbursements.tsx](frontend/src/pages/Reimbursements.tsx)

- 顶部新增筛选栏：项目下拉、报销人下拉（用 `authApi.listUsers()` 拉取，admin/finance 才显示）、状态下拉、关键词输入框；变更时调用 `reimbursementApi.list(params)`。非 admin/finance 角色隐藏报销人筛选。
- 删除行 14 的 `expenseTypes` 静态映射，改为 `useEffect` 中 `reimburseCategoryApi.tree()` 加载并保存到 state。
- 新建/编辑表单（行 100-102）将 `expense_type` 单选改为**两级 Cascader 或 两个联动 Select**：
  - 大类 Select（必填）→ 选定后显示子类 Select（如有子级）。
  - 提交时把子级 id（无子级时取大类 id）写入 `expense_type`，同时写入 `expense_category_id` / `expense_subcategory_id`。
- 列渲染 `expense_type`（行 69）：从分类树查 name；老数据回退 `expenseTypesFallback['material'|'travel'|'equipment_rental'|'other']` 中文映射。

### 5. 库存入库表单 [frontend/src/pages/Inventory.tsx](frontend/src/pages/Inventory.tsx)

入库分支（当前 `stockModal === 'in'` 仅显示 supplier_name，行 144）改造为：

```tsx
{stockModal === 'in' && (
  <>
    <Form.Item name="project_id" label="关联项目">  {/* 选填，但建议填 */}
      <Select options={projects.map(p => ({ value: p.project_id, label: p.project_name }))}
              onChange={(v) => {
                const p = projects.find(x => x.project_id === v);
                stockForm.setFieldValue('project_name', p?.project_name);
                stockForm.setFieldValue('contract_id', undefined);
                loadProjectContracts(v);   // 拉取该项目的合同
              }} />
    </Form.Item>
    <Form.Item name="project_name" hidden><Input /></Form.Item>
    <Form.Item name="contract_id" label="关联合同"
               tooltip="选择项目后可见">
      <Select options={projectContracts.map(c => ({
                value: c.contract_id,
                label: `${c.contract_no} - ${c.contract_name}`
              }))}
              disabled={!stockForm.getFieldValue('project_id')}
              onChange={(v) => {
                const c = projectContracts.find(x => x.contract_id === v);
                stockForm.setFieldValue('contract_no', c?.contract_no);
              }} />
    </Form.Item>
    <Form.Item name="contract_no" hidden><Input /></Form.Item>
    <Form.Item name="supplier_name" label="供应商"><Input /></Form.Item>
  </>
)}
```

state 增加 `const [projectContracts, setProjectContracts] = useState<any[]>([]);`，`loadProjectContracts` 调用 `contractApi.list({ project_id })`。

物料下拉（行 138-140）label 调整加上单价：
```ts
options={materials.map(m => ({
  value: m.material_id,
  label: `${m.material_name}${m.specification ? ' - ' + m.specification : ''}${m.unit_price ? ' - ¥' + m.unit_price : ''} (库存:${m.stock_quantity || 0})`,
}))}
```
出库分支保持原貌，仅同步把单价加入显示。

### 6. 项目详情页 + 移除 Analysis 顶级菜单

**新建** [frontend/src/pages/ProjectDetail.tsx](frontend/src/pages/ProjectDetail.tsx)：
- `useParams` 取 `id`；`useEffect` 并行加载 project / contracts / reimbursements / stock records / analysis。
- 顶部面包屑：`项目管理 / {project_name}`，返回按钮 `navigate(-1)`。
- 顶部 4 个统计卡：合同金额 / 总成本 / 利润 / 利润率（来自 analysis 接口）。
- AntD `Tabs`：
  - **基本信息**：现 Projects 页的字段 + 项目地址、起止日期。
  - **关联合同**：Table 展示该项目的合同（client/supplier/construction），列出金额、已付款、状态。
  - **报销明细**：Table 报销记录，按状态着色。
  - **出入库记录**：Table 含合同号、物料、数量、金额。
  - **成本分析**：左 Pie（成本构成：采购/施工/报销/物料），右 Bar（合同金额 vs 已付款 vs 应付款）。下方 Descriptions 展示 `revenue / cost / profit / profit_rate / payment_progress / acceptance` 全字段。复用现有 [Analysis.tsx](frontend/src/pages/Analysis.tsx) 的 PieChart/BarChart 写法。

**Projects 列表** [frontend/src/pages/Projects.tsx](frontend/src/pages/Projects.tsx)：
- `project_name` 列改为可点击 Link：`<a onClick={() => navigate(\`/projects/\${record.project_id}\`)}>...</a>`。
- 操作列追加「详情」按钮，导航到详情页。

**App.tsx**：
- 行 12 删除 `import Analysis`，行 44 删除 `<Route path="analysis" />`。
- 行 39 后增加 `<Route path="projects/:id" element={<ProjectDetail />} />`，并 `import ProjectDetail`。
- 删除 [frontend/src/pages/Analysis.tsx](frontend/src/pages/Analysis.tsx)。

**MainLayout** [frontend/src/components/MainLayout.tsx](frontend/src/components/MainLayout.tsx)：
- 行 76 删除 `{ key: '/analysis', ... }`。
- 行 39 删除 `pageTitles['/analysis']`。
- selectedKeys 逻辑（行 104）改为：`location.pathname.startsWith('/projects') ? '/projects' : location.pathname`，以便项目详情页时左侧菜单仍高亮"项目管理"。

---

## 关键改动文件清单

| 模块 | 文件 |
|------|------|
| 后端 | `backend/app/models/reimburse_category.py`（新建）|
| 后端 | `backend/app/schemas/reimburse_category.py`（新建）|
| 后端 | `backend/app/routers/reimburse_categories.py`（新建）|
| 后端 | `backend/app/main.py`（注册路由 + 默认分类种子）|
| 后端 | `backend/app/models/reimbursement.py`（新增 expense_category_id/subcategory_id）|
| 后端 | `backend/app/schemas/reimbursement.py`（同步新字段）|
| 后端 | `backend/app/routers/reimbursements.py`（list 加 applicant_id/keyword 过滤；create/update 写新字段；返回新字段）|
| 后端 | `backend/app/models/inventory.py`（StockRecordModel 加 contract_id/contract_no）|
| 后端 | `backend/app/schemas/inventory.py`（StockInCreate 加 project_id/contract_id 等）|
| 后端 | `backend/app/routers/inventory.py`（stock_in 写绑定字段；list_stock_records 加 project_id 过滤；_record_to_dict 返回合同字段）|
| 后端 | `backend/app/routers/analysis.py`（material_cost 改为统计入库已绑定记录）|
| 前端 | `frontend/src/components/FileUpload.tsx`（50MB 限制 + upload_time 显示 + 按钮 hint）|
| 前端 | `frontend/src/api/client.ts`（reimburseCategoryApi）|
| 前端 | `frontend/src/pages/ReimburseCategories.tsx`（新建）|
| 前端 | `frontend/src/pages/Reimbursements.tsx`（筛选栏 + 级联类型选择 + 老数据兼容）|
| 前端 | `frontend/src/pages/Inventory.tsx`（入库选项目→合同；物料下拉加单价）|
| 前端 | `frontend/src/pages/Projects.tsx`（点击进入详情）|
| 前端 | `frontend/src/pages/ProjectDetail.tsx`（新建，Tabs + 图表）|
| 前端 | `frontend/src/App.tsx`（路由加 /projects/:id；删 /analysis）|
| 前端 | `frontend/src/components/MainLayout.tsx`（删 analysis 菜单 + 加分类管理菜单 + 详情高亮）|
| 前端 | 删除 `frontend/src/pages/Analysis.tsx` |

---

## 验证方案

### 本地启动
1. 后端：`cd backend && uvicorn app.main:app --reload --port 8000`
2. 前端：`cd frontend && npm run dev`，浏览器开 http://localhost:5173
3. `./dev.sh` 一键启动（如有现成脚本）。

### 端到端测试

**附件改造**
- 在合同/报销/验收任一处上传一个 < 50MB 文件，列表中应显示 `YYYY-MM-DD HH:mm` 上传时间。
- 选取一个 > 50MB 文件，应被前端拦截并提示。
- 上传按钮文字应包含 `≤ 50MB` 提示。

**报销类型管理**
- admin 登录，左侧菜单出现「报销类型管理」，新建一级"办公"，再添加子级"耗材""差旅"。
- 普通用户登录提交报销，类型先选"办公"再选"耗材"，提交后列表应显示中文名称。
- admin 删除一个被引用的子类应报错"已被报销引用"。
- 删除已禁用的空大类应成功。

**报销筛选**
- 顶部按项目过滤、按报销人过滤（admin 才显示）、按关键词过滤，列表正确缩减。

**库存入库**
- 入库时先选项目，合同下拉变为该项目下的合同（含 contract_no - contract_name）；
- 物料下拉显示 `名称 - 规格 - ¥单价 (库存:n)`；
- 提交后到 records 表中能看到 contract_no 列；
- 进入项目详情 → 出入库 Tab 看到这条入库记录。

**项目分析合并**
- 顶部菜单不再有「项目分析」。
- 项目列表点击项目名跳转到 `/projects/:id`，5 个 Tab 加载正确，最后 Tab 渲染 Pie + Bar 图表。
- 利润率与原 `/analysis` 单项目分析数值一致。
- 浏览器刷新详情页保持当前 Tab 路径正常。

### 单元 / 接口检查
- `GET /api/reimburse-categories` 返回树形 JSON。
- `GET /api/reimbursements?applicant_id=xxx&keyword=车票` 正确过滤。
- `POST /api/inventory/stock-in` body 含 `contract_id`，DB 中新记录带该字段（DynamoDB 控制台或 `aws dynamodb get-item` 验证；**只读**，遵守生产安全规则）。

### 部署前检查
- `npm run build` 通过类型检查（前端 tsconfig 严格模式）。
- 后端 `python -m compileall app` 通过。
- 不修改任何 CDK/Apollo 配置；本期改动均为应用层。

---

## 不在本期范围
- 新增大类排序的拖拽 UI（用 sort_order 数字编辑即可）。
- DynamoDB 索引重建 / 数据回填脚本：旧 `expense_type` 字符串与新分类 id 共存，前端做兼容回退。
- 全局看板 Dashboard 的内容增强（顶部菜单 Dashboard 仍保留，但本期不为它移植 `/analysis` 内容）。
