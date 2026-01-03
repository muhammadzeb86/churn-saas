import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SummaryMetrics } from '../components/dashboard/SummaryMetrics';
import { RiskDistributionChart } from '../components/dashboard/RiskDistributionChart';
import { RetentionHistogram } from '../components/dashboard/RetentionHistogram';
import { FilterControls } from '../components/dashboard/FilterControls';
import { PredictionsTable } from '../components/dashboard/PredictionsTable';
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
      
      // Use new dashboard data endpoint (returns customer-level predictions)
      const response = await predictionsAPI.getDashboardData();
      
      // API returns { success: true, predictions: [...], metadata: {...} }
      const predictionsData = response.data?.predictions || [];
      setAllPredictions(predictionsData);
      setFilteredPredictions(predictionsData); // Initially show all
      
      console.log(`✅ Loaded ${predictionsData.length} customer predictions for dashboard`);
      
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load data');
      setError(error);
      console.error('❌ Dashboard loading failed:', error);
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

          {/* Enhanced Predictions Table */}
          <ErrorBoundary
            fallback={<div className="text-red-600 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">Predictions table unavailable. Please refresh the page.</div>}
            onError={(error) => console.error('Table error:', error)}
          >
            <PredictionsTable
              predictions={filteredPredictions}
              isLoading={isLoading}
              error={error}
            />
          </ErrorBoundary>
        </div>
      </div>
    </ErrorBoundary>
  );
};

export default Dashboard;
