import React from 'react';

export interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`p-12 sm:p-16 text-center space-y-3 max-w-md mx-auto ${className}`}>
      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center mx-auto mb-2 shadow-xs">
        {icon}
      </div>
      <h3 className="text-sm font-bold text-slate-800 tracking-tight">{title}</h3>
      <p className="text-xs text-slate-500 leading-relaxed max-w-sm mx-auto">{description}</p>
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}
