'use client';

import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl';
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl';
  className?: string;
}

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth,
  size,
  className = '',
}: ModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
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
  }, [isOpen, onClose]);

  if (!isOpen || !mounted) return null;

  const widthKey = size || maxWidth || 'md';
  const maxWidthStyles = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '3xl': 'max-w-3xl',
    '4xl': 'max-w-4xl',
    '5xl': 'max-w-5xl',
  }[widthKey] || 'max-w-lg';

  const modalContent = (
    <div className="fixed inset-0 z-[100] overflow-y-auto">
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-navy-950/70 backdrop-blur-sm transition-opacity animate-fadeIn"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Centering wrapper with full viewport accessibility on all devices */}
      <div className="flex min-h-full items-center justify-center p-3 sm:p-4 md:p-6 pointer-events-none">
        {/* Modal Dialog Card */}
        <div
          role="dialog"
          aria-modal="true"
          className={cn(
            'relative w-full my-auto flex flex-col bg-white rounded-2xl sm:rounded-3xl shadow-modal border border-slate-200 z-10 animate-slideUp overflow-hidden pointer-events-auto text-left',
            'max-h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-3.5rem)]',
            maxWidthStyles,
            className
          )}
        >
          {/* Header */}
          <div className="flex items-start justify-between px-4 py-3.5 sm:px-6 sm:py-4.5 border-b border-slate-100 flex-shrink-0 bg-white">
            <div className="pr-4 sm:pr-6 min-w-0">
              {title && (
                <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight truncate">
                  {title}
                </h2>
              )}
              {description && (
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed line-clamp-2 sm:line-clamp-none">
                  {description}
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 p-1.5 rounded-xl hover:bg-slate-100 transition-colors flex-shrink-0 ml-auto"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Scrollable Content Body */}
          <div className="overflow-y-auto p-4 sm:p-6 flex-1 overscroll-contain">
            {children}
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
