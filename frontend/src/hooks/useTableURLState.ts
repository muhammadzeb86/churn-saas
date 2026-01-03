import { useSearchParams } from 'react-router-dom';
import { useEffect } from 'react';

interface TableURLState {
  pageIndex: number;
  pageSize: number;
  sortBy: Array<{ id: string; desc: boolean }>;
}

/**
 * Persist table state to URL for shareability and browser back/forward
 */
export const useTableURLState = (
  state: TableURLState,
  setState: (newState: Partial<TableURLState>) => void
) => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Load state from URL on mount
  useEffect(() => {
    const page = searchParams.get('page');
    const size = searchParams.get('size');
    const sortField = searchParams.get('sort');
    const sortOrder = searchParams.get('order');

    const newState: Partial<TableURLState> = {};

    if (page) {
      const pageNum = parseInt(page, 10);
      if (!isNaN(pageNum) && pageNum > 0) {
        newState.pageIndex = pageNum - 1; // 0-indexed internally
      }
    }

    if (size) {
      const sizeNum = parseInt(size, 10);
      if (!isNaN(sizeNum) && [10, 25, 50, 100].includes(sizeNum)) {
        newState.pageSize = sizeNum;
      }
    }

    if (sortField) {
      newState.sortBy = [{
        id: sortField,
        desc: sortOrder === 'desc'
      }];
    }

    if (Object.keys(newState).length > 0) {
      setState(newState);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only on mount

  // Save state to URL when it changes
  useEffect(() => {
    const params = new URLSearchParams(searchParams);

    // Page (1-indexed for users)
    params.set('page', (state.pageIndex + 1).toString());

    // Page size
    params.set('size', state.pageSize.toString());

    // Sorting
    if (state.sortBy.length > 0) {
      params.set('sort', state.sortBy[0].id);
      params.set('order', state.sortBy[0].desc ? 'desc' : 'asc');
    } else {
      params.delete('sort');
      params.delete('order');
    }

    setSearchParams(params, { replace: true }); // Don't create history entries
  }, [state.pageIndex, state.pageSize, state.sortBy, searchParams, setSearchParams]);
};

