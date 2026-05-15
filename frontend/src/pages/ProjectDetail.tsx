import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Row, Col, Statistic, Typography, Tabs, Table, Tag, Spin, Descriptions, Breadcrumb, Button, message } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { projectApi, contractApi, reimbursementApi, inventoryApi, analysisApi, acceptanceApi, reimburseCategoryApi } from '../api/client';
import FileManager from '../components/FileManager';

const { Title } = Typography;
const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2'];

const projectStatusMap: Record<string, { label: string; color: string }> = {
  active: { label: '进行中', color: 'blue' }, completed: { label: '已完成', color: 'green' },
  suspended: { label: '已暂停', color: 'orange' }, cancelled: { label: '已取消', color: 'red' },
};
const contractTypeMap: Record<string, string> = {
  client: '甲方合同', supplier: '供应商采购合同', construction: '施工人员施工合同',
};
const contractStatusMap: Record<string, { label: string; color: string }> = {
  draft: { label: '待签订', color: 'default' }, signed: { label: '已签订', color: 'blue' },
  fulfilled: { label: '已履行', color: 'green' }, terminated: { label: '已终止', color: 'red' },
};
const reimburseStatusMap: Record<string, { label: string; color: string }> = {
  pending_review: { label: '待审核', color: 'orange' }, manager_approved: { label: '主管已审', color: 'blue' },
  finance_approved: { label: '财务已审', color: 'cyan' }, paid: { label: '已付款', color: 'green' }, rejected: { label: '已驳回', color: 'red' },
};
const legacyReimburseTypeLabels: Record<string, string> = {
  material: '物料采购', travel: '差旅费', equipment_rental: '设备租赁', other: '其他',
};
const acceptanceStatusMap: Record<string, { label: string; color: string }> = {
  pending_upload: { label: '待上传', color: 'default' },
  uploaded: { label: '已上传', color: 'blue' },
  pending_acceptance: { label: '待验收', color: 'orange' },
  accepted: { label: '已验收', color: 'green' },
  needs_rectification: { label: '需整改', color: 'red' },
};
const acceptanceResultMap: Record<string, { label: string; color: string }> = {
  passed: { label: '合格', color: 'green' },
  failed: { label: '不合格', color: 'red' },
};

export default function ProjectDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [project, setProject] = useState<any>(null);
  const [contracts, setContracts] = useState<any[]>([]);
  const [reimbursements, setReimbursements] = useState<any[]>([]);
  const [stockRecords, setStockRecords] = useState<any[]>([]);
  const [acceptances, setAcceptances] = useState<any[]>([]);
  const [analysis, setAnalysis] = useState<any>(null);
  const [acceptanceFileRecord, setAcceptanceFileRecord] = useState<any>(null);
  const [contractFileRecord, setContractFileRecord] = useState<any>(null);
  const [reimburseFileRecord, setReimburseFileRecord] = useState<any>(null);
  const [categoryTree, setCategoryTree] = useState<any[]>([]);
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const canEditAcceptance = ['admin', 'project_manager'].includes(user.role);
  const canEditContract = ['admin', 'project_manager', 'procurement'].includes(user.role);

  useEffect(() => {
    reimburseCategoryApi.tree().then(r => setCategoryTree(r.data.data || [])).catch(() => {});
  }, []);

  const renderExpenseLabel = (record: any) => {
    const subId = record.expense_subcategory_id;
    const catId = record.expense_category_id;
    if (subId) {
      const parent = categoryTree.find((c: any) => c.category_id === catId);
      const child = parent?.children?.find((c: any) => c.category_id === subId);
      if (child) return parent ? `${parent.name} / ${child.name}` : child.name;
    }
    if (catId) {
      const parent = categoryTree.find((c: any) => c.category_id === catId);
      if (parent) return parent.name;
    }
    const t = record.expense_type;
    return legacyReimburseTypeLabels[t] || categoryTree.find((c: any) => c.category_id === t)?.name || t || '-';
  };

  useEffect(() => { if (id) loadAll(id); }, [id]);

  const loadAll = async (pid: string) => {
    setLoading(true);
    try {
      const [pRes, cRes, rRes, sRes, accRes, aRes] = await Promise.allSettled([
        projectApi.get(pid),
        contractApi.list({ project_id: pid }),
        reimbursementApi.list({ project_id: pid }),
        inventoryApi.listRecords({ project_id: pid }),
        acceptanceApi.list({ project_id: pid }),
        analysisApi.projectAnalysis(pid),
      ]);
      if (pRes.status === 'fulfilled') setProject(pRes.value.data.data);
      if (cRes.status === 'fulfilled') setContracts(cRes.value.data.data || []);
      if (rRes.status === 'fulfilled') setReimbursements(rRes.value.data.data || []);
      if (sRes.status === 'fulfilled') setStockRecords(sRes.value.data.data || []);
      if (accRes.status === 'fulfilled') setAcceptances(accRes.value.data.data || []);
      if (aRes.status === 'fulfilled') setAnalysis(aRes.value.data.data);
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载失败');
    } finally { setLoading(false); }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!project) return <div>项目不存在</div>;

  const cost = analysis?.cost || {};
  const revenue = analysis?.revenue || {};
  const profit = analysis?.profit || {};
  const payment = analysis?.payment_progress || {};

  const pieData = [
    { name: '采购成本', value: cost.supplier_cost || 0 },
    { name: '施工成本', value: cost.construction_cost || 0 },
    { name: '报销成本', value: cost.reimbursement_cost || 0 },
    { name: '物料成本', value: cost.material_cost || 0 },
  ].filter(d => d.value > 0);

  const paymentBars = [
    { name: '甲方收款', planned: revenue.client_contract_amount || 0, paid: revenue.client_paid_amount || 0 },
    { name: '供应商付款', planned: cost.supplier_cost || 0, paid: payment.supplier_paid || 0 },
    { name: '施工付款', planned: cost.construction_cost || 0, paid: payment.construction_paid || 0 },
  ];

  const contractColumns = [
    { title: '合同编号', dataIndex: 'contract_no', key: 'contract_no', width: 160 },
    { title: '合同名称', dataIndex: 'contract_name', key: 'contract_name' },
    { title: '类型', dataIndex: 'contract_type', key: 'contract_type', render: (t: string) => contractTypeMap[t] || t },
    { title: '合同主体', dataIndex: 'party_name', key: 'party_name' },
    { title: '金额(含税)', dataIndex: 'amount_with_tax', key: 'amount_with_tax', render: (v: number) => v ? `¥${v.toLocaleString()}` : '-' },
    { title: '已付款', dataIndex: 'paid_amount', key: 'paid_amount', render: (v: number) => v ? `¥${v.toLocaleString()}` : '¥0' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const st = contractStatusMap[s]; return st ? <Tag color={st.color}>{st.label}</Tag> : s; } },
    { title: '附件', key: 'attachments', width: 80, render: (_: any, r: any) => <Button type="link" size="small" onClick={() => setContractFileRecord(r)}>{r.attachments?.length ? `${r.attachments.length}个` : '查看'}</Button> },
    { title: '签订日期', dataIndex: 'sign_date', key: 'sign_date' },
  ];

  const reimburseColumns = [
    { title: '报销人', dataIndex: 'applicant_name', key: 'applicant_name' },
    { title: '类型', key: 'expense_type', render: (_: any, r: any) => renderExpenseLabel(r) },
    { title: '金额', dataIndex: 'amount_with_tax', key: 'amount_with_tax', render: (v: number) => `¥${v?.toLocaleString() || 0}` },
    { title: '事由', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const x = reimburseStatusMap[s]; return x ? <Tag color={x.color}>{x.label}</Tag> : s; } },
    { title: '凭证', key: 'vouchers', width: 80, render: (_: any, r: any) => <Button type="link" size="small" onClick={() => setReimburseFileRecord(r)}>{r.vouchers?.length ? `${r.vouchers.length}个` : '查看'}</Button> },
    { title: '发生日期', dataIndex: 'expense_date', key: 'expense_date' },
  ];

  const acceptanceColumns = [
    { title: '验收日期', dataIndex: 'acceptance_date', key: 'acceptance_date', render: (v: string) => v || '-' },
    { title: '验收地点', dataIndex: 'acceptance_location', key: 'acceptance_location', render: (v: string) => v || '-' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const x = acceptanceStatusMap[s]; return x ? <Tag color={x.color}>{x.label}</Tag> : s; } },
    { title: '资料', key: 'docs', width: 80, render: (_: any, r: any) => {
      const count = (r.basic_docs?.length || 0) + (r.engineering_docs?.length || 0);
      return <Button type="link" size="small" onClick={() => setAcceptanceFileRecord(r)}>{count ? `${count}个` : '查看'}</Button>;
    } },
    { title: '验收结果', dataIndex: 'result', key: 'result', render: (v: string) => { const x = acceptanceResultMap[v]; return x ? <Tag color={x.color}>{x.label}</Tag> : '-'; } },
  ];

  const stockColumns = [
    { title: '物料', dataIndex: 'material_name', key: 'material_name' },
    { title: '类型', dataIndex: 'record_type', key: 'record_type', render: (t: string) => t === 'in' ? <Tag color="green">入库</Tag> : t === 'out' ? <Tag color="blue">出库</Tag> : <Tag color="orange">盘点</Tag> },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    { title: '供应商/领用人', key: 'party', render: (_: any, r: any) => r.supplier_name || r.requester_name || '-' },
    { title: '合同', dataIndex: 'contract_no', key: 'contract_no', render: (v: string) => v || '-' },
    { title: '日期', dataIndex: 'record_date', key: 'record_date' },
  ];

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 12 }}
        items={[
          { title: <a onClick={() => navigate('/projects')}>项目管理</a> },
          { title: project.project_name },
        ]} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          {project.project_name}{' '}
          {(() => { const st = projectStatusMap[project.status]; return st ? <Tag color={st.color}>{st.label}</Tag> : null; })()}
        </Title>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}><Card size="small"><Statistic title="甲方合同金额" value={revenue.client_contract_amount || 0} prefix="¥" precision={2} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="总成本" value={cost.total_cost || 0} prefix="¥" precision={2} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="利润" value={profit.profit || 0} prefix="¥" precision={2} valueStyle={{ color: (profit.profit || 0) >= 0 ? '#52c41a' : '#ff4d4f' }} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="利润率" value={profit.profit_rate || 0} suffix="%" precision={2} /></Card></Col>
      </Row>

      <Tabs items={[
        { key: 'info', label: '基本信息', children: (
          <Card>
            <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
              <Descriptions.Item label="项目名称">{project.project_name}</Descriptions.Item>
              <Descriptions.Item label="客户">{project.client_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="负责人">{project.project_manager_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="状态">{(() => { const st = projectStatusMap[project.status]; return st ? <Tag color={st.color}>{st.label}</Tag> : project.status; })()}</Descriptions.Item>
              <Descriptions.Item label="开始日期">{project.start_date || '-'}</Descriptions.Item>
              <Descriptions.Item label="结束日期">{project.end_date || '-'}</Descriptions.Item>
              <Descriptions.Item label="项目地址" span={2}>{project.address || '-'}</Descriptions.Item>
              <Descriptions.Item label="项目描述" span={2}>{project.description || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        )},
        { key: 'contracts', label: `关联合同 (${contracts.length})`, children: (
          <Table columns={contractColumns} dataSource={contracts} rowKey="contract_id" size="middle" scroll={{ x: 1100 }} />
        )},
        { key: 'reimbursements', label: `报销明细 (${reimbursements.length})`, children: (
          <Table columns={reimburseColumns} dataSource={reimbursements} rowKey="reimburse_id" size="middle" scroll={{ x: 900 }} />
        )},
        { key: 'inventory', label: `出入库记录 (${stockRecords.length})`, children: (
          <Table columns={stockColumns} dataSource={stockRecords} rowKey="record_id" size="middle" scroll={{ x: 1100 }} />
        )},
        { key: 'acceptances', label: `验收资料 (${acceptances.length})`, children: (
          <Table columns={acceptanceColumns} dataSource={acceptances} rowKey="acceptance_id" size="middle" />
        )},
        { key: 'analysis', label: '成本分析', children: (
          <>
            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Card title="成本构成" style={{ marginBottom: 16 }}>
                  {pieData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={260}>
                      <PieChart>
                        <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} label dataKey="value">
                          {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                        </Pie>
                        <Tooltip formatter={(v: any) => `¥${Number(v).toLocaleString()}`} />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <div style={{ color: '#999', textAlign: 'center', padding: 40 }}>暂无成本数据</div>}
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card title="收付款进度" style={{ marginBottom: 16 }}>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={paymentBars}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip formatter={(v: any) => `¥${Number(v).toLocaleString()}`} />
                      <Legend />
                      <Bar dataKey="planned" name="合同金额" fill="#1677ff" />
                      <Bar dataKey="paid" name="已收/付款" fill="#52c41a" />
                    </BarChart>
                  </ResponsiveContainer>
                </Card>
              </Col>
            </Row>
            <Card title="详细数据">
              <Descriptions column={{ xs: 1, sm: 2, md: 3 }} bordered size="small">
                <Descriptions.Item label="甲方合同金额">¥{(revenue.client_contract_amount || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="甲方已收款">¥{(revenue.client_paid_amount || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="甲方未收款">¥{(revenue.client_unpaid_amount || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="采购成本">¥{(cost.supplier_cost || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="施工成本">¥{(cost.construction_cost || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="报销成本">¥{(cost.reimbursement_cost || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="物料成本">¥{(cost.material_cost || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="总成本">¥{(cost.total_cost || 0).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="利润">¥{(profit.profit || 0).toLocaleString()}（{profit.profit_rate || 0}%）</Descriptions.Item>
              </Descriptions>
            </Card>
          </>
        )},
      ]} />

      {contractFileRecord && (
        <FileManager
          open={!!contractFileRecord}
          title={contractFileRecord?.contract_name || '合同'}
          entityType="contract"
          entityId={contractFileRecord?.contract_id || ''}
          files={contractFileRecord?.attachments || []}
          canEdit={canEditContract}
          onSave={async (files) => {
            await contractApi.update(contractFileRecord.contract_id, { attachments: files });
            if (id) loadAll(id);
          }}
          onClose={() => setContractFileRecord(null)}
        />
      )}

      {reimburseFileRecord && (
        <FileManager
          open={!!reimburseFileRecord}
          title={`${reimburseFileRecord?.applicant_name || ''} 报销凭证`}
          entityType="reimbursement"
          entityId={reimburseFileRecord?.reimburse_id || ''}
          files={reimburseFileRecord?.vouchers || []}
          canEdit={['pending_review', 'rejected'].includes(reimburseFileRecord?.status) && (reimburseFileRecord?.applicant_id === user.user_id || user.role === 'admin')}
          onSave={async (files) => {
            await reimbursementApi.update(reimburseFileRecord.reimburse_id, { vouchers: files });
            if (id) loadAll(id);
          }}
          onClose={() => setReimburseFileRecord(null)}
        />
      )}

      {acceptanceFileRecord && (
        <FileManager
          open={!!acceptanceFileRecord}
          title={`${acceptanceFileRecord?.project_name || '验收'} 验收资料`}
          entityType="acceptance"
          entityId={acceptanceFileRecord?.acceptance_id || ''}
          files={[...(acceptanceFileRecord?.basic_docs || []), ...(acceptanceFileRecord?.engineering_docs || [])]}
          canEdit={canEditAcceptance}
          onSave={async (files) => {
            await acceptanceApi.update(acceptanceFileRecord.acceptance_id, { basic_docs: files, engineering_docs: [] });
            if (id) loadAll(id);
          }}
          onClose={() => setAcceptanceFileRecord(null)}
        />
      )}
    </div>
  );
}
