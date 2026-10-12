'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { 
  Check, 
  ShieldCheck, 
  Lock, 
  ArrowRight, 
  CheckCircle2, 
  AlertCircle, 
  Sparkles, 
  RefreshCw,
  QrCode,
  FileCheck2,
  Copy
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthProvider';
import { 
  getSubscriptionPlans, 
  createPaymentOrder, 
  verifyPayment, 
  SubscriptionPlanItem 
} from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

declare global {
  interface Window {
    Razorpay: any;
  }
}

function CheckoutContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedPlan = searchParams.get('plan') || 'basic';

  const { isAuthenticated, isLoading, user } = useAuth();
  const [plans, setPlans] = useState<SubscriptionPlanItem[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>(requestedPlan);
  const [loadingPlans, setLoadingPlans] = useState(true);
  
  // Checkout & User Details
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [phone, setPhone] = useState(user?.mobile_number || '');
  
  // Payment Flow State
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successResult, setSuccessResult] = useState<{
    plan_name: string;
    bills_limit: number;
    is_unlimited: boolean;
    membership_expires_at?: string;
    last_valid_day?: string;
    payment_id?: string;
  } | null>(null);

  // Require login before checkout
  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.push(`/login?redirect=/checkout?plan=${encodeURIComponent(selectedPlanId)}`);
      return;
    }

    getSubscriptionPlans()
      .then((data) => {
        if (data && data.plans) {
          setPlans(data.plans);
          // If query param matched a plan, select it
          if (data.plans.some(p => p.id === requestedPlan)) {
            setSelectedPlanId(requestedPlan);
          }
        }
      })
      .catch((err: any) => {
        if (err.status === 401) {
          router.push(`/login?redirect=/checkout?plan=${encodeURIComponent(selectedPlanId)}`);
        } else {
          setErrorMsg('Failed to load plans. Please refresh.');
        }
      })
      .finally(() => {
        setLoadingPlans(false);
      });
  }, [isLoading, isAuthenticated, router, requestedPlan, selectedPlanId]);

  useEffect(() => {
    if (user) {
      if (user.full_name) setFullName(user.full_name);
      if (user.email) setEmail(user.email);
      if (user.mobile_number) setPhone(user.mobile_number);
    }
  }, [user]);

  // Load Razorpay script
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (document.getElementById('razorpay-checkout-js')) return;
    const script = document.createElement('script');
    script.id = 'razorpay-checkout-js';
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    document.body.appendChild(script);
  }, []);

  const activePlan = plans.find(p => p.id === selectedPlanId) || plans[0] || {
    id: 'basic',
    name: 'Basic',
    price_inr: 199.0,
    price_paise: 19900,
    bills_limit: 50,
    duration_days: 30,
    is_unlimited: false,
    features: []
  };

  const handlePayNow = async () => {
    setErrorMsg('');
    setIsProcessing(true);

    try {
      // 1. Authoritative server-side order creation
      const order = await createPaymentOrder({
        planId: selectedPlanId,
        customer_name: fullName,
        customer_email: email,
        customer_phone: phone
      });

      if (!order || !order.orderId) {
        throw new Error('Server was unable to generate payment order.');
      }

      // 2. Launch Razorpay Checkout Modal
      if (typeof window.Razorpay === 'undefined') {
        throw new Error('Payment gateway is still loading. Please retry in a few seconds.');
      }

      const options = {
        key: order.keyId,
        amount: order.amount,
        currency: order.currency || 'INR',
        name: 'Kangra Hub',
        description: `${order.planName || activePlan.name} Subscription (30 Days)`,
        order_id: order.orderId,
        prefill: {
          name: fullName || user?.full_name || '',
          email: email || user?.email || '',
          contact: phone || user?.mobile_number || ''
        },
        theme: {
          color: '#0284c7'
        },
        handler: async function (response: any) {
          try {
            // 3. Server-side verification & atomic subscription activation
            const ver = await verifyPayment({
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_signature: response.razorpay_signature,
              planId: selectedPlanId,
              customer_name: fullName,
              customer_email: email,
              customer_phone: phone
            });

            if (ver.success || ver.ok) {
              setSuccessResult({
                plan_name: ver.plan_name || activePlan.name,
                bills_limit: ver.bills_limit !== undefined ? ver.bills_limit : activePlan.bills_limit,
                is_unlimited: !!ver.is_unlimited,
                membership_expires_at: ver.membership_expires_at,
                last_valid_day: ver.last_valid_day,
                payment_id: ver.payment_id || response.razorpay_payment_id
              });
            } else {
              setErrorMsg(ver.message || 'Payment verification could not be completed.');
            }
          } catch (err: any) {
            setErrorMsg(err.message || 'Payment signature verification failed.');
          } finally {
            setIsProcessing(false);
          }
        },
        modal: {
          ondismiss: function () {
            setIsProcessing(false);
          }
        }
      };

      const rzp = new window.Razorpay(options);
      rzp.on('payment.failed', function (resp: any) {
        setIsProcessing(false);
        setErrorMsg(resp.error?.description || 'Payment was unsuccessful or cancelled.');
      });
      rzp.open();

    } catch (err: any) {
      setIsProcessing(false);
      setErrorMsg(err.message || 'Payment initialization failed. Please try again.');
    }
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-14 h-14 bg-brand-50 border border-brand-200 text-brand-600 rounded-2xl flex items-center justify-center mb-4 shadow-sm animate-pulse">
          <Lock className="w-7 h-7" />
        </div>
        <h2 className="text-xl font-extrabold text-slate-900 mb-2">Member Authentication Required</h2>
        <p className="text-sm text-slate-600 max-w-md mb-6 leading-relaxed">
          Please log in to continue with your subscription checkout.
        </p>
        <Link href={`/login?redirect=/checkout?plan=${encodeURIComponent(selectedPlanId)}`}>
          <Button variant="primary" size="md" className="font-bold">
            Log In to Checkout
          </Button>
        </Link>
      </div>
    );
  }

  // Confirmation Success Screen
  if (successResult) {
    return (
      <div className="min-h-screen bg-slate-50/50 py-16 px-4 sm:px-6 lg:px-8 flex items-center justify-center">
        <div className="max-w-xl w-full bg-white rounded-3xl border border-slate-200 shadow-xl p-8 sm:p-10 text-center space-y-6">
          <div className="w-16 h-16 bg-emerald-50 border border-emerald-200 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto shadow-sm">
            <CheckCircle2 className="w-9 h-9" />
          </div>
          
          <div className="space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
              Subscription Active
            </span>
            <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
              Welcome to {successResult.plan_name}!
            </h2>
            <p className="text-sm text-slate-600">
              Your subscription payment was verified and activated for your firm.
            </p>
          </div>

          <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200/80 text-left space-y-3.5 text-xs sm:text-sm">
            <div className="flex justify-between items-center text-slate-600">
              <span>Plan:</span>
              <strong className="text-slate-900 font-bold">{successResult.plan_name}</strong>
            </div>
            <div className="flex justify-between items-center text-slate-600">
              <span>Bill Conversion Limit:</span>
              <strong className="text-slate-900 font-bold">
                {successResult.is_unlimited || successResult.bills_limit === -1 
                  ? 'Unlimited Bills' 
                  : `${successResult.bills_limit} Bills / Month`}
              </strong>
            </div>
            <div className="flex justify-between items-center text-slate-600">
              <span>Validity:</span>
              <strong className="text-emerald-700 font-bold">
                {successResult.last_valid_day ? `Until ${successResult.last_valid_day} (11:59 PM IST)` : '30 Days'}
              </strong>
            </div>
            {successResult.payment_id && (
              <div className="flex justify-between items-center text-slate-600 pt-2 border-t border-slate-200">
                <span>Payment Reference:</span>
                <span className="font-mono text-slate-500 text-[11px] truncate max-w-[200px]">
                  {successResult.payment_id}
                </span>
              </div>
            )}
          </div>

          <div className="pt-2 flex flex-col sm:flex-row gap-3">
            <Link href="/convert" className="flex-1">
              <Button variant="primary" size="lg" className="w-full font-bold justify-center" iconRight={<ArrowRight className="w-4 h-4" />}>
                Convert Statements Now
              </Button>
            </Link>
            <Link href="/dashboard" className="flex-1">
              <Button variant="outline" size="lg" className="w-full font-semibold justify-center">
                View Dashboard
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Title */}
        <div className="text-center space-y-2">
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Subscription Checkout
          </h1>
          <p className="text-xs sm:text-sm text-slate-600">
            Securely activate your monthly plan for fast bank statement conversions.
          </p>
        </div>

        {errorMsg && (
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-2xl flex items-center gap-3 text-xs sm:text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Left Column: Plan Selection & Customer Info */}
          <div className="lg:col-span-7 space-y-6">
            
            {/* Step 1: Select Plan */}
            <div className="bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-black text-slate-900 tracking-tight">Select Subscription Plan</h3>
                <Link href="/plans" className="text-xs text-brand-600 hover:text-brand-700 font-bold">
                  View Full Details
                </Link>
              </div>

              <div className="grid grid-cols-1 gap-3">
                {plans.map((p) => {
                  const isSelected = p.id === selectedPlanId;
                  return (
                    <div
                      key={p.id}
                      onClick={() => setSelectedPlanId(p.id)}
                      className={`cursor-pointer p-4 rounded-2xl border transition-all duration-200 flex items-center justify-between ${
                        isSelected
                          ? 'border-brand-500 bg-brand-50/40 ring-2 ring-brand-500/20'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-extrabold text-sm text-slate-900">{p.name}</span>
                          {p.badge && (
                            <span className="text-[10px] font-black uppercase tracking-wider bg-slate-900 text-white px-2 py-0.5 rounded-full">
                              {p.badge}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500">
                          {p.bills_limit === -1 ? 'Unlimited Bills' : `${p.bills_limit} Bills / Month`}
                        </div>
                      </div>
                      
                      {/* Price (Exact amount, ZERO tax labels) */}
                      <div className="text-right">
                        <div className="text-base font-black text-slate-900">
                          ₹{Math.round(p.price_inr)}
                        </div>
                        <span className="text-[11px] text-slate-400">/ 30 days</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Step 2: Contact Details */}
            <div className="bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card space-y-4">
              <h3 className="text-sm font-black text-slate-900 tracking-tight">Billing & Member Details</h3>
              <div className="space-y-3.5">
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Full Name / Firm Name</label>
                  <Input
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Ramesh Kumar & Associates"
                    className="text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Email Address</label>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="user@example.com"
                    className="text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Mobile Number (Optional)</label>
                  <Input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 9876543210"
                    className="text-xs"
                  />
                </div>
              </div>
            </div>

          </div>

          {/* Right Column: Order Summary */}
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card space-y-6 sticky top-24">
              <h3 className="text-sm font-black text-slate-900 tracking-tight">Order Summary</h3>

              {/* Exact breakdown with NO tax labels */}
              <div className="space-y-3.5 text-xs">
                <div className="flex justify-between text-slate-600">
                  <span>Selected Plan:</span>
                  <strong className="text-slate-900 font-bold">{activePlan.name}</strong>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Bill Conversion Capacity:</span>
                  <strong className="text-slate-900 font-bold">
                    {activePlan.bills_limit === -1 ? 'Unlimited Bills' : `${activePlan.bills_limit} Bills`}
                  </strong>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Subscription Validity:</span>
                  <strong className="text-slate-900 font-bold">30 Days (IST Midnight)</strong>
                </div>

                <div className="pt-3 border-t border-slate-200 flex justify-between items-baseline">
                  <span className="text-sm font-black text-slate-900">Total Payable:</span>
                  <div className="text-right">
                    <span className="text-2xl font-black text-brand-600">
                      ₹{Math.round(activePlan.price_inr)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="space-y-3 pt-2">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={handlePayNow}
                  loading={isProcessing}
                  className="w-full font-bold justify-center rounded-2xl py-3.5 shadow-md shadow-brand-500/20 bg-brand-600 hover:bg-brand-500"
                  iconRight={<ArrowRight className="w-4 h-4" />}
                >
                  Pay ₹{Math.round(activePlan.price_inr)} & Activate
                </Button>

                <div className="flex items-center justify-center gap-2 text-[11px] text-slate-500 font-medium text-center">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>Razorpay Test Mode • Instant Server Verification</span>
                </div>
              </div>

            </div>
          </div>

        </div>

      </div>
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <CheckoutContent />
    </Suspense>
  );
}
