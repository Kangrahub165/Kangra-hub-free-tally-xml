'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Clock,
  ArrowRight,
  AlertTriangle,
  RefreshCw,
  HelpCircle,
  Check,
  Loader2,
  Calendar,
  Lock,
  ChevronRight
} from 'lucide-react';
import { GoldTick } from '@/components/ui/GoldTick';
import {
  getMySubscription,
  verifyRazorpayPayment,
  StaffMembershipResponse,
  StaffMembershipRecord
} from '@/lib/api';

interface StaffMembershipCardProps {
  onSuccess?: () => void;
  compact?: boolean;
}

export function StaffMembershipCard({ onSuccess, compact = false }: StaffMembershipCardProps) {
  const [loading, setLoading] = useState(true);
  const [membershipData, setMembershipData] = useState<StaffMembershipResponse | null>(null);

  // Manual payment ID verification form state
  const [paymentIdInput, setPaymentIdInput] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationError, setVerificationError] = useState('');
  const [verificationSuccess, setVerificationSuccess] = useState<string | null>(null);
  const [showManualVerifyInput, setShowManualVerifyInput] = useState(false);

  // Fetch current membership status from authoritative server
  const fetchStatus = async () => {
    try {
      setLoading(true);
      const data = await getMySubscription();
      setMembershipData(data);
    } catch (err: any) {
      console.warn('Could not fetch membership status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleVerifyPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    const pid = paymentIdInput.trim();
    if (!pid) {
      setVerificationError('Please enter your Razorpay Payment ID (e.g. pay_...).');
      return;
    }

    setIsVerifying(true);
    setVerificationError('');
    setVerificationSuccess(null);

    try {
      const res = await verifyRazorpayPayment({ payment_id: pid });
      if (res.success) {
        setVerificationSuccess(
          res.message || 'Payment successfully verified! Your Staff Membership is active.'
        );
        setPaymentIdInput('');
        setShowManualVerifyInput(false);
        await fetchStatus();
        if (onSuccess) onSuccess();
      } else {
        setVerificationError('Verification could not be completed. Please check your Payment ID.');
      }
    } catch (err: any) {
      setVerificationError(
        err.message || 'Verification failed. Please contact support if money was debited.'
      );
    } finally {
      setIsVerifying(false);
    }
  };

  const mem: StaffMembershipRecord | undefined = membershipData?.membership;
  const isStaff = membershipData?.is_staff || false;
  const isGold = membershipData?.is_gold || false;
  const staffStatus = membershipData?.staff_status || 'INACTIVE';
  const isActive = staffStatus === 'ACTIVE' && isStaff;
  const isExpired = staffStatus === 'EXPIRED';

  // Section 4 display wording: "Valid until end of {last valid day} (expires 12:00 AM IST on {next day})"
  const displayWording = mem?.display_wording || '';

  return (
    <div className="w-full bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden transition-all">
      {/* Expiry Banner (PRD Section 9 & 11) */}
      {isExpired && (
        <div className="bg-amber-500 text-navy-950 px-5 py-3 font-semibold text-xs flex items-center justify-between border-b border-amber-600/20 animate-fadeIn">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 text-navy-950" />
            <span>
              Your Staff Membership has expired. Please renew your membership to continue Staff benefits.
            </span>
          </div>
          <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-navy-950 text-amber-400 ml-2 whitespace-nowrap">
            Renewal Required
          </span>
        </div>
      )}

      {/* Expiry Notification Alert (PRD Section 9) */}
      {!isExpired && membershipData?.notification_alert?.message && (
        <div className="bg-blue-50 text-blue-900 px-5 py-2.5 text-xs font-semibold flex items-center gap-2 border-b border-blue-200">
          <Clock className="w-4 h-4 text-blue-600 flex-shrink-0" />
          <span>{membershipData.notification_alert.message}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="relative bg-gradient-to-br from-slate-950 via-navy-900 to-slate-900 text-white p-6 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-amber-400/10 border border-amber-400/30 text-amber-400">
              <Sparkles className="w-6 h-6" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-black text-white tracking-tight">Staff Membership</h3>
                <GoldTick size="md" />
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Professional tier for unlimited Tally XML bill conversions
              </p>
            </div>
          </div>

          {/* Status Badge */}
          <div>
            {loading ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-white/10 text-slate-300">
                <Loader2 className="w-3 h-3 animate-spin" /> Checking...
              </span>
            ) : isActive ? (
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-extrabold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Active Staff Member
              </span>
            ) : isExpired ? (
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-extrabold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                <AlertTriangle className="w-4 h-4 text-rose-400" /> Membership Expired
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-extrabold bg-amber-400/20 text-amber-300 border border-amber-400/40">
                Standard Tier (5 bills/day)
              </span>
            )}
          </div>
        </div>

        {/* Pricing & Expiry Display */}
        <div className="mt-6 flex flex-wrap items-baseline justify-between gap-4 pt-5 border-t border-white/10">
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-black text-amber-400 tracking-tight">₹499</span>
              <span className="text-xs font-bold text-slate-300">/ 30-day period</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1 font-medium">
              Manual renewal only • No recurring auto-debit
            </p>
          </div>

          {/* Active / Expired Expiry Date Notice */}
          {displayWording && (
            <div className="text-right sm:text-right">
              <span className="text-[11px] text-slate-400 block font-medium">Membership Schedule</span>
              <p className="text-xs font-bold text-amber-300 max-w-xs">{displayWording}</p>
            </div>
          )}
        </div>
      </div>

      {/* Main Body */}
      <div className="p-6 sm:p-7 space-y-6">
        {/* Verification Success Toast */}
        {verificationSuccess && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-bold flex items-start gap-3 animate-fadeIn">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-extrabold text-emerald-900 text-sm">Payment Verified Successfully!</p>
              <p className="mt-0.5 font-medium">{verificationSuccess}</p>
              {displayWording && <p className="mt-1 font-bold text-emerald-700">{displayWording}</p>}
            </div>
          </div>
        )}

        {/* Verification Error Toast */}
        {verificationError && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 font-bold flex items-start gap-3 animate-fadeIn">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-extrabold text-rose-900 text-sm">Verification Notice</p>
              <p className="mt-0.5 font-medium">{verificationError}</p>
            </div>
          </div>
        )}

        {/* Benefits Grid (PRD Section 11) */}
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
            Membership Benefits Included
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {[
              'Unlimited bills per day',
              'Zero daily limit countdowns',
              'Official Kangra Hub Gold Tick',
              'Priority OCR & XML generation',
              'Multi-page smart deduplication',
              'Ad-free & banner-free experience',
            ].map((perk, i) => (
              <div
                key={i}
                className="flex items-center gap-2.5 p-2 rounded-lg bg-slate-50 border border-slate-100 text-xs font-semibold text-slate-700"
              >
                <span className="w-4 h-4 rounded-full bg-amber-100 text-amber-800 flex items-center justify-center flex-shrink-0 text-[10px] font-black">
                  ✓
                </span>
                <span>{perk}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Renewal Explanation for Active Members */}
        {isActive && (
          <div className="p-4 rounded-xl bg-amber-50/80 border border-amber-200/80 flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-slate-800">
              <strong className="text-slate-900 font-extrabold block">
                Early Renewal Preserves Remaining Time:
              </strong>
              Renewing your membership before it expires adds 30 full IST calendar days to your
              existing expiry date. You never lose already-paid time.
            </div>
          </div>
        )}

        {/* Payment CTA Section */}
        <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200 text-center space-y-4">
          <div className="max-w-md mx-auto space-y-1">
            <h4 className="text-base font-extrabold text-slate-900">
              {isActive ? 'Renew Staff Membership (₹499 / 30 Days)' : 'Join Staff Membership (₹499 / 30 Days)'}
            </h4>
            <p className="text-xs text-slate-600 font-medium">
              Unlimited Sales & Purchase bill conversions with official Gold Tick. Manual renewal only.
            </p>
          </div>

          <div className="pt-1 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/checkout"
              className="w-full sm:w-auto px-8 h-12 rounded-xl bg-blue-700 hover:bg-blue-800 text-white font-bold text-sm shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-[0.99]"
            >
              <span>{isActive ? 'Renew Membership (₹499.00)' : 'Proceed to Checkout (₹499.00)'}</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3 text-[11px] text-slate-500 font-medium pt-2 border-t border-slate-200/60">
            <span className="flex items-center gap-1 text-slate-700">
              <Lock className="w-3.5 h-3.5 text-emerald-600" /> 256-bit Encrypted
            </span>
            <span>•</span>
            <span>UPI · Cards · NetBanking</span>
            <span>•</span>
            <span>Instant Server Verification</span>
          </div>
        </div>

        {/* Manual Payment Verification Toggle */}
        <div className="pt-2 border-t border-slate-100 text-center">
          <button
            type="button"
            onClick={() => setShowManualVerifyInput(!showManualVerifyInput)}
            className="text-xs font-bold text-navy-800 hover:text-amber-600 inline-flex items-center gap-1 transition-colors"
          >
            {showManualVerifyInput ? 'Hide Payment ID Verification' : 'Paid already? Enter Payment ID to activate'}
            <ChevronRight
              className={`w-3.5 h-3.5 transition-transform ${showManualVerifyInput ? 'rotate-90' : ''}`}
            />
          </button>

          {showManualVerifyInput && (
            <form onSubmit={handleVerifyPayment} className="mt-4 max-w-md mx-auto space-y-3 text-left">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Razorpay Payment ID <span className="text-slate-400 font-normal">(from receipt or SMS)</span>
                </label>
                <input
                  type="text"
                  value={paymentIdInput}
                  onChange={(e) => setPaymentIdInput(e.target.value)}
                  placeholder="e.g. pay_Q8kX1z9yABcDeF"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs font-mono font-semibold focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <button
                type="submit"
                disabled={isVerifying || !paymentIdInput.trim()}
                className="w-full py-2.5 rounded-xl bg-navy-900 hover:bg-navy-950 text-white font-bold text-xs shadow disabled:opacity-50 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                {isVerifying ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Verifying your payment...
                  </>
                ) : (
                  <>
                    Verify & Activate Membership <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default StaffMembershipCard;
