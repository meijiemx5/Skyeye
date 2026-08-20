import { useEffect, useState } from 'react';
import { Table, Select, DatePicker, Space, Tag, Typography, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { auditLogApi } from '../api/client';

const { Title } = Typography;
const actionLabels: Record<string, { label: string; color: string }> = {
  login: { label: '登录', color: 'blue' },
  logout: { label: '退出', color: 'default' },
  create: { label: '新增', color: 'green' },
  update: { label: '更新', color: 'orange' },
  delete: { label: '删除', color: 'red' },
  audit: { label: '审核', color: 'cyan' },
  confirm_receipt: { label: '收款确认', color: 'geekblue' },
  create_document: { label: '创建单据', color: 'purple' },
  generate_voucher: { label: '生成凭证', color: 'lime' },
  pay: { label: '报销付款', color: 'green' },
  payment: { label: '合同付款', color: 'green' },
  stock_in: { label: '入库', color: 'green' },
  stock_out: { label: '出库', color: 'blue' },
  adjustment: { label: '盘点', color: 'orange' },
};
const resourceLabels: Record<string, string> = {
  user: '用户', contract: '合同', reimbursement: '报销',
  acceptance: '验收', inventory: '库存', project: '项目',
  reimburse_category: '报销类型', invoice_batch: '发票批次', invoice: '发票',
};

export default function AuditLogs() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<any>({});
  // 服务端分页：后端按 page/page_size 切片并返回 total，前端必须把这两个参数传上去，
  // 否则永远只拿到最新一页，分页器看起来"只有 1 页"。
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [total, setTotal] = useState(0);

  useEffect(() => { loadData(); }, [filters, page, pageSize]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await auditLogApi.list({ ...filters, page, page_size: pageSize });
      setData(res.data.data || []);
      setTotal(res.data.total || 0);
    } catch {} finally { setLoading(false); }
  };

  // 换筛选条件要回到第 1 页，否则会停在一个超出范围的页码上看到空列表
  const changeFilter = (patch: any) => {
    setPage(1);
    setFilters((p: any) => ({ ...p, ...patch }));
  };

  const columns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-' },
    { title: '用户', dataIndex: 'user_name', key: 'user_name', width: 100 },
    { title: '操作', dataIndex: 'action', key: 'action', width: 100,
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
        <Select allowClear placeholder="操作类型" style={{ width: 130 }}
          onChange={(v) => changeFilter({ action: v })}
          options={Object.entries(actionLabels).map(([k, v]) => ({ value: k, label: v.label }))} />
        <Select allowClear placeholder="资源类型" style={{ width: 130 }}
          onChange={(v) => changeFilter({ resource_type: v })}
          options={Object.entries(resourceLabels).map(([k, v]) => ({ value: k, label: v }))} />
        <DatePicker placeholder="选择日期" onChange={(_, ds) => changeFilter({ date: ds || undefined })} />
        <Button icon={<ReloadOutlined />} onClick={() => loadData()}>刷新</Button>
      </Space>
      <Table columns={columns} dataSource={data} rowKey="log_id" loading={loading} size="middle"
        scroll={{ x: 900 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          // 后端 page_size 上限 200，超过会被拒
          pageSizeOptions: ['20', '50', '100', '200'],
          showTotal: (t, [from, to]) => `第 ${from}-${to} 条 / 共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }} />
    </div>
  );
}
