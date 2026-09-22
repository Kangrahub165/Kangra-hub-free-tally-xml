'use client';

import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import { Download, Smartphone, X, Check, Monitor, ExternalLink, Sparkles, HelpCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

export function AdminPwaInstall() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandalone, setIsStandalone] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);

  useEffect(() => {
    // Check if running as installed standalone PWA
    const checkStandalone = () => {
      const isStandaloneMode = 
        window.matchMedia('(display-mode: standalone)').matches ||
        (window.navigator as any).standalone === true;
      setIsStandalone(isStandaloneMode);
    };

    checkStandalone();

    // Register Service Worker for PWA compliance
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch((err) => {
        console.warn('Admin PWA ServiceWorker registration notice:', err);
      });
    }

    // Capture install prompt event
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    const handleAppInstalled = () => {
      setIsInstalled(true);
      setDeferredPrompt(null);
      setIsModalOpen(false);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isModalOpen) {
        setIsModalOpen(false);
      }
    };
    if (isModalOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isModalOpen]);

  // If running in standalone mode or already installed, hide install control completely
  if (isStandalone || isInstalled) {
    return null;
  }

  const handleOpenModal = () => {
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleTriggerInstall = async () => {
    if (!deferredPrompt) return;
    setIsInstalling(true);
    try {
      await deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') {
        setIsInstalled(true);
        setDeferredPrompt(null);
        setIsModalOpen(false);
      } else {
        // Dismissed: Close modal gracefully, leave header button available for later
        setIsModalOpen(false);
      }
    } catch (err) {
      console.warn('PWA install prompt error:', err);
    } finally {
      setIsInstalling(false);
    }
  };

  return (
    <>
      {/* Integrated Admin Header Install Button */}
      <button
        onClick={handleOpenModal}
        className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-500 hover:to-brand-400 text-white rounded-xl text-xs font-bold transition-all shadow-glow-brand active:scale-95 focus:outline-none focus:ring-2 focus:ring-brand-400 border-none"
        aria-label="Install Admin Console App"
        title="Install Kangra Hub Admin Console as an App"
      >
        <Download className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="hidden sm:inline">Install App</span>
      </button>

      {/* Professional Custom PWA Installation Modal */}
      {isModalOpen && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-navy-950/70 backdrop-blur-sm animate-fadeIn"
          role="dialog"
          aria-modal="true"
          aria-labelledby="pwa-install-title"
        >
          {/* Backdrop */}
          <div 
            className="fixed inset-0"
            onClick={handleCloseModal}
            aria-hidden="true"
          />

          {/* Modal Container */}
          <div className="relative w-full max-w-md bg-white rounded-3xl shadow-modal border border-slate-200 z-10 overflow-hidden animate-scaleIn max-h-[92vh] flex flex-col">
            
            {/* Top Close Button */}
            <button
              onClick={handleCloseModal}
              className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-100 transition-colors z-20"
              aria-label="Close dialog"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Modal Header & Branding */}
            <div className="p-6 sm:p-7 text-center border-b border-slate-100 bg-slate-50/50">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white p-2 border border-slate-200 shadow-sm mx-auto mb-3.5">
                <Image
                  src="/logo.webp"
                  alt="Kangra Hub Logo"
                  width={48}
                  height={48}
                  className="rounded-xl object-contain"
                />
              </div>

              <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-brand-50 text-brand-700 text-[10px] font-extrabold uppercase tracking-wider mb-2 border border-brand-200">
                <Sparkles className="w-3 h-3" />
                <span>Admin Console PWA</span>
              </div>

              <h2 id="pwa-install-title" className="text-xl font-black text-slate-900 tracking-tight">
                Install Admin Console
              </h2>
              <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto leading-relaxed">
                Get quick, distraction-free access to your Admin Command Center directly from your desktop or home screen.
              </p>
            </div>

            {/* Modal Body - Benefits & Fallback Details */}
            <div className="p-6 space-y-4 overflow-y-auto flex-1">
              {deferredPrompt ? (
                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-3 rounded-2xl bg-slate-50 border border-slate-200/80">
                    <div className="w-7 h-7 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Check className="w-4 h-4 font-bold" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">Faster & Direct Access</h4>
                      <p className="text-[11px] text-slate-500 leading-normal">
                        Launch instantly from your dock or taskbar without opening a browser tab.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-2xl bg-slate-50 border border-slate-200/80">
                    <div className="w-7 h-7 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Monitor className="w-4 h-4 font-bold" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">Dedicated Window</h4>
                      <p className="text-[11px] text-slate-500 leading-normal">
                        Runs in a clean, standalone window without URL bars or browser clutter.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-3 rounded-2xl bg-slate-50 border border-slate-200/80">
                    <div className="w-7 h-7 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Smartphone className="w-4 h-4 font-bold" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">Desktop & Mobile Optimized</h4>
                      <p className="text-[11px] text-slate-500 leading-normal">
                        Maintains session state and fast caching across all your administrative tasks.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                /* Fallback Instructions when browser does not fire beforeinstallprompt */
                <div className="space-y-3">
                  <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-900">
                    <div className="font-bold flex items-center gap-1.5 mb-1 text-amber-800">
                      <HelpCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                      <span>How to install from your browser menu:</span>
                    </div>
                    <ul className="space-y-2 mt-2 text-[11px] text-amber-900/90 list-disc pl-4 leading-relaxed">
                      <li>
                        <strong>Google Chrome & Microsoft Edge:</strong> Click the install icon (<strong>⊕</strong>) in the address bar, or open menu <strong>⋮</strong> &rarr; <em>&ldquo;Install Kangra Hub...&rdquo;</em>
                      </li>
                      <li>
                        <strong>Safari (macOS / iOS):</strong> Click the <strong>Share</strong> icon (<strong>↑</strong>) &rarr; select <em>&ldquo;Add to Dock&rdquo;</em> or <em>&ldquo;Add to Home Screen&rdquo;</em>.
                      </li>
                      <li>
                        <strong>Firefox:</strong> You can bookmark this page or create a desktop shortcut for one-click access.
                      </li>
                    </ul>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer Actions */}
            <div className="p-4 sm:p-5 border-t border-slate-100 bg-slate-50/50 flex items-center justify-end gap-2.5">
              <Button
                variant="secondary"
                size="md"
                onClick={handleCloseModal}
              >
                {deferredPrompt ? 'Not Now' : 'Close'}
              </Button>

              {deferredPrompt && (
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleTriggerInstall}
                  loading={isInstalling}
                  className="bg-gradient-to-r from-brand-600 to-brand-500 border-none shadow-glow-brand hover:from-brand-500 hover:to-brand-400"
                  icon={<Download className="w-4 h-4" />}
                >
                  Install App
                </Button>
              )}
            </div>

          </div>
        </div>
      )}
    </>
  );
}
