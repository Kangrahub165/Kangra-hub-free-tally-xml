'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { Menu, X, ArrowRight, User, FileSpreadsheet, Shield, LogOut, Sparkles, Clock } from 'lucide-react';
import { getPublicSettings, PublicSettings, getUserUsage, UsageInfo } from '@/lib/api';
import { useAuth } from './auth/AuthProvider';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { GoldTick } from './ui/GoldTick';
import { SubscriptionModal } from './SubscriptionModal';

export function Header() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [showSubModal, setShowSubModal] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  const { isAuthenticated, isAdmin, isStaff, isGold, isExpired, logout, user } = useAuth();

  useEffect(() => {
    getPublicSettings().then(setSettings).catch(() => {});
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const dismissed = sessionStorage.getItem('kh_verified_banner_dismissed');
      if (dismissed === 'true') {
        setBannerDismissed(true);
      }
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated && !isStaff && !isAdmin) {
      getUserUsage().then(setUsage).catch(() => {});
    }
  }, [isAuthenticated, isStaff, isAdmin, pathname]);

  // Admin routes have their own full-screen specialized workspace sidebar
  if (pathname?.startsWith('/admin')) {
    return null;
  }

  const handleLogout = () => {
    logout();
    window.location.href = '/';
  };

  const dismissBanner = () => {
    setBannerDismissed(true);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('kh_verified_banner_dismissed', 'true');
    }
  };

  const isFree = settings?.site_mode !== 'PAID';
  const billsRemaining = usage?.bills_remaining_today ?? 5;

  const isDarkWorkspace = isStaff || isAdmin;

  const navLinks = [
    { label: 'Home', href: '/' },
    { label: 'Sales', href: '/sales' },
    { label: 'Purchase', href: '/purchase' },
    ...(isDarkWorkspace
      ? [{ label: 'Batch Workspace', href: '/workspace' }]
      : [{ label: 'Gold Pricing', href: '/checkout' }]),
    { label: 'Bank Import', href: 'https://kangrahubtallyxml.netlify.app/', external: true },
    ...(isAuthenticated
      ? [{ label: isAdmin ? 'Admin Panel' : 'Dashboard', href: isAdmin ? '/admin' : '/dashboard' }]
      : []),
  ];

  return (
    <>
      {/* Top Expiry Alert Banner (When subscription has expired) */}
      {isExpired && (
        <div className="bg-rose-950 text-rose-200 text-xs px-4 py-2 border-b border-rose-800/80 relative z-50">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap">
              <span className="p-1 rounded-md bg-rose-500/20 text-rose-400 flex-shrink-0">
                <Clock className="w-3.5 h-3.5" />
              </span>
              <span className="text-[11px] sm:text-xs">
                <strong className="text-rose-400">Staff Membership Expired:</strong> Your subscription has expired. Please renew your membership to continue unlimited bill conversions and keep your Golden Tick.
              </span>
            </div>
            <Link
              href="/checkout"
              className="px-3 py-1 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white text-[11px] font-bold shadow-xs cursor-pointer flex-shrink-0"
            >
              Renew Membership
            </Link>
          </div>
        </div>
      )}

      {/* Top Dismissible Verified Upsell Banner (Only for Normal/Free Users) */}
      {!bannerDismissed && !isStaff && !isAdmin && !isExpired && (
        <div className="bg-gradient-to-r from-navy-950 via-slate-900 to-navy-950 text-white text-xs px-4 py-2 border-b border-amber-500/20 relative z-50">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap">
              <span className="p-1 rounded-md bg-amber-400/20 text-amber-400 flex-shrink-0">
                <Sparkles className="w-3.5 h-3.5" />
              </span>
              <span className="text-[11px] sm:text-xs text-slate-200">
                <strong className="text-amber-400">Kangra Hub Verified:</strong> Unlimited daily bills, zero waiting, and official Gold Tick!
              </span>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <Link
                href="/checkout"
                className="hidden sm:inline-flex text-[11px] font-semibold text-slate-300 hover:text-white underline underline-offset-2"
              >
                View Gold Plan
              </Link>
              <button
                type="button"
                onClick={() => setShowSubModal(true)}
                className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white text-[11px] font-bold shadow-xs cursor-pointer"
              >
                Get Verified
              </button>
              <button
                type="button"
                onClick={dismissBanner}
                className="text-slate-400 hover:text-white p-0.5"
                aria-label="Dismiss banner"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      <header className={`sticky top-0 z-40 transition-colors ${
        isDarkWorkspace
          ? 'bg-slate-950/95 border-b border-slate-800 text-slate-100 shadow-md backdrop-blur-md'
          : 'glass-header shadow-subtle'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-18">
            
            {/* Logo & Brand Identity */}
            <div className="flex items-center gap-3.5">
              <Link href="/" className="flex items-center gap-3 group focus:outline-none">
                <div className="relative w-10 h-10 flex-shrink-0">
                  <Image
                    src="/logo.webp"
                    alt="Kangra Hub — Sales & Purchase"
                    width={40}
                    height={40}
                    priority
                    className="w-full h-full object-contain rounded-xl transition-transform group-hover:scale-105 shadow-xs"
                  />
                </div>
                <div className="flex flex-col">
                  <span className={`font-extrabold text-lg tracking-tight leading-tight ${
                    isDarkWorkspace ? 'text-white' : 'text-gradient-brand'
                  }`}>
                    Kangra Hub
                  </span>
                  <span className={`text-[10px] font-bold tracking-wider uppercase ${
                    isDarkWorkspace ? 'text-amber-400' : 'text-navy-500'
                  }`}>
                    Sales & Purchase
                  </span>
                </div>
              </Link>

              {/* Mode / Quota Status Badge */}
              <div className="hidden lg:inline-flex items-center ml-2">
                {isDarkWorkspace ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-xs">
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                    <span>{isAdmin ? 'Admin Workspace' : 'Staff SaaS Workspace'}</span>
                    <GoldTick size="sm" />
                  </span>
                ) : (
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-[11px] text-slate-700">
                    <span className="font-bold text-brand-700">
                      Bills left today: {billsRemaining} / 5
                    </span>
                    <span className="text-slate-400 font-medium">· Resets 12:00 AM IST</span>
                  </div>
                )}
              </div>
            </div>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-1.5" aria-label="Main Navigation">
              {navLinks.map((link) => {
                if (link.external) {
                  return (
                    <a
                      key={link.label}
                      href={link.href}
                      className={`px-3 py-1.5 rounded-xl text-xs lg:text-sm font-semibold transition-all duration-150 ${
                        isDarkWorkspace
                          ? 'text-slate-300 hover:text-white hover:bg-slate-800'
                          : 'text-slate-600 hover:text-brand-600 hover:bg-slate-100/80'
                      }`}
                    >
                      {link.label}
                    </a>
                  );
                }
                const isActive = link.href === '/' ? pathname === '/' : (pathname === link.href || pathname?.startsWith(link.href));
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`px-3 py-1.5 rounded-xl text-xs lg:text-sm font-semibold transition-all duration-150 ${
                      isActive
                        ? isDarkWorkspace
                          ? 'bg-slate-800 text-amber-300 font-bold border border-slate-700 shadow-xs'
                          : 'bg-brand-50 text-brand-700 font-bold shadow-xs'
                        : isDarkWorkspace
                          ? 'text-slate-300 hover:text-white hover:bg-slate-800 font-medium'
                          : 'text-slate-600 hover:text-brand-600 hover:bg-slate-100/80 font-medium'
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>

            {/* User / Authentication CTAs */}
            <div className="hidden md:flex items-center gap-2.5">
              {isAuthenticated ? (
                <div className="flex items-center gap-2">
                  <Link
                    href={isAdmin ? '/admin' : '/dashboard'}
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold transition-colors ${
                      isDarkWorkspace
                        ? 'text-slate-200 hover:text-white hover:bg-slate-800'
                        : 'text-slate-700 hover:text-brand-600 hover:bg-slate-100'
                    }`}
                  >
                    <span className={`w-7 h-7 rounded-full flex items-center justify-center font-black text-[11px] ${
                      isGold
                        ? 'bg-amber-400/20 text-amber-300 ring-1 ring-amber-400/50'
                        : 'bg-brand-100 text-brand-700'
                    }`}>
                      {user?.fullName?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase() || 'U'}
                    </span>
                    <span className="max-w-[120px] truncate">{user?.fullName || user?.email?.split('@')[0] || (isAdmin ? 'Admin' : 'My Account')}</span>
                    {isGold && <GoldTick size="sm" />}
                    {isAdmin && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-amber-500 text-slate-950">
                        Admin
                      </span>
                    )}
                  </Link>
                  <button
                    onClick={handleLogout}
                    title="Sign out"
                    className={`inline-flex items-center justify-center font-semibold transition-all duration-200 rounded-xl px-3 py-1.5 text-xs gap-1.5 border cursor-pointer ${
                      isDarkWorkspace
                        ? 'text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 border-slate-800'
                        : 'text-slate-500 hover:text-rose-600 hover:bg-rose-50 border-slate-200'
                    }`}
                    aria-label="Sign out"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign Out
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    href="/login"
                    className="inline-flex items-center justify-center font-semibold transition-all duration-200 rounded-xl px-3 py-1.5 text-xs gap-1.5 bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-transparent active:scale-[0.97]"
                  >
                    Log In
                  </Link>
                  <Link
                    href="/signup"
                    className="inline-flex items-center justify-center font-semibold transition-all duration-200 rounded-xl px-3.5 py-1.5 text-xs gap-1.5 bg-brand-600 text-white hover:bg-brand-500 shadow-sm border border-brand-700/20 active:scale-[0.97]"
                  >
                    Sign Up
                  </Link>
                </div>
              )}
            </div>

            {/* Mobile Menu Trigger */}
            <div className="flex md:hidden items-center gap-2">
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className={`p-2 rounded-xl transition-colors ${
                  isDarkWorkspace
                    ? 'text-slate-300 hover:text-white hover:bg-slate-800'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
                aria-label="Toggle menu"
                aria-expanded={mobileMenuOpen}
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Drawer Menu */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 flex justify-end md:hidden">
            <div className="fixed inset-0 bg-navy-950/60 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)}></div>
            <div className={`relative w-[280px] max-w-[80vw] h-full shadow-2xl animate-slideInRight flex flex-col pt-6 px-5 pb-6 overflow-y-auto ${
              isDarkWorkspace
                ? 'bg-slate-950 text-slate-100 border-l border-slate-800'
                : 'bg-white text-slate-900'
            }`}>
              <div className={`flex items-center justify-between pb-3 mb-2 border-b ${
                isDarkWorkspace ? 'border-slate-800' : 'border-slate-100'
              }`}>
                <span className={`text-xs font-medium ${isDarkWorkspace ? 'text-slate-400' : 'text-slate-500'}`}>Account Tier</span>
                {isDarkWorkspace ? (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-400">
                    {isAdmin ? 'Admin' : 'Staff'} (Unlimited) <GoldTick size="sm" />
                  </span>
                ) : (
                  <span className="text-xs font-bold text-brand-700">
                    {billsRemaining} Bills Left Today
                  </span>
                )}
              </div>

              <div className="space-y-1">
                {navLinks.map((link) => {
                  if (link.external) {
                    return (
                      <a
                        key={link.label}
                        href={link.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`block px-3 py-3 rounded-xl text-sm font-semibold transition-colors ${
                          isDarkWorkspace
                            ? 'text-slate-300 hover:bg-slate-900 hover:text-white'
                            : 'text-navy-700 hover:bg-navy-50'
                        }`}
                      >
                        {link.label}
                      </a>
                    );
                  }
                  const isMobileActive = link.href === '/' ? pathname === '/' : (pathname === link.href || pathname?.startsWith(link.href));
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`block px-3 py-3 rounded-xl text-sm font-semibold transition-colors ${
                        isMobileActive
                          ? isDarkWorkspace
                            ? 'bg-slate-800 text-amber-300 font-bold border border-slate-700'
                            : 'bg-brand-50 text-brand-700 font-bold'
                          : isDarkWorkspace
                            ? 'text-slate-300 hover:bg-slate-900 hover:text-white'
                            : 'text-navy-700 hover:bg-navy-50'
                      }`}
                    >
                      {link.label}
                    </Link>
                  );
                })}
              </div>

              <div className={`mt-auto pt-6 space-y-2 border-t ${
                isDarkWorkspace ? 'border-slate-800' : 'border-slate-100'
              }`}>
                {!isStaff && !isAdmin && (
                  <button
                    onClick={() => {
                      setMobileMenuOpen(false);
                      setShowSubModal(true);
                    }}
                    className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs flex items-center justify-center gap-2 cursor-pointer shadow-sm"
                  >
                    <Sparkles className="w-4 h-4" /> Get Verified (Unlimited)
                  </button>
                )}

                {isAuthenticated ? (
                  <button
                    onClick={handleLogout}
                    className="w-full py-2.5 rounded-xl border border-rose-200 text-rose-600 hover:bg-rose-50 font-bold text-xs flex items-center justify-center gap-2"
                  >
                    <LogOut className="w-4 h-4" /> Sign Out
                  </button>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    <Link
                      href="/login"
                      onClick={() => setMobileMenuOpen(false)}
                      className="py-2.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-bold text-xs text-center"
                    >
                      Log In
                    </Link>
                    <Link
                      href="/signup"
                      onClick={() => setMobileMenuOpen(false)}
                      className="py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs text-center shadow-xs"
                    >
                      Sign Up
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Subscription Modal */}
      <SubscriptionModal
        isOpen={showSubModal}
        onClose={() => setShowSubModal(false)}
        onSuccess={() => {
          if (isAuthenticated) {
            getUserUsage().then(setUsage).catch(() => {});
          }
        }}
      />
    </>
  );
}

export default Header;
