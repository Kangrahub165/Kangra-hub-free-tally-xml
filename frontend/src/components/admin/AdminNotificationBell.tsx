'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  Bell, 
  Mail, 
  ShieldAlert, 
  FileCheck, 
  KeyRound, 
  CheckCheck, 
  ExternalLink,
  ChevronRight,
  Clock
} from 'lucide-react';
import { 
  getAdminUnreadCounts, 
  getAdminNotificationsFeed, 
  markAdminNotificationsRead, 
  UnreadNotificationCounts, 
  NotificationFeedItem 
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';

export function AdminNotificationBell() {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [counts, setCounts] = useState<UnreadNotificationCounts>({
    total_unread: 0,
    categories: {
      contact_messages: 0,
      account_appeals: 0,
      conversion_reviews: 0,
      support_requests: 0,
    },
  });
  const [feed, setFeed] = useState<NotificationFeedItem[]>([]);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchCounts = async () => {
    try {
      const data = await getAdminUnreadCounts();
      if (data && typeof data.total_unread === 'number') {
        setCounts(data);
      }
    } catch {}
  };

  const fetchFeed = async () => {
    setLoading(true);
    try {
      const data = await getAdminNotificationsFeed();
      if (data && Array.isArray(data.items)) {
        setFeed(data.items);
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCounts();
    // Poll unread counts every 30 seconds
    const interval = setInterval(fetchCounts, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchFeed();
    }
  }, [isOpen]);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleMarkAllRead = async () => {
    try {
      const res = await markAdminNotificationsRead({ mark_all: true });
      if (res && res.counts) {
        setCounts(res.counts);
      }
      setFeed((prev) => prev.map((item) => ({ ...item, is_read: true })));
    } catch {}
  };

  const handleItemClick = async (item: NotificationFeedItem) => {
    try {
      await markAdminNotificationsRead({ notification_id: item.id });
      setCounts((prev) => ({
        ...prev,
        total_unread: Math.max(0, prev.total_unread - 1),
      }));
    } catch {}
    setIsOpen(false);
    router.push(item.action_url);
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'CONTACT':
        return <Mail className="w-3.5 h-3.5 text-blue-600" />;
      case 'APPEAL':
        return <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />;
      case 'REVIEW':
        return <FileCheck className="w-3.5 h-3.5 text-amber-600" />;
      case 'RECOVERY':
        return <KeyRound className="w-3.5 h-3.5 text-purple-600" />;
      default:
        return <Bell className="w-3.5 h-3.5 text-slate-600" />;
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-xl text-slate-300 hover:text-white hover:bg-slate-800 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/40"
        aria-label="Admin Notifications"
        title="Admin Notifications Center"
      >
        <Bell className="w-5 h-5" />
        {counts.total_unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-rose-500 text-white font-black text-[10px] rounded-full flex items-center justify-center animate-pulse shadow-sm">
            {counts.total_unread > 99 ? '99+' : counts.total_unread}
          </span>
        )}
      </button>

      {/* Popover Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2.5 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 z-50 overflow-hidden animate-fadeIn">
          {/* Header */}
          <div className="p-4 bg-slate-900 text-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bell className="w-4 h-4 text-brand-400" />
              <span className="text-xs font-bold uppercase tracking-wider">
                Admin Notifications
              </span>
              {counts.total_unread > 0 && (
                <span className="bg-rose-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {counts.total_unread} new
                </span>
              )}
            </div>
            {counts.total_unread > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-[11px] text-slate-300 hover:text-white font-semibold flex items-center gap-1 transition-colors"
                title="Mark all notifications as read"
              >
                <CheckCheck className="w-3.5 h-3.5 text-emerald-400" />
                Mark all read
              </button>
            )}
          </div>

          {/* Category Summary Pills */}
          <div className="grid grid-cols-2 gap-1.5 p-2.5 bg-slate-50 border-b border-slate-100 text-[11px]">
            <Link
              href="/admin/notifications?tab=contact"
              onClick={() => setIsOpen(false)}
              className="p-2 rounded-xl bg-white border border-slate-200/80 hover:border-brand-300 hover:shadow-xs transition-all flex items-center justify-between"
            >
              <div className="flex items-center gap-1.5 font-semibold text-slate-700">
                <Mail className="w-3.5 h-3.5 text-blue-600" />
                <span>Messages</span>
              </div>
              <Badge variant={counts.categories.contact_messages > 0 ? 'primary' : 'neutral'} size="sm">
                {counts.categories.contact_messages}
              </Badge>
            </Link>

            <Link
              href="/admin/appeals"
              onClick={() => setIsOpen(false)}
              className="p-2 rounded-xl bg-white border border-slate-200/80 hover:border-rose-300 hover:shadow-xs transition-all flex items-center justify-between"
            >
              <div className="flex items-center gap-1.5 font-semibold text-slate-700">
                <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
                <span>Appeals</span>
              </div>
              <Badge variant={counts.categories.account_appeals > 0 ? 'danger' : 'neutral'} size="sm">
                {counts.categories.account_appeals}
              </Badge>
            </Link>

            <Link
              href="/admin/conversions"
              onClick={() => setIsOpen(false)}
              className="p-2 rounded-xl bg-white border border-slate-200/80 hover:border-amber-300 hover:shadow-xs transition-all flex items-center justify-between"
            >
              <div className="flex items-center gap-1.5 font-semibold text-slate-700">
                <FileCheck className="w-3.5 h-3.5 text-amber-600" />
                <span>Reviews</span>
              </div>
              <Badge variant={counts.categories.conversion_reviews > 0 ? 'warning' : 'neutral'} size="sm">
                {counts.categories.conversion_reviews}
              </Badge>
            </Link>

            <Link
              href="/admin/recovery"
              onClick={() => setIsOpen(false)}
              className="p-2 rounded-xl bg-white border border-slate-200/80 hover:border-purple-300 hover:shadow-xs transition-all flex items-center justify-between"
            >
              <div className="flex items-center gap-1.5 font-semibold text-slate-700">
                <KeyRound className="w-3.5 h-3.5 text-purple-600" />
                <span>Recovery</span>
              </div>
              <Badge variant={counts.categories.support_requests > 0 ? 'purple' : 'neutral'} size="sm">
                {counts.categories.support_requests}
              </Badge>
            </Link>
          </div>

          {/* Notification Feed List */}
          <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
            {loading ? (
              <div className="p-8 text-center text-xs text-slate-400">
                Loading notifications...
              </div>
            ) : feed.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No active notifications right now.
              </div>
            ) : (
              feed.slice(0, 10).map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleItemClick(item)}
                  className={`p-3.5 hover:bg-slate-50 cursor-pointer transition-colors flex items-start gap-3 ${
                    !item.is_read ? 'bg-brand-50/40' : ''
                  }`}
                >
                  <div className="mt-0.5 p-1.5 rounded-lg bg-slate-100 flex-shrink-0">
                    {getCategoryIcon(item.category)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <h4 className="text-xs font-bold text-slate-900 truncate">
                        {item.title}
                      </h4>
                      {!item.is_read && (
                        <span className="w-2 h-2 rounded-full bg-rose-500 flex-shrink-0" />
                      )}
                    </div>
                    <p className="text-[11px] text-slate-600 mt-0.5 line-clamp-2 leading-relaxed">
                      {item.snippet}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400 font-mono">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(item.created_at).toLocaleDateString('en-IN', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                      <span>•</span>
                      <span className="uppercase font-sans font-semibold text-slate-500">
                        {item.category_label}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="p-3 bg-slate-50 border-t border-slate-100 text-center">
            <Link
              href="/admin/notifications"
              onClick={() => setIsOpen(false)}
              className="text-xs font-bold text-brand-600 hover:text-brand-700 flex items-center justify-center gap-1"
            >
              <span>Go to Notifications Center</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
