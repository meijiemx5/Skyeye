import { useEffect, useMemo, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, DatePicker, InputNumber, Space, Tag, message, Popconfirm, Typography, Row, Col, Progress, Alert } from 'antd';
import { PlusOutlined, EyeOutlined, SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi, alertApi, authApi } from '../api/client';
import dayjs from 'dayjs';
import FileUpload, { FileInfo } from '../components/FileUpload';
import ChecklistDots, { ChecklistItem } from '../components/ChecklistDots';
import { formatMoney } from '../utils/constants';

const { Title, Text } = Typography;
const statusMap: Record<string, { label: string; color: string }> = {
  active: { label: '进行中', color: 'blue' }, completed: { label: '已完成', color: 'green' },
  suspended: { label: '已暂停', color: 'orange' }, cancelled: { label: '已取消', color: 'red' },
};
const statusOrder = Object.keys(statusMap);

/** 完整度筛选：这一项只能在前端做，数据来自 /api/alerts/board 而不是项目列表接口 */
const healthOptions = [
  { value: 'overdue', label: '有逾期项' },
  { value: 'incomplete', label: '有未完成项' },
  { value: 'complete', label: '资料齐全' },
];

const textSorter = (a?: string, b?: string) => (a || '').localeCompare(b || '', 'zh-CN');
const numberSorter = (a?: number, b?: number) => (Number(a) || 0) - (Number(b) || 0);

const roleLabels: Record<string, string> = {
  admin: '管理员', finance: '财务', project_manager: '项目负责人',
  procurement: '采购', construction: '施工', warehouse: '仓库',
};

interface Checklist { items: ChecklistItem[]; health_score: number; counts: Record<string, number>; }

export default function Projects() {
  const [data, setData] = useState<any[]>([]);
  const [checklists, setChecklists] = useState<Record<string, Checklist>>({});
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

  // 服务端筛选（后端 list_projects 支持 status / keyword）
  const [filters, setFilters] = useState<{ status?: string; keyword?: string }>({});
  const [keywordInput, setKeywordInput] = useState('');
  // 前端筛选：负责人是手填文本、完整度来自另一个接口，后端没有对应查询条件
  const [managerFilter, setManagerFilter] = useState<string | undefined>();
  const [healthFilter, setHealthFilter] = useState<string | undefined>();
  const [users, setUsers] = useState<any[]>([]);

  useEffect(() => { loadData(); }, [filters.status, filters.keyword]);
  useEffect(() => {
    authApi.userOptions().then(r => setUsers(r.data.data || [])).catch(() => {});
  }, []);

  const loadData = async (overrides?: typeof filters) => {
    setLoading(true);
    try {
      const params: any = { ...(overrides ?? filters) };
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k]; });
      const [projectRes, boardRes] = await Promise.allSettled([
        projectApi.list(params),
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

  const resetFilters = () => {
    setKeywordInput('');
    setManagerFilter(undefined);
    setHealthFilter(undefined);
    setFilters({});
    loadData({});
  };

  // 负责人选项从当前结果里取：项目负责人是手填文本，系统里没有可查的负责人档案
  const managerOptions = useMemo(() => {
    const names = [...new Set(data.map(p => p.project_manager_name).filter(Boolean))];
    return names.sort((a, b) => textSorter(a, b)).map(n => ({ value: n, label: n }));
  }, [data]);

  const visibleData = useMemo(() => data.filter(p => {
    if (managerFilter && p.project_manager_name !== managerFilter) return false;
    if (healthFilter) {
      const counts = checklists[p.project_id]?.counts;
      if (!counts) return false;
      if (healthFilter === 'overdue' && !counts.overdue) return false;
      if (healthFilter === 'incomplete' && counts.ok >= counts.total) return false;
      if (healthFilter === 'complete' && counts.ok < counts.total) return false;
    }
    return true;
  }), [data, managerFilter, healthFilter, checklists]);

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
    // 编辑时把"清空负责人"表达成空串：后端按 exclude_none 处理请求，
    // 传 undefined 会被丢掉，负责人就清不掉了
    if (editing) values.project_manager_id = values.project_manager_id || '';
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
      sorter: (a: any, b: any) => textSorter(a.project_name, b.project_name),
      render: (name: string, r: any) => <a onClick={() => navigate(`/projects/${r.project_id}`)}>{name}</a> },
    { title: '客户', dataIndex: 'client_name', key: 'client_name',
      sorter: (a: any, b: any) => textSorter(a.client_name, b.client_name) },
    { title: '负责人', dataIndex: 'project_manager_name', key: 'project_manager_name', width: 130,
      sorter: (a: any, b: any) => textSorter(a.project_manager_name, b.project_manager_name),
      render: (name: string, r: any) => {
        if (!name) return <Tag color="orange">未指派</Tag>;
        // 只有名字没有账号 → 本人收不到待办，标出来让管理员补
        return r.project_manager_id
          ? name
          : <Space size={4}><span>{name}</span><Tag color="orange">未关联账号</Tag></Space>;
      } },
    { title: '预算', dataIndex: 'budget_amount', key: 'budget_amount', width: 130,
      sorter: (a: any, b: any) => numberSorter(a.budget_amount, b.budget_amount),
      render: (v: number) => v ? formatMoney(v) : <Tag color="orange">未填</Tag> },
    { title: '报价', dataIndex: 'quote_amount', key: 'quote_amount', width: 130,
      sorter: (a: any, b: any) => numberSorter(a.quote_amount, b.quote_amount),
      render: (v: number) => v ? formatMoney(v) : <Tag color="orange">未填</Tag> },
    { title: '完整度', key: 'checklist', width: 200,
      sorter: (a: any, b: any) => numberSorter(
        checklists[a.project_id]?.health_score, checklists[b.project_id]?.health_score),
      render: (_: any, r: any) => {
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
    { title: '状态', dataIndex: 'status', key: 'status', width: 90,
      sorter: (a: any, b: any) => statusOrder.indexOf(a.status) - statusOrder.indexOf(b.status),
      render: (s: string) => { const st = statusMap[s]; return st ? <Tag color={st.color}>{st.label}</Tag> : s; } },
    { title: '开始日期', dataIndex: 'start_date', key: 'start_date', width: 120,
      sorter: (a: any, b: any) => textSorter(a.start_date, b.start_date) },
    { title: '结束日期', dataIndex: 'end_date', key: 'end_date', width: 120,
      sorter: (a: any, b: any) => textSorter(a.end_date, b.end_date) },
    { title: '操作', key: 'action', width: 220, fixed: 'right' as const, render: (_: any, record: any) => (
      <Space>
        <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/projects/${record.project_id}`)}>详情</Button>
        {canEdit && <Button size="small" onClick={() => openModal(record)}>编辑</Button>}
        {canDelete && <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.project_id)}><Button size="small" danger>删除</Button></Popconfirm>}
      </Space>
    )},
  ];

  const filtered = visibleData.length !== data.length;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>项目管理</Title>
        {canEdit && <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>新建项目</Button>}
      </div>

      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col xs={24} sm={12} md={6}>
          <Input.Search allowClear placeholder="搜索项目/客户/负责人/地址"
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            onSearch={(v) => setFilters({ ...filters, keyword: v })} />
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Select allowClear placeholder="项目状态" style={{ width: '100%' }}
            value={filters.status}
            options={Object.entries(statusMap).map(([k, v]) => ({ value: k, label: v.label }))}
            onChange={(v) => setFilters({ ...filters, status: v })} />
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Select allowClear placeholder="按负责人" style={{ width: '100%' }}
            showSearch optionFilterProp="label"
            value={managerFilter}
            options={managerOptions}
            onChange={setManagerFilter} />
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Select allowClear placeholder="按完整度" style={{ width: '100%' }}
            value={healthFilter}
            options={healthOptions}
            onChange={setHealthFilter} />
        </Col>
        <Col xs={12} sm={6} md={6}>
          <Space>
            <Button icon={<SearchOutlined />} type="primary"
              onClick={() => setFilters({ ...filters, keyword: keywordInput })}>查询</Button>
            <Button icon={<ReloadOutlined />} onClick={resetFilters}>重置</Button>
          </Space>
        </Col>
      </Row>

      <Text type="secondary" style={{ fontSize: 12 }}>
        共 {visibleData.length} 个项目{filtered ? `（已从 ${data.length} 个中筛选）` : ''} · 点击表头可排序
      </Text>

      <Table columns={columns} dataSource={visibleData} rowKey="project_id" loading={loading}
        size="middle" scroll={{ x: 1500 }} style={{ marginTop: 8 }}
        pagination={{ showSizeChanger: true, showTotal: (t) => `共 ${t} 条`, defaultPageSize: 20 }} />

      <Modal title={editing ? '编辑项目' : '新建项目'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} width={680}>
        <Form form={form} layout="vertical">
          <Form.Item name="project_name" label="项目名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="client_name" label="客户名称"><Input /></Form.Item></Col>
            <Col span={12}>
              <Form.Item
                name="project_manager_id" label="项目负责人"
                tooltip="必须选择系统账号：预警和待办按账号派发，只写名字的话提醒不到本人"
              >
                <Select allowClear showSearch optionFilterProp="label" placeholder="选择负责人账号"
                  options={users.map(u => ({
                    value: u.user_id,
                    label: `${u.display_name || u.username}（${roleLabels[u.role] || u.role}）`,
                  }))} />
              </Form.Item>
            </Col>
          </Row>
          {/* 存量项目的负责人是手填文本，没有账号关联 —— 提醒重新选一次，否则收不到待办 */}
          {editing && !editing.project_manager_id && editing.project_manager_name && (
            <Alert
              type="warning" showIcon style={{ marginBottom: 16 }}
              message={`当前负责人「${editing.project_manager_name}」没有关联系统账号，本人收不到项目待办与预警，请重新选择。`}
            />
          )}
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
