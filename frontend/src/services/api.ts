import axios, { InternalAxiosRequestConfig } from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'https://backend.retainwiseanalytics.com';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ✅ PRODUCTION-GRADE: Token provider function (set by app at runtime)
let tokenProviderFunction: (() => Promise<string | null>) | null = null;

/**
 * Set the token provider function
 * This should be called by the app when Clerk is initialized
 */
export const setTokenProvider = (provider: () => Promise<string | null>) => {
  tokenProviderFunction = provider;
};

// ✅ PRODUCTION-GRADE: Clerk JWT Token Interceptor
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    try {
      if (tokenProviderFunction) {
        const token = await tokenProviderFunction();
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
    } catch (error) {
      console.error('❌ Failed to get authentication token:', error);
      // Continue without token - backend will return 401 if needed
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// API endpoints
export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/api/auth/login', { email, password }),
  signup: (name: string, email: string, password: string) =>
    api.post('/api/auth/signup', { name, email, password }),
  checkHealth: () => api.get('/health'),
  syncUser: () => api.post('/api/sync-user'),
};

export const dataAPI = {
  uploadFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    // ✅ DO NOT set Content-Type manually for multipart/form-data
    // Axios automatically sets it with the correct boundary parameter
    return api.post('/api/csv', formData, {
      timeout: 120000, // 2 minutes for large file uploads
    });
  },
  // ✅ CRITICAL: Add trailing slash to match backend router structure
  getPredictions: () => api.get('/api/predictions/'),
};

export const uploadAPI = {
  getUploads: (userId: string) => api.get('/api/uploads', {
    params: { user_id: userId }
  }),
  uploadCSV: (formData: FormData, onProgress?: (percentCompleted: number) => void) => 
    api.post('/api/csv', formData, {
      // ✅ CRITICAL: Delete the default Content-Type header for multipart/form-data
      // This allows Axios to set the correct boundary automatically
      headers: {
        'Content-Type': undefined as any,  // Delete default application/json header
      },
      timeout: 120000, // 2 minutes for large file uploads
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percentCompleted);
        }
      },
    }),
};

export const predictionsAPI = {
  // User ID is extracted from JWT token on backend
  // ✅ CRITICAL: Add trailing slashes to match backend router structure
  // Backend router mounted at /api/predictions with routes defined as "/" 
  // FastAPI requires trailing slash for consistency, eliminates 307 redirects
  
  // Get prediction jobs/metadata (for Predictions page)
  getPredictions: () => api.get('/api/predictions/'),
  
  // Get customer-level prediction data for dashboard (Tasks 4.1-4.5)
  getDashboardData: (limit?: number) => api.get('/api/predictions/dashboard/data', {
    params: { limit: limit || 1000 }
  }),
  
  getPredictionDetail: (id: string) => api.get(`/api/predictions/${id}/`),
  
  downloadPrediction: (id: string) => api.get(`/api/predictions/download_predictions/${id}`),
};

export const powerbiAPI = {
  getEmbedToken: () => api.get('/api/embed-token'),
};

// Helper function to get the full API URL for endpoints
export const getApiUrl = (endpoint: string) => `${API_URL}${endpoint}`;

export default api;
