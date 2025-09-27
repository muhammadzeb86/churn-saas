import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'https://api.retainwiseanalytics.com';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// API endpoints
export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  signup: (name: string, email: string, password: string) =>
    api.post('/auth/signup', { name, email, password }),
  checkHealth: () => api.get('/health'),
  syncUser: (userData: any) => api.post('/auth/sync_user', userData),
};

export const dataAPI = {
  uploadFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  getPredictions: () => api.get('/predictions'),
};

export const uploadAPI = {
  getUploads: (userId: string) => api.get('/uploads', {
    params: { user_id: userId }
  }),
  uploadCSV: (formData: FormData) => api.post('/upload/csv', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }),
};

export const predictionsAPI = {
  getPredictions: (userId: string) => api.get('/predictions', {
    params: { user_id: userId }
  }),
  getPredictionDetail: (id: string, userId: string) => api.get(`/predictions/${id}`, {
    params: { user_id: userId }
  }),
  downloadPrediction: (id: string, userId: string) => api.get(`/predictions/download_predictions/${id}`, {
    params: { user_id: userId }
  }),
};

export const powerbiAPI = {
  getEmbedToken: () => api.get('/powerbi/embed-token'),
};

// Helper function to get the full API URL for endpoints
export const getApiUrl = (endpoint: string) => `${API_URL}${endpoint}`;

export default api;
