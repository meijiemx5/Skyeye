/** 与后端共享的业务枚举文案，供多个页面复用。 */

// 报销链路: 提交报销 → 项目收款 → 创建单据 → 财务审核 → 凭证生成 → 付款
export const REIMBURSE_STATUS: Record<string, { label: string; color: string }> = {
  pending_review: { label: '待主管审核', color: 'orange' },
  manager_approved: { label: '主管已审', color: 'blue' },
  receipt_confirmed: { label: '项目已收款', color: 'geekblue' },
  document_created: { label: '单据已创建', color: 'purple' },
  finance_approved: { label: '财务已审', color: 'cyan' },
  voucher_generated: { label: '凭证已生成', color: 'lime' },
  paid: { label: '已付款', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
};

/** 链路顺序，用于步骤条 */
export const REIMBURSE_CHAIN = [
  'pending_review', 'manager_approved', 'receipt_confirmed',
  'document_created', 'finance_approved', 'voucher_generated', 'paid',
];

export const REIMBURSE_CHAIN_STEPS = [
  { title: '提交报销' }, { title: '主管审核' }, { title: '项目收款' }, { title: '创建单据' },
  { title: '财务审核' }, { title: '凭证生成' }, { title: '付款' },
];

// 发票类别与默认税率（表单预填，实际以发票为准）
export const INVOICE_CATEGORIES = [
  { value: 'material', label: '材料', defaultRate: 13 },
  { value: 'construction', label: '施工', defaultRate: 9 },
  { value: 'service', label: '技术服务', defaultRate: 6 },
  { value: 'other', label: '其他', defaultRate: 0 },
];

export const INVOICE_CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  INVOICE_CATEGORIES.map(c => [c.value, c.label]),
);

/** 常见税率选项：一般计税 13/9/6，小规模 3/1，免税 0 */
export const TAX_RATE_OPTIONS = [13, 9, 6, 3, 1, 0].map(r => ({ value: r, label: `${r}%` }));

export const PAYMENT_STAGES = [
  { value: 'advance', label: '预付款' },
  { value: 'progress', label: '进度款' },
  { value: 'final', label: '尾款' },
  { value: 'other', label: '其他' },
];

export const BATCH_STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: '待开票', color: 'default' },
  issued: { label: '已开票', color: 'blue' },
  received: { label: '甲方已收', color: 'green' },
  void: { label: '已作废', color: 'red' },
};

// 项目完整度清单
export const CHECKLIST_LABELS: Record<string, string> = {
  budget: '预算',
  quote: '报价',
  client_contract: '甲方合同',
  supplier_contract: '采购合同',
  labor_contract: '工费',
  acceptance: '验收资料',
  invoice: '发票',
  reimbursement: '报销',
};

export const CHECKLIST_STATUS: Record<string, { label: string; color: string }> = {
  ok: { label: '已完成', color: '#0f9d58' },
  missing: { label: '未完成', color: '#f59e0b' },
  overdue: { label: '已逾期', color: '#e5484d' },
  warning: { label: '有风险', color: '#f59e0b' },
};

export const SEVERITY: Record<string, { label: string; color: string }> = {
  high: { label: '紧急', color: 'red' },
  medium: { label: '待处理', color: 'orange' },
  low: { label: '提示', color: 'blue' },
};

export const TODO_TYPE_LABELS: Record<string, string> = {
  project_checklist: '项目未完成项',
  reimbursement: '报销待处理',
  reimbursement_rejected: '报销被驳回',
  acceptance_rectification: '验收整改',
  stock_warning: '库存预警',
};

export const formatMoney = (v?: number | null) =>
  `¥${Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
