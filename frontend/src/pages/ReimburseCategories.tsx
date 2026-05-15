import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, Space, Tag, message, Typography, Popconfirm, Switch } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { reimburseCategoryApi } from '../api/client';

const { Title } = Typography;

interface CategoryNode {
  category_id: string;
  name: string;
  parent_id?: string | null;
  level: number;
  sort_order: number;
  is_active: boolean;
  code?: string | null;
  children?: CategoryNode[];
}

export default function ReimburseCategories() {
  const [tree, setTree] = useState<CategoryNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CategoryNode | null>(null);
  const [parentForNew, setParentForNew] = useState<CategoryNode | null>(null);
  const [form] = Form.useForm();

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await reimburseCategoryApi.tree();
      setTree(res.data.data || []);
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载失败');
    } finally { setLoading(false); }
  };

  const openCreate = (parent: CategoryNode | null) => {
    setEditing(null);
    setParentForNew(parent);
    form.resetFields();
    form.setFieldsValue({ sort_order: 0, is_active: true });
    setModalOpen(true);
  };

  const openEdit = (record: CategoryNode) => {
    setEditing(record);
    setParentForNew(null);
    form.setFieldsValue({
      name: record.name,
      sort_order: record.sort_order,
      code: record.code,
      is_active: record.is_active,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await reimburseCategoryApi.update(editing.category_id, values);
        message.success('更新成功');
      } else {
        await reimburseCategoryApi.create({ ...values, parent_id: parentForNew?.category_id || null });
        message.success('创建成功');
      }
      setModalOpen(false); form.resetFields(); setEditing(null); setParentForNew(null);
      loadData();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const handleDelete = async (id: string) => {
    try { await reimburseCategoryApi.delete(id); message.success('删除成功'); loadData(); }
    catch (e: any) { message.error(e.response?.data?.detail || '删除失败'); }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '层级', dataIndex: 'level', key: 'level', width: 80,
      render: (l: number) => l === 1 ? <Tag color="blue">大类</Tag> : <Tag color="green">子类</Tag> },
    { title: '编码', dataIndex: 'code', key: 'code', width: 120 },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80,
      render: (a: boolean) => a ? <Tag color="green">启用</Tag> : <Tag>停用</Tag> },
    { title: '操作', key: 'action', width: 280, render: (_: any, r: CategoryNode) => (
      <Space>
        {r.level === 1 && <Button size="small" icon={<PlusOutlined />} onClick={() => openCreate(r)}>添加子类</Button>}
        <Button size="small" onClick={() => openEdit(r)}>编辑</Button>
        <Popconfirm title="确定删除此分类？" onConfirm={() => handleDelete(r.category_id)}>
          <Button size="small" danger>删除</Button>
        </Popconfirm>
      </Space>
    )},
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>报销类型管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate(null)}>新增大类</Button>
      </div>
      <Table
        columns={columns}
        dataSource={tree}
        rowKey="category_id"
        loading={loading}
        size="middle"
        expandable={{ defaultExpandAllRows: true, childrenColumnName: 'children' }}
        pagination={false}
      />
      <Modal title={editing ? '编辑分类' : (parentForNew ? `新增子类（父类: ${parentForNew.name}）` : '新增大类')}
             open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}><Input /></Form.Item>
          <Form.Item name="code" label="编码（可选）"><Input placeholder="便于报表/导出区分" /></Form.Item>
          <Form.Item name="sort_order" label="排序" tooltip="数值越小越靠前"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          {editing && <Form.Item name="is_active" label="启用" valuePropName="checked"><Switch /></Form.Item>}
        </Form>
      </Modal>
    </div>
  );
}
