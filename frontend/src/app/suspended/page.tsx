'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useSearchParams } from 'next/navigation';
import { 
  ShieldAlert, 
  Clock, 
  Calendar, 
  Send, 
  CheckCircle2, 
  AlertTriangle, 
  MessageSquare, 
  ArrowLeft, 
  RefreshCw, 
  HelpCircle,
  FileText
} from 'lucide-react';
import { submitAccountAppeal, getUserAppealStatus } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { StatusAlert } from '@/components/ui/StatusAlert';

function SuspendedContent() {
  const searchParams = useSearchParams();

  const paramEmail = searchParams.get('email') || '';
  const paramName = searchParams.get('name') || '';
  const paramUserId = searchParams.get('user_id') || '';
  const paramReason = searchParams.get('reason') || '';
  const paramSuspendedAt = searchParams.get('suspended_at') || '';
  const paramDeleteAt = searchParams.get('delete_at') || '';

  // Appeal Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [emailInput, setEmailInput] = useState(paramEmail);
  const [nameInput, setNameInput] = useState(paramName);
  const [userIdInput, setUserIdInput] = useState(paramUserId);
  const [subject, setSubject] = useState('Request to review my suspended account');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitSuccess, setSubmitSuccess] = useState<any>(null);

  // Live Appeal Tracker State
  const [existingAppeal, setExistingAppeal] = useState<any>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);

  // Format Dynamic 3-Month Scheduled Deletion Date
  const formatDeletionDate = (dateStr?: string) => {
    let targetDate: Date;
    if (dateStr) {
      targetDate = new Date(dateStr);
    } else if (paramSuspendedAt) {
      targetDate = new Date(paramSuspendedAt);
      targetDate.setDate(targetDate.getDate() + 90);
    } else {
      targetDate = new Date();
      targetDate.setDate(targetDate.getDate() + 90);
    }
    
    if (isNaN(targetDate.getTime())) {
      targetDate = new Date();
      targetDate.setDate(targetDate.getDate() + 90);
    }

    return targetDate.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  };

  const formattedDeletionDate = formatDeletionDate(paramDeleteAt);

  // Fetch Existing Appeal Status if Email Available
  const checkAppealStatus = async (emailToCheck: string) => {
    if (!emailToCheck) return;
    setCheckingStatus(true);
    try {
      const res = await getUserAppealStatus(emailToCheck);
      if (res.has_appeal && res.appeal) {
        setExistingAppeal(res.appeal);
      } else {
        setExistingAppeal(null);
      }
    } catch {
      // ignore
    } finally {
      setCheckingStatus(false);
    }
  };

  useEffect(() => {
    if (paramEmail) {
      checkAppealStatus(paramEmail);
    }
  }, [paramEmail]);

  const handleSubmitAppeal = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');

    const targetEmail = emailInput.trim();
    if (!targetEmail || !targetEmail.includes('@')) {
      setSubmitError('Please enter a valid registered email address.');
      return;
    }

    const cleanMsg = message.trim();
    if (!cleanMsg) {
      setSubmitError('Please provide a message explaining your situation.');
      return;
    }

    if (cleanMsg.length < 10) {
      setSubmitError('Please provide a more detailed explanation for your appeal (minimum 10 characters).');
      return;
    }

    setSubmitting(true);
    try {
      const res = await submitAccountAppeal({
        email: targetEmail,
        user_name: nameInput.trim() || undefined,
        user_id: userIdInput.trim() || undefined,
        subject: subject.trim(),
        message: cleanMsg
      });

      setSubmitSuccess({
        requestId: res.request_id,
        message: res.message
      });
      setMessage('');
      // Reload status
      checkAppealStatus(targetEmail);
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to submit appeal. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-navy-50 gradient-surface flex items-center justify-center p-4 sm:p-6 lg:p-8">
      <div className="max-w-2xl w-full bg-white glass-card rounded-3xl border border-navy-200/60 shadow-modal overflow-hidden">
        
        {/* Header Ribbon */}
        <div className="bg-gradient-to-r from-amber-600 via-rose-600 to-red-600 p-6 text-white text-center sm:text-left sm:flex sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center flex-shrink-0 border border-white/20">
              <ShieldAlert className="w-7 h-7 text-white" />
            </div>
            <div>
              <div className="text-[11px] font-bold text-amber-200 tracking-wider uppercase">
                Account Status Notification
              </div>
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                Your Account Has Been Suspended
              </h1>
            </div>
          </div>
          <div className="mt-3 sm:mt-0">
            <Badge variant="warning" size="sm" className="bg-white/20 text-white border-white/30">
              Access Restricted
            </Badge>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 sm:p-8 space-y-6">
          
          {/* Main Informational Notice */}
          <div className="space-y-3">
            <p className="text-sm sm:text-base text-navy-700 leading-relaxed font-medium">
              Your Kangra Hub account has been temporarily suspended due to a policy or account-related issue.
            </p>
            <p className="text-xs sm:text-sm text-navy-500 leading-relaxed">
              You currently cannot access your Kangra Hub account, PDF conversion engine, or services while the suspension is active.
            </p>
          </div>

          {/* Specific Suspension Reason if provided */}
          {paramReason && (
            <div className="bg-amber-50/80 border border-amber-200 rounded-2xl p-4 sm:p-5 flex items-start gap-3.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="space-y-1 text-xs sm:text-sm">
                <span className="font-bold text-amber-950 block">Reason for Suspension:</span>
                <span className="text-amber-900 leading-relaxed block">{paramReason}</span>
              </div>
            </div>
          )}

          {/* Deletion Warning Box with Dynamic 3-Month Date */}
          <div className="bg-navy-50 gradient-surface border border-navy-200/60 rounded-2xl p-4 sm:p-5 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-navy-800 uppercase tracking-wider">
              <Clock className="w-4 h-4 text-navy-500" />
              <span>Data Retention & Scheduled Deletion Notice</span>
            </div>
            <p className="text-xs text-navy-600 leading-relaxed">
              <strong>Important:</strong> If your account remains suspended, it may be scheduled for permanent deletion <strong>3 months</strong> after the suspension date. You can contact the administrator or submit an appeal for review before this date.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <Calendar className="w-4 h-4 text-brand-600" />
              <span className="text-xs text-navy-700 font-semibold">
                Scheduled deletion date:
              </span>
              <span className="text-xs font-black text-rose-600 bg-rose-50 px-2.5 py-0.5 rounded-full border border-rose-200">
                {formattedDeletionDate}
              </span>
            </div>
          </div>

          {/* Active Appeal Status Tracker (PRD Section 18) */}
          {existingAppeal && (
            <div className="bg-brand-50/60 border border-brand-200 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-brand-600" />
                  <span className="text-xs font-bold text-navy-900">My Submitted Appeal</span>
                </div>
                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => checkAppealStatus(paramEmail || emailInput)}
                    disabled={checkingStatus}
                    className="text-[11px] text-brand-600 hover:text-brand-800 flex items-center gap-1 font-medium"
                  >
                    <RefreshCw className={`w-3 h-3 ${checkingStatus ? 'animate-spin' : ''}`} />
                    Refresh
                  </button>
                  {existingAppeal.status === 'approved' ? (
                    <Badge variant="success" size="sm">Approved</Badge>
                  ) : existingAppeal.status === 'rejected' ? (
                    <Badge variant="danger" size="sm">Rejected</Badge>
                  ) : existingAppeal.status === 'under_review' ? (
                    <Badge variant="purple" size="sm">Under Review</Badge>
                  ) : (
                    <Badge variant="warning" size="sm">Pending Review</Badge>
                  )}
                </div>
              </div>

              <div className="space-y-1.5 text-xs text-navy-600">
                <div className="flex items-center justify-between text-[11px] text-navy-500">
                  <span>Submitted: {new Date(existingAppeal.created_at).toLocaleString()}</span>
                  <span>ID: {existingAppeal.id.slice(0, 8)}...</span>
                </div>
                <div className="bg-white glass-card p-3 rounded-xl border border-navy-200/60 text-navy-700">
                  <div className="font-semibold text-navy-900 mb-0.5">{existingAppeal.subject}</div>
                  <div className="text-navy-600 line-clamp-3">{existingAppeal.message}</div>
                </div>
              </div>

              {existingAppeal.admin_response && (
                <div className="bg-amber-50/90 border border-amber-200 p-3 rounded-xl space-y-1 text-xs">
                  <span className="font-bold text-amber-950 block">Administrator Response:</span>
                  <span className="text-amber-900 leading-relaxed block">{existingAppeal.admin_response}</span>
                </div>
              )}

              {existingAppeal.status === 'approved' && (
                <div className="pt-2">
                  <Link href="/login">
                    <Button variant="primary" size="sm" className="w-full">
                      Account Recovered &bull; Return to Sign In
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div className="pt-2 flex flex-col sm:flex-row items-center gap-3">
            <Button
              variant="primary"
              size="lg"
              className="w-full sm:flex-1 py-3 text-sm font-extrabold shadow-md hover:shadow-lg"
              onClick={() => {
                setSubmitSuccess(null);
                setSubmitError('');
                setIsModalOpen(true);
              }}
            >
              <MessageSquare className="w-4 h-4 mr-2" />
              Contact Administrator / Submit Appeal
            </Button>
            <Link href="/login" className="w-full sm:w-auto">
              <Button variant="outline" size="lg" className="w-full text-xs font-bold text-navy-600">
                <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
                Return to Login
              </Button>
            </Link>
          </div>

          {/* Footer Assistance */}
          <div className="pt-4 border-t border-navy-100 flex items-center justify-between text-[11px] text-navy-400">
            <span>Kangra Hub Account Security</span>
            <Link href="/contact" className="hover:text-brand-600 transition-colors flex items-center gap-1">
              <HelpCircle className="w-3 h-3" />
              General Help Desk
            </Link>
          </div>
        </div>
      </div>

      {/* Contact / Appeal Modal (PRD Sections 7, 8) */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Contact Administrator / Submit Appeal"
        size="lg"
      >
        {submitSuccess ? (
          <div className="p-6 text-center space-y-4">
            <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-black text-navy-900 tracking-tight">Appeal Submitted</h3>
              <p className="text-xs text-navy-500 max-w-md mx-auto leading-relaxed">
                {submitSuccess.message}
              </p>
            </div>
            <div className="bg-navy-50 gradient-surface border border-navy-200/60 rounded-xl p-3 inline-block">
              <span className="text-xs text-navy-500">Request ID: </span>
              <span className="font-mono text-xs font-bold text-navy-900">{submitSuccess.requestId}</span>
            </div>
            <div className="pt-4">
              <Button variant="primary" onClick={() => setIsModalOpen(false)} className="w-full">
                Close & Return
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmitAppeal} className="p-6 space-y-4">
            {submitError && (
              <StatusAlert
                type="error"
                message={submitError}
                onDismiss={() => setSubmitError('')}
              />
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Name */}
              <div className="space-y-1">
                <label className="text-xs font-bold text-navy-700">Account Name</label>
                <input
                  type="text"
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  placeholder="Your full name"
                  disabled={!!paramName}
                  className={`w-full px-3 py-2 text-xs rounded-xl border border-navy-300/60 ${paramName ? 'bg-navy-100 text-navy-500 cursor-not-allowed' : 'bg-white text-navy-900'}`}
                />
              </div>

              {/* Email */}
              <div className="space-y-1">
                <label className="text-xs font-bold text-navy-700">Registered Email Address</label>
                <input
                  type="email"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  placeholder="your-email@example.com"
                  disabled={!!paramEmail}
                  required
                  className={`w-full px-3 py-2 text-xs rounded-xl border border-navy-300/60 ${paramEmail ? 'bg-navy-100 text-navy-500 cursor-not-allowed' : 'bg-white text-navy-900'}`}
                />
              </div>
            </div>

            {/* User ID */}
            {paramUserId && (
              <div className="space-y-1">
                <label className="text-xs font-bold text-navy-700">User ID</label>
                <input
                  type="text"
                  value={userIdInput}
                  disabled
                  className="w-full px-3 py-2 text-xs rounded-xl border border-navy-300/60 bg-navy-100 text-navy-500 cursor-not-allowed font-mono"
                />
              </div>
            )}

            {/* Appeal Subject */}
            <div className="space-y-1">
              <label className="text-xs font-bold text-navy-700">Appeal Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Request to review my suspended account"
                className="w-full px-3 py-2 text-xs rounded-xl border border-navy-300/60 bg-white text-navy-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-accent-500 focus:ring-accent-500/20"
              />
            </div>

            {/* Message */}
            <div className="space-y-1">
              <label className="text-xs font-bold text-navy-700">Tell us about your issue</label>
              <textarea
                rows={5}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Please explain your situation, provide any relevant information, or tell us why you believe your account should be reviewed."
                required
                className="w-full px-3.5 py-2.5 text-xs rounded-xl border border-navy-300/60 bg-white text-navy-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-accent-500 focus:ring-accent-500/20 placeholder:text-navy-400 resize-none leading-relaxed"
              />
              <div className="flex justify-between items-center text-[10px] text-navy-400 pt-0.5">
                <span>Minimum 10 characters</span>
                <span>{message.trim().length} characters</span>
              </div>
            </div>

            <div className="pt-3 flex items-center justify-end gap-2.5">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsModalOpen(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={submitting || message.trim().length < 10}
              >
                {submitting ? (
                  <span className="flex items-center gap-1.5">
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Submitting Appeal...
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <Send className="w-3.5 h-3.5" />
                    Submit Appeal
                  </span>
                )}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}

export default function SuspendedPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-navy-50 gradient-surface flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <SuspendedContent />
    </Suspense>
  );
}
