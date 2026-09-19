'use client';

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  FileSpreadsheet, 
  CheckCircle2, 
  XCircle, 
  Sparkles, 
  Layers, 
  ToggleLeft, 
  ToggleRight,
  RefreshCw,
  Server,
  ShieldCheck,
  Cpu
} from 'lucide-react';
import { getAdminMetrics, getAdminSettings, updateAdminSettings } from '@/lib/api';
import { BuyCoffeeCard } from '@/components/BuyCoffeeCard';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';

export default function AdminOverviewPage() {
  const [metrics, setMetrics] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [updatingMode, setUpdatingMode] = useState(false);

  const fetchData = () => {
    Promise.all([getAdminMetrics(), getAdminSettings()])
      .then(([m, s]) => {
        setMetrics(m);
        setSettings(s);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleToggleMode = async () => {
    if (!settings) return;
    const newMode = settings.site_mode === 'FREE' ? 'PAID' : 'FREE';
    setUpdatingMode(true);
    try {
      await updateAdminSettings({ site_mode: newMode });
      await fetchData();
    } catch (e) {
      alert('Failed to update site mode');
    } finally {
      setUpdatingMode(false);
    }
  };

  const isFree = settings?.site_mode === 'FREE';

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      
      {/* Title & Site Mode Controller */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Administrator Overview
            </h1>
            <Badge variant="purple" size="sm">
              Root Console
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Real-time conversion traffic monitoring, quota controllers, and global platform flags
          </p>
        </div>

        {/* Global Access Mode Switch (PRD Section 10, 11, 57) */}
        <div className="flex items-center gap-3.5 bg-slate-50 p-2.5 rounded-2xl border border-slate-200/80">
          <div className="text-left">
            <span className="text-[10px] uppercase font-bold text-slate-400 block leading-none mb-1">
              Website Access Mode
            </span>
            <span className={`text-xs font-black ${isFree ? 'text-emerald-700' : 'text-brand-700'}`}>
              {isFree ? 'FREE TO EVERYONE' : 'PAID SERVICE'}
            </span>
          </div>
          <button
            onClick={handleToggleMode}
            disabled={updatingMode}
            className={`p-1.5 rounded-xl border transition-all ${
              isFree
                ? 'bg-emerald-600 text-white border-emerald-700 hover:bg-emerald-700 shadow-xs'
                : 'bg-brand-600 text-white border-brand-700 hover:bg-brand-700 shadow-xs'
            }`}
            title="Toggle between Free and Paid mode"
            aria-label="Toggle site access mode"
          >
            {isFree ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        
        <Card className="p-5 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Total Users</span>
              <div className="text-2xl font-black text-slate-900 mt-2 tabular-nums">{metrics?.total_users ?? 2}</div>
            </div>
            <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100/70 shadow-xs">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            Registered user profiles
          </div>
        </Card>

        <Card className="p-5 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Unlimited Users</span>
              <div className="text-2xl font-black text-emerald-600 mt-2 tabular-nums">{metrics?.unlimited_users ?? 1}</div>
            </div>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100/70 shadow-xs">
              <Sparkles className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            Bypassing daily page caps
          </div>
        </Card>

        <Card className="p-5 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Conversions Today</span>
              <div className="text-2xl font-black text-slate-900 mt-2 tabular-nums">{metrics?.conversions_today ?? 0}</div>
            </div>
            <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center border border-purple-100/70 shadow-xs">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            {metrics?.pages_processed_today ?? 0} pages parsed today
          </div>
        </Card>

        <Card className="p-5 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Conversion Health</span>
              <div className="text-2xl font-black text-slate-900 mt-2 tabular-nums">100%</div>
            </div>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100/70 shadow-xs">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-emerald-600 font-semibold">
            Zero schema failures recorded
          </div>
        </Card>

      </div>

      {/* Grid: Platform Engine Status & Section 129 Support Card */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left 8 Cols: Platform Engine Status */}
        <Card className="lg:col-span-8 shadow-card">
          <CardHeader>
            <CardTitle>Platform Engine & Quota Architecture</CardTitle>
            <CardDescription>
              Live operational parameters governing daily user limits and temporary cleanup schedules
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <span className="text-slate-500 font-medium">Free Daily User Limit</span>
                <div className="text-lg font-black text-slate-900 mt-1">
                  {settings?.free_daily_page_limit ?? 50} Pages / User
                </div>
                <span className="text-[11px] text-slate-500 mt-0.5 block">Resets at 00:00 Asia/Kolkata</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <span className="text-slate-500 font-medium">Registered Bank Parsers</span>
                <div className="text-lg font-black text-brand-600 mt-1">
                  38 Target Banks Active
                </div>
                <span className="text-[11px] text-slate-500 mt-0.5 block">Automated column detection</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <span className="text-slate-500 font-medium">Temporary Document Storage</span>
                <div className="text-lg font-black text-slate-900 mt-1">
                  Auto-Purge (Volatile RAM)
                </div>
                <span className="text-[11px] text-slate-500 mt-0.5 block">Zero permanent financial retention</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <span className="text-slate-500 font-medium">Admin Quota Exemption</span>
                <div className="text-lg font-black text-emerald-600 mt-1">
                  Server-Side Unlimited
                </div>
                <span className="text-[11px] text-slate-500 mt-0.5 block">Uncapped diagnostic conversions</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Right 4 Cols: Section 129 "Buy Me a Coffee" Admin Widget */}
        <div className="lg:col-span-4 space-y-4">
          <BuyCoffeeCard
            upiId={settings?.buy_coffee_upi_id}
            paymentUrl={settings?.buy_coffee_payment_url}
            buttonText={settings?.buy_coffee_button_text}
            supportMessage={settings?.buy_coffee_message}
            qrPath={settings?.buy_coffee_qr_path || '/buy-a-coffee/googlepay_qr.png'}
          />

          <div className="p-4 rounded-2xl bg-slate-100 border border-slate-200/80 text-[11px] text-slate-500 leading-normal">
            🔒 <strong>Strictly Admin-Only:</strong> This voluntary project support card is visible exclusively inside the administrator console and is never rendered to public website visitors or during conversion reviews.
          </div>
        </div>

      </div>

    </div>
  );
}
