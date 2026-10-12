import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastContextType {
  showToast: (toast: Omit<ToastItem, 'id'>) => void;
  success: (message: string, title?: string) => void;
  error: (message: string, title?: string) => void;
  warning: (message: string, title?: string) => void;
  info: (message: string, title?: string) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    ({ type, title, message, duration = 3000 }: Omit<ToastItem, 'id'>) => {
      const id = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newToast: ToastItem = { id, type, title, message, duration };

      setToasts((prev) => [...prev, newToast]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  const success = useCallback((message: string, title?: string) => {
    showToast({ type: 'success', title: title || 'Thành công', message, duration: 3000 });
  }, [showToast]);

  const error = useCallback((message: string, title?: string) => {
    showToast({ type: 'error', title: title || 'Thông báo lỗi', message, duration: 3500 });
  }, [showToast]);

  const warning = useCallback((message: string, title?: string) => {
    showToast({ type: 'warning', title: title || 'Cảnh báo', message, duration: 3000 });
  }, [showToast]);

  const info = useCallback((message: string, title?: string) => {
    showToast({ type: 'info', title: title || 'Thông tin', message, duration: 3000 });
  }, [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, success, error, warning, info, removeToast }}>
      {children}
      
      {/* Toast Notification Container (Top-Right Rectangular Toasts) */}
      <div 
        className="fixed top-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none"
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <ToastCard key={toast.id} toast={toast} onDismiss={() => removeToast(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const duration = toast.duration || 3000;

  const config = {
    success: {
      border: 'border-accent-emerald/40',
      bgIcon: 'bg-accent-emerald/15 text-accent-emerald',
      progressBar: 'bg-accent-emerald',
      icon: CheckCircle2,
      defaultTitle: 'Thành công',
    },
    error: {
      border: 'border-accent-rose/40',
      bgIcon: 'bg-accent-rose/15 text-accent-rose',
      progressBar: 'bg-accent-rose',
      icon: AlertCircle,
      defaultTitle: 'Thông báo lỗi',
    },
    warning: {
      border: 'border-amber-500/40',
      bgIcon: 'bg-amber-500/15 text-amber-500',
      progressBar: 'bg-amber-500',
      icon: AlertTriangle,
      defaultTitle: 'Cảnh báo',
    },
    info: {
      border: 'border-blue-500/40',
      bgIcon: 'bg-blue-500/15 text-blue-500',
      progressBar: 'bg-blue-500',
      icon: Info,
      defaultTitle: 'Thông tin',
    },
  }[toast.type];

  const IconComponent = config.icon;

  return (
    <div
      className={`pointer-events-auto relative overflow-hidden rounded-xl border ${config.border} bg-surface-container-lowest/95 backdrop-blur-md shadow-xl p-3.5 transition-all duration-300 animate-slide-left`}
      style={{
        animation: 'toastSlideIn 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards'
      }}
    >
      <div className="flex items-start gap-3">
        <div className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${config.bgIcon}`}>
          <IconComponent className="w-4 h-4" />
        </div>

        <div className="flex-1 min-w-0 pr-2">
          <h5 className="text-xs font-bold text-text-primary tracking-tight leading-snug">
            {toast.title || config.defaultTitle}
          </h5>
          <p className="text-[11px] text-text-secondary mt-0.5 leading-relaxed break-words">
            {toast.message}
          </p>
        </div>

        <button
          onClick={onDismiss}
          className="shrink-0 p-1 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-container transition-colors cursor-pointer"
          title="Đóng thông báo"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Progress Bar counting down the duration */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-surface-container overflow-hidden">
        <div
          className={`h-full ${config.progressBar}`}
          style={{
            animation: `toastProgress ${duration}ms linear forwards`,
          }}
        />
      </div>
    </div>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
