'use client';

import React, { useState, Suspense } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { Shield, Lock, Mail, Eye, EyeOff, ArrowRight, ShieldCheck, ArrowLeft, KeyRound, CheckCircle2 } from 'lucide-react';
import { setAuthToken, clearAuthToken, adminLogin, verifyAdmin, adminForgotPassword } from '@/lib/api';
import { getSupabaseClient, sendAdminPasswordReset } from '@/lib/supabaseClient';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { Badge } from '@/components/ui/Badge';

function AdminLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextUrl = searchParams.get('next') || searchParams.get('redirect');
  const isExpired = searchParams.get('expired') === 'true';
  const isUnauthorized = searchParams.get('error') === 'unauthorized' || searchParams.get('denied') === 'true';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resetSuccess, setResetSuccess] = useState('');

  // Handle session expired or unauthorized query parameters
  React.useEffect(() => {
    if (isExpired) {
      setError('Your admin session has expired. Please sign in again.');
    } else if (isUnauthorized) {
      setError('Administrator access is required.');
    }
  }, [isExpired, isUnauthorized]);

  // Password reset modal / section state
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetModalError, setResetModalError] = useState('');

  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setResetSuccess('');

    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setError('Please provide both administrator email and password.');
      return;
    }

    setLoading(true);

    try {
      const supabase = getSupabaseClient();
      let token: string | null = null;
      let isAdminVerified = false;

      // 1. Try direct Supabase authentication if client keys are present
      if (supabase) {
        try {
          const { data: authData, error: authError } = await supabase.auth.signInWithPassword({
            email: cleanEmail,
            password: password,
          });

          if (!authError && authData.session?.access_token) {
            token = authData.session.access_token;
            setAuthToken(token, true);
            try {
              const check = await verifyAdmin();
              if (check && check.is_admin) {
                isAdminVerified = true;
              } else {
                await supabase.auth.signOut();
                clearAuthToken();
                token = null;
              }
            } catch {
              await supabase.auth.signOut();
              clearAuthToken();
              token = null;
            }
          }
        } catch {
          // Continue to backend fallback
        }
      }

      // 2. Fallback to backend authentication proxy (supports local dev credentials & server Supabase verification)
      if (!isAdminVerified) {
        const data = await adminLogin(cleanEmail, password);
        if (data && data.is_admin && data.token) {
          token = data.token;
          setAuthToken(token, true);
          isAdminVerified = true;
        } else {
          clearAuthToken();
          setError('Access denied. This login portal is restricted to authorized administrators.');
          setLoading(false);
          return;
        }
      }

      if (isAdminVerified && token) {
        let destination = '/admin';
        if (nextUrl && nextUrl.startsWith('/admin') && !nextUrl.startsWith('/admin/login')) {
          try {
            const parsed = new URL(nextUrl, 'http://localhost');
            parsed.searchParams.delete('expired');
            parsed.searchParams.delete('error');
            parsed.searchParams.delete('denied');
            const searchPart = parsed.searchParams.toString();
            destination = parsed.pathname + (searchPart ? `?${searchPart}` : '');
          } catch {
            destination = nextUrl.split('?')[0];
          }
        }
        router.push(destination);
      }
    } catch (err: any) {
      setError('Access denied. This login portal is restricted to authorized administrators.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetModalError('');
    const targetEmail = (resetEmail || email).trim();
    if (!targetEmail) {
      setResetModalError('Please enter your administrator email address.');
      return;
    }

    setResetLoading(true);
    try {
      // First attempt via backend recovery endpoint which logs recovery dispatch to kangrahub@gmail.com
      const res = await adminForgotPassword(targetEmail);
      if (res && res.success) {
        setResetSuccess(res.message);
        setShowForgotModal(false);
      } else {
        setResetModalError(res?.message || 'Failed to dispatch password reset request.');
      }
    } catch (backendErr: any) {
      // Fallback to client-side Supabase if configured
      try {
        const clientRes = await sendAdminPasswordReset(targetEmail);
        if (clientRes.success) {
          setResetSuccess(clientRes.message);
          setShowForgotModal(false);
          return;
        }
      } catch {}
      setResetModalError(backendErr?.message || 'Failed to dispatch password reset request.');
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 sm:p-6 lg:p-8 text-slate-100 selection:bg-brand-500 selection:text-white">
      {/* Background radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-brand-950/40 via-slate-950 to-slate-950 pointer-events-none" />

      <div className="relative w-full max-w-md">
        
        {/* Top Header Card Branding */}
        <div className="text-center mb-6 space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-purple-600 text-white shadow-lg shadow-brand-500/20 mb-2 border border-white/10">
            <Shield className="w-7 h-7" />
          </div>
          <div className="flex items-center justify-center gap-2">
            <span className="text-xs font-bold uppercase tracking-widest text-brand-400">Kangra Hub Admin</span>
            <Badge variant="purple" size="sm">Staff Only</Badge>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white">
            Administrator Sign In
          </h1>
          <p className="text-xs text-slate-400 max-w-xs mx-auto">
            Authorized administrative personnel only. All access attempts are cryptographically audited.
          </p>
        </div>

        {/* Form Container */}
        <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl shadow-black/60 space-y-5">
          
          {error && (
            <StatusAlert
              type="error"
              message={error}
              onDismiss={() => setError('')}
            />
          )}

          {resetSuccess && (
            <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{resetSuccess}</span>
            </div>
          )}

          <form onSubmit={handleAdminLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Admin Email Address
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none flex items-center justify-center">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  placeholder="Enter your admin email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-white placeholder:text-slate-500 rounded-xl pl-10 pr-4 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  autoComplete="username"
                  style={{ colorScheme: 'dark', backgroundColor: '#1e293b', color: '#ffffff' }}
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setResetEmail(email);
                    setShowForgotModal(true);
                  }}
                  className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
                >
                  Forgot password?
                </button>
              </div>

              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none flex items-center justify-center">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-white placeholder:text-slate-500 rounded-xl pl-10 pr-10 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  autoComplete="current-password"
                  style={{ colorScheme: 'dark', backgroundColor: '#1e293b', color: '#ffffff' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 p-1"
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
              className="w-full mt-2 bg-gradient-to-r from-brand-600 to-purple-600 hover:from-brand-500 hover:to-purple-500 text-white shadow-md shadow-brand-600/30"
              loading={loading}
              iconRight={<ArrowRight className="w-4 h-4" />}
            >
              Verify & Enter Console
            </Button>
          </form>
        </div>

        {/* Back Link */}
        <div className="text-center mt-6">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Return to Public Portal
          </Link>
        </div>

      </div>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="relative w-full max-w-sm bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-brand-500/20 text-brand-400 flex items-center justify-center">
                <KeyRound className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Reset Admin Password</h3>
                <p className="text-[11px] text-slate-400">Authoritative Administrator Recovery</p>
              </div>
            </div>

            {/* Security Notice Box */}
            <div className="p-3 bg-slate-800/80 border border-slate-700/60 rounded-xl space-y-1.5 text-xs">
              <p className="text-[11px] text-slate-300 leading-relaxed">
                Enter your registered administrator email address. If an active administrator account exists, recovery instructions will be dispatched to the verified recovery contact.
              </p>
            </div>

            {resetModalError && (
              <StatusAlert
                type="error"
                message={resetModalError}
                onDismiss={() => setResetModalError('')}
              />
            )}

            <form onSubmit={handleForgotPassword} className="space-y-3">
              <div>
                <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Admin Login Email
                </label>
                <input
                  type="email"
                  required
                  placeholder="Enter your admin email"
                  value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-white placeholder:text-slate-500 rounded-xl px-3.5 py-2 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                  style={{ colorScheme: 'dark', backgroundColor: '#1e293b', color: '#ffffff' }}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowForgotModal(false)}
                  disabled={resetLoading}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  loading={resetLoading}
                >
                  Send Reset Link
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminLoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-xs text-slate-400">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading admin gateway...</span>
        </div>
      </div>
    }>
      <AdminLoginForm />
    </Suspense>
  );
}
