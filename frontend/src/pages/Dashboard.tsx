import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SummaryMetrics } from '../components/dashboard/SummaryMetrics';
import { Prediction } from '../types';
import { predictionsAPI } from '../services/api';

const Dashboard: React.FC = () => {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadPredictions = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Use existing API - returns all predictions (no pagination yet)
      // TODO: Implement server-side pagination in Phase 5 for 50k+ records
      const response = await predictionsAPI.getPredictions();
      
      // API returns { predictions: [...] }
      const predictionsData = response.data?.predictions || [];
      setPredictions(predictionsData);
      
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load data');
      setError(error);
      console.error('Loading failed:', error.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPredictions();
  }, [loadPredictions]);

  return (
    <ErrorBoundary
      onError={(error, info) => {
        console.error('Dashboard error:', error, info);
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
              modelVersion="v2.1.4"
            />
          </ErrorBoundary>

          {/* Placeholder for future components */}
          {predictions.length > 0 && (
            <div className="text-center text-gray-500 dark:text-gray-400 py-8 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg">
              <p className="mb-2">📊 More visualizations coming soon...</p>
              <p className="text-sm">
                Next: Risk Distribution Chart & Retention Histogram
              </p>
              <p className="text-xs mt-2 text-gray-400">
                Phase 4 - Task 4.2 & 4.3
              </p>
            </div>
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
};

export default Dashboard;
