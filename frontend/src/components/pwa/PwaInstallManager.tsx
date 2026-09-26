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

    // Check if already captured globally on window
    if (typeof window !== 'undefined' && (window as any).__pwaDeferredPrompt) {
      setDeferredPrompt((window as any).__pwaDeferredPrompt);
    }

    // Capture install prompt event
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      (window as any).__pwaDeferredPrompt = e;
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      window.dispatchEvent(new Event('kh:pwa-prompt-ready'));
    };

    const handlePromptReady = () => {
      if (typeof window !== 'undefined' && (window as any).__pwaDeferredPrompt) {
        setDeferredPrompt((window as any).__pwaDeferredPrompt);
      }
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('kh:pwa-prompt-ready', handlePromptReady);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('kh:pwa-prompt-ready', handlePromptReady);
    };
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
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/70 backdrop-blur-sm animate-fadeIn"
      role="dialog"
      aria-modal="true"
    >
      <div className="absolute inset-0" onClick={() => setDismissed(true)}></div>
      <div className="relative w-full max-w-md bg-white rounded-3xl shadow-modal border border-slate-200 z-10 overflow-hidden animate-scaleIn flex flex-col">
        <button
          onClick={() => setDismissed(true)}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-100 transition-colors z-20"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-7 text-center border-b border-slate-100 bg-slate-50/50">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white p-2 border border-slate-200 shadow-sm mx-auto mb-3.5">
            <Smartphone className="w-8 h-8 text-brand-600" />
          </div>
          <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-brand-50 text-brand-700 text-[10px] font-extrabold uppercase tracking-wider mb-2 border border-brand-200">
            <Sparkles className="w-3 h-3" />
            <span>App Install</span>
          </div>
          <h2 className="text-xl font-black text-slate-900 tracking-tight">
            Install Kangra Hub App
          </h2>
          <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto leading-relaxed">
            Get quick, distraction-free access directly from your desktop or home screen.
          </p>
        </div>

        <div className="p-6 space-y-3 bg-white">
          <div className="flex items-start gap-3 p-3 rounded-2xl bg-slate-50 border border-slate-200/80">
            <div className="w-7 h-7 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">Faster & Direct Access</h4>
              <p className="text-[11px] text-slate-500">Launch instantly without opening a browser.</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 rounded-2xl bg-slate-50 border border-slate-200/80">
            <div className="w-7 h-7 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center flex-shrink-0 mt-0.5">
              <Smartphone className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">Offline Capabilities</h4>
              <p className="text-[11px] text-slate-500">Use features faster with local caching.</p>
            </div>
          </div>
        </div>

        <div className="p-5 border-t border-slate-100 bg-slate-50/50 flex items-center justify-end gap-3">
          <Button variant="secondary" size="md" onClick={() => setDismissed(true)}>
            Not Now
          </Button>
          <Button variant="primary" size="md" onClick={handleInstallClick} className="bg-gradient-to-r from-brand-600 to-brand-500 border-none shadow-glow-brand hover:from-brand-500 hover:to-brand-400" icon={<Download className="w-4 h-4" />}>
            Install App
          </Button>
        </div>
      </div>
    </div>
  );
}
