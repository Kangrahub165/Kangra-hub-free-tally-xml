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
    <div className={`p-12 sm:p-16 text-center space-y-3 max-w-md mx-auto relative ${className}`}>
      <div className="absolute inset-0 bg-slate-50/50 bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:16px_16px] rounded-3xl -z-10" />
      <div className="w-14 h-14 rounded-2xl bg-white border border-slate-100 text-brand-600 flex items-center justify-center mx-auto mb-4 shadow-card">
        {icon}
      </div>
      <h3 className="text-sm font-bold text-slate-800 tracking-tight">{title}</h3>
      <p className="text-xs text-slate-500 leading-relaxed max-w-sm mx-auto">{description}</p>
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}
