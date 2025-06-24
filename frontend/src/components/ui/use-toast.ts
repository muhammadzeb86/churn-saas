import { useState, useCallback } from 'react';

interface ToastOptions {
  variant?: 'default' | 'destructive';
  title?: string;
  description: string;
}

interface Toast extends ToastOptions {
  id: number;
}

export const useToast = () => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback(({ variant = 'default', title, description }: ToastOptions) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, variant, title, description }]);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  return { toast, toasts };
}; 