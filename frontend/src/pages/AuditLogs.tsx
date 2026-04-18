import { useEffect, useState } from 'react';
import { Table, Select, DatePicker, Space, Tag, Typography } from 'antd';
import { auditLogApi } from '../api/client';

const { Title } = Typography;
const actionLabels: Record<string, { label: string; color: string }> = {
  login: { label: '登录', color: 'blue' },
  logout: { label: '退出', color: 'default' },
  create: { label: '新增', color: 'green' },
  update: { label: '更新', color: 'orange' },
  delete: { label: '删除', color: 'red' },
};
const resourceLabels: Record<string, string> = {
  user: '用户', contract: '合同', reimbursement: '报销',
  acceptance: '验收', inventory: '库存', project: '项目',
};

export default function AuditLogs() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<any>({});

  useEffect(() => { loadData(); }, [filters]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await auditLogApi.list(filters);
      setData(res.data.data || []);
    } catch {} finally { setLoading(false); }
  };

  const columns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-' },
    { title: '用户', dataIndex: 'user_name', key: 'user_name', width: 100 },
    { title: '操作', dataIndex: 'action', key: 'action', width: 80,
      render: (a: string) => { const s = actionLabels[a]; return s ? <Tag color={s.color}>{s.label}</Tag> : a; } },
    { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type', width: 100,
      render: (t: string) => resourceLabels[t] || t },
    { title: '资源ID', dataIndex: 'resource_id', key: 'resource_id', width: 120 },
    { title: '详情', dataIndex: 'detail', key: 'detail', ellipsis: true },
    { title: 'IP地址', dataIndex: 'ip_address', key: 'ip_address', width: 130 },
  ];

  return (
    <div>
      <Title level={4}>操作日志</Title>
      <Space style={{ marginBottom: 16 }} wrap>
        <Select allowClear placeholder="操作类型" style={{ width: 120 }}
          onChange={(v) => setFilters((p: any) => ({ ...p, action: v }))}
          options={Object.entries(actionLabels).map(([k, v]) => ({ value: k, label: v.label }))} />
        <Select allowClear placeholder="资源类型" style={{ width: 120 }}
          onChange={(v) => setFilters((p: any) => ({ ...p, resource_type: v }))}
          options={Object.entries(resourceLabels).map(([k, v]) => ({ value: k, label: v }))} />
        <DatePicker placeholder="选择日期" onChange={(_, ds) => setFilters((p: any) => ({ ...p, date: ds || undefined }))} />
      </Space>
      <Table columns={columns} dataSource={data} rowKey="log_id" loading={loading} size="middle"
        scroll={{ x: 900 }} pagination={{ pageSize: 50 }} />
    </div>
  );
}
