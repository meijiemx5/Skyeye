import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, Space, Tag, message, Typography, Popconfirm, Switch } from 'antd';
import { PlusOutlined, KeyOutlined } from '@ant-design/icons';
import { authApi } from '../api/client';

const { Title } = Typography;
const roleOptions = [
  { value: 'admin', label: '管理员' },
  { value: 'finance', label: '财务人员' },
  { value: 'project_manager', label: '项目负责人' },
  { value: 'procurement', label: '采购专员' },
  { value: 'construction', label: '施工人员' },
  { value: 'warehouse', label: '仓库管理员' },
];
const roleColors: Record<string, string> = { admin: 'red', finance: 'blue', project_manager: 'green', procurement: 'orange', construction: 'cyan', warehouse: 'purple' };
const roleLabels: Record<string, string> = { admin: '管理员', finance: '财务人员', project_manager: '项目负责人', procurement: '采购专员', construction: '施工人员', warehouse: '仓库管理员' };

export default function Users() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [form] = Form.useForm();

  useEffect(() => { loadData(); }, []);
  const loadData = async () => {
    setLoading(true);
    try { const res = await authApi.listUsers(); setData(res.data.data || []); } catch {} finally { setLoading(false); }
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) { await authApi.updateUser(editing.user_id, values); message.success('更新成功'); }
      else { await authApi.createUser(values); message.success('创建成功'); }
      setModalOpen(false); form.resetFields(); setEditing(null); loadData();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const handleDelete = async (id: string) => {
    try { await authApi.deleteUser(id); message.success('删除成功'); loadData(); } catch (e: any) { message.error(e.response?.data?.detail || '删除失败'); }
  };

  const handleToggleActive = async (user: any) => {
    try { await authApi.updateUser(user.user_id, { is_active: !user.is_active }); message.success('状态更新成功'); loadData(); } catch {}
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '姓名', dataIndex: 'display_name', key: 'display_name' },
    { title: '角色', dataIndex: 'role', key: 'role', render: (r: string) => <Tag color={roleColors[r]}>{roleLabels[r] || r}</Tag> },
    { title: '部门', dataIndex: 'department', key: 'department' },
    { title: '电话', dataIndex: 'phone', key: 'phone' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    { title: '状态', dataIndex: 'is_active', key: 'is_active', render: (v: boolean, record: any) => <Switch checked={v} onChange={() => handleToggleActive(record)} checkedChildren="启用" unCheckedChildren="禁用" /> },
    { title: '操作', key: 'action', width: 250, render: (_: any, record: any) => (
      <Space>
        <Popconfirm title="确定重置密码为 123456 ?" onConfirm={async () => { try { await authApi.resetPassword(record.user_id); message.success('密码已重置为: 123456'); } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); } }}>
          <Button size="small" icon={<KeyOutlined />}>重置密码</Button>
        </Popconfirm>
        <Button size="small" onClick={() => { setEditing(record); form.setFieldsValue(record); setModalOpen(true); }}>编辑</Button>
        <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.user_id)}><Button size="small" danger>删除</Button></Popconfirm>
      </Space>
    )},
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>用户管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setModalOpen(true); }}>新建用户</Button>
      </div>
      <Table columns={columns} dataSource={data} rowKey="user_id" loading={loading} size="middle" />
      <Modal title={editing ? '编辑用户' : '新建用户'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={500}>
        <Form form={form} layout="vertical">
          {!editing && <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input /></Form.Item>}
          {!editing && <Form.Item name="password" label="密码" rules={[{ required: true }]}><Input.Password /></Form.Item>}
          <Form.Item name="display_name" label="姓名" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}><Select options={roleOptions} /></Form.Item>
          <Form.Item name="department" label="部门"><Input /></Form.Item>
          <Form.Item name="phone" label="电话"><Input /></Form.Item>
          <Form.Item name="email" label="邮箱"><Input /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
