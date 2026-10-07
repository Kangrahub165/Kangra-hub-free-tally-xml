'use client';

import { useEffect } from 'react';
import { notFound, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

export default function StaffDemoPage() {
  const router = useRouter();

  // PRD Addendum 3 Part 4.2.1: The /staff-demo route must not exist in production.
  if (process.env.NODE_ENV === 'production') {
    notFound();
  }

  useEffect(() => {
    // PRD Addendum 3 Part 4.2.2: In development, redirect to /workspace with a console warning.
    console.warn('[KangraHub] /staff-demo is deprecated. Redirecting to production Batch Workspace at /workspace');
    router.replace('/workspace');
  }, [router]);

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4 text-center">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
      <h2 className="text-white font-bold text-lg mb-1">Redirecting to Batch Workspace...</h2>
      <p className="text-slate-400 text-sm">Demo routes are deprecated. Opening real workspace.</p>
    </div>
  );
}
