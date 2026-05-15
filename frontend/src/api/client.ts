import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor - attach JWT token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor - handle auth errors
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default client;

// Auth API
export const authApi = {
  login: (data: { username: string; password: string }) => client.post('/api/auth/login', data),
  getMe: () => client.get('/api/auth/me'),
  logout: () => client.post('/api/auth/logout'),
  changePassword: (data: { old_password: string; new_password: string }) => client.post('/api/auth/change-password', data),
  listUsers: () => client.get('/api/auth/users'),
  createUser: (data: any) => client.post('/api/auth/users', data),
  updateUser: (userId: string, data: any) => client.put(`/api/auth/users/${userId}`, data),
  deleteUser: (userId: string) => client.delete(`/api/auth/users/${userId}`),
  resetPassword: (userId: string) => client.post(`/api/auth/users/${userId}/reset-password`),
};

// Project API
export const projectApi = {
  list: (params?: any) => client.get('/api/projects', { params }),
  get: (id: string) => client.get(`/api/projects/${id}`),
  create: (data: any) => client.post('/api/projects', data),
  update: (id: string, data: any) => client.put(`/api/projects/${id}`, data),
  delete: (id: string) => client.delete(`/api/projects/${id}`),
};

// Contract API
export const contractApi = {
  list: (params?: any) => client.get('/api/contracts', { params }),
  get: (id: string) => client.get(`/api/contracts/${id}`),
  create: (data: any) => client.post('/api/contracts', data),
  update: (id: string, data: any) => client.put(`/api/contracts/${id}`, data),
  delete: (id: string) => client.delete(`/api/contracts/${id}`),
  statistics: (params?: any) => client.get('/api/contracts/statistics', { params }),
  addPayment: (id: string, data: any) => client.post(`/api/contracts/${id}/payment`, data),
  getPayments: (id: string) => client.get(`/api/contracts/${id}/payments`),
};

// Reimbursement API
export const reimbursementApi = {
  list: (params?: any) => client.get('/api/reimbursements', { params }),
  get: (id: string) => client.get(`/api/reimbursements/${id}`),
  create: (data: any) => client.post('/api/reimbursements', data),
  update: (id: string, data: any) => client.put(`/api/reimbursements/${id}`, data),
  audit: (id: string, data: any) => client.post(`/api/reimbursements/${id}/audit`, data),
  pay: (id: string, data: any) => client.post(`/api/reimbursements/${id}/pay`, data),
  delete: (id: string) => client.delete(`/api/reimbursements/${id}`),
};

// Acceptance API
export const acceptanceApi = {
  list: (params?: any) => client.get('/api/acceptances', { params }),
  get: (id: string) => client.get(`/api/acceptances/${id}`),
  create: (data: any) => client.post('/api/acceptances', data),
  update: (id: string, data: any) => client.put(`/api/acceptances/${id}`, data),
  delete: (id: string) => client.delete(`/api/acceptances/${id}`),
};

// Inventory API
export const inventoryApi = {
  listMaterials: (params?: any) => client.get('/api/inventory/materials', { params }),
  getMaterial: (id: string) => client.get(`/api/inventory/materials/${id}`),
  createMaterial: (data: any) => client.post('/api/inventory/materials', data),
  updateMaterial: (id: string, data: any) => client.put(`/api/inventory/materials/${id}`, data),
  deleteMaterial: (id: string) => client.delete(`/api/inventory/materials/${id}`),
  getWarnings: () => client.get('/api/inventory/materials/warnings'),
  getStatistics: () => client.get('/api/inventory/materials/statistics'),
  listRecords: (params?: any) => client.get('/api/inventory/records', { params }),
  stockIn: (data: any) => client.post('/api/inventory/stock-in', data),
  stockOut: (data: any) => client.post('/api/inventory/stock-out', data),
  adjustment: (data: any) => client.post('/api/inventory/adjustment', data),
};

// Analysis API
export const analysisApi = {
  projectAnalysis: (projectId: string) => client.get(`/api/analysis/project/${projectId}`),
  overview: () => client.get('/api/analysis/overview'),
};

// Audit Log API
export const auditLogApi = {
  list: (params?: any) => client.get('/api/audit-logs', { params }),
};

// Reimburse Category API
export const reimburseCategoryApi = {
  tree: () => client.get('/api/reimburse-categories'),
  flat: () => client.get('/api/reimburse-categories/flat'),
  create: (data: any) => client.post('/api/reimburse-categories', data),
  update: (id: string, data: any) => client.put(`/api/reimburse-categories/${id}`, data),
  delete: (id: string) => client.delete(`/api/reimburse-categories/${id}`),
};

// Upload API
export const uploadApi = {
  getUploadUrl: (params: any) => client.post('/api/upload/presigned-url', null, { params }),
  getDownloadUrl: (s3Key: string, download: boolean = false) => client.get('/api/upload/presigned-download', { params: { s3_key: s3Key, download } }),
};
