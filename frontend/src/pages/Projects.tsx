import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, DatePicker, Space, Tag, message, Popconfirm, Typography } from 'antd';
import { PlusOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../api/client';
import dayjs from 'dayjs';

const { Title } = Typography;
const statusMap: Record<string, { label: string; color: string }> = {
  active: { label: '进行中', color: 'blue' }, completed: { label: '已完成', color: 'green' },
  suspended: { label: '已暂停', color: 'orange' }, cancelled: { label: '已取消', color: 'red' },
};

export default function Projects() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const canEdit = ['admin', 'project_manager'].includes(user.role);
  const canDelete = user.role === 'admin';

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try { const res = await projectApi.list(); setData(res.data.data || []); } catch {} finally { setLoading(false); }
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (values.start_date) values.start_date = values.start_date.format('YYYY-MM-DD');
    if (values.end_date) values.end_date = values.end_date.format('YYYY-MM-DD');
    try {
      if (editing) { await projectApi.update(editing.project_id, values); message.success('更新成功'); }
      else { await projectApi.create(values); message.success('创建成功'); }
      setModalOpen(false); form.resetFields(); setEditing(null); loadData();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const handleDelete = async (id: string) => {
    try { await projectApi.delete(id); message.success('删除成功'); loadData(); } catch (e: any) { message.error(e.response?.data?.detail || '删除失败'); }
  };

  const columns = [
    { title: '项目名称', dataIndex: 'project_name', key: 'project_name',
      render: (name: string, r: any) => <a onClick={() => navigate(`/projects/${r.project_id}`)}>{name}</a> },
    { title: '客户', dataIndex: 'client_name', key: 'client_name' },
    { title: '负责人', dataIndex: 'project_manager_name', key: 'project_manager_name' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const st = statusMap[s]; return st ? <Tag color={st.color}>{st.label}</Tag> : s; } },
    { title: '开始日期', dataIndex: 'start_date', key: 'start_date' },
    { title: '结束日期', dataIndex: 'end_date', key: 'end_date' },
    { title: '操作', key: 'action', width: 240, render: (_: any, record: any) => (
      <Space>
        <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/projects/${record.project_id}`)}>详情</Button>
        {canEdit && <Button size="small" onClick={() => { setEditing(record); form.setFieldsValue({ ...record, start_date: record.start_date ? dayjs(record.start_date) : null, end_date: record.end_date ? dayjs(record.end_date) : null }); setModalOpen(true); }}>编辑</Button>}
        {canDelete && <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.project_id)}><Button size="small" danger>删除</Button></Popconfirm>}
      </Space>
    )},
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>项目管理</Title>
        {canEdit && <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setModalOpen(true); }}>新建项目</Button>}
      </div>
      <Table columns={columns} dataSource={data} rowKey="project_id" loading={loading} size="middle" />
      <Modal title={editing ? '编辑项目' : '新建项目'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={600}>
        <Form form={form} layout="vertical">
          <Form.Item name="project_name" label="项目名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="client_name" label="客户名称"><Input /></Form.Item>
          <Form.Item name="project_manager_name" label="项目负责人"><Input /></Form.Item>
          <Form.Item name="description" label="项目描述"><Input.TextArea rows={3} /></Form.Item>
          <Space>
            <Form.Item name="start_date" label="开始日期"><DatePicker /></Form.Item>
            <Form.Item name="end_date" label="结束日期"><DatePicker /></Form.Item>
          </Space>
          <Form.Item name="address" label="项目地址"><Input /></Form.Item>
          {editing && <Form.Item name="status" label="状态"><Select options={Object.entries(statusMap).map(([k, v]) => ({ value: k, label: v.label }))} /></Form.Item>}
        </Form>
      </Modal>
    </div>
  );
}
