'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowRight, Mail, Lock, Eye, EyeOff, CheckCircle2 } from 'lucide-react';
import { userLogin } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { StatusAlert } from '@/components/ui/StatusAlert';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextUrl = searchParams.get('redirect') || searchParams.get('next');
  const isExpired = searchParams.get('expired') === 'true';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');

  useEffect(() => {
    if (isExpired) {
      setInfoMessage('Your session has expired. Please log in again to continue.');
    } else if (nextUrl && (nextUrl.includes('/convert') || nextUrl === '/convert')) {
      setInfoMessage('Please log in or create a free account to continue.');
    }
  }, [isExpired, nextUrl]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setError('Please enter both your email address and password.');
      return;
    }

    setLoading(true);

    try {
      await userLogin(cleanEmail, password);
      // Determine destination: never redirect normal user to /admin
      let target = '/dashboard';
      if (nextUrl && !nextUrl.startsWith('/admin')) {
        target = nextUrl;
      }
      router.push(target);
    } catch (err: any) {
      if (
        err.status === 403 ||
        err.code === 'ACCOUNT_SUSPENDED' ||
        (err.message && err.message.toLowerCase().includes('suspended'))
      ) {
        const queryParams = new URLSearchParams();
        queryParams.set('email', cleanEmail);
        if (err.full_name) queryParams.set('name', err.full_name);
        if (err.user_id) queryParams.set('user_id', err.user_id);
        if (err.suspension_reason) queryParams.set('reason', err.suspension_reason);
        if (err.suspended_at) queryParams.set('suspended_at', err.suspended_at);
        if (err.suspension_delete_at) queryParams.set('delete_at', err.suspension_delete_at);
        router.push(`/suspended?${queryParams.toString()}`);
        return;
      }
      const msg = err.message || 'Invalid email or password. Please check your credentials and try again.';
      // Ensure no raw JWT or internal errors are exposed
      if (msg.toLowerCase().includes('jwt') || msg.toLowerCase().includes('claims') || msg.toLowerCase().includes('signature')) {
        setError('Invalid email or password. Please try again.');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-4 sm:p-6 lg:p-10 bg-slate-50">
      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-12 bg-white rounded-3xl border border-slate-200 shadow-elevated overflow-hidden">
        
        {/* Left Value Prop Hero (5 cols) */}
        <div className="hidden lg:flex lg:col-span-5 bg-gradient-to-br from-slate-900 via-slate-950 to-brand-950 p-8 flex-col justify-between text-white relative">
          <div className="absolute inset-0 bg-[radial-gradient(#38bdf810_1px,transparent_1px)] bg-[size:16px_16px] pointer-events-none" />

          <div className="relative z-10 space-y-6">
            <Link href="/" className="flex items-center gap-3 inline-flex">
              <div className="relative w-9 h-9 flex-shrink-0">
                <Image
                  src="/logo.webp"
                  alt="Kangra Hub"
                  width={36}
                  height={36}
                  className="rounded-xl shadow-xs"
                />
              </div>
              <div className="flex flex-col">
                <span className="font-extrabold text-base tracking-tight text-white leading-tight">
                  Kangra Hub
                </span>
                <span className="text-[10px] font-bold text-brand-300 tracking-wider uppercase">
                  Free Tally XML
                </span>
              </div>
            </Link>

            <div className="space-y-3 pt-4">
              <Badge variant="success" size="sm" pulse>
                Daily 50-Page Free Quota
              </Badge>
              <h2 className="text-xl font-extrabold text-white tracking-tight leading-snug">
                The modern standard for statement to Tally conversion.
              </h2>
              <p className="text-xs text-slate-300 leading-relaxed">
                Log into your account to convert bank statements, customize recurring party mappings, and monitor transaction math audits.
              </p>
            </div>

            <div className="space-y-2.5 pt-2">
              <div className="flex items-center gap-2.5 text-xs text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>38+ Bank statement templates supported</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Double-entry balance check before export</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>Zero permanent financial PDF storage</span>
              </div>
            </div>
          </div>

          <div className="relative z-10 pt-6 border-t border-slate-800 text-[11px] text-slate-400">
            🔒 Bank statements processed in ephemeral RAM.
          </div>
        </div>

        {/* Right Form Column (7 cols) */}
        <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-center">
          <div className="max-w-md w-full mx-auto space-y-6">
            
            {/* Header */}
            <div>
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Welcome Back
              </h1>
              <p className="text-xs text-slate-500 mt-1 font-medium">
                Enter your credentials to access your conversion dashboard
              </p>
            </div>

            {infoMessage && (
              <StatusAlert
                type="info"
                message={infoMessage}
                onDismiss={() => setInfoMessage('')}
              />
            )}

            {error && (
              <StatusAlert
                type="error"
                message={error}
                onDismiss={() => setError('')}
              />
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              <Input
                label="Email Address"
                type="email"
                required
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                icon={<Mail className="w-4 h-4" />}
                autoComplete="email"
              />

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                    Password
                  </label>
                  <Link
                    href="/forgot-password"
                    className="text-xs font-semibold text-brand-600 hover:text-brand-700"
                  >
                    Forgot Password?
                  </Link>
                </div>

                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none flex items-center justify-center">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-white text-sm text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 pl-10 pr-10 py-2.5 transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                variant="primary"
                size="md"
                className="w-full mt-3"
                loading={loading}
                iconRight={<ArrowRight className="w-4 h-4" />}
              >
                Sign In to Account
              </Button>
            </form>

            <div className="pt-4 border-t border-slate-100 text-center text-xs text-slate-500">
              New to Kangra Hub?{' '}
              <Link
                href={`/signup${nextUrl ? `?redirect=${encodeURIComponent(nextUrl)}` : ''}`}
                className="font-bold text-brand-600 hover:text-brand-700"
              >
                Create Free Account (50 Pgs/Day)
              </Link>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-[60vh] flex items-center justify-center text-xs text-slate-400">Loading sign in...</div>}>
      <LoginForm />
    </Suspense>
  );
}
