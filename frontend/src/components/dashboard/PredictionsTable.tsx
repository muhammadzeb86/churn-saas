import React, { useMemo, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  SortingState,
} from '@tanstack/react-table';
import { PredictionRow } from './PredictionRow';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { useTableURLState } from '../../hooks/useTableURLState';
import { validatePrediction } from '../../utils/validationUtils';
import type { Prediction } from '../../types';

interface PredictionsTableProps {
  predictions: Prediction[];
  isLoading?: boolean;
  error?: Error | null;
}

const DEFAULT_PAGE_SIZE = 25;

const columnHelper = createColumnHelper<Prediction>();

export const PredictionsTable: React.FC<PredictionsTableProps> = ({
  predictions,
  isLoading = false,
  error = null
}) => {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'churn_probability', desc: true }
  ]);
  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: DEFAULT_PAGE_SIZE,
  });

  // Validate predictions
  const validPredictions = useMemo(() => {
    return predictions.filter(validatePrediction);
  }, [predictions]);

  // Define columns
  const columns = useMemo(
    () => [
      columnHelper.display({
        id: 'expander',
        size: 48,
        cell: (info) => {
          const id = info.row.original.id;
          const isExpanded = expandedRows.has(id);
          return (
            <button
              onClick={() => {
                setExpandedRows((prev) => {
                  const newSet = new Set(prev);
                  if (newSet.has(id)) {
                    newSet.delete(id);
                  } else {
                    newSet.add(id);
                  }
                  return newSet;
                });
              }}
              className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              {isExpanded ? '▼' : '▶'}
            </button>
          );
        },
        enableSorting: false,
      }),
      columnHelper.accessor('customer_id', {
        header: 'Customer ID',
        cell: (info) => (
          <span className="font-medium text-gray-900 dark:text-white">
            {info.getValue() || info.row.original.id.substring(0, 8)}
          </span>
        ),
      }),
      columnHelper.accessor('churn_probability', {
        header: 'Churn Risk',
        cell: (info) => {
          const value = info.getValue();
          const percentage = (value * 100).toFixed(1);
          const colorClass =
            value >= 0.7
              ? 'text-red-600 dark:text-red-400 font-semibold'
              : value >= 0.4
              ? 'text-yellow-600 dark:text-yellow-400 font-medium'
              : 'text-green-600 dark:text-green-400 font-semibold';
          return <span className={`tabular-nums ${colorClass}`}>{percentage}%</span>;
        },
      }),
      columnHelper.accessor('retention_probability', {
        header: 'Retention',
        cell: (info) => {
          const value = info.getValue();
          const percentage = (value * 100).toFixed(1);
          const colorClass =
            value >= 0.7
              ? 'text-green-600 dark:text-green-400 font-semibold'
              : value >= 0.4
              ? 'text-yellow-600 dark:text-yellow-400 font-medium'
              : 'text-red-600 dark:text-red-400 font-semibold';
          return <span className={`tabular-nums ${colorClass}`}>{percentage}%</span>;
        },
      }),
      columnHelper.accessor('churn_probability', {
        id: 'risk_level',
        header: 'Risk Level',
        cell: (info) => {
          const value = info.getValue();
          let level: string;
          let bgColor: string;
          let textColor: string;

          if (value >= 0.7) {
            level = 'HIGH';
            bgColor = 'bg-red-100 dark:bg-red-900/30';
            textColor = 'text-red-800 dark:text-red-300';
          } else if (value >= 0.4) {
            level = 'MEDIUM';
            bgColor = 'bg-yellow-100 dark:bg-yellow-900/30';
            textColor = 'text-yellow-800 dark:text-yellow-300';
          } else {
            level = 'LOW';
            bgColor = 'bg-green-100 dark:bg-green-900/30';
            textColor = 'text-green-800 dark:text-green-300';
          }

          return (
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor} ${textColor}`}
            >
              {level}
            </span>
          );
        },
        enableSorting: false,
      }),
      columnHelper.accessor('created_at', {
        header: 'Date',
        cell: (info) => {
          const date = new Date(info.getValue());
          return (
            <span className="text-gray-600 dark:text-gray-400">
              {date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })}
            </span>
          );
        },
      }),
    ],
    [expandedRows]
  );

  const table = useReactTable({
    data: validPredictions,
    columns,
    state: {
      sorting,
      pagination,
    },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: false,
  });

  // Persist table state to URL
  useTableURLState(
    {
      pageIndex: pagination.pageIndex,
      pageSize: pagination.pageSize,
      sortBy: sorting,
    },
    (newState) => {
      if (newState.pageIndex !== undefined) {
        setPagination((prev) => ({ ...prev, pageIndex: newState.pageIndex! }));
      }
      if (newState.pageSize !== undefined) {
        setPagination((prev) => ({ ...prev, pageSize: newState.pageSize! }));
      }
      if (newState.sortBy !== undefined) {
        setSorting(newState.sortBy);
      }
    }
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-100 dark:bg-gray-700/50 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-8">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400 font-semibold mb-2">
            Failed to load predictions
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{error.message}</p>
        </div>
      </div>
    );
  }

  // Empty state
  if (!validPredictions.length) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-12 text-center">
        <div className="text-gray-400 dark:text-gray-500 text-6xl mb-4">📊</div>
        <h3 className="text-xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
          No predictions yet
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Upload a CSV file to start analyzing customer churn risk.
        </p>
      </div>
    );
  }

  // Calculate range for display
  const startItem = pagination.pageIndex * pagination.pageSize + 1;
  const endItem = Math.min((pagination.pageIndex + 1) * pagination.pageSize, validPredictions.length);
  const pageCount = table.getPageCount();

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md mb-6 predictions-table-container">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white">Predictions</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {validPredictions.length.toLocaleString()} total predictions
            </p>
          </div>

          {/* Page size selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">Show:</span>
            <select
              value={table.getState().pagination.pageSize}
              onChange={(e) => {
                table.setPageSize(Number(e.target.value));
              }}
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Rows per page"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full predictions-table">
          <thead className="bg-gray-50 dark:bg-gray-700/50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={`px-4 py-3 text-left text-xs font-medium text-gray-700 dark:text-gray-300 uppercase tracking-wider ${
                      header.column.getCanSort()
                        ? 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors'
                        : ''
                    }`}
                    onClick={header.column.getToggleSortingHandler()}
                    data-label={flexRender(header.column.columnDef.header, header.getContext())}
                  >
                    <div className="flex items-center gap-2">
                      <span>
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </span>
                      {header.column.getCanSort() && (
                        <span className="inline-block">
                          {header.column.getIsSorted() ? (
                            header.column.getIsSorted() === 'desc' ? (
                              <ArrowDown className="w-4 h-4" />
                            ) : (
                              <ArrowUp className="w-4 h-4" />
                            )
                          ) : (
                            <ArrowUpDown className="w-4 h-4 opacity-40" />
                          )}
                        </span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {table.getRowModel().rows.map((row) => {
              const isExpanded = expandedRows.has(row.original.id);
              return (
                <PredictionRow
                  key={row.id}
                  row={row}
                  isExpanded={isExpanded}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pageCount > 1 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Results info */}
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Showing <span className="font-semibold text-gray-900 dark:text-white">{startItem}</span> to{' '}
              <span className="font-semibold text-gray-900 dark:text-white">{endItem}</span> of{' '}
              <span className="font-semibold text-gray-900 dark:text-white">
                {validPredictions.length.toLocaleString()}
              </span>{' '}
              results
            </div>

            {/* Pagination controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => table.setPageIndex(0)}
                disabled={!table.getCanPreviousPage()}
                className="px-3 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Go to first page"
              >
                First
              </button>
              <button
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
                className="px-3 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Go to previous page"
              >
                Previous
              </button>
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Page <span className="font-semibold">{pagination.pageIndex + 1}</span> of{' '}
                <span className="font-semibold">{pageCount}</span>
              </span>
              <button
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
                className="px-3 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Go to next page"
              >
                Next
              </button>
              <button
                onClick={() => table.setPageIndex(pageCount - 1)}
                disabled={!table.getCanNextPage()}
                className="px-3 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Go to last page"
              >
                Last
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

