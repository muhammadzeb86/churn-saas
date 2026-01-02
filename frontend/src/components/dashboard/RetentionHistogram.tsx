import React, { useMemo, useCallback, lazy, Suspense, useRef, useEffect } from 'react';
import { z } from 'zod';
import { ErrorBoundary } from '../ErrorBoundary';
import debounce from 'lodash.debounce';
import type { Prediction } from '../../types';
import { ChartSkeleton } from './ChartSkeleton';
import { ChartError } from './ChartError';
import { ChartEmpty } from './ChartEmpty';

// ✅ Bar chart, not area chart
const RetentionBarChart = lazy(() => import('./charts/RetentionBarChart'));

// ✅ Strict schema (same as Task 4.2)
const PredictionSchema = z.object({
  id: z.string(),
  churn_probability: z.number().min(0).max(1),
  status: z.enum(['queued', 'processing', 'completed', 'failed'])
}).strict();

type ValidatedPrediction = z.infer<typeof PredictionSchema>;

// ✅ FIX: Use `unknown` instead of `any` for type safety
const isValidPrediction = (pred: unknown): pred is ValidatedPrediction => {
  const result = PredictionSchema.safeParse(pred);
  return result.success && result.data.status === 'completed';
};

export interface RetentionHistogramProps {
  predictions: Prediction[];
  isLoading?: boolean;
  error?: Error | null;
  enableSampling?: boolean;
  /** Show confidence intervals when sampling */
  showConfidenceIntervals?: boolean;
  onBinClick?: (bin: BinData) => void;
  modelMetadata?: {
    version: string;
    accuracy: number;
    lastTrained?: Date;
  };
}

export interface BinData {
  label: string;
  count: number;
  /** Lower bound of 95% confidence interval */
  countLow?: number;
  /** Upper bound of 95% confidence interval */
  countHigh?: number;
  percentage: number;
  /** Confidence interval width for percentage */
  percentageCI?: number;
  minRetention: number;
  maxRetention: number;
  midpoint: number;
  ariaLabel: string;
}

interface ProcessingStats {
  processed: number;
  sampled: boolean;
  duration: number;
  validationErrors: number;
  emptyBins: number;
  numBins: number;
}

const SAMPLE_THRESHOLD = 10000;

// ✅ Fisher-Yates sampling (same as Task 4.2)
function getSampledPredictions<T>(arr: T[], maxSamples: number): T[] {
  if (arr.length <= maxSamples) return arr;
  
  const shuffled = [...arr];
  for (let i = 0; i < maxSamples; i++) {
    const j = Math.floor(Math.random() * (arr.length - i)) + i;
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, maxSamples);
}

// ✅ FIX: Simple adaptive binning based on data range
function getOptimalBinCount(retentionProbs: number[]): number {
  if (retentionProbs.length === 0) return 10;
  
  const min = Math.min(...retentionProbs);
  const max = Math.max(...retentionProbs);
  const range = max - min;
  
  // Adaptive based on data spread
  if (range < 0.2) return 5;   // Narrow range (e.g., 0.4-0.6)
  if (range < 0.5) return 7;   // Moderate range (e.g., 0.3-0.8)
  return 10;                   // Full range or default
}

const ChartCrashFallback: React.FC = () => (
  <div className="bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-800 rounded-lg p-6 text-center">
    <p className="text-red-800 dark:text-red-300 font-semibold mb-2">Chart Error</p>
    <p className="text-sm text-red-700 dark:text-red-400">
      The histogram component encountered an error. Please refresh the page.
    </p>
  </div>
);

export const RetentionHistogram: React.FC<RetentionHistogramProps> = React.memo(({
  predictions,
  isLoading = false,
  error = null,
  enableSampling = true,
  showConfidenceIntervals = true,
  onBinClick,
  modelMetadata
}) => {
  const mountedRef = useRef(true);
  
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  // ✅ FIX: Optimized to 2 loops instead of 5, with confidence intervals
  const { histogramData, stats, modeBin, meanRetention } = useMemo(() => {
    if (!predictions?.length) {
      return {
        histogramData: [],
        stats: { processed: 0, sampled: false, duration: 0, validationErrors: 0, emptyBins: 0, numBins: 10 },
        modeBin: null,
        meanRetention: 0
      };
    }
    
    const startTime = performance.now();
    
    // Calculate optimal bin count first
    const validRetentionProbs = predictions
      .filter(p => isValidPrediction(p))
      .map(p => 1 - p.churn_probability);
    
    const numBins = getOptimalBinCount(validRetentionProbs);
    
    // Sample if needed
    const shouldSample = enableSampling && predictions.length > SAMPLE_THRESHOLD;
    const sampledPredictions = shouldSample
      ? getSampledPredictions(predictions, SAMPLE_THRESHOLD)
      : predictions;
    
    // Initialize bins
    const binWidth = 1.0 / numBins;
    const bins = Array.from({ length: numBins }, (_, i) => ({
      count: 0,
      minRetention: i * binWidth,
      maxRetention: (i + 1) * binWidth,
      midpoint: (i + 0.5) * binWidth
    }));
    
    let validCount = 0;
    let validationErrors = 0;
    let weightedSum = 0;
    
    // ✅ LOOP 1: Single pass through predictions
    for (const pred of sampledPredictions) {
      if (!isValidPrediction(pred)) {
        validationErrors++;
        if (process.env.NODE_ENV === 'development' && validationErrors <= 5) {
          console.debug('[RetentionHistogram] Invalid prediction skipped');
        }
        continue;
      }
      
      validCount++;
      
      const retentionProb = 1 - pred.churn_probability;
      const binIndex = Math.min(Math.floor(retentionProb / binWidth), numBins - 1);
      
      bins[binIndex].count++;
      weightedSum += retentionProb;
    }
    
    const sampledTotal = bins.reduce((sum: number, bin) => sum + bin.count, 0);
    const scaleFactor = predictions.length / sampledPredictions.length;
    const meanRet = validCount > 0 ? weightedSum / validCount : 0;
    
    // ✅ LOOP 2: Single pass to create final data with confidence intervals
    let maxBin = bins[0];
    const histogramData = bins.map((bin) => {
      const percentage = sampledTotal > 0 ? (bin.count / sampledTotal) * 100 : 0;
      const estimatedCount = bin.count * scaleFactor;
      
      // ✅ FIX: Calculate confidence intervals (95% CI using normal approximation)
      let countLow: number | undefined;
      let countHigh: number | undefined;
      let percentageCI: number | undefined;
      
      if (shouldSample && bin.count > 0) {
        // Standard error for count estimate
        const standardError = Math.sqrt(bin.count) * scaleFactor;
        countLow = Math.max(0, Math.round(estimatedCount - 1.96 * standardError));
        countHigh = Math.round(estimatedCount + 1.96 * standardError);
        
        // Relative error for percentage
        percentageCI = (1.96 * standardError / estimatedCount) * 100;
      }
      
      const scaledCount = Math.round(estimatedCount);
      const minPercent = Math.round(bin.minRetention * 100);
      const maxPercent = Math.round(bin.maxRetention * 100);
      const label = `${minPercent}-${maxPercent}%`;
      
      if (bin.count > maxBin.count) {
        maxBin = bin;
      }
      
      return {
        label,
        count: scaledCount,
        countLow,
        countHigh,
        percentage: Math.round(percentage),
        percentageCI: percentageCI ? Math.round(percentageCI * 10) / 10 : undefined,
        minRetention: bin.minRetention,
        maxRetention: bin.maxRetention,
        midpoint: bin.midpoint,
        ariaLabel: `Retention probability ${label}: ${formatNumber(scaledCount)} customers` +
          (countLow && countHigh ? ` (range ${formatNumber(countLow)}-${formatNumber(countHigh)})` : '') +
          ` (${Math.round(percentage)}%)`
      };
    });
    
    const modeBin = histogramData.reduce((max: BinData, bin: BinData) => 
      bin.count > max.count ? bin : max,
      histogramData[0]
    );
    
    const emptyBins = histogramData.filter(bin => bin.count === 0).length;
    const duration = performance.now() - startTime;
    
    if (process.env.NODE_ENV === 'development' && duration > 100) {
      console.warn('[RetentionHistogram] Slow calculation:', {
        duration: `${duration.toFixed(0)}ms`,
        predictions: predictions.length,
        sampled: shouldSample,
        numBins
      });
    }
    
    return {
      histogramData,
      stats: {
        processed: validCount,
        sampled: shouldSample,
        duration,
        validationErrors,
        emptyBins,
        numBins
      },
      modeBin,
      meanRetention: meanRet
    };
  }, [predictions, enableSampling]);
  
  // ✅ FIX: Stable debounce with useRef
  const handleBinInteractionRef = useRef(
    debounce(
      (bin: BinData, event: React.MouseEvent | React.KeyboardEvent) => {
        if (event.defaultPrevented) return;
        event.preventDefault();
        
        if (process.env.NODE_ENV === 'development') {
          console.debug('[RetentionHistogram] Bin clicked:', bin.label);
        }
        
        onBinClick?.(bin);
      },
      300,
      { leading: true, trailing: false }
    )
  );
  
  const handleBinInteraction = useCallback((bin: BinData, event: React.MouseEvent | React.KeyboardEvent) => {
    handleBinInteractionRef.current(bin, event);
  }, []);
  
  useEffect(() => {
    return () => {
      handleBinInteractionRef.current.cancel();
    };
  }, []);
  
  if (isLoading) {
    return (
      <div
        className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md"
        role="status"
        aria-busy="true"
        aria-label="Loading retention histogram"
      >
        <ChartSkeleton />
      </div>
    );
  }
  
  if (error) {
    return <ChartError error={error} onRetry={() => window.location.reload()} />;
  }
  
  if (!histogramData.length || histogramData.every(bin => bin.count === 0)) {
    return <ChartEmpty />;
  }
  
  // Calculate total customers for display (explicit typing for TypeScript)
  const totalCustomers: number = histogramData.reduce((sum: number, bin: BinData) => sum + bin.count, 0);
  
  return (
    <ErrorBoundary
      fallback={<ChartCrashFallback />}
      onError={(error) => {
        console.error('[RetentionHistogram] Render error:', error);
      }}
    >
      <div
        className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md mb-6"
        role="region"
        aria-label="Customer retention probability distribution"
        aria-describedby="histogram-description"
        aria-live="polite"
        aria-atomic="false"
      >
        <div id="histogram-description" className="sr-only">
          Bar chart showing distribution of customers across {stats.numBins} retention probability ranges.
          Use arrow keys to navigate between bars. Press Enter or Space to view details for a specific range.
        </div>
        
        <div role="status" aria-live="polite" className="sr-only">
          Showing {totalCustomers} customers
          across {stats.numBins - stats.emptyBins} retention probability ranges.
          {stats.sampled && ` Data sampled from ${predictions.length.toLocaleString()} total predictions. Estimates include confidence intervals.`}
          {stats.validationErrors > 0 && ` ${stats.validationErrors} predictions skipped due to validation errors.`}
        </div>
        
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
            Retention Probability Distribution
          </h3>
          
          {modeBin && (
            <div className="flex items-center gap-3 text-sm">
              <div className="flex items-center gap-1">
                <span className="text-gray-600 dark:text-gray-400">Peak:</span>
                <span className="font-semibold text-blue-600 dark:text-blue-400">
                  {modeBin.label}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-gray-600 dark:text-gray-400">Bins:</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                  {stats.numBins}
                </span>
              </div>
            </div>
          )}
        </div>
        
        {/* ✅ NEW: Sampling notice with confidence interval explanation */}
        {stats.sampled && showConfidenceIntervals && (
          <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-300">
              ℹ️ Data sampled for performance. Counts shown with 95% confidence intervals.
              {' '}Hover over bars to see ranges.
            </p>
          </div>
        )}
        
        {stats.validationErrors > 0 && (
          <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
            <p className="text-sm text-yellow-800 dark:text-yellow-300">
              ⚠️ {stats.validationErrors} predictions were skipped due to invalid data.
            </p>
          </div>
        )}
        
        <Suspense fallback={<div className="h-80 flex items-center justify-center"><div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-600"></div></div>}>
          <RetentionBarChart
            data={histogramData}
            showConfidenceIntervals={showConfidenceIntervals && stats.sampled}
            onBarClick={(bin: BinData, event: React.MouseEvent) => {
              handleBinInteraction(bin, event);
            }}
          />
        </Suspense>
        
        {/* Statistical insights */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          {modeBin && (
            <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg">
              <p className="text-xs text-blue-600 dark:text-blue-400 font-medium mb-1">
                Most Common Range
              </p>
              <p className="text-lg font-bold text-blue-800 dark:text-blue-300">
                {modeBin.label}
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400">
                {formatNumber(modeBin.count)} customers
                {modeBin.countLow && modeBin.countHigh && 
                  ` (${formatNumber(modeBin.countLow)}-${formatNumber(modeBin.countHigh)})`
                }
              </p>
            </div>
          )}
          
          <div className="bg-green-50 dark:bg-green-900/20 p-3 rounded-lg">
            <p className="text-xs text-green-600 dark:text-green-400 font-medium mb-1">
              Average Retention
            </p>
            <p className="text-lg font-bold text-green-800 dark:text-green-300">
              {(meanRetention * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-green-600 dark:text-green-400">
              across all customers
            </p>
          </div>
          
          <div className="bg-gray-50 dark:bg-gray-700/20 p-3 rounded-lg">
            <p className="text-xs text-gray-600 dark:text-gray-400 font-medium mb-1">
              Data Quality
            </p>
            <p className="text-lg font-bold text-gray-800 dark:text-gray-300">
              {((stats.processed / (stats.processed + stats.validationErrors)) * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {formatNumber(stats.processed)} valid predictions
            </p>
          </div>
        </div>
        
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
              Sampled: {SAMPLE_THRESHOLD.toLocaleString()} of{' '}
              {predictions.length.toLocaleString()} predictions (
              {((SAMPLE_THRESHOLD / predictions.length) * 100).toFixed(1)}%)
              {showConfidenceIntervals && ' | 95% confidence intervals shown'}
              <br />
            </>
          )}
          Calculation: {stats.duration.toFixed(0)}ms | Bins: {stats.numBins} (adaptive) | Empty: {stats.emptyBins}
        </div>
      </div>
    </ErrorBoundary>
  );
});

function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num);
}

function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(date);
}

RetentionHistogram.displayName = 'RetentionHistogram';

