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
                <span className="text-[10px] font-bold text-brand-300 tracking-wider uppercase">Free Tally XML</span>
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
              className="w-full mt-2"
              loading={loading}
              iconRight={<ArrowRight className="w-4 h-4" />}
            >
              Send Reset Link
            </Button>

            <div className="text-center pt-3 border-t border-navy-100 flex flex-col gap-2">
              <Link
                href="/login"
                className="text-xs font-semibold text-navy-500 hover:text-navy-800 inline-flex items-center justify-center gap-1.5 transition-colors"
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
      </div>
    </div>
  );
}
