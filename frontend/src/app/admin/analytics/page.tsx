'use client';

import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Users, FileSpreadsheet, RefreshCw } from 'lucide-react';
import { getAdminAnalytics } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';

export default function AdminAnalyticsPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    getAdminAnalytics().then(setData).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-black text-slate-900">Platform Analytics & Growth Trends</h1>
          <Badge variant="primary" size="sm">Live Telemetry</Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Aggregated metrics for daily conversion throughput, banking template utilization, and platform success rates.
        </p>
      </div>

      {/* 3 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Overall Conversion Success Rate</span>
          <div className="text-2xl font-black text-emerald-600 mt-2 font-mono">
            {data?.conversion_success_rate || 100}%
          </div>
          <span className="text-[11px] text-slate-500 mt-1 inline-block">Double-entry balanced</span>
        </Card>

        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Total Lifetime Conversions</span>
          <div className="text-2xl font-black text-slate-900 mt-2 font-mono tabular-nums">
            {data?.total_conversions || 0}
          </div>
          <span className="text-[11px] text-brand-600 font-semibold mt-1 inline-block">Vouchers generated</span>
        </Card>

        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Registered Accounts</span>
          <div className="text-2xl font-black text-slate-900 mt-2 font-mono tabular-nums">
            {data?.total_users || 0}
          </div>
          <span className="text-[11px] text-slate-500 mt-1 inline-block">Accountants & SMEs</span>
        </Card>
      </div>

      {/* Top Banks & Daily Trends */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-6 shadow-card">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand-600" />
            Most Popular Bank Formats
          </h2>
          <div className="space-y-2.5">
            {data?.popular_banks?.map((b: any, idx: number) => (
              <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs">
                <span className="font-bold text-slate-800">{b.bank}</span>
                <Badge variant="primary" size="sm">{b.conversions} jobs</Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6 shadow-card">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900 mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-emerald-600" />
            Weekly Conversion Volume
          </h2>
          <div className="space-y-2 text-xs">
            {data?.daily_trends?.map((d: any, idx: number) => (
              <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-slate-50">
                <span className="font-bold text-slate-700 w-12">{d.day}</span>
                <div className="flex-1 mx-3 bg-slate-200 rounded-full h-2 overflow-hidden">
                  <div className="bg-brand-500 h-full rounded-full" style={{ width: `${Math.min(100, d.conversions * 3)}%` }} />
                </div>
                <span className="font-mono text-slate-800 font-bold">{d.conversions} jobs ({d.pages} pgs)</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
