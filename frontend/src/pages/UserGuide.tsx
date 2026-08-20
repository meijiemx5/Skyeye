import { Typography, Table, Card, Collapse, Tag, Divider } from 'antd';
import { CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;

const Yes = () => <CheckCircleFilled style={{ color: '#52c41a', fontSize: 16 }} />;
const No = () => <CloseCircleFilled style={{ color: '#ff4d4f', fontSize: 16 }} />;

const permissionData = [
  { key: '1', module: '用户管理', sub: '创建/编辑/删除用户', admin: true, finance: false, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '2', module: '用户管理', sub: '重置密码', admin: true, finance: false, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '3', module: '用户管理', sub: '修改自己密码', admin: true, finance: true, pm: true, procurement: true, construction: true, warehouse: true },
  { key: '4', module: '项目管理', sub: '创建/编辑项目', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '5', module: '项目管理', sub: '删除项目', admin: true, finance: false, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '6', module: '项目管理', sub: '查看项目列表/详情', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '6b', module: '项目管理', sub: '项目下拉选项（填单用）', admin: true, finance: true, pm: true, procurement: true, construction: true, warehouse: true },
  { key: '6c', module: '项目管理', sub: '填写项目预算/报价', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '7', module: '合同管理', sub: '创建甲方合同', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '8', module: '合同管理', sub: '创建供应商合同', admin: true, finance: false, pm: false, procurement: true, construction: false, warehouse: false },
  { key: '9', module: '合同管理', sub: '删除合同', admin: true, finance: false, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '10', module: '合同管理', sub: '查看合同（完整）', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '10a', module: '合同管理', sub: '合同下拉选项（付款/收款用）', admin: true, finance: true, pm: true, procurement: true, construction: false, warehouse: false },
  { key: '10b', module: '合同管理', sub: '合同付款登记', admin: true, finance: true, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '10c', module: '发票管理', sub: '查看发票批次/开票进度', admin: true, finance: true, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '10d', module: '发票管理', sub: '维护发票批次与单张发票', admin: true, finance: true, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '11', module: '报销管理', sub: '提交报销申请', admin: true, finance: true, pm: true, procurement: true, construction: true, warehouse: true },
  { key: '12', module: '报销管理', sub: '主管审核', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '12b', module: '报销管理', sub: '项目收款确认', admin: true, finance: true, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '12c', module: '报销管理', sub: '跳过项目收款（需填原因）', admin: true, finance: false, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '12d', module: '报销管理', sub: '创建报销单据', admin: true, finance: true, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '13', module: '报销管理', sub: '财务审核', admin: true, finance: true, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '13b', module: '报销管理', sub: '生成会计凭证', admin: true, finance: true, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '14', module: '报销管理', sub: '付款操作', admin: true, finance: true, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '15', module: '验收资料', sub: '创建/编辑验收记录', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '16', module: '验收资料', sub: '查看验收资料', admin: true, finance: false, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '17', module: '库存管理', sub: '创建物料', admin: true, finance: false, pm: false, procurement: true, construction: false, warehouse: true },
  { key: '18', module: '库存管理', sub: '入库/出库', admin: true, finance: false, pm: false, procurement: true, construction: false, warehouse: false },
  { key: '19', module: '库存管理', sub: '盘点调整', admin: true, finance: false, pm: false, procurement: false, construction: false, warehouse: true },
  { key: '20', module: '项目分析', sub: '查看总览分析', admin: true, finance: true, pm: true, procurement: false, construction: false, warehouse: false },
  { key: '21', module: '项目分析', sub: '查看单项目分析', admin: true, finance: true, pm: true, procurement: true, construction: true, warehouse: true },
  { key: '22', module: '操作日志', sub: '查看日志', admin: true, finance: false, pm: false, procurement: false, construction: false, warehouse: false },
  { key: '23', module: '待办中心', sub: '查看我的待办', admin: true, finance: true, pm: true, procurement: true, construction: true, warehouse: true },
  { key: '24', module: '待办中心', sub: '查看项目完整度看板', admin: true, finance: true, pm: true, procurement: true, construction: true, warehouse: true },
];

const permColumns = [
  { title: '模块', dataIndex: 'module', key: 'module', width: 100,
    onCell: (_: any, index: number | undefined) => {
      if (index === undefined) return {};
      const data = permissionData;
      if (index === 0 || data[index].module !== data[index - 1].module) {
        let count = 1;
        for (let i = index + 1; i < data.length && data[i].module === data[index].module; i++) count++;
        return { rowSpan: count };
      }
      return { rowSpan: 0 };
    }
  },
  { title: '操作', dataIndex: 'sub', key: 'sub' },
  { title: '管理员', dataIndex: 'admin', key: 'admin', width: 80, align: 'center' as const, render: (v: boolean) => v ? <Yes /> : <No /> },
  { title: '财务', dataIndex: 'finance', key: 'finance', width: 80, align: 'center' as const, render: (v: boolean) => v ? <Yes /> : <No /> },
  { title: '项目负责人', dataIndex: 'pm', key: 'pm', width: 100, align: 'center' as const, render: (v: boolean) => v ? <Yes /> : <No /> },
  { title: '采购', dataIndex: 'procurement', key: 'procurement', width: 80, align: 'center' as const, render: (v: boolean) => v ? <Yes /> : <No /> },
  { title: '施工', dataIndex: 'construction', key: 'construction', width: 80, align: 'center' as const, render: (v: boolean) => v ? <Yes /> : <No /> },
  { title: '仓库', dataIndex: 'warehouse', key: 'warehouse', width: 80, align: 'center' as const, render: (v: boolean) => v ? <Yes /> : <No /> },
];

const roleGuides = [
  {
    key: 'admin',
    label: <span><Tag color="red">管理员</Tag> 使用指南</span>,
    children: (
      <div>
        <Paragraph>管理员拥有系统最高权限，负责系统配置和用户管理。</Paragraph>
        <Title level={5}>日常操作</Title>
        <Paragraph>
          <ul>
            <li><b>用户管理</b>：左侧菜单 → 用户管理，可新建用户、分配角色、启用/禁用账号、重置密码</li>
            <li><b>项目管理</b>：创建新项目，分配项目负责人，跟踪项目状态</li>
            <li><b>合同管理</b>：查看和管理所有类型合同（甲方、供应商、施工）</li>
            <li><b>报销审批</b>：可代替任何角色进行审核和付款操作</li>
            <li><b>数据分析</b>：查看总览分析和单项目分析，监控公司运营状况</li>
            <li><b>操作日志</b>：查看所有用户的操作记录，支持按类型和日期筛选</li>
          </ul>
        </Paragraph>
        <Title level={5}>注意事项</Title>
        <Paragraph>
          <ul>
            <li>首次部署后请立即修改默认密码（点击右上角用户名 → 修改密码）</li>
            <li>为其他用户创建账号时请选择正确的角色</li>
            <li>删除操作不可恢复，请谨慎执行</li>
          </ul>
        </Paragraph>
      </div>
    ),
  },
  {
    key: 'finance',
    label: <span><Tag color="blue">财务人员</Tag> 使用指南</span>,
    children: (
      <div>
        <Paragraph>财务人员负责报销链路的资金环节、合同付款与开票管理。</Paragraph>
        <Title level={5}>日常操作</Title>
        <Paragraph>
          <ul>
            <li><b>我的待办</b>：每天第一件事打开「我的待办」，里面就是当前该你处理的事</li>
            <li><b>项目收款确认</b>：报销主管审完后，选择本次收款对应的甲方合同、填写收款金额与日期</li>
            <li><b>创建单据</b>：收款确认后点击"创建单据"，单据号留空会自动生成（BX-日期-编号）</li>
            <li><b>财务审核</b>：单据创建后进行财务审核</li>
            <li><b>生成凭证</b>：财务审核通过后点击"生成凭证"，凭证号留空自动生成（PZ-日期-编号），可挂凭证附件</li>
            <li><b>付款操作</b>：凭证生成后才能付款，填写付款金额、方式和时间</li>
            <li><b>合同付款</b>：在合同列表「已付款」列点击💲付款按钮，登记每笔付款（金额、方式、日期）</li>
            <li><b>发票管理</b>：合同列表「发票」列进入，按批次开票，同一批次内材料/施工/技术服务分开录入</li>
            <li><b>数据分析</b>：查看项目收入、成本和利润分析</li>
          </ul>
        </Paragraph>
        <Title level={5}>报销完整链路</Title>
        <Paragraph>
          提交报销 → 主管审核 → <Text strong>项目收款（您）</Text> → <Text strong>创建单据（您）</Text> →{' '}
          <Text strong>财务审核（您）</Text> → <Text strong>凭证生成（您）</Text> → <Text strong>付款（您）</Text> → 完成
        </Paragraph>
        <Paragraph type="secondary">
          项目收款是硬门禁：没确认项目已收到甲方款项，就不能创建单据。确实需要先垫付的，
          由管理员在收款确认弹窗里勾选"强制跳过"并填写原因，原因会记入审批日志。
        </Paragraph>
        <Title level={5}>报销编辑规则</Title>
        <Paragraph>
          <ul>
            <li><b>待主管审核/已驳回</b>：申请人本人和管理员可编辑（修改金额、事由、凭证等）</li>
            <li><b>进入链路后（主管已审及之后）</b>：不可编辑，只能查看</li>
            <li>被驳回后可修改并重新提交，状态自动回到"待主管审核"</li>
            <li>点击列表里的状态标签可以看到完整链路进度与每一步的操作人</li>
          </ul>
        </Paragraph>
        <Title level={5}>合同可见范围</Title>
        <Paragraph type="secondary">
          按公司要求，完整合同信息（条款、附件等）只对管理员和项目负责人开放。
          你在付款和收款确认时看到的是精简的合同选项（合同号、名称、金额、已付），足够完成付款登记。
        </Paragraph>
      </div>
    ),
  },
  {
    key: 'project_manager',
    label: <span><Tag color="green">项目负责人</Tag> 使用指南</span>,
    children: (
      <div>
        <Paragraph>项目负责人负责管理甲方合同、项目验收和报销主管审核，并保证自己项目的资料齐全。</Paragraph>
        <Title level={5}>日常操作</Title>
        <Paragraph>
          <ul>
            <li><b>我的待办</b>：每天第一件事打开「我的待办」，里面列出你项目上还缺哪些东西</li>
            <li><b>项目管理</b>：创建和编辑自己负责的项目，填写<b>项目预算与报价</b>，更新项目状态</li>
            <li><b>完整度预警</b>：项目详情 →「完整度预警」页签，逐项看预算、报价、甲方合同、采购合同、工费、验收资料、发票、报销八项的状态与期限</li>
            <li><b>甲方合同</b>：创建和管理甲方合同（与客户签订的合同）</li>
            <li><b>报销审核</b>：审核团队成员的报销申请（第一级审核）</li>
            <li><b>验收管理</b>：创建验收记录，上传验收资料，更新验收状态</li>
            <li><b>项目分析</b>：查看自己项目的成本、利润与开票进度</li>
          </ul>
        </Paragraph>
        <Title level={5}>说明</Title>
        <Paragraph type="secondary">
          你只能看到自己负责的项目及其合同。项目预算填写后，成本一旦超过预算或用到 90% 以上，
          项目看板与待办里会给出预警。
        </Paragraph>
      </div>
    ),
  },
  {
    key: 'procurement',
    label: <span><Tag color="orange">采购专员</Tag> 使用指南</span>,
    children: (
      <div>
        <Paragraph>采购专员负责供应商合同管理和库存入出库操作。</Paragraph>
        <Title level={5}>日常操作</Title>
        <Paragraph>
          <ul>
            <li><b>供应商合同</b>：创建和管理供应商采购合同</li>
            <li><b>物料管理</b>：左侧菜单 → 库存管理，新增物料信息</li>
            <li><b>入库操作</b>：采购物料到库后，点击"入库"按钮录入入库信息</li>
            <li><b>出库操作</b>：项目领用物料时，点击"出库"按钮录入出库信息</li>
            <li><b>库存查看</b>：查看库存预警，及时补充低库存物料</li>
          </ul>
        </Paragraph>
      </div>
    ),
  },
  {
    key: 'construction',
    label: <span><Tag color="cyan">施工人员</Tag> 使用指南</span>,
    children: (
      <div>
        <Paragraph>施工人员主要用系统提交报销和跟进报销进度。</Paragraph>
        <Title level={5}>日常操作</Title>
        <Paragraph>
          <ul>
            <li><b>我的待办</b>：报销被驳回时会出现在这里，提醒你改完重新提交</li>
            <li><b>提交报销</b>：左侧菜单 → 报销管理 → 提交报销，填写报销信息并提交</li>
            <li><b>查看报销进度</b>：点击报销列表里的状态标签，能看到完整链路走到哪一步了</li>
            <li><b>修改报销</b>：被驳回的报销可修改后重新提交</li>
          </ul>
        </Paragraph>
        <Title level={5}>报销提交流程</Title>
        <Paragraph>
          填写报销类型、金额、事由、日期 → 提交 → 主管审核 → 项目收款确认 → 创建单据 → 财务审核 → 凭证生成 → 付款
        </Paragraph>
        <Paragraph type="secondary">
          报销类型只能从系统已有的费用大类里选，需要新增大类请联系管理员。
          合同信息按公司要求已收归管理员与项目负责人查看。
        </Paragraph>
      </div>
    ),
  },
  {
    key: 'warehouse',
    label: <span><Tag color="purple">仓库管理员</Tag> 使用指南</span>,
    children: (
      <div>
        <Paragraph>仓库管理员负责库存盘点和物料信息维护。</Paragraph>
        <Title level={5}>日常操作</Title>
        <Paragraph>
          <ul>
            <li><b>物料管理</b>：新增和编辑物料基本信息（名称、规格、仓库位置等）</li>
            <li><b>库存盘点</b>：左侧菜单 → 库存管理 → 点击"盘点"按钮</li>
            <li><b>盘点操作</b>：输入物料ID、实际盘点数量和调整原因，系统自动计算差异并更新库存</li>
            <li><b>库存预警</b>：关注库存预警提醒，及时通知采购专员补货</li>
          </ul>
        </Paragraph>
      </div>
    ),
  },
];

export default function UserGuide() {
  return (
    <div>
      <Title level={4}>📖 用户指南</Title>
      <Paragraph type="secondary">本指南包含各角色的权限说明和操作指引，帮助您快速上手系统。</Paragraph>

      <Divider />
      <Title level={5}>一、权限矩阵</Title>
      <Paragraph type="secondary">不同角色拥有不同的操作权限，<CheckCircleFilled style={{ color: '#52c41a' }} /> 表示有权限，<CloseCircleFilled style={{ color: '#ff4d4f' }} /> 表示无权限。</Paragraph>
      <Table columns={permColumns} dataSource={permissionData} rowKey="key" size="small"
        pagination={false} bordered scroll={{ x: 800 }} style={{ marginBottom: 24 }} />

      <Divider />
      <Title level={5}>二、各角色操作指南</Title>
      <Paragraph type="secondary">请展开您对应角色的指南查看详细操作说明。</Paragraph>
      <Collapse items={roleGuides} defaultActiveKey={[]} style={{ marginTop: 16 }} />

      <Divider />
      <Title level={5}>三、待办中心与项目完整度预警</Title>
      <Card size="small">
        <Paragraph>
          <b>每天上班第一件事：打开「我的待办」，把里面的事清空。</b>
          左侧菜单「我的待办」旁边的红点就是当前待办数量。
        </Paragraph>
        <Paragraph>
          <b>待办来自哪里：</b>
          <ul>
            <li><b>项目未完成项</b>：你负责的项目缺预算、报价、合同、验收资料、发票等（按角色分派：采购合同派给采购，发票派给财务）</li>
            <li><b>报销待处理</b>：链路上正卡在你这一环的报销；停留超过 7 天会升级为紧急</li>
            <li><b>报销被驳回</b>：提醒申请人改完重新提交</li>
            <li><b>验收整改</b>：验收结果为需整改的项目</li>
            <li><b>库存预警</b>：缺货或低于最低库存的物料（派给采购、仓库）</li>
          </ul>
        </Paragraph>
        <Paragraph>
          <b>项目完整度：</b>工作台的「项目看板」把每个项目的八项组成部分画成八个圆点 ——
          <Text style={{ color: '#0f9d58' }}>绿</Text>=已完成、
          <Text style={{ color: '#f59e0b' }}>黄</Text>=未完成或有风险、
          <Text style={{ color: '#e5484d' }}>红</Text>=已逾期、灰=本项目不适用。鼠标停在圆点上看具体说明。
        </Paragraph>
        <Table size="small" pagination={false} bordered style={{ marginTop: 12 }}
          dataSource={[
            { key: '1', item: '预算', rule: '项目填了预算金额', due: '开工后 7 天内', owner: '项目负责人' },
            { key: '2', item: '报价', rule: '项目填了报价金额', due: '开工后 7 天内', owner: '项目负责人' },
            { key: '3', item: '甲方合同', rule: '存在已签订的甲方合同', due: '开工后 14 天内', owner: '项目负责人' },
            { key: '4', item: '采购合同', rule: '有材料成本时需有供应商合同', due: '开工后 30 天内', owner: '采购专员' },
            { key: '5', item: '工费', rule: '存在施工合同', due: '开工后 30 天内', owner: '项目负责人' },
            { key: '6', item: '验收资料', rule: '至少上传 1 份验收资料', due: '计划完工日', owner: '项目负责人' },
            { key: '7', item: '发票', rule: '已开票金额达到甲方合同金额', due: '完工后 30 天内', owner: '财务' },
            { key: '8', item: '报销', rule: '没有停留超 7 天的在途报销', due: '—', owner: '当前处理人' },
          ]}
          columns={[
            { title: '组成部分', dataIndex: 'item', key: 'item', width: 100 },
            { title: '算完成的条件', dataIndex: 'rule', key: 'rule' },
            { title: '期限', dataIndex: 'due', key: 'due', width: 130 },
            { title: '催谁', dataIndex: 'owner', key: 'owner', width: 100 },
          ]}
        />
      </Card>

      <Divider />
      <Title level={5}>四、发票分批次开具</Title>
      <Card size="small">
        <Paragraph>
          发票不是一次开完的，而且一次开票可能是多张。系统按<b>「批次 + 单张发票」</b>两层管理：
          一个批次代表一次开票行为，批次下面挂这次开的每一张发票，扫描件传在单张发票上。
        </Paragraph>
        <Paragraph>
          <b>举个例子：</b>100 万的项目，甲方先要 40 万预付款发票，其中材料 30 万（税率 13%）、
          工费 10 万（税率 9%）——这是<b>一个批次、两张发票</b>；剩下 60 万过一段时间再开，是<b>另一个批次</b>。
        </Paragraph>
        <Paragraph>
          <b>操作路径：</b>
          <ol>
            <li>合同管理 → 找到甲方合同 → 点「发票」列的按钮</li>
            <li>点「新建批次」，填批次说明（如"预付款40万"）、款项阶段、开票日期</li>
            <li>在批次那一行点「加发票」，选类别（系统按类别预填税率：材料 13%、施工 9%、技术服务 6%）</li>
            <li>填含税金额，系统自动算不含税与税额；发票上印的数字不一致时可手工覆盖</li>
            <li>上传发票扫描件，保存。批次合计与开票进度自动更新</li>
          </ol>
        </Paragraph>
        <Paragraph type="secondary">
          小规模纳税人、简易计税的 3% / 1% / 免税也能选。项目详情 →「发票开票」页签可以看该项目整体的开票进度；
          未开票余额过了完工期还没清零，发票项会在项目看板亮红灯。
        </Paragraph>
      </Card>

      <Divider />
      <Title level={5}>五、附件上传</Title>
      <Card size="small">
        <Paragraph>
          系统支持在以下模块上传附件，附件直传S3存储，支持下载和删除：
        </Paragraph>
        <Table size="small" pagination={false} bordered style={{ marginBottom: 16 }}
          dataSource={[
            { key: '1', module: '合同管理', timing: '编辑合同时', types: '合同PDF、发票、到款截图', where: '编辑弹窗底部「附件」区域' },
            { key: '2', module: '报销管理', timing: '提交报销时', types: '发票、收据（最多5个）', where: '提交弹窗底部「报销凭证」区域' },
            { key: '3', module: '验收资料', timing: '编辑验收时', types: '验收报告、施工图纸、调试报告', where: '编辑弹窗底部（分为基础资料和工程资料）' },
            { key: '4', module: '项目管理', timing: '编辑项目时', types: '预算表、报价单', where: '编辑弹窗底部「预算表附件」「报价单附件」区域' },
            { key: '5', module: '发票管理', timing: '录入单张发票时', types: '发票扫描件、PDF（每张最多5个）', where: '发票弹窗底部「发票扫描件」区域' },
            { key: '6', module: '报销管理', timing: '生成凭证时', types: '会计凭证（最多5个）', where: '生成凭证弹窗「凭证附件」区域' },
          ]}
          columns={[
            { title: '模块', dataIndex: 'module', key: 'module', width: 100 },
            { title: '上传时机', dataIndex: 'timing', key: 'timing', width: 120 },
            { title: '附件类型', dataIndex: 'types', key: 'types' },
            { title: '上传位置', dataIndex: 'where', key: 'where' },
          ]}
        />
        <Paragraph>
          <b>操作步骤：</b>
          <ol>
            <li>进入对应模块，点击记录的「编辑」按钮（或新建）</li>
            <li>在弹窗中向下滚动找到「附件」或「报销凭证」区域</li>
            <li>点击「上传附件」按钮，选择文件</li>
            <li>上传成功后文件会显示在列表中，可下载或删除</li>
            <li>点击「确定」保存记录（附件信息随记录一起保存）</li>
          </ol>
        </Paragraph>
        <Paragraph>
          <b>查看与下载：</b>
          <ul>
            <li>列表页「附件」或「凭证」列显示已上传文件数量</li>
            <li>点击「编辑」进入详情查看附件列表</li>
            <li>可预览的文件（PDF、图片、TXT）显示「查看」按钮，点击在新标签页中在线预览</li>
            <li>所有文件都有「下载」按钮，点击直接下载到本地</li>
            <li>编辑模式下可点击「删除」移除附件</li>
          </ul>
        </Paragraph>
      </Card>

      <Divider />
      <Title level={5}>六、通用操作</Title>
      <Card size="small">
        <Paragraph>
          <ul>
            <li><b>修改密码</b>：点击右上角用户名 → 修改密码</li>
            <li><b>退出登录</b>：点击右上角用户名 → 退出登录</li>
            <li><b>侧边栏折叠</b>：点击顶部左侧的折叠按钮可收起/展开侧边栏</li>
            <li><b>数据筛选</b>：大部分列表页都支持按状态、类型等条件筛选</li>
          </ul>
        </Paragraph>
      </Card>
    </div>
  );
}
