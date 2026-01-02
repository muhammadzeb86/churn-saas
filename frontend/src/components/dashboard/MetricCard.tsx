import React, { memo } from 'react';
import clsx from 'clsx';
import { 
  Users, 
  AlertTriangle, 
  AlertCircle, 
  TrendingUp,
  CheckCircle,
  HelpCircle 
} from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  /** Semantic meaning for proper aria labels */
  semantic: 'neutral' | 'alert' | 'warning' | 'success' | 'info';
  isLoading?: boolean;
  error?: string;
  /** Optional click handler for drill-down */
  onClick?: () => void;
  /** Data quality indicator */
  confidence?: 'high' | 'medium' | 'low';
}

const SEMANTIC_CONFIG = {
  neutral: {
    icon: Users,
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    text: 'text-blue-800 dark:text-blue-300',
    border: 'border-blue-200 dark:border-blue-800',
    ariaLabel: 'Informational metric'
  },
  alert: {
    icon: AlertCircle,
    bg: 'bg-red-50 dark:bg-red-900/20',
    text: 'text-red-800 dark:text-red-300',
    border: 'border-red-200 dark:border-red-800',
    ariaLabel: 'Critical alert metric'
  },
  warning: {
    icon: AlertTriangle,
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    text: 'text-yellow-800 dark:text-yellow-300',
    border: 'border-yellow-200 dark:border-yellow-800',
    ariaLabel: 'Warning metric'
  },
  success: {
    icon: CheckCircle,
    bg: 'bg-green-50 dark:bg-green-900/20',
    text: 'text-green-800 dark:text-green-300',
    border: 'border-green-200 dark:border-green-800',
    ariaLabel: 'Positive metric'
  },
  info: {
    icon: TrendingUp,
    bg: 'bg-indigo-50 dark:bg-indigo-900/20',
    text: 'text-indigo-800 dark:text-indigo-300',
    border: 'border-indigo-200 dark:border-indigo-800',
    ariaLabel: 'Performance metric'
  }
} as const;

const MetricCardComponent: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  semantic,
  isLoading = false,
  error,
  onClick,
  confidence
}) => {
  const config = SEMANTIC_CONFIG[semantic];
  const Icon = config.icon;

  // Skeleton loader
  if (isLoading) {
    return (
      <div 
        className="bg-gray-100 dark:bg-gray-800 animate-pulse rounded-lg p-6 min-h-[120px]"
        role="presentation"
        aria-label="Loading metric"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="w-10 h-10 bg-gray-300 dark:bg-gray-700 rounded-full" />
          <div className="h-4 bg-gray-300 dark:bg-gray-700 rounded w-1/4" />
        </div>
        <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-1/2 mb-2" />
        <div className="h-4 bg-gray-300 dark:bg-gray-700 rounded w-1/3" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div 
        className={clsx(
          'border-2 rounded-lg p-4',
          'bg-red-50 dark:bg-red-900/20',
          'border-red-200 dark:border-red-800'
        )}
        role="alert"
        aria-label={`Error loading ${title}`}
      >
        <div className="flex items-start">
          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 mr-2 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              Failed to load
            </p>
            <p className="text-xs text-red-700 dark:text-red-400 mt-1">
              {error}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const handleInteraction = (e: React.KeyboardEvent | React.MouseEvent) => {
    if (!onClick) return;
    
    if ('key' in e && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick();
    } else if (e.type === 'click') {
      onClick();
    }
  };

  return (
    <article
      className={clsx(
        'rounded-lg border-2 p-6 transition-all duration-200',
        'hover:shadow-lg hover:-translate-y-0.5 focus:outline-none',
        config.bg,
        config.border,
        onClick && 'cursor-pointer focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
      )}
      role={onClick ? 'button' : 'article'}
      onClick={onClick}
      onKeyDown={onClick ? handleInteraction : undefined}
      tabIndex={onClick ? 0 : -1}
      aria-label={`${title}: ${value}${subtitle ? `, ${subtitle}` : ''}. ${config.ariaLabel}`}
    >
      {/* Header with icon and confidence indicator */}
      <div className="flex items-start justify-between mb-4">
        <div className={clsx(
          'p-2 rounded-lg',
          config.bg.replace('bg-', 'bg-opacity-30')
        )}>
          <Icon className={clsx('w-6 h-6', config.text)} />
        </div>
        
        {confidence && (
          <div className="flex items-center text-xs">
            <span className="mr-1 text-gray-600 dark:text-gray-400">
              Confidence:
            </span>
            <span className={clsx(
              'px-2 py-1 rounded-full font-medium',
              confidence === 'high' && 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300',
              confidence === 'medium' && 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300',
              confidence === 'low' && 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
            )}>
              {confidence}
            </span>
          </div>
        )}
      </div>

      {/* Content */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {title}
        </h3>
        
        <div className="flex items-baseline">
          <p 
            className={clsx(
              'text-3xl font-bold tabular-nums', // Consistent number width
              config.text
            )}
            data-testid="metric-value"
          >
            {value}
          </p>
          
          {subtitle && (
            <p className="ml-2 text-sm text-gray-600 dark:text-gray-400">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      {/* Interaction hint */}
      {onClick && (
        <div className="mt-4 text-xs text-gray-500 dark:text-gray-400 flex items-center">
          <span>Click to drill down</span>
          <span className="ml-1" aria-hidden="true">→</span>
        </div>
      )}
    </article>
  );
};

// Memoize to prevent unnecessary re-renders
export const MetricCard = memo(MetricCardComponent, (prev, next) => {
  // Custom comparison - only re-render if values actually changed
  return (
    prev.title === next.title &&
    prev.value === next.value &&
    prev.subtitle === next.subtitle &&
    prev.isLoading === next.isLoading &&
    prev.error === next.error &&
    prev.semantic === next.semantic &&
    prev.confidence === next.confidence
  );
});

MetricCard.displayName = 'MetricCard';

