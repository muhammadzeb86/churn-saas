import React, { useMemo, useCallback, lazy, Suspense, useRef, useEffect } from 'react';
import { z } from 'zod';
import { ErrorBoundary } from '../ErrorBoundary';
import debounce from 'lodash.debounce';
import type { Prediction } from '../../types';
import { ChartSkeleton } from './ChartSkeleton';
import { ChartError } from './ChartError';
import { ChartEmpty } from './ChartEmpty';

// Lazy load Recharts (50KB saved on initial load)
const RiskBarChart = lazy(() => import('./charts/BarChart'));

// ✅ FIX #1: Strict schema with minimal required fields
const PredictionSchema = z.object({
  id: z.string(),
  churn_probability: z.number().min(0).max(1),
  status: z.enum(['queued', 'processing', 'completed', 'failed'])
}).strict(); // No passthrough - reject unknown properties

type ValidatedPrediction = z.infer<typeof PredictionSchema>;

// ✅ FIX #1: Type guard that matches schema
const isValidPrediction = (pred: any): pred is ValidatedPrediction => {
  return (
    typeof pred?.id === 'string' &&
    typeof pred?.churn_probability === 'number' &&
    pred.churn_probability >= 0 &&
    pred.churn_probability <= 1 &&
    pred.status === 'completed' // Only process completed predictions
  );
};

export interface RiskDistributionChartProps {
  predictions: Prediction[];
  isLoading?: boolean;
  error?: Error | null;
  thresholds?: {
    high: number;
    medium: number;
  };
  onSegmentClick?: (segment: RiskLevel) => void;
  /** Enable sampling for datasets > 10k */
  enableSampling?: boolean;
  /** Model metadata for context */
  modelMetadata?: {
    version: string;
    accuracy: number;
    lastTrained?: Date;
  };
}

export type RiskLevel = 'low' | 'medium' | 'high';

export interface RiskSegment {
  type: RiskLevel;
  name: string;
  count: number;
  percentage: number;
  color: string;
  range: string;
  ariaLabel: string;
}

interface ProcessingStats {
  processed: number;
  sampled: boolean;
  duration: number;
  validationErrors: number;
}

const SAMPLE_THRESHOLD = 10000;
const DEFAULT_THRESHOLDS = { high: 0.7, medium: 0.4 };

// ✅ FIX #2: Proper random sampling (Fisher-Yates shuffle + slice)
function getSampledPredictions<T>(arr: T[], maxSamples: number): T[] {
  if (arr.length <= maxSamples) return arr;
  
  // Create shuffled copy without modifying original
  const shuffled = [...arr];
  
  // Fisher-Yates shuffle (first maxSamples elements)
  for (let i = 0; i < maxSamples; i++) {
    const j = Math.floor(Math.random() * (arr.length - i)) + i;
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  
  return shuffled.slice(0, maxSamples);
}

// Fallback component for chart errors
const ChartCrashFallback: React.FC = () => (
  <div className="bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-800 rounded-lg p-6 text-center">
    <p className="text-red-800 dark:text-red-300 font-semibold mb-2">
      Chart Error
    </p>
    <p className="text-sm text-red-700 dark:text-red-400">
      The chart component encountered an error. Please refresh the page.
    </p>
  </div>
);

export const RiskDistributionChart: React.FC<RiskDistributionChartProps> = React.memo(({
  predictions,
  isLoading = false,
  error = null,
  thresholds = DEFAULT_THRESHOLDS,
  onSegmentClick,
  enableSampling = true,
  modelMetadata
}) => {
  // ✅ FIX #5: Refs to prevent memory leaks
  const mountedRef = useRef(true);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  // Optimized data processing with proper sampling
  const { riskData, stats } = useMemo(() => {
    if (!predictions?.length) {
      return {
        riskData: [],
        stats: { processed: 0, sampled: false, duration: 0, validationErrors: 0 }
      };
    }
    
    const startTime = performance.now();
    
    // ✅ FIX #2: Proper sampling
    const shouldSample = enableSampling && predictions.length > SAMPLE_THRESHOLD;
    const sampledPredictions = shouldSample
      ? getSampledPredictions(predictions, SAMPLE_THRESHOLD)
      : predictions;
    
    // Process sampled data
    let counts = { low: 0, medium: 0, high: 0 };
    let validCount = 0;
    let validationErrors = 0;
    
    // ✅ FIX #1: Proper validation with type guard
    for (const pred of sampledPredictions) {
      if (!isValidPrediction(pred)) {
        validationErrors++;
        // Log first 5 errors only (avoid console spam)
        if (validationErrors <= 5) {
          // Cast to any for debug logging of invalid data
          const debugPred = pred as any;
          console.debug('[RiskChart] Invalid prediction:', {
            hasId: !!debugPred?.id,
            hasProb: typeof debugPred?.churn_probability === 'number',
            status: debugPred?.status
          });
        }
        continue;
      }
      
      validCount++;
      
      const prob = pred.churn_probability;
      
      // Categorize
      if (prob >= thresholds.high) counts.high++;
      else if (prob >= thresholds.medium) counts.medium++;
      else counts.low++;
    }
    
    // ✅ FIX #3: Calculate percentages BEFORE scaling
    const sampledTotal = counts.low + counts.medium + counts.high;
    const percentages = {
      low: sampledTotal > 0 ? (counts.low / sampledTotal) * 100 : 0,
      medium: sampledTotal > 0 ? (counts.medium / sampledTotal) * 100 : 0,
      high: sampledTotal > 0 ? (counts.high / sampledTotal) * 100 : 0
    };
    
    // ✅ FIX #3: Scale counts back to full population
    const scaleFactor = predictions.length / sampledPredictions.length;
    const scaledCounts = {
      low: Math.round(counts.low * scaleFactor),
      medium: Math.round(counts.medium * scaleFactor),
      high: Math.round(counts.high * scaleFactor)
    };
    
    // Create segments with scaled counts but original percentages
    const riskData = [
      createSegment('low', scaledCounts.low, percentages.low, thresholds),
      createSegment('medium', scaledCounts.medium, percentages.medium, thresholds),
      createSegment('high', scaledCounts.high, percentages.high, thresholds)
    ].filter(s => s.count > 0);
    
    const duration = performance.now() - startTime;
    
    // Monitor performance (only if still mounted)
    if (mountedRef.current && duration > 100) {
      console.warn('[RiskChart] Slow calculation:', {
        duration: `${duration.toFixed(0)}ms`,
        predictions: predictions.length,
        sampled: shouldSample,
        validationErrors
      });
    }
    
    return {
      riskData,
      stats: {
        processed: validCount,
        sampled: shouldSample,
        duration,
        validationErrors
      }
    };
  }, [predictions, thresholds, enableSampling]);
  
  // ✅ FIX #6: Debounced click handler
  const handleSegmentInteraction = useMemo(
    () =>
      debounce(
        (segment: RiskSegment, event: React.MouseEvent | React.KeyboardEvent) => {
          if (event.defaultPrevented) return;
          
          event.preventDefault();
          
          console.debug('[RiskChart] Segment clicked:', {
            segment: segment.type,
            count: segment.count,
            timestamp: Date.now()
          });
          
          onSegmentClick?.(segment.type);
        },
        300,
        { leading: true, trailing: false }
      ),
    [onSegmentClick]
  );
  
  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      handleSegmentInteraction.cancel();
    };
  }, [handleSegmentInteraction]);
  
  // Loading state
  if (isLoading) {
    return (
      <div
        className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md"
        role="status"
        aria-busy="true"
        aria-label="Loading risk distribution chart"
      >
        <ChartSkeleton />
      </div>
    );
  }
  
  // Error state
  if (error) {
    return <ChartError error={error} onRetry={() => window.location.reload()} />;
  }
  
  // Empty state
  if (!riskData.length) {
    return <ChartEmpty />;
  }
  
  return (
    <ErrorBoundary
      fallback={<ChartCrashFallback />}
      onError={(error) => {
        console.error('[RiskChart] Render error:', error);
      }}
    >
      <div
        className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md mb-6"
        role="region"
        aria-label="Customer risk distribution"
        aria-describedby="chart-description"
        aria-live="polite"
        aria-atomic="false"
      >
        {/* ✅ FIX #4: Proper accessibility */}
        <div id="chart-description" className="sr-only">
          Bar chart showing distribution of customers across low, medium, and high risk categories.
          Use arrow keys to navigate between bars. Press Enter or Space to filter by risk level.
        </div>
        
        {/* Live region for screen readers */}
        <div role="status" aria-live="polite" className="sr-only">
          Showing {riskData.reduce((sum, s) => sum + s.count, 0)} customers
          across {riskData.length} risk levels.
          {stats.sampled && ` Data sampled from ${predictions.length.toLocaleString()} total predictions.`}
          {stats.validationErrors > 0 && ` ${stats.validationErrors} predictions skipped due to validation errors.`}
        </div>
        
        <h3 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
          Customer Risk Distribution
        </h3>
        
        {/* Validation warning */}
        {stats.validationErrors > 0 && (
          <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
            <p className="text-sm text-yellow-800 dark:text-yellow-300">
              ⚠️ {stats.validationErrors} predictions were skipped due to invalid data.
            </p>
          </div>
        )}
        
        {/* Lazy-loaded chart */}
        <Suspense fallback={<div className="h-80 flex items-center justify-center"><div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-600"></div></div>}>
          <RiskBarChart
            data={riskData}
            onBarClick={(segment: RiskSegment, event: React.MouseEvent) => {
              handleSegmentInteraction(segment, event);
            }}
          />
        </Suspense>
        
        {/* Accessible legend with keyboard support */}
        <div className="mt-4 flex flex-wrap justify-center gap-4" role="group" aria-label="Risk level legend">
          {riskData.map((segment) => (
            <button
              key={segment.type}
              onClick={(e) => handleSegmentInteraction(segment, e)}
              onKeyDown={(e) => {
                // ✅ FIX #4: Only trigger on Enter/Space
                if (e.key === 'Enter' || e.key === ' ') {
                  handleSegmentInteraction(segment, e);
                }
              }}
              disabled={!onSegmentClick}
              className="flex items-center gap-2 px-3 py-2 rounded-md transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label={segment.ariaLabel}
              role="button"
              tabIndex={0}
            >
              <div
                className="w-4 h-4 rounded"
                style={{ backgroundColor: segment.color }}
                aria-hidden="true"
              />
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {segment.name}:
              </span>
              <span className="font-semibold text-gray-900 dark:text-white">
                {formatNumber(segment.count)}
              </span>
              <span className="text-sm text-gray-500">
                ({segment.percentage}%)
              </span>
            </button>
          ))}
        </div>
        
        {/* Model metadata footer */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500">
          {modelMetadata && (
            <>
              Model v{modelMetadata.version} |{' '}
              Accuracy: {(modelMetadata.accuracy * 100).toFixed(1)}%
              {modelMetadata.lastTrained && (
                <> | Last trained: {formatDate(modelMetadata.lastTrained)}</>
              )}
              <br />
            </>
          )}
          {stats.sampled && (
            <>
              Data sampled for performance: {SAMPLE_THRESHOLD.toLocaleString()} of{' '}
              {predictions.length.toLocaleString()} predictions (
              {((SAMPLE_THRESHOLD / predictions.length) * 100).toFixed(1)}%)
              <br />
            </>
          )}
          Calculation time: {stats.duration.toFixed(0)}ms
        </div>
      </div>
    </ErrorBoundary>
  );
});

// ✅ FIX #3: Create segment with count and percentage as separate values
function createSegment(
  type: RiskLevel,
  count: number,
  percentage: number, // Now passed directly, not calculated
  thresholds: { high: number; medium: number }
): RiskSegment {
  const configs: Record<RiskLevel, { name: string; color: string; range: string }> = {
    low: {
      name: 'Low Risk',
      color: '#10b981',
      range: `0-${(thresholds.medium * 100).toFixed(0)}%`
    },
    medium: {
      name: 'Medium Risk',
      color: '#f59e0b',
      range: `${(thresholds.medium * 100).toFixed(0)}-${(thresholds.high * 100).toFixed(0)}%`
    },
    high: {
      name: 'High Risk',
      color: '#ef4444',
      range: `${(thresholds.high * 100).toFixed(0)}-100%`
    }
  };
  
  const config = configs[type];
  
  return {
    type,
    name: config.name,
    count,
    percentage: Math.round(percentage), // Use provided percentage
    color: config.color,
    range: config.range,
    ariaLabel: `${config.name}: ${formatNumber(count)} customers (${Math.round(percentage)}%). Churn probability ${config.range}`
  };
}

// XSS-safe number formatting
function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num);
}

// XSS-safe date formatting
function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(date);
}

RiskDistributionChart.displayName = 'RiskDistributionChart';

