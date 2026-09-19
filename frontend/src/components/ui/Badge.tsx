import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'purple';
  size?: 'sm' | 'md';
  pulse?: boolean;
}

export function Badge({
  children,
  className = '',
  variant = 'neutral',
  size = 'sm',
  pulse = false,
  ...props
}: BadgeProps) {
  const sizeStyles = {
    sm: 'text-[11px] px-2.5 py-0.5 font-semibold gap-1.5',
    md: 'text-xs px-3 py-1 font-bold gap-2',
  }[size];

  const variantStyles = {
    neutral: 'bg-slate-100 text-slate-700 border-slate-200/80',
    primary: 'bg-brand-50 text-brand-700 border-brand-200',
    success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    warning: 'bg-amber-50 text-amber-800 border-amber-200',
    danger: 'bg-rose-50 text-rose-700 border-rose-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
  }[variant];

  const pulseColors = {
    neutral: 'bg-slate-400',
    primary: 'bg-brand-500',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-rose-500',
    purple: 'bg-purple-500',
  }[variant];

  return (
    <span
      className={`inline-flex items-center rounded-full border shadow-xs select-none transition-colors ${sizeStyles} ${variantStyles} ${className}`}
      {...props}
    >
      {pulse && (
        <span className={`w-1.5 h-1.5 rounded-full ${pulseColors} animate-pulse`} />
      )}
      {children}
    </span>
  );
}
