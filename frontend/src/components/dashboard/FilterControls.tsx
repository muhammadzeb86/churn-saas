import React, { useState, useMemo, useEffect } from 'react';
import { useFilters, filterPredictions, exportFilteredData, generateShareableUrl } from './hooks/useFilters';
import { exportToExcel, validateExportData } from '../../utils/excelExport';
import { RiskLevelFilter } from './filters/RiskLevelFilter';
import { DateRangeFilter } from './filters/DateRangeFilter';
import { SearchFilter } from './filters/SearchFilter';
import { X, Filter, Download, Share2, ChevronDown, ChevronUp, AlertTriangle, FileSpreadsheet, FileText } from 'lucide-react';
import type { Prediction } from '../../types';

interface FilterControlsProps {
  predictions: Prediction[];
  onFilteredDataChange: (filtered: Prediction[], metrics: any) => void;
  highRiskThreshold?: number;
  mediumRiskThreshold?: number;
}

// Simple toast notification
interface Toast {
  message: string;
  type: 'success' | 'error';
}

export const FilterControls: React.FC<FilterControlsProps> = ({
  predictions,
  onFilteredDataChange,
  highRiskThreshold = 0.7,
  mediumRiskThreshold = 0.4
}) => {
  const {
    filters,
    setRiskLevel,
    setDateRange,
    setSearchQuery,
    resetFilters,
    hasActiveFilters,
    thresholds,
    performanceWarnings
  } = useFilters({
    highRiskThreshold,
    mediumRiskThreshold
  });
  
  const [isExpanded, setIsExpanded] = useState(true);
  const [toast, setToast] = useState<Toast | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [isExporting, setIsExporting] = useState(false);
  
  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  
  // Apply filters with performance tracking
  const filteredResult = useMemo(() => {
    return filterPredictions(predictions, filters, thresholds);
  }, [predictions, filters, thresholds]);
  
  // Notify parent of filtered data changes
  useEffect(() => {
    onFilteredDataChange(filteredResult.items, filteredResult.metrics);
  }, [filteredResult, onFilteredDataChange]);
  
  // Export handler with Excel and CSV options
  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      setIsExporting(true);
      setExportProgress(0);
      
      const timestamp = new Date().toISOString().split('T')[0];
      const riskSuffix = filters.riskLevel !== 'all' ? `_${filters.riskLevel}` : '';
      const filename = `churn_predictions${riskSuffix}_${timestamp}`;
      
      if (format === 'excel') {
        // Validate first
        const validation = validateExportData(filteredResult.items);
        if (!validation.valid) {
          setToast({ message: validation.errors[0], type: 'error' });
          return;
        }
        
        // Export to Excel with progress
        const result = await exportToExcel({
          predictions: filteredResult.items,
          filename,
          includeSummary: true,
          maskingStrategy: 'partial', // GDPR compliance
          onProgress: (percent) => setExportProgress(percent),
          riskThresholds: thresholds,
          modelVersion: 'v2.1.4'
        });
        
        if (result.success) {
          setToast({ 
            message: `✅ Exported ${result.rowsExported} predictions to Excel`, 
            type: 'success' 
          });
        } else {
          setToast({ message: result.error || 'Export failed', type: 'error' });
        }
        
      } else {
        // Existing CSV export
        exportFilteredData(filteredResult.items, `${filename}.csv`);
        setToast({ 
          message: `Exported ${filteredResult.items.length} predictions to CSV`, 
          type: 'success' 
        });
      }
      
      setShowExportMenu(false);
      
    } catch (error) {
      console.error('Export failed:', error);
      setToast({ 
        message: error instanceof Error ? error.message : 'Export failed. Please try again.', 
        type: 'error' 
      });
    } finally {
      setIsExporting(false);
      setExportProgress(0);
    }
  };
  
  // Share handler
  const handleShare = () => {
    try {
      const shareUrl = generateShareableUrl(filters);
      
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(shareUrl).then(
          () => setToast({ message: 'Filter link copied to clipboard!', type: 'success' }),
          () => setToast({ message: 'Failed to copy link', type: 'error' })
        );
      } else {
        // Fallback for older browsers
        const tempInput = document.createElement('input');
        tempInput.value = shareUrl;
        document.body.appendChild(tempInput);
        tempInput.select();
        const success = document.execCommand('copy');
        document.body.removeChild(tempInput);
        
        setToast({
          message: success ? 'Filter link copied!' : 'Failed to copy link',
          type: success ? 'success' : 'error'
        });
      }
    } catch (error) {
      console.error('Share failed:', error);
      setToast({ message: 'Failed to generate share link', type: 'error' });
    }
  };
  
  const totalCount = predictions.length;
  const filteredCount = filteredResult.items.length;
  const filterPercentage = totalCount > 0 ? Math.round((filteredCount / totalCount) * 100) : 0;
  
  return (
    <>
      {/* Toast notification */}
      {toast && (
        <div 
          className={`fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in ${
            toast.type === 'success' 
              ? 'bg-green-500 text-white' 
              : 'bg-red-500 text-white'
          }`}
          role="alert"
        >
          {toast.message}
        </div>
      )}
      
      {/* Export progress bar */}
      {isExporting && exportProgress > 0 && (
        <div className="fixed top-16 right-4 w-80 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-4 z-50 animate-fade-in">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-700 dark:text-gray-300">Exporting to Excel...</span>
            <span className="font-semibold text-gray-900 dark:text-white">{exportProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${exportProgress}%` }}
              role="progressbar"
              aria-valuenow={exportProgress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
        </div>
      )}
      
      <div 
        className="bg-white dark:bg-gray-800 rounded-lg shadow-md mb-6 border border-gray-200 dark:border-gray-700"
        role="region"
        aria-label="Filter controls"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <Filter className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Filters
            </h3>
            
            {hasActiveFilters && (
              <span className="px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded-full">
                Active
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-3">
            {/* Results count */}
            <div className="text-sm text-gray-600 dark:text-gray-400">
              <span className="font-semibold text-gray-900 dark:text-white">
                {filteredCount.toLocaleString()}
              </span>
              {filteredCount !== totalCount && (
                <>
                  <span className="mx-1">of</span>
                  <span>{totalCount.toLocaleString()}</span>
                  <span className="ml-1 text-xs">({filterPercentage}%)</span>
                </>
              )}
            </div>
            
            {/* Action buttons */}
            <div className="flex items-center gap-1">
              {/* Export button with dropdown */}
              {filteredCount > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowExportMenu(!showExportMenu)}
                    disabled={isExporting}
                    className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    aria-haspopup="true"
                    aria-expanded={showExportMenu}
                    aria-label="Export predictions"
                  >
                    <Download className="w-4 h-4" />
                    <span className="hidden sm:inline">Export</span>
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  
                  {showExportMenu && (
                    <div 
                      className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-10"
                      role="menu"
                      aria-label="Export format options"
                    >
                      <button
                        onClick={() => handleExport('excel')}
                        disabled={isExporting}
                        className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-3 disabled:opacity-50 border-b border-gray-100 dark:border-gray-700"
                        role="menuitem"
                        tabIndex={0}
                      >
                        <FileSpreadsheet className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 dark:text-white">Export to Excel</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">Professional formatting (.xlsx)</div>
                        </div>
                      </button>
                      <button
                        onClick={() => handleExport('csv')}
                        disabled={isExporting}
                        className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-3 disabled:opacity-50"
                        role="menuitem"
                        tabIndex={0}
                      >
                        <FileText className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 dark:text-white">Export to CSV</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">Simple format (.csv)</div>
                        </div>
                      </button>
                    </div>
                  )}
                </div>
              )}
              
              {/* Share button */}
              {hasActiveFilters && (
                <button
                  onClick={handleShare}
                  className="p-2 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md transition-colors"
                  aria-label="Share filter link"
                  title="Copy filter link"
                >
                  <Share2 className="w-4 h-4" />
                </button>
              )}
              
              {/* Reset button */}
              {hasActiveFilters && (
                <button
                  onClick={resetFilters}
                  className="flex items-center gap-1 px-3 py-1 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                  aria-label="Clear all filters"
                >
                  <X className="w-4 h-4" />
                  <span className="hidden sm:inline">Clear</span>
                </button>
              )}
              
              {/* Expand/collapse toggle */}
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                aria-label={isExpanded ? 'Collapse filters' : 'Expand filters'}
                aria-expanded={isExpanded}
              >
                {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
        
        {/* Filter controls */}
        {isExpanded && (
          <div className="p-4 space-y-4">
            {/* Performance warnings display */}
            {performanceWarnings.length > 0 && (
              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-yellow-800 dark:text-yellow-300">
                    <p className="font-medium mb-1">Performance Warning:</p>
                    {performanceWarnings.map((warning, i) => (
                      <p key={i} className="text-xs">{warning}</p>
                    ))}
                  </div>
                </div>
              </div>
            )}
            
            {/* Risk Level Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Risk Level
              </label>
              <RiskLevelFilter
                value={filters.riskLevel}
                onChange={setRiskLevel}
              />
            </div>
            
            {/* Date Range Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Date Range
              </label>
              <DateRangeFilter
                value={filters.dateRange}
                customStartDate={filters.customStartDate}
                customEndDate={filters.customEndDate}
                onChange={setDateRange}
              />
            </div>
            
            {/* Search Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Search Customer
              </label>
              <SearchFilter
                value={filters.searchQuery}
                onChange={setSearchQuery}
                placeholder="Search by customer ID..."
              />
            </div>
          </div>
        )}
      </div>
    </>
  );
};

