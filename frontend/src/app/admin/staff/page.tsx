'use client';

import React, { useState, useEffect } from 'react';
import {
  Users,
  ShieldCheck,
  Sparkles,
  Search,
  Plus,
  Trash2,
  Calendar,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
  ShieldAlert,
  CreditCard,
  Check,
  X,
  ExternalLink,
  Smartphone
} from 'lucide-react';
import {
  getStaffList,
  addStaffMember,
  removeStaffMember,
  toggleGoldTick,
  extendStaffExpiry,
  getStaffAuditLogs,
  getSuspiciousActivity,
  whitelistDevice,
  getAdminSubscriptions,
  approveSubscription,
  rejectSubscription,
  StaffUserItem,
  StaffAuditLogItem,
  SuspiciousActivityItem,
  UserSubscriptionItem
} from '@/lib/api';
import { GoldTick } from '@/components/ui/GoldTick';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { KangraLoader } from '@/components/ui/KangraLoader';

export default function AdminStaffManagementPage() {
  const [activeTab, setActiveTab] = useState<'staff' | 'subscriptions' | 'audit' | 'anti_abuse'>('staff');
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Data states
  const [staffList, setStaffList] = useState<StaffUserItem[]>([]);
  const [subscriptions, setSubscriptions] = useState<UserSubscriptionItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<StaffAuditLogItem[]>([]);
  const [suspiciousSignals, setSuspiciousSignals] = useState<SuspiciousActivityItem[]>([]);

  // Feedback states
  const [actionMsg, setActionMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newIsGold, setNewIsGold] = useState(false);
  const [newExpiryDays, setNewExpiryDays] = useState<number>(30);
  const [isSubmittingAdd, setIsSubmittingAdd] = useState(false);

  // Extend Expiry Modal
  const [selectedStaffUser, setSelectedStaffUser] = useState<StaffUserItem | null>(null);
  const [isExtendModalOpen, setIsExtendModalOpen] = useState(false);
  const [extendDays, setExtendDays] = useState(30);

  const loadData = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      if (activeTab === 'staff') {
        const res = await getStaffList();
        setStaffList(res.staff || []);
      } else if (activeTab === 'subscriptions') {
        const res = await getAdminSubscriptions();
        setSubscriptions(res.subscriptions || []);
      } else if (activeTab === 'audit') {
        const res = await getStaffAuditLogs();
        setAuditLogs(res.logs || []);
      } else if (activeTab === 'anti_abuse') {
        const res = await getSuspiciousActivity();
        setSuspiciousSignals(res.signals || []);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const showNotification = (msg: string) => {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(''), 4000);
  };

  // Staff Actions
  const handleAddStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserEmail.trim()) return;
    setIsSubmittingAdd(true);
    try {
      const res = await addStaffMember({
        user_id_or_email: newUserEmail.trim(),
        is_gold: newIsGold,
        expiry_days: newExpiryDays > 0 ? newExpiryDays : undefined,
      });
      showNotification(res.message);
      setIsAddModalOpen(false);
      setNewUserEmail('');
      setNewIsGold(false);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error adding staff user.');
    } finally {
      setIsSubmittingAdd(false);
    }
  };

  const handleRemoveStaff = async (userIdOrEmail: string) => {
    if (!confirm(`Are you sure you want to remove ${userIdOrEmail} from the Staff group? They will revert to the standard 5-bill daily limit immediately.`)) {
      return;
    }
    try {
      const res = await removeStaffMember({ user_id_or_email: userIdOrEmail });
      showNotification(res.message);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error removing staff user.');
    }
  };

  const handleToggleGold = async (userId: string, currentGold: boolean) => {
    try {
      const res = await toggleGoldTick({ user_id: userId, is_gold: !currentGold });
      showNotification(res.message);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error updating Gold Tick.');
    }
  };

  const handleExtendExpiry = async () => {
    if (!selectedStaffUser) return;
    try {
      const res = await extendStaffExpiry({ user_id: selectedStaffUser.id, days: extendDays });
      showNotification(res.message);
      setIsExtendModalOpen(false);
      setSelectedStaffUser(null);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error extending expiry.');
    }
  };

  // Subscription Actions
  const handleApproveSub = async (subId: string) => {
    try {
      const res = await approveSubscription({ subscription_id: subId });
      showNotification(res.message);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error approving subscription.');
    }
  };

  const handleRejectSub = async (subId: string) => {
    const reason = prompt('Please enter rejection reason:');
    if (!reason) return;
    try {
      const res = await rejectSubscription({ subscription_id: subId, admin_notes: reason });
      showNotification(res.message);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error rejecting subscription.');
    }
  };

  // Device Whitelist Action
  const handleWhitelistToggle = async (deviceId: string, currentStatus: boolean) => {
    try {
      const res = await whitelistDevice({ device_id: deviceId, is_whitelisted: !currentStatus });
      showNotification(res.message);
      loadData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error toggling device whitelist.');
    }
  };

  const filteredStaff = staffList.filter((s) =>
    (s.email || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (s.full_name || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 font-sans">
      {/* Page Title & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">Staff & Verified Tier</h1>
            <GoldTick size="md" />
          </div>
          <p className="text-xs text-slate-500">
            PRD Specification: Manage Staff users with unlimited conversions, Gold Verified Ticks, manual subscriptions, and anti-abuse safeguards.
          </p>
        </div>

        {activeTab === 'staff' && (
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" />
            Add Staff User
          </button>
        )}
      </div>

      {/* Notifications */}
      {actionMsg && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          {actionMsg}
        </div>
      )}
      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs font-semibold text-rose-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600" />
          {errorMsg}
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2 overflow-x-auto">
        {[
          { key: 'staff', label: 'Staff Members', icon: Users, badge: staffList.length },
          { key: 'subscriptions', label: 'Paid Subscriptions', icon: CreditCard, badge: subscriptions.filter(s => s.status === 'PENDING').length },
          { key: 'audit', label: 'Staff Audit Logs', icon: History },
          { key: 'anti_abuse', label: 'Anti-Abuse Monitor', icon: ShieldAlert, badge: suspiciousSignals.length },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                isActive
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              {tab.badge !== undefined && tab.badge > 0 && (
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-extrabold ${
                  isActive ? 'bg-amber-400 text-slate-950' : 'bg-slate-200 text-slate-700'
                }`}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Staff Members List */}
      {activeTab === 'staff' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search staff by email or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <span className="text-xs text-slate-500 font-medium">
              Showing {filteredStaff.length} of {staffList.length} staff users
            </span>
          </div>

          {loading ? (
            <div className="p-12 flex justify-center">
              <KangraLoader message="Loading Staff Group members..." />
            </div>
          ) : filteredStaff.length === 0 ? (
            <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 text-slate-500 text-xs">
              No staff members found matching query. Click "Add Staff User" to add one.
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold">
                  <tr>
                    <th className="p-4">User</th>
                    <th className="p-4">Source</th>
                    <th className="p-4">Gold Tick</th>
                    <th className="p-4">Expiry / Grace</th>
                    <th className="p-4">Conversions</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {filteredStaff.map((staff) => (
                    <tr key={staff.id} className="hover:bg-slate-50/70">
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <span className="w-7 h-7 rounded-full bg-amber-100 text-amber-800 flex items-center justify-center font-bold text-xs">
                            {staff.full_name?.charAt(0) || staff.email?.charAt(0)}
                          </span>
                          <div>
                            <div className="font-bold text-slate-900 flex items-center gap-1.5">
                              {staff.full_name || 'Kangra Hub User'}
                              {staff.is_gold && <GoldTick size="sm" />}
                            </div>
                            <span className="text-slate-500 text-[11px] font-mono">{staff.email}</span>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          staff.staff_source === 'SUBSCRIPTION'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-indigo-100 text-indigo-800'
                        }`}>
                          {staff.staff_source === 'SUBSCRIPTION' ? 'Paid Subscription' : 'Admin Granted'}
                        </span>
                      </td>
                      <td className="p-4">
                        <button
                          onClick={() => handleToggleGold(staff.id, staff.is_gold)}
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition-colors ${
                            staff.is_gold
                              ? 'bg-amber-100 text-amber-900 border border-amber-300'
                              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                          }`}
                        >
                          <GoldTick size="sm" showTooltip={false} />
                          {staff.is_gold ? 'Verified' : 'Grant Gold'}
                        </button>
                      </td>
                      <td className="p-4">
                        {staff.subscription_expiry ? (
                          <div className="space-y-0.5">
                            <span className="text-[11px] font-mono font-bold text-slate-800 block">
                              {staff.subscription_expiry.slice(0, 10)}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              +3-day grace period
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-emerald-600 font-bold">Unlimited / Permanent</span>
                        )}
                      </td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[11px] font-extrabold border border-emerald-200">
                          Unlimited (0/day limit)
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => {
                              setSelectedStaffUser(staff);
                              setIsExtendModalOpen(true);
                            }}
                            className="px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700"
                            title="Extend Expiry"
                          >
                            Extend
                          </button>
                          <button
                            onClick={() => handleRemoveStaff(staff.id)}
                            className="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50 hover:text-rose-700"
                            title="Remove from Staff"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Subscriptions Approval */}
      {activeTab === 'subscriptions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-800">
              Subscription Orders via UPI ({subscriptions.length})
            </h2>
            <span className="text-xs text-slate-500">
              UPI Destination: <strong>Kangrahub@pnb</strong>
            </span>
          </div>

          {loading ? (
            <div className="p-12 flex justify-center">
              <KangraLoader message="Loading subscription records..." />
            </div>
          ) : subscriptions.length === 0 ? (
            <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 text-slate-500 text-xs">
              No subscription payment submissions found.
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold">
                  <tr>
                    <th className="p-4">User</th>
                    <th className="p-4">UTR / Reference</th>
                    <th className="p-4">Amount</th>
                    <th className="p-4">Date</th>
                    <th className="p-4">Status</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {subscriptions.map((sub) => (
                    <tr key={sub.id} className="hover:bg-slate-50/70">
                      <td className="p-4">
                        <div className="font-bold text-slate-900">{sub.user_email}</div>
                        <span className="text-[11px] text-slate-500 font-mono">{sub.id}</span>
                      </td>
                      <td className="p-4 font-mono font-bold text-slate-800 select-all">
                        {sub.txn_id || 'N/A'}
                      </td>
                      <td className="p-4 font-black text-slate-900">
                        ₹{sub.amount}
                      </td>
                      <td className="p-4 text-[11px] text-slate-500">
                        {sub.created_at?.slice(0, 16).replace('T', ' ')}
                      </td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          sub.status === 'ACTIVE'
                            ? 'bg-emerald-100 text-emerald-800'
                            : sub.status === 'PENDING'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}>
                          {sub.status}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        {sub.status === 'PENDING' ? (
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleApproveSub(sub.id)}
                              className="px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleRejectSub(sub.id)}
                              className="px-3 py-1 rounded-lg bg-rose-100 hover:bg-rose-200 text-rose-700 font-bold text-xs"
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-[11px] text-slate-400">Processed</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Staff Audit Logs */}
      {activeTab === 'audit' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-800">Staff Group Administrative History</h2>
            <span className="text-xs text-slate-500">Permanently audited on server</span>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold">
                <tr>
                  <th className="p-4">Timestamp</th>
                  <th className="p-4">Admin</th>
                  <th className="p-4">Action</th>
                  <th className="p-4">Target User</th>
                  <th className="p-4">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70">
                    <td className="p-4 font-mono text-[11px] text-slate-500">
                      {log.created_at?.slice(0, 16).replace('T', ' ')}
                    </td>
                    <td className="p-4 font-bold text-slate-900">{log.admin_name}</td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 text-slate-800">
                        {log.action}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-[11px] text-slate-700">{log.target_user_email}</td>
                    <td className="p-4 text-slate-600">{log.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Anti-Abuse Monitor */}
      {activeTab === 'anti_abuse' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-800">Anti-Abuse & Device Pool Signals</h2>
              <p className="text-xs text-slate-500">
                Monitors shared device fingerprints, multi-account daily pools, and cross-account identical bills.
              </p>
            </div>
          </div>

          {suspiciousSignals.length === 0 ? (
            <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 text-emerald-600 text-xs font-bold">
              No suspicious abuse patterns detected. All device pools within normal limits.
            </div>
          ) : (
            <div className="space-y-3">
              {suspiciousSignals.map((sig, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs flex items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                        sig.severity === 'ALERT'
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}>
                        {sig.type}
                      </span>
                      <span className="text-[11px] font-mono text-slate-400">{sig.timestamp}</span>
                    </div>
                    <p className="text-xs font-semibold text-slate-800">{sig.details}</p>
                  </div>

                  {sig.device_id && (
                    <button
                      onClick={() => handleWhitelistToggle(sig.device_id!, false)}
                      className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold whitespace-nowrap"
                    >
                      Whitelist Device
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add Staff Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Add User to Staff Group"
      >
        <form onSubmit={handleAddStaff} className="space-y-4 text-xs font-sans">
          <div>
            <label className="block font-bold text-slate-700 mb-1">
              User Email or User ID <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. user@example.com"
              value={newUserEmail}
              onChange={(e) => setNewUserEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200">
            <input
              type="checkbox"
              id="goldTickCheckbox"
              checked={newIsGold}
              onChange={(e) => setNewIsGold(e.target.checked)}
              className="w-4 h-4 rounded text-brand-600 focus:ring-brand-500"
            />
            <label htmlFor="goldTickCheckbox" className="font-bold text-slate-800 cursor-pointer flex items-center gap-1.5">
              Grant Kangra Hub Gold Tick
              <GoldTick size="sm" showTooltip={false} />
            </label>
          </div>

          <div>
            <label className="block font-bold text-slate-700 mb-1">
              Subscription Validity (Days)
            </label>
            <input
              type="number"
              min="0"
              value={newExpiryDays}
              onChange={(e) => setNewExpiryDays(parseInt(e.target.value) || 0)}
              className="w-full px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <span className="text-[11px] text-slate-400 mt-0.5 block">
              Enter 0 for permanent / unlimited access. Defaults to 30 days.
            </span>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              className="px-4 py-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmittingAdd}
              className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold disabled:opacity-50"
            >
              {isSubmittingAdd ? 'Adding...' : 'Add to Staff Group'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Extend Expiry Modal */}
      <Modal
        isOpen={isExtendModalOpen}
        onClose={() => setIsExtendModalOpen(false)}
        title={`Extend Subscription: ${selectedStaffUser?.email || ''}`}
      >
        <div className="space-y-4 text-xs font-sans">
          <p className="text-slate-600">
            Current Expiry: <strong>{selectedStaffUser?.subscription_expiry?.slice(0, 10) || 'Unlimited'}</strong>
          </p>

          <div>
            <label className="block font-bold text-slate-700 mb-1">
              Extend by Days
            </label>
            <input
              type="number"
              min="1"
              value={extendDays}
              onChange={(e) => setExtendDays(parseInt(e.target.value) || 30)}
              className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setIsExtendModalOpen(false)}
              className="px-4 py-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-bold"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleExtendExpiry}
              className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold"
            >
              Confirm Extension
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
