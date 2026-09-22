import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success' | 'white' | 'dark' | 'outline-dark';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
  iconRight?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className = '',
      variant = 'primary',
      size = 'md',
      loading = false,
      disabled = false,
      icon,
      iconRight,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-semibold transition-all duration-200 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.97] select-none';

    const sizeStyles = {
      sm: 'px-3 py-1.5 text-xs gap-1.5',
      md: 'px-4 py-2.5 text-sm gap-2',
      lg: 'px-6 py-3.5 text-base gap-2.5',
    }[size];

    const variantStyles = {
      primary:
        'bg-brand-600 text-white hover:bg-brand-500 hover:text-white shadow-sm border border-brand-700/20 hover:shadow-glow-brand',
      secondary:
        'bg-brand-50 text-brand-700 hover:bg-brand-100/80 hover:text-brand-800 border border-brand-200/80 shadow-xs',
      outline:
        'bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900 border border-slate-200 shadow-xs hover:border-slate-300',
      ghost:
        'bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-transparent',
      danger:
        'bg-rose-600 text-white hover:bg-rose-700 hover:text-white shadow-xs border border-rose-700/20',
      success:
        'bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white shadow-xs border border-emerald-700/20',
      white:
        'bg-white text-navy-950 hover:bg-slate-100 hover:text-navy-900 border border-slate-200/80 shadow-elevated hover:shadow-subtle',
      dark:
        'bg-navy-800 text-white hover:bg-navy-700 hover:text-white border border-navy-700 shadow-xs hover:border-navy-600',
      'outline-dark':
        'bg-white/10 text-white hover:bg-white/20 hover:text-white border border-white/20 shadow-xs hover:border-white/30',
    }[variant];

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(baseStyles, sizeStyles, variantStyles, className)}
        {...props}
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin text-current" />}
        {!loading && icon}
        {children}
        {!loading && iconRight}
      </button>
    );
  }
);

Button.displayName = 'Button';
