'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { 
  KeyRound, 
  Search, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Clock, 
  ShieldCheck, 
  Mail, 
  ArrowRight, 
  UserCheck, 
  RotateCcw, 
  Plus, 
  Send, 
  FileSpreadsheet,
  Check,
  X
} from 'lucide-react';
import { 
  getAdminRecoveryRequests, 
  adminStep1Review, 
  adminSendStep2Code, 
  adminVerifyStep2Code, 
  adminCompleteRecovery, 
  adminRejectRecovery,
  adminCreateRecoveryRequest
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { Modal } from '@/components/ui/Modal';

function RecoveryConsoleContent() {
  const searchParams = useSearchParams();
  const prefillEmail = searchParams.get('email') || '';
  const urlId = searchParams.get('id') || '';

  const [requests, setRequests] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [search, setSearch] = useState(prefillEmail);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Review Modal State
  const [selectedReq, setSelectedReq] = useState<any>(null);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [step1Decision, setStep1Decision] = useState<'PASSED' | 'FAILED' | 'ADDITIONAL_VERIFICATION_REQUIRED'>('PASSED');
  const [step1Notes, setStep1Notes] = useState('');
  const [submittingStep1, setSubmittingStep1] = useState(false);

  // Step 2 State
  const [proposedNewEmail, setProposedNewEmail] = useState('');
  const [sendingStep2Code, setSendingStep2Code] = useState(false);
  const [step2OtpInput, setStep2OtpInput] = useState('');
  const [verifyingStep2, setVerifyingStep2] = useState(false);
  const [completingRecovery, setCompletingRecovery] = useState(false);
  const [step2DevCode, setStep2DevCode] = useState<string | null>(null);

  // Reject State
  const [rejectReason, setRejectReason] = useState('');
  const [rejecting, setRejecting] = useState(false);

  // New Request Modal State
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [newIdentifier, setNewIdentifier] = useState(prefillEmail);
  const [newReason, setNewReason] = useState('');
  const [newProposedEmail, setNewProposedEmail] = useState('');
  const [creatingRequest, setCreatingRequest] = useState(false);

  const fetchRequests = () => {
    setLoading(true);
    getAdminRecoveryRequests(statusFilter)
      .then((data) => {
        setRequests(data);
        setLoading(false);
        if (urlId && Array.isArray(data)) {
          const matched = data.find((r: any) => r.request_id === urlId || r.id === urlId);
          if (matched) {
            openReviewModal(matched);
          }
        }
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchRequests();
  }, [statusFilter]);

  const openReviewModal = (req: any) => {
    setSelectedReq(req);
    setStep1Decision(req.step1_status === 'FAILED' ? 'FAILED' : req.step1_status === 'ADDITIONAL_VERIFICATION_REQUIRED' ? 'ADDITIONAL_VERIFICATION_REQUIRED' : 'PASSED');
    setStep1Notes(req.step1_notes || '');
    setProposedNewEmail(req.proposed_new_email || req.requested_new_email || '');
    setStep2OtpInput('');
    setStep2DevCode(null);
    setRejectReason('');
    setIsReviewOpen(true);
  };

  const handleStep1Submit = async () => {
    if (!selectedReq) return;
    setSubmittingStep1(true);
    setErrorMsg('');
    try {
      const res = await adminStep1Review(selectedReq.id, step1Decision, step1Notes);
      setActionMsg(res.message || 'Step 1 review recorded.');
      setSelectedReq(res.request);
      fetchRequests();
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to submit Step 1 review.');
    } finally {
      setSubmittingStep1(false);
    }
  };

  const handleSendStep2Code = async () => {
    if (!selectedReq || !proposedNewEmail) return;
    setSendingStep2Code(true);
    setErrorMsg('');
    try {
      const res = await adminSendStep2Code(selectedReq.id, proposedNewEmail);
      setActionMsg(res.message || 'Verification code sent to proposed new email.');
      if (res.dev_code) {
        setStep2DevCode(res.dev_code);
      }
      fetchRequests();
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to dispatch verification code.');
    } finally {
      setSendingStep2Code(false);
    }
  };

  const handleVerifyStep2 = async () => {
    if (!selectedReq || !step2OtpInput) return;
    setVerifyingStep2(true);
    setErrorMsg('');
    try {
      const res = await adminVerifyStep2Code(selectedReq.id, step2OtpInput);
      setActionMsg(res.message || 'Step 2 new email verified successfully.');
      setSelectedReq(res.request);
      fetchRequests();
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Verification code check failed.');
    } finally {
      setVerifyingStep2(false);
    }
  };

  const handleCompleteRecovery = async () => {
    if (!selectedReq) return;
    setCompletingRecovery(true);
    setErrorMsg('');
    try {
      const res = await adminCompleteRecovery(selectedReq.id);
      setActionMsg(res.message || 'Account recovery completed successfully.');
      setSelectedReq(res.request);
      fetchRequests();
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to complete recovery.');
    } finally {
      setCompletingRecovery(false);
    }
  };

  const handleRejectRecovery = async () => {
    if (!selectedReq || !rejectReason.trim()) {
      setErrorMsg('Please specify a rejection reason.');
      return;
    }
    setRejecting(true);
    setErrorMsg('');
    try {
      const res = await adminRejectRecovery(selectedReq.id, rejectReason);
      setActionMsg(res.message || 'Recovery request rejected.');
      setSelectedReq(res.request);
      fetchRequests();
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to reject recovery request.');
    } finally {
      setRejecting(false);
    }
  };

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIdentifier.trim() || !newReason.trim()) {
      setErrorMsg('Identifier and reason are mandatory.');
      return;
    }
    setCreatingRequest(true);
    setErrorMsg('');
    try {
      const res = await adminCreateRecoveryRequest({
        account_identifier: newIdentifier.trim(),
        reason: newReason.trim(),
        requested_new_email: newProposedEmail.trim() || undefined,
      });
      setActionMsg('Recovery request created successfully.');
      setIsNewModalOpen(false);
      setNewIdentifier('');
      setNewReason('');
      setNewProposedEmail('');
      fetchRequests();
      if (res?.request) {
        openReviewModal(res.request);
      }
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create recovery request.');
    } finally {
      setCreatingRequest(false);
    }
  };

  const filteredRequests = requests.filter((r) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      r.id.toLowerCase().includes(s) ||
      r.account_identifier.toLowerCase().includes(s) ||
      (r.known_email && r.known_email.toLowerCase().includes(s)) ||
      (r.requested_new_email && r.requested_new_email.toLowerCase().includes(s)) ||
      (r.proposed_new_email && r.proposed_new_email.toLowerCase().includes(s)) ||
      r.status.toLowerCase().includes(s)
    );
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Completed':
      case 'Approved':
        return <Badge variant="success" size="sm">{status}</Badge>;
      case 'Under Review':
        return <Badge variant="primary" size="sm">{status}</Badge>;
      case 'Additional Verification Required':
        return <Badge variant="warning" size="sm">{status}</Badge>;
      case 'Rejected':
        return <Badge variant="danger" size="sm">{status}</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{status || 'Pending'}</Badge>;
    }
  };

  const getStepBadge = (stepStatus: string) => {
    switch (stepStatus) {
      case 'PASSED':
      case 'VERIFIED':
        return <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200"><Check className="w-3 h-3 text-emerald-600" /> {stepStatus}</span>;
      case 'FAILED':
        return <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-rose-50 px-2 py-0.5 rounded-full border border-red-200"><X className="w-3 h-3 text-rose-600" /> FAILED</span>;
      case 'CODE_SENT':
        return <span className="inline-flex items-center gap-1 text-[11px] font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded-full border border-brand-200"><Mail className="w-3 h-3 text-brand-600" /> CODE SENT</span>;
      case 'ADDITIONAL_VERIFICATION_REQUIRED':
        return <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200"><Clock className="w-3 h-3 text-amber-600" /> MORE INFO</span>;
      default:
        return <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">PENDING</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-black text-slate-900 tracking-tight">
              Two-Step Account Recovery Console
            </h1>
            <Badge variant="purple" size="sm">
              PRD P0 Security
            </Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Audited identity verification and email transfer workflow for lost account contacts
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchRequests}
            icon={<RotateCcw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsNewModalOpen(true)}
            icon={<Plus className="w-3.5 h-3.5" />}
          >
            New Recovery Request
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {actionMsg && (
        <StatusAlert
          type="success"
          message={actionMsg}
          onDismiss={() => setActionMsg('')}
        />
      )}
      {errorMsg && (
        <StatusAlert
          type="error"
          message={errorMsg}
          onDismiss={() => setErrorMsg('')}
        />
      )}

      {/* Filter and Search Bar */}
      <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Status:</span>
          {['ALL', 'Pending', 'Under Review', 'Additional Verification Required', 'Approved', 'Completed', 'Rejected'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                statusFilter === st
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search request or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
          />
        </div>
      </div>

      {/* Recovery Requests Table */}
      <Card>
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading account recovery records...
          </div>
        ) : filteredRequests.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-2">
            <UserCheck className="w-8 h-8 text-slate-300 mx-auto" />
            <div className="text-xs font-semibold text-slate-700">No account recovery requests found</div>
            <p className="text-[11px] text-slate-400">All registered users are verified and operating normally.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">\n<Table>
            <TableHeader>
              <tr>
                <TableHead>Request Reference</TableHead>
                <TableHead>Account Identifier</TableHead>
                <TableHead>Proposed New Email</TableHead>
                <TableHead align="center">Step 1: Ownership</TableHead>
                <TableHead align="center">Step 2: New Email OTP</TableHead>
                <TableHead>Status</TableHead>
                <TableHead align="right">Administrative Action</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {filteredRequests.map((req) => (
                <TableRow key={req.id}>
                  <TableCell>
                    <div className="font-mono font-bold text-slate-900 text-xs">{req.id}</div>
                    <div className="text-[10px] text-slate-400">
                      {new Date(req.submitted_at).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-mono text-xs text-slate-800 font-semibold">{req.account_identifier}</div>
                    <div className="text-[10px] text-slate-400 truncate max-w-[180px]">{req.reason}</div>
                  </TableCell>
                  <TableCell>
                    <div className="font-mono text-xs text-brand-700 font-medium">
                      {req.proposed_new_email || req.requested_new_email || <span className="text-slate-400">Not specified yet</span>}
                    </div>
                  </TableCell>
                  <TableCell align="center">
                    {getStepBadge(req.step1_status)}
                  </TableCell>
                  <TableCell align="center">
                    {getStepBadge(req.step2_status)}
                  </TableCell>
                  <TableCell>
                    {getStatusBadge(req.status)}
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openReviewModal(req)}
                      icon={<KeyRound className="w-3.5 h-3.5 text-brand-600" />}
                    >
                      Inspect & Review
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>\n</div>
        )}
      </Card>

      {/* Two-Step Verification Dossier & Review Modal */}
      <Modal
        isOpen={isReviewOpen}
        onClose={() => setIsReviewOpen(false)}
        title={`Account Recovery Dossier — ${selectedReq?.id || ''}`}
        size="lg"
      >
        {selectedReq && (
          <div className="space-y-6">
            {/* Top Summary Banner */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs font-bold text-slate-900">Current Account: <span className="font-mono text-brand-700">{selectedReq.account_identifier}</span></div>
                <div className="text-[11px] text-slate-500 mt-0.5">Reason: {selectedReq.reason}</div>
              </div>
              <div className="flex items-center gap-2">
                {getStatusBadge(selectedReq.status)}
              </div>
            </div>

            {/* Account History Cross-Check Details (Step 1 Verification Evidence) */}
            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs space-y-2.5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <FileSpreadsheet className="w-3.5 h-3.5 text-slate-500" />
                Account History Cross-Check (Ownership Evidence)
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">User ID</span>
                  <div className="font-mono font-bold text-slate-800 mt-0.5">{selectedReq.account_history?.user_id || selectedReq.user_id || 'Matched by email'}</div>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Name</span>
                  <div className="font-semibold text-slate-800 mt-0.5">{selectedReq.account_history?.full_name || 'Verified User'}</div>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Total Conversions</span>
                  <div className="font-mono font-bold text-slate-800 mt-0.5">{selectedReq.account_history?.total_conversions || 0} files</div>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Registered At</span>
                  <div className="font-mono text-[11px] text-slate-700 mt-0.5">{selectedReq.account_history?.registered_at ? new Date(selectedReq.account_history.registered_at).toLocaleDateString('en-IN') : 'Jan 2024'}</div>
                </div>
              </div>
              {selectedReq.identity_verification_info && (
                <div className="p-2.5 bg-brand-50/70 border border-blue-100 rounded-lg text-xs text-blue-900 mt-2">
                  <span className="font-bold">Applicant Note:</span> {selectedReq.identity_verification_info}
                </div>
              )}
            </div>

            {/* STEP 1 PANEL: Admin Ownership Cross-Check */}
            <div className={`p-4.5 rounded-2xl border ${selectedReq.step1_status === 'PASSED' ? 'bg-emerald-50/40 border-emerald-200' : 'bg-slate-50 border-slate-200'} space-y-3.5`}>
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 flex items-center gap-1.5">
                    <span>STEP 1 — Account Ownership Cross-Check</span>
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Verify conversion history, registration timestamp, and applicant claims before approving email change
                  </p>
                </div>
                {getStepBadge(selectedReq.step1_status)}
              </div>

              <div className="space-y-3 pt-1">
                <div className="flex flex-wrap gap-4 text-xs font-semibold">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="step1Decision"
                      value="PASSED"
                      checked={step1Decision === 'PASSED'}
                      onChange={() => setStep1Decision('PASSED')}
                      className="text-emerald-600 focus:ring-emerald-500"
                    />
                    <span className="text-emerald-800">Pass Step 1 (Verified Owner)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="step1Decision"
                      value="ADDITIONAL_VERIFICATION_REQUIRED"
                      checked={step1Decision === 'ADDITIONAL_VERIFICATION_REQUIRED'}
                      onChange={() => setStep1Decision('ADDITIONAL_VERIFICATION_REQUIRED')}
                      className="text-amber-600 focus:ring-amber-500"
                    />
                    <span className="text-amber-800">Request Additional Info</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="step1Decision"
                      value="FAILED"
                      checked={step1Decision === 'FAILED'}
                      onChange={() => setStep1Decision('FAILED')}
                      className="text-rose-600 focus:ring-red-500"
                    />
                    <span className="text-red-800">Fail Step 1 (Reject Ownership)</span>
                  </label>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Internal Admin Notes & Cross-Check Rationale:</label>
                  <input
                    type="text"
                    placeholder="e.g. Cross-checked with recent SBI statement conversion of 21 pages."
                    value={step1Notes}
                    onChange={(e) => setStep1Notes(e.target.value)}
                    className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                </div>

                <div className="flex justify-end pt-1">
                  <Button
                    variant="primary"
                    size="sm"
                    loading={submittingStep1}
                    onClick={handleStep1Submit}
                  >
                    Save Step 1 Decision
                  </Button>
                </div>
              </div>
            </div>

            {/* STEP 2 PANEL: New Email Verification */}
            <div className={`p-4.5 rounded-2xl border ${selectedReq.step1_status !== 'PASSED' ? 'bg-slate-100 opacity-60 border-slate-200' : selectedReq.step2_status === 'VERIFIED' ? 'bg-emerald-50/40 border-emerald-200' : 'bg-slate-50 border-slate-200'} space-y-3.5`}>
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 flex items-center gap-1.5">
                    <span>STEP 2 — New Email Verification</span>
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Dispatch verification code to proposed new email. The new email must be verified before completing change.
                  </p>
                </div>
                {getStepBadge(selectedReq.step2_status)}
              </div>

              {selectedReq.step1_status !== 'PASSED' ? (
                <div className="p-3 bg-slate-200/70 rounded-xl text-xs text-slate-600 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-slate-500 shrink-0" />
                  <span>Step 1 ownership verification must be completed and PASSED before Step 2 can be initiated.</span>
                </div>
              ) : (
                <div className="space-y-3 pt-1">
                  {/* Step 2A: Send Code */}
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <input
                      type="email"
                      placeholder="Enter proposed new email (e.g. user.new@example.com)"
                      value={proposedNewEmail}
                      onChange={(e) => setProposedNewEmail(e.target.value)}
                      disabled={selectedReq.step2_status === 'VERIFIED'}
                      className="flex-1 px-3 py-1.5 bg-white border border-slate-300 rounded-xl text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={sendingStep2Code}
                      disabled={selectedReq.step2_status === 'VERIFIED' || !proposedNewEmail}
                      onClick={handleSendStep2Code}
                      icon={<Send className="w-3.5 h-3.5" />}
                    >
                      {selectedReq.step2_status === 'CODE_SENT' ? 'Resend Code' : 'Send Code'}
                    </Button>
                  </div>

                  {step2DevCode && (
                    <div className="p-2.5 bg-brand-50 border border-brand-200 rounded-xl text-xs text-brand-900 flex items-center justify-between">
                      <span>Dev environment simulation code: <strong className="font-mono font-bold text-sm tracking-widest">{step2DevCode}</strong></span>
                      <button
                        onClick={() => setStep2OtpInput(step2DevCode)}
                        className="text-[11px] text-brand-700 underline font-semibold hover:text-brand-800"
                      >
                        Auto-fill
                      </button>
                    </div>
                  )}

                  {/* Step 2B: Verify Code */}
                  {selectedReq.step2_status !== 'VERIFIED' && (
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2 border-t border-slate-200/70">
                      <input
                        type="text"
                        maxLength={8}
                        placeholder="Enter 6-digit code received on new email"
                        value={step2OtpInput}
                        onChange={(e) => setStep2OtpInput(e.target.value.replace(/[^0-9]/g, ''))}
                        className="flex-1 px-3 py-1.5 bg-white border border-slate-300 rounded-xl text-xs font-mono tracking-wider text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                      />
                      <Button
                        variant="primary"
                        size="sm"
                        loading={verifyingStep2}
                        disabled={!step2OtpInput || step2OtpInput.length < 6}
                        onClick={handleVerifyStep2}
                        icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                      >
                        Verify Code
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* COMPLETION / REJECTION ACTION BAR */}
            <div className="p-4 bg-slate-100/80 rounded-2xl border border-slate-200 flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-slate-600">
                {selectedReq.status === 'Completed' ? (
                  <span className="font-bold text-emerald-700 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Recovery Completed. User can now log in with {selectedReq.proposed_new_email}.
                  </span>
                ) : selectedReq.step1_status === 'PASSED' && selectedReq.step2_status === 'VERIFIED' ? (
                  <span className="font-bold text-brand-700 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-brand-600" />
                    Both verification steps PASSED. Ready to commit email change.
                  </span>
                ) : (
                  <span>Both Step 1 and Step 2 must be verified to complete recovery.</span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {selectedReq.status !== 'Completed' && selectedReq.status !== 'Rejected' && (
                  <>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={handleRejectRecovery}
                      loading={rejecting}
                    >
                      Reject Request
                    </Button>

                    <Button
                      variant="primary"
                      size="sm"
                      loading={completingRecovery}
                      disabled={selectedReq.step1_status !== 'PASSED' || selectedReq.step2_status !== 'VERIFIED'}
                      onClick={handleCompleteRecovery}
                      icon={<ShieldCheck className="w-4 h-4" />}
                    >
                      Complete Email Change
                    </Button>
                  </>
                )}
              </div>
            </div>

          </div>
        )}
      </Modal>

      {/* New Request Creation Modal */}
      <Modal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        title="Initiate Account Recovery Request"
        size="md"
      >
        <form onSubmit={handleCreateRequest} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Account Identifier (Registered Email, Mobile, or User ID)
            </label>
            <input
              type="text"
              required
              placeholder="e.g. customer@example.com"
              value={newIdentifier}
              onChange={(e) => setNewIdentifier(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Recovery Reason & Evidence
            </label>
            <textarea
              required
              rows={3}
              placeholder="e.g. Lost access to old domain email. Has verified previous SBI statement conversions."
              value={newReason}
              onChange={(e) => setNewReason(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Proposed New Email (Optional at this stage)
            </label>
            <input
              type="email"
              placeholder="e.g. customer.new@example.com"
              value={newProposedEmail}
              onChange={(e) => setNewProposedEmail(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsNewModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              loading={creatingRequest}
            >
              Submit Recovery Request
            </Button>
          </div>
        </form>
      </Modal>

    </div>
  );
}

export default function AdminRecoveryPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-400">Loading Account Recovery Console...</div>}>
      <RecoveryConsoleContent />
    </Suspense>
  );
}
