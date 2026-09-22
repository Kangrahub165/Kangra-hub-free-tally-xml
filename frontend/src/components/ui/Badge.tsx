import React from 'react';
import { cn } from '@/lib/utils';

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
    sm: 'text-[11px] px-2.5 py-0.5 font-bold gap-1.5',
    md: 'text-xs px-3 py-1 font-extrabold gap-2',
  }[size];

  const variantStyles = {
    neutral: 'bg-slate-50 text-slate-700 ring-1 ring-inset ring-slate-200 border-transparent',
    primary: 'bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200 border-transparent',
    success: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200 border-transparent',
    warning: 'bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-200 border-transparent',
    danger: 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-200 border-transparent',
    purple: 'bg-purple-50 text-purple-700 ring-1 ring-inset ring-purple-200 border-transparent',
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
      className={cn(
        'inline-flex items-center rounded-full border shadow-xs select-none transition-colors',
        sizeStyles,
        variantStyles,
        className
      )}
      {...props}
    >
      {pulse && (
        <span className={`w-1.5 h-1.5 rounded-full ${pulseColors} animate-pulse`} />
      )}
      {children}
    </span>
  );
}
