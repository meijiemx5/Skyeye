import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, Dropdown, Avatar, theme, Modal, Form, Input, message, Tag, Drawer, Grid } from 'antd';
import {
  DashboardOutlined, ProjectOutlined, FileTextOutlined, AccountBookOutlined,
  CheckCircleOutlined, InboxOutlined, UserOutlined, TagsOutlined,
  LogoutOutlined, MenuFoldOutlined, MenuUnfoldOutlined, KeyOutlined, FileSearchOutlined, QuestionCircleOutlined,
} from '@ant-design/icons';
import { authApi } from '../api/client';

const { Header, Sider, Content } = Layout;

const roleLabels: Record<string, string> = {
  admin: '管理员', finance: '财务人员', project_manager: '项目负责人',
  procurement: '采购专员', construction: '施工人员', warehouse: '仓库管理员',
};

const { useBreakpoint } = Grid;

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pwdModalOpen, setPwdModalOpen] = useState(false);
  const [pwdForm] = Form.useForm();
  const navigate = useNavigate();
  const location = useLocation();
  const { token: { colorBgContainer } } = theme.useToken();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  const pageTitles: Record<string, string> = {
    '/': '工作台',
    '/projects': '项目管理',
    '/contracts': '合同管理',
    '/reimbursements': '报销管理',
    '/acceptances': '验收资料',
    '/inventory': '库存管理',
    '/reimburse-categories': '报销类型管理',
    '/users': '用户管理',
    '/audit-logs': '操作日志',
    '/guide': '用户指南',
  };

  useEffect(() => {
    const path = location.pathname.startsWith('/projects/') ? '/projects' : location.pathname;
    const pageTitle = pageTitles[path] || 'Skyeye';
    document.title = `${pageTitle} - Skyeye`;
  }, [location.pathname]);

  const handleChangePassword = async () => {
    const values = await pwdForm.validateFields();
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的新密码不一致');
      return;
    }
    try {
      await authApi.changePassword({ old_password: values.old_password, new_password: values.new_password });
      message.success('密码修改成功，请重新登录');
      setPwdModalOpen(false);
      pwdForm.resetFields();
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      navigate('/login');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '密码修改失败');
    }
  };

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '工作台' },
    { key: '/projects', icon: <ProjectOutlined />, label: '项目管理' },
    { key: '/contracts', icon: <FileTextOutlined />, label: '合同管理' },
    { key: '/reimbursements', icon: <AccountBookOutlined />, label: '报销管理' },
    { key: '/acceptances', icon: <CheckCircleOutlined />, label: '验收资料' },
    { key: '/inventory', icon: <InboxOutlined />, label: '库存管理' },
    ...(user.role === 'admin' ? [
      { key: '/reimburse-categories', icon: <TagsOutlined />, label: '报销类型管理' },
      { key: '/users', icon: <UserOutlined />, label: '用户管理' },
      { key: '/audit-logs', icon: <FileSearchOutlined />, label: '操作日志' },
    ] : []),
    { key: '/guide', icon: <QuestionCircleOutlined />, label: '用户指南' },
  ];

  const handleLogout = async () => {
    try { await authApi.logout(); } catch {}
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
    if (isMobile) setDrawerOpen(false);
  };

  const siderMenu = (
    <>
      <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: collapsed && !isMobile ? 16 : 20, fontWeight: 'bold', background: '#001529' }}>
        {collapsed && !isMobile ? '👁' : '👁 Skyeye'}
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[location.pathname.startsWith('/projects/') ? '/projects' : location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
      />
    </>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {isMobile ? (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={220}
          bodyStyle={{ padding: 0, background: '#001529' }}
          headerStyle={{ display: 'none' }}
        >
          {siderMenu}
        </Drawer>
      ) : (
        <Sider trigger={null} collapsible collapsed={collapsed} theme="dark">
          {siderMenu}
        </Sider>
      )}
      <Layout>
        <Header style={{ padding: '0 16px', background: colorBgContainer, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #f0f0f0' }}>
          <Button type="text" icon={collapsed && !isMobile ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => isMobile ? setDrawerOpen(true) : setCollapsed(!collapsed)} />
          <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 6 : 12 }}>
            <Tag color="blue" style={{ margin: 0, fontSize: isMobile ? 11 : 14 }}>{roleLabels[user.role] || user.role}</Tag>
            <Dropdown menu={{
              items: [
                ...(isMobile ? [{ key: 'role', label: roleLabels[user.role] || user.role, disabled: true }] : []),
                { key: 'change-pwd', icon: <KeyOutlined />, label: '修改密码', onClick: () => { pwdForm.resetFields(); setPwdModalOpen(true); } },
                { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
              ]
            }}>
              <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Avatar icon={<UserOutlined />} size="small" />
                {!isMobile && <span>{user.display_name || user.username}</span>}
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content style={{ margin: isMobile ? 8 : 16, padding: isMobile ? 12 : 24, background: colorBgContainer, borderRadius: 8, minHeight: 280, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>

      <Modal title="修改密码" open={pwdModalOpen} onOk={handleChangePassword} onCancel={() => setPwdModalOpen(false)} okText="确认修改">
        <Form form={pwdForm} layout="vertical">
          <Form.Item name="old_password" label="原密码" rules={[{ required: true, message: '请输入原密码' }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="new_password" label="新密码" rules={[{ required: true, message: '请输入新密码' }, { min: 6, message: '密码至少6位' }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="confirm_password" label="确认新密码" rules={[{ required: true, message: '请确认新密码' }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
