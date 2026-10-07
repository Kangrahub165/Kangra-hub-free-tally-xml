'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { Lock, Eye, EyeOff, CheckCircle2, ArrowRight, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { getSupabaseClient } from '@/lib/supabaseClient';

export default function ResetPasswordPage() {
  const router = useRouter();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match. Please ensure both passwords are identical.');
      return;
    }

    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters in length.');
      return;
    }

    setLoading(true);

    try {
      const supabase = getSupabaseClient();
      if (!supabase) {
        throw new Error('Authentication backend is unavailable. Please try again.');
      }

      const { error: updateErr } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (updateErr) {
        throw updateErr;
      }

      setSuccess(true);
      setTimeout(() => {
        router.push('/login?message=Password%20updated%20successfully.%20Please%20log%20in.');
      }, 2000);
    } catch (err: any) {
      const msg = err.message || 'Unable to update password. Your reset link may have expired.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-4 sm:p-6 lg:p-10 bg-navy-50 gradient-surface">
      <div className="w-full max-w-md bg-white glass-card rounded-3xl border border-navy-200/60 shadow-modal p-6 sm:p-8 animate-slideUp">
        
        {/* Brand Header */}
        <div className="text-center mb-6">
          <Link href="/" className="inline-block mb-3 focus:outline-none">
            <Image
              src="/logo.webp"
              alt="Kangra Hub — Sales & Purchase"
              width={48}
              height={48}
              className="mx-auto rounded-2xl shadow-glow-brand"
            />
          </Link>
          <h1 className="text-2xl font-black text-navy-900 tracking-tight">
            Set New Password
          </h1>
          <p className="text-xs text-navy-500 mt-1">
            Choose a strong, secure password for your Kangra Hub account
          </p>
        </div>

        {error && (
          <div className="mb-4">
            <StatusAlert type="error" message={error} onDismiss={() => setError('')} />
          </div>
        )}

        {success ? (
          <div className="text-center py-6 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-glow-brand">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-bold text-navy-900">Password Updated!</h3>
              <p className="text-xs text-navy-600">
                Your password has been changed successfully. Redirecting you to login...
              </p>
            </div>
            <div className="pt-2">
              <Link href="/login">
                <Button variant="primary" size="sm" className="w-full">
                  Continue to Sign In
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleUpdatePassword} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-navy-700 uppercase tracking-wider mb-1.5">
                New Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-navy-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="At least 6 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-white text-sm text-navy-900 rounded-xl border border-navy-300/60 pl-10 pr-10 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-navy-400 hover:text-navy-600"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-navy-700 uppercase tracking-wider mb-1.5">
                Confirm New Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-navy-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="Re-enter your new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-white text-sm text-navy-900 rounded-xl border border-navy-300/60 pl-10 pr-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                />
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full mt-2"
              loading={loading}
              iconRight={<ArrowRight className="w-4 h-4" />}
            >
              Update Password
            </Button>

            <div className="text-center pt-2">
              <Link href="/login" className="text-xs text-navy-500 hover:text-navy-800">
                Cancel and return to Sign In
              </Link>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}
