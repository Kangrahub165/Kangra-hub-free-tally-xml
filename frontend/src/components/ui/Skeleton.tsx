import React from 'react';

export interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular' | 'rounded';
  width?: string | number;
  height?: string | number;
  lines?: number;
}

export function Skeleton({
  className = '',
  variant = 'text',
  width,
  height,
  lines = 1,
}: SkeletonProps) {
  const baseClasses = 'skeleton';

  const variantClasses = {
    text: 'h-4 rounded',
    circular: 'rounded-full',
    rectangular: 'rounded-none',
    rounded: 'rounded-xl',
  }[variant];

  const style: React.CSSProperties = {};
  if (width) style.width = typeof width === 'number' ? `${width}px` : width;
  if (height) style.height = typeof height === 'number' ? `${height}px` : height;

  if (variant === 'text' && lines > 1) {
    return (
      <div className={`space-y-2.5 ${className}`}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`${baseClasses} h-4 rounded`}
            style={{
              ...style,
              width: i === lines - 1 ? '75%' : style.width || '100%',
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`${baseClasses} ${variantClasses} ${className}`}
      style={style}
    />
  );
}

/* Preset skeleton compositions for common use cases */

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200/90 p-6 space-y-4 ${className}`}>
      <div className="flex items-center gap-3">
        <Skeleton variant="circular" width={40} height={40} />
        <div className="flex-1 space-y-2">
          <Skeleton width="60%" />
          <Skeleton width="40%" />
        </div>
      </div>
      <Skeleton variant="text" lines={3} />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4, className = '' }: { rows?: number; cols?: number; className?: string }) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200/90 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="bg-slate-50/90 border-b border-slate-200 px-4 py-3.5 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} width={`${Math.random() * 40 + 60}px`} height={12} />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="px-4 py-3 flex gap-4 border-b border-slate-100 last:border-0">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} width={`${Math.random() * 50 + 50}px`} height={14} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonMetricCard({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200/90 p-6 space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <Skeleton width="40%" height={12} />
        <Skeleton variant="rounded" width={36} height={36} />
      </div>
      <Skeleton width="60%" height={28} />
      <Skeleton width="80%" height={8} variant="rounded" />
    </div>
  );
}
