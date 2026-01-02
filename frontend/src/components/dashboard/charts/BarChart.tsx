import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import type { RiskSegment } from '../RiskDistributionChart';

interface BarChartProps {
  data: RiskSegment[];
  onBarClick?: (segment: RiskSegment, event: React.MouseEvent) => void;
}

export const RiskBarChart: React.FC<BarChartProps> = ({ data, onBarClick }) => {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={data}
        margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
        aria-label="Risk distribution bar chart"
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="name"
          stroke="#6b7280"
          style={{ fontSize: '14px' }}
          aria-label="Risk level"
        />
        <YAxis
          stroke="#6b7280"
          style={{ fontSize: '14px' }}
          aria-label="Number of customers"
          tickFormatter={(value) => value.toLocaleString()}
        />
        <Tooltip
          content={<CustomTooltip />}
          cursor={{ fill: 'rgba(0, 0, 0, 0.05)' }}
        />
        <Bar
          dataKey="count"
          radius={[8, 8, 0, 0]}
          onClick={(data, index, event) => {
            if (onBarClick) {
              onBarClick(data as RiskSegment, event);
            }
          }}
          style={{ cursor: onBarClick ? 'pointer' : 'default' }}
          aria-label="Risk level bar"
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

// Custom tooltip with XSS protection
const CustomTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null;
  
  const data = payload[0].payload as RiskSegment;
  
  return (
    <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-lg border-2 border-gray-200 dark:border-gray-700">
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-3 h-3 rounded"
          style={{ backgroundColor: data.color }}
          aria-hidden="true"
        />
        <p className="font-semibold text-gray-900 dark:text-white">{data.name}</p>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
        Customers: <span className="font-semibold">{formatNumber(data.count)}</span>
      </p>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
        Percentage: <span className="font-semibold">{data.percentage}%</span>
      </p>
      <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
        Churn Probability: {data.range}
      </p>
    </div>
  );
};

// XSS-safe number formatting
function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num);
}

export default RiskBarChart;

