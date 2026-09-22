'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { Menu, X, ArrowRight, User, FileSpreadsheet, Shield, LogOut } from 'lucide-react';
import { getPublicSettings, PublicSettings, clearAuthToken, getUserRole } from '@/lib/api';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

export function Header() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userRole, setUserRole] = useState<'ADMIN' | 'USER' | 'GUEST'>('GUEST');

  useEffect(() => {
    getPublicSettings().then(setSettings).catch(() => {});
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('kh_auth_token');
      setIsLoggedIn(!!token);
      setUserRole(getUserRole());
    }
  }, [pathname]);

  // Admin routes have their own full-screen specialized workspace sidebar
  if (pathname?.startsWith('/admin')) {
    return null;
  }

  const handleLogout = () => {
    clearAuthToken();
    setIsLoggedIn(false);
    setUserRole('GUEST');
    window.location.href = '/';
  };

  const isFree = settings?.site_mode !== 'PAID';
  const isAdmin = userRole === 'ADMIN';

  const navLinks = [
    { label: 'How It Works', href: '/how-it-works' },
    { label: 'Unlock PDF', href: '/unlock-pdf' },
    { label: 'Supported Banks', href: '/supported-banks' },
    { label: 'FAQ', href: '/faq' },
    { label: 'Contact', href: '/contact' },
  ];

  return (
    <header className="sticky top-0 z-40 glass-header shadow-subtle transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-18">
          
          {/* Logo & Brand Identity */}
          <div className="flex items-center gap-3.5">
            <Link href="/" className="flex items-center gap-3 group focus:outline-none">
              <div className="relative w-10 h-10 flex-shrink-0">
                <Image
                  src="/logo.webp"
                  alt="Kangra Hub Free Tally XML"
                  width={40}
                  height={40}
                  priority
                  className="w-full h-full object-contain rounded-xl transition-transform group-hover:scale-105 shadow-xs"
                />
              </div>
              <div className="flex flex-col">
                <span className="font-extrabold text-lg tracking-tight text-gradient-brand leading-tight">
                  Kangra Hub
                </span>
                <span className="text-[10px] font-bold text-navy-500 tracking-wider uppercase">
                  Tally XML Platform
                </span>
              </div>
            </Link>

            {/* Compact Mode Status Badge */}
            <div className="hidden lg:inline-flex items-center ml-2">
              {isFree ? (
                <Badge variant="success" size="sm" pulse>
                  Free Standard Access
                </Badge>
              ) : (
                <Badge variant="primary" size="sm">
                  Paid Service
                </Badge>
              )}
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1.5" aria-label="Main Navigation">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-1.5 rounded-xl text-xs lg:text-sm font-semibold transition-all duration-150 ${
                    isActive
                      ? 'bg-brand-50 text-brand-700 font-bold shadow-xs'
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
            {isLoggedIn ? (
              <div className="flex items-center gap-2">
                <Link href="/dashboard">
                  <Button variant="outline" size="sm" icon={<User className="w-3.5 h-3.5 text-slate-500" />}>
                    Dashboard
                  </Button>
                </Link>
                <Link href="/convert">
                  <Button variant="primary" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                    Convert Statement
                  </Button>
                </Link>
                <button
                  onClick={handleLogout}
                  title="Sign out"
                  className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-colors ml-1"
                  aria-label="Sign out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link href="/login">
                  <Button variant="ghost" size="sm">
                    Log In
                  </Button>
                </Link>
                <Link href="/signup">
                  <Button variant="primary" size="sm" className="bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-500 hover:to-brand-400 border-none shadow-glow-brand" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                    Get Started Free
                  </Button>
                </Link>
              </div>
            )}
          </div>

          {/* Mobile Menu Trigger */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
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
          <div className="relative w-[280px] max-w-[80vw] h-full bg-white shadow-2xl animate-slideInRight flex flex-col pt-6 px-5 pb-6 overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <span className="text-xs text-slate-500 font-medium">Service Mode</span>
            {isFree ? (
              <Badge variant="success" size="sm" pulse>
                Free Access (50 Pgs/Day)
              </Badge>
            ) : (
              <Badge variant="primary" size="sm">
                Paid Service
              </Badge>
            )}
          </div>

          <div className="space-y-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`block px-3 py-3 rounded-xl text-sm font-semibold transition-colors ${
                  pathname === link.href
                    ? 'bg-brand-50 text-brand-700 font-bold'
                    : 'text-navy-700 hover:bg-navy-50'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>

          <div className="pt-3 border-t border-slate-100 flex flex-col gap-2">
            {isLoggedIn ? (
              <>
                <Link
                  href="/convert"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full"
                >
                  <Button variant="primary" size="md" className="w-full" iconRight={<ArrowRight className="w-4 h-4" />}>
                    Start Conversion
                  </Button>
                </Link>
                <div className="grid grid-cols-2 gap-2">
                  <Link
                    href="/dashboard"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <Button variant="outline" size="sm" className="w-full">
                      Dashboard
                    </Button>
                  </Link>
                  <button
                    onClick={() => {
                      setMobileMenuOpen(false);
                      handleLogout();
                    }}
                    className="w-full inline-flex items-center justify-center text-xs font-semibold text-rose-600 bg-rose-50 rounded-xl py-2"
                  >
                    Sign Out
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link
                  href="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full"
                >
                  <Button variant="primary" size="md" className="w-full" iconRight={<ArrowRight className="w-4 h-4" />}>
                    Create Free Account
                  </Button>
                </Link>
                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full"
                >
                  <Button variant="outline" size="md" className="w-full">
                    Log In
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
        </div>
      )}
    </header>
  );
}
