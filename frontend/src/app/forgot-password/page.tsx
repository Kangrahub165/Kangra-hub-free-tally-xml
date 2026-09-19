'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Mail, CheckCircle2, ArrowLeft, ArrowRight, KeyRound } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card } from '@/components/ui/Card';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleReset = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setSubmitted(true);
    }, 450);
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-4 sm:p-6 bg-slate-50">
      <div className="max-w-md w-full bg-white p-7 sm:p-9 rounded-3xl border border-slate-200 shadow-elevated">
        
        {/* Brand Icon Header */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-block mb-3.5 focus:outline-none">
            <Image
              src="/logo.webp"
              alt="Kangra Hub"
              width={48}
              height={48}
              className="mx-auto rounded-2xl shadow-xs"
            />
          </Link>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Reset Your Password
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            We will email you instructions to safely reset your credentials
          </p>
        </div>

        {submitted ? (
          <div className="text-center py-6 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-slate-900">Email Dispatched</h3>
              <p className="text-xs text-slate-600 leading-relaxed max-w-xs mx-auto">
                If an account is associated with <strong className="text-slate-900">{email}</strong>, you will receive a secure password recovery link shortly.
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
              className="w-full mt-2"
              loading={loading}
              iconRight={<ArrowRight className="w-4 h-4" />}
            >
              Send Reset Link
            </Button>

            <div className="text-center pt-3 border-t border-slate-100 flex flex-col gap-2">
              <Link
                href="/login"
                className="text-xs font-semibold text-slate-500 hover:text-slate-800 inline-flex items-center justify-center gap-1.5 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Return to Login
              </Link>
              <Link
                href="/recover"
                className="text-[11px] font-semibold text-brand-600 hover:text-brand-700 hover:underline"
              >
                Lost access to both email & phone? Request Account Recovery
              </Link>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}
