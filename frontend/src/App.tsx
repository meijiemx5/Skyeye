import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from './components/MainLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import Contracts from './pages/Contracts';
import Reimbursements from './pages/Reimbursements';
import ReimburseCategories from './pages/ReimburseCategories';
import Acceptances from './pages/Acceptances';
import Inventory from './pages/Inventory';
import Users from './pages/Users';
import AuditLogs from './pages/AuditLogs';
import UserGuide from './pages/UserGuide';
import Todos from './pages/Todos';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token');
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <ConfigProvider locale={zhCN} theme={{
      token: {
        colorPrimary: '#2563eb',
        colorInfo: '#2563eb',
        colorSuccess: '#0f9d58',
        colorWarning: '#f59e0b',
        colorError: '#e5484d',
        colorTextBase: '#1e293b',
        colorBgLayout: '#f5f7fa',
        borderRadius: 8,
        borderRadiusLG: 12,
        controlHeight: 36,
        fontSize: 14,
        lineHeight: 1.5715,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Roboto, 'Helvetica Neue', Arial, sans-serif",
        boxShadow: '0 1px 2px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.06)',
        boxShadowSecondary: '0 6px 16px rgba(15,23,42,0.08)',
      },
      components: {
        Layout: {
          headerBg: '#ffffff',
          bodyBg: '#f5f7fa',
          siderBg: '#0f172a',
          headerHeight: 60,
          headerPadding: '0 20px',
        },
        Menu: {
          darkItemBg: 'transparent',
          darkSubMenuItemBg: 'transparent',
          darkItemSelectedBg: '#2563eb',
          darkItemHoverBg: 'rgba(148,163,184,0.16)',
          darkItemColor: 'rgba(226,232,240,0.75)',
          darkItemHoverColor: '#ffffff',
          darkItemSelectedColor: '#ffffff',
          itemBorderRadius: 8,
          itemMarginInline: 10,
          itemHeight: 42,
        },
        Card: {
          borderRadiusLG: 12,
          paddingLG: 20,
          colorBorderSecondary: '#eef1f6',
        },
        Table: {
          headerBg: '#f8fafc',
          headerColor: '#64748b',
          headerSplitColor: 'transparent',
          borderColor: '#eef1f6',
          rowHoverBg: '#f8fafc',
          cellPaddingBlock: 12,
          headerBorderRadius: 10,
        },
        Button: {
          fontWeight: 500,
          primaryShadow: '0 1px 2px rgba(37,99,235,0.22)',
          defaultShadow: 'none',
        },
        Statistic: {
          contentFontSize: 26,
          titleFontSize: 13,
        },
        Tag: {
          borderRadiusSM: 6,
        },
        Segmented: {
          itemSelectedBg: '#2563eb',
          itemSelectedColor: '#ffffff',
        },
      },
    }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={
            <PrivateRoute>
              <MainLayout />
            </PrivateRoute>
          }>
            <Route index element={<Dashboard />} />
            <Route path="todos" element={<Todos />} />
            <Route path="projects" element={<Projects />} />
            <Route path="projects/:id" element={<ProjectDetail />} />
            <Route path="contracts" element={<Contracts />} />
            <Route path="reimbursements" element={<Reimbursements />} />
            <Route path="reimburse-categories" element={<ReimburseCategories />} />
            <Route path="acceptances" element={<Acceptances />} />
            <Route path="inventory" element={<Inventory />} />
            <Route path="users" element={<Users />} />
            <Route path="audit-logs" element={<AuditLogs />} />
            <Route path="guide" element={<UserGuide />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
