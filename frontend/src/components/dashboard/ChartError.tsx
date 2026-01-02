import React from 'react';
import { AlertCircle } from 'lucide-react';

interface ChartErrorProps {
  error: Error;
  onRetry?: () => void;
}

/**
 * Error state for charts
 * Displays user-friendly error message with retry option
 */
export const ChartError: React.FC<ChartErrorProps> = ({ error, onRetry }) => {
  return (
    <div
      className="bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-800 rounded-lg p-8 text-center"
      role="alert"
      aria-label="Chart loading error"
    >
      <div className="flex justify-center mb-4">
        <AlertCircle className="w-12 h-12 text-red-600 dark:text-red-400" />
      </div>
      
      <h3 className="text-xl font-semibold text-red-800 dark:text-red-300 mb-2">
        Unable to Load Chart
      </h3>
      
      <p className="text-red-700 dark:text-red-400 mb-4 max-w-md mx-auto">
        {error.message || 'An unexpected error occurred while loading the risk distribution chart.'}
      </p>
      
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
        >
          Try Again
        </button>
      )}
    </div>
  );
};

