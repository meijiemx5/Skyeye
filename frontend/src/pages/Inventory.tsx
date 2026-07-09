import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, InputNumber, DatePicker, Space, Tag, message, Typography, Popconfirm, Tabs, Card, Row, Col, Statistic } from 'antd';
import { PlusOutlined, ImportOutlined, ExportOutlined, ToolOutlined } from '@ant-design/icons';
import { inventoryApi, projectApi, contractApi } from '../api/client';

const { Title } = Typography;
const categoryMap: Record<string, string> = { equipment: '弱电设备', cable: '线缆', accessory: '配件', tool: '工具', other: '其他' };
const statusColors: Record<string, string> = { normal: 'green', warning: 'orange', out_of_stock: 'red' };
const statusLabels: Record<string, string> = { normal: '正常', warning: '库存预警', out_of_stock: '缺货' };

export default function Inventory() {
  const [materials, setMaterials] = useState<any[]>([]);
  const [records, setRecords] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [materialModal, setMaterialModal] = useState(false);
  const [stockModal, setStockModal] = useState<string>('');
  const [editing, setEditing] = useState<any>(null);
  const [form] = Form.useForm();
  const [stockForm] = Form.useForm();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const canCreateMaterial = ['admin', 'procurement', 'warehouse'].includes(user.role);
  const canStockInOut = ['admin', 'procurement'].includes(user.role);
  const canAdjust = ['admin', 'warehouse'].includes(user.role);
  const canDelete = user.role === 'admin';

  const [projects, setProjects] = useState<any[]>([]);
  const [projectContracts, setProjectContracts] = useState<any[]>([]);
  const [recordFilters, setRecordFilters] = useState<{ record_type?: string; project_id?: string }>({});

  useEffect(() => { loadAll(); projectApi.list().then(r => setProjects(r.data.data || [])).catch(() => {}); }, []);

  const loadProjectContracts = async (project_id?: string) => {
    if (!project_id) { setProjectContracts([]); return; }
    try {
      const res = await contractApi.list({ project_id });
      setProjectContracts(res.data.data || []);
    } catch { setProjectContracts([]); }
  };

  const loadRecords = async (overrides?: { record_type?: string; project_id?: string }) => {
    const params: any = { ...(overrides ?? recordFilters) };
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k]; });
    try { const res = await inventoryApi.listRecords(params); setRecords(res.data.data || []); } catch {}
  };

  const loadAll = async () => {
    setLoading(true);
    try {
      const [matRes, recRes, statsRes] = await Promise.allSettled([inventoryApi.listMaterials(), inventoryApi.listRecords(), inventoryApi.getStatistics()]);
      if (matRes.status === 'fulfilled') setMaterials(matRes.value.data.data || []);
      if (recRes.status === 'fulfilled') setRecords(recRes.value.data.data || []);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data.data);
    } catch {} finally { setLoading(false); }
  };

  const handleMaterialSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) { await inventoryApi.updateMaterial(editing.material_id, values); message.success('更新成功'); }
      else { await inventoryApi.createMaterial(values); message.success('创建成功'); }
      setMaterialModal(false); form.resetFields(); setEditing(null); loadAll();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const handleStockSubmit = async () => {
    const values = await stockForm.validateFields();
    if (values.record_date) values.record_date = values.record_date.format('YYYY-MM-DD');
    try {
      if (stockModal === 'in') await inventoryApi.stockIn(values);
      else if (stockModal === 'out') await inventoryApi.stockOut(values);
      else await inventoryApi.adjustment(values);
      message.success('操作成功'); setStockModal(''); stockForm.resetFields(); loadAll();
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败'); }
  };

  const matColumns = [
    { title: '名称', dataIndex: 'material_name', key: 'material_name' },
    { title: '分类', dataIndex: 'category', key: 'category', render: (c: string) => categoryMap[c] || c },
    { title: '规格', dataIndex: 'specification', key: 'specification' },
    { title: '品牌', dataIndex: 'brand', key: 'brand' },
    { title: '单位', dataIndex: 'unit', key: 'unit' },
    { title: '单价', dataIndex: 'unit_price', key: 'unit_price', render: (v: number) => v ? `¥${v}` : '-' },
    { title: '库存', dataIndex: 'stock_quantity', key: 'stock_quantity' },
    { title: '状态', dataIndex: 'stock_status', key: 'stock_status', render: (s: string) => <Tag color={statusColors[s]}>{statusLabels[s] || s}</Tag> },
    { title: '位置', dataIndex: 'warehouse_location', key: 'warehouse_location' },
    ...(canCreateMaterial || canDelete ? [{ title: '操作', key: 'action', width: 120, render: (_: any, r: any) => (
      <Space>
        {canCreateMaterial && <Button size="small" onClick={() => { setEditing(r); form.setFieldsValue(r); setMaterialModal(true); }}>编辑</Button>}
        {canDelete && <Popconfirm title="确定删除?" onConfirm={async () => { await inventoryApi.deleteMaterial(r.material_id); message.success('已删除'); loadAll(); }}><Button size="small" danger>删除</Button></Popconfirm>}
      </Space>
    )}] : []),
  ];

  const recColumns = [
    { title: '物料', dataIndex: 'material_name', key: 'material_name' },
    { title: '类型', dataIndex: 'record_type', key: 'record_type', render: (t: string) => t === 'in' ? <Tag color="green">入库</Tag> : t === 'out' ? <Tag color="blue">出库</Tag> : <Tag color="orange">盘点</Tag> },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    { title: '供应商/领用人', key: 'party', render: (_: any, r: any) => r.supplier_name || r.requester_name || '-' },
    { title: '项目', dataIndex: 'project_name', key: 'project_name' },
    { title: '合同', dataIndex: 'contract_no', key: 'contract_no', render: (v: string) => v || '-' },
    { title: '日期', dataIndex: 'record_date', key: 'record_date' },
  ];

  return (
    <div>
      <Title level={4}>库存管理</Title>
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}><Card size="small"><Statistic title="物料总数" value={stats.total_materials} /></Card></Col>
          <Col span={5}><Card size="small"><Statistic title="库存总值" value={stats.total_value} prefix="¥" precision={2} /></Card></Col>
          <Col span={5}><Card size="small"><Statistic title="入库总量" value={stats.total_in} /></Card></Col>
          <Col span={5}><Card size="small"><Statistic title="出库总量" value={stats.total_out} /></Card></Col>
          <Col span={5}><Card size="small"><Statistic title="预警数" value={(stats.warning_count || 0) + (stats.out_of_stock_count || 0)} valueStyle={{ color: '#cf1322' }} /></Card></Col>
        </Row>
      )}

      <Tabs items={[
        { key: 'materials', label: '物料列表', children: (
          <>
            <Space style={{ marginBottom: 16 }}>
              {canCreateMaterial && <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setMaterialModal(true); }}>新增物料</Button>}
              {canStockInOut && <Button icon={<ImportOutlined />} onClick={() => { stockForm.resetFields(); setStockModal('in'); }}>入库</Button>}
              {canStockInOut && <Button icon={<ExportOutlined />} onClick={() => { stockForm.resetFields(); setStockModal('out'); }}>出库</Button>}
              {canAdjust && <Button icon={<ToolOutlined />} onClick={() => { stockForm.resetFields(); setStockModal('adjust'); }}>盘点</Button>}
            </Space>
            <Table columns={matColumns} dataSource={materials} rowKey="material_id" loading={loading} size="middle" scroll={{ x: 1100 }} />
          </>
        )},
        { key: 'records', label: '出入库记录', children: (
          <>
            <Space style={{ marginBottom: 16 }}>
              <Select allowClear placeholder="按类型筛选" style={{ width: 140 }}
                options={[{ value: 'in', label: '入库' }, { value: 'out', label: '出库' }, { value: 'adjustment', label: '盘点' }]}
                onChange={(v) => { const f = { ...recordFilters, record_type: v }; setRecordFilters(f); loadRecords(f); }}
              />
              <Select allowClear showSearch optionFilterProp="label" placeholder="按项目筛选" style={{ width: 200 }}
                options={projects.map(p => ({ value: p.project_id, label: p.project_name }))}
                onChange={(v) => { const f = { ...recordFilters, project_id: v }; setRecordFilters(f); loadRecords(f); }}
              />
            </Space>
            <Table columns={recColumns} dataSource={records} rowKey="record_id" loading={loading} size="middle" />
          </>
        )},
      ]} />

      <Modal title={editing ? '编辑物料' : '新增物料'} open={materialModal} onOk={handleMaterialSubmit} onCancel={() => setMaterialModal(false)} width={600}>
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}><Form.Item name="material_name" label="物料名称" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="category" label="分类" rules={[{ required: true }]}><Select options={Object.entries(categoryMap).map(([k, v]) => ({ value: k, label: v }))} /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="specification" label="规格型号"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="brand" label="品牌"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="unit" label="单位" rules={[{ required: true }]}><Input placeholder="个/米/套" /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="unit_price" label="单价"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="min_stock_threshold" label="最低库存"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="warehouse_location" label="仓库位置"><Input /></Form.Item></Col>
          </Row>
        </Form>
      </Modal>

      <Modal title={stockModal === 'in' ? '入库' : stockModal === 'out' ? '出库' : '盘点调整'} open={!!stockModal} onOk={handleStockSubmit} onCancel={() => setStockModal('')}>
        <Form form={stockForm} layout="vertical">
          <Form.Item name="material_id" label="选择物料" rules={[{ required: true, message: '请选择物料' }]}>
            <Select placeholder="选择物料" showSearch optionFilterProp="label"
              options={materials.map(m => ({
                value: m.material_id,
                label: `${m.material_name}${m.specification ? ' - ' + m.specification : ''}${m.unit_price ? ' - ¥' + m.unit_price : ''} (库存:${m.stock_quantity || 0})`,
              }))}
            />
          </Form.Item>
          {stockModal !== 'adjust' && <Form.Item name="quantity" label="数量" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item>}
          {stockModal === 'adjust' && <Form.Item name="actual_quantity" label="实际数量" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item>}
          {stockModal === 'in' && (
            <>
              <Form.Item name="project_id" label="关联项目" tooltip="选择后可关联到该项目下的合同">
                <Select allowClear placeholder="选择关联项目（可选）" showSearch optionFilterProp="label"
                  options={projects.map(p => ({ value: p.project_id, label: p.project_name }))}
                  onChange={(v) => {
                    const p = projects.find(x => x.project_id === v);
                    stockForm.setFieldValue('project_name', p?.project_name);
                    stockForm.setFieldValue('contract_id', undefined);
                    stockForm.setFieldValue('contract_no', undefined);
                    loadProjectContracts(v);
                  }}
                />
              </Form.Item>
              <Form.Item name="project_name" hidden><Input /></Form.Item>
              <Form.Item name="contract_id" label="关联合同" tooltip="先选项目后再选合同">
                <Select allowClear placeholder={stockForm.getFieldValue('project_id') ? '选择关联合同（可选）' : '请先选择项目'}
                  showSearch optionFilterProp="label"
                  disabled={!stockForm.getFieldValue('project_id')}
                  options={projectContracts.map(c => ({ value: c.contract_id, label: `${c.contract_no || ''} - ${c.contract_name || ''}` }))}
                  onChange={(v) => {
                    const c = projectContracts.find(x => x.contract_id === v);
                    stockForm.setFieldValue('contract_no', c?.contract_no);
                  }}
                />
              </Form.Item>
              <Form.Item name="contract_no" hidden><Input /></Form.Item>
              <Form.Item name="unit_price" label="入库单价（可选，覆盖物料单价）"><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item name="supplier_name" label="供应商"><Input /></Form.Item>
            </>
          )}
          {stockModal === 'out' && (
            <>
              <Form.Item name="project_id" label="关联项目" rules={[{ required: true, message: '请选择关联项目' }]}>
                <Select placeholder="选择项目" showSearch optionFilterProp="label"
                  options={projects.map(p => ({ value: p.project_id, label: p.project_name }))}
                  onChange={(v) => { const p = projects.find(x => x.project_id === v); if (p) stockForm.setFieldValue('project_name', p.project_name); }}
                />
              </Form.Item>
              <Form.Item name="project_name" hidden><Input /></Form.Item>
              <Form.Item name="requester_name" label="领用人"><Input /></Form.Item>
            </>
          )}
          {stockModal === 'adjust' && <Form.Item name="adjustment_reason" label="调整原因"><Input.TextArea /></Form.Item>}
          <Form.Item name="record_date" label="日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
