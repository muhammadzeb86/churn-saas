import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SummaryMetrics } from '../components/dashboard/SummaryMetrics';
import { RiskDistributionChart } from '../components/dashboard/RiskDistributionChart';
import { RetentionHistogram } from '../components/dashboard/RetentionHistogram';
import { FilterControls } from '../components/dashboard/FilterControls';
import { Prediction } from '../types';
import { predictionsAPI } from '../services/api';

const Dashboard: React.FC = () => {
  const [allPredictions, setAllPredictions] = useState<Prediction[]>([]);
  const [filteredPredictions, setFilteredPredictions] = useState<Prediction[]>([]);
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
      const predictionsData = response.data?.predictions || response.data || [];
      setAllPredictions(predictionsData);
      setFilteredPredictions(predictionsData); // Initially show all
      
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load data');
      setError(error);
      console.error('Loading failed:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPredictions();
  }, [loadPredictions]);

  // Handle filtered data from FilterControls
  const handleFilteredDataChange = useCallback((filtered: Prediction[], metrics: any) => {
    setFilteredPredictions(filtered);
    
    // Log performance warning if filtering is slow
    if (metrics.duration > 100) {
      console.warn(`Filtering took ${metrics.duration.toFixed(0)}ms for ${metrics.originalCount} items`);
    }
  }, []);

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
          {/* Filter Controls */}
          <FilterControls
            predictions={allPredictions}
            onFilteredDataChange={handleFilteredDataChange}
            highRiskThreshold={0.7}
            mediumRiskThreshold={0.4}
          />

          {/* Summary Metrics with its own error boundary */}
          <ErrorBoundary 
            fallback={<div className="text-red-600 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">Metrics unavailable. Please refresh the page.</div>}
            onError={(error) => console.error('Metrics error:', error)}
          >
            <SummaryMetrics
              predictions={filteredPredictions}
              isLoading={isLoading}
              error={error}
              modelVersion="v2.1.4"
            />
          </ErrorBoundary>

          {/* Risk Distribution Chart */}
          <ErrorBoundary
            fallback={<div className="text-red-600 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">Risk chart unavailable. Please refresh the page.</div>}
            onError={(error) => console.error('Risk chart error:', error)}
          >
            <RiskDistributionChart
              predictions={filteredPredictions}
              isLoading={isLoading}
              error={error}
              modelMetadata={{
                version: "v2.1.4",
                accuracy: 0.87
              }}
              enableSampling={true}
            />
          </ErrorBoundary>

          {/* Retention Probability Histogram */}
          <ErrorBoundary
            fallback={<div className="text-red-600 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">Retention histogram unavailable. Please refresh the page.</div>}
            onError={(error) => console.error('Retention histogram error:', error)}
          >
            <RetentionHistogram
              predictions={filteredPredictions}
              isLoading={isLoading}
              error={error}
              modelMetadata={{
                version: "v2.1.4",
                accuracy: 0.87
              }}
              enableSampling={true}
              showConfidenceIntervals={true}
            />
          </ErrorBoundary>

          {/* Placeholder for future components */}
          {filteredPredictions.length > 0 && (
            <div className="text-center text-gray-500 dark:text-gray-400 py-8 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg">
              <p className="mb-2">📊 More visualizations coming soon...</p>
              <p className="text-sm">
                Next: Trend Analysis & Time Series Predictions
              </p>
              <p className="text-xs mt-2 text-gray-400">
                Phase 4 - Tasks 4.5+
              </p>
            </div>
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
};

export default Dashboard;
