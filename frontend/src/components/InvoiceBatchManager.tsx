import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Modal, Table, Button, Form, Input, InputNumber, Select, DatePicker, Space, Tag,
  Popconfirm, message, Row, Col, Progress, Alert, Empty, Typography,
} from 'antd';
import { PlusOutlined, FileAddOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { invoiceApi } from '../api/client';
import FileUpload, { FileInfo } from './FileUpload';
import {
  BATCH_STATUS, INVOICE_CATEGORIES, INVOICE_CATEGORY_LABELS, PAYMENT_STAGES,
  TAX_RATE_OPTIONS, formatMoney,
} from '../utils/constants';

const { Text } = Typography;

interface ContractOption {
  contract_id: string;
  contract_no?: string;
  contract_name?: string;
  project_id?: string;
  project_name?: string;
  amount_with_tax?: number;
}

interface InvoiceBatchManagerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  canManage: boolean;
  /** 固定到某个合同；不传则由用户从 contractOptions 里选 */
  contractId?: string;
  /** 按项目查看该项目所有批次 */
  projectId?: string;
  contractOptions?: ContractOption[];
}

/** 含税 → 不含税 + 税额，与后端 services/invoice_calc.py 同一算法 */
function splitAmount(amountWithTax?: number | null, taxRatePercent?: number | null) {
  const total = Number(amountWithTax || 0);
  const rate = Number(taxRatePercent || 0) / 100;
  const withoutTax = Math.round((total / (1 + rate)) * 100) / 100;
  return { withoutTax, tax: Math.round((total - withoutTax) * 100) / 100 };
}

export default function InvoiceBatchManager({
  open, title, onClose, canManage, contractId, projectId, contractOptions = [],
}: InvoiceBatchManagerProps) {
  const [batches, setBatches] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const [batchModal, setBatchModal] = useState<{ editing?: any } | null>(null);
  const [invoiceModal, setInvoiceModal] = useState<{ batch: any; editing?: any } | null>(null);
  const [attachments, setAttachments] = useState<FileInfo[]>([]);
  const [batchForm] = Form.useForm();
  const [invoiceForm] = Form.useForm();

  const watchedAmount = Form.useWatch('amount_with_tax', invoiceForm);
  const watchedRate = Form.useWatch('tax_rate', invoiceForm);
  const derived = useMemo(() => splitAmount(watchedAmount, watchedRate), [watchedAmount, watchedRate]);

  const loadData = useCallback(async () => {
    if (!contractId && !projectId) return;
    setLoading(true);
    try {
      const params = contractId ? { contract_id: contractId } : { project_id: projectId };
      const [batchRes, summaryRes] = await Promise.allSettled([
        invoiceApi.listBatches(params),
        invoiceApi.summary(params),
      ]);
      if (batchRes.status === 'fulfilled') setBatches(batchRes.value.data.data || []);
      if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value.data.data);
    } finally {
      setLoading(false);
    }
  }, [contractId, projectId]);

  useEffect(() => { if (open) loadData(); }, [open, loadData]);

  // --- 批次 ---------------------------------------------------------------

  const openBatchModal = (editing?: any) => {
    batchForm.resetFields();
    if (editing) {
      batchForm.setFieldsValue({
        ...editing,
        issue_date: editing.issue_date ? dayjs(editing.issue_date) : null,
      });
    } else {
      batchForm.setFieldsValue({
        payment_stage: 'advance', status: 'issued', issue_date: dayjs(),
        contract_id: contractId || undefined,
      });
    }
    setBatchModal({ editing });
  };

  const submitBatch = async () => {
    const values = await batchForm.validateFields();
    if (values.issue_date) values.issue_date = values.issue_date.format('YYYY-MM-DD');
    try {
      if (batchModal?.editing) {
        await invoiceApi.updateBatch(batchModal.editing.batch_id, values);
        message.success('批次更新成功');
      } else {
        const contract = contractOptions.find(c => c.contract_id === values.contract_id);
        await invoiceApi.createBatch({
          ...values,
          contract_id: values.contract_id || contractId,
          contract_no: contract?.contract_no,
          project_id: contract?.project_id || projectId,
          project_name: contract?.project_name,
        });
        message.success('批次创建成功');
      }
      setBatchModal(null);
      loadData();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败');
    }
  };

  const deleteBatch = async (batch: any) => {
    try {
      await invoiceApi.deleteBatch(batch.batch_id);
      message.success('批次已删除');
      loadData();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败');
    }
  };

  // --- 单张发票 -----------------------------------------------------------

  const openInvoiceModal = (batch: any, editing?: any) => {
    invoiceForm.resetFields();
    setAttachments(editing?.attachments || []);
    if (editing) {
      invoiceForm.setFieldsValue({
        ...editing,
        tax_rate: Math.round(Number(editing.tax_rate || 0) * 10000) / 100,
        issue_date: editing.issue_date ? dayjs(editing.issue_date) : null,
      });
    } else {
      invoiceForm.setFieldsValue({
        category: 'material', tax_rate: 13,
        issue_date: batch.issue_date ? dayjs(batch.issue_date) : dayjs(),
      });
    }
    setInvoiceModal({ batch, editing });
  };

  const submitInvoice = async () => {
    const values = await invoiceForm.validateFields();
    if (values.issue_date) values.issue_date = values.issue_date.format('YYYY-MM-DD');
    values.attachments = attachments;
    const { batch, editing } = invoiceModal!;
    try {
      if (editing) {
        await invoiceApi.updateInvoice(batch.batch_id, editing.invoice_id, values);
        message.success('发票更新成功');
      } else {
        await invoiceApi.addInvoice(batch.batch_id, values);
        message.success('发票添加成功');
      }
      setInvoiceModal(null);
      loadData();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败');
    }
  };

  const deleteInvoice = async (batch: any, invoice: any) => {
    try {
      await invoiceApi.deleteInvoice(batch.batch_id, invoice.invoice_id);
      message.success('发票已删除');
      loadData();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败');
    }
  };

  // --- 表格 ---------------------------------------------------------------

  const batchColumns = [
    { title: '批次号', dataIndex: 'batch_no', key: 'batch_no', width: 150 },
    { title: '批次说明', dataIndex: 'batch_name', key: 'batch_name',
      render: (v: string, r: any) => v || r.payment_stage_label || '-' },
    { title: '款项阶段', dataIndex: 'payment_stage_label', key: 'payment_stage', width: 90 },
    { title: '开票日期', dataIndex: 'issue_date', key: 'issue_date', width: 110 },
    { title: '张数', dataIndex: 'invoice_count', key: 'invoice_count', width: 70,
      render: (v: number) => `${v || 0} 张` },
    { title: '含税合计', dataIndex: 'total_amount_with_tax', key: 'total', width: 130,
      render: (v: number) => formatMoney(v) },
    { title: '税额', dataIndex: 'total_tax_amount', key: 'tax', width: 110,
      render: (v: number) => formatMoney(v) },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => { const x = BATCH_STATUS[s]; return x ? <Tag color={x.color}>{x.label}</Tag> : s; } },
    ...(canManage ? [{ title: '操作', key: 'action', width: 210, render: (_: any, r: any) => (
      <Space size={4}>
        <Button size="small" type="link" icon={<FileAddOutlined />} onClick={() => openInvoiceModal(r)}>加发票</Button>
        <Button size="small" type="link" onClick={() => openBatchModal(r)}>编辑</Button>
        <Popconfirm title={`删除批次 ${r.batch_no}？其下 ${r.invoice_count || 0} 张发票会一起删除`} onConfirm={() => deleteBatch(r)}>
          <Button size="small" type="link" danger>删除</Button>
        </Popconfirm>
      </Space>
    )}] : []),
  ];

  const invoiceColumns = (batch: any) => [
    { title: '发票号码', dataIndex: 'invoice_no', key: 'invoice_no', render: (v: string) => v || '-' },
    { title: '类别', dataIndex: 'category', key: 'category', width: 90,
      render: (v: string) => <Tag>{INVOICE_CATEGORY_LABELS[v] || v}</Tag> },
    { title: '税率', dataIndex: 'tax_rate', key: 'tax_rate', width: 70,
      render: (v: number) => `${Math.round(Number(v || 0) * 10000) / 100}%` },
    { title: '含税金额', dataIndex: 'amount_with_tax', key: 'amount_with_tax', width: 130,
      render: (v: number) => formatMoney(v) },
    { title: '不含税', dataIndex: 'amount_without_tax', key: 'amount_without_tax', width: 130,
      render: (v: number) => formatMoney(v) },
    { title: '税额', dataIndex: 'tax_amount', key: 'tax_amount', width: 110,
      render: (v: number) => formatMoney(v) },
    { title: '开票日期', dataIndex: 'issue_date', key: 'issue_date', width: 110 },
    { title: '附件', key: 'attachments', width: 70,
      render: (_: any, r: any) => `${r.attachments?.length || 0} 个` },
    ...(canManage ? [{ title: '操作', key: 'action', width: 130, render: (_: any, r: any) => (
      <Space size={4}>
        <Button size="small" type="link" onClick={() => openInvoiceModal(batch, r)}>编辑</Button>
        <Popconfirm title="确定删除该张发票?" onConfirm={() => deleteInvoice(batch, r)}>
          <Button size="small" type="link" danger>删除</Button>
        </Popconfirm>
      </Space>
    )}] : []),
  ];

  const invoicedRate = Math.min(Number(summary?.invoiced_rate || 0), 100);

  return (
    <>
      <Modal title={`🧾 ${title} - 发票管理`} open={open} onCancel={onClose} footer={null} width={1080}>
        <Alert
          type="info" showIcon style={{ marginBottom: 12 }}
          message="发票分批次开具：一个批次代表一次开票行为，同一批次内材料/施工/技术服务税率不同的发票分开录入。"
        />

        <Row gutter={16} align="middle" style={{ marginBottom: 16 }}>
          <Col xs={24} md={14}>
            <Progress percent={Number(invoicedRate.toFixed(2))} status={summary?.fully_invoiced ? 'success' : 'active'} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              合同额 {formatMoney(summary?.contract_amount)} · 已开票 {formatMoney(summary?.invoiced_amount)} · 未开票 {formatMoney(summary?.remaining_amount)}
            </Text>
          </Col>
          <Col xs={24} md={10} style={{ textAlign: 'right' }}>
            <Space wrap>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {summary?.batch_count || 0} 个批次 / {summary?.invoice_count || 0} 张发票
              </Text>
              {canManage && (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => openBatchModal()}>新建批次</Button>
              )}
            </Space>
          </Col>
        </Row>

        <Table
          columns={batchColumns}
          dataSource={batches}
          rowKey="batch_id"
          loading={loading}
          size="small"
          scroll={{ x: 1000 }}
          pagination={false}
          locale={{ emptyText: <Empty description="还没有开票记录" /> }}
          expandable={{
            expandedRowRender: (batch: any) => (
              <Table
                columns={invoiceColumns(batch)}
                dataSource={batch.invoices || []}
                rowKey="invoice_id"
                size="small"
                pagination={false}
                scroll={{ x: 900 }}
                locale={{ emptyText: '该批次还没有录入发票' }}
              />
            ),
            defaultExpandAllRows: true,
          }}
        />

        {summary?.by_tax_rate && Object.keys(summary.by_tax_rate).length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Text type="secondary" style={{ fontSize: 12, marginRight: 8 }}>按税率汇总：</Text>
            <Space wrap>
              {Object.entries(summary.by_tax_rate).map(([rate, v]: [string, any]) => (
                <Tag key={rate} color="blue">{rate}：{formatMoney(v.amount_with_tax)}（税额 {formatMoney(v.tax_amount)}）</Tag>
              ))}
            </Space>
          </div>
        )}
      </Modal>

      <Modal
        title={batchModal?.editing ? `编辑批次 ${batchModal.editing.batch_no}` : '新建发票批次'}
        open={!!batchModal} onOk={submitBatch} onCancel={() => setBatchModal(null)} width={560}
      >
        <Form form={batchForm} layout="vertical">
          {!contractId && !batchModal?.editing && (
            <Form.Item name="contract_id" label="关联合同" rules={[{ required: true, message: '请选择合同' }]}>
              <Select showSearch optionFilterProp="label" placeholder="选择合同"
                options={contractOptions.map(c => ({
                  value: c.contract_id,
                  label: `${c.contract_no || ''} ${c.contract_name || ''}`.trim(),
                }))} />
            </Form.Item>
          )}
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="payment_stage" label="款项阶段" rules={[{ required: true }]}>
                <Select options={PAYMENT_STAGES} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="status" label="批次状态" rules={[{ required: true }]}>
                <Select options={Object.entries(BATCH_STATUS).map(([k, v]) => ({ value: k, label: v.label }))} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="batch_name" label="批次说明">
            <Input placeholder="如：预付款40万" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="issue_date" label="开票日期">
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="planned_amount" label="本批次计划开票额">
                <InputNumber style={{ width: '100%' }} min={0} prefix="¥" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="remarks" label="备注"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title={invoiceModal?.editing ? '编辑发票' : `向批次 ${invoiceModal?.batch?.batch_no || ''} 添加发票`}
        open={!!invoiceModal} onOk={submitInvoice} onCancel={() => setInvoiceModal(null)} width={640}
      >
        <Form form={invoiceForm} layout="vertical">
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="invoice_no" label="发票号码"><Input /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="invoice_code" label="发票代码"><Input /></Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="category" label="发票类别" rules={[{ required: true }]}>
                <Select
                  options={INVOICE_CATEGORIES.map(c => ({ value: c.value, label: c.label }))}
                  onChange={(v) => {
                    const preset = INVOICE_CATEGORIES.find(c => c.value === v);
                    if (preset) invoiceForm.setFieldValue('tax_rate', preset.defaultRate);
                  }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="tax_rate" label="税率(%)" rules={[{ required: true, message: '请填写税率' }]}>
                <Select options={TAX_RATE_OPTIONS} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="amount_with_tax" label="含税金额" rules={[{ required: true, message: '请填写含税金额' }]}>
                <InputNumber style={{ width: '100%' }} min={0.01} prefix="¥" />
              </Form.Item>
            </Col>
          </Row>

          <Alert
            type="success" style={{ marginBottom: 12 }}
            message={`按此税率换算：不含税 ${formatMoney(derived.withoutTax)}，税额 ${formatMoney(derived.tax)}`}
            description="发票上印的数字才是准的；如与换算结果不一致，在下面手工填写覆盖。"
          />

          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="amount_without_tax" label="不含税金额（可留空自动换算）">
                <InputNumber style={{ width: '100%' }} min={0} prefix="¥" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tax_amount" label="税额（可留空自动换算）">
                <InputNumber style={{ width: '100%' }} min={0} prefix="¥" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="issue_date" label="开票日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="buyer_name" label="购买方"><Input /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="seller_name" label="销售方"><Input /></Form.Item>
            </Col>
          </Row>
          <Form.Item name="remarks" label="备注"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item label="发票扫描件 / PDF">
            <FileUpload
              entityType="invoice"
              entityId={invoiceModal?.batch?.batch_id || ''}
              files={attachments}
              onChange={setAttachments}
              maxCount={5}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
