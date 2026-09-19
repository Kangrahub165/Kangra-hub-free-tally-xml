import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success';
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
      'inline-flex items-center justify-center font-semibold transition-all duration-150 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98] select-none';

    const sizeStyles = {
      sm: 'px-3 py-1.5 text-xs gap-1.5',
      md: 'px-4 py-2.5 text-sm gap-2',
      lg: 'px-6 py-3.5 text-base gap-2.5',
    }[size];

    const variantStyles = {
      primary:
        'bg-slate-900 text-white hover:bg-slate-800 shadow-sm border border-slate-900/10 hover:shadow',
      secondary:
        'bg-brand-50 text-brand-700 hover:bg-brand-100/80 border border-brand-200/80 shadow-xs',
      outline:
        'bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 shadow-xs hover:border-slate-300',
      ghost:
        'bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-transparent',
      danger:
        'bg-rose-600 text-white hover:bg-rose-700 shadow-xs border border-rose-700/20',
      success:
        'bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs border border-emerald-700/20',
    }[variant];

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
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
