'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Maximize2, Minimize2, X, AlertTriangle } from 'lucide-react';
import { Button } from './Button';

export interface MasterModalShellProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: string;
  badge?: React.ReactNode;
  headerAction?: React.ReactNode;
  children: React.ReactNode;
  footer: React.ReactNode;
  onSaveShortcut?: () => void;
  isDirty?: boolean;
  isSubmitting?: boolean;
  tipText?: string;
}

export const MasterModalShell: React.FC<MasterModalShellProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  badge,
  headerAction,
  children,
  footer,
  onSaveShortcut,
  isDirty = false,
  isSubmitting = false,
  tipText,
}) => {
  const [mounted, setMounted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const shellRef = useRef<HTMLDivElement>(null);
  const triggerButtonRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setMounted(true);
    // Restore fullscreen preference from localStorage
    try {
      const saved = localStorage.getItem('kh_master_modal_fullscreen');
      if (saved === 'true') {
        setIsFullscreen(true);
      }
    } catch {}
  }, []);

  // Track previously focused element to return focus on close
  useEffect(() => {
    if (isOpen) {
      triggerButtonRef.current = document.activeElement as HTMLElement;
      setShowDiscardConfirm(false);
    } else if (triggerButtonRef.current) {
      try {
        triggerButtonRef.current.focus();
      } catch {}
    }
  }, [isOpen]);

  const toggleFullscreen = () => {
    setIsFullscreen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('kh_master_modal_fullscreen', next ? 'true' : 'false');
      } catch {}
      return next;
    });
  };

  const handleRequestClose = useCallback(() => {
    if (isDirty) {
      setShowDiscardConfirm(true);
    } else {
      onClose();
    }
  }, [isDirty, onClose]);

  // Global Keyboard listener for Ctrl+A and Esc inside the modal window
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // 1. Ctrl+A or Cmd+A -> Save
      const isSave = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a';
      if (isSave) {
        e.preventDefault();
        e.stopPropagation();
        if (!isSubmitting && onSaveShortcut) {
          onSaveShortcut();
        }
        return;
      }

      // 2. Escape -> Close / Discard confirmation
      if (e.key === 'Escape') {
        // If discard confirmation is open, close confirmation
        if (showDiscardConfirm) {
          e.preventDefault();
          e.stopPropagation();
          setShowDiscardConfirm(false);
          return;
        }

        // Check if an open portal dropdown is currently handling Escape
        const openDropdown = document.querySelector('[data-portal-dropdown-open="true"]');
        if (openDropdown) {
          // Let the portal dropdown close first
          return;
        }

        e.preventDefault();
        e.stopPropagation();
        handleRequestClose();
      }
    };

    // Attach to window with capture so Ctrl+A is intercepted everywhere inside modal inputs
    window.addEventListener('keydown', handleKeyDown, true);
    return () => {
      window.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [isOpen, isSubmitting, onSaveShortcut, showDiscardConfirm, handleRequestClose]);

  // Lock body scroll while modal is active
  useEffect(() => {
    if (isOpen) {
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = prevOverflow;
      };
    }
  }, [isOpen]);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-0 md:p-3"
      role="dialog"
      aria-modal="true"
    >
      {/* Dimmed backdrop - PRD §1.6: clicking dimmed background does NOT close */}
      <div
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-xs transition-opacity duration-200"
        aria-hidden="true"
        onClick={(e) => {
          e.stopPropagation();
          // Intentional: Background click does NOT close modal
        }}
      />

      {/* Main Master Window Container */}
      <div
        ref={shellRef}
        className={`relative z-10 flex flex-col bg-white text-slate-900 shadow-2xl transition-all duration-200 outline-none ${
          isFullscreen
            ? 'w-screen h-screen max-w-none max-h-none rounded-none'
            : 'w-full md:w-[min(1200px,94vw)] h-full md:h-[min(90vh,860px)] md:rounded-2xl border border-slate-200 overflow-hidden'
        }`}
        style={{
          minWidth: isFullscreen ? undefined : 'min(100%, 1024px)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky Fixed Header - Fixed at top, never scrolled away */}
        <header className="flex-none flex items-center justify-between px-5 py-3.5 bg-slate-50 border-b border-slate-200 select-none">
          <div className="flex items-center gap-3 min-w-0 pr-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="text-sm md:text-base font-bold text-slate-900 tracking-tight flex items-center gap-2 truncate">
                  {title}
                </div>
                {badge && <div className="shrink-0">{badge}</div>}
              </div>
              {subtitle && (
                <p className="text-[11px] text-slate-500 font-normal truncate mt-0.5">
                  {subtitle}
                </p>
              )}
            </div>
          </div>

          {/* Header Controls: Actions, Fullscreen Toggle, Close ✕ */}
          <div className="flex items-center gap-1.5 shrink-0">
            {headerAction}
            <button
              type="button"
              onClick={toggleFullscreen}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200/70 transition-colors"
              title={isFullscreen ? 'Restore standard size' : 'Expand to full screen (100vw × 100vh)'}
              aria-label={isFullscreen ? 'Restore' : 'Full screen'}
            >
              {isFullscreen ? (
                <Minimize2 className="w-4 h-4 text-slate-700" />
              ) : (
                <Maximize2 className="w-4 h-4 text-slate-700" />
              )}
            </button>
            <button
              type="button"
              onClick={handleRequestClose}
              className="p-1.5 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors ml-1"
              title="Close window (Esc)"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Scrollable Body - 2 Columns on desktop (5fr : 7fr), stacks below 900px */}
        <div className="flex-1 min-h-0 overflow-x-hidden overflow-y-auto bg-slate-50/30">
          {tipText && (
            <div className="px-5 pt-2 pb-0">
              <div className="text-[11px] text-emerald-800 bg-emerald-50/90 border border-emerald-200/80 px-3 py-1 rounded-lg flex items-center justify-between">
                <span>{tipText}</span>
                <span className="font-mono text-[10px] text-emerald-700 font-semibold">Tally Shortcut: Ctrl+A</span>
              </div>
            </div>
          )}
          <div className="p-4 md:p-5">
            {children}
          </div>
        </div>

        {/* Sticky Fixed Footer - Always visible, never scrolled away */}
        <footer className="flex-none px-5 py-3 bg-white border-t border-slate-200 shadow-xs">
          {footer}
        </footer>
      </div>

      {/* Discard Confirmation Modal (if dirty on Esc or ✕) */}
      {showDiscardConfirm && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
          <div
            className="w-full max-w-md bg-white rounded-xl shadow-2xl border border-slate-200 p-5 space-y-4 animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3 text-slate-900">
              <div className="w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center shrink-0 text-amber-700">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Discard unsaved changes?</h3>
                <p className="text-xs text-slate-500 mt-1">
                  You have unsaved changes in this master. If you close now, your edits will be discarded.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={() => setShowDiscardConfirm(false)}
                className="text-xs font-semibold"
              >
                Keep Editing
              </Button>
              <Button
                variant="danger"
                size="sm"
                type="button"
                onClick={() => {
                  setShowDiscardConfirm(false);
                  onClose();
                }}
                className="text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white"
              >
                Discard Changes
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>,
    document.body
  );
};
