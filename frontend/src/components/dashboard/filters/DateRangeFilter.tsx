import React, { useState } from 'react';
import { Calendar } from 'lucide-react';
import clsx from 'clsx';
import type { DateRange } from '../hooks/useFilters';

interface DateRangeFilterProps {
  value: DateRange;
  customStartDate?: string;
  customEndDate?: string;
  onChange: (range: DateRange, startDate?: string, endDate?: string) => void;
}

const DATE_OPTIONS = [
  { value: 'all' as const, label: 'All Time' },
  { value: '7d' as const, label: 'Last 7 days' },
  { value: '30d' as const, label: 'Last 30 days' },
  { value: '90d' as const, label: 'Last 90 days' },
  { value: 'custom' as const, label: 'Custom Range' }
] as const;

export const DateRangeFilter: React.FC<DateRangeFilterProps> = ({
  value,
  customStartDate,
  customEndDate,
  onChange
}) => {
  const [localStartDate, setLocalStartDate] = useState(customStartDate || '');
  const [localEndDate, setLocalEndDate] = useState(customEndDate || '');
  
  const handleRangeChange = (range: DateRange) => {
    if (range === 'custom') {
      onChange(range, localStartDate || undefined, localEndDate || undefined);
    } else {
      onChange(range);
    }
  };
  
  const handleCustomDateChange = () => {
    if (localStartDate || localEndDate) {
      onChange('custom', localStartDate || undefined, localEndDate || undefined);
    }
  };
  
  return (
    <div className="space-y-3">
      {/* Quick date range buttons */}
      <div className="flex flex-wrap gap-2">
        {DATE_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => handleRangeChange(option.value)}
            className={clsx(
              'px-3 py-2 text-sm font-medium rounded-md border-2 transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
              value === option.value
                ? 'bg-blue-100 dark:bg-blue-900/30 border-blue-500 dark:border-blue-500 text-blue-800 dark:text-blue-300'
                : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
            )}
            aria-pressed={value === option.value}
          >
            {option.label}
          </button>
        ))}
      </div>
      
      {/* Custom date range inputs */}
      {value === 'custom' && (
        <div className="flex flex-col sm:flex-row gap-3 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Start Date
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="date"
                value={localStartDate}
                onChange={(e) => setLocalStartDate(e.target.value)}
                onBlur={handleCustomDateChange}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="Start date"
              />
            </div>
          </div>
          
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              End Date
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="date"
                value={localEndDate}
                onChange={(e) => setLocalEndDate(e.target.value)}
                onBlur={handleCustomDateChange}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="End date"
                min={localStartDate}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

