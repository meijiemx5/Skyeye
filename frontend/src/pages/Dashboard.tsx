import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, List, Tag, Spin, Table, Progress, Button, Space, Empty } from 'antd';
import {
  ProjectOutlined, FileTextOutlined, AccountBookOutlined, InboxOutlined,
  WarningOutlined, CheckSquareOutlined, DashboardOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { analysisApi, inventoryApi, alertApi, todoApi } from '../api/client';
import TodoList, { TodoItem } from '../components/TodoList';
import ChecklistDots from '../components/ChecklistDots';
import { CHECKLIST_LABELS, formatMoney } from '../utils/constants';
import { can } from '../utils/permissions';

const { Title, Text } = Typography;

export default function Dashboard() {
  const [overview, setOverview] = useState<any>(null);
  const [warnings, setWarnings] = useState<any[]>([]);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [todoSummary, setTodoSummary] = useState<any>(null);
  const [board, setBoard] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [overviewRes, warningRes, todoRes, boardRes] = await Promise.allSettled([
        analysisApi.overview(),
        inventoryApi.getWarnings(),
        todoApi.list(),
        can('alerts:board') ? alertApi.board() : Promise.resolve(null),
      ]);
      if (overviewRes.status === 'fulfilled') setOverview(overviewRes.value.data.data);
      if (warningRes.status === 'fulfilled') setWarnings(warningRes.value.data.data || []);
      if (todoRes.status === 'fulfilled') {
        setTodos(todoRes.value.data.data?.todos || []);
        setTodoSummary(todoRes.value.data.data?.summary);
      }
      if (boardRes.status === 'fulfilled' && boardRes.value) setBoard(boardRes.value.data.data);
    } catch {} finally { setLoading(false); }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const s = overview?.summary || {};
  const boardSummary = board?.summary || {};
  const checklistKeys: string[] = board?.checklist_keys || Object.keys(CHECKLIST_LABELS);

  const boardColumns = [
    { title: '项目', dataIndex: 'project_name', key: 'project_name',
      render: (name: string, r: any) => (
        can('project:list')
          ? <a onClick={() => navigate(`/projects/${r.project_id}`)}>{name}</a>
          : <span>{name}</span>
      ) },
    { title: '负责人', dataIndex: 'project_manager_name', key: 'pm',
      width: 100, render: (v: string) => v || <Text type="secondary">未指派</Text> },
    { title: `完整度（${checklistKeys.map(k => CHECKLIST_LABELS[k] || k).join(' · ')}）`,
      key: 'items', width: 260,
      render: (_: any, r: any) => <ChecklistDots items={r.items} /> },
    { title: '健康度', dataIndex: 'health_score', key: 'health', width: 160,
      sorter: (a: any, b: any) => a.health_score - b.health_score,
      render: (v: number) => (
        <Progress
          percent={v} size="small"
          strokeColor={v >= 90 ? '#0f9d58' : v >= 60 ? '#f59e0b' : '#e5484d'}
        />
      ) },
    { title: '待办', key: 'counts', width: 150, render: (_: any, r: any) => (
      <Space size={4}>
        {r.counts.overdue > 0 && <Tag color="red">逾期 {r.counts.overdue}</Tag>}
        {r.counts.missing > 0 && <Tag color="orange">未完成 {r.counts.missing}</Tag>}
        {r.counts.warning > 0 && <Tag color="gold">风险 {r.counts.warning}</Tag>}
        {r.counts.overdue + r.counts.missing + r.counts.warning === 0 && <Tag color="green">齐全</Tag>}
      </Space>
    )},
  ];

  return (
    <div>
      <Title level={4}>欢迎回来，{user.display_name || user.username}</Title>

      <Card
        style={{ marginTop: 16 }}
        title={
          <span>
            <CheckSquareOutlined style={{ color: '#2563eb' }} /> 我的待办
            {!!todoSummary?.total && (
              <Tag color="red" style={{ marginLeft: 8 }}>{todoSummary.total} 项</Tag>
            )}
            {!!todoSummary?.high && (
              <Tag color="volcano">紧急 {todoSummary.high}</Tag>
            )}
          </span>
        }
        extra={<Button type="link" onClick={() => navigate('/todos')}>查看全部</Button>}
      >
        <TodoList todos={todos.slice(0, 6)} />
      </Card>

      {can('alerts:board') && (
        <Card
          style={{ marginTop: 16 }}
          title={<span><DashboardOutlined style={{ color: '#2563eb' }} /> 项目看板 · 完整度预警</span>}
          extra={
            <Space size={4} wrap>
              <Tag color="red">逾期项 {boardSummary.overdue_items || 0}</Tag>
              <Tag color="orange">未完成项 {boardSummary.missing_items || 0}</Tag>
              <Tag color="blue">平均健康度 {boardSummary.average_health ?? 100}%</Tag>
            </Space>
          }
        >
          {board?.projects?.length ? (
            <Table
              columns={boardColumns}
              dataSource={board.projects}
              rowKey="project_id"
              size="small"
              pagination={board.projects.length > 10 ? { pageSize: 10 } : false}
              scroll={{ x: 900 }}
            />
          ) : <Empty description="暂无进行中的项目" />}
        </Card>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} sm={6}><Card><Statistic title="项目总数" value={s.total_projects || 0} prefix={<ProjectOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="进行中项目" value={s.active_projects || 0} valueStyle={{ color: '#1677ff' }} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="合同总数" value={s.total_contracts || 0} prefix={<FileTextOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="在途报销" value={s.pending_reimbursements || 0} prefix={<AccountBookOutlined />} valueStyle={{ color: '#faad14' }} /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12}><Card><Statistic title="合同总金额" value={s.total_revenue || 0} precision={2} prefix="¥" /></Card></Col>
        <Col xs={24} sm={12}><Card><Statistic title="库存总值" value={s.inventory_value || 0} precision={2} prefix="¥" suffix={<InboxOutlined />} /></Card></Col>
      </Row>

      {warnings.length > 0 && (
        <Card title={<span><WarningOutlined style={{ color: '#faad14' }} /> 库存预警</span>} style={{ marginTop: 16 }}>
          <List
            size="small"
            dataSource={warnings.slice(0, 5)}
            renderItem={(item: any) => (
              <List.Item>
                <span>{item.material_name} ({item.specification})</span>
                <Tag color={item.stock_status === 'out_of_stock' ? 'red' : 'orange'}>
                  库存: {item.stock_quantity} {item.unit}
                </Tag>
              </List.Item>
            )}
          />
        </Card>
      )}

      {overview?.projects?.length > 0 && (
        <Card title="项目盈亏概览" style={{ marginTop: 16 }}>
          <List
            size="small"
            dataSource={overview.projects.slice(0, 8)}
            renderItem={(p: any) => (
              <List.Item>
                <span>{p.project_name}</span>
                <div>
                  {p.over_budget && <Tag color="red">超预算</Tag>}
                  <Tag color={p.status === 'active' ? 'blue' : 'green'}>{p.status === 'active' ? '进行中' : '已完成'}</Tag>
                  <Text type="secondary" style={{ marginLeft: 8 }}>成本 {formatMoney(p.cost)}</Text>
                  <span style={{ marginLeft: 8 }}>利润率: {p.profit_rate}%</span>
                </div>
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  );
}
