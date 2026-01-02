import React from 'react';

/**
 * Loading skeleton for charts
 * Provides visual feedback while data is loading
 */
export const ChartSkeleton: React.FC = () => {
  return (
    <div className="animate-pulse" role="presentation">
      {/* Title skeleton */}
      <div className="h-6 bg-gray-300 dark:bg-gray-700 rounded w-1/3 mb-4" />
      
      {/* Chart area skeleton */}
      <div className="h-80 bg-gray-200 dark:bg-gray-700 rounded-lg mb-4 flex items-end justify-around p-4 gap-2">
        {/* Simulated bars */}
        <div className="bg-gray-300 dark:bg-gray-600 rounded-t w-full h-1/2" />
        <div className="bg-gray-300 dark:bg-gray-600 rounded-t w-full h-3/4" />
        <div className="bg-gray-300 dark:bg-gray-600 rounded-t w-full h-2/3" />
      </div>
      
      {/* Legend skeleton */}
      <div className="flex justify-center gap-4">
        <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-24" />
        <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-24" />
        <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-24" />
      </div>
    </div>
  );
};

