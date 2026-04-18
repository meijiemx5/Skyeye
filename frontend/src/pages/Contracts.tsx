import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, InputNumber, DatePicker, Space, Tag, message, Popconfirm, Typography, Card, Row, Col, Statistic } from 'antd';
import { PlusOutlined, DollarOutlined } from '@ant-design/icons';
import { contractApi, projectApi } from '../api/client';
import FileUpload, { FileInfo } from '../components/FileUpload';
import FileManager from '../components/FileManager';
import dayjs from 'dayjs';

const { Title } = Typography;
const typeMap: Record<string, string> = { client: '甲方合同', supplier: '供应商采购合同', construction: '施工人员施工合同' };
const statusMap: Record<string, { label: string; color: string }> = {
  draft: { label: '待签订', color: 'default' }, signed: { label: '已签订', color: 'blue' },
  fulfilled: { label: '已履行', color: 'green' }, terminated: { label: '已终止', color: 'red' },
};

export default function Contracts() {
  const [data, setData] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [filterType, setFilterType] = useState<string>('');
  const [projects, setProjects] = useState<any[]>([]);
  const [attachments, setAttachments] = useState<FileInfo[]>([]);
  const [fileRecord, setFileRecord] = useState<any>(null);
  const [payRecord, setPayRecord] = useState<any>(null);
  const [form] = Form.useForm();
  const [payForm] = Form.useForm();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const canCreate = ['admin', 'project_manager', 'procurement'].includes(user.role);
  const canPay = ['admin', 'finance'].includes(user.role);
  const canDelete = user.role === 'admin';

  useEffect(() => { loadData(); loadStats(); loadProjects(); }, [filterType]);

  const loadProjects = async () => {
    try { const res = await projectApi.list(); setProjects(res.data.data || []); } catch {}
  };

  const loadData = async () => {
    setLoading(true);
    try { const res = await contractApi.list({ contract_type: filterType || undefined }); setData(res.data.data || []); } catch {} finally { setLoading(false); }
  };

  const loadStats = async () => {
    try { const res = await contractApi.statistics(); setStats(res.data.data); } catch {}
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (values.sign_date) values.sign_date = values.sign_date.format('YYYY-MM-DD');
    if (values.work_start_date) values.work_start_date = values.work_start_date.format('YYYY-MM-DD');
    if (values.work_end_date) values.work_end_date = values.work_end_date.format('YYYY-MM-DD');
    values.attachments = attachments;
    try {
      if (editing) { await contractApi.update(editing.contract_id, values); message.success('更新成功'); }
      else { await contractApi.create(values); message.success('创建成功'); }
      setModalOpen(false); form.resetFields(); setEditing(null); setAttachments([]); loadData(); loadStats();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const handleDelete = async (id: string) => {
    try { await contractApi.delete(id); message.success('删除成功'); loadData(); loadStats(); } catch (e: any) { message.error(e.response?.data?.detail || '删除失败'); }
  };

  const columns = [
    { title: '合同编号', dataIndex: 'contract_no', key: 'contract_no', width: 160 },
    { title: '合同名称', dataIndex: 'contract_name', key: 'contract_name' },
    { title: '关联项目', dataIndex: 'project_name', key: 'project_name' },
    { title: '类型', dataIndex: 'contract_type', key: 'contract_type', render: (t: string) => typeMap[t] || t },
    { title: '合同主体', dataIndex: 'party_name', key: 'party_name' },
    { title: '金额(含税)', dataIndex: 'amount_with_tax', key: 'amount_with_tax', render: (v: number) => v ? `¥${v.toLocaleString()}` : '-' },
    { title: '已付款', key: 'paid_amount', render: (_: any, r: any) => <Space><span>{r.paid_amount ? `¥${r.paid_amount.toLocaleString()}` : '¥0'}</span>{canPay && <Button type="link" size="small" icon={<DollarOutlined />} onClick={() => { setPayRecord(r); payForm.resetFields(); }}>付款</Button>}</Space> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const st = statusMap[s]; return st ? <Tag color={st.color}>{st.label}</Tag> : s; } },
    { title: '附件', key: 'attachments', width: 80, render: (_: any, record: any) => <Button type="link" size="small" onClick={() => setFileRecord(record)}>{record.attachments?.length ? `${record.attachments.length}个` : '管理'}</Button> },
    { title: '签订日期', dataIndex: 'sign_date', key: 'sign_date' },
    ...(canCreate || canDelete ? [{ title: '操作', key: 'action', width: 150, render: (_: any, record: any) => (
      <Space>
        {canCreate && <Button size="small" onClick={() => { setEditing(record); setAttachments(record.attachments || []); form.setFieldsValue({ ...record, sign_date: record.sign_date ? dayjs(record.sign_date) : null, work_start_date: record.work_start_date ? dayjs(record.work_start_date) : null, work_end_date: record.work_end_date ? dayjs(record.work_end_date) : null }); setModalOpen(true); }}>编辑</Button>}
        {canDelete && <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.contract_id)}><Button size="small" danger>删除</Button></Popconfirm>}
      </Space>
    )}] : []),
  ];

  return (
    <div>
      <Title level={4}>合同管理</Title>
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}><Card size="small"><Statistic title="合同总数" value={stats.total_count} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="总金额" value={stats.total_amount} prefix="¥" precision={2} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="已付款" value={stats.total_paid} prefix="¥" precision={2} valueStyle={{ color: '#3f8600' }} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="未付款" value={stats.total_unpaid} prefix="¥" precision={2} valueStyle={{ color: '#cf1322' }} /></Card></Col>
        </Row>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Select value={filterType} onChange={setFilterType} style={{ width: 200 }} allowClear placeholder="按类型筛选"
            options={[{ value: '', label: '全部' }, ...Object.entries(typeMap).map(([k, v]) => ({ value: k, label: v }))]} />
        </Space>
        {canCreate && <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setAttachments([]); setModalOpen(true); }}>新建合同</Button>}
      </div>
      <Table columns={columns} dataSource={data} rowKey="contract_id" loading={loading} size="middle" scroll={{ x: 1200 }} />
      <Modal title={editing ? '编辑合同' : '新建合同'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={700}>
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}><Form.Item name="contract_name" label="合同名称" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="contract_type" label="合同类型" rules={[{ required: true }]}><Select options={Object.entries(typeMap).map(([k, v]) => ({ value: k, label: v }))} /></Form.Item></Col>
          </Row>
          <Form.Item name="project_id" label="关联项目" rules={[{ required: true, message: '请选择关联项目' }]}>
            <Select placeholder="选择关联项目" showSearch optionFilterProp="label"
              options={projects.map(p => ({ value: p.project_id, label: p.project_name }))}
              onChange={(v) => { const p = projects.find(x => x.project_id === v); if (p) form.setFieldValue('project_name', p.project_name); }}
            />
          </Form.Item>
          <Form.Item name="project_name" hidden><Input /></Form.Item>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="party_name" label="合同主体名称" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="party_phone" label="联系电话"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="amount_with_tax" label="金额(含税)"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="amount_without_tax" label="金额(不含税)"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="sign_date" label="签订日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="work_start_date" label="工期开始"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="work_end_date" label="工期结束"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}>{editing && <Form.Item name="status" label="状态"><Select options={Object.entries(statusMap).map(([k, v]) => ({ value: k, label: v.label }))} /></Form.Item>}</Col>
          </Row>
          <Form.Item name="remarks" label="备注"><Input.TextArea rows={2} /></Form.Item>
          {editing && (
            <Form.Item label="附件">
              <FileUpload entityType="contract" entityId={editing?.contract_id || ''} files={attachments} onChange={setAttachments} />
            </Form.Item>
          )}
        </Form>
      </Modal>
      {fileRecord && <FileManager open={!!fileRecord} title={fileRecord?.contract_name || '合同'} entityType="contract" entityId={fileRecord?.contract_id || ''} files={fileRecord?.attachments || []} canEdit={canCreate} onSave={async (files) => { await contractApi.update(fileRecord.contract_id, { attachments: files }); loadData(); }} onClose={() => setFileRecord(null)} />}
      <Modal title={`合同付款 - ${payRecord?.contract_name || ''}`} open={!!payRecord} onOk={async () => {
        const v = await payForm.validateFields(); if (v.payment_date) v.payment_date = v.payment_date.format('YYYY-MM-DD');
        try { await contractApi.addPayment(payRecord.contract_id, v); message.success('付款登记成功'); setPayRecord(null); payForm.resetFields(); loadData(); loadStats(); } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
      }} onCancel={() => setPayRecord(null)}>
        <p>合同金额: ¥{payRecord?.amount_with_tax?.toLocaleString() || 0} | 已付: ¥{payRecord?.paid_amount?.toLocaleString() || 0} | 未付: ¥{((payRecord?.amount_with_tax || 0) - (payRecord?.paid_amount || 0)).toLocaleString()}</p>
        <Form form={payForm} layout="vertical">
          <Form.Item name="amount" label="本次付款金额" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={0.01} /></Form.Item>
          <Form.Item name="payment_method" label="付款方式" rules={[{ required: true }]}><Select options={[{ value: 'bank_transfer', label: '银行转账' }, { value: 'cash', label: '现金' }, { value: 'check', label: '支票' }]} /></Form.Item>
          <Form.Item name="payment_date" label="付款日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
