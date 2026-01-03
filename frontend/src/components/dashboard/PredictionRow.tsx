import React from 'react';
import { Row, flexRender } from '@tanstack/react-table';
import { PredictionDetails } from './PredictionDetails';
import type { Prediction } from '../../types';

interface PredictionRowProps {
  row: Row<Prediction>;
  isExpanded: boolean;
}

export const PredictionRow: React.FC<PredictionRowProps> = ({ row, isExpanded }) => {
  return (
    <>
      <tr className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
        {row.getVisibleCells().map((cell) => (
          <td
            key={cell.id}
            className="px-4 py-3 text-sm"
            data-label={cell.column.columnDef.header as string}
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </td>
        ))}
      </tr>

      {isExpanded && (
        <tr>
          <td colSpan={row.getVisibleCells().length} className="px-4 py-0 bg-gray-50 dark:bg-gray-900/50">
            <div className="py-4">
              <PredictionDetails prediction={row.original} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

