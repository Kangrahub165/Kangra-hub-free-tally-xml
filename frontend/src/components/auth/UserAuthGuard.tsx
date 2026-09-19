'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getAuthToken } from '@/lib/api';

export function UserAuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authorized, setAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const token = getAuthToken();
      if (!token) {
        setAuthorized(false);
        router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
      } else {
        setAuthorized(true);
      }
    }
  }, [pathname, router]);

  if (authorized !== true) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 text-slate-400">
        <div className="flex items-center gap-3 text-xs font-semibold">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Verifying authentication...</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
