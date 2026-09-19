'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ArrowLeft, ArrowRight, CheckCircle2, Search } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { submitAccountRecovery, getAccountRecoveryStatus } from '@/lib/api';

export default function AccountRecoveryPage() {
  const [activeTab, setActiveTab] = useState<'SUBMIT' | 'TRACK'>('SUBMIT');

  // Submit Form States
  const [accountIdentifier, setAccountIdentifier] = useState('');
  const [knownEmail, setKnownEmail] = useState('');
  const [knownMobile, setKnownMobile] = useState('');
  const [requestedNewEmail, setRequestedNewEmail] = useState('');
  const [requestedNewMobile, setRequestedNewMobile] = useState('');
  const [reason, setReason] = useState('');
  const [identityInfo, setIdentityInfo] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submittedResult, setSubmittedResult] = useState<{ reference_id: string; message: string } | null>(null);

  // Track Status States
  const [trackRefId, setTrackRefId] = useState('');
  const [tracking, setTracking] = useState(false);
  const [trackError, setTrackError] = useState('');
  const [trackResult, setTrackResult] = useState<any | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSubmittedResult(null);

    if (!accountIdentifier.trim()) {
      setSubmitError('Please provide your registered account identifier (email or phone).');
      return;
    }
    if (!reason.trim()) {
      setSubmitError('Please provide a reason explaining why you need account recovery.');
      return;
    }
    if (!requestedNewEmail.trim() && !requestedNewMobile.trim()) {
      setSubmitError('Please provide at least one new contact detail (new email or new mobile number).');
      return;
    }

    setSubmitting(true);
    try {
      const res = await submitAccountRecovery({
        account_identifier: accountIdentifier.trim(),
        known_email: knownEmail.trim() || undefined,
        known_mobile: knownMobile.trim() || undefined,
        requested_new_email: requestedNewEmail.trim() || undefined,
        requested_new_mobile: requestedNewMobile.trim() || undefined,
        reason: reason.trim(),
        identity_verification_info: identityInfo.trim() || undefined,
      });
      setSubmittedResult({
        reference_id: res.reference_id,
        message: res.message || 'Your recovery request has been received.',
      });
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to submit recovery request. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTrack = async (e: React.FormEvent) => {
    e.preventDefault();
    setTrackError('');
    setTrackResult(null);

    if (!trackRefId.trim()) {
      setTrackError('Please enter your recovery Reference ID.');
      return;
    }

    setTracking(true);
    try {
      const res = await getAccountRecoveryStatus(trackRefId.trim());
      setTrackResult(res);
    } catch (err: any) {
      setTrackError(err.message || 'Recovery request not found. Please verify the Reference ID.');
    } finally {
      setTracking(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center p-4 sm:p-6 bg-slate-50">
      <div className="max-w-xl w-full bg-white p-6 sm:p-9 rounded-3xl border border-slate-200 shadow-elevated">
        
        {/* Header */}
        <div className="text-center mb-6">
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
            Account Recovery Assistance
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Controlled recovery workflow for users who lost access to their registered email and phone.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-slate-200 mb-6">
          <button
            type="button"
            onClick={() => setActiveTab('SUBMIT')}
            className={`flex-1 py-2.5 text-xs font-bold border-b-2 transition-colors ${
              activeTab === 'SUBMIT'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Submit Recovery Request
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('TRACK')}
            className={`flex-1 py-2.5 text-xs font-bold border-b-2 transition-colors ${
              activeTab === 'TRACK'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Track Status
          </button>
        </div>

        {/* TAB 1: SUBMIT */}
        {activeTab === 'SUBMIT' && (
          <div>
            {submittedResult ? (
              <div className="text-center py-6 space-y-4">
                <div className="w-14 h-14 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-base font-bold text-slate-900">Request Successfully Submitted</h2>
                  <p className="text-xs text-slate-600 leading-relaxed max-w-sm mx-auto">
                    {submittedResult.message}
                  </p>
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl font-mono text-sm font-bold text-slate-800 inline-block">
                    Reference ID: <span className="text-brand-600">{submittedResult.reference_id}</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Save this reference ID to track your request status anytime on this page.
                  </p>
                </div>
                <div className="pt-3 flex justify-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSubmittedResult(null);
                      setAccountIdentifier('');
                      setReason('');
                      setRequestedNewEmail('');
                      setRequestedNewMobile('');
                    }}
                  >
                    Submit Another Request
                  </Button>
                  <Link href="/login">
                    <Button variant="primary" size="sm">
                      Return to Sign In
                    </Button>
                  </Link>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {submitError && (
                  <StatusAlert
                    type="error"
                    message={submitError}
                    onDismiss={() => setSubmitError('')}
                  />
                )}

                <Input
                  label="Registered Account Identifier"
                  type="text"
                  required
                  placeholder="name@company.com or 9876543210"
                  value={accountIdentifier}
                  onChange={(e) => setAccountIdentifier(e.target.value)}
                  helperText="The email address or mobile number originally associated with your account"
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Input
                    label="Known Previous Email"
                    type="email"
                    placeholder="old-email@company.com"
                    value={knownEmail}
                    onChange={(e) => setKnownEmail(e.target.value)}
                  />
                  <Input
                    label="Known Previous Mobile"
                    type="tel"
                    placeholder="9876543210"
                    value={knownMobile}
                    onChange={(e) => setKnownMobile(e.target.value)}
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Input
                    label="Requested New Email"
                    type="email"
                    placeholder="new-email@company.com"
                    value={requestedNewEmail}
                    onChange={(e) => setRequestedNewEmail(e.target.value)}
                  />
                  <Input
                    label="Requested New Mobile"
                    type="tel"
                    placeholder="9876543210"
                    value={requestedNewMobile}
                    onChange={(e) => setRequestedNewMobile(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Reason for Recovery <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    required
                    rows={3}
                    placeholder="Describe what happened to your previous contact credentials..."
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    className="w-full bg-white text-xs text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 p-3 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600 resize-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Identity Verification Details (Optional)
                  </label>
                  <textarea
                    rows={2}
                    placeholder="Any proof or details to help security staff verify your identity..."
                    value={identityInfo}
                    onChange={(e) => setIdentityInfo(e.target.value)}
                    className="w-full bg-white text-xs text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 p-3 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600 resize-none"
                  />
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  className="w-full mt-2"
                  loading={submitting}
                  iconRight={<ArrowRight className="w-4 h-4" />}
                >
                  Submit Recovery Request
                </Button>
              </form>
            )}
          </div>
        )}

        {/* TAB 2: TRACK */}
        {activeTab === 'TRACK' && (
          <div className="space-y-5">
            <form onSubmit={handleTrack} className="flex gap-2">
              <div className="flex-1">
                <input
                  type="text"
                  required
                  placeholder="Enter Reference ID (e.g. REC-A1B2C3D4)"
                  value={trackRefId}
                  onChange={(e) => setTrackRefId(e.target.value)}
                  className="w-full bg-white text-xs text-slate-900 placeholder:text-slate-400 rounded-xl border border-slate-300 px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                />
              </div>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                loading={tracking}
                icon={<Search className="w-4 h-4" />}
              >
                Track
              </Button>
            </form>

            {trackError && (
              <StatusAlert
                type="error"
                message={trackError}
                onDismiss={() => setTrackError('')}
              />
            )}

            {trackResult && (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-medium">Request Reference</span>
                  <span className="font-mono text-xs font-bold text-slate-900">{trackResult.reference_id || trackResult.request_reference}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-medium">Review Status</span>
                  <span className={`text-xs font-black uppercase px-2.5 py-0.5 rounded-full ${
                    trackResult.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-800' :
                    trackResult.status === 'REJECTED' ? 'bg-rose-100 text-rose-800' :
                    'bg-amber-100 text-amber-800'
                  }`}>
                    {trackResult.status}
                  </span>
                </div>
                {trackResult.decision_reason && (
                  <div className="pt-2 border-t border-slate-200 text-xs">
                    <span className="font-bold text-slate-700">Staff Note: </span>
                    <span className="text-slate-600">{trackResult.decision_reason}</span>
                  </div>
                )}
                {trackResult.reviewed_at && (
                  <div className="text-[11px] text-slate-400">
                    Reviewed on: {new Date(trackResult.reviewed_at).toLocaleString('en-IN')}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="text-center pt-5 mt-6 border-t border-slate-100">
          <Link
            href="/login"
            className="text-xs font-semibold text-slate-500 hover:text-slate-800 inline-flex items-center gap-1.5 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Return to Login
          </Link>
        </div>

      </div>
    </div>
  );
}
