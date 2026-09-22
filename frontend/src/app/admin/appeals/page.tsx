'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { 
  ShieldAlert, 
  Search, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  User, 
  Mail, 
  Calendar, 
  AlertTriangle, 
  Eye, 
  RotateCcw, 
  MessageSquare,
  Sparkles,
  ArrowRight,
  Filter
} from 'lucide-react';
import { 
  getAdminAppeals, 
  getAdminAppealDetails, 
  adminRecoverAppeal, 
  adminRejectAppeal 
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';

function AdminAppealsContent() {
  const searchParams = useSearchParams();
  const urlSearch = searchParams.get('search') || '';
  const urlId = searchParams.get('id') || '';

  const [appeals, setAppeals] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [search, setSearch] = useState(urlSearch);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Appeal Detail & Review Modal State
  const [selectedAppeal, setSelectedAppeal] = useState<any>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isRecoverConfirmOpen, setIsRecoverConfirmOpen] = useState(false);
  const [isRejectConfirmOpen, setIsRejectConfirmOpen] = useState(false);
  const [adminResponseText, setAdminResponseText] = useState('');
  const [processingAction, setProcessingAction] = useState(false);

  const fetchAppeals = () => {
    getAdminAppeals(statusFilter, search)
      .then((data) => {
        setAppeals(data);
        setLoading(false);
        if (urlId && Array.isArray(data)) {
          const matched = data.find((a: any) => a.id === urlId);
          if (matched) {
            openAppealDetail(matched);
          }
        }
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchAppeals();
  }, [statusFilter, search]);

  const openAppealDetail = async (appeal: any) => {
    setSelectedAppeal(appeal);
    setIsDetailOpen(true);
    try {
      const fresh = await getAdminAppealDetails(appeal.id);
      setSelectedAppeal(fresh);
    } catch {
      // keep initial
    }
  };

  const handleRecover = async () => {
    if (!selectedAppeal) return;
    setProcessingAction(true);
    try {
      const res = await adminRecoverAppeal(selectedAppeal.id);
      setActionMsg(res.message || 'Account has been successfully recovered.');
      setIsRecoverConfirmOpen(false);
      setIsDetailOpen(false);
      fetchAppeals();
      setTimeout(() => setActionMsg(''), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to recover account.');
      setTimeout(() => setErrorMsg(''), 4000);
    } finally {
      setProcessingAction(false);
    }
  };

  const handleReject = async () => {
    if (!selectedAppeal) return;
    setProcessingAction(true);
    try {
      const res = await adminRejectAppeal(
        selectedAppeal.id,
        adminResponseText.trim() || undefined,
        adminResponseText.trim() || undefined
      );
      setActionMsg(res.message || 'Appeal marked as rejected. Decision email dispatched.');
      setIsRejectConfirmOpen(false);
      setIsDetailOpen(false);
      setAdminResponseText('');
      fetchAppeals();
      setTimeout(() => setActionMsg(''), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to reject appeal.');
      setTimeout(() => setErrorMsg(''), 4000);
    } finally {
      setProcessingAction(false);
    }
  };

  const formatDisplayDate = (dStr?: string) => {
    if (!dStr) return '—';
    try {
      const d = new Date(dStr);
      if (isNaN(d.getTime())) return dStr;
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      });
    } catch {
      return dStr;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Suspended Account Appeals
            </h1>
            <Badge variant="danger" size="sm">
              PRD Section 11
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Review user suspension appeals, inspect policy compliance, recover legitimate accounts, or reject appeals
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search email, name, or appeal ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {['ALL', 'PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED'].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              statusFilter === st
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {st === 'ALL' ? 'All Appeals' : st.replace('_', ' ')}
          </button>
        ))}
      </div>

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

      {/* Appeals Table */}
      <Card className="shadow-card overflow-hidden">
        {loading ? (
          <div className="p-20 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading appeals...
          </div>
        ) : appeals.length === 0 ? (
          <EmptyState
            icon={<ShieldAlert className="w-6 h-6" />}
            title="No appeals found"
            description={search ? `No appeals match "${search}".` : 'There are no account appeals in this view.'}
          />
        ) : (
          <div className="overflow-x-auto">\n<Table>
            <TableHeader>
              <tr>
                <TableHead>User Profile</TableHead>
                <TableHead>Appeal Subject & Reason</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Suspension Date</TableHead>
                <TableHead>Scheduled Deletion</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {appeals.map((a) => (
                <TableRow key={a.id} className="hover:bg-slate-50/80">
                  <TableCell>
                    <div className="space-y-0.5">
                      <div className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5 text-slate-400" />
                        {a.user_name || 'User'}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {a.user_email}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        ID: {String(a.user_id).slice(0, 12)}...
                      </div>
                    </div>
                  </TableCell>

                  <TableCell className="max-w-xs">
                    <div className="space-y-1">
                      <div className="text-xs font-semibold text-slate-800 line-clamp-1">
                        {a.subject || 'Account Review Request'}
                      </div>
                      <div className="text-[11px] text-slate-500 line-clamp-2 italic">
                        &quot;{a.message}&quot;
                      </div>
                    </div>
                  </TableCell>

                  <TableCell>
                    {a.status === 'approved' ? (
                      <Badge variant="success" size="sm">Approved</Badge>
                    ) : a.status === 'rejected' ? (
                      <Badge variant="danger" size="sm">Rejected</Badge>
                    ) : a.status === 'under_review' ? (
                      <Badge variant="purple" size="sm">Under Review</Badge>
                    ) : (
                      <Badge variant="warning" size="sm">Pending</Badge>
                    )}
                  </TableCell>

                  <TableCell className="text-xs text-slate-600">
                    {formatDisplayDate(a.suspension_date || a.created_at)}
                  </TableCell>

                  <TableCell>
                    <div className="space-y-1">
                      <div className="text-xs font-semibold text-slate-700">
                        {formatDisplayDate(a.scheduled_deletion_date)}
                      </div>
                      {a.is_eligible_for_deletion && (
                        <span className="inline-block text-[10px] font-extrabold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                          Eligible for Deletion
                        </span>
                      )}
                    </div>
                  </TableCell>

                  <TableCell className="text-xs text-slate-500">
                    {formatDisplayDate(a.created_at)}
                  </TableCell>

                  <TableCell className="text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openAppealDetail(a)}
                      className="text-xs"
                    >
                      <Eye className="w-3.5 h-3.5 mr-1" />
                      Review
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>\n</div>
        )}
      </Card>

      {/* Appeal Detail & Decision Modal (PRD Section 12, 13, 15) */}
      <Modal
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        title="Account Appeal Dossier & Decision"
        size="4xl"
      >
        {selectedAppeal && (
          <div className="space-y-5">
            
            {/* Header / Dossier Overview */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <div className="space-y-1 min-w-0">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Applicant</span>
                <div className="text-sm font-bold text-slate-900 truncate">{selectedAppeal.user_name}</div>
                <div className="text-xs text-slate-600 font-mono break-all">{selectedAppeal.user_email}</div>
                <div className="text-[11px] text-slate-400 font-mono break-all">ID: {selectedAppeal.user_id}</div>
              </div>

              <div className="space-y-1.5">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Account State</span>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={selectedAppeal.status === 'approved' ? 'success' : selectedAppeal.status === 'rejected' ? 'danger' : 'warning'} size="sm">
                    Appeal: {selectedAppeal.status.toUpperCase()}
                  </Badge>
                  {selectedAppeal.is_eligible_for_deletion && (
                    <Badge variant="danger" size="sm">Eligible for Deletion</Badge>
                  )}
                </div>
                <div className="text-[11px] text-slate-500">
                  Suspension Date: {formatDisplayDate(selectedAppeal.suspension_date)}
                </div>
                <div className="text-[11px] text-slate-500">
                  Scheduled Deletion: {formatDisplayDate(selectedAppeal.scheduled_deletion_date)}
                </div>
              </div>
            </div>

            {/* Suspension Reason if recorded */}
            {selectedAppeal.suspension_reason && (
              <div className="bg-amber-50 border border-amber-200 p-3.5 rounded-xl text-xs space-y-1">
                <span className="font-bold text-amber-950 block">Initial Suspension Reason:</span>
                <span className="text-amber-900 block break-words">{selectedAppeal.suspension_reason}</span>
              </div>
            )}

            {/* Appeal User Statement */}
            <div className="space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <span className="text-xs font-bold text-slate-700">Appeal Submission: {selectedAppeal.subject}</span>
                <span className="text-[11px] text-slate-400">
                  {new Date(selectedAppeal.created_at).toLocaleString()}
                </span>
              </div>
              <div className="bg-white border border-slate-200 p-4 rounded-xl text-xs text-slate-700 leading-relaxed whitespace-pre-wrap break-words">
                {selectedAppeal.message}
              </div>
            </div>

            {/* Previous Administrator Response if present */}
            {selectedAppeal.admin_response && (
              <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-xl text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-800">Administrator Response:</span>
                  <span className="text-[10px] text-slate-400">By {selectedAppeal.reviewed_by || 'Admin'}</span>
                </div>
                <span className="text-slate-600 block break-words">{selectedAppeal.admin_response}</span>
              </div>
            )}

            {/* Action Buttons */}
            <div className="pt-3 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2.5 sm:gap-3 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDetailOpen(false)}
                className="w-full sm:w-auto justify-center"
              >
                Close
              </Button>

              {selectedAppeal.status !== 'rejected' && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full sm:w-auto justify-center text-rose-600 border-rose-200 hover:bg-rose-50"
                  onClick={() => {
                    setAdminResponseText(selectedAppeal.admin_response || '');
                    setIsRejectConfirmOpen(true);
                  }}
                >
                  <XCircle className="w-3.5 h-3.5 mr-1 text-rose-600" />
                  Keep Suspended
                </Button>
              )}

              {selectedAppeal.status !== 'approved' && (
                <Button
                  variant="primary"
                  size="sm"
                  className="w-full sm:w-auto justify-center bg-emerald-600 hover:bg-emerald-700 text-white"
                  onClick={() => setIsRecoverConfirmOpen(true)}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                  Recover Account
                </Button>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Recover Confirmation Modal (PRD Section 13) */}
      <Modal
        isOpen={isRecoverConfirmOpen}
        onClose={() => setIsRecoverConfirmOpen(false)}
        title="Confirm Account Recovery"
        size="md"
      >
        <div className="space-y-4">
          <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div className="text-center space-y-1.5">
            <h3 className="text-base font-black text-slate-900">
              Are you sure you want to recover this account?
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              This will set the account status to <strong>ACTIVE</strong>, clear suspension flags and scheduled deletion dates, and automatically send an account recovery notification email to <strong>{selectedAppeal?.user_email}</strong>.
            </p>
          </div>

          <div className="pt-3 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2.5 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsRecoverConfirmOpen(false)}
              disabled={processingAction}
              className="w-full sm:w-auto justify-center"
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="w-full sm:w-auto justify-center bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
              onClick={handleRecover}
              disabled={processingAction}
            >
              {processingAction ? 'Recovering...' : 'Yes, Recover Account'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reject Confirmation & Note Modal (PRD Section 15) */}
      <Modal
        isOpen={isRejectConfirmOpen}
        onClose={() => setIsRejectConfirmOpen(false)}
        title="Keep Account Suspended"
        size="md"
      >
        <div className="space-y-4">
          <div className="w-12 h-12 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div className="text-center space-y-1.5">
            <h3 className="text-base font-black text-slate-900">
              Are you sure you want to keep this account suspended?
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              The user&apos;s account will remain suspended and scheduled deletion dates will be retained. A formal decision email will be dispatched to the user.
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-700">Administrator Review Response / Reason</label>
            <textarea
              rows={3}
              value={adminResponseText}
              onChange={(e) => setAdminResponseText(e.target.value)}
              placeholder="Explain why the account remains suspended (included in user email notification)..."
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600 placeholder:text-slate-400 resize-none"
            />
          </div>

          <div className="pt-3 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2.5 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsRejectConfirmOpen(false)}
              disabled={processingAction}
              className="w-full sm:w-auto justify-center"
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="w-full sm:w-auto justify-center bg-rose-600 hover:bg-rose-700 text-white font-bold"
              onClick={handleReject}
              disabled={processingAction}
            >
              {processingAction ? 'Processing...' : 'Confirm Keep Suspended'}
            </Button>
          </div>
        </div>
      </Modal>

    </div>
  );
}

export default function AdminAppealsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-400">Loading account appeals console...</div>}>
      <AdminAppealsContent />
    </Suspense>
  );
}
