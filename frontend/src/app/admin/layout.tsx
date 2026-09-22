'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { 
  LayoutDashboard, 
  Users, 
  FileSpreadsheet, 
  Gauge,
  HardDrive,
  Layers,
  FlaskConical,
  Calculator,
  SlidersHorizontal,
  Bell,
  BarChart3,
  Shield,
  ShieldAlert,
  Coffee,
  Settings as SettingsIcon,
  ArrowLeft,
  Lock,
  Menu,
  X,
  ShieldCheck,
  LogOut,
  Sparkles,
  History,
  KeyRound,
  CreditCard
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

import { getAuthToken, clearAuthToken, verifyAdmin } from '@/lib/api';
import { AdminNotificationBell } from '@/components/admin/AdminNotificationBell';
import { AdminPwaInstall } from '@/components/admin/AdminPwaInstall';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Exempt dedicated admin login and reset-password pages from layout wrapper & checks
  const isAuthPage = pathname === '/admin/login' || 
    pathname.startsWith('/admin/login/') ||
    pathname === '/admin/reset-password' ||
    pathname.startsWith('/admin/reset-password/');

  // Dynamically set admin manifest
  useEffect(() => {
    if (typeof window !== 'undefined') {
      let link = document.querySelector("link[rel~='manifest']") as HTMLLinkElement;
      if (!link) {
        link = document.createElement('link');
        link.rel = 'manifest';
        document.head.appendChild(link);
      }
      link.href = '/admin-manifest.webmanifest';
      return () => {
        link.href = '/manifest.webmanifest';
      };
    }
  }, []);

  useEffect(() => {
    if (isAuthPage) return;

    if (typeof window !== 'undefined') {
      const token = getAuthToken();
      if (!token) {
        setIsAdmin(false);
        router.replace(`/admin/login?next=${encodeURIComponent(pathname)}`);
        return;
      }

      verifyAdmin()
        .then((res) => {
          if (res && res.is_admin) {
            setIsAdmin(true);
          } else {
            setIsAdmin(false);
            router.replace('/dashboard');
          }
        })
        .catch((err: any) => {
          setIsAdmin(false);
          if (err?.status === 403 || err?.code === 'FORBIDDEN') {
            router.replace('/dashboard');
          } else {
            clearAuthToken();
            router.replace(`/admin/login?next=${encodeURIComponent(pathname)}`);
          }
        });
    }
  }, [pathname, isAuthPage, router]);

  const handleLogout = () => {
    if (typeof window !== 'undefined') {
      clearAuthToken();
      window.location.href = '/admin/login';
    }
  };

  // If on admin auth pages (login, reset-password), render children directly without admin sidebar
  if (isAuthPage) {
    return <>{children}</>;
  }

  // Strictly block rendering of any admin components until verification succeeds
  if (isAdmin !== true) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-400">
        <div className="flex items-center gap-3 text-xs font-semibold">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Verifying administrator privileges...</span>
        </div>
      </div>
    );
  }

  const adminNavGroups = [
    {
      title: 'ADMIN CONSOLE',
      items: [
        { label: 'Overview', href: '/admin', icon: LayoutDashboard },
      ]
    },
    {
      title: 'CONVERSION',
      items: [
        { label: 'Convert Statement', href: '/admin/convert', icon: Sparkles },
        { label: 'Conversion History', href: '/admin/history', icon: History },
        { label: 'Conversions Monitor', href: '/admin/conversions', icon: FileSpreadsheet },
      ]
    },
    {
      title: 'USERS & BILLING',
      items: [
        { label: 'Users & Access', href: '/admin/users', icon: Users },
        { label: 'Usage & Quotas', href: '/admin/usage', icon: Gauge },
        { label: 'Page Purchase Requests', href: '/admin/payments', icon: CreditCard },
        { label: 'Account Recovery', href: '/admin/recovery', icon: KeyRound },
        { label: 'Account Appeals', href: '/admin/appeals', icon: ShieldAlert },
      ]
    },
    {
      title: 'PARSING',
      items: [
        { label: 'Banks & Parsers', href: '/admin/parsers', icon: Layers },
        { label: 'Statement Testing Lab', href: '/admin/testing-lab', icon: FlaskConical },
      ]
    },
    {
      title: 'ACCOUNTING',
      items: [
        { label: 'Ledger & Accounting', href: '/admin/accounting', icon: Calculator },
      ]
    },
    {
      title: 'PLATFORM',
      items: [
        { label: 'Site Configuration', href: '/admin/settings', icon: SlidersHorizontal },
        { label: 'Analytics', href: '/admin/analytics', icon: BarChart3 },
        { label: 'Notifications', href: '/admin/notifications', icon: Bell },
      ]
    },
    {
      title: 'SYSTEM',
      items: [
        { label: 'File & Processing', href: '/admin/processing', icon: HardDrive },
        { label: 'Security', href: '/admin/security', icon: Shield },
        { label: 'Audit Logs', href: '/admin/logs', icon: ShieldAlert },
      ]
    },
    {
      title: 'ADMIN',
      items: [
        { label: 'Section 129', href: '/admin/section-129', icon: Coffee },
        { label: 'Admin Settings', href: '/admin/system', icon: SettingsIcon },
      ]
    },
  ];

  const getPageTitle = () => {
    const clean = pathname.replace('/admin', '').replace(/^\//, '');
    if (!clean) return 'Command Overview';
    return clean
      .split('/')
      .map((seg) => seg.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()))
      .join(' › ');
  };

  return (
    <div className="bg-slate-100 min-h-screen flex flex-col md:flex-row">
      
      {/* Mobile Backdrop Overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-navy-950/70 backdrop-blur-sm z-30 md:hidden animate-fadeIn"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Admin Sidebar */}
      <aside
        className={`${
          mobileSidebarOpen ? 'fixed inset-y-0 left-0 z-40 w-72 animate-slideInRight' : 'hidden'
        } md:flex md:w-64 gradient-hero text-slate-300 p-4 flex-col justify-between border-r border-accent-500/20 flex-shrink-0 md:sticky md:top-0 h-screen overflow-y-auto dark-scrollbar`}
      >
        <div>
          {/* Header Brand */}
          <div className="flex items-center justify-between pb-5 border-b border-white/10">
            <div className="flex items-center gap-3 group">
              <div className="relative w-8 h-8 flex-shrink-0">
                <Image
                  src="/logo.webp"
                  alt="Kangra Hub"
                  width={32}
                  height={32}
                  className="rounded-lg shadow-glow-brand transition-transform group-hover:scale-105"
                />
              </div>
              <div>
                <div className="font-extrabold text-xs text-white leading-tight drop-shadow-card">Admin Console</div>
                <div className="text-[10px] text-accent-400 font-semibold tracking-wider uppercase">Command Center</div>
              </div>
            </div>
            {mobileSidebarOpen && (
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white"
                aria-label="Close sidebar"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Grouped Navigation Links */}
          <nav className="mt-4 space-y-4" aria-label="Admin grouped navigation">
            {adminNavGroups.map((group) => (
              <div key={group.title}>
                <div className="text-[9px] font-extrabold uppercase tracking-widest text-slate-500 px-3 mb-1">
                  {group.title}
                </div>
                <div className="space-y-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMobileSidebarOpen(false)}
                        className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all nav-link ${
                          isActive
                            ? 'bg-brand-600/90 text-white shadow-glow-brand font-bold nav-link-active'
                            : 'text-slate-400 hover:text-white hover:bg-white/5 nav-link-inactive'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                        <span className="truncate">{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="pt-4 mt-6 border-t border-slate-800/80 space-y-2.5">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to User Portal
          </Link>
          <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
            <span>Auth: <strong className="text-emerald-400">ADMIN</strong></span>
            <button
              onClick={handleLogout}
              className="text-slate-400 hover:text-rose-400 transition-colors flex items-center gap-1 font-sans text-xs"
            >
              <LogOut className="w-3 h-3" /> Exit
            </button>
          </div>
        </div>
      </aside>

      {/* Main Admin Workspace Area with Top Bar */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* Sticky Top Header Bar */}
        <header className="sticky top-0 z-20 glass-header-dark text-white px-4 sm:px-6 py-3 border-b border-navy-800 flex items-center justify-between shadow-subtle">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              aria-label="Open sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="min-w-0">
              <div className="text-[10px] font-bold uppercase tracking-widest text-accent-400 truncate opacity-80">
                Kangra Hub Admin
              </div>
              <h1 className="text-sm font-extrabold text-white truncate drop-shadow-xs">
                {getPageTitle()}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
            <AdminNotificationBell />
            <AdminPwaInstall />
            <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-white/10 text-xs">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="font-mono text-emerald-50 font-bold bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-900/50">SUPER_ADMIN</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
