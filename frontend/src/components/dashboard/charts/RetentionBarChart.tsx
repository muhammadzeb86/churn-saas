import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ErrorBar
} from 'recharts';
import type { BinData } from '../RetentionHistogram';

interface RetentionBarChartProps {
  data: BinData[];
  showConfidenceIntervals?: boolean;
  onBarClick?: (bin: BinData, event: React.MouseEvent) => void;
}

export const RetentionBarChart: React.FC<RetentionBarChartProps> = ({ 
  data, 
  showConfidenceIntervals = false,
  onBarClick 
}) => {
  // ✅ Color gradient: Higher retention = greener
  const getBarColor = (midpoint: number): string => {
    const retentionPercent = midpoint * 100;
    if (retentionPercent >= 70) return '#10b981'; // Green
    if (retentionPercent >= 50) return '#3b82f6'; // Blue
    if (retentionPercent >= 30) return '#f59e0b'; // Yellow
    return '#ef4444'; // Red
  };
  
  // Calculate error bar data for confidence intervals
  const dataWithErrors = data.map(bin => ({
    ...bin,
    // Error bar values (difference from count)
    errorLow: bin.countLow ? bin.count - bin.countLow : undefined,
    errorHigh: bin.countHigh ? bin.countHigh - bin.count : undefined
  }));
  
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={dataWithErrors}
        margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
        aria-label="Retention probability distribution bar chart"
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="label"
          stroke="#6b7280"
          style={{ fontSize: '12px' }}
          aria-label="Retention probability range"
          angle={-45}
          textAnchor="end"
          height={60}
        />
        <YAxis
          stroke="#6b7280"
          style={{ fontSize: '12px' }}
          aria-label="Number of customers"
          tickFormatter={(value) => value.toLocaleString()}
        />
        <Tooltip
          content={<CustomTooltip showConfidenceIntervals={showConfidenceIntervals} />}
          cursor={{ fill: 'rgba(59, 130, 246, 0.1)' }}
        />
        <Bar
          dataKey="count"
          radius={[8, 8, 0, 0]}
          onClick={(data, index, event) => {
            if (onBarClick) {
              onBarClick(data as BinData, event);
            }
          }}
          style={{ cursor: onBarClick ? 'pointer' : 'default' }}
          aria-label="Retention probability bar"
        >
          {data.map((entry, index) => (
            <Cell 
              key={`cell-${index}`} 
              fill={getBarColor(entry.midpoint)} 
            />
          ))}
          
          {/* ✅ Show confidence interval error bars when sampling */}
          {showConfidenceIntervals && (
            <ErrorBar 
              dataKey="errorHigh" 
              width={4} 
              strokeWidth={2}
              stroke="#6b7280"
              direction="y"
            />
          )}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

interface CustomTooltipProps {
  active?: boolean;
  payload?: any[];
  showConfidenceIntervals?: boolean;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ 
  active, 
  payload, 
  showConfidenceIntervals = false 
}) => {
  if (!active || !payload || !payload.length) return null;
  
  const data = payload[0].payload as BinData;
  
  return (
    <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-lg border-2 border-blue-200 dark:border-blue-700">
      <div className="mb-2">
        <p className="font-semibold text-gray-900 dark:text-white">
          Retention Probability: {data.label}
        </p>
      </div>
      <div className="space-y-1">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Customers: <span className="font-semibold text-blue-600 dark:text-blue-400">{formatNumber(data.count)}</span>
        </p>
        
        {/* ✅ Show confidence interval in tooltip */}
        {showConfidenceIntervals && data.countLow && data.countHigh && (
          <p className="text-xs text-gray-500 dark:text-gray-500">
            95% CI: {formatNumber(data.countLow)} - {formatNumber(data.countHigh)}
          </p>
        )}
        
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Percentage: <span className="font-semibold">{data.percentage}%</span>
          {showConfidenceIntervals && data.percentageCI && (
            <span className="text-xs text-gray-500"> (±{data.percentageCI.toFixed(1)}%)</span>
          )}
        </p>
        
        <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
          Range: {(data.minRetention * 100).toFixed(0)}% - {(data.maxRetention * 100).toFixed(0)}%
        </p>
      </div>
      
      {showConfidenceIntervals && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500 dark:text-gray-500 italic">
            Error bars show 95% confidence interval
          </p>
        </div>
      )}
    </div>
  );
};

function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num);
}

export default RetentionBarChart;

