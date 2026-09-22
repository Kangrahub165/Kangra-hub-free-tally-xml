'use client';

import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react';

/* ───── Types ───── */
export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

/* ───── Context ───── */
interface ToastContextValue {
  addToast: (toast: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Fallback for when used outside provider — silently no-op
    return {
      addToast: () => {},
      removeToast: () => {},
      toast: {
        success: (message: string, title?: string) => {},
        error: (message: string, title?: string) => {},
        warning: (message: string, title?: string) => {},
        info: (message: string, title?: string) => {},
      },
    };
  }
  return {
    addToast: ctx.addToast,
    removeToast: ctx.removeToast,
    toast: {
      success: (message: string, title?: string) => ctx.addToast({ type: 'success', message, title }),
      error: (message: string, title?: string) => ctx.addToast({ type: 'error', message, title }),
      warning: (message: string, title?: string) => ctx.addToast({ type: 'warning', message, title }),
      info: (message: string, title?: string) => ctx.addToast({ type: 'info', message, title }),
    },
  };
}

/* ───── Single Toast ───── */
function Toast({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const duration = item.duration ?? 4000;
    if (duration <= 0) return;
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onDismiss(item.id), 200);
    }, duration);
    return () => clearTimeout(timer);
  }, [item, onDismiss]);

  const handleDismiss = () => {
    setExiting(true);
    setTimeout(() => onDismiss(item.id), 200);
  };

  const config = {
    success: {
      icon: <CheckCircle2 className="w-4.5 h-4.5 text-emerald-500 flex-shrink-0" />,
      bg: 'bg-white border-emerald-200/80',
      accent: 'bg-emerald-500',
    },
    error: {
      icon: <AlertCircle className="w-4.5 h-4.5 text-rose-500 flex-shrink-0" />,
      bg: 'bg-white border-rose-200/80',
      accent: 'bg-rose-500',
    },
    warning: {
      icon: <AlertTriangle className="w-4.5 h-4.5 text-amber-500 flex-shrink-0" />,
      bg: 'bg-white border-amber-200/80',
      accent: 'bg-amber-500',
    },
    info: {
      icon: <Info className="w-4.5 h-4.5 text-brand-500 flex-shrink-0" />,
      bg: 'bg-white border-brand-200/80',
      accent: 'bg-brand-500',
    },
  }[item.type];

  return (
    <div
      role="alert"
      className={`relative overflow-hidden flex items-start gap-3 px-4 py-3.5 rounded-xl border shadow-elevated max-w-sm w-full ${config.bg} ${
        exiting ? 'animate-toast-out' : 'animate-toast-in'
      }`}
    >
      {/* Accent bar */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${config.accent} rounded-l-xl`} />
      <div className="pl-1 pt-0.5">{config.icon}</div>
      <div className="flex-1 min-w-0">
        {item.title && (
          <p className="text-sm font-semibold text-slate-900 leading-tight">{item.title}</p>
        )}
        <p className="text-xs text-slate-600 leading-relaxed mt-0.5">{item.message}</p>
      </div>
      <button
        onClick={handleDismiss}
        className="text-slate-400 hover:text-slate-600 p-0.5 rounded-lg hover:bg-slate-100 transition-colors flex-shrink-0"
        aria-label="Dismiss notification"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

/* ───── Toaster (Container) ───── */
export function Toaster({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev.slice(-4), { ...toast, id }]); // Max 5 visible
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      {/* Toast container */}
      {toasts.length > 0 && (
        <div
          className="fixed top-4 right-4 z-[100] flex flex-col gap-2.5 pointer-events-none sm:max-w-sm w-full sm:w-auto px-4 sm:px-0"
          aria-live="polite"
          aria-label="Notifications"
        >
          {toasts.map((item) => (
            <div key={item.id} className="pointer-events-auto">
              <Toast item={item} onDismiss={removeToast} />
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
