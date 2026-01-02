import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SummaryMetrics } from '../components/dashboard/SummaryMetrics';
import { Prediction, PaginatedResponse } from '../types';

// TODO: Import from actual API service when available
// import { predictionsAPI } from '../services/api';

// Fallback component for error boundaries
const DashboardErrorFallback = ({ error, resetErrorBoundary }: any) => (
  <div className="max-w-7xl mx-auto px-4 py-8">
    <div className="bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-800 rounded-xl p-8 text-center">
      <div className="text-6xl mb-4" aria-hidden="true">⚠️</div>
      <h2 className="text-2xl font-bold text-red-800 dark:text-red-300 mb-4">
        Dashboard Unavailable
      </h2>
      <p className="text-red-700 dark:text-red-400 mb-6">
        We encountered an error loading your dashboard.
      </p>
      <div className="space-x-4">
        <button
          onClick={resetErrorBoundary}
          className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          Try Again
        </button>
        <button
          onClick={() => window.location.reload()}
          className="px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
        >
          Refresh Page
        </button>
      </div>
    </div>
  </div>
);

export const Dashboard: React.FC = () => {
  const { getToken } = useAuth();
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [pagination, setPagination] = useState({
    page: 1,
    total: 0,
    hasMore: false
  });

  const loadPredictions = useCallback(async (page = 1, append = false) => {
    try {
      setIsLoading(true);
      setError(null);
      
      const token = await getToken();
      
      // TODO: Replace with actual API call when available
      // const response: PaginatedResponse<Prediction> = await predictionsAPI.getPredictions({
      //   page,
      //   pageSize: 100,
      //   status: 'completed',
      //   sortBy: 'churn_probability',
      //   sortOrder: 'desc'
      // }, token);
      
      // Mock data for development
      const response: PaginatedResponse<Prediction> = {
        data: [],
        metadata: {
          page,
          pageSize: 100,
          total: 0,
          hasMore: false
        }
      };

      // Server-side aggregation for large datasets
      if (response.metadata.total > 50000) {
        // TODO: Implement server-side aggregation endpoint
        // const summary = await predictionsAPI.getSummaryMetrics(token);
      }

      setPredictions(prev => 
        append ? [...prev, ...response.data] : response.data
      );
      
      setPagination({
        page,
        total: response.metadata.total,
        hasMore: response.metadata.hasMore
      });
      
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load data');
      setError(error);
      
      // TODO: Show toast notification
      console.error('Loading failed:', error.message);
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    loadPredictions(1);
  }, [loadPredictions]);

  return (
    <ErrorBoundary
      FallbackComponent={DashboardErrorFallback}
      onError={(error, info) => {
        // Log to monitoring service
        console.error('Dashboard error:', error, info);
        // TODO: Send to Sentry or similar
        // Sentry.captureException(error, { contexts: { react: info } });
      }}
      onReset={() => {
        setPredictions([]);
        setError(null);
        loadPredictions(1);
      }}
    >
      <div className="max-w-7xl mx-auto px-4 py-8">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Churn Risk Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Monitor customer retention and identify at-risk accounts
          </p>
        </header>

        <div className="space-y-6">
          {/* Summary Metrics with its own error boundary */}
          <ErrorBoundary 
            fallback={<div className="text-red-600 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">Metrics unavailable. Please refresh the page.</div>}
            onError={(error) => console.error('Metrics error:', error)}
          >
            <SummaryMetrics
              predictions={predictions}
              isLoading={isLoading}
              error={error}
              pagination={{
                total: pagination.total,
                shown: predictions.length
              }}
              modelVersion="v2.1.4"
            />
          </ErrorBoundary>

          {/* Data quality summary */}
          {predictions.length > 0 && (
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-gray-700 dark:text-gray-300">
                  Showing {predictions.length} of {pagination.total} predictions
                </span>
                {pagination.hasMore && (
                  <button
                    onClick={() => loadPredictions(pagination.page + 1, true)}
                    disabled={isLoading}
                    className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium disabled:opacity-50"
                  >
                    {isLoading ? 'Loading...' : 'Load More'}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Placeholder for future components */}
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <p className="mb-2">More visualizations coming soon...</p>
            <p className="text-sm">
              Next: Risk Distribution Chart & Retention Histogram
            </p>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
};
