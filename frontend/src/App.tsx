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

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token');
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <ConfigProvider locale={zhCN} theme={{
      token: {
        colorPrimary: '#1677ff',
        borderRadius: 6,
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
