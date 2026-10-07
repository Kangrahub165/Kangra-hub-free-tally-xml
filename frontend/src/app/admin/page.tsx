'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Users, 
  Receipt, 
  Star, 
  Bell, 
  ShieldAlert, 
  SlidersHorizontal, 
  Activity, 
  ArrowRight,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  Clock
} from 'lucide-react';
import { 
  getAdminWebsiteUsers, 
  getAdminReviews, 
  getAdminSystemNotifications, 
  getAdminActivityLogs,
  getAdminSettings,
  updateAdminSettings,
  WebsiteAdminUser,
  ReviewItem,
  AdminSystemNotification,
  UserActivityLog
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';

export default function AdminOverviewPage() {
  const [users, setUsers] = useState<WebsiteAdminUser[]>([]);
  const [reviewsData, setReviewsData] = useState<{ reviews: ReviewItem[]; total: number; average_rating: number } | null>(null);
  const [notifications, setNotifications] = useState<AdminSystemNotification[]>([]);
  const [recentActivities, setRecentActivities] = useState<UserActivityLog[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [uRes, rRes, nRes, aRes, sRes] = await Promise.all([
        getAdminWebsiteUsers().catch(() => ({ users: [], total: 0 })),
        getAdminReviews().catch(() => ({ reviews: [], total: 0, average_rating: 5.0 })),
        getAdminSystemNotifications().catch(() => ({ notifications: [], count: 0 })),
        getAdminActivityLogs({ limit: 6 }).catch(() => ({ logs: [], count: 0 })),
        getAdminSettings().catch(() => null),
      ]);
      setUsers(uRes.users || []);
      setReviewsData(rRes);
      setNotifications(nRes.notifications || []);
      setRecentActivities(aRes.logs || []);
      setSettings(sRes);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const totalUsers = users.length;
  const activeUsers = users.filter((u) => u.account_status === 'ACTIVE').length;
  const suspendedUsers = users.filter((u) => u.account_status === 'SUSPENDED' || u.account_status === 'BLOCKED').length;
  const totalInvoices = users.reduce((acc, u) => acc + (u.total_conversions || 0), 0);
  const unreadAlerts = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto animate-fadeIn">
      
      {/* Top Banner / Hero */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-navy-900 text-white p-6 sm:p-7 rounded-3xl border border-navy-800 shadow-glow-brand relative overflow-hidden group">
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 rounded-full bg-brand-500/20 blur-3xl pointer-events-none" />
        <div className="relative z-10 space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-white tracking-tight">
              Main Website Administration
            </h1>
            <Badge variant="purple" size="sm">
              Kangra Hub — Sales & Purchase
            </Badge>
          </div>
          <p className="text-xs text-navy-200">
            Platform governance, user management, activity audit logging, reviews moderation & security controls
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-2.5">
          <Button
            variant="outline-dark"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-xs font-semibold flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>
          <a
            href="https://kangrahubtallyxml.netlify.app/"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button
              variant="dark"
              size="sm"
              className="bg-navy-800 hover:bg-navy-700 text-slate-300 font-semibold text-xs flex items-center gap-1.5"
            >
              <span>Bank Statement Admin</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </Button>
          </a>
        </div>
      </div>

      {/* 4 Primary Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        
        {/* Card 1: Registered Users */}
        <Link href="/admin/users">
          <Card className="p-5 flex flex-col justify-between hover:shadow-card-hover transition-all cursor-pointer group bg-gradient-to-br from-white to-slate-50/50">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Registered Users</span>
                <div className="text-2xl font-black text-slate-900 mt-2 tabular-nums">
                  {loading ? '...' : totalUsers}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100/70 shadow-xs group-hover:scale-110 transition-transform">
                <Users className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px]">
              <span className="text-emerald-600 font-semibold">{activeUsers} Active</span>
              {suspendedUsers > 0 && (
                <span className="text-rose-600 font-semibold">{suspendedUsers} Suspended</span>
              )}
            </div>
          </Card>
        </Link>

        {/* Card 2: Sales & Purchase Invoices */}
        <Card className="p-5 flex flex-col justify-between hover:shadow-card-hover transition-all bg-gradient-to-br from-white to-slate-50/50 group">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Invoices Converted</span>
              <div className="text-2xl font-black text-slate-900 mt-2 tabular-nums">
                {loading ? '...' : totalInvoices}
              </div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100/70 shadow-xs group-hover:scale-110 transition-transform">
              <Receipt className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            Sales & Purchase Tally XML vouchers
          </div>
        </Card>

        {/* Card 3: Ratings & Reviews */}
        <Link href="/admin/reviews">
          <Card className="p-5 flex flex-col justify-between hover:shadow-card-hover transition-all cursor-pointer group bg-gradient-to-br from-white to-slate-50/50">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Average Rating</span>
                <div className="text-2xl font-black text-amber-500 mt-2 tabular-nums flex items-baseline gap-1">
                  <span>{loading ? '...' : (reviewsData?.average_rating ?? 5.0)}</span>
                  <span className="text-sm font-bold text-amber-400">★</span>
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-500 flex items-center justify-center border border-amber-100/70 shadow-xs group-hover:scale-110 transition-transform">
                <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
              <span>{reviewsData?.total ?? 0} Customer Reviews</span>
              <span className="text-brand-600 font-semibold group-hover:translate-x-0.5 transition-transform">Manage →</span>
            </div>
          </Card>
        </Link>

        {/* Card 4: System Alerts & Notifications */}
        <Link href="/admin/notifications">
          <Card className="p-5 flex flex-col justify-between hover:shadow-card-hover transition-all cursor-pointer group bg-gradient-to-br from-white to-slate-50/50">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">System Alerts</span>
                <div className="text-2xl font-black text-slate-900 mt-2 tabular-nums">
                  {loading ? '...' : notifications.length}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center border border-purple-100/70 shadow-xs group-hover:scale-110 transition-transform">
                <Bell className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] flex items-center justify-between">
              <span className={unreadAlerts > 0 ? "text-rose-600 font-bold" : "text-emerald-600 font-semibold"}>
                {unreadAlerts} Unread Alerts
              </span>
              <span className="text-brand-600 font-semibold group-hover:translate-x-0.5 transition-transform">View →</span>
            </div>
          </Card>
        </Link>

      </div>

      {/* Main Website Modules Quick Navigation */}
      <div>
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-3">
          Administrative Modules
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          
          <Link href="/admin/users">
            <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-card hover:shadow-card-hover hover:border-brand-300 transition-all group flex flex-col justify-between h-full">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0 border border-brand-100">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900 group-hover:text-brand-600 transition-colors">
                    User Management
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Registered users, identity details, mobile numbers, gender, suspension controls & activity timelines.
                  </p>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-brand-600 font-bold">
                <span>Manage Users</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>

          <Link href="/admin/activity">
            <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-card hover:shadow-card-hover hover:border-brand-300 transition-all group flex flex-col justify-between h-full">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 border border-emerald-100">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900 group-hover:text-brand-600 transition-colors">
                    User Activity Logs
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Audit trail recording WHO did WHAT, WHEN, in WHICH MODULE, with WHAT STATUS across Web & PWA.
                  </p>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-brand-600 font-bold">
                <span>View Complete Logs</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>

          <Link href="/admin/reviews">
            <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-card hover:shadow-card-hover hover:border-brand-300 transition-all group flex flex-col justify-between h-full">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-500 flex items-center justify-center shrink-0 border border-amber-100">
                  <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900 group-hover:text-brand-600 transition-colors">
                    Ratings & Reviews
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Moderate customer ratings (1 to 5 stars), approve or hide reviews, and track customer satisfaction.
                  </p>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-brand-600 font-bold">
                <span>Moderate Reviews</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>

        </div>
      </div>

      {/* Grid: Recent User Activities & Platform Policies */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left 7 Cols: Recent User Activity Stream */}
        <Card className="lg:col-span-7 shadow-card">
          <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <CardTitle className="text-base">Recent User Activities</CardTitle>
              <CardDescription>Live audit trail of user actions across Web and PWA</CardDescription>
            </div>
            <Link href="/admin/activity">
              <Button variant="ghost" size="sm" className="text-xs">
                View All
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="p-4 sm:p-6">
            {recentActivities.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                No recent activity records found.
              </div>
            ) : (
              <div className="space-y-3">
                {recentActivities.map((act) => (
                  <div key={act.id} className="p-3 bg-slate-50/80 rounded-xl border border-slate-100 flex items-start justify-between gap-3 text-xs">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900">{act.action}</span>
                        <Badge variant={act.status === 'SUCCESS' ? 'success' : 'danger'} size="sm">
                          {act.status}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-slate-500">
                        By <span className="font-medium text-slate-700">{act.user_email || 'Anonymous'}</span> • Module: {act.module || 'System'}
                      </p>
                    </div>
                    <span className="text-[10px] text-slate-400 shrink-0 font-mono">
                      {new Date(act.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right 5 Cols: Platform Policies & Quota Architecture */}
        <Card className="lg:col-span-5 shadow-card">
          <CardHeader className="border-b border-slate-100 pb-4">
            <CardTitle className="text-base">Quota & Security Framework</CardTitle>
            <CardDescription>Operational parameters for Sales & Purchase engine</CardDescription>
          </CardHeader>
          <CardContent className="p-4 sm:p-6 space-y-3 text-xs">
            
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                <span className="text-slate-500 font-medium block">Daily Free Quota</span>
                <span className="text-sm font-black text-slate-900">5 Free Bills Daily</span>
              </div>
              <Badge variant="success" size="sm">Asia/Kolkata</Badge>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                <span className="text-slate-500 font-medium block">Staff Membership</span>
                <span className="text-sm font-black text-amber-600">₹499 / 30 Days</span>
              </div>
              <Badge variant="primary" size="sm">Subscription Only</Badge>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                <span className="text-slate-500 font-medium block">Authentication Security</span>
                <span className="text-sm font-black text-emerald-600">Real Supabase Auth</span>
              </div>
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                <span className="text-slate-500 font-medium block">Volatile OCR Processing</span>
                <span className="text-sm font-black text-slate-900">Zero On-Disk Storage</span>
              </div>
              <Badge variant="purple" size="sm">Encrypted RAM</Badge>
            </div>

          </CardContent>
        </Card>

      </div>

    </div>
  );
}
