'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  ShieldCheck,
  CheckCircle2,
  Lock,
  ArrowRight,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Check,
  HelpCircle,
  ExternalLink,
  ChevronRight,
  CreditCard,
  Phone,
  Mail,
  User,
  Edit2,
  Calendar,
  Layers,
  ArrowLeft
} from 'lucide-react';
import { GoldTick } from '@/components/ui/GoldTick';
import { useAuth } from '@/components/auth/AuthProvider';
import {
  getMySubscription,
  createPaymentOrder,
  verifyPayment,
  getPaymentConfig,
  PaymentConfig,
  StaffMembershipResponse
} from '@/lib/api';

export default function CheckoutPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();

  const [loading, setLoading] = useState(true);
  const [membershipData, setMembershipData] = useState<StaffMembershipResponse | null>(null);
  const [gatewayConfig, setGatewayConfig] = useState<PaymentConfig | null>(null);
  const [gatewayKeyId, setGatewayKeyId] = useState<string | null>(null);

  // Prefilled user details state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [isEditingDetails, setIsEditingDetails] = useState(false);

  // Payment states
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [paymentSuccess, setPaymentSuccess] = useState<{
    paymentId: string;
    expiryWording: string;
  } | null>(null);

  // Fetch current user subscription status and payment configuration
  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      try {
        const [sub, pConfig] = await Promise.all([
          getMySubscription().catch(() => null),
          getPaymentConfig().catch(() => null)
        ]);
        if (isMounted) {
          if (sub) setMembershipData(sub);
          if (pConfig) {
            setGatewayConfig(pConfig);
            if (pConfig.razorpay_key_id) {
              setGatewayKeyId(pConfig.razorpay_key_id);
            }
          }
        }
      } catch (err) {
        console.warn('Failed to fetch checkout prerequisites:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    if (!authLoading) {
      loadData();
    }

    return () => {
      isMounted = false;
    };
  }, [authLoading, isAuthenticated]);

  // Sync user profile into form inputs (pre-fill once or when user changes without overwriting manual edits)
  const [hasPrefilled, setHasPrefilled] = useState(false);
  useEffect(() => {
    if (user && !hasPrefilled) {
      const initialName = user.fullName || (user as any).user_metadata?.full_name || (user as any).user_metadata?.name || user.email?.split('@')[0] || 'Member';
      const initialEmail = user.email || '';
      const initialPhone = user.mobileNumber || (user as any).user_metadata?.mobile_number || (user as any).user_metadata?.phone || (user as any).phone || '';
      if (!name) setName(initialName);
      if (!email) setEmail(initialEmail);
      if (!phone && initialPhone) setPhone(initialPhone);
      if (initialPhone || initialEmail) setHasPrefilled(true);
    }
  }, [user, hasPrefilled, name, email, phone]);

  // Validation
  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const isPhoneValid = /^[0-9+\s\-()]{10,15}$/.test(phone.trim());
  const isFormValid = Boolean(name.trim() && isEmailValid && isPhoneValid);

  // Compute preview dates (PRD Section 2.6: max(today, current expiry) + 30 days)
  const currentExpiry = membershipData?.membership?.membership_expires_at;
  const isCurrentlyStaff = membershipData?.is_staff || false;

  const getPreviewDates = () => {
    const now = new Date();
    let baseDate = now;
    let isRenewal = false;

    if (currentExpiry) {
      const expDate = new Date(currentExpiry);
      if (expDate > now) {
        baseDate = expDate;
        isRenewal = true;
      }
    }

    const newExp = new Date(baseDate);
    newExp.setDate(newExp.getDate() + 30);

    const fmt: Intl.DateTimeFormatOptions = { day: '2-digit', month: 'short', year: 'numeric' };
    return {
      fromDate: now.toLocaleDateString('en-IN', fmt),
      toDate: newExp.toLocaleDateString('en-IN', fmt),
      isRenewal: isRenewal || Boolean(currentExpiry),
    };
  };

  const preview = getPreviewDates();
  const isTestMode = Boolean(gatewayKeyId?.startsWith('rzp_test_') || gatewayConfig?.is_test_mode);

  function normalizePhone(p?: string): string | undefined {
    if (!p) return undefined;
    const d = p.replace(/\D/g, '').replace(/^(91|0)/, '');
    return d.length === 10 ? `+91${d}` : undefined;
  }

  // Load Razorpay checkout.js dynamically
  const loadRazorpay = (): Promise<boolean> => {
    return new Promise((resolve) => {
      if (typeof window === 'undefined') return resolve(false);
      if ((window as any).Razorpay) return resolve(true);

      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  };

  // Launch prefilled checkout (PRD Addendum 4 Section 2.3 & 2.4)
  const handleProceedToPay = async () => {
    if (!isFormValid || isProcessing) return;

    setPaymentError(null);
    setIsProcessing(true);

    let watchdogTimer: NodeJS.Timeout | null = null;

    // 15-second watchdog timer (PRD Addendum 4 Section 2.5 #3)
    watchdogTimer = setTimeout(() => {
      setIsProcessing(false);
      setPaymentError(
        'The payment window did not open. If you have an ad blocker or popup blocker enabled, please disable it and try again.'
      );
    }, 15000);

    try {
      // 1. Create order on authoritative server (PRD Section 2.6 & 2.7)
      const order = await createPaymentOrder({
        planId: 'gold_monthly',
        customer_name: name.trim(),
        customer_email: email.trim(),
        customer_phone: phone.trim(),
      });
      if (!order || !order.orderId) {
        throw new Error('Failed to obtain a valid order ID from the payment server.');
      }

      if (order.keyId) {
        setGatewayKeyId(order.keyId);
      }

      // 2. Load script safely
      const loaded = await loadRazorpay();
      if (!loaded) {
        throw new Error('Could not load Razorpay payment gateway. Please check your internet connection or disable ad blockers.');
      }

      // 3. Prepare prefill and public assets
      const safeContact = normalizePhone(phone.trim());
      const safeLogo = typeof window !== 'undefined' ? `${window.location.origin}/logo.png` : '/logo.png';

      // 4. Open Razorpay checkout with PREFILLED details (skips user details step)
      const rzpOptions: any = {
        key: order.keyId,
        order_id: order.orderId,
        amount: order.amount,
        currency: order.currency || 'INR',
        name: 'Kangra Hub',
        description: preview.isRenewal ? 'Kangra Hub Gold Renewal' : 'Kangra Hub Gold Membership',
        image: safeLogo,
        prefill: {
          name: name.trim(),
          email: email.trim(),
          ...(safeContact ? { contact: safeContact } : {}),
        },
        notes: {
          plan_id: 'gold_monthly',
          user_id: user?.id || 'guest',
          customer_name: name.trim(),
          customer_email: email.trim(),
          customer_phone: phone.trim(),
        },
        theme: {
          color: '#1d4ed8',
          backdrop_color: 'rgba(15,23,42,0.55)',
        },
        retry: {
          enabled: true,
          max_count: 3,
        },
        modal: {
          backdropclose: false,
          confirm_close: true,
          ondismiss: () => {
            if (watchdogTimer) clearTimeout(watchdogTimer);
            setIsProcessing(false);
          },
        },
        handler: async (response: any) => {
          if (watchdogTimer) clearTimeout(watchdogTimer);
          try {
            setIsProcessing(true);
            // Authoritative server verification (PRD Section 2.7)
            const verifyRes = await verifyPayment({
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_signature: response.razorpay_signature,
              customer_name: name.trim(),
              customer_email: email.trim(),
              customer_phone: phone.trim(),
            });

            if (verifyRes.ok || verifyRes.success) {
              setPaymentSuccess({
                paymentId: response.razorpay_payment_id,
                expiryWording:
                  verifyRes.display_wording ||
                  `Valid until ${preview.toDate}`,
              });
            } else {
              setPaymentError(verifyRes.message || 'Payment received but confirmation is pending. Please contact support.');
            }
          } catch (err: any) {
            setPaymentError(
              err.message ||
                'Payment verification encountered an issue. If amount was debited, your membership will activate automatically.'
            );
          } finally {
            setIsProcessing(false);
          }
        },
      };

      const rzp = new (window as any).Razorpay(rzpOptions);

      rzp.on('payment.failed', (e: any) => {
        if (watchdogTimer) clearTimeout(watchdogTimer);
        setIsProcessing(false);
        console.error('[Razorpay Payment Failed]:', {
          code: e.error?.code,
          description: e.error?.description,
          source: e.error?.source,
          step: e.error?.step,
          reason: e.error?.reason,
          metadata: e.error?.metadata
        });
        setPaymentError(
          e.error?.description || e.error?.reason || 'Payment failed or was cancelled. Please try again.'
        );
      });

      rzp.open();
    } catch (err: any) {
      if (watchdogTimer) clearTimeout(watchdogTimer);
      setIsProcessing(false);
      console.error('[Checkout Error]:', err);
      setPaymentError(err.message || 'Could not initiate payment. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 pb-24 sm:pb-16 font-sans">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-2 -ml-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              title="Return to home"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-slate-900">
                KANGRA HUB
              </span>
              <span className="text-slate-300">/</span>
              <span className="text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200 flex items-center gap-1">
                <GoldTick size="sm" />
                Gold Checkout
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs font-semibold">
            {isTestMode ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200 shadow-xs" title="Razorpay Sandbox Mode: No real funds will be charged">
                <Sparkles className="w-3.5 h-3.5 text-amber-600" />
                <span>Test Mode</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-xs">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Secure Checkout</span>
              </span>
            )}
            <span className="hidden sm:inline text-slate-400 font-normal">|</span>
            <span className="hidden sm:inline text-slate-600 font-medium">256-bit SSL</span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-[1120px] mx-auto px-4 sm:px-6 pt-6 sm:pt-8">
        {/* Success State */}
        {paymentSuccess ? (
          <div className="max-w-xl mx-auto bg-white rounded-2xl shadow-xl border border-slate-200 p-8 sm:p-10 text-center space-y-6 animate-fadeIn">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-inner">
              <CheckCircle2 className="w-10 h-10" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-black text-slate-900 tracking-tight">
                Membership Activated!
              </h2>
              <p className="text-sm text-slate-600">
                Your Kangra Hub Gold subscription has been activated successfully.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-left text-xs space-y-2">
              <div className="flex justify-between items-center py-1 border-b border-slate-200">
                <span className="text-slate-500 font-medium">Payment ID</span>
                <span className="font-mono font-bold text-slate-900">{paymentSuccess.paymentId}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-200">
                <span className="text-slate-500 font-medium">Status</span>
                <span className="font-bold text-emerald-700 flex items-center gap-1">
                  <GoldTick size="sm" /> Active Verified Gold
                </span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-500 font-medium">Validity</span>
                <span className="font-bold text-slate-900">{paymentSuccess.expiryWording}</span>
              </div>
            </div>

            <div className="pt-2 flex flex-col sm:flex-row gap-3">
              <Link
                href="/sales"
                className="flex-1 py-3.5 px-4 rounded-xl bg-blue-700 hover:bg-blue-800 text-white font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2"
              >
                <span>Convert Sales Invoices</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/purchase"
                className="flex-1 py-3.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-950 text-white font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2"
              >
                <span>Convert Purchase Invoices</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
            {/* LEFT COLUMN (7/12): Order Summary, Benefits, Policy */}
            <div className="lg:col-span-7 space-y-6">
              {/* A. Plan Card */}
              <div className="bg-white rounded-2xl p-6 sm:p-7 border border-slate-200 shadow-sm space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="p-2 rounded-xl bg-amber-400/15 border border-amber-400/30 text-amber-600">
                      <Sparkles className="w-5 h-5" />
                    </span>
                    <div>
                      <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
                        <span>Kangra Hub Gold</span>
                        <GoldTick size="md" />
                      </h1>
                      <p className="text-xs text-slate-500 font-medium mt-0.5">
                        Professional tier for unlimited Tally XML bill conversions
                      </p>
                    </div>
                  </div>

                  <span
                    className={`text-xs font-bold px-3 py-1 rounded-full border ${
                      preview.isRenewal
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    }`}
                  >
                    {preview.isRenewal ? 'Renewal' : 'New Plan'}
                  </span>
                </div>

                {/* Exact Dates & Validity Preview */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center gap-3 text-xs">
                  <Calendar className="w-4 h-4 text-blue-600 flex-shrink-0" />
                  <div className="text-slate-700">
                    <span className="font-semibold text-slate-900">Coverage Window: </span>
                    <span>
                      {preview.fromDate} → until{' '}
                      <strong className="text-slate-900 font-bold">{preview.toDate}</strong> (30 full IST days)
                    </span>
                  </div>
                </div>

                {currentExpiry && (
                  <p className="text-xs text-slate-500 font-medium">
                    Current plan expires on{' '}
                    <strong className="text-slate-800 font-semibold">
                      {new Date(currentExpiry).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </strong>
                    . Remaining time is preserved.
                  </p>
                )}
              </div>

              {/* B. What You Get (2 Columns) */}
              <div className="bg-white rounded-2xl p-6 sm:p-7 border border-slate-200 shadow-sm space-y-4">
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-800">
                  Included Gold Benefits
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    'Unlimited Sales & Purchase bill conversions',
                    'Zero daily quota restrictions or timers',
                    'Official Kangra Hub Verified Gold Tick',
                    'Multi-page smart invoice consolidation',
                    'Dual UOM & Piece multiplier preservation',
                    'Canonical Place of Supply & State resolution',
                    'Direct Tally-ready XML (Vouchers & Masters)',
                    'Ad-free & uninterrupted SaaS workspace',
                  ].map((perk, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 p-2.5 rounded-xl bg-slate-50/80 border border-slate-100 text-xs font-semibold text-slate-800"
                    >
                      <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 text-[10px] font-black mt-0.5">
                        ✓
                      </span>
                      <span>{perk}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* C. Early Renewal Info Banner */}
              <div className="rounded-2xl p-4 sm:p-5 bg-blue-50/90 border border-blue-200 flex items-start gap-3.5 text-xs text-blue-900">
                <ShieldCheck className="w-5 h-5 text-blue-700 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h3 className="font-extrabold text-blue-950 text-sm">
                    Early Renewal Preserves All Remaining Time
                  </h3>
                  <p className="text-blue-800 leading-relaxed font-medium">
                    If you renew before your current expiry date, your remaining days are strictly
                    retained and 30 full calendar days are added after your existing expiry date.
                    You never lose a single hour.
                  </p>
                </div>
              </div>

              {/* D. How It Works (3 Steps) */}
              <div className="bg-white rounded-2xl p-6 sm:p-7 border border-slate-200 shadow-sm space-y-4">
                <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-800">
                  How Activation Works
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 space-y-1.5">
                    <span className="w-6 h-6 rounded-lg bg-blue-700 text-white flex items-center justify-center font-bold text-xs">
                      1
                    </span>
                    <h4 className="font-bold text-xs text-slate-900">Verify Details</h4>
                    <p className="text-[11px] text-slate-600 font-medium leading-relaxed">
                      Confirm your name, email, and mobile number.
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 space-y-1.5">
                    <span className="w-6 h-6 rounded-lg bg-blue-700 text-white flex items-center justify-center font-bold text-xs">
                      2
                    </span>
                    <h4 className="font-bold text-xs text-slate-900">Secure Payment</h4>
                    <p className="text-[11px] text-slate-600 font-medium leading-relaxed">
                      Pay via UPI, Cards, NetBanking, or Wallet through Razorpay.
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 space-y-1.5">
                    <span className="w-6 h-6 rounded-lg bg-blue-700 text-white flex items-center justify-center font-bold text-xs">
                      3
                    </span>
                    <h4 className="font-bold text-xs text-slate-900">Instant Access</h4>
                    <p className="text-[11px] text-slate-600 font-medium leading-relaxed">
                      Plan activates immediately on server + invoice emailed.
                    </p>
                  </div>
                </div>
              </div>

              {/* E. Help & Policy */}
              <div className="bg-white rounded-2xl p-6 sm:p-7 border border-slate-200 shadow-sm space-y-3 text-xs text-slate-600">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="font-bold text-slate-800">Need help with checkout?</span>
                  <div className="flex items-center gap-4">
                    <a
                      href="mailto:support@kangrahub.com"
                      className="text-blue-700 hover:underline font-semibold flex items-center gap-1"
                    >
                      <Mail className="w-3.5 h-3.5" /> support@kangrahub.com
                    </a>
                    <a
                      href="https://wa.me/919805987622"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-700 hover:underline font-semibold flex items-center gap-1"
                    >
                      <Phone className="w-3.5 h-3.5" /> WhatsApp Support
                    </a>
                  </div>
                </div>
                <div className="pt-3 border-t border-slate-100 flex flex-wrap gap-4 text-[11px] text-slate-500">
                  <Link href="/terms" className="hover:text-slate-800 underline">
                    Terms & Conditions
                  </Link>
                  <Link href="/privacy" className="hover:text-slate-800 underline">
                    Privacy Policy
                  </Link>
                  <span>•</span>
                  <span>GST-compliant invoice sent to email upon completion</span>
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN (5/12, Sticky): Payment Card */}
            <div className="lg:col-span-5 lg:sticky lg:top-20 space-y-4">
              <div className="bg-white rounded-2xl p-6 sm:p-7 border border-slate-200 shadow-md space-y-5">
                <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                  <h2 className="text-lg font-black text-slate-900 tracking-tight">Payment Details</h2>
                  <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                    Live Checkout
                  </span>
                </div>

                {/* Paying As (Prefilled from Profile with Edit Action) */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                      Paying as
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsEditingDetails(!isEditingDetails)}
                      className="text-xs font-bold text-blue-700 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
                    >
                      <Edit2 className="w-3 h-3" />
                      {isEditingDetails ? 'Done' : 'Edit'}
                    </button>
                  </div>

                  {isEditingDetails ? (
                    <div className="space-y-3 pt-1">
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">
                          Full Name
                        </label>
                        <input
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          placeholder="Your full name"
                          className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">
                          Email Address (for invoice)
                        </label>
                        <input
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          placeholder="name@example.com"
                          className={`w-full px-3 py-2 rounded-lg border text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none ${
                            !isEmailValid && email ? 'border-rose-500' : 'border-slate-300'
                          }`}
                        />
                        {!isEmailValid && email && (
                          <span className="text-[10px] text-rose-600 font-semibold mt-0.5 block">
                            Please enter a valid email address.
                          </span>
                        )}
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">
                          Mobile Number
                        </label>
                        <input
                          type="tel"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          placeholder="10-digit mobile number"
                          className={`w-full px-3 py-2 rounded-lg border text-xs font-medium focus:ring-2 focus:ring-blue-600 focus:outline-none ${
                            !isPhoneValid && phone ? 'border-rose-500' : 'border-slate-300'
                          }`}
                        />
                        {!isPhoneValid && phone && (
                          <span className="text-[10px] text-rose-600 font-semibold mt-0.5 block">
                            Please enter a valid 10-digit mobile number.
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center gap-2 text-slate-900 font-bold">
                        <User className="w-3.5 h-3.5 text-slate-500" />
                        <span>{name || 'Name not provided'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-700 font-medium">
                        <Mail className="w-3.5 h-3.5 text-slate-500" />
                        <span>{email || 'Email missing'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-700 font-medium">
                        <Phone className="w-3.5 h-3.5 text-slate-500" />
                        <span>{phone || 'Phone missing (required for Razorpay)'}</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Price Breakdown */}
                <div className="space-y-2.5 pt-2">
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>Kangra Hub Gold (30 Days)</span>
                    <span className="font-semibold text-slate-900">₹422.88</span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>GST (18% Included)</span>
                    <span className="font-semibold text-slate-900">₹76.12</span>
                  </div>
                  <div className="pt-3 border-t border-slate-200 flex justify-between items-baseline">
                    <div>
                      <span className="text-sm font-bold text-slate-900">Total Payable</span>
                      <p className="text-[11px] text-slate-500 font-medium">One-time payment • No auto-debit</p>
                    </div>
                    <span className="text-3xl font-black text-slate-900 tracking-tight">₹499.00</span>
                  </div>
                </div>

                {/* Error Banner with Inline Retry Button (PRD Addendum 4 Section 2.5 #1) */}
                {paymentError && (
                  <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 space-y-2.5 animate-fadeIn">
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                      <div className="font-semibold leading-relaxed flex-1">
                        {paymentError}
                      </div>
                    </div>
                    <div className="flex items-center justify-end pt-1">
                      <button
                        type="button"
                        onClick={() => {
                          setPaymentError(null);
                          handleProceedToPay();
                        }}
                        className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Retry Payment</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Validation Note if Missing Info */}
                {!isFormValid && (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2 font-medium">
                    <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                    <span>Please enter a valid name, email, and 10-digit phone number to continue.</span>
                  </div>
                )}

                {/* Primary Pay Button (52px high, full width) */}
                <button
                  type="button"
                  onClick={handleProceedToPay}
                  disabled={!isFormValid || isProcessing}
                  aria-busy={isProcessing}
                  className={`w-full h-[52px] rounded-xl font-bold text-base transition-all flex items-center justify-center gap-2 cursor-pointer shadow-sm ${
                    !isFormValid
                      ? 'bg-slate-200 text-slate-700 cursor-not-allowed'
                      : isProcessing
                      ? 'bg-blue-700 text-white cursor-wait'
                      : 'bg-blue-700 hover:bg-blue-800 text-white shadow-blue-700/20 active:scale-[0.99]'
                  }`}
                >
                  {isProcessing ? (
                    <>
                      <RotateCcw className="w-4 h-4 animate-spin" />
                      <span>Processing Payment...</span>
                    </>
                  ) : !isFormValid ? (
                    <span>Enter details to pay ₹499.00</span>
                  ) : (
                    <>
                      <span>Pay ₹499.00</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>

                {/* Sandbox / Test Mode Note (PRD Addendum 4 Section 2.5 #6) */}
                {isTestMode && (
                  <p className="text-[11px] text-amber-600 font-medium text-center flex items-center justify-center gap-1">
                    <Sparkles className="w-3 h-3 text-amber-500" />
                    <span>Test mode: no real money will be charged</span>
                  </p>
                )}

                {/* Accepted Methods */}
                <div className="pt-2 text-center space-y-2">
                  <div className="flex items-center justify-center gap-2 text-xs font-semibold text-slate-600">
                    <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">UPI</span>
                    <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">Cards</span>
                    <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">NetBanking</span>
                    <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">Wallets</span>
                  </div>

                  {/* Trust Row */}
                  <div className="text-[11px] text-slate-500 font-medium space-y-1">
                    <div className="flex items-center justify-center gap-1.5 text-slate-600">
                      <Lock className="w-3 h-3 text-emerald-600" />
                      <span>256-bit encrypted • Secured by Razorpay</span>
                    </div>
                    <p>No card or UPI PIN details stored on our servers.</p>
                  </div>
                </div>

                <p className="text-[10px] text-slate-400 text-center font-medium">
                  By paying you agree to the{' '}
                  <Link href="/terms" className="underline hover:text-slate-600">
                    Terms of Service
                  </Link>{' '}
                  and{' '}
                  <Link href="/privacy" className="underline hover:text-slate-600">
                    Refund Policy
                  </Link>
                  .
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Mobile Sticky Bottom Pay Bar (< 1024px) */}
      {!paymentSuccess && (
        <div className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-slate-200 p-4 shadow-lg flex items-center justify-between gap-4">
          <div>
            <span className="text-[11px] text-slate-500 font-semibold block">Total Payable</span>
            <span className="text-xl font-black text-slate-900">₹499.00</span>
          </div>
          <button
            type="button"
            onClick={handleProceedToPay}
            disabled={!isFormValid || isProcessing}
            className={`flex-1 h-12 rounded-xl font-bold text-sm flex items-center justify-center gap-2 cursor-pointer shadow-sm ${
              !isFormValid
                ? 'bg-slate-200 text-slate-700 cursor-not-allowed'
                : isProcessing
                ? 'bg-blue-700 text-white'
                : 'bg-blue-700 hover:bg-blue-800 text-white shadow-blue-700/20'
            }`}
          >
            {isProcessing ? 'Processing...' : 'Pay ₹499.00'}
          </button>
        </div>
      )}
    </div>
  );
}
