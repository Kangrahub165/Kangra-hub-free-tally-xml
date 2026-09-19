import React from 'react';
import Link from 'next/link';
import { ArrowLeft, FileQuestion } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export default function NotFound() {
  return (
    <div className="min-h-[calc(100vh-14rem)] flex items-center justify-center p-6 bg-slate-50">
      <div className="max-w-md w-full text-center space-y-4 bg-white p-8 sm:p-10 rounded-3xl border border-slate-200 shadow-elevated">
        <div className="w-14 h-14 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center mx-auto border border-brand-100 shadow-xs">
          <FileQuestion className="w-7 h-7" />
        </div>
        <div className="space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-widest text-brand-600">
            Error 404
          </span>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Page Not Found
          </h1>
          <p className="text-xs text-slate-500 leading-relaxed max-w-xs mx-auto">
            The page you are looking for does not exist or may have been moved.
          </p>
        </div>
        <div className="pt-2">
          <Link href="/">
            <Button variant="primary" size="md" icon={<ArrowLeft className="w-4 h-4" />}>
              Return to Homepage
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
