import React from 'react';
import { AlertCircle, CheckCircle2, AlertTriangle, Info, X } from 'lucide-react';

export interface StatusAlertProps {
  type?: 'error' | 'warning' | 'success' | 'info';
  title?: string;
  message: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export function StatusAlert({
  type = 'info',
  title,
  message,
  onDismiss,
  className = '',
}: StatusAlertProps) {
  const styles = {
    error: 'bg-rose-50 border-rose-200/80 text-rose-800',
    warning: 'bg-amber-50 border-amber-200/80 text-amber-900',
    success: 'bg-emerald-50 border-emerald-200/80 text-emerald-800',
    info: 'bg-brand-50 border-brand-200/80 text-brand-900',
  }[type];

  const icons = {
    error: <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />,
    warning: <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />,
    success: <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />,
    info: <Info className="w-4 h-4 text-brand-600 flex-shrink-0 mt-0.5" />,
  }[type];

  return (
    <div
      role="alert"
      className={`p-4 rounded-xl border flex items-start gap-3 text-xs leading-relaxed shadow-xs ${styles} ${className}`}
    >
      {icons}
      <div className="flex-1">
        {title && <h4 className="font-bold mb-0.5">{title}</h4>}
        <div className="text-[12px]">{message}</div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-700 p-1 -mr-1 -mt-1 rounded-lg transition-colors"
          aria-label="Dismiss alert"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
