'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Shield, Lock, Eye, EyeOff, CheckCircle2, ArrowLeft, ArrowRight, KeyRound } from 'lucide-react';
import { getSupabaseClient } from '@/lib/supabaseClient';
import { Button } from '@/components/ui/Button';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { Badge } from '@/components/ui/Badge';

function AdminResetPasswordForm() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      setError('Supabase authentication client is not configured. Please ensure environment variables are configured.');
      return;
    }

    // Check if recovery session is active or wait for auth state change
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setSessionReady(true);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' || session) {
        setSessionReady(true);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!password || !confirmPassword) {
      setError('Please provide and confirm your new password.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters in length.');
      return;
    }

    if (password !== confirmPassword) {
      setError('The passwords do not match. Please verify and try again.');
      return;
    }

    const supabase = getSupabaseClient();
    if (!supabase) {
      setError('Supabase authentication client is not configured.');
      return;
    }

    setLoading(true);
    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password: password,
      });

      if (updateError) {
        setError(updateError.message || 'Failed to update administrator password.');
        return;
      }

      setSuccess(true);
    } catch (err: any) {
      setError(err?.message || 'An unexpected error occurred while updating the password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 sm:p-6 lg:p-8 text-slate-100 selection:bg-brand-500 selection:text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-brand-950/40 via-slate-950 to-slate-950 pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Header Branding */}
        <div className="text-center mb-6 space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-purple-600 text-white shadow-elevated shadow-brand-500/20 mb-2 border border-white/10">
            <KeyRound className="w-7 h-7" />
          </div>
          <div className="flex items-center justify-center gap-2">
            <span className="text-xs font-bold uppercase tracking-widest text-brand-400">Security Recovery</span>
            <Badge variant="purple" size="sm">Staff Only</Badge>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white">
            Set New Admin Password
          </h1>
          <p className="text-xs text-slate-400 max-w-xs mx-auto">
            Create a strong new password for your authoritative administrator account.
          </p>
        </div>

        {/* Card */}
        <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl shadow-black/60 space-y-5 animate-slideUp">
          {error && (
            <StatusAlert
              type="error"
              message={error}
              onDismiss={() => setError('')}
            />
          )}

          {success ? (
            <div className="text-center py-4 space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">Password Updated Successfully</h3>
                <p className="text-xs text-slate-400 leading-relaxed max-w-xs mx-auto">
                  Your administrator credentials have been securely updated. You can now access the Admin Console with your new password.
                </p>
              </div>
              <div className="pt-2">
                <Link href="/admin/login">
                  <Button
                    variant="primary"
                    size="md"
                    className="w-full bg-gradient-to-r from-brand-600 to-purple-600 hover:from-brand-500 hover:to-purple-500 text-white"
                    iconRight={<ArrowRight className="w-4 h-4" />}
                  >
                    Proceed to Admin Login
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleUpdatePassword} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  New Password
                </label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none flex items-center justify-center">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    placeholder="Enter at least 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white placeholder:text-slate-400 rounded-xl pl-10 pr-10 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                    autoComplete="new-password"
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

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Confirm New Password
                </label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none flex items-center justify-center">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    placeholder="Re-enter your new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-white placeholder:text-slate-400 rounded-xl pl-10 pr-4 py-2.5 text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                    autoComplete="new-password"
                    style={{ colorScheme: 'dark', backgroundColor: '#1e293b', color: '#ffffff' }}
                  />
                </div>
              </div>

              <Button
                type="submit"
                variant="primary"
                size="md"
                className="w-full mt-2 bg-gradient-to-r from-brand-600 to-purple-600 hover:from-brand-500 hover:to-purple-500 text-white shadow-card shadow-brand-600/30"
                loading={loading}
                iconRight={<ArrowRight className="w-4 h-4" />}
              >
                Update Password & Secure Account
              </Button>
            </form>
          )}
        </div>

        {/* Back Link */}
        <div className="text-center mt-6">
          <Link
            href="/admin/login"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Return to Admin Login
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function AdminResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-xs text-slate-400">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span>Loading recovery gateway...</span>
        </div>
      </div>
    }>
      <AdminResetPasswordForm />
    </Suspense>
  );
}
