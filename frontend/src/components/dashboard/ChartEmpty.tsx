import React from 'react';
import { BarChart3 } from 'lucide-react';

/**
 * Empty state for charts
 * Displayed when there is no data to visualize
 */
export const ChartEmpty: React.FC = () => {
  return (
    <div
      className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-12 text-center"
      role="region"
      aria-label="No chart data available"
    >
      <div className="flex justify-center mb-4">
        <BarChart3 className="w-16 h-16 text-gray-400 dark:text-gray-500" />
      </div>
      
      <h3 className="text-gray-700 dark:text-gray-300 text-xl font-semibold mb-3">
        No Risk Data Available
      </h3>
      
      <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
        There are no completed predictions to display in the risk distribution chart.
        Upload a CSV file to start analyzing customer churn risk.
      </p>
    </div>
  );
};

