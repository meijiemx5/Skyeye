import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, Select, Spin, Table, Descriptions, Divider } from 'antd';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { analysisApi, projectApi } from '../api/client';

const { Title } = Typography;
const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2'];

export default function Analysis() {
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [overview, setOverview] = useState<any>(null);
  const [projectData, setProjectData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { loadProjects(); loadOverview(); }, []);
  useEffect(() => { if (selectedProject) loadProjectAnalysis(selectedProject); }, [selectedProject]);

  const loadProjects = async () => {
    try { const res = await projectApi.list(); setProjects(res.data.data || []); } catch {}
  };

  const loadOverview = async () => {
    setLoading(true);
    try { const res = await analysisApi.overview(); setOverview(res.data.data); } catch {} finally { setLoading(false); }
  };

  const loadProjectAnalysis = async (pid: string) => {
    setLoading(true);
    try { const res = await analysisApi.projectAnalysis(pid); setProjectData(res.data.data); } catch {} finally { setLoading(false); }
  };

  if (loading && !overview) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const projectChartData = overview?.projects?.map((p: any) => ({ name: p.project_name?.substring(0, 8), revenue: p.revenue, cost: p.cost, profit: p.profit })) || [];

  return (
    <div>
      <Title level={4}>项目分析</Title>

      {overview && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}><Card size="small"><Statistic title="总收入" value={overview.summary.total_revenue} prefix="¥" precision={2} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="总成本" value={overview.summary.total_cost} prefix="¥" precision={2} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="活跃项目" value={overview.summary.active_projects} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="待审报销" value={overview.summary.pending_reimbursements} valueStyle={{ color: '#faad14' }} /></Card></Col>
          </Row>

          {projectChartData.length > 0 && (
            <Card title="项目收入/成本/利润对比" style={{ marginBottom: 16 }}>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={projectChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(v: any) => `¥${Number(v).toLocaleString()}`} />
                  <Legend />
                  <Bar dataKey="revenue" name="收入" fill="#1677ff" />
                  <Bar dataKey="cost" name="成本" fill="#faad14" />
                  <Bar dataKey="profit" name="利润" fill="#52c41a" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          <Table
            columns={[
              { title: '项目', dataIndex: 'project_name', key: 'project_name' },
              { title: '状态', dataIndex: 'status', key: 'status' },
              { title: '收入', dataIndex: 'revenue', key: 'revenue', render: (v: number) => `¥${v?.toLocaleString() || 0}` },
              { title: '成本', dataIndex: 'cost', key: 'cost', render: (v: number) => `¥${v?.toLocaleString() || 0}` },
              { title: '利润', dataIndex: 'profit', key: 'profit', render: (v: number) => <span style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>¥{v?.toLocaleString() || 0}</span> },
              { title: '利润率', dataIndex: 'profit_rate', key: 'profit_rate', render: (v: number) => `${v}%` },
            ]}
            dataSource={overview.projects}
            rowKey="project_id"
            size="middle"
            style={{ marginBottom: 16 }}
          />
        </>
      )}

      <Divider />
      <Title level={5}>单项目分析</Title>
      <Select value={selectedProject || undefined} onChange={setSelectedProject} style={{ width: 300, marginBottom: 16 }} placeholder="选择项目查看详细分析"
        options={projects.map((p: any) => ({ value: p.project_id, label: p.project_name }))} />

      {projectData && (
        <Row gutter={16}>
          <Col span={12}>
            <Card title="收入与成本">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="甲方合同金额">¥{projectData.revenue.client_contract_amount?.toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="总成本">¥{projectData.cost.total_cost?.toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="利润">¥{projectData.profit.profit?.toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="利润率">{projectData.profit.profit_rate}%</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
          <Col span={12}>
            <Card title="成本构成">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={[
                    { name: '采购成本', value: projectData.cost.supplier_cost },
                    { name: '施工成本', value: projectData.cost.construction_cost },
                    { name: '报销成本', value: projectData.cost.reimbursement_cost },
                    { name: '物料成本', value: projectData.cost.material_cost },
                  ].filter(d => d.value > 0)} cx="50%" cy="50%" outerRadius={70} label dataKey="value">
                    {[0,1,2,3].map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: any) => `¥${Number(v).toLocaleString()}`} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
