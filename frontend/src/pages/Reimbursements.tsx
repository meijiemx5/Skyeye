import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, InputNumber, DatePicker, Space, Tag, message, Typography } from 'antd';
import { PlusOutlined, CheckOutlined, DollarOutlined } from '@ant-design/icons';
import { reimbursementApi, projectApi } from '../api/client';
import dayjs from 'dayjs';
import FileUpload, { FileInfo } from '../components/FileUpload';
import FileManager from '../components/FileManager';

const { Title } = Typography;
const statusMap: Record<string, { label: string; color: string }> = {
  pending_review: { label: '待审核', color: 'orange' }, manager_approved: { label: '主管已审', color: 'blue' },
  finance_approved: { label: '财务已审', color: 'cyan' }, paid: { label: '已付款', color: 'green' }, rejected: { label: '已驳回', color: 'red' },
};
const expenseTypes: Record<string, string> = { material: '物料采购', travel: '差旅费', equipment_rental: '设备租赁', other: '其他' };

export default function Reimbursements() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [auditModal, setAuditModal] = useState<any>(null);
  const [payModal, setPayModal] = useState<any>(null);
  const [vouchers, setVouchers] = useState<FileInfo[]>([]);
  const [editingReimburse, setEditingReimburse] = useState<any>(null);
  const [fileRecord, setFileRecord] = useState<any>(null);
  const [form] = Form.useForm();
  const [auditForm] = Form.useForm();
  const [payForm] = Form.useForm();
  const [projects, setProjects] = useState<any[]>([]);
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  useEffect(() => { loadData(); projectApi.list().then(r => setProjects(r.data.data || [])).catch(() => {}); }, []);
  const loadData = async () => {
    setLoading(true);
    try { const res = await reimbursementApi.list(); setData(res.data.data || []); } catch {} finally { setLoading(false); }
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (values.expense_date) values.expense_date = values.expense_date.format('YYYY-MM-DD');
    values.vouchers = vouchers;
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

  const handleAudit = async () => {
    const values = await auditForm.validateFields();
    try { await reimbursementApi.audit(auditModal.reimburse_id, values); message.success('审核成功'); setAuditModal(null); auditForm.resetFields(); loadData(); }
    catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const handlePay = async () => {
    const values = await payForm.validateFields();
    if (values.payment_time) values.payment_time = values.payment_time.format('YYYY-MM-DD HH:mm');
    try { await reimbursementApi.pay(payModal.reimburse_id, values); message.success('付款成功'); setPayModal(null); payForm.resetFields(); loadData(); }
    catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const columns = [
    { title: '报销人', dataIndex: 'applicant_name', key: 'applicant_name' },
    { title: '项目', dataIndex: 'project_name', key: 'project_name' },
    { title: '类型', dataIndex: 'expense_type', key: 'expense_type', render: (t: string) => expenseTypes[t] || t },
    { title: '金额', dataIndex: 'amount_with_tax', key: 'amount_with_tax', render: (v: number) => `¥${v?.toLocaleString() || 0}` },
    { title: '事由', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const st = statusMap[s]; return st ? <Tag color={st.color}>{st.label}</Tag> : s; } },
    { title: '凭证', key: 'vouchers', width: 80, render: (_: any, record: any) => <Button type="link" size="small" onClick={() => setFileRecord(record)}>{record.vouchers?.length ? `${record.vouchers.length}个` : '管理'}</Button> },
    { title: '发生日期', dataIndex: 'expense_date', key: 'expense_date' },
    { title: '操作', key: 'action', width: 250, render: (_: any, r: any) => (
      <Space>
        {['pending_review', 'rejected'].includes(r.status) && (r.applicant_id === user.user_id || user.role === 'admin') &&
          <Button size="small" onClick={() => { setEditingReimburse(r); setVouchers(r.vouchers || []); form.setFieldsValue({ ...r, expense_date: r.expense_date ? dayjs(r.expense_date) : null }); setModalOpen(true); }}>编辑</Button>
        }
        {(r.status === 'pending_review' || r.status === 'manager_approved') && ['admin', 'project_manager', 'finance'].includes(user.role) &&
          <Button size="small" icon={<CheckOutlined />} onClick={() => { setAuditModal(r); auditForm.resetFields(); }}>审核</Button>
        }
        {r.status === 'finance_approved' && ['admin', 'finance'].includes(user.role) &&
          <Button size="small" type="primary" icon={<DollarOutlined />} onClick={() => { setPayModal(r); payForm.setFieldsValue({ payment_amount: r.amount_with_tax }); }}>付款</Button>
        }
      </Space>
    )},
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>报销管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setVouchers([]); setEditingReimburse(null); setModalOpen(true); }}>提交报销</Button>
      </div>
      <Table columns={columns} dataSource={data} rowKey="reimburse_id" loading={loading} size="middle" scroll={{ x: 1000 }} />

      <Modal title={editingReimburse ? '编辑报销申请' : '提交报销申请'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={600}>
        <Form form={form} layout="vertical">
          <Form.Item name="expense_type" label="报销类型" rules={[{ required: true }]}>
            <Select options={Object.entries(expenseTypes).map(([k, v]) => ({ value: k, label: v }))} />
          </Form.Item>
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

      <Modal title="审核报销" open={!!auditModal} onOk={handleAudit} onCancel={() => setAuditModal(null)}>
        <p>报销人: {auditModal?.applicant_name} | 金额: ¥{auditModal?.amount_with_tax} | 事由: {auditModal?.description}</p>
        <Form form={auditForm} layout="vertical">
          <Form.Item name="action" label="审核结果" rules={[{ required: true }]}>
            <Select options={[{ value: 'approved', label: '通过' }, { value: 'rejected', label: '驳回' }]} />
          </Form.Item>
          <Form.Item name="comments" label="审核意见"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="付款操作" open={!!payModal} onOk={handlePay} onCancel={() => setPayModal(null)}>
        <Form form={payForm} layout="vertical">
          <Form.Item name="payment_amount" label="付款金额" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="payment_method" label="付款方式" rules={[{ required: true }]}>
            <Select options={[{ value: 'bank_transfer', label: '银行转账' }, { value: 'cash', label: '现金' }]} />
          </Form.Item>
          <Form.Item name="payment_time" label="付款时间" rules={[{ required: true }]}><DatePicker showTime style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>
      {fileRecord && <FileManager open={!!fileRecord} title={`${fileRecord?.applicant_name || ''} 报销凭证`} entityType="reimbursement" entityId={fileRecord?.reimburse_id || ''} files={fileRecord?.vouchers || []} canEdit={['pending_review', 'rejected'].includes(fileRecord?.status) && (fileRecord?.applicant_id === user.user_id || user.role === 'admin')} onSave={async (files) => { await reimbursementApi.update(fileRecord.reimburse_id, { vouchers: files }); loadData(); }} onClose={() => setFileRecord(null)} />}
    </div>
  );
}
