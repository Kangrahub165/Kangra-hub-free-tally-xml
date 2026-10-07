'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import { 
  ArrowRight, 
  CheckCircle2, 
  XCircle, 
  ShieldCheck, 
  Mail, 
  Lock, 
  Phone, 
  User, 
  Eye, 
  EyeOff, 
  RefreshCw, 
  Check, 
  AlertCircle,
  Clock
} from 'lucide-react';
import { 
  setAuthToken, 
  checkEmailStatus,
  initiateSupabaseSignup,
  getSignupPendingStatus,
  verifySupabaseEmailOtp,
  resendSupabaseEmailOtp
} from '@/lib/api';
import { getSupabaseClient } from '@/lib/supabaseClient';
import { recordUserActivity } from '@/lib/activityLogger';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { OtpInput } from '@/components/ui/OtpInput';

function SignupContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams.get('redirect') || searchParams.get('next') || '/dashboard';

  // Step 1: DETAILS -> Step 2: EMAIL_OTP (Pure Email Verification)
  const [step, setStep] = useState<'DETAILS' | 'EMAIL_OTP'>('DETAILS');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState('');
  const [successInfo, setSuccessInfo] = useState('');
  const [duplicateVerified, setDuplicateVerified] = useState(false);

  // Form Fields (PRD Requirements 2, 3, 4, 5)
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [countryCode, setCountryCode] = useState('+91');
  const [mobileNumber, setMobileNumber] = useState('');
  const [gender, setGender] = useState<'Male' | 'Female' | 'Other' | 'Prefer not to say'>('Male');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);

  // OTP Verification, 10-Minute Validity & Cooldown
  const [emailOtp, setEmailOtp] = useState('');
  const [cooldown, setCooldown] = useState(0);
  const [validitySeconds, setValiditySeconds] = useState(600); // 10 minutes exact validity
  const [maskedEmail, setMaskedEmail] = useState('');
  const [isRecoveredSession, setIsRecoveredSession] = useState(false);

  // 1. Session recovery on page mount (accidentally closed tab / refreshed page)
  useEffect(() => {
    try {
      const storedPending = sessionStorage.getItem('kangra_pending_signup') || localStorage.getItem('kangra_pending_signup');
      if (storedPending) {
        const parsed = JSON.parse(storedPending);
        if (parsed.email) {
          getSignupPendingStatus(parsed.email, parsed.mobileNumber).then((status) => {
            if (status.active && status.remaining_seconds > 0) {
              setEmail(status.email || parsed.email);
              if (status.mobile_number) setMobileNumber(status.mobile_number);
              if (status.full_name) setFullName(status.full_name);
              setMaskedEmail(status.masked_email || '');
              setValiditySeconds(status.remaining_seconds);
              setStep('EMAIL_OTP');
              setIsRecoveredSession(true);
              setSuccessInfo('Resumed your active pending verification. Please enter the OTP sent to your email.');
            }
          }).catch(() => {});
        }
      }
    } catch {}
  }, []);

  // 2. 10-minute OTP Validity ticker
  useEffect(() => {
    if (step !== 'EMAIL_OTP') return;
    if (validitySeconds <= 0) return;

    const timer = setInterval(() => {
      setValiditySeconds((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [step, validitySeconds]);

  // 3. 60-second cooldown timer for resend spam prevention
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const formatValidityTime = (totalSecs: number) => {
    const mins = Math.floor(Math.max(0, totalSecs) / 60);
    const secs = Math.max(0, totalSecs) % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // Dynamic Password Strength Evaluation (PRD Section 3)
  const evaluatePasswordStrength = (pwd: string) => {
    if (!pwd) {
      return {
        score: 0,
        label: 'Enter password',
        color: 'bg-slate-200',
        textColor: 'text-slate-400',
        badgeVariant: 'secondary' as const,
        checks: {
          minLength: false,
          hasUpper: false,
          hasLower: false,
          hasNumber: false,
          hasSpecial: false,
        }
      };
    }

    const checks = {
      minLength: pwd.length >= 8,
      hasUpper: /[A-Z]/.test(pwd),
      hasLower: /[a-z]/.test(pwd),
      hasNumber: /[0-9]/.test(pwd),
      hasSpecial: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd),
    };

    const criteriaMet = Object.values(checks).filter(Boolean).length;

    // Weak: < 8 chars or <= 2 criteria passed
    if (pwd.length < 8 || criteriaMet <= 2) {
      return {
        score: 1,
        label: 'Weak',
        color: 'bg-rose-500',
        textColor: 'text-rose-600',
        badgeVariant: 'error' as const,
        checks
      };
    }

    // Medium: 8+ chars and 3-4 criteria
    if (criteriaMet === 3 || criteriaMet === 4) {
      return {
        score: 2,
        label: 'Medium',
        color: 'bg-amber-500',
        textColor: 'text-amber-600',
        badgeVariant: 'warning' as const,
        checks
      };
    }

    // Strong: 8+ chars and all criteria met
    return {
      score: 3,
      label: 'Strong',
      color: 'bg-emerald-500',
      textColor: 'text-emerald-600',
      badgeVariant: 'success' as const,
      checks
    };
  };

  const strength = evaluatePasswordStrength(password);
  const passwordsMatch = confirmPassword.length > 0 && password === confirmPassword;
  const passwordsMismatch = confirmPassword.length > 0 && password !== confirmPassword;

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
    if (lower.includes('already registered') || lower.includes('user already registered')) {
      return 'This email address is already linked to an account. Please log in.';
    }
    return msg || "We couldn't process your request right now. Please try again.";
  };

  const handleDetailsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessInfo('');

    // 1. Mandatory Full Name
    if (!fullName.trim()) {
      setError('Please enter your full name.');
      return;
    }

    // 2. Mandatory Mobile Number (PRD Section 4 - Mandatory, but NO SMS OTP)
    const cleanPhone = mobileNumber.replace(/[^0-9]/g, '');
    if (!cleanPhone || cleanPhone.length !== 10) {
      setError('Mobile number is mandatory. Please provide a valid 10-digit Indian mobile number.');
      return;
    }

    // 3. Password requirements & match validation
    if (password.length < 8) {
      setError('Password must be at least 8 characters in length.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match. Please ensure both password fields are identical.');
      return;
    }

    // 4. Terms agreement
    if (!termsAccepted) {
      setError('You must agree to the Terms of Service and Privacy Policy to create an account.');
      return;
    }

    setLoading(true);
    try {
      const cleanEmail = email.trim().toLowerCase();

      // Masked email for display fallback (e.g. k****2@gmail.com)
      const emailParts = cleanEmail.split('@');
      const userPart = emailParts[0] || '';
      const domainPart = emailParts[1] || '';
      const maskedEmailFormatted = userPart.length > 2
        ? `${userPart[0]}****${userPart.slice(-1)}@${domainPart}`
        : `${userPart[0] || '*'}***@${domainPart}`;

      setMaskedEmail(maskedEmailFormatted);

      // Check existing email status
      const emailStatus = await checkEmailStatus(cleanEmail, cleanPhone);
      if (emailStatus.exists && emailStatus.verified) {
        setError('This email address is already linked to an account.');
        setDuplicateVerified(true);
        setLoading(false);
        return;
      }

      // Initiate Supabase Auth Email OTP via authoritative backend service
      const res = await initiateSupabaseSignup({
        email: cleanEmail,
        mobile_number: cleanPhone,
        full_name: fullName.trim(),
        gender: gender,
        password: password,
      });

      // Save pending verification session for recovery upon accidental tab close or page reload
      const pendingData = {
        email: cleanEmail,
        mobileNumber: cleanPhone,
        fullName: fullName.trim(),
        savedAt: Date.now(),
      };
      try {
        sessionStorage.setItem('kangra_pending_signup', JSON.stringify(pendingData));
        localStorage.setItem('kangra_pending_signup', JSON.stringify(pendingData));
      } catch {}

      setMaskedEmail(res.masked_email || maskedEmailFormatted);
      setValiditySeconds(res.remaining_seconds || 600);

      if (res.status === 'PENDING_OTP_ACTIVE') {
        setIsRecoveredSession(true);
        setSuccessInfo('An unverified signup is already pending. Please enter the OTP that was already sent to your email.');
      } else {
        setIsRecoveredSession(false);
        setCooldown(60);
        setSuccessInfo('Verification code sent to your email address (valid for 10 minutes).');
      }

      setEmailOtp('');
      setStep('EMAIL_OTP');

    } catch (err: any) {
      const errMsg = mapErrorMessage(err);
      if (errMsg.toLowerCase().includes('already linked') || errMsg.toLowerCase().includes('already registered')) {
        setDuplicateVerified(true);
      }
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleEmailOtpVerify = async (e?: React.FormEvent, customCode?: string) => {
    if (e && e.preventDefault) e.preventDefault();
    const code = (customCode || emailOtp).trim().replace(/[^0-9]/g, '');
    if (!code || code.length < 8) {
      setError('Please enter the 8-digit verification code sent to your email.');
      return;
    }

    if (validitySeconds <= 0) {
      setError('This verification code has expired (10-minute validity exceeded). Please request a new OTP.');
      return;
    }

    setError('');
    setSuccessInfo('');
    setLoading(true);

    try {
      const cleanEmail = email.trim().toLowerCase();
      const cleanPhone = mobileNumber.replace(/[^0-9]/g, '');

      // Verify OTP through authoritative backend service which enforces the 10-minute validity window
      const res = await verifySupabaseEmailOtp({
        email: cleanEmail,
        otp: code,
        mobile_number: cleanPhone,
      });

      // Verification confirmed by Supabase Auth! Clear saved pending recovery state
      try {
        sessionStorage.removeItem('kangra_pending_signup');
        localStorage.removeItem('kangra_pending_signup');
      } catch {}

      // Establish authenticated session
      if (res?.token) {
        setAuthToken(res.token, false, res.refresh_token);
      }

      await recordUserActivity({
        action: 'User registered and verified email',
        module: 'Auth',
        metadata: { email: cleanEmail }
      });

      setSuccessInfo('Email verified successfully! Setting up your session...');
      setTimeout(() => {
        window.location.href = redirectTarget;
      }, 700);

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
      const cleanPhone = mobileNumber.replace(/[^0-9]/g, '');

      const res = await resendSupabaseEmailOtp({
        email: cleanEmail,
        mobile_number: cleanPhone,
      });

      setValiditySeconds(res.remaining_seconds || 600);
      setCooldown(res.cooldown_seconds || 60);
      setIsRecoveredSession(false);
      setEmailOtp('');
      setSuccessInfo('A fresh verification code has been dispatched to your email (valid for 10 minutes).');
    } catch (err: any) {
      setError(mapErrorMessage(err));
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-4 sm:p-6 lg:p-10 bg-slate-50">
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 bg-white rounded-3xl border border-slate-200 shadow-xl overflow-hidden">
        
        {/* Left Value Prop Hero (5 cols) */}
        <div className="hidden lg:flex lg:col-span-5 bg-gradient-to-br from-slate-900 via-navy-900 to-slate-950 p-8 flex-col justify-between text-white relative">
          <div className="space-y-6">
            <Link href="/" className="flex items-center gap-3">
              <div className="relative w-9 h-9 flex-shrink-0">
                <Image src="/logo.webp" alt="Kangra Hub" width={36} height={36} className="rounded-xl shadow-md" />
              </div>
              <div className="flex flex-col">
                <span className="font-extrabold text-base tracking-tight text-white leading-tight">Kangra Hub</span>
                <span className="text-[10px] font-bold text-brand-400 tracking-wider uppercase">Sales & Purchase</span>
              </div>
            </Link>

            <div className="space-y-3 pt-4">
              <Badge variant="success" size="sm" pulse>Daily 5 Free Bills Quota</Badge>
              <h2 className="text-xl font-extrabold text-white tracking-tight leading-snug">
                Automated Sales & Purchase to Tally XML
              </h2>
              <p className="text-xs text-slate-300 leading-relaxed">
                Join accounting professionals converting GST invoices to TallyPrime XML vouchers in seconds.
              </p>
            </div>

            <div className="space-y-2.5 pt-4 border-t border-slate-800">
              <div className="flex items-center gap-2.5 text-xs text-slate-300">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>5 Free Bills Daily (Resets midnight IST)</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-300">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Instant GSTIN & HSN line item parsing</span>
              </div>
              <div className="flex items-center gap-2.5 text-xs text-slate-300">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Zero client data storage — RAM-only parsing</span>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-slate-800 text-[11px] text-slate-400">
            🔒 Pure Supabase authentication with verified email security.
          </div>
        </div>

        {/* Right Form Column (7 cols) */}
        <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-center">
          <div className="max-w-md w-full mx-auto">
            
            {/* Header */}
            <div className="text-center mb-6">
              <Link href="/" className="inline-block mb-2 focus:outline-none">
                <Image
                  src="/logo.webp"
                  alt="Kangra Hub"
                  width={44}
                  height={44}
                  className="mx-auto rounded-2xl shadow-sm"
                />
              </Link>
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Create Free Account
              </h1>
              <p className="text-xs text-slate-500 mt-1">
                Fast, secure Sales & Purchase invoice to Tally XML conversion
              </p>

              {/* Step indicator */}
              <div className="flex items-center justify-center gap-2 mt-4">
                <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
                  step === 'DETAILS'
                    ? 'bg-brand-50 text-brand-700 border border-brand-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}>
                  {step !== 'DETAILS' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-brand-600" />}
                  <span>1. User Details</span>
                </div>

                <span className="text-slate-300 text-xs">→</span>

                <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
                  step === 'EMAIL_OTP'
                    ? 'bg-brand-50 text-brand-700 border border-brand-200'
                    : 'bg-slate-100 text-slate-400'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${step === 'EMAIL_OTP' ? 'bg-brand-600' : 'bg-slate-300'}`} />
                  <span>2. Email OTP</span>
                </div>
              </div>
            </div>

            {/* Error & Info Alerts */}
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
                  <span>This email is already registered.</span>
                </div>
                <p className="text-xs text-amber-700">
                  An account with <span className="font-semibold">{email}</span> already exists. Please log in directly.
                </p>
                <Link
                  href={`/login?email=${encodeURIComponent(email.trim())}`}
                  className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-xl shadow-sm transition-colors"
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

            {/* STEP 1: Registration Details Form */}
            {step === 'DETAILS' && (
              <form onSubmit={handleDetailsSubmit} className="space-y-4">
                
                {/* Full Name */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Full Name <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="text"
                      required
                      placeholder="Rahul Sharma"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full bg-white text-sm text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 pl-10 pr-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                    />
                  </div>
                </div>

                {/* Email Address */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Email Address <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="email"
                      required
                      placeholder="name@company.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-white text-sm text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 pl-10 pr-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                    />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">Verification OTP will be sent to this email address.</p>
                </div>

                {/* Mobile Number & Gender (2-Col Grid) */}
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                  {/* Mobile Number (MANDATORY, NO SMS OTP) */}
                  <div className="sm:col-span-7">
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                      Mobile Number <span className="text-rose-500">*</span>
                    </label>
                    <div className="flex gap-2">
                      <select
                        value={countryCode}
                        onChange={(e) => setCountryCode(e.target.value)}
                        className="w-24 bg-white px-2.5 py-2.5 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                      >
                        <option value="+91">+91 (IN)</option>
                      </select>
                      <div className="relative flex-1">
                        <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                        <input
                          type="tel"
                          required
                          placeholder="9876543210"
                          maxLength={10}
                          value={mobileNumber}
                          onChange={(e) => setMobileNumber(e.target.value.replace(/[^0-9]/g, ''))}
                          className="w-full bg-white text-sm text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 pl-9 pr-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Gender Selection */}
                  <div className="sm:col-span-5">
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                      Gender <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={gender}
                      onChange={(e) => setGender(e.target.value as any)}
                      className="w-full bg-white px-3 py-2.5 rounded-xl border border-slate-300 text-sm font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                    >
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                      <option value="Prefer not to say">Prefer not to say</option>
                    </select>
                  </div>
                </div>

                {/* Password Fields */}
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                        Create Password <span className="text-rose-500">*</span>
                      </label>
                      {password && (
                        <span className={`text-xs font-bold ${strength.textColor}`}>
                          Strength: {strength.label}
                        </span>
                      )}
                    </div>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        required
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-white text-sm text-slate-900 rounded-xl border border-slate-300 pl-10 pr-10 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>

                    {/* Visual Password Strength Meter (PRD Section 3) */}
                    {password && (
                      <div className="mt-2 space-y-2">
                        {/* 3-Bar Visual Indicator */}
                        <div className="grid grid-cols-3 gap-1.5 h-1.5">
                          <div className={`rounded-full transition-all duration-300 ${strength.score >= 1 ? strength.color : 'bg-slate-200'}`} />
                          <div className={`rounded-full transition-all duration-300 ${strength.score >= 2 ? strength.color : 'bg-slate-200'}`} />
                          <div className={`rounded-full transition-all duration-300 ${strength.score >= 3 ? strength.color : 'bg-slate-200'}`} />
                        </div>

                        {/* Password Requirements Checklist */}
                        <div className="grid grid-cols-2 gap-x-2 gap-y-1 pt-1 text-[11px] text-slate-600">
                          <div className={`flex items-center gap-1.5 ${strength.checks.minLength ? 'text-emerald-600 font-semibold' : 'text-slate-500'}`}>
                            {strength.checks.minLength ? <Check className="w-3 h-3 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />}
                            <span>8+ characters</span>
                          </div>
                          <div className={`flex items-center gap-1.5 ${strength.checks.hasUpper && strength.checks.hasLower ? 'text-emerald-600 font-semibold' : 'text-slate-500'}`}>
                            {strength.checks.hasUpper && strength.checks.hasLower ? <Check className="w-3 h-3 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />}
                            <span>Upper & lower case</span>
                          </div>
                          <div className={`flex items-center gap-1.5 ${strength.checks.hasNumber ? 'text-emerald-600 font-semibold' : 'text-slate-500'}`}>
                            {strength.checks.hasNumber ? <Check className="w-3 h-3 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />}
                            <span>At least one number</span>
                          </div>
                          <div className={`flex items-center gap-1.5 ${strength.checks.hasSpecial ? 'text-emerald-600 font-semibold' : 'text-slate-500'}`}>
                            {strength.checks.hasSpecial ? <Check className="w-3 h-3 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />}
                            <span>Special character (!@#)</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Confirm Password */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                        Confirm Password <span className="text-rose-500">*</span>
                      </label>
                      {passwordsMatch && (
                        <span className="text-xs font-bold text-emerald-600 flex items-center gap-1">
                          <Check className="w-3 h-3" /> Passwords match
                        </span>
                      )}
                      {passwordsMismatch && (
                        <span className="text-xs font-bold text-rose-600 flex items-center gap-1">
                          <XCircle className="w-3 h-3" /> Passwords do not match
                        </span>
                      )}
                    </div>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        required
                        placeholder="••••••••"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className={`w-full bg-white text-sm text-slate-900 rounded-xl border pl-10 pr-10 py-2.5 focus:outline-none focus:ring-2 ${
                          passwordsMismatch
                            ? 'border-rose-400 focus:ring-rose-500/20 focus:border-rose-500'
                            : passwordsMatch
                            ? 'border-emerald-400 focus:ring-emerald-500/20 focus:border-emerald-500'
                            : 'border-slate-300 focus:ring-brand-500/20 focus:border-brand-500'
                        }`}
                      />
                    </div>
                  </div>
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
                  disabled={passwordsMismatch}
                  iconRight={<ArrowRight className="w-4 h-4" />}
                >
                  Continue & Verify Email
                </Button>
              </form>
            )}

            {/* STEP 2: Email OTP Verification Form (Pure Email Verification) */}
            {step === 'EMAIL_OTP' && (
              <form onSubmit={(e) => handleEmailOtpVerify(e)} className="space-y-4">
                <div className="text-center pb-1">
                  <h2 className="text-xl font-black text-slate-900 tracking-tight">
                    Enter verification code
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">
                    We sent an 8-digit verification code to <strong className="text-slate-800 font-mono">{maskedEmail || email}</strong>
                  </p>
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-center space-y-2">
                  {isRecoveredSession && (
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200 shadow-xs mb-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
                      Pending Verification Session Restored
                    </div>
                  )}
                  <p className="text-[11px] text-slate-500">
                    Check your inbox or spam folder for the Kangra Hub verification email.
                  </p>

                  {/* 10-Minute Validity Indicator */}
                  <div className="pt-1">
                    {validitySeconds > 0 ? (
                      <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-brand-50 text-brand-700 border border-brand-200/80 shadow-xs">
                        <Clock className="w-3.5 h-3.5 text-brand-600 animate-pulse" />
                        <span>OTP valid for {formatValidityTime(validitySeconds)}</span>
                      </div>
                    ) : (
                      <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200/80 shadow-xs">
                        <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                        <span>OTP has expired (10-minute validity exceeded)</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* 8 Numeric Boxes with Paste and Auto-Submit (PRD Addendum 4 Section 1.5) */}
                <div className="py-1">
                  <OtpInput
                    value={emailOtp}
                    onChange={setEmailOtp}
                    onComplete={(code) => handleEmailOtpVerify(undefined, code)}
                    length={8}
                    disabled={loading || validitySeconds <= 0}
                    hasError={Boolean(error)}
                    autoFocus
                  />
                  {validitySeconds <= 0 && (
                    <p className="text-center text-xs text-rose-600 font-medium mt-2">
                      This OTP has expired. Click &quot;Send New OTP&quot; below to receive a new 10-minute code.
                    </p>
                  )}
                </div>

                {validitySeconds > 0 ? (
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    className="w-full"
                    loading={loading}
                    iconRight={<ArrowRight className="w-4 h-4" />}
                  >
                    Verify Email & Access Dashboard
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="primary"
                    size="md"
                    className="w-full"
                    onClick={handleResend}
                    loading={resending}
                    iconRight={<RefreshCw className="w-4 h-4" />}
                  >
                    Send New OTP (10 Minutes)
                  </Button>
                )}

                <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => {
                      try {
                        sessionStorage.removeItem('kangra_pending_signup');
                        localStorage.removeItem('kangra_pending_signup');
                      } catch {}
                      setStep('DETAILS');
                      setError('');
                    }}
                    className="text-slate-600 hover:text-slate-900 font-medium"
                  >
                    ← Change Email / Edit Details
                  </button>

                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={cooldown > 0 || resending}
                    className="text-brand-600 hover:text-brand-700 font-semibold disabled:text-slate-400"
                  >
                    {resending ? 'Sending...' : cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend Code'}
                  </button>
                </div>
              </form>
            )}

            <div className="pt-4 border-t border-slate-100 text-center text-xs text-slate-500 mt-6">
              Already have an account?{' '}
              <Link href="/login" className="text-brand-600 font-bold hover:underline">
                Sign In
              </Link>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-8 h-8 border-3 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <SignupContent />
    </Suspense>
  );
}
