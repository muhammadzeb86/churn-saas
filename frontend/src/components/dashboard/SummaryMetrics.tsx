import React, { useMemo, useCallback } from 'react';
import { z } from 'zod';
import { MetricCard } from './MetricCard';
import { AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

// Robust validation schema - RELAXED for dashboard data
const PredictionSchema = z.object({
  id: z.string(),
  churn_probability: z.number().min(0).max(1).nullable().optional(),
  retention_probability: z.number().min(0).max(1).nullable().optional(),
  status: z.string().optional(), // Relaxed - accept any string status
  created_at: z.string().optional(),
  // Allow all other properties to pass through
}).passthrough();

interface SummaryMetricsProps {
  predictions: unknown[];
  isLoading?: boolean;
  error?: Error | null;
  /** Configuration-driven thresholds */
  thresholds?: {
    highRisk: number;
    mediumRisk: number;
  };
  /** Optional pagination info */
  pagination?: {
    total: number;
    shown: number;
  };
  /** Model version for metrics context */
  modelVersion?: string;
}

interface CalculatedMetrics {
  total: number;
  highRisk: number;
  mediumRisk: number;
  lowRisk: number;
  avgRetention: number;
  dataQuality: {
    valid: number;
    invalid: number;
    missingChurnProb: number;
  };
  distribution: {
    mean: number;
    median: number;
    stdDev: number;
  };
}

const DEFAULT_THRESHOLDS = {
  highRisk: 0.7,
  mediumRisk: 0.4
} as const;

export const SummaryMetrics: React.FC<SummaryMetricsProps> = ({
  predictions: rawPredictions,
  isLoading = false,
  error = null,
  thresholds = DEFAULT_THRESHOLDS,
  pagination,
  modelVersion
}) => {
  // Single-pass calculation with comprehensive metrics
  const metrics = useMemo<CalculatedMetrics | null>(() => {
    if (!rawPredictions || rawPredictions.length === 0) {
      console.log('📊 SummaryMetrics: No predictions data', { rawPredictions });
      return null;
    }

    console.log(`📊 SummaryMetrics: Processing ${rawPredictions.length} predictions`);

    try {
      // Initialize accumulators
      let highRisk = 0;
      let mediumRisk = 0;
      let lowRisk = 0;
      let totalRetention = 0;
      let validCount = 0;
      let invalidCount = 0;
      let missingChurnProb = 0;
      
      // For distribution stats
      const churnProbabilities: number[] = [];

      for (const rawPred of rawPredictions) {
        try {
          const pred = PredictionSchema.parse(rawPred);
          
          // Accept any completed status (backend always sends "completed" for dashboard data)
          // Skip validation of status field since all dashboard data is pre-filtered

          // Handle missing/null churn probability
          if (pred.churn_probability == null) {
            missingChurnProb++;
            continue;
          }

          const churnProb = pred.churn_probability;
          
          // Validate probability range
          if (churnProb < 0 || churnProb > 1) {
            console.warn('Invalid churn probability range:', churnProb);
            invalidCount++;
            continue;
          }

          validCount++;
          churnProbabilities.push(churnProb);
          totalRetention += 1 - churnProb;

          // Single-pass categorization
          if (churnProb > thresholds.highRisk) {
            highRisk++;
          } else if (churnProb > thresholds.mediumRisk) {
            mediumRisk++;
          } else {
            lowRisk++;
          }
        } catch (validationError) {
          invalidCount++;
          // Log with details for debugging
          console.warn('📊 SummaryMetrics: Prediction validation failed:', validationError, rawPred);
        }
      }

      console.log(`📊 SummaryMetrics: Calculated metrics`, {
        total: validCount,
        highRisk,
        mediumRisk,
        lowRisk,
        invalidCount,
        missingChurnProb
      });

      // Calculate distribution stats
      let mean = 0;
      let median = 0;
      let stdDev = 0;
      
      if (churnProbabilities.length > 0) {
        mean = churnProbabilities.reduce((a, b) => a + b, 0) / churnProbabilities.length;
        
        // Sort for median
        const sorted = [...churnProbabilities].sort((a, b) => a - b);
        const mid = Math.floor(sorted.length / 2);
        median = sorted.length % 2 !== 0 
          ? sorted[mid] 
          : (sorted[mid - 1] + sorted[mid]) / 2;
        
        // Standard deviation
        const variance = churnProbabilities.reduce((acc, val) => 
          acc + Math.pow(val - mean, 2), 0) / churnProbabilities.length;
        stdDev = Math.sqrt(variance);
      }

      const result = {
        total: validCount,
        highRisk,
        mediumRisk,
        lowRisk,
        avgRetention: validCount > 0 ? totalRetention / validCount : 0,
        dataQuality: {
          valid: validCount,
          invalid: invalidCount,
          missingChurnProb
        },
        distribution: { mean, median, stdDev }
      };

      console.log('📊 SummaryMetrics: Final result:', result);

      // Return null if no valid data
      if (validCount === 0) {
        console.warn('📊 SummaryMetrics: No valid predictions after validation');
        return null;
      }

      return result;
    } catch (error) {
      // Gracefully handle calculation errors
      console.error('Metrics calculation failed:', error);
      return null;
    }
  }, [rawPredictions, thresholds]);

  // Formatting utilities
  const formatNumber = useCallback((num: number) => {
    return new Intl.NumberFormat('en-US', {
      notation: num >= 10000 ? 'compact' : 'standard',
      maximumFractionDigits: 1
    }).format(num);
  }, []);

  const formatPercentage = useCallback((num: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1
    }).format(num);
  }, []);

  // Handle error state
  if (error) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <MetricCard
            key={i}
            title={['Total Customers', 'High Risk', 'Medium Risk', 'Avg Retention'][i]}
            value="--"
            semantic="warning"
            error={i === 0 ? error.message : undefined}
          />
        ))}
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <MetricCard
            key={i}
            title={['Total Customers', 'High Risk', 'Medium Risk', 'Avg Retention'][i]}
            value={0}
            semantic="neutral"
            isLoading
          />
        ))}
      </div>
    );
  }

  // Empty state
  if (!metrics || metrics.total === 0) {
    return (
      <div 
        className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-8 text-center mb-6"
        role="region"
        aria-label="No data available"
      >
        <div className="text-gray-400 dark:text-gray-500 text-6xl mb-4" aria-hidden="true">
          📊
        </div>
        <h3 className="text-gray-700 dark:text-gray-300 text-xl font-semibold mb-3">
          Ready to analyze your customers
        </h3>
        <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-md mx-auto">
          Upload a CSV file or connect your database to start predicting churn risk.
        </p>
        <div>
          <a 
            href="/upload"
            className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Upload CSV
          </a>
        </div>
      </div>
    );
  }

  // Data quality warning
  const hasDataIssues = metrics.dataQuality.invalid > 0 || metrics.dataQuality.missingChurnProb > 0;
  const dataQualityScore = metrics.dataQuality.valid / 
    (metrics.dataQuality.valid + metrics.dataQuality.invalid + metrics.dataQuality.missingChurnProb);

  return (
    <>
      {/* Data quality banner */}
      {hasDataIssues && (
        <div 
          className={clsx(
            'rounded-lg p-4 mb-4 border',
            dataQualityScore > 0.95 
              ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
              : dataQualityScore > 0.9
              ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
              : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
          )}
          role="alert"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <AlertTriangle className="w-5 h-5 mr-2" />
              <span className="font-medium">
                Data quality: {formatPercentage(dataQualityScore)}
              </span>
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {metrics.dataQuality.invalid > 0 && `${metrics.dataQuality.invalid} invalid`}
              {metrics.dataQuality.invalid > 0 && metrics.dataQuality.missingChurnProb > 0 && ', '}
              {metrics.dataQuality.missingChurnProb > 0 && `${metrics.dataQuality.missingChurnProb} missing probabilities`}
            </div>
          </div>
        </div>
      )}

      {/* Model version indicator */}
      {modelVersion && (
        <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
          Model: {modelVersion}
        </div>
      )}

      {/* Main metrics grid */}
      <div 
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
        role="region"
        aria-label="Customer churn risk summary metrics"
      >
        <MetricCard
          title="Total Customers"
          value={formatNumber(metrics.total)}
          subtitle={pagination ? `of ${formatNumber(pagination.total)}` : undefined}
          semantic="neutral"
          confidence={dataQualityScore > 0.95 ? 'high' : dataQualityScore > 0.9 ? 'medium' : 'low'}
        />

        <MetricCard
          title="High Risk"
          value={formatNumber(metrics.highRisk)}
          subtitle={formatPercentage(metrics.highRisk / metrics.total)}
          semantic="alert"
          onClick={() => {
            // Could trigger filter for high risk customers
            console.log('Filter to high risk');
          }}
        />

        <MetricCard
          title="Medium Risk"
          value={formatNumber(metrics.mediumRisk)}
          subtitle={formatPercentage(metrics.mediumRisk / metrics.total)}
          semantic="warning"
        />

        <MetricCard
          title="Avg Retention"
          value={formatPercentage(metrics.avgRetention)}
          subtitle={`σ ${metrics.distribution.stdDev.toFixed(3)}`}
          semantic={metrics.avgRetention > 0.7 ? 'success' : 'info'}
        />
      </div>

      {/* Optional distribution insight */}
      {metrics.distribution.stdDev > 0.2 && (
        <div className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 p-3 rounded-lg mb-4">
          <strong>Insight:</strong> High variance in predictions ({metrics.distribution.stdDev.toFixed(2)}).
          Consider segmenting customers for more targeted retention strategies.
        </div>
      )}
    </>
  );
};

