'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Search, Sparkles, Check, X, ShieldAlert, UserCheck, Shield, Users, Eye, Ban, RotateCcw, FileSpreadsheet, Mail, KeyRound, AlertTriangle, Calendar } from 'lucide-react';
import { getAdminUsers, grantUserUnlimited, revokeUserUnlimited, getAdminUserDetails, toggleUserSuspension, updateUserAccountStatus, resetUserDailyUsage, updateUserQuota, apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // User Details Modal State
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [quotaMode, setQuotaMode] = useState<'GLOBAL' | 'CUSTOM'>('GLOBAL');
  const [customQuotaValue, setCustomQuotaValue] = useState<number>(50);
  const [savingQuota, setSavingQuota] = useState(false);

  // Suspend Account Modal State
  const [isSuspendModalOpen, setIsSuspendModalOpen] = useState(false);
  const [userToSuspend, setUserToSuspend] = useState<any>(null);
  const [suspendReasonInput, setSuspendReasonInput] = useState('Routine policy compliance review');
  const [suspendingUser, setSuspendingUser] = useState(false);

  const fetchUsers = () => {
    getAdminUsers(search)
      .then((data) => {
        setUsers(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchUsers();
  }, [search]);

  const handleGrant = async (userId: string) => {
    try {
      await grantUserUnlimited(userId);
      setActionMsg(`Unlimited conversion allowance granted to user.`);
      fetchUsers();
      if (selectedUser?.id === userId) {
        openUserDetails(userId);
      }
      setTimeout(() => setActionMsg(''), 3500);
    } catch {
      setErrorMsg('Failed to grant unlimited access');
      setTimeout(() => setErrorMsg(''), 3500);
    }
  };

  const handleRevoke = async (userId: string) => {
    try {
      await revokeUserUnlimited(userId);
      setActionMsg(`Unlimited conversion allowance revoked.`);
      fetchUsers();
      if (selectedUser?.id === userId) {
        openUserDetails(userId);
      }
      setTimeout(() => setActionMsg(''), 3500);
    } catch {
      setErrorMsg('Failed to revoke unlimited access');
      setTimeout(() => setErrorMsg(''), 3500);
    }
  };

  const handleOpenSuspendModal = (user: any) => {
    setUserToSuspend(user);
    setSuspendReasonInput('Routine policy compliance review');
    setIsSuspendModalOpen(true);
  };

  const handleConfirmSuspend = async () => {
    if (!userToSuspend) return;
    setSuspendingUser(true);
    try {
      const res = await updateUserAccountStatus(userToSuspend.id, 'SUSPENDED', suspendReasonInput.trim());
      setActionMsg(res.message || `Account for ${userToSuspend.email} has been suspended.`);
      setIsSuspendModalOpen(false);
      setUserToSuspend(null);
      fetchUsers();
      if (selectedUser?.id === userToSuspend.id) {
        openUserDetails(userToSuspend.id);
      }
      setTimeout(() => setActionMsg(''), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to suspend account.');
      setTimeout(() => setErrorMsg(''), 4000);
    } finally {
      setSuspendingUser(false);
    }
  };

  const handleRecoverUser = async (userId: string) => {
    try {
      const res = await updateUserAccountStatus(userId, 'ACTIVE');
      setActionMsg(res.message || 'Account recovered successfully and recovery email sent.');
      fetchUsers();
      if (selectedUser?.id === userId) {
        openUserDetails(userId);
      }
      setTimeout(() => setActionMsg(''), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to recover account.');
      setTimeout(() => setErrorMsg(''), 4000);
    }
  };

  const handleToggleSuspend = async (userId: string) => {
    try {
      const res = await toggleUserSuspension(userId);
      setActionMsg(res.message || 'Account status updated.');
      fetchUsers();
      if (selectedUser?.id === userId) {
        openUserDetails(userId);
      }
      setTimeout(() => setActionMsg(''), 3500);
    } catch {
      setErrorMsg('Failed to update suspension status.');
      setTimeout(() => setErrorMsg(''), 3500);
    }
  };

  const handleResetUsage = async (userId: string) => {
    try {
      const res = await resetUserDailyUsage(userId);
      setActionMsg(res.message || "Today's page usage reset to 0.");
      fetchUsers();
      if (selectedUser?.id === userId) {
        openUserDetails(userId);
      }
      setTimeout(() => setActionMsg(''), 3500);
    } catch {
      setErrorMsg('Failed to reset daily usage.');
      setTimeout(() => setErrorMsg(''), 3500);
    }
  };

  const openUserDetails = async (userId: string) => {
    setIsDetailsOpen(true);
    setDetailsLoading(true);
    try {
      const details = await getAdminUserDetails(userId);
      setSelectedUser(details);
      setQuotaMode(details.quota_mode === 'CUSTOM' ? 'CUSTOM' : 'GLOBAL');
      setCustomQuotaValue(details.custom_daily_limit || (typeof details.daily_limit === 'number' ? details.daily_limit : 50));
    } catch {
      setErrorMsg('Failed to load user details.');
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleSaveUserQuota = async () => {
    if (!selectedUser) return;
    setSavingQuota(true);
    try {
      const res = await updateUserQuota(selectedUser.id, {
        mode: quotaMode,
        custom_daily_limit: quotaMode === 'CUSTOM' ? Number(customQuotaValue) : undefined,
      });
      setActionMsg(res.message || 'User quota updated successfully.');
      fetchUsers();
      openUserDetails(selectedUser.id);
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update user quota.');
      setTimeout(() => setErrorMsg(''), 3500);
    } finally {
      setSavingQuota(false);
    }
  };

  const [resendingVerification, setResendingVerification] = useState(false);
  const handleResendVerification = async (userId: string) => {
    setResendingVerification(true);
    try {
      const res = await apiFetch<any>(`/admin/users/${userId}/resend-verification`, { method: 'POST' });
      setActionMsg(res.message || 'Verification email dispatched to user.');
      setTimeout(() => setActionMsg(''), 3500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to dispatch verification email.');
      setTimeout(() => setErrorMsg(''), 3500);
    } finally {
      setResendingVerification(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              User Access & Quotas Management
            </h1>
            <Badge variant="purple" size="sm">
              PRD Section 57
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Inspect user profiles, manage daily quotas, override conversion allowances, or suspend suspicious accounts
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search email, mobile, or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
          />
        </div>
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

      {/* Users Table Card */}
      <Card className="shadow-card overflow-hidden">
        {loading ? (
          <div className="p-20 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading registered users...
          </div>
        ) : users.length === 0 ? (
          <EmptyState
            icon={<Users className="w-6 h-6" />}
            title="No users found"
            description={search ? `No accounts matched "${search}".` : 'No registered users in the database yet.'}
          />
        ) : (
          <Table>
            <TableHeader>
              <tr>
                <TableHead>User Profile</TableHead>
                <TableHead>Contact Info</TableHead>
                <TableHead>Role & Status</TableHead>
                <TableHead align="center">Today's Pages</TableHead>
                <TableHead align="center">Daily Allowance</TableHead>
                <TableHead align="right">Administrative Actions</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {users.map((u) => {
                const isAdmin = u.role === 'ADMIN' || u.role === 'SUPER_ADMIN';
                const isSuspended = u.is_suspended;
                return (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="font-bold text-slate-900 flex items-center gap-2">
                        <span>{u.full_name || 'Registered User'}</span>
                        {isSuspended && (
                          <Badge variant="danger" size="sm">
                            Suspended
                          </Badge>
                        )}
                        {u.is_eligible_for_deletion && (
                          <Badge variant="danger" size="sm" className="bg-rose-100 text-rose-800 border-rose-300 font-extrabold">
                            Eligible for Deletion
                          </Badge>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        ID: {u.id}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="font-mono text-slate-700 text-xs font-semibold">
                        {u.email}
                      </div>
                      <div className="font-mono text-slate-400 text-[11px]">
                        {u.mobile_number || 'Mobile not set'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge
                          variant={isAdmin ? 'purple' : 'neutral'}
                          size="sm"
                        >
                          {u.role}
                        </Badge>
                        <Badge
                          variant={isSuspended ? 'danger' : 'success'}
                          size="sm"
                        >
                          {isSuspended ? 'Suspended' : 'Active'}
                        </Badge>
                        <Badge
                          variant={u.email_verified ? 'success' : 'warning'}
                          size="sm"
                        >
                          {u.email_verified ? 'Verified' : 'Unverified'}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell align="center">
                      <span className="font-mono font-bold text-slate-800 text-xs">
                        {u.today_usage || 0} pgs
                      </span>
                    </TableCell>
                    <TableCell align="center">
                      {isAdmin ? (
                        <span className="text-purple-700 font-bold text-xs">Admin Unlimited</span>
                      ) : u.is_unlimited ? (
                        <span className="text-emerald-700 font-bold text-xs flex items-center justify-center gap-1">
                          <Sparkles className="w-3.5 h-3.5 text-emerald-600" /> Unlimited
                        </span>
                      ) : u.quota_mode === 'CUSTOM' ? (
                        <span className="text-brand-700 font-bold text-xs flex items-center justify-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-brand-600" />
                          {u.daily_limit} Pgs / Day (Custom)
                        </span>
                      ) : (
                        <span className="text-slate-600 font-medium text-xs">
                          {u.daily_limit || 50} Pgs / Day
                        </span>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openUserDetails(u.id)}
                          icon={<Eye className="w-3.5 h-3.5 text-slate-600" />}
                        >
                          Inspect
                        </Button>

                        {!isAdmin && (
                          <>
                            {u.is_unlimited ? (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleRevoke(u.id)}
                              >
                                Revoke
                              </Button>
                            ) : (
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => handleGrant(u.id)}
                                icon={<Sparkles className="w-3 h-3 text-brand-600" />}
                              >
                                Unlimited
                              </Button>
                            )}

                            <Button
                              variant={isSuspended ? 'success' : 'outline'}
                              size="sm"
                              onClick={() => isSuspended ? handleRecoverUser(u.id) : handleOpenSuspendModal(u)}
                              title={isSuspended ? 'Recover Account' : 'Suspend Account'}
                              className={isSuspended ? 'text-emerald-700 border-emerald-300' : 'text-rose-600 border-rose-200'}
                            >
                              {isSuspended ? 'Recover' : 'Suspend'}
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>

      {/* User Details Modal (PRD Section 57) */}
      <Modal
        isOpen={isDetailsOpen}
        onClose={() => {
          setIsDetailsOpen(false);
          setSelectedUser(null);
        }}
        title="User Account & Quota Dossier"
        size="4xl"
      >
        {detailsLoading || !selectedUser ? (
          <div className="p-12 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading user profile & conversion history...
          </div>
        ) : (
          <div className="space-y-6">
            {/* Quick Profile Strip */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-col gap-3">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-extrabold text-base text-slate-900 truncate">{selectedUser.full_name || 'Registered User'}</h3>
                    {selectedUser.username && (
                      <span className="text-xs text-slate-500 font-mono">@{selectedUser.username}</span>
                    )}
                  </div>
                  <div className="text-xs text-slate-600 font-mono mt-0.5 break-all">{selectedUser.email}</div>
                  {selectedUser.mobile_number && (
                    <div className="text-xs text-slate-500 font-mono mt-0.5">Mobile: {selectedUser.mobile_number}</div>
                  )}
                  <div className="text-[11px] text-slate-400 font-mono mt-1">
                    Account ID: {selectedUser.id}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 flex-shrink-0">
                  <Badge variant={selectedUser.role === 'ADMIN' ? 'purple' : 'neutral'} size="sm">
                    {selectedUser.role}
                  </Badge>
                  <Badge variant={selectedUser.is_suspended ? 'danger' : 'success'} size="sm">
                    {selectedUser.is_suspended ? 'Suspended' : 'Active'}
                  </Badge>
                  {selectedUser.is_unlimited && (
                    <Badge variant="success" size="sm">
                      Unlimited Tier
                    </Badge>
                  )}
                  <Badge variant={selectedUser.email_verified ? 'success' : 'warning'} size="sm">
                    {selectedUser.email_verified ? 'Email Verified' : 'Email Unverified'}
                  </Badge>
                </div>
              </div>

              {/* Registration & Last Active Dates */}
              <div className="pt-2 border-t border-slate-200/80 flex flex-wrap items-center justify-between text-[11px] text-slate-500 font-mono">
                <div>
                  Registered: {selectedUser.registration_date ? new Date(selectedUser.registration_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A'}
                </div>
                <div>
                  Last Active: {selectedUser.last_login ? new Date(selectedUser.last_login).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'N/A'}
                </div>
              </div>
            </div>

            {/* Suspended Account Info Box */}
            {selectedUser.is_suspended && (
              <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-rose-800 font-bold text-xs">
                    <Ban className="w-4 h-4 text-rose-600" />
                    <span>Account Is Currently Suspended</span>
                  </div>
                  {selectedUser.is_eligible_for_deletion ? (
                    <Badge variant="danger" size="sm">
                      Eligible for Deletion (&gt; 90 Days)
                    </Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">
                      Suspended
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
                  <div>
                    <span className="text-[11px] font-semibold text-rose-900 uppercase">Suspension Reason:</span>
                    <p className="text-slate-800 bg-white/80 p-2 rounded-lg border border-rose-100 mt-1 font-medium">
                      {selectedUser.suspension_reason || 'No specific reason provided'}
                    </p>
                  </div>
                  <div className="space-y-1.5 bg-white/80 p-2 rounded-lg border border-rose-100">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Suspended On:</span>
                      <span className="font-mono font-semibold text-slate-800">
                        {selectedUser.suspended_at ? new Date(selectedUser.suspended_at).toLocaleDateString('en-IN') : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Scheduled Deletion:</span>
                      <span className="font-mono font-semibold text-rose-700">
                        {selectedUser.suspension_delete_at ? new Date(selectedUser.suspension_delete_at).toLocaleDateString('en-IN') : 'N/A'}
                      </span>
                    </div>
                    <div className="pt-1 border-t border-rose-100 flex justify-end">
                      <Link
                        href={`/admin/appeals?search=${encodeURIComponent(selectedUser.email)}`}
                        className="text-[11px] text-brand-700 hover:text-brand-900 font-semibold underline"
                      >
                        View User Appeals &rarr;
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Quota & Usage KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block">Today's Usage</span>
                <div className="text-base font-black font-mono text-slate-800 mt-0.5">
                  {selectedUser.today_usage || 0} pgs
                </div>
              </div>
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block">Remaining Today</span>
                <div className="text-base font-black font-mono text-emerald-700 mt-0.5">
                  {selectedUser.is_unlimited || selectedUser.role === 'ADMIN' ? 'Unlimited' : `${selectedUser.pages_remaining_today ?? 0} pgs`}
                </div>
              </div>
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block">Daily Allowance</span>
                <div className="text-base font-black font-mono text-brand-700 mt-0.5 truncate" title={String(selectedUser.daily_limit)}>
                  {selectedUser.daily_limit}
                </div>
              </div>
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block">Extra Pages</span>
                <div className="text-base font-black font-mono text-indigo-700 mt-0.5">
                  {selectedUser.additional_page_balance || 0} pgs
                </div>
              </div>
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block">Total Processed</span>
                <div className="text-base font-black font-mono text-slate-800 mt-0.5">
                  {selectedUser.total_pages_processed || 0} pgs
                </div>
              </div>
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
                <span className="text-[10px] text-slate-400 uppercase font-semibold block">Conversions</span>
                <div className="text-base font-black font-mono text-slate-800 mt-0.5">
                  {selectedUser.successful_conversions || 0}/{selectedUser.total_conversions || 0}
                </div>
              </div>
            </div>

            {/* Daily Free Page Quota Management (PRD Sections 20 & 21) */}
            <div className="p-4.5 bg-slate-50 rounded-2xl border border-slate-200 space-y-3.5">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                    Daily Free Page Quota Control
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Configure whether this user operates on the Global Free Daily Quota or an individual override
                  </p>
                </div>
                <Badge variant={quotaMode === 'CUSTOM' ? 'purple' : 'neutral'} size="sm">
                  {quotaMode === 'CUSTOM' ? 'Custom Quota Active' : 'Using Global Quota'}
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-700 block">Quota Selection Mode:</label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer select-none">
                      <input
                        type="radio"
                        name="quotaMode"
                        value="GLOBAL"
                        checked={quotaMode === 'GLOBAL'}
                        onChange={() => setQuotaMode('GLOBAL')}
                        className="text-brand-600 focus:ring-brand-500 w-3.5 h-3.5"
                      />
                      <span>Use Global Free Quota ({selectedUser.global_daily_limit || 50} pgs/day)</span>
                    </label>

                    <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer select-none">
                      <input
                        type="radio"
                        name="quotaMode"
                        value="CUSTOM"
                        checked={quotaMode === 'CUSTOM'}
                        onChange={() => setQuotaMode('CUSTOM')}
                        className="text-brand-600 focus:ring-brand-500 w-3.5 h-3.5"
                      />
                      <span>Custom Per-User Quota</span>
                    </label>
                  </div>
                </div>

                {quotaMode === 'CUSTOM' && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 block">
                      Custom Daily Pages Allowance:
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min={1}
                        max={100000}
                        value={customQuotaValue}
                        onChange={(e) => setCustomQuotaValue(Number(e.target.value))}
                        placeholder="e.g. 200"
                        className="w-32 px-3 py-1.5 bg-white border border-slate-300 rounded-xl text-xs font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                      />
                      <span className="text-xs text-slate-500 font-medium">Pages / Day</span>
                    </div>
                    <span className="text-[11px] text-slate-400 block">Overrides global quota for this specific user</span>
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-2 border-t border-slate-200/60">
                <Button
                  variant="primary"
                  size="sm"
                  loading={savingQuota}
                  onClick={handleSaveUserQuota}
                >
                  Save Quota Settings
                </Button>
              </div>
            </div>

            {/* Administrative Action Bar (PRD Full Responsiveness) */}
            <div className="p-4 bg-slate-100/80 rounded-2xl border border-slate-200 space-y-3">
              <span className="text-xs font-bold text-slate-800 block">User Support & Diagnostics:</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  loading={resendingVerification}
                  onClick={() => handleResendVerification(selectedUser.id)}
                  icon={<Mail className="w-3.5 h-3.5" />}
                  className="w-full justify-center text-xs"
                >
                  Resend Verification
                </Button>

                <Link
                  href={`/admin/recovery?email=${encodeURIComponent(selectedUser.email)}`}
                  className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-xl shadow-xs transition-colors w-full"
                >
                  <KeyRound className="w-3.5 h-3.5 text-slate-600" />
                  Account Recovery
                </Link>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleResetUsage(selectedUser.id)}
                  icon={<RotateCcw className="w-3.5 h-3.5" />}
                  className="w-full justify-center text-xs"
                >
                  Reset Today's Usage
                </Button>

                {selectedUser.is_unlimited ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRevoke(selectedUser.id)}
                    className="w-full justify-center text-xs"
                  >
                    Revoke Unlimited
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleGrant(selectedUser.id)}
                    icon={<Sparkles className="w-3.5 h-3.5 text-brand-600" />}
                    className="w-full justify-center text-xs"
                  >
                    Grant Unlimited
                  </Button>
                )}

                {selectedUser.is_suspended ? (
                  <Button
                    variant="success"
                    size="sm"
                    onClick={() => handleRecoverUser(selectedUser.id)}
                    icon={<Check className="w-3.5 h-3.5" />}
                    className="w-full justify-center text-emerald-700 border-emerald-300 text-xs"
                  >
                    Recover Account
                  </Button>
                ) : (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleOpenSuspendModal(selectedUser)}
                    icon={<Ban className="w-3.5 h-3.5" />}
                    className="w-full justify-center text-xs"
                  >
                    Suspend Account
                  </Button>
                )}
              </div>
            </div>

            {/* User's Statement Conversion History */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
                Recent Conversions ({selectedUser.conversions?.length || 0})
              </h4>
              {(!selectedUser.conversions || selectedUser.conversions.length === 0) ? (
                <div className="text-center py-8 text-xs text-slate-400 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                  No conversions recorded for this user yet.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200 max-h-60">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 font-bold uppercase text-[10px] border-b border-slate-200">
                      <tr>
                        <th className="p-2.5">Date</th>
                        <th className="p-2.5">Bank</th>
                        <th className="p-2.5">File Name</th>
                        <th className="p-2.5 text-center">Pages</th>
                        <th className="p-2.5 text-center">Txs</th>
                        <th className="p-2.5">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white text-[11px]">
                      {selectedUser.conversions.map((c: any) => {
                        const isPartial = Boolean(c.is_partial_conversion || (c.pages_skipped && c.pages_skipped > 0) || c.status === 'PARTIALLY_COMPLETED');
                        const totalPages = c.total_pdf_pages || c.page_count || 0;
                        const processedPages = c.pages_processed !== undefined ? c.pages_processed : totalPages;
                        return (
                          <tr key={c.id} className="hover:bg-slate-50">
                            <td className="p-2.5 font-mono text-slate-500 whitespace-nowrap">
                              {new Date(c.created_at).toLocaleDateString('en-IN', {
                                day: '2-digit',
                                month: 'short',
                                hour: '2-digit',
                                minute: '2-digit'
                              })}
                            </td>
                            <td className="p-2.5 font-semibold text-slate-800">{c.bank_name}</td>
                            <td className="p-2.5 font-mono truncate max-w-[160px] text-slate-600" title={c.file_name}>{c.file_name}</td>
                            <td className="p-2.5 text-center font-mono">
                              {isPartial ? (
                                <span className="inline-flex items-center gap-1 text-purple-700 font-bold">
                                  <span>{processedPages}/{totalPages}</span>
                                  <span className="text-[9px] px-1 py-0.2 bg-purple-100 rounded text-purple-800">Partial</span>
                                </span>
                              ) : (
                                <span className="font-semibold text-slate-800">{processedPages}</span>
                              )}
                            </td>
                            <td className="p-2.5 text-center font-mono font-bold text-slate-800">{c.transaction_count}</td>
                            <td className="p-2.5">
                              <Badge
                                variant={c.status === 'COMPLETED' ? 'success' : isPartial || c.status === 'PARTIALLY_COMPLETED' ? 'purple' : 'warning'}
                                size="sm"
                              >
                                {isPartial ? 'Partially Done' : c.status}
                              </Badge>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Suspend Confirmation Modal */}
      <Modal
        isOpen={isSuspendModalOpen}
        onClose={() => {
          setIsSuspendModalOpen(false);
          setUserToSuspend(null);
        }}
        title="Suspend User Account"
        size="md"
      >
        {userToSuspend && (
          <div className="space-y-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-800 leading-relaxed">
                Suspending this user will immediately invalidate active sessions, block further logins, schedule account deletion in 90 days, and dispatch an automated suspension email.
              </div>
            </div>

            <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs">
              <div className="text-slate-500">Target User:</div>
              <div className="font-bold text-slate-800 text-sm mt-0.5">{userToSuspend.full_name || 'User'}</div>
              <div className="font-mono text-slate-600">{userToSuspend.email}</div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 block">
                Reason for Suspension <span className="text-rose-500">*</span>
              </label>
              <textarea
                rows={3}
                value={suspendReasonInput}
                onChange={(e) => setSuspendReasonInput(e.target.value)}
                placeholder="Specify the policy violation or reason..."
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-600"
              />
              <span className="text-[11px] text-slate-400">
                This reason will be visible to the user on their suspended portal and in their notification email.
              </span>
            </div>

            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-200">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setIsSuspendModalOpen(false);
                  setUserToSuspend(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                loading={suspendingUser}
                disabled={!suspendReasonInput.trim()}
                onClick={handleConfirmSuspend}
                icon={<Ban className="w-3.5 h-3.5" />}
              >
                Confirm Suspension
              </Button>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
}
