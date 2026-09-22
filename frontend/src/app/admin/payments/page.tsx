'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { 
  CreditCard, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Search, 
  RefreshCw, 
  Eye, 
  Check, 
  X, 
  AlertCircle,
  ExternalLink,
  MessageCircle,
  FileImage,
  DollarSign
} from 'lucide-react';
import { 
  getAdminPaymentRequests, 
  approvePaymentRequest, 
  rejectPaymentRequest, 
  PaymentRequest 
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { StatusAlert } from '@/components/ui/StatusAlert';

export default function AdminPaymentsPage() {
  const searchParams = useSearchParams();
  const highlightRequestId = searchParams.get('requestId');

  const [requests, setRequests] = useState<PaymentRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState<'ALL' | 'PENDING' | 'APPROVED' | 'REJECTED'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Alert messages
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Screenshot viewer modal
  const [viewingScreenshotUrl, setViewingScreenshotUrl] = useState<string | null>(null);

  // Approve modal
  const [approveTarget, setApproveTarget] = useState<PaymentRequest | null>(null);
  const [grantedPagesInput, setGrantedPagesInput] = useState<number>(0);
  const [approveNotesInput, setApproveNotesInput] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Reject modal
  const [rejectTarget, setRejectTarget] = useState<PaymentRequest | null>(null);
  const [rejectReasonInput, setRejectReasonInput] = useState('');

  const loadRequests = async () => {
    setLoading(true);
    try {
      const data = await getAdminPaymentRequests();
      setRequests(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load page purchase requests.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, []);

  // If URL has ?requestId=..., switch tab to ALL or find request
  useEffect(() => {
    if (highlightRequestId && requests.length > 0) {
      const found = requests.find(r => r.id === highlightRequestId);
      if (found) {
        if (found.status === 'PENDING') {
          setFilterTab('PENDING');
        } else {
          setFilterTab('ALL');
        }
      }
    }
  }, [highlightRequestId, requests]);

  const handleOpenApprove = (req: PaymentRequest) => {
    setApproveTarget(req);
    setGrantedPagesInput(req.requested_pages);
    const amt = req.amount_paid ?? req.amount_inr ?? 0;
    setApproveNotesInput(`Approved payment of ₹${amt} via Google Pay / UPI.`);
  };

  const handleConfirmApprove = async () => {
    if (!approveTarget) return;
    setActionLoading(true);
    setErrorMsg('');
    try {
      await approvePaymentRequest(approveTarget.id, grantedPagesInput, approveNotesInput);
      setSuccessMsg(`Approved request #${approveTarget.id.substring(0, 8)}: granted ${grantedPagesInput} pages to ${approveTarget.user_email}.`);
      setApproveTarget(null);
      await loadRequests();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to approve request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenReject = (req: PaymentRequest) => {
    setRejectTarget(req);
    setRejectReasonInput('Payment screenshot invalid or transaction reference not found.');
  };

  const handleConfirmReject = async () => {
    if (!rejectTarget) return;
    setActionLoading(true);
    setErrorMsg('');
    try {
      await rejectPaymentRequest(rejectTarget.id, rejectReasonInput);
      setSuccessMsg(`Rejected request #${rejectTarget.id.substring(0, 8)}.`);
      setRejectTarget(null);
      await loadRequests();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to reject request.');
    } finally {
      setActionLoading(false);
    }
  };

  // Metrics
  const pendingCount = requests.filter(r => r.status === 'PENDING').length;
  const approvedCount = requests.filter(r => r.status === 'APPROVED').length;
  const rejectedCount = requests.filter(r => r.status === 'REJECTED').length;
  const totalPagesGranted = requests
    .filter(r => r.status === 'APPROVED')
    .reduce((sum, r) => sum + (r.granted_pages || r.requested_pages || 0), 0);
  const totalRevenue = requests
    .filter(r => r.status === 'APPROVED')
    .reduce((sum, r) => sum + (r.amount_paid ?? r.amount_inr ?? 0), 0);

  // Filtered
  const filtered = requests.filter(r => {
    if (filterTab !== 'ALL' && r.status !== filterTab) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const notes = r.notes || r.user_notes || '';
    return (
      r.id.toLowerCase().includes(q) ||
      (r.user_email && r.user_email.toLowerCase().includes(q)) ||
      (r.user_id && r.user_id.toLowerCase().includes(q)) ||
      notes.toLowerCase().includes(q)
    );
  });

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-amber-500 text-white flex items-center justify-center shadow-xs">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Page Purchase Requests
              </h1>
              <p className="text-xs text-slate-500">
                Verify manual Google Pay / UPI screenshots and credit conversion pages at ₹2/page.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="https://wa.me/919805987622"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
          >
            <MessageCircle className="w-4 h-4" />
            Support WhatsApp: +91 9805987622
          </a>
          <Button
            variant="outline"
            size="sm"
            onClick={loadRequests}
            loading={loading}
            icon={<RefreshCw className="w-4 h-4" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {successMsg && (
        <StatusAlert
          type="success"
          message={successMsg}
          onDismiss={() => setSuccessMsg('')}
        />
      )}
      {errorMsg && (
        <StatusAlert
          type="error"
          message={errorMsg}
          onDismiss={() => setErrorMsg('')}
        />
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <Card className="p-4 border-amber-200 bg-amber-50/30">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-amber-800 uppercase tracking-wider">Pending Review</span>
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-amber-900 font-mono">
            {pendingCount}
          </div>
        </Card>

        <Card className="p-4 border-emerald-200 bg-emerald-50/30">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider">Approved</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-emerald-900 font-mono">
            {approvedCount}
          </div>
        </Card>

        <Card className="p-4 border-rose-200 bg-rose-50/30">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-rose-800 uppercase tracking-wider">Rejected</span>
            <XCircle className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-rose-900 font-mono">
            {rejectedCount}
          </div>
        </Card>

        <Card className="p-4 border-blue-200 bg-brand-50/30">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-blue-800 uppercase tracking-wider">Pages Credited</span>
            <CreditCard className="w-4 h-4 text-brand-600" />
          </div>
          <div className="mt-2 text-2xl font-black text-blue-900 font-mono">
            {totalPagesGranted.toLocaleString()}
          </div>
        </Card>

        <Card className="p-4 border-slate-200 bg-white">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Total Revenue</span>
            <DollarSign className="w-4 h-4 text-slate-500" />
          </div>
          <div className="mt-2 text-2xl font-black text-slate-900 font-mono">
            ₹{totalRevenue.toFixed(2)}
          </div>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 scrollbar-hide">
          {(['ALL', 'PENDING', 'APPROVED', 'REJECTED'] as const).map((tab) => {
            const count = tab === 'ALL' ? requests.length : tab === 'PENDING' ? pendingCount : tab === 'APPROVED' ? approvedCount : rejectedCount;
            return (
              <button
                key={tab}
                onClick={() => setFilterTab(tab)}
                className={`relative flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap overflow-hidden ${
                  filterTab === tab
                    ? 'bg-navy-900 text-white shadow-md scale-100'
                    : 'bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-200 scale-95 hover:scale-100'
                }`}
              >
                {filterTab === tab && <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-shimmer" />}
                <span className="capitalize">{tab.toLowerCase()}</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${
                  filterTab === tab ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-700'
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        <div className="w-full sm:w-72 relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search email, UTR, ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
          />
        </div>
      </div>

      {/* Requests Table */}
      <Card className="shadow-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200/80 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Date / Request ID</th>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Pages</th>
                <th className="py-3 px-4">Amount (₹)</th>
                <th className="py-3 px-4">Payment Proof</th>
                <th className="py-3 px-4">UTR / Remarks</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400 font-semibold">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-brand-600" />
                    Loading page purchase requests...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400 font-semibold">
                    No payment requests found matching your filter.
                  </td>
                </tr>
              ) : (
                filtered.map((req) => {
                  const isHighlighted = req.id === highlightRequestId;
                  return (
                    <tr
                      key={req.id}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        isHighlighted ? 'bg-amber-50/50 border-l-4 border-amber-500' : ''
                      }`}
                    >
                      {/* Date / Request ID */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="font-semibold text-slate-900">
                          {new Date(req.created_at).toLocaleDateString('en-IN', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </div>
                        <div className="font-mono text-[10px] text-slate-400">
                          #{req.id.substring(0, 8)}
                        </div>
                      </td>

                      {/* User */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-slate-800 truncate max-w-[180px]">
                          {req.user_email || 'Anonymous / Test'}
                        </div>
                        <div className="font-mono text-[10px] text-slate-400 truncate max-w-[180px]">
                          {req.user_id}
                        </div>
                      </td>

                      {/* Pages */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="font-black text-slate-900 font-mono text-sm">
                          {req.status === 'APPROVED' && req.granted_pages ? req.granted_pages : req.requested_pages}
                        </div>
                        {req.status === 'APPROVED' && req.granted_pages && req.granted_pages !== req.requested_pages && (
                          <div className="text-[10px] text-slate-400 line-through">
                            Req: {req.requested_pages}
                          </div>
                        )}
                      </td>

                      {/* Amount */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className="font-bold font-mono text-slate-900">
                          ₹{(req.amount_paid ?? req.amount_inr ?? 0).toFixed(2)}
                        </span>
                      </td>

                      {/* Screenshot */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {req.screenshot_url ? (
                          <button
                            onClick={() => setViewingScreenshotUrl(req.screenshot_url!)}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-brand-50 hover:bg-blue-100 text-blue-700 font-bold text-[11px] border border-blue-200 transition-colors"
                          >
                            <FileImage className="w-3.5 h-3.5" />
                            View Proof
                          </button>
                        ) : (
                          <span className="text-slate-400 italic text-[11px]">No file</span>
                        )}
                      </td>

                      {/* Notes / UTR */}
                      <td className="py-3.5 px-4">
                        <div className="max-w-[200px] truncate text-slate-700" title={req.notes || req.user_notes || ''}>
                          {req.notes || req.user_notes || <span className="text-slate-400 italic">—</span>}
                        </div>
                        {req.admin_notes && (
                          <div className="text-[10px] text-slate-500 max-w-[200px] truncate" title={req.admin_notes}>
                            Admin: {req.admin_notes}
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {req.status === 'PENDING' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider bg-amber-50 text-amber-600 border border-amber-200/60 shadow-xs">
                            <Clock className="w-3 h-3" /> PENDING
                          </span>
                        )}
                        {req.status === 'APPROVED' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider bg-emerald-50 text-emerald-600 border border-emerald-200/60 shadow-xs">
                            <CheckCircle2 className="w-3 h-3" /> APPROVED
                          </span>
                        )}
                        {req.status === 'REJECTED' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider bg-rose-50 text-rose-600 border border-rose-200/60 shadow-xs">
                            <XCircle className="w-3 h-3" /> REJECTED
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        {req.status === 'PENDING' ? (
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => handleOpenApprove(req)}
                              icon={<Check className="w-3.5 h-3.5" />}
                              className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-7 px-2.5 text-xs"
                            >
                              Approve
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenReject(req)}
                              icon={<X className="w-3.5 h-3.5 text-rose-600" />}
                              className="border-rose-200 hover:bg-rose-50 text-rose-700 font-bold h-7 px-2.5 text-xs"
                            >
                              Reject
                            </Button>
                          </div>
                        ) : (
                          <span className="text-[11px] font-mono text-slate-400">
                            {req.reviewed_at
                              ? new Date(req.reviewed_at).toLocaleDateString('en-IN', {
                                  month: 'short',
                                  day: 'numeric'
                                })
                              : 'Done'}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Screenshot Viewer Modal */}
      <Modal
        isOpen={Boolean(viewingScreenshotUrl)}
        onClose={() => setViewingScreenshotUrl(null)}
        title="Payment Confirmation Screenshot Proof"
        description="Verify transaction timestamp, recipient UPI ID (9418250639@ybl), and paid amount."
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="bg-slate-900 rounded-2xl p-2 flex items-center justify-center max-h-[70vh] overflow-auto">
            {viewingScreenshotUrl && (
              <img
                src={viewingScreenshotUrl}
                alt="Payment proof"
                className="max-h-[65vh] w-auto object-contain rounded-xl"
              />
            )}
          </div>
          <div className="flex justify-end">
            <Button
              variant="outline"
              size="md"
              onClick={() => setViewingScreenshotUrl(null)}
            >
              Close Proof
            </Button>
          </div>
        </div>
      </Modal>

      {/* Approve Modal */}
      <Modal
        isOpen={Boolean(approveTarget)}
        onClose={() => setApproveTarget(null)}
        title="Approve Page Purchase & Credit Balance"
        description={`Approving request #${approveTarget?.id.substring(0, 8)} for ${approveTarget?.user_email}.`}
        maxWidth="md"
        className="max-h-[90vh] overflow-y-auto"
      >
        <div className="space-y-5 animate-slideUp">
          <div className="bg-gradient-to-br from-emerald-50 to-white p-5 rounded-2xl border border-emerald-100 shadow-sm space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-slate-500 font-semibold text-xs uppercase tracking-wider">Requested Pages</span>
              <strong className="text-navy-900 text-lg font-black">{approveTarget?.requested_pages}</strong>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500 font-semibold text-xs uppercase tracking-wider">Claimed Amount</span>
              <strong className="text-emerald-600 font-black font-mono text-xl">₹{((approveTarget?.amount_paid ?? approveTarget?.amount_inr ?? 0)).toFixed(2)}</strong>
            </div>
            <div className="flex flex-col gap-1 pt-2 border-t border-emerald-100/50">
              <span className="text-slate-400 font-semibold text-[10px] uppercase tracking-wider">User Remarks</span>
              <span className="text-slate-700 text-sm font-medium">{approveTarget?.notes || approveTarget?.user_notes || 'None'}</span>
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              Granted Pages to Credit <span className="text-rose-500">*</span>
            </label>
            <Input
              type="number"
              min="1"
              value={grantedPagesInput}
              onChange={(e) => setGrantedPagesInput(parseInt(e.target.value) || 0)}
              className="text-lg font-bold h-12"
            />
            <p className="text-[11px] text-slate-500 font-medium">
              Pages will be instantly credited to the user's permanent purchased balance.
            </p>
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              Admin Notes <span className="text-slate-400 font-normal">(Optional)</span>
            </label>
            <Input
              type="text"
              value={approveNotesInput}
              onChange={(e) => setApproveNotesInput(e.target.value)}
              placeholder="e.g. Verified via UPI transaction 4123..."
              className="h-11"
            />
          </div>

          <div className="flex gap-3 pt-4 border-t border-slate-100">
            <Button
              variant="outline"
              size="md"
              onClick={() => setApproveTarget(null)}
              className="w-1/3 hover:bg-slate-100"
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleConfirmApprove}
              loading={actionLoading}
              disabled={actionLoading || grantedPagesInput <= 0}
              className="w-2/3 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-bold shadow-glow-brand"
              icon={<Check className="w-5 h-5" />}
            >
              Confirm & Credit {grantedPagesInput} Pages
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reject Modal */}
      <Modal
        isOpen={Boolean(rejectTarget)}
        onClose={() => setRejectTarget(null)}
        title="Reject Page Purchase Request"
        description={`Rejecting request #${rejectTarget?.id.substring(0, 8)}.`}
        maxWidth="md"
        className="max-h-[90vh] overflow-y-auto"
      >
        <div className="space-y-5 animate-slideDown">
          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              Rejection Reason <span className="text-rose-500">*</span>
            </label>
            <Input
              type="text"
              value={rejectReasonInput}
              onChange={(e) => setRejectReasonInput(e.target.value)}
              placeholder="e.g. Amount not received in bank statement..."
              className="h-11 border-rose-200 focus:ring-rose-500/20 focus:border-rose-500"
              autoFocus
            />
            <p className="text-[11px] text-slate-500 font-medium">
              This reason will be visible to the user in their notification feed.
            </p>
          </div>

          <div className="flex gap-3 pt-4 border-t border-slate-100">
            <Button
              variant="outline"
              size="md"
              onClick={() => setRejectTarget(null)}
              className="w-1/3 hover:bg-slate-100"
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="md"
              onClick={handleConfirmReject}
              loading={actionLoading}
              disabled={actionLoading || !rejectReasonInput.trim()}
              className="w-2/3 font-bold shadow-glow-brand"
              icon={<X className="w-5 h-5" />}
            >
              Confirm Rejection
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
