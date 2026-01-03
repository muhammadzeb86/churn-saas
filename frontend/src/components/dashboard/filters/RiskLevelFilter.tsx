import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, Users } from 'lucide-react';
import clsx from 'clsx';
import type { RiskLevel } from '../hooks/useFilters';

interface RiskLevelFilterProps {
  value: RiskLevel;
  onChange: (level: RiskLevel) => void;
}

const RISK_OPTIONS = [
  {
    value: 'all' as const,
    label: 'All Customers',
    icon: Users,
    color: 'blue',
    description: undefined
  },
  {
    value: 'high' as const,
    label: 'High Risk',
    icon: AlertCircle,
    color: 'red',
    description: '≥ 70% churn probability'
  },
  {
    value: 'medium' as const,
    label: 'Medium Risk',
    icon: AlertTriangle,
    color: 'yellow',
    description: '40-70% churn probability'
  },
  {
    value: 'low' as const,
    label: 'Low Risk',
    icon: CheckCircle,
    color: 'green',
    description: '< 40% churn probability'
  }
] as const;

const COLOR_CLASSES = {
  blue: {
    active: 'bg-blue-100 dark:bg-blue-900/30 border-blue-500 dark:border-blue-500 text-blue-800 dark:text-blue-300',
    inactive: 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-blue-50 dark:hover:bg-blue-900/10'
  },
  red: {
    active: 'bg-red-100 dark:bg-red-900/30 border-red-500 dark:border-red-500 text-red-800 dark:text-red-300',
    inactive: 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-red-50 dark:hover:bg-red-900/10'
  },
  yellow: {
    active: 'bg-yellow-100 dark:bg-yellow-900/30 border-yellow-500 dark:border-yellow-500 text-yellow-800 dark:text-yellow-300',
    inactive: 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-yellow-50 dark:hover:bg-yellow-900/10'
  },
  green: {
    active: 'bg-green-100 dark:bg-green-900/30 border-green-500 dark:border-green-500 text-green-800 dark:text-green-300',
    inactive: 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-green-50 dark:hover:bg-green-900/10'
  }
} as const;

export const RiskLevelFilter: React.FC<RiskLevelFilterProps> = ({ value, onChange }) => {
  return (
    <div 
      className="grid grid-cols-2 md:grid-cols-4 gap-2"
      role="group"
      aria-label="Filter by risk level"
    >
      {RISK_OPTIONS.map((option) => {
        const Icon = option.icon;
        const isActive = value === option.value;
        const colorClass = COLOR_CLASSES[option.color];
        
        return (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={clsx(
              'flex flex-col items-center justify-center p-3 border-2 rounded-lg transition-all duration-200',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
              isActive ? colorClass.active : colorClass.inactive
            )}
            aria-pressed={isActive}
            aria-label={`${option.label}${option.description ? `: ${option.description}` : ''}`}
          >
            <Icon className="w-5 h-5 mb-1" />
            <span className="text-sm font-medium">{option.label}</span>
            {option.description && (
              <span className="text-xs mt-1 opacity-75">{option.description}</span>
            )}
          </button>
        );
      })}
    </div>
  );
};

