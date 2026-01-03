/**
 * Core TypeScript type definitions for RetainWise frontend
 * @module types
 */

/**
 * Prediction record from the backend API
 */
export interface Prediction {
  id: string;
  user_id: string;
  customer_id?: string;
  upload_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  churn_probability: number;
  retention_probability: number;
  risk_level?: 'high' | 'medium' | 'low';
  created_at: string;
  updated_at: string;
  result_file_key?: string;
  explanation?: string;
  risk_factors?: string | string[]; // Can be JSON string or array
  protective_factors?: string | string[]; // Can be JSON string or array
  model_version?: string;
}

/**
 * Summary metrics calculated from predictions
 */
export interface SummaryMetrics {
  totalCustomers: number;
  highRisk: number;
  mediumRisk: number;
  lowRisk: number;
  avgRetentionProb: number;
}

/**
 * Upload record from the backend API
 */
export interface Upload {
  id: string;
  user_id: string;
  filename: string;
  file_size: number;
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  error_message?: string;
}

/**
 * API error response
 */
export interface APIError {
  detail: string;
  code?: string;
  field?: string;
}

/**
 * Paginated API response wrapper
 */
export interface PaginatedResponse<T> {
  data: T[];
  metadata: {
    page: number;
    pageSize: number;
    total: number;
    hasMore: boolean;
  };
}

