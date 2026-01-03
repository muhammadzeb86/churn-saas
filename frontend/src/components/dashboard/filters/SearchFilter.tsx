import React, { useState, useEffect } from 'react';
import { Search, X } from 'lucide-react';

interface SearchFilterProps {
  value: string;
  onChange: (query: string) => void;
  placeholder?: string;
}

export const SearchFilter: React.FC<SearchFilterProps> = ({
  value,
  onChange,
  placeholder = 'Search...'
}) => {
  // Local state for immediate UI feedback (before debounce)
  const [localValue, setLocalValue] = useState(value);
  
  // Sync local value with prop value
  useEffect(() => {
    setLocalValue(value);
  }, [value]);
  
  const handleChange = (newValue: string) => {
    setLocalValue(newValue);
    onChange(newValue);
  };
  
  const handleClear = () => {
    setLocalValue('');
    onChange('');
  };
  
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
      <input
        type="text"
        value={localValue}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-10 pr-10 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        aria-label="Search filter"
      />
      {localValue && (
        <button
          onClick={handleClear}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          aria-label="Clear search"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};

