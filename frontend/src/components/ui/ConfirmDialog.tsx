'use client';

import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, AlertCircle, Info, Trash2, X, RefreshCw } from 'lucide-react';
import { Button } from './Button';
import { cn } from '@/lib/utils';

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  message: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'primary' | 'info';
  icon?: React.ReactNode;
  confirmIcon?: React.ReactNode;
  loading?: boolean;
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'warning',
  icon,
  confirmIcon,
  loading = false,
}: ConfirmDialogProps) {
  const [mounted, setMounted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !loading && !isSubmitting) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose, loading, isSubmitting]);

  if (!isOpen || !mounted) return null;

  const handleConfirm = async () => {
    try {
      setIsSubmitting(true);
      await onConfirm();
    } finally {
      setIsSubmitting(false);
    }
  };

  const getVariantStyles = () => {
    switch (variant) {
      case 'danger':
        return {
          iconBg: 'bg-rose-50 text-rose-600 border border-rose-200 shadow-xs',
          defaultIcon: <Trash2 className="w-5 h-5" />,
          buttonVariant: 'danger' as const,
        };
      case 'warning':
        return {
          iconBg: 'bg-amber-50 text-amber-600 border border-amber-200 shadow-xs',
          defaultIcon: <AlertTriangle className="w-5 h-5" />,
          buttonVariant: 'primary' as const,
          customConfirmClass: 'bg-amber-600 hover:bg-amber-700 text-white border-amber-700/20',
        };
      case 'info':
        return {
          iconBg: 'bg-blue-50 text-blue-600 border border-blue-200 shadow-xs',
          defaultIcon: <Info className="w-5 h-5" />,
          buttonVariant: 'primary' as const,
        };
      case 'primary':
      default:
        return {
          iconBg: 'bg-brand-50 text-brand-600 border border-brand-200 shadow-xs',
          defaultIcon: <AlertCircle className="w-5 h-5" />,
          buttonVariant: 'primary' as const,
        };
    }
  };

  const styleConfig = getVariantStyles();
  const isLoading = loading || isSubmitting;

  const dialogContent = (
    <div className="fixed inset-0 z-[110] overflow-y-auto">
      {/* Backdrop overlay with blur */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity animate-fadeIn"
        onClick={() => {
          if (!isLoading) onClose();
        }}
        aria-hidden="true"
      />

      {/* Center alignment container */}
      <div className="flex min-h-full items-center justify-center p-4 sm:p-6 pointer-events-none">
        {/* Modal Dialog Card */}
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-dialog-title"
          aria-describedby="confirm-dialog-description"
          className={cn(
            'relative w-full max-w-md my-auto bg-white rounded-2xl sm:rounded-3xl shadow-2xl border border-slate-200 z-10 animate-slideUp overflow-hidden pointer-events-auto text-left p-6 sm:p-7'
          )}
        >
          {/* Close button */}
          <button
            onClick={onClose}
            disabled={isLoading}
            className="absolute top-4.5 right-4.5 text-slate-400 hover:text-slate-600 p-1.5 rounded-xl hover:bg-slate-100 transition-colors disabled:opacity-40"
            aria-label="Close dialog"
          >
            <X className="w-4.5 h-4.5" />
          </button>

          <div className="flex items-start gap-4 sm:gap-4.5">
            {/* Action Icon */}
            <div className={cn('w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0 mt-0.5', styleConfig.iconBg)}>
              {icon || styleConfig.defaultIcon}
            </div>

            {/* Title & Description */}
            <div className="flex-1 min-w-0 pr-4">
              <h3 id="confirm-dialog-title" className="text-base sm:text-lg font-black text-slate-900 tracking-tight">
                {title}
              </h3>
              <div id="confirm-dialog-description" className="mt-2 text-xs sm:text-sm text-slate-600 leading-relaxed font-medium">
                {message}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="mt-6 pt-5 border-t border-slate-100 flex flex-col-reverse sm:flex-row items-center justify-end gap-2.5 sm:gap-3">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={onClose}
              disabled={isLoading}
              className="w-full sm:w-auto font-bold text-slate-700"
            >
              {cancelText}
            </Button>
            <Button
              type="button"
              variant={styleConfig.buttonVariant}
              size="md"
              loading={isLoading}
              onClick={handleConfirm}
              icon={confirmIcon}
              className={cn('w-full sm:w-auto font-bold px-5 shadow-sm', styleConfig.customConfirmClass)}
            >
              {confirmText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(dialogContent, document.body);
}
