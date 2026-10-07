'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Home, 
  Receipt, 
  ShoppingCart, 
  History, 
  User 
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthProvider';

export function MobileBottomNav() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuth();

  // Hide on admin routes and auth pages
  if (
    pathname.startsWith('/admin') ||
    pathname === '/login' ||
    pathname === '/signup' ||
    pathname.startsWith('/recover-account')
  ) {
    return null;
  }

  const navItems = [
    {
      label: 'Home',
      href: '/',
      icon: Home,
      isActive: pathname === '/',
    },
    {
      label: 'Sales',
      href: '/sales',
      icon: Receipt,
      isActive: pathname === '/sales',
    },
    {
      label: 'Purchase',
      href: '/purchase',
      icon: ShoppingCart,
      isActive: pathname === '/purchase',
    },
    {
      label: 'History',
      href: '/history',
      icon: History,
      isActive: pathname === '/history',
    },
    {
      label: 'Profile',
      href: isAuthenticated ? '/dashboard' : '/login?redirect=/dashboard',
      icon: User,
      isActive: pathname === '/dashboard',
    },
  ];

  return (
    <nav
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-lg border-t border-slate-200/90 shadow-[0_-4px_20px_rgba(0,0,0,0.06)] px-2 py-1 safe-area-pb"
      aria-label="Mobile Bottom Navigation"
    >
      <div className="flex items-center justify-around max-w-lg mx-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = item.isActive;
          return (
            <Link
              key={item.label}
              href={item.href}
              className={`flex flex-col items-center justify-center flex-1 py-1.5 px-1 rounded-xl transition-all duration-200 relative ${
                active
                  ? 'text-brand-600 font-bold scale-105'
                  : 'text-slate-500 hover:text-slate-900 font-medium'
              }`}
            >
              {active && (
                <span className="absolute -top-1 w-6 h-1 rounded-full bg-brand-600 shadow-glow-brand" />
              )}
              <Icon className={`w-5 h-5 ${active ? 'stroke-[2.5px]' : 'stroke-[1.75px]'}`} />
              <span className="text-[10px] tracking-tight mt-0.5">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
