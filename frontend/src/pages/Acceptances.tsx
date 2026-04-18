import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, DatePicker, Space, Tag, message, Typography, Popconfirm } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { acceptanceApi } from '../api/client';

const { Title } = Typography;
const statusMap: Record<string, { label: string; color: string }> = {
  pending_upload: { label: '待上传', color: 'default' }, uploaded: { label: '已上传', color: 'blue' },
  pending_acceptance: { label: '待验收', color: 'orange' }, accepted: { label: '已验收', color: 'green' }, needs_rectification: { label: '需整改', color: 'red' },
};

export default function Acceptances() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [form] = Form.useForm();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const canEdit = ['admin', 'project_manager'].includes(user.role);
  const canDelete = user.role === 'admin';

  useEffect(() => { loadData(); }, []);
  const loadData = async () => {
    setLoading(true);
    try { const res = await acceptanceApi.list(); setData(res.data.data || []); } catch {} finally { setLoading(false); }
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (values.acceptance_date) values.acceptance_date = values.acceptance_date.format('YYYY-MM-DD');
    try {
      if (editing) { await acceptanceApi.update(editing.acceptance_id, values); message.success('更新成功'); }
      else { await acceptanceApi.create(values); message.success('创建成功'); }
      setModalOpen(false); form.resetFields(); setEditing(null); loadData();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const handleDelete = async (id: string) => {
    try { await acceptanceApi.delete(id); message.success('删除成功'); loadData(); } catch (e: any) { message.error(e.response?.data?.detail || '删除失败'); }
  };

  const columns = [
    { title: '项目名称', dataIndex: 'project_name', key: 'project_name' },
    { title: '验收日期', dataIndex: 'acceptance_date', key: 'acceptance_date' },
    { title: '验收地点', dataIndex: 'acceptance_location', key: 'acceptance_location' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const st = statusMap[s]; return st ? <Tag color={st.color}>{st.label}</Tag> : s; } },
    { title: '验收结果', dataIndex: 'result', key: 'result', render: (r: string) => r === 'passed' ? <Tag color="green">合格</Tag> : r === 'failed' ? <Tag color="red">不合格</Tag> : '-' },
    ...(canEdit || canDelete ? [{ title: '操作', key: 'action', render: (_: any, record: any) => (
      <Space>
        {canEdit && <Button size="small" onClick={() => { setEditing(record); form.setFieldsValue(record); setModalOpen(true); }}>编辑</Button>}
        {canDelete && <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.acceptance_id)}><Button size="small" danger>删除</Button></Popconfirm>}
      </Space>
    )}] : []),
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>验收资料管理</Title>
        {canEdit && <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setModalOpen(true); }}>新建验收</Button>}
      </div>
      <Table columns={columns} dataSource={data} rowKey="acceptance_id" loading={loading} size="middle" />
      <Modal title={editing ? '编辑验收记录' : '新建验收记录'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={600}>
        <Form form={form} layout="vertical">
          {!editing && <Form.Item name="project_name" label="项目名称" rules={[{ required: true }]}><Input /></Form.Item>}
          {!editing && <Form.Item name="project_id" label="项目ID" rules={[{ required: true }]}><Input /></Form.Item>}
          <Form.Item name="acceptance_date" label="验收日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="acceptance_location" label="验收地点"><Input /></Form.Item>
          {editing && <Form.Item name="status" label="状态"><Select options={Object.entries(statusMap).map(([k, v]) => ({ value: k, label: v.label }))} /></Form.Item>}
          {editing && <Form.Item name="result" label="验收结果"><Select allowClear options={[{ value: 'passed', label: '合格' }, { value: 'failed', label: '不合格' }]} /></Form.Item>}
          {editing && <Form.Item name="rectification_requirements" label="整改要求"><Input.TextArea rows={2} /></Form.Item>}
        </Form>
      </Modal>
    </div>
  );
}
