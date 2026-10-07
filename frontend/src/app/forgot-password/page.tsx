'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Mail, CheckCircle2, ArrowLeft, ArrowRight, KeyRound } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { getSupabaseClient } from '@/lib/supabaseClient';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setError('Please enter your email address.');
      return;
    }

    setLoading(true);

    try {
      const supabase = getSupabaseClient();
      if (!supabase) {
        throw new Error('Authentication service currently unavailable. Please try again.');
      }

      const redirectUrl = typeof window !== 'undefined'
        ? `${window.location.origin}/reset-password`
        : 'https://tally.kangrahub.com/reset-password';

      const { error: resetErr } = await supabase.auth.resetPasswordForEmail(cleanEmail, {
        redirectTo: redirectUrl,
      });

      if (resetErr) {
        throw resetErr;
      }

      setSubmitted(true);
    } catch (err: any) {
      const msg = err.message || 'Unable to send recovery email. Please check your email and try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-4 sm:p-6 lg:p-10 bg-navy-50 gradient-surface">
      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-2 bg-white glass-card rounded-3xl border border-navy-200/60 shadow-modal overflow-hidden animate-slideUp">
        
        {/* Left Value Prop Hero */}
        <div className="hidden lg:flex gradient-hero p-8 flex-col justify-between text-white relative">
          <div className="absolute inset-0 bg-[radial-gradient(#38bdf810_1px,transparent_1px)] bg-[size:16px_16px] pointer-events-none" />
          <div className="relative z-10 space-y-6">
            <Link href="/" className="flex items-center gap-3 inline-flex">
              <div className="relative w-9 h-9 flex-shrink-0">
                <Image src="/logo.webp" alt="Kangra Hub" width={36} height={36} className="rounded-xl shadow-glow-brand" />
              </div>
              <div className="flex flex-col">
                <span className="font-extrabold text-base tracking-tight text-white leading-tight">Kangra Hub</span>
                <span className="text-[10px] font-bold text-brand-300 tracking-wider uppercase">Sales & Purchase</span>
              </div>
            </Link>
            <div className="space-y-3 pt-4">
              <h2 className="text-xl font-extrabold text-white tracking-tight leading-snug">Secure Account Recovery</h2>
              <p className="text-xs text-navy-300 leading-relaxed">Follow the steps to regain access to your Kangra Hub account.</p>
            </div>
          </div>
        </div>

        {/* Right Form Column */}
        <div className="p-6 sm:p-10 flex flex-col justify-center">
          <div className="max-w-sm w-full mx-auto">
            {/* Brand Icon Header */}
            <div className="text-center mb-8">
              <Link href="/" className="inline-block mb-3.5 focus:outline-none">
                <Image
                  src="/logo.webp"
                  alt="Kangra Hub"
                  width={48}
                  height={48}
                  className="mx-auto rounded-2xl shadow-glow-brand"
                />
              </Link>
              <h1 className="text-2xl font-black text-navy-900 tracking-tight">
                Reset Your Password
              </h1>
              <p className="text-xs text-navy-500 mt-1">
                We will email you instructions to safely reset your credentials
              </p>
            </div>

            {error && (
              <div className="mb-4">
                <StatusAlert type="error" message={error} onDismiss={() => setError('')} />
              </div>
            )}

            {submitted ? (
              <div className="text-center py-6 space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-glow-brand">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-navy-900">Email Dispatched</h3>
                  <p className="text-xs text-navy-600 leading-relaxed max-w-xs mx-auto">
                    If an account is associated with <strong className="text-navy-900">{email}</strong>, you will receive a secure password recovery link shortly.
                  </p>
                </div>
                <div className="pt-2">
                  <Link href="/login">
                    <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
                      Back to Sign In
                    </Button>
                  </Link>
                </div>
              </div>
            ) : (
              <form onSubmit={handleReset} className="space-y-4">
                <Input
                  label="Email Address"
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  icon={<Mail className="w-4 h-4" />}
                />

                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  className="w-full"
                  loading={loading}
                  iconRight={<ArrowRight className="w-4 h-4" />}
                >
                  Send Recovery Link
                </Button>

                <div className="text-center pt-2">
                  <Link href="/login" className="text-xs font-semibold text-brand-600 hover:underline">
                    Back to Sign In
                  </Link>
                </div>
              </form>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
