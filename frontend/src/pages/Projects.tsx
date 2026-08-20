import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, DatePicker, InputNumber, Space, Tag, message, Popconfirm, Typography, Row, Col, Progress } from 'antd';
import { PlusOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi, alertApi } from '../api/client';
import dayjs from 'dayjs';
import FileUpload, { FileInfo } from '../components/FileUpload';
import ChecklistDots, { ChecklistItem } from '../components/ChecklistDots';
import { formatMoney } from '../utils/constants';

const { Title } = Typography;
const statusMap: Record<string, { label: string; color: string }> = {
  active: { label: '进行中', color: 'blue' }, completed: { label: '已完成', color: 'green' },
  suspended: { label: '已暂停', color: 'orange' }, cancelled: { label: '已取消', color: 'red' },
};

export default function Projects() {
  const [data, setData] = useState<any[]>([]);
  const [checklists, setChecklists] = useState<Record<string, { items: ChecklistItem[]; health_score: number }>>({});
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [budgetDocs, setBudgetDocs] = useState<FileInfo[]>([]);
  const [quoteDocs, setQuoteDocs] = useState<FileInfo[]>([]);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const canEdit = ['admin', 'project_manager'].includes(user.role);
  const canDelete = user.role === 'admin';

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [projectRes, boardRes] = await Promise.allSettled([
        projectApi.list(),
        alertApi.board({ project_status: 'all' }),
      ]);
      if (projectRes.status === 'fulfilled') setData(projectRes.value.data.data || []);
      if (boardRes.status === 'fulfilled') {
        const map: Record<string, any> = {};
        for (const p of boardRes.value.data.data?.projects || []) map[p.project_id] = p;
        setChecklists(map);
      }
    } catch {} finally { setLoading(false); }
  };

  const openModal = (record?: any) => {
    setEditing(record || null);
    setBudgetDocs(record?.budget_docs || []);
    setQuoteDocs(record?.quote_docs || []);
    if (record) {
      form.setFieldsValue({
        ...record,
        start_date: record.start_date ? dayjs(record.start_date) : null,
        end_date: record.end_date ? dayjs(record.end_date) : null,
      });
    } else {
      form.resetFields();
    }
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (values.start_date) values.start_date = values.start_date.format('YYYY-MM-DD');
    if (values.end_date) values.end_date = values.end_date.format('YYYY-MM-DD');
    values.budget_docs = budgetDocs;
    values.quote_docs = quoteDocs;
    try {
      if (editing) { await projectApi.update(editing.project_id, values); message.success('更新成功'); }
      else { await projectApi.create(values); message.success('创建成功'); }
      setModalOpen(false); form.resetFields(); setEditing(null); setBudgetDocs([]); setQuoteDocs([]); loadData();
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
    { title: '预算', dataIndex: 'budget_amount', key: 'budget_amount', width: 120,
      render: (v: number) => v ? formatMoney(v) : <Tag color="orange">未填</Tag> },
    { title: '报价', dataIndex: 'quote_amount', key: 'quote_amount', width: 120,
      render: (v: number) => v ? formatMoney(v) : <Tag color="orange">未填</Tag> },
    { title: '完整度', key: 'checklist', width: 220, render: (_: any, r: any) => {
      const checklist = checklists[r.project_id];
      if (!checklist) return '-';
      return (
        <Space direction="vertical" size={2}>
          <ChecklistDots items={checklist.items} />
          <Progress
            percent={checklist.health_score} size="small" style={{ width: 150 }}
            strokeColor={checklist.health_score >= 90 ? '#0f9d58' : checklist.health_score >= 60 ? '#f59e0b' : '#e5484d'}
          />
        </Space>
      );
    } },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90, render: (s: string) => { const st = statusMap[s]; return st ? <Tag color={st.color}>{st.label}</Tag> : s; } },
    { title: '开始日期', dataIndex: 'start_date', key: 'start_date', width: 110 },
    { title: '结束日期', dataIndex: 'end_date', key: 'end_date', width: 110 },
    { title: '操作', key: 'action', width: 220, render: (_: any, record: any) => (
      <Space>
        <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/projects/${record.project_id}`)}>详情</Button>
        {canEdit && <Button size="small" onClick={() => openModal(record)}>编辑</Button>}
        {canDelete && <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.project_id)}><Button size="small" danger>删除</Button></Popconfirm>}
      </Space>
    )},
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>项目管理</Title>
        {canEdit && <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>新建项目</Button>}
      </div>
      <Table columns={columns} dataSource={data} rowKey="project_id" loading={loading} size="middle" scroll={{ x: 1400 }} />
      <Modal title={editing ? '编辑项目' : '新建项目'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={680}>
        <Form form={form} layout="vertical">
          <Form.Item name="project_name" label="项目名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="client_name" label="客户名称"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="project_manager_name" label="项目负责人"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="budget_amount" label="项目预算" tooltip="预算用于成本超支预警，未填写会在项目看板亮灯">
                <InputNumber style={{ width: '100%' }} min={0} prefix="¥" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quote_amount" label="项目报价">
                <InputNumber style={{ width: '100%' }} min={0} prefix="¥" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="项目描述"><Input.TextArea rows={2} /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="start_date" label="开始日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={12}><Form.Item name="end_date" label="结束日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="address" label="项目地址"><Input /></Form.Item>
          {editing && <Form.Item name="status" label="状态"><Select options={Object.entries(statusMap).map(([k, v]) => ({ value: k, label: v.label }))} /></Form.Item>}
          {editing && (
            <>
              <Form.Item label="预算表附件">
                <FileUpload entityType="project" entityId={editing.project_id} files={budgetDocs} onChange={setBudgetDocs} maxCount={5} />
              </Form.Item>
              <Form.Item label="报价单附件">
                <FileUpload entityType="project" entityId={editing.project_id} files={quoteDocs} onChange={setQuoteDocs} maxCount={5} />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
}
