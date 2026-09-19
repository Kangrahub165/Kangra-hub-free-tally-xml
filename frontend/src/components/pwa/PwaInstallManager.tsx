'use client';

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { Download, Sparkles, X, Smartphone } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { getAuthToken } from '@/lib/api';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

export function PwaInstallManager({ 
  mode = 'USER', 
  isAdminAuthenticated = false 
}: { 
  mode?: 'USER' | 'ADMIN'; 
  isAdminAuthenticated?: boolean;
}) {
  const pathname = usePathname();
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandalone, setIsStandalone] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Register Service Worker for PWA compliance
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch((err) => {
        console.warn('SW registration warning:', err);
      });
    }

    // Check if running as installed standalone PWA
    const isStandaloneMode = 
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true;
    setIsStandalone(isStandaloneMode);

    // Standalone launch authentication gating:
    if (isStandaloneMode) {
      const token = getAuthToken();
      const currentPath = window.location.pathname;
      if (!token) {
        if (mode === 'ADMIN' && currentPath.startsWith('/admin') && !currentPath.includes('/admin/login')) {
          window.location.href = `/admin/login?next=${encodeURIComponent(currentPath)}`;
        } else if (mode === 'USER' && (currentPath.startsWith('/dashboard') || currentPath.startsWith('/convert'))) {
          window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
        }
      }
    }

    // Capture install prompt event
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, [mode]);

  // STRICT REQUIREMENT: Admin PWA install prompt is exclusively managed by AdminPwaInstall in Admin Header!
  // Floating bottom-right banner is permanently disabled for ADMIN mode.
  if (mode === 'ADMIN') {
    return null;
  }

  // USER mode PWA install prompt MUST NEVER be shown on Admin routes!
  if (mode === 'USER' && pathname?.startsWith('/admin')) {
    return null;
  }

  // If already installed or dismissed, do not render banner
  if (isStandalone || dismissed || !deferredPrompt) {
    return null;
  }

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setDeferredPrompt(null);
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-40 max-w-sm w-full p-4 bg-slate-900 text-white rounded-2xl shadow-2xl border border-slate-800 flex items-center justify-between gap-3 animate-fadeIn">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center flex-shrink-0">
          <Smartphone className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <h4 className="text-xs font-bold truncate">
            Install Kangra Hub App
          </h4>
          <p className="text-[11px] text-slate-300 truncate">
            Quick launch from desktop or home screen
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1.5 flex-shrink-0">
        <Button
          variant="primary"
          size="sm"
          onClick={handleInstallClick}
          icon={<Download className="w-3.5 h-3.5" />}
        >
          Install
        </Button>
        <button
          onClick={() => setDismissed(true)}
          className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          aria-label="Dismiss installation prompt"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
