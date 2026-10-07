'use client';

import React, { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from './AuthProvider';
import { KangraLoader } from '@/components/ui/KangraLoader';

export function UserAuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center p-6">
        <KangraLoader
          size="md"
          text="Verifying session..."
          subtext="Connecting securely to Kangra Hub"
        />
      </div>
    );
  }

  return <>{children}</>;
}
