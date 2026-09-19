'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowRight, CheckCircle2, ShieldCheck, Mail, Lock, Phone, User, Eye, EyeOff, RefreshCw, Copy } from 'lucide-react';
import { setAuthToken, checkEmailStatus } from '@/lib/api';
import { getSupabaseClient } from '@/lib/supabaseClient';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { OtpInput } from '@/components/ui/OtpInput';

function SignupContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get('redirect') || searchParams.get('next') || '/dashboard';

  const EMAIL_OTP_LENGTH = 8;

  // Step 1: DETAILS -> Step 2: EMAIL_OTP (Pure Email Verification)
  const [step, setStep] = useState<'DETAILS' | 'EMAIL_OTP'>('DETAILS');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState('');
  const [successInfo, setSuccessInfo] = useState('');
  const [duplicateVerified, setDuplicateVerified] = useState(false);
  const [duplicateUnverified, setDuplicateUnverified] = useState(false);

  // Form Fields
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [countryCode, setCountryCode] = useState('+91');
  const [mobileNumber, setMobileNumber] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);

  // OTP Verification & Cooldown
  const [emailOtp, setEmailOtp] = useState('');
  const [cooldown, setCooldown] = useState(0);
  const [maskedEmail, setMaskedEmail] = useState('');
  const [copiedOtp, setCopiedOtp] = useState(false);

  // 60-second cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const mapErrorMessage = (rawError: any): string => {
    const msg = typeof rawError === 'string' ? rawError : rawError?.message || '';
    const lower = msg.toLowerCase();
    if (lower.includes('expired') || lower.includes('timeout')) {
      return 'This verification code has expired. Please request a new code.';
    }
    if (lower.includes('incorrect') || lower.includes('invalid') || lower.includes('wrong') || lower.includes('mismatch') || lower.includes('403')) {
      return 'That verification code is incorrect. Please check your email and try again.';
    }
    if (lower.includes('too many') || lower.includes('rate limit') || lower.includes('wait') || lower.includes('429')) {
      return 'Too many verification attempts. Please wait and try again later.';
    }
    if (lower.includes('fail') || lower.includes('gateway') || lower.includes('deliver') || lower.includes('connect') || lower.includes('smtp') || lower.includes('database') || lower.includes('unexpected_failure') || lower.includes('500') || lower.includes('internal') || lower.includes('jwt') || lower.includes('token') || lower.includes('stack')) {
      return "We couldn't send the verification email right now. Please try again.";
    }
    return msg || "We couldn't send the verification email right now. Please try again.";
  };

  const handleCopyEnteredOtp = () => {
    if (!emailOtp || emailOtp.length < EMAIL_OTP_LENGTH) return;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(emailOtp);
      setCopiedOtp(true);
      setTimeout(() => setCopiedOtp(false), 2000);
    }
  };

  const handleDetailsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessInfo('');

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter both passwords.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters in length.');
      return;
    }
    const cleanPhone = mobileNumber.replace(/[^0-9]/g, '');
    if (cleanPhone && cleanPhone.length < 10) {
      setError('Please provide a valid 10-digit Indian mobile number.');
      return;
    }
    if (!termsAccepted) {
      setError('You must agree to the Terms of Service and Privacy Policy to create an account.');
      return;
    }

    setLoading(true);
    try {
      const fullMobile = cleanPhone ? `${countryCode}${cleanPhone}` : '';
      const cleanEmail = email.trim().toLowerCase();

      // Format masked email: e.g. k****2@gmail.com
      const emailParts = cleanEmail.split('@');
      const userPart = emailParts[0] || '';
      const domainPart = emailParts[1] || '';
      const maskedEmailFormatted = userPart.length > 2
        ? `${userPart[0]}****${userPart.slice(-1)}@${domainPart}`
        : `${userPart[0] || '*'}***@${domainPart}`;

      setMaskedEmail(maskedEmailFormatted);

      // Check duplicate email status before proceeding
      const emailStatus = await checkEmailStatus(cleanEmail);
      if (emailStatus.exists && emailStatus.verified) {
        setError('This email address is already linked to an account.');
        setDuplicateVerified(true);
        setLoading(false);
        return;
      }
      if (emailStatus.exists && !emailStatus.verified) {
        setDuplicateUnverified(true);
        setSuccessInfo('This email address already has a pending verification. Sending a fresh verification code.');
      } else {
        setDuplicateVerified(false);
        setDuplicateUnverified(false);
      }

      // Request OTP via Supabase Auth official signInWithOtp flow
      const supabase = getSupabaseClient();
      if (!supabase) {
        throw new Error("We couldn't send the verification email right now. Please try again.");
      }

      const { error: sbError } = await supabase.auth.signInWithOtp({
        email: cleanEmail,
        options: {
          shouldCreateUser: true,
          data: {
            full_name: fullName.trim(),
            ...(fullMobile ? { mobile_number: fullMobile, phone: fullMobile } : {}),
          },
        },
      });

      if (sbError) {
        throw sbError;
      }

      setCooldown(60);
      setSuccessInfo('Verification code sent to your email address.');
      setEmailOtp('');
      setStep('EMAIL_OTP');

    } catch (err: any) {
      setError(mapErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleEmailOtpVerify = async (codeToVerify?: string) => {
    const code = (codeToVerify || emailOtp).trim().replace(/[^0-9]/g, '');
    if (!code || code.length < EMAIL_OTP_LENGTH) {
      setError(`Please enter the complete ${EMAIL_OTP_LENGTH}-digit verification code.`);
      return;
    }

    setError('');
    setSuccessInfo('');
    setLoading(true);

    try {
      const cleanPhone = mobileNumber.replace(/[^0-9]/g, '');
      const fullMobile = cleanPhone ? `${countryCode}${cleanPhone}` : '';
      const cleanEmail = email.trim().toLowerCase();

      let emailVerified = false;
      const supabase = getSupabaseClient();
      if (!supabase) {
        throw new Error("Authentication service is unavailable. Please try again.");
      }

      let lastError: any = null;

      // 1. Primary: Verify with type 'email' (dispatched via signInWithOtp)
      try {
        const { data, error: sbErr } = await supabase.auth.verifyOtp({
          email: cleanEmail,
          token: code,
          type: 'email',
        });

        if (!sbErr && (data?.session || data?.user)) {
          emailVerified = true;
          if (data?.session?.access_token) {
            setAuthToken(data.session.access_token, false);
          }
          if (password) {
            try {
              await supabase.auth.updateUser({
                password,
                data: {
                  full_name: fullName.trim(),
                  phone: fullMobile,
                  mobile_number: fullMobile,
                  email_verified: true,
                },
              });
            } catch {}
          }
        } else if (sbErr) {
          lastError = sbErr;
        }
      } catch (err) {
        lastError = err;
      }

      // 2. Secondary fallback: Verify with type 'signup' (if project triggered signup confirmation token)
      if (!emailVerified) {
        try {
          const { data: suData, error: suErr } = await supabase.auth.verifyOtp({
            email: cleanEmail,
            token: code,
            type: 'signup',
          });

          if (!suErr && (suData?.session || suData?.user)) {
            emailVerified = true;
            if (suData?.session?.access_token) {
              setAuthToken(suData.session.access_token, false);
            }
            if (password) {
              try {
                await supabase.auth.updateUser({
                  password,
                  data: {
                    full_name: fullName.trim(),
                    phone: fullMobile,
                    mobile_number: fullMobile,
                    email_verified: true,
                  },
                });
              } catch {}
            }
          } else if (suErr) {
            lastError = suErr;
          }
        } catch (err) {
          lastError = err;
        }
      }

      if (!emailVerified) {
        throw lastError || new Error('That verification code is incorrect. Please check your email and try again.');
      }

      // Email verified! Complete registration and redirect directly
      setSuccessInfo('Email verified successfully! Setting up your session...');
      setTimeout(() => {
        router.push(redirectTarget);
      }, 500);

    } catch (err: any) {
      setError(mapErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0 || resending) return;
    setError('');
    setSuccessInfo('');
    setResending(true);

    try {
      const cleanEmail = email.trim().toLowerCase();
      const supabase = getSupabaseClient();
      if (!supabase) {
        throw new Error("We couldn't send the verification email right now. Please try again.");
      }
      const { error: sbErr } = await supabase.auth.signInWithOtp({
        email: cleanEmail,
        options: { shouldCreateUser: true },
      });
      if (sbErr) {
        throw sbErr;
      }
      setCooldown(60);
      setSuccessInfo('A new verification code has been sent.');
    } catch (err: any) {
      setError(mapErrorMessage(err));
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-4 sm:p-6 bg-slate-50">
      <div className="max-w-md w-full bg-white p-6 sm:p-8 rounded-3xl border border-slate-200 shadow-elevated">
        
        {/* Header */}
        <div className="text-center mb-6">
          <Link href="/" className="inline-block mb-3 focus:outline-none">
            <Image
              src="/logo.webp"
              alt="Kangra Hub"
              width={48}
              height={48}
              className="mx-auto rounded-2xl shadow-xs"
            />
          </Link>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Create Free Account
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Fast, secure bank statement to Tally XML conversion
          </p>

          {/* Progress Indicator (Step 1: Details -> Step 2: Email Verification) */}
          <div className="flex items-center justify-center gap-2 mt-4">
            <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
              step === 'DETAILS'
                ? 'bg-brand-50 text-brand-700 border border-brand-200/60'
                : 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
            }`}>
              {step !== 'DETAILS' ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-brand-600" />}
              <span>1. Registration</span>
            </div>

            <span className="text-slate-300 text-xs">→</span>

            <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
              step === 'EMAIL_OTP'
                ? 'bg-brand-50 text-brand-700 border border-brand-200/60'
                : 'bg-slate-100 text-slate-400'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${step === 'EMAIL_OTP' ? 'bg-brand-600' : 'bg-slate-300'}`} />
              <span>2. Email Verification</span>
            </div>
          </div>
        </div>

        {/* Global Error & Success Alerts */}
        {error && (
          <div className="mb-4">
            <StatusAlert
              type="error"
              message={error}
              onDismiss={() => {
                setError('');
                setDuplicateVerified(false);
              }}
            />
          </div>
        )}

        {duplicateVerified && (
          <div className="mb-4 p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 space-y-3">
            <div className="flex items-center gap-2 font-bold text-xs">
              <ShieldCheck className="w-4 h-4 text-amber-600 shrink-0" />
              <span>This email address is already linked to an account.</span>
            </div>
            <p className="text-xs text-amber-700">
              An account with <span className="font-semibold">{email}</span> already exists. Please sign in to access your dashboard.
            </p>
            <Link
              href={`/login?email=${encodeURIComponent(email.trim())}`}
              className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-xl shadow-xs transition-colors"
            >
              Go to Login
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        )}

        {successInfo && (
          <div className="mb-4">
            <StatusAlert
              type="success"
              message={successInfo}
              onDismiss={() => setSuccessInfo('')}
            />
          </div>
        )}

        {/* STEP 1: Registration Form */}
        {step === 'DETAILS' && (
          <form onSubmit={handleDetailsSubmit} className="space-y-3.5">
            {/* Full Name */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  required
                  placeholder="Rahul Sharma"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-white text-sm text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 pl-10 pr-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                />
              </div>
            </div>

            {/* Email Address */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="email"
                  required
                  placeholder="rahul@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-white text-sm text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 pl-10 pr-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                />
              </div>
            </div>

            {/* Mobile Number */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Mobile Number <span className="text-slate-400 font-normal lowercase">(optional)</span>
              </label>
              <div className="flex gap-2">
                <select
                  value={countryCode}
                  onChange={(e) => setCountryCode(e.target.value)}
                  className="w-26 bg-white px-3 py-2.5 rounded-xl border border-slate-300 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                >
                  <option value="+91">+91 (IN)</option>
                </select>
                <div className="relative flex-1">
                  <Phone className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type="tel"
                    placeholder="9876543210"
                    value={mobileNumber}
                    onChange={(e) => setMobileNumber(e.target.value.replace(/[^0-9]/g, ''))}
                    className="w-full bg-white text-sm text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 pl-10 pr-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                </div>
              </div>
            </div>

            {/* Password Fields */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-white text-sm text-slate-900 rounded-xl border border-slate-300 pl-10 pr-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full bg-white text-sm text-slate-900 rounded-xl border border-slate-300 pl-10 pr-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-500">
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="flex items-center gap-1.5 hover:text-slate-800"
              >
                {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                <span>{showPassword ? 'Hide' : 'Show'} passwords</span>
              </button>
            </div>

            {/* Terms Agreement Checkbox */}
            <div className="flex items-start gap-2 pt-1">
              <input
                type="checkbox"
                id="terms"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="mt-0.5 w-4 h-4 rounded text-brand-600 border-slate-300 focus:ring-brand-500"
              />
              <label htmlFor="terms" className="text-xs text-slate-600 leading-relaxed select-none">
                I agree to the{' '}
                <Link href="/terms" className="text-brand-600 font-semibold hover:underline">
                  Terms of Service
                </Link>{' '}
                and{' '}
                <Link href="/privacy" className="text-brand-600 font-semibold hover:underline">
                  Privacy Policy
                </Link>.
              </label>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full mt-2"
              loading={loading}
              iconRight={<ArrowRight className="w-4 h-4" />}
            >
              Continue to Email Verification
            </Button>
          </form>
        )}

        {/* STEP 2: Email OTP Verification */}
        {step === 'EMAIL_OTP' && (
          <div className="space-y-6 text-center">
            <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-700 flex items-center justify-center mx-auto border border-brand-200/80 shadow-xs">
              <Mail className="w-6 h-6 text-brand-600" />
            </div>

            <div className="space-y-1">
              <h3 className="text-base font-bold text-slate-900">Verify Your Email</h3>
              <p className="text-xs text-slate-500">
                We've sent an {EMAIL_OTP_LENGTH}-digit verification code to:{' '}
                <strong className="text-slate-800 font-medium">
                  {maskedEmail}
                </strong>
              </p>
            </div>

            {/* 8-box OTP input */}
            <OtpInput
              length={EMAIL_OTP_LENGTH}
              value={emailOtp}
              onChange={setEmailOtp}
              onComplete={(code) => handleEmailOtpVerify(code)}
              disabled={loading}
              hasError={!!error}
            />

            {/* Real Copy OTP Button (Only active when complete OTP has been typed/pasted/autofilled by user) */}
            {emailOtp.length === EMAIL_OTP_LENGTH && (
              <div className="flex justify-center -mt-2">
                <button
                  type="button"
                  onClick={handleCopyEnteredOtp}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
                >
                  {copiedOtp ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedOtp ? 'Copied to Clipboard!' : 'Copy OTP'}</span>
                </button>
              </div>
            )}

            <Button
              type="button"
              variant="primary"
              size="md"
              className="w-full"
              loading={loading}
              onClick={() => handleEmailOtpVerify()}
              iconRight={<ArrowRight className="w-4 h-4" />}
            >
              Verify Email & Continue
            </Button>

            {/* Resend & Back Navigation */}
            <div className="flex flex-col items-center gap-2.5 pt-1 text-xs">
              <div className="text-slate-500">
                Didn't receive the code?{' '}
                {cooldown > 0 ? (
                  <span className="font-semibold text-slate-400">
                    Resend available in <span className="font-mono text-brand-600">{cooldown}s</span>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resending}
                    className="font-bold text-brand-600 hover:text-brand-700 inline-flex items-center gap-1 hover:underline"
                  >
                    {resending ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
                    Resend Code
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => {
                  setStep('DETAILS');
                  setError('');
                  setSuccessInfo('');
                }}
                className="font-semibold text-slate-400 hover:text-slate-700 transition-colors"
              >
                ← Edit Registration Information
              </button>
            </div>
          </div>
        )}

        <div className="pt-4 border-t border-slate-100 text-center text-xs text-slate-500">
          Already have an account?{' '}
          <Link href={`/login${redirectTarget !== '/dashboard' ? `?redirect=${encodeURIComponent(redirectTarget)}` : ''}`} className="font-bold text-brand-600 hover:text-brand-700">
            Sign In
          </Link>
        </div>

      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={
      <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-6 bg-slate-50">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-500">Loading signup portal...</p>
        </div>
      </div>
    }>
      <SignupContent />
    </Suspense>
  );
}
