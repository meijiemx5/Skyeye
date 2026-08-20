import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, Select, Space, Button, Spin, message } from 'antd';
import { ReloadOutlined, CheckSquareOutlined } from '@ant-design/icons';
import { todoApi } from '../api/client';
import TodoList, { TodoItem } from '../components/TodoList';
import { SEVERITY, TODO_TYPE_LABELS } from '../utils/constants';

const { Title, Text } = Typography;

export default function Todos() {
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<{ todo_type?: string; severity?: string }>({});

  const loadData = async (overrides?: typeof filters) => {
    setLoading(true);
    try {
      const params: any = { ...(overrides ?? filters) };
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k]; });
      const res = await todoApi.list(params);
      setTodos(res.data.data?.todos || []);
      setSummary(res.data.data?.summary);
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载待办失败');
    } finally {
      setLoading(false);
    }
  };

  // 首次加载与筛选变化都走这里
  useEffect(() => { loadData(); }, [filters.todo_type, filters.severity]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}><CheckSquareOutlined /> 我的待办</Title>
        <Button icon={<ReloadOutlined />} onClick={() => loadData()}>刷新</Button>
      </div>
      <Text type="secondary">每天上班第一件事：把这里清空。项目缺件、报销在途、验收整改、库存告警都会汇总到这里。</Text>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="待办总数" value={summary?.total || 0} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="紧急" value={summary?.high || 0} valueStyle={{ color: '#e5484d' }} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="待处理" value={summary?.medium || 0} valueStyle={{ color: '#f59e0b' }} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="提示" value={summary?.low || 0} valueStyle={{ color: '#2563eb' }} /></Card></Col>
      </Row>

      <Card style={{ marginTop: 16 }}>
        <Space wrap style={{ marginBottom: 12 }}>
          <Select
            allowClear placeholder="按类型筛选" style={{ width: 180 }}
            value={filters.todo_type}
            options={Object.entries(summary?.by_type || {}).map(([k, v]) => ({
              value: k, label: `${TODO_TYPE_LABELS[k] || k} (${v})`,
            }))}
            onChange={(v) => setFilters({ ...filters, todo_type: v })}
          />
          <Select
            allowClear placeholder="按紧急程度筛选" style={{ width: 160 }}
            value={filters.severity}
            options={Object.entries(SEVERITY).map(([k, v]) => ({ value: k, label: v.label }))}
            onChange={(v) => setFilters({ ...filters, severity: v })}
          />
        </Space>
        {loading ? <Spin style={{ display: 'block', margin: '40px auto' }} /> : <TodoList todos={todos} />}
      </Card>
    </div>
  );
}
