import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, List, Tag, Spin } from 'antd';
import { ProjectOutlined, FileTextOutlined, AccountBookOutlined, InboxOutlined, WarningOutlined } from '@ant-design/icons';
import { analysisApi, inventoryApi } from '../api/client';

const { Title } = Typography;

export default function Dashboard() {
  const [overview, setOverview] = useState<any>(null);
  const [warnings, setWarnings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [overviewRes, warningRes] = await Promise.allSettled([
        analysisApi.overview(),
        inventoryApi.getWarnings(),
      ]);
      if (overviewRes.status === 'fulfilled') setOverview(overviewRes.value.data.data);
      if (warningRes.status === 'fulfilled') setWarnings(warningRes.value.data.data || []);
    } catch {} finally { setLoading(false); }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const s = overview?.summary || {};

  return (
    <div>
      <Title level={4}>欢迎回来，{user.display_name || user.username}</Title>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} sm={6}><Card><Statistic title="项目总数" value={s.total_projects || 0} prefix={<ProjectOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="进行中项目" value={s.active_projects || 0} valueStyle={{ color: '#1677ff' }} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="合同总数" value={s.total_contracts || 0} prefix={<FileTextOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="待审报销" value={s.pending_reimbursements || 0} prefix={<AccountBookOutlined />} valueStyle={{ color: '#faad14' }} /></Card></Col>
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
        <Card title="项目概览" style={{ marginTop: 16 }}>
          <List
            size="small"
            dataSource={overview.projects.slice(0, 8)}
            renderItem={(p: any) => (
              <List.Item>
                <span>{p.project_name}</span>
                <div>
                  <Tag color={p.status === 'active' ? 'blue' : 'green'}>{p.status === 'active' ? '进行中' : '已完成'}</Tag>
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
