'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Lock } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthProvider';
import { Button } from '@/components/ui/Button';

export default function ConversionPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.push('/login?redirect=/conversion');
      return;
    }
    router.replace('/convert');
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-14 h-14 bg-brand-50 border border-brand-200 text-brand-600 rounded-2xl flex items-center justify-center mb-4 shadow-sm animate-pulse">
          <Lock className="w-7 h-7" />
        </div>
        <h2 className="text-xl font-extrabold text-slate-900 mb-2">Member Authentication Required</h2>
        <p className="text-sm text-slate-600 max-w-md mb-6 leading-relaxed">
          Please log in to your Kangra Hub account to access and use the conversion feature.
        </p>
        <Link href="/login?redirect=/conversion">
          <Button variant="primary" size="md" className="font-bold">
            Log In to Continue
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center space-y-3">
        <div className="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-slate-500 font-medium">Opening conversion workspace...</p>
      </div>
    </div>
  );
}
