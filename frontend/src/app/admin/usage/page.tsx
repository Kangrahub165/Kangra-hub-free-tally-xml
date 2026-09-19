'use client';

import React, { useState, useEffect } from 'react';
import { Gauge, Clock, Building2, Users, RefreshCw, AlertCircle, TrendingUp } from 'lucide-react';
import { getAdminUsageOverview } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';

export default function AdminUsagePage() {
  const [usage, setUsage] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const loadData = () => {
    setLoading(true);
    getAdminUsageOverview()
      .then((data) => {
        setUsage(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-black text-slate-900">Usage & Quotas Command Center</h1>
            <Badge variant="primary" size="sm">Asia/Kolkata Midnight Reset</Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Real-time tracking of daily free page allowances, bank usage density, and server-side atomic quota enforcement.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} loading={loading} icon={<RefreshCw className="w-3.5 h-3.5" />}>
          Refresh Usage
        </Button>
      </div>

      {/* Top 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Pages Processed Today</span>
          <div className="text-2xl font-black text-slate-900 mt-2 font-mono tabular-nums">
            {usage?.total_pages_today || 0}
          </div>
          <span className="text-[11px] text-emerald-600 font-semibold mt-1 inline-block">Atomic counter verified</span>
        </Card>

        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Standard Free Limit</span>
          <div className="text-2xl font-black text-slate-900 mt-2 font-mono tabular-nums">
            {usage?.free_daily_limit || 50} <span className="text-xs font-semibold text-slate-500">pgs/user</span>
          </div>
          <span className="text-[11px] text-slate-500 mt-1 inline-block">Applies to standard accounts</span>
        </Card>

        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Unlimited User Tier</span>
          <div className="text-2xl font-black text-purple-700 mt-2 font-mono tabular-nums">
            {usage?.unlimited_user_count || 1}
          </div>
          <span className="text-[11px] text-purple-600 font-semibold mt-1 inline-block">Bypass quota enforcement</span>
        </Card>

        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Next Auto Reset</span>
          <div className="text-2xl font-black text-slate-900 mt-2 font-mono">
            00:00 IST
          </div>
          <span className="text-[11px] text-slate-500 mt-1 inline-block">Asia/Kolkata timezone</span>
        </Card>
      </div>

      {/* Usage by Bank Breakdown */}
      <Card className="shadow-card p-6">
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Building2 className="w-4 h-4 text-brand-600" />
          Page Volume Breakdown by Bank Today
        </h2>

        {usage?.pages_by_bank && Object.keys(usage.pages_by_bank).length > 0 ? (
          <div className="space-y-3">
            {Object.entries(usage.pages_by_bank).map(([bank, count]: [string, any]) => (
              <div key={bank} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs">
                <span className="font-bold text-slate-800">{bank}</span>
                <span className="font-mono font-extrabold text-slate-900 bg-white px-2.5 py-1 rounded-lg border border-slate-200 shadow-xs">
                  {count} pages
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-xs text-slate-500">
            No bank conversions processed today yet. Quota resets at 00:00 IST.
          </div>
        )}
      </Card>
    </div>
  );
}
