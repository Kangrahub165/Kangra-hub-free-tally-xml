'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import { 
  Bell, 
  AlertTriangle, 
  CheckCircle2, 
  Save, 
  Mail, 
  ShieldAlert, 
  FileCheck, 
  KeyRound, 
  CheckCheck, 
  Trash2, 
  ExternalLink,
  Search,
  RefreshCw,
  Clock,
  Inbox,
  Megaphone,
  User,
  Copy,
  Building,
  FileText,
  Check
} from 'lucide-react';
import { 
  getAdminNotifications, 
  updateAdminNotifications,
  getAdminUnreadCounts,
  getAdminNotificationsFeed,
  markAdminNotificationsRead,
  getAdminContactMessages,
  deleteAdminContactMessage,
  UnreadNotificationCounts,
  NotificationFeedItem
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';

function AdminNotificationsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') === 'contact' ? 'inbox' : 'inbox';

  const [activeView, setActiveView] = useState<'inbox' | 'broadcast'>(initialTab);
  const [categoryFilter, setCategoryFilter] = useState<'ALL' | 'CONTACT' | 'APPEAL' | 'REVIEW' | 'RECOVERY'>('ALL');
  const [search, setSearch] = useState('');

  // Selected contact message modal state
  const [selectedMessage, setSelectedMessage] = useState<any | null>(null);
  const [isMessageModalOpen, setIsMessageModalOpen] = useState(false);
  const [copiedEmail, setCopiedEmail] = useState(false);

  // Broadcast banners state
  const [broadcastData, setBroadcastData] = useState<any>({
    announcement_enabled: false,
    announcement_message: '',
    announcement_type: 'info',
    maintenance_banner: false,
    maintenance_message: ''
  });
  const [savingBroadcast, setSavingBroadcast] = useState(false);
  const [broadcastMsg, setBroadcastMsg] = useState('');

  // Inbox & feed state
  const [counts, setCounts] = useState<UnreadNotificationCounts>({
    total_unread: 0,
    categories: {
      contact_messages: 0,
      account_appeals: 0,
      conversion_reviews: 0,
      support_requests: 0
    }
  });
  const [feed, setFeed] = useState<NotificationFeedItem[]>([]);
  const [contactMessages, setContactMessages] = useState<any[]>([]);
  const [loadingInbox, setLoadingInbox] = useState(true);

  const loadInboxData = async () => {
    setLoadingInbox(true);
    try {
      const [cRes, fRes, mRes] = await Promise.all([
        getAdminUnreadCounts(),
        getAdminNotificationsFeed(),
        getAdminContactMessages()
      ]);
      if (cRes) setCounts(cRes);
      if (fRes && Array.isArray(fRes.items)) setFeed(fRes.items);
      if (mRes && Array.isArray(mRes.messages)) setContactMessages(mRes.messages);
    } catch {} finally {
      setLoadingInbox(false);
    }
  };

  useEffect(() => {
    getAdminNotifications().then(setBroadcastData).catch(() => {});
    loadInboxData();
  }, []);

  const handleSaveBroadcast = async () => {
    setSavingBroadcast(true);
    try {
      await updateAdminNotifications(broadcastData);
      setBroadcastMsg('Notification preferences updated successfully.');
      setTimeout(() => setBroadcastMsg(''), 4000);
    } catch (err: any) {
      setBroadcastMsg('Update failed: ' + err.message);
    } finally {
      setSavingBroadcast(false);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      const res = await markAdminNotificationsRead({ mark_all: true });
      if (res && res.counts) setCounts(res.counts);
      setFeed((prev) => prev.map((item) => ({ ...item, is_read: true })));
    } catch {}
  };

  const handleMarkSingleRead = async (id: string) => {
    try {
      await markAdminNotificationsRead({ notification_id: id });
      setFeed((prev) => prev.map((i) => i.id === id ? { ...i, is_read: true } : i));
      setCounts((prev) => ({ ...prev, total_unread: Math.max(0, prev.total_unread - 1) }));
    } catch {}
  };

  const handleDeleteMessage = async (msgId: string) => {
    if (!confirm('Are you sure you want to delete this contact submission?')) return;
    try {
      await deleteAdminContactMessage(msgId);
      setContactMessages((prev) => prev.filter((m) => m.id !== msgId));
      setFeed((prev) => prev.filter((f) => f.id !== msgId));
      if (selectedMessage?.id === msgId) {
        setIsMessageModalOpen(false);
        setSelectedMessage(null);
      }
    } catch {}
  };

  const handleDeleteFromModal = async (msgId: string) => {
    await handleDeleteMessage(msgId);
  };

  const handleCopyEmail = (email: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(email);
      setCopiedEmail(true);
      setTimeout(() => setCopiedEmail(false), 2000);
    }
  };

  const handleOpenAction = (item: NotificationFeedItem) => {
    if (item.category === 'CONTACT') {
      const fullMsg = contactMessages.find((m) => m.id === item.id) || {
        id: item.id,
        name: item.metadata?.name || item.title.replace('Inquiry from ', ''),
        email: item.metadata?.email || '',
        bank_name: item.metadata?.bank_name || item.metadata?.bank || '',
        subject_type: item.metadata?.subject_type || 'REPORT_ISSUE',
        job_id: item.metadata?.job_id || '',
        message: item.metadata?.message || item.snippet,
        created_at: item.created_at,
        is_read: item.is_read
      };
      setSelectedMessage(fullMsg);
      setIsMessageModalOpen(true);
      if (!item.is_read) {
        handleMarkSingleRead(item.id);
      }
    } else {
      router.push(item.action_url);
    }
  };

  // Automatically open message modal if query parameter messageId is supplied
  useEffect(() => {
    const msgId = searchParams.get('messageId');
    if (msgId && (contactMessages.length > 0 || feed.length > 0)) {
      const match = contactMessages.find((m) => m.id === msgId) || 
        feed.find((f) => f.id === msgId && f.category === 'CONTACT');
      if (match) {
        const fullMsg = 'message' in match && match.message ? match : {
          id: match.id,
          name: (match as any).metadata?.name || match.title?.replace('Inquiry from ', '') || 'Anonymous User',
          email: (match as any).metadata?.email || '',
          bank_name: (match as any).metadata?.bank_name || (match as any).metadata?.bank || '',
          subject_type: (match as any).metadata?.subject_type || 'REPORT_ISSUE',
          job_id: (match as any).metadata?.job_id || '',
          message: (match as any).metadata?.message || (match as any).snippet || '',
          created_at: match.created_at,
          is_read: match.is_read
        };
        setSelectedMessage(fullMsg);
        setIsMessageModalOpen(true);
        if (!match.is_read) {
          handleMarkSingleRead(match.id);
        }
      }
    }
  }, [searchParams, contactMessages, feed]);

  const filteredFeed = feed.filter((item) => {
    if (categoryFilter !== 'ALL' && item.category !== categoryFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        item.title.toLowerCase().includes(q) ||
        item.snippet.toLowerCase().includes(q) ||
        item.category_label.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      
      {/* Top Header Card */}
      <div className="bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Notification & Broadcast Center
            </h1>
            {counts.total_unread > 0 && (
              <span className="bg-rose-500 text-white font-black text-xs px-2 py-0.5 rounded-full animate-pulse">
                {counts.total_unread} Actionable
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500">
            Real-time support inquiries, appeals, review flags, recovery requests, and sitewide broadcast banners
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-2xl self-start sm:self-auto">
          <button
            onClick={() => setActiveView('inbox')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              activeView === 'inbox'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Inbox className="w-3.5 h-3.5" />
            <span>Inquiries & Alerts</span>
            {counts.total_unread > 0 && (
              <span className="w-2 h-2 rounded-full bg-rose-500" />
            )}
          </button>

          <button
            onClick={() => setActiveView('broadcast')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              activeView === 'broadcast'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Megaphone className="w-3.5 h-3.5" />
            <span>Broadcast Banners</span>
          </button>
        </div>
      </div>

      {activeView === 'inbox' ? (
        <div className="space-y-6">
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
            <button
              onClick={() => setCategoryFilter(categoryFilter === 'CONTACT' ? 'ALL' : 'CONTACT')}
              className={`p-4 rounded-2xl border text-left transition-all ${
                categoryFilter === 'CONTACT'
                  ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-500/20 shadow-xs'
                  : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between text-xs text-slate-500 font-semibold">
                <span>Contact Messages</span>
                <Mail className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-black text-slate-900 mt-2">
                {counts.categories.contact_messages}
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">From /contact form</span>
            </button>

            <button
              onClick={() => setCategoryFilter(categoryFilter === 'APPEAL' ? 'ALL' : 'APPEAL')}
              className={`p-4 rounded-2xl border text-left transition-all ${
                categoryFilter === 'APPEAL'
                  ? 'bg-rose-50 border-rose-300 ring-2 ring-rose-500/20 shadow-xs'
                  : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between text-xs text-slate-500 font-semibold">
                <span>Account Appeals</span>
                <ShieldAlert className="w-4 h-4 text-rose-600" />
              </div>
              <div className="text-2xl font-black text-slate-900 mt-2">
                {counts.categories.account_appeals}
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Pending recovery review</span>
            </button>

            <button
              onClick={() => setCategoryFilter(categoryFilter === 'REVIEW' ? 'ALL' : 'REVIEW')}
              className={`p-4 rounded-2xl border text-left transition-all ${
                categoryFilter === 'REVIEW'
                  ? 'bg-amber-50 border-amber-300 ring-2 ring-amber-500/20 shadow-xs'
                  : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between text-xs text-slate-500 font-semibold">
                <span>Conversion Reviews</span>
                <FileCheck className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-2xl font-black text-slate-900 mt-2">
                {counts.categories.conversion_reviews}
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Balance mismatches</span>
            </button>

            <button
              onClick={() => setCategoryFilter(categoryFilter === 'RECOVERY' ? 'ALL' : 'RECOVERY')}
              className={`p-4 rounded-2xl border text-left transition-all ${
                categoryFilter === 'RECOVERY'
                  ? 'bg-purple-50 border-purple-300 ring-2 ring-purple-500/20 shadow-xs'
                  : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between text-xs text-slate-500 font-semibold">
                <span>Support Recovery</span>
                <KeyRound className="w-4 h-4 text-purple-600" />
              </div>
              <div className="text-2xl font-black text-slate-900 mt-2">
                {counts.categories.support_requests}
              </div>
              <span className="text-[10px] text-slate-400 mt-1 block">Lost email/credentials</span>
            </button>
          </div>

          {/* Filter & Search Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search inquiries, names, emails, statements..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
              />
            </div>

            <div className="flex items-center gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={loadInboxData}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Refresh
              </Button>
              {counts.total_unread > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleMarkAllRead}
                  icon={<CheckCheck className="w-3.5 h-3.5" />}
                >
                  Mark All Read
                </Button>
              )}
            </div>
          </div>

          {/* Notifications Feed */}
          <div className="space-y-3">
            {loadingInbox ? (
              <div className="p-12 text-center text-xs text-slate-400">
                Loading notifications feed...
              </div>
            ) : filteredFeed.length === 0 ? (
              <div className="p-12 text-center text-xs text-slate-400 bg-white rounded-3xl border border-dashed border-slate-200">
                No notifications match your current filter.
              </div>
            ) : (
              filteredFeed.map((item) => (
                <Card
                  key={item.id}
                  className={`p-4 sm:p-5 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                    !item.is_read ? 'border-brand-300 bg-brand-50/20' : 'bg-white'
                  }`}
                >
                  <div className="flex items-start gap-3.5 min-w-0">
                    <div className="p-2 rounded-xl bg-slate-100 flex-shrink-0 mt-0.5">
                      {item.category === 'CONTACT' && <Mail className="w-4 h-4 text-blue-600" />}
                      {item.category === 'APPEAL' && <ShieldAlert className="w-4 h-4 text-rose-600" />}
                      {item.category === 'REVIEW' && <FileCheck className="w-4 h-4 text-amber-600" />}
                      {item.category === 'RECOVERY' && <KeyRound className="w-4 h-4 text-purple-600" />}
                    </div>

                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-extrabold text-xs text-slate-900">
                          {item.title}
                        </span>
                        <Badge
                          variant={
                            item.category === 'APPEAL'
                              ? 'danger'
                              : item.category === 'CONTACT'
                              ? 'primary'
                              : item.category === 'REVIEW'
                              ? 'warning'
                              : 'purple'
                          }
                          size="sm"
                        >
                          {item.category_label}
                        </Badge>
                        {!item.is_read && (
                          <Badge variant="danger" size="sm" pulse>
                            Unread
                          </Badge>
                        )}
                      </div>

                      <p className="text-xs text-slate-600 leading-relaxed break-words">
                        {item.snippet}
                      </p>

                      <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono pt-1">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(item.created_at).toLocaleString('en-IN', {
                            day: '2-digit',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </span>
                        {item.metadata?.email && (
                          <span>Email: {item.metadata.email}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center flex-shrink-0 pt-2 sm:pt-0">
                    {!item.is_read && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleMarkSingleRead(item.id)}
                        title="Mark as read"
                      >
                        <CheckCheck className="w-3.5 h-3.5" />
                      </Button>
                    )}

                    {item.category === 'CONTACT' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteMessage(item.id)}
                        className="text-slate-400 hover:text-rose-600"
                        title="Delete inquiry"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    )}

                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenAction(item)}
                      iconRight={<ExternalLink className="w-3 h-3" />}
                    >
                      Open Action
                    </Button>
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>
      ) : (
        /* Broadcast Banners Console */
        <div className="space-y-6">
          {broadcastMsg && (
            <div className="p-4 bg-brand-50 border border-brand-200 rounded-2xl text-xs text-brand-800 font-semibold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-brand-600 flex-shrink-0" />
              <span>{broadcastMsg}</span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Announcement Banner */}
            <Card className="p-6 space-y-4 shadow-card">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
                  <Bell className="w-4 h-4 text-brand-600" />
                  General Announcement Banner
                </h2>
                <input
                  type="checkbox"
                  checked={broadcastData.announcement_enabled}
                  onChange={(e) => setBroadcastData({ ...broadcastData, announcement_enabled: e.target.checked })}
                  className="w-4 h-4 accent-brand-600 rounded"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">Banner Message</label>
                <textarea
                  rows={3}
                  value={broadcastData.announcement_message}
                  onChange={(e) => setBroadcastData({ ...broadcastData, announcement_message: e.target.value })}
                  className="w-full p-3 text-xs rounded-xl border border-slate-300"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">Banner Type</label>
                <select
                  value={broadcastData.announcement_type}
                  onChange={(e) => setBroadcastData({ ...broadcastData, announcement_type: e.target.value })}
                  className="w-full p-2 text-xs rounded-xl border border-slate-300"
                >
                  <option value="info">Informational (Blue)</option>
                  <option value="warning">Important Notice (Amber)</option>
                  <option value="alert">Critical Alert (Rose)</option>
                </select>
              </div>
            </Card>

            {/* Maintenance Mode Banner */}
            <Card className="p-6 space-y-4 shadow-card">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  Maintenance Schedule Banner
                </h2>
                <input
                  type="checkbox"
                  checked={broadcastData.maintenance_banner}
                  onChange={(e) => setBroadcastData({ ...broadcastData, maintenance_banner: e.target.checked })}
                  className="w-4 h-4 accent-amber-600 rounded"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">Maintenance Notice</label>
                <textarea
                  rows={3}
                  value={broadcastData.maintenance_message}
                  onChange={(e) => setBroadcastData({ ...broadcastData, maintenance_message: e.target.value })}
                  className="w-full p-3 text-xs rounded-xl border border-slate-300"
                />
              </div>

              <p className="text-[11px] text-slate-400 leading-relaxed">
                Warns active accountants before scheduled nightly upgrades or database optimizations.
              </p>
            </Card>
          </div>

          <div className="flex justify-end">
            <Button
              variant="primary"
              size="md"
              onClick={handleSaveBroadcast}
              loading={savingBroadcast}
              icon={<Save className="w-4 h-4" />}
            >
              Save Notification Settings
            </Button>
          </div>
        </div>
      )}

      {/* Contact Inquiry Detail Modal */}
      <Modal
        isOpen={isMessageModalOpen && selectedMessage !== null}
        onClose={() => {
          setIsMessageModalOpen(false);
          setSelectedMessage(null);
        }}
        title="Contact Inquiry Details"
        description="Public support & statement assistance inquiry"
        size="lg"
      >
        {selectedMessage && (
          <div className="space-y-5">
            {/* Metadata Badges & Timing */}
            <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="primary" size="sm">
                  Contact Message
                </Badge>
                {selectedMessage.subject_type && (
                  <Badge variant="purple" size="sm">
                    {String(selectedMessage.subject_type).replace(/_/g, ' ')}
                  </Badge>
                )}
                <Badge variant={selectedMessage.is_read ? 'neutral' : 'danger'} size="sm">
                  {selectedMessage.is_read ? 'Read' : 'Unread'}
                </Badge>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-slate-500 font-mono">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {new Date(selectedMessage.created_at).toLocaleString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
              </div>
            </div>

            {/* Sender & Context Details */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-1">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                  <User className="w-3 h-3 text-slate-400" /> Sender Name
                </div>
                <div className="text-sm font-bold text-slate-900 truncate">
                  {selectedMessage.name || 'Anonymous User'}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-1">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1 justify-between">
                  <span className="flex items-center gap-1">
                    <Mail className="w-3 h-3 text-slate-400" /> Sender Email
                  </span>
                  {selectedMessage.email && (
                    <button
                      type="button"
                      onClick={() => handleCopyEmail(selectedMessage.email)}
                      className="text-brand-600 hover:text-brand-700 text-[10px] font-semibold inline-flex items-center gap-1"
                      title="Copy email address"
                    >
                      {copiedEmail ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedEmail ? 'Copied' : 'Copy'}</span>
                    </button>
                  )}
                </div>
                <div className="text-sm font-bold text-slate-900 truncate">
                  {selectedMessage.email || 'No email provided'}
                </div>
              </div>

              {selectedMessage.bank_name && (
                <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                    <Building className="w-3 h-3 text-slate-400" /> Referenced Bank
                  </div>
                  <div className="text-xs font-bold text-slate-800">
                    {selectedMessage.bank_name}
                  </div>
                </div>
              )}

              {selectedMessage.job_id && (
                <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                    <FileText className="w-3 h-3 text-slate-400" /> Related Job ID
                  </div>
                  <div className="text-xs font-mono font-bold text-slate-800">
                    {selectedMessage.job_id}
                  </div>
                </div>
              )}
            </div>

            {/* Complete User Message Body */}
            <div className="space-y-2">
              <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
                User Inquiry / Request Details
              </label>
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-800 leading-relaxed whitespace-pre-wrap font-sans min-h-[90px]">
                {selectedMessage.message || selectedMessage.snippet || 'No message text provided.'}
              </div>
            </div>

            {/* Modal Actions */}
            <div className="pt-3 border-t border-slate-100 flex items-center justify-between flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDeleteFromModal(selectedMessage.id)}
                className="text-rose-600 hover:bg-rose-50 border-rose-200"
                icon={<Trash2 className="w-3.5 h-3.5" />}
              >
                Delete Inquiry
              </Button>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setIsMessageModalOpen(false);
                    setSelectedMessage(null);
                  }}
                >
                  Close
                </Button>

                {selectedMessage.email && (
                  <a
                    href={`mailto:${selectedMessage.email}?subject=${encodeURIComponent(
                      `Re: Kangra Hub Support [${selectedMessage.id}]`
                    )}&body=${encodeURIComponent(
                      `Hi ${selectedMessage.name || 'there'},\n\nRegarding your inquiry:\n"${selectedMessage.message?.slice(0, 100)}..."\n\n`
                    )}`}
                  >
                    <Button
                      variant="primary"
                      size="sm"
                      icon={<Mail className="w-3.5 h-3.5" />}
                    >
                      Reply via Email
                    </Button>
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default function AdminNotificationsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-400">Loading notifications center...</div>}>
      <AdminNotificationsContent />
    </Suspense>
  );
}
