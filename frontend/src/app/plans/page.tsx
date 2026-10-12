'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  Check, 
  Sparkles, 
  ShieldCheck, 
  Zap, 
  ArrowRight, 
  Lock, 
  FileCheck,
  Building2,
  Clock,
  HelpCircle,
  AlertCircle
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthProvider';
import { getSubscriptionPlans, SubscriptionPlanItem } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';

export default function PlansPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();
  const [plans, setPlans] = useState<SubscriptionPlanItem[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [fetchError, setFetchError] = useState('');

  // PRD Item 1: Require login before users can view subscription plans and their details.
  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.push('/login?redirect=/plans');
      return;
    }

    // Fetch authoritative subscription plans from backend
    getSubscriptionPlans()
      .then((data) => {
        if (data && data.plans) {
          setPlans(data.plans);
        }
      })
      .catch((err: any) => {
        if (err.status === 401) {
          router.push('/login?redirect=/plans');
        } else {
          setFetchError(err.message || 'Unable to load subscription plans. Please refresh.');
        }
      })
      .finally(() => {
        setLoadingPlans(false);
      });
  }, [isLoading, isAuthenticated, router]);

  // If auth is loading or unauthenticated, show clean auth redirect screen
  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-14 h-14 bg-brand-50 border border-brand-200 text-brand-600 rounded-2xl flex items-center justify-center mb-4 shadow-sm animate-pulse">
          <Lock className="w-7 h-7" />
        </div>
        <h2 className="text-xl font-extrabold text-slate-900 mb-2">Member Authentication Required</h2>
        <p className="text-sm text-slate-600 max-w-md mb-6 leading-relaxed">
          Please log in to your Kangra Hub account to view verified subscription plans, firm pricing, and bill limits.
        </p>
        <Link href="/login?redirect=/plans">
          <Button variant="primary" size="md" className="font-bold">
            Log In to View Plans
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-12">
        
        {/* Header Banner */}
        <div className="text-center space-y-3.5 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-50 border border-brand-200 text-brand-700 text-xs font-bold tracking-wide">
            <Sparkles className="w-3.5 h-3.5 text-brand-600" />
            OFFICIAL SUBSCRIPTION PLANS
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-900 tracking-tight">
            Flexible Plans for Every Firm
          </h1>
          <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
            Choose the right capacity for your accounting workflow. Straightforward pricing per firm with guaranteed 30-day validity.
          </p>
        </div>

        {fetchError && (
          <div className="p-4 bg-amber-50 border border-amber-200 text-amber-800 rounded-2xl flex items-center gap-3 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-amber-600" />
            <span>{fetchError}</span>
          </div>
        )}

        {/* Plans Grid */}
        {loadingPlans ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-pulse">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-96 bg-white rounded-3xl border border-slate-200 p-8 space-y-6" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 items-stretch">
            {plans.map((p) => {
              const isPopular = p.id === 'standard';
              const isPremium = p.id === 'premium';

              return (
                <div
                  key={p.id}
                  className={`relative flex flex-col justify-between bg-white rounded-3xl p-7 sm:p-8 transition-all duration-300 ${
                    isPopular
                      ? 'border-2 border-brand-500 shadow-xl shadow-brand-500/10 ring-4 ring-brand-500/5'
                      : isPremium
                      ? 'border-2 border-purple-500 shadow-xl shadow-purple-500/10'
                      : 'border border-slate-200 shadow-card hover:border-slate-300'
                  }`}
                >
                  {/* Badge */}
                  {p.badge && (
                    <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                      <span className={`px-3 py-1 rounded-full text-[11px] font-black tracking-wide uppercase shadow-sm ${
                        isPopular
                          ? 'bg-brand-600 text-white'
                          : isPremium
                          ? 'bg-purple-600 text-white'
                          : 'bg-slate-800 text-white'
                      }`}>
                        {p.badge}
                      </span>
                    </div>
                  )}

                  <div className="space-y-6">
                    {/* Plan Heading */}
                    <div>
                      <h3 className="text-xl font-black text-slate-900 tracking-tight">{p.name}</h3>
                      <p className="text-xs text-slate-500 mt-1.5 min-h-[32px]">{p.tagline}</p>
                    </div>

                    {/* Pricing Display — EXACT AMOUNT, ZERO TAX LABELS */}
                    <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-1">
                      <div className="flex items-baseline gap-1">
                        <span className="text-lg font-bold text-slate-700">₹</span>
                        <span className="text-4xl font-black text-slate-900 tracking-tight">
                          {Math.round(p.price_inr)}
                        </span>
                        <span className="text-xs font-semibold text-slate-500 ml-1">/ month</span>
                      </div>
                      <div className="text-[11px] font-bold text-brand-700">
                        {p.bills_limit === -1 ? 'Unlimited bills included' : `${p.bills_limit} bills included per month`}
                      </div>
                    </div>

                    {/* Limit Highlight Pill */}
                    <div className="flex items-center gap-2 p-3 bg-slate-50/80 rounded-xl border border-slate-200/80 text-xs">
                      <FileCheck className="w-4 h-4 text-brand-600 flex-shrink-0" />
                      <div className="font-semibold text-slate-700">
                        Monthly Limit:{' '}
                        <strong className="text-slate-900 font-bold">
                          {p.bills_limit === -1 ? 'Unlimited Bills' : `${p.bills_limit} Bills`}
                        </strong>
                      </div>
                    </div>

                    {/* Features List */}
                    <div className="space-y-3 pt-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Included Features</span>
                      <ul className="space-y-2.5">
                        {p.features.map((feat, idx) => (
                          <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-600">
                            <div className="w-4 h-4 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                              <Check className="w-3 h-3 stroke-[3]" />
                            </div>
                            <span className="leading-snug">{feat}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* CTA Button */}
                  <div className="pt-8 mt-auto">
                    <Link href={`/checkout?plan=${p.id}`} className="block w-full">
                      <Button
                        variant={isPopular ? 'primary' : 'outline'}
                        size="lg"
                        className={`w-full font-bold justify-center rounded-2xl text-xs sm:text-sm py-3.5 shadow-sm transition-all duration-200 ${
                          isPopular
                            ? 'bg-brand-600 hover:bg-brand-500 text-white shadow-brand-500/25'
                            : isPremium
                            ? 'bg-purple-600 hover:bg-purple-500 text-white border-transparent shadow-purple-500/25'
                            : 'border-slate-300 text-slate-700 hover:bg-slate-50'
                        }`}
                        iconRight={<ArrowRight className="w-4 h-4" />}
                      >
                        Choose {p.name}
                      </Button>
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Security & Guarantee Strip */}
        <div className="p-6 bg-white rounded-3xl border border-slate-200 shadow-card grid grid-cols-1 sm:grid-cols-3 gap-6 text-center sm:text-left">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">100% Secure Checkout</h4>
              <p className="text-[11px] text-slate-500">Razorpay verified server verification</p>
            </div>
          </div>
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">30-Day Full Validity</h4>
              <p className="text-[11px] text-slate-500">Snapped to 11:59 PM IST midnight rule</p>
            </div>
          </div>
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center flex-shrink-0">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">Instant Activation</h4>
              <p className="text-[11px] text-slate-500">Bill limits applied to firm immediately</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
