import { useEffect, useMemo, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, InputNumber, DatePicker, Space, Tag, message,
  Typography, Row, Col, Popconfirm, Checkbox, Steps, Descriptions, Alert,
} from 'antd';
import {
  PlusOutlined, CheckOutlined, DollarOutlined, SearchOutlined, ReloadOutlined,
  BankOutlined, FileTextOutlined, BookOutlined,
} from '@ant-design/icons';
import { reimbursementApi, projectApi, authApi, reimburseCategoryApi, contractApi } from '../api/client';
import dayjs from 'dayjs';
import FileUpload, { FileInfo } from '../components/FileUpload';
import FileManager from '../components/FileManager';
import { REIMBURSE_STATUS, REIMBURSE_CHAIN, REIMBURSE_CHAIN_STEPS, formatMoney } from '../utils/constants';
import { can, currentUser } from '../utils/permissions';

const { Title, Text } = Typography;
const legacyTypeLabels: Record<string, string> = { material: '物料采购', travel: '差旅费', equipment_rental: '设备租赁', other: '其他' };

interface CategoryNode {
  category_id: string; name: string; parent_id?: string | null;
  level: number; sort_order: number; is_active: boolean;
  children?: CategoryNode[];
}

export default function Reimbursements() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [auditModal, setAuditModal] = useState<any>(null);
  const [payModal, setPayModal] = useState<any>(null);
  const [receiptModal, setReceiptModal] = useState<any>(null);
  const [documentModal, setDocumentModal] = useState<any>(null);
  const [voucherModal, setVoucherModal] = useState<any>(null);
  const [detailRecord, setDetailRecord] = useState<any>(null);
  const [vouchers, setVouchers] = useState<FileInfo[]>([]);
  const [voucherFiles, setVoucherFiles] = useState<FileInfo[]>([]);
  const [editingReimburse, setEditingReimburse] = useState<any>(null);
  const [fileRecord, setFileRecord] = useState<any>(null);
  const [form] = Form.useForm();
  const [auditForm] = Form.useForm();
  const [payForm] = Form.useForm();
  const [receiptForm] = Form.useForm();
  const [documentForm] = Form.useForm();
  const [voucherForm] = Form.useForm();
  const [projects, setProjects] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [clientContracts, setClientContracts] = useState<any[]>([]);
  const [categoryTree, setCategoryTree] = useState<CategoryNode[]>([]);
  const [filters, setFilters] = useState<{ project_id?: string; applicant_id?: string; status?: string; keyword?: string }>({});
  const user = currentUser();
  const canFilterByApplicant = ['admin', 'finance'].includes(user.role || '');
  const canDelete = can('reimburse:delete');
  const canSkipReceipt = can('reimburse:receipt_skip');

  const skipReceipt: boolean = Form.useWatch('skip', receiptForm);
  const selectedCategoryId: string | undefined = Form.useWatch('expense_category_id', form);
  const selectedCategory = useMemo(
    () => categoryTree.find(c => c.category_id === selectedCategoryId),
    [categoryTree, selectedCategoryId],
  );

  useEffect(() => {
    loadData();
    projectApi.options().then(r => setProjects(r.data.data || [])).catch(() => {});
    reimburseCategoryApi.tree().then(r => setCategoryTree(r.data.data || [])).catch(() => {});
    if (can('contract:options')) {
      contractApi.options({ contract_type: 'client' }).then(r => setClientContracts(r.data.data || [])).catch(() => {});
    }
    if (canFilterByApplicant) {
      authApi.listUsers().then(r => setUsers(r.data.data || [])).catch(() => {});
    }
  }, []);

  const loadData = async (overrides?: typeof filters) => {
    setLoading(true);
    try {
      const params: any = { ...(overrides ?? filters) };
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k]; });
      const res = await reimbursementApi.list(params);
      setData(res.data.data || []);
    } catch {} finally { setLoading(false); }
  };

  const renderExpenseLabel = (record: any) => {
    const subId = record.expense_subcategory_id;
    const catId = record.expense_category_id;
    if (subId) {
      const parent = categoryTree.find(c => c.category_id === catId);
      const child = parent?.children?.find(c => c.category_id === subId);
      if (child) return parent ? `${parent.name} / ${child.name}` : child.name;
    }
    if (catId) {
      const parent = categoryTree.find(c => c.category_id === catId);
      if (parent) return parent.name;
    }
    // legacy fallback
    const t = record.expense_type;
    return legacyTypeLabels[t] || categoryTree.find(c => c.category_id === t)?.name || t;
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (values.expense_date) values.expense_date = values.expense_date.format('YYYY-MM-DD');
    values.vouchers = vouchers;

    // Derive expense_type from sub if available, else parent
    const subId = values.expense_subcategory_id;
    const catId = values.expense_category_id;
    values.expense_type = subId || catId;
    if (!values.expense_type) {
      message.error('请选择报销类型');
      return;
    }

    try {
      if (editingReimburse) {
        await reimbursementApi.update(editingReimburse.reimburse_id, values);
        message.success('更新成功');
      } else {
        await reimbursementApi.create(values);
        message.success('提交成功');
      }
      setModalOpen(false); form.resetFields(); setVouchers([]); setEditingReimburse(null); loadData();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  /** 链路操作统一走这里：校验 → 调接口 → 提示 → 刷新 */
  const runStep = async (
    action: () => Promise<any>,
    close: () => void,
    fallbackMessage = '操作成功',
  ) => {
    try {
      const res = await action();
      message.success(res?.data?.message || fallbackMessage);
      close();
      loadData();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败');
    }
  };

  const handleAudit = async () => {
    const values = await auditForm.validateFields();
    await runStep(() => reimbursementApi.audit(auditModal.reimburse_id, values),
      () => { setAuditModal(null); auditForm.resetFields(); }, '审核成功');
  };

  const handleReceipt = async () => {
    const values = await receiptForm.validateFields();
    if (values.receipt_date) values.receipt_date = values.receipt_date.format('YYYY-MM-DD');
    const contract = clientContracts.find(c => c.contract_id === values.contract_id);
    await runStep(() => reimbursementApi.confirmReceipt(receiptModal.reimburse_id, {
      ...values, contract_no: contract?.contract_no,
    }), () => { setReceiptModal(null); receiptForm.resetFields(); }, '项目收款确认成功');
  };

  const handleDocument = async () => {
    const values = await documentForm.validateFields();
    await runStep(() => reimbursementApi.createDocument(documentModal.reimburse_id, values),
      () => { setDocumentModal(null); documentForm.resetFields(); }, '单据创建成功');
  };

  const handleVoucher = async () => {
    const values = await voucherForm.validateFields();
    await runStep(() => reimbursementApi.generateVoucher(voucherModal.reimburse_id, {
      ...values, voucher_files: voucherFiles,
    }), () => { setVoucherModal(null); voucherForm.resetFields(); setVoucherFiles([]); }, '凭证生成成功');
  };

  const handlePay = async () => {
    const values = await payForm.validateFields();
    if (values.payment_time) values.payment_time = values.payment_time.format('YYYY-MM-DD HH:mm');
    await runStep(() => reimbursementApi.pay(payModal.reimburse_id, values),
      () => { setPayModal(null); payForm.resetFields(); }, '付款成功');
  };

  const handleDelete = async (id: string) => {
    await runStep(() => reimbursementApi.delete(id), () => {}, '删除成功');
  };

  const openEdit = (r: any) => {
    setEditingReimburse(r);
    setVouchers(r.vouchers || []);
    // Pre-fill cascaded fields; if new fields missing, map legacy expense_type to a parent id.
    const catId = r.expense_category_id || (categoryTree.find(c => c.category_id === r.expense_type)?.category_id);
    const subId = r.expense_subcategory_id;
    form.setFieldsValue({
      ...r,
      expense_category_id: catId,
      expense_subcategory_id: subId,
      expense_date: r.expense_date ? dayjs(r.expense_date) : null,
    });
    setModalOpen(true);
  };

  const openReceipt = (r: any) => {
    receiptForm.resetFields();
    const matching = clientContracts.filter(c => c.project_id === r.project_id);
    receiptForm.setFieldsValue({
      receipt_date: dayjs(),
      contract_id: matching.length === 1 ? matching[0].contract_id : undefined,
      skip: false,
    });
    setReceiptModal(r);
  };

  const columns = [
    { title: '报销人', dataIndex: 'applicant_name', key: 'applicant_name', width: 90 },
    { title: '项目', dataIndex: 'project_name', key: 'project_name', ellipsis: true },
    { title: '类型', key: 'expense_type', width: 130, render: (_: any, r: any) => renderExpenseLabel(r) },
    { title: '金额', dataIndex: 'amount_with_tax', key: 'amount_with_tax', width: 110,
      render: (v: number) => formatMoney(v) },
    { title: '事由', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '状态', dataIndex: 'status', key: 'status', width: 110,
      render: (s: string, r: any) => {
        const st = REIMBURSE_STATUS[s];
        return (
          <a onClick={() => setDetailRecord(r)}>
            {st ? <Tag color={st.color}>{st.label}</Tag> : s}
          </a>
        );
      } },
    { title: '下一步', dataIndex: 'next_step_label', key: 'next_step', width: 100,
      render: (v: string) => v ? <Text type="secondary">{v}</Text> : '-' },
    { title: '单据号', dataIndex: 'document_no', key: 'document_no', width: 140, render: (v: string) => v || '-' },
    { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no', width: 140, render: (v: string) => v || '-' },
    { title: '凭证', key: 'vouchers', width: 80, render: (_: any, record: any) => <Button type="link" size="small" onClick={() => setFileRecord(record)}>{record.vouchers?.length ? `${record.vouchers.length}个` : '管理'}</Button> },
    { title: '发生日期', dataIndex: 'expense_date', key: 'expense_date', width: 110 },
    { title: '操作', key: 'action', width: 300, fixed: 'right' as const, render: (_: any, r: any) => (
      <Space wrap size={4}>
        {['pending_review', 'rejected'].includes(r.status) && (r.applicant_id === user.user_id || user.role === 'admin') &&
          <Button size="small" onClick={() => openEdit(r)}>编辑</Button>
        }
        {r.status === 'pending_review' && can('reimburse:audit_manager') &&
          <Button size="small" icon={<CheckOutlined />} onClick={() => { setAuditModal(r); auditForm.resetFields(); }}>主管审核</Button>
        }
        {r.status === 'manager_approved' && can('reimburse:receipt') &&
          <Button size="small" icon={<BankOutlined />} onClick={() => openReceipt(r)}>确认收款</Button>
        }
        {r.status === 'receipt_confirmed' && can('reimburse:document') &&
          <Button size="small" icon={<FileTextOutlined />} onClick={() => { setDocumentModal(r); documentForm.resetFields(); }}>创建单据</Button>
        }
        {r.status === 'document_created' && can('reimburse:audit_finance') &&
          <Button size="small" icon={<CheckOutlined />} onClick={() => { setAuditModal(r); auditForm.resetFields(); }}>财务审核</Button>
        }
        {r.status === 'finance_approved' && can('reimburse:voucher') &&
          <Button size="small" icon={<BookOutlined />} onClick={() => { setVoucherModal(r); voucherForm.resetFields(); setVoucherFiles([]); }}>生成凭证</Button>
        }
        {r.status === 'voucher_generated' && can('reimburse:pay') &&
          <Button size="small" type="primary" icon={<DollarOutlined />} onClick={() => { setPayModal(r); payForm.setFieldsValue({ payment_amount: r.amount_with_tax, payment_time: dayjs() }); }}>付款</Button>
        }
        {canDelete && <Popconfirm title="确定删除该报销记录?" onConfirm={() => handleDelete(r.reimburse_id)}><Button size="small" danger>删除</Button></Popconfirm>}
      </Space>
    )},
  ];

  const chainIndex = (status: string) => {
    const idx = REIMBURSE_CHAIN.indexOf(status);
    return idx < 0 ? 0 : idx;
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>报销管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setVouchers([]); setEditingReimburse(null); setModalOpen(true); }}>提交报销</Button>
      </div>

      <Alert
        type="info" showIcon style={{ marginBottom: 12 }}
        message="报销链路：提交报销 → 主管审核 → 项目收款 → 创建单据 → 财务审核 → 凭证生成 → 付款。未确认项目收款不能创建单据（管理员可留痕跳过）。"
      />

      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col xs={24} sm={12} md={6}>
          <Select allowClear placeholder="按项目过滤" style={{ width: '100%' }}
            showSearch optionFilterProp="label"
            value={filters.project_id}
            options={projects.map(p => ({ value: p.project_id, label: p.project_name }))}
            onChange={(v) => setFilters({ ...filters, project_id: v })} />
        </Col>
        {canFilterByApplicant && (
          <Col xs={24} sm={12} md={5}>
            <Select allowClear placeholder="按报销人过滤" style={{ width: '100%' }}
              showSearch optionFilterProp="label"
              value={filters.applicant_id}
              options={users.map(u => ({ value: u.user_id, label: `${u.display_name || u.username}` }))}
              onChange={(v) => setFilters({ ...filters, applicant_id: v })} />
          </Col>
        )}
        <Col xs={24} sm={12} md={4}>
          <Select allowClear placeholder="状态" style={{ width: '100%' }}
            value={filters.status}
            options={Object.entries(REIMBURSE_STATUS).map(([k, v]) => ({ value: k, label: v.label }))}
            onChange={(v) => setFilters({ ...filters, status: v })} />
        </Col>
        <Col xs={24} sm={12} md={5}>
          <Input.Search allowClear placeholder="搜索事由/项目/报销人"
            value={filters.keyword}
            onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
            onSearch={() => loadData()} />
        </Col>
        <Col xs={24} sm={24} md={4}>
          <Space>
            <Button icon={<SearchOutlined />} type="primary" onClick={() => loadData()}>查询</Button>
            <Button icon={<ReloadOutlined />} onClick={() => { setFilters({}); loadData({}); }}>重置</Button>
          </Space>
        </Col>
      </Row>

      <Table columns={columns} dataSource={data} rowKey="reimburse_id" loading={loading} size="middle" scroll={{ x: 1700 }} />

      <Modal title={editingReimburse ? '编辑报销申请' : '提交报销申请'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={600}>
        <Form form={form} layout="vertical">
          <Row gutter={12}>
            <Col span={selectedCategory?.children?.length ? 12 : 24}>
              <Form.Item
                name="expense_category_id" label="报销类型（大类）"
                tooltip="只能选择系统已有的费用大类；新增大类请联系管理员在「报销类型管理」中维护"
                rules={[{ required: true, message: '请选择大类' }]}
              >
                <Select placeholder="选择大类" showSearch optionFilterProp="label"
                  options={categoryTree.filter(c => c.is_active).map(c => ({ value: c.category_id, label: c.name }))}
                  onChange={() => form.setFieldValue('expense_subcategory_id', undefined)} />
              </Form.Item>
            </Col>
            {!!selectedCategory?.children?.length && (
              <Col span={12}>
                <Form.Item name="expense_subcategory_id" label="子类">
                  <Select allowClear placeholder="选择子类" showSearch optionFilterProp="label"
                    options={(selectedCategory.children || []).filter(c => c.is_active).map(c => ({ value: c.category_id, label: c.name }))} />
                </Form.Item>
              </Col>
            )}
          </Row>
          <Form.Item name="project_id" label="关联项目" rules={[{ required: true, message: '请选择关联项目' }]}>
            <Select placeholder="选择关联项目" showSearch optionFilterProp="label"
              options={projects.map(p => ({ value: p.project_id, label: p.project_name }))}
              onChange={(v) => { const p = projects.find(x => x.project_id === v); if (p) form.setFieldValue('project_name', p.project_name); }}
            />
          </Form.Item>
          <Form.Item name="project_name" hidden><Input /></Form.Item>
          <Form.Item name="amount_with_tax" label="报销金额(含税)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="description" label="报销事由" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="expense_date" label="发生日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item label="报销凭证（发票/收据）">
            <FileUpload entityType="reimbursement" entityId={editingReimburse?.reimburse_id || 'new'} files={vouchers} onChange={setVouchers} maxCount={5} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={auditModal?.status === 'document_created' ? '财务审核' : '主管审核'}
        open={!!auditModal} onOk={handleAudit} onCancel={() => setAuditModal(null)}
      >
        <p>报销人: {auditModal?.applicant_name} | 金额: {formatMoney(auditModal?.amount_with_tax)} | 事由: {auditModal?.description}</p>
        {auditModal?.document_no && <p>单据号: {auditModal.document_no}</p>}
        <Form form={auditForm} layout="vertical">
          <Form.Item name="action" label="审核结果" rules={[{ required: true }]}>
            <Select options={[{ value: 'approved', label: '通过' }, { value: 'rejected', label: '驳回' }]} />
          </Form.Item>
          <Form.Item name="comments" label="审核意见"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="项目收款确认" open={!!receiptModal} onOk={handleReceipt} onCancel={() => setReceiptModal(null)} width={560}>
        <Alert
          type="warning" showIcon style={{ marginBottom: 12 }}
          message="确认该报销所属项目已收到甲方款项后，才能创建报销单据。"
        />
        <p>项目: {receiptModal?.project_name || '未关联项目'} | 报销金额: {formatMoney(receiptModal?.amount_with_tax)}</p>
        <Form form={receiptForm} layout="vertical">
          {canSkipReceipt && (
            <Form.Item name="skip" valuePropName="checked">
              <Checkbox>项目尚未收款，管理员强制跳过（会记入审批日志）</Checkbox>
            </Form.Item>
          )}
          {skipReceipt ? (
            <Form.Item name="skip_reason" label="跳过原因" rules={[{ required: true, message: '跳过必须填写原因' }]}>
              <Input.TextArea rows={2} placeholder="如：小额差旅费，先行垫付" />
            </Form.Item>
          ) : (
            <>
              <Form.Item name="contract_id" label="收款对应的甲方合同" rules={[{ required: true, message: '请选择甲方合同' }]}>
                <Select showSearch optionFilterProp="label" placeholder="选择甲方合同"
                  options={clientContracts
                    .filter(c => !receiptModal?.project_id || c.project_id === receiptModal.project_id)
                    .map(c => ({
                      value: c.contract_id,
                      label: `${c.contract_no} ${c.contract_name || ''} (已收 ${formatMoney(c.paid_amount)})`,
                    }))} />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="receipt_amount" label="本次收款金额" rules={[{ required: true, message: '请填写收款金额' }]}>
                    <InputNumber style={{ width: '100%' }} min={0.01} prefix="¥" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="receipt_date" label="收款日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
                </Col>
              </Row>
              <Form.Item name="note" label="备注"><Input.TextArea rows={2} /></Form.Item>
            </>
          )}
        </Form>
      </Modal>

      <Modal title="创建报销单据" open={!!documentModal} onOk={handleDocument} onCancel={() => setDocumentModal(null)}>
        <p>报销人: {documentModal?.applicant_name} | 金额: {formatMoney(documentModal?.amount_with_tax)}</p>
        <Form form={documentForm} layout="vertical">
          <Form.Item name="document_no" label="单据号" tooltip="留空则自动生成 BX-日期-编号"><Input placeholder="留空自动生成" /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="生成会计凭证" open={!!voucherModal} onOk={handleVoucher} onCancel={() => setVoucherModal(null)} width={560}>
        <p>单据号: {voucherModal?.document_no || '-'} | 金额: {formatMoney(voucherModal?.amount_with_tax)}</p>
        <Form form={voucherForm} layout="vertical">
          <Form.Item name="voucher_no" label="凭证号" tooltip="留空则自动生成 PZ-日期-编号"><Input placeholder="留空自动生成" /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item label="凭证附件">
            <FileUpload entityType="reimbursement" entityId={voucherModal?.reimburse_id || ''} files={voucherFiles} onChange={setVoucherFiles} maxCount={5} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="付款操作" open={!!payModal} onOk={handlePay} onCancel={() => setPayModal(null)}>
        <p>凭证号: {payModal?.voucher_no || '-'} | 单据号: {payModal?.document_no || '-'}</p>
        <Form form={payForm} layout="vertical">
          <Form.Item name="payment_amount" label="付款金额" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="payment_method" label="付款方式" rules={[{ required: true }]}>
            <Select options={[{ value: 'bank_transfer', label: '银行转账' }, { value: 'cash', label: '现金' }]} />
          </Form.Item>
          <Form.Item name="payment_time" label="付款时间" rules={[{ required: true }]}><DatePicker showTime style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="报销链路进度" open={!!detailRecord} onCancel={() => setDetailRecord(null)} footer={null} width={700}>
        {detailRecord && (
          <>
            <Steps
              size="small"
              current={detailRecord.status === 'rejected' ? 0 : chainIndex(detailRecord.status)}
              status={detailRecord.status === 'rejected' ? 'error' : 'process'}
              items={REIMBURSE_CHAIN_STEPS}
              style={{ marginBottom: 16 }}
            />
            <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
              <Descriptions.Item label="当前状态">{REIMBURSE_STATUS[detailRecord.status]?.label || detailRecord.status}</Descriptions.Item>
              <Descriptions.Item label="下一步">{detailRecord.next_step_label || '已完结'}</Descriptions.Item>
              <Descriptions.Item label="项目收款">
                {detailRecord.receipt_skipped
                  ? <Tag color="orange">管理员跳过：{detailRecord.receipt_skip_reason}</Tag>
                  : detailRecord.receipt_confirmed_at
                    ? `${formatMoney(detailRecord.receipt_amount)}（${detailRecord.receipt_contract_no || '-'}，${detailRecord.receipt_date || '-'}）`
                    : '未确认'}
              </Descriptions.Item>
              <Descriptions.Item label="收款确认人">{detailRecord.receipt_confirmed_by_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="单据号">{detailRecord.document_no || '-'}</Descriptions.Item>
              <Descriptions.Item label="单据创建人">{detailRecord.document_created_by_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="凭证号">{detailRecord.voucher_no || '-'}</Descriptions.Item>
              <Descriptions.Item label="凭证生成人">{detailRecord.voucher_generated_by_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="付款金额">{detailRecord.payment_amount ? formatMoney(detailRecord.payment_amount) : '-'}</Descriptions.Item>
              <Descriptions.Item label="付款时间">{detailRecord.payment_time || '-'}</Descriptions.Item>
            </Descriptions>
            {!!detailRecord.audit_logs?.length && (
              <Table
                style={{ marginTop: 16 }}
                size="small" pagination={false} rowKey={(_, i) => String(i)}
                dataSource={detailRecord.audit_logs}
                columns={[
                  { title: '环节', dataIndex: 'audit_level', key: 'level' },
                  { title: '操作', dataIndex: 'action', key: 'action' },
                  { title: '操作人', dataIndex: 'auditor_name', key: 'auditor_name' },
                  { title: '时间', dataIndex: 'audit_time', key: 'audit_time',
                    render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
                  { title: '意见', dataIndex: 'comments', key: 'comments', ellipsis: true },
                ]}
              />
            )}
          </>
        )}
      </Modal>

      {fileRecord && <FileManager open={!!fileRecord} title={`${fileRecord?.applicant_name || ''} 报销凭证`} entityType="reimbursement" entityId={fileRecord?.reimburse_id || ''} files={fileRecord?.vouchers || []} canEdit={['pending_review', 'rejected'].includes(fileRecord?.status) && (fileRecord?.applicant_id === user.user_id || user.role === 'admin')} onSave={async (files) => { await reimbursementApi.update(fileRecord.reimburse_id, { vouchers: files }); loadData(); }} onClose={() => setFileRecord(null)} />}
    </div>
  );
}
