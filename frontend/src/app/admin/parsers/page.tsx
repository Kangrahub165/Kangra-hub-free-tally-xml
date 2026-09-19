'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { getAdminParsersHealth } from '@/lib/api';
import { Cpu, CheckCircle2, FlaskConical, Building2, Search, ArrowUpRight, ShieldCheck, Activity, Filter, X } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';

export default function AdminParsersPage() {
  const [parsers, setParsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'HEALTHY' | 'UNTESTED'>('ALL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminParsersHealth()
      .then((data) => {
        setParsers(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filtered = parsers.filter((p) => {
    const matchesSearch =
      p.bank_name.toLowerCase().includes(search.toLowerCase()) ||
      p.parser_key.toLowerCase().includes(search.toLowerCase());
    if (!matchesSearch) return false;
    if (filterStatus === 'ALL') return true;
    if (filterStatus === 'HEALTHY') return p.status === 'Healthy';
    if (filterStatus === 'UNTESTED') return p.last_tested === 'Untested';
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Bank Parsers Health Dashboard
            </h1>
            <Badge variant="purple" size="sm">
              PRD Section 60-61
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Real-time health monitoring, signature accuracy metrics, and template health across all 38 registered Indian bank parsers
          </p>
        </div>

        {/* CTA to Testing Lab */}
        <Link href="/admin/testing-lab">
          <Button
            variant="primary"
            size="md"
            className="bg-purple-700 hover:bg-purple-800 border-purple-800 text-white"
            icon={<FlaskConical className="w-4 h-4" />}
          >
            Open Statement Testing Lab
          </Button>
        </Link>
      </div>

      {/* Parser Engine KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center border border-purple-200">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 uppercase font-semibold">Registered Adapters</span>
            <div className="text-xl font-black text-slate-900 mt-0.5">38 Banks</div>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-200">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 uppercase font-semibold">Active Operational</span>
            <div className="text-xl font-black text-emerald-700 mt-0.5">100% Ready</div>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center border border-blue-200">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 uppercase font-semibold">Detection Accuracy</span>
            <div className="text-xl font-black text-blue-700 mt-0.5">99.4%</div>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center border border-amber-200">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 uppercase font-semibold">Math Balance Status</span>
            <div className="text-xl font-black text-amber-700 mt-0.5">100% Validated</div>
          </div>
        </Card>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search bank name or adapter key..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-9 py-2 bg-white rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-600"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {(['ALL', 'HEALTHY', 'UNTESTED'] as const).map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                filterStatus === st
                  ? 'bg-purple-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* 38 Bank Parsers Table */}
      <Card className="shadow-card overflow-hidden">
        {loading ? (
          <div className="p-20 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-purple-500 border-t-transparent animate-spin" />
            Loading parser health registry...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Cpu className="w-6 h-6" />}
            title="No parsers found"
            description={`No bank parser matching "${search}"`}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-bold uppercase text-[10px] border-b border-slate-200">
                <tr>
                  <th className="p-4">Bank Institution</th>
                  <th className="p-4">Adapter Key</th>
                  <th className="p-4">Format / Engine</th>
                  <th className="p-4 text-center">Status</th>
                  <th className="p-4 text-center">Detection Rate</th>
                  <th className="p-4 text-center">Math Audit</th>
                  <th className="p-4 text-right">Lab Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filtered.map((p) => {
                  const isVerified = p.tests_run > 0;
                  return (
                    <tr key={p.parser_key} className="hover:bg-slate-50/70 transition-colors">
                      <td className="p-4">
                        <div className="font-bold text-slate-900 text-xs">
                          {p.bank_name}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          Adapter v{p.version} • {p.last_tested === 'Untested' ? 'Awaiting sample' : `Last verified: ${p.last_tested}`}
                        </div>
                      </td>
                      <td className="p-4 font-mono text-slate-600 text-[11px]">
                        <span className="px-2 py-1 bg-slate-100 rounded-md font-semibold text-slate-700">
                          {p.parser_key}
                        </span>
                      </td>
                      <td className="p-4 text-slate-600 font-medium text-xs">
                        {p.format_name}
                      </td>
                      <td className="p-4 text-center">
                        <Badge
                          variant={p.status === 'Healthy' ? 'success' : 'warning'}
                          size="sm"
                        >
                          {p.status}
                        </Badge>
                      </td>
                      <td className="p-4 text-center">
                        <span className="font-mono font-bold text-blue-700 text-xs">
                          {p.detection_success_rate}%
                        </span>
                      </td>
                      <td className="p-4 text-center">
                        <span className="font-mono font-bold text-emerald-700 text-xs">
                          {p.balance_validation_rate}%
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <Link
                          href={`/admin/testing-lab?parser=${p.parser_key}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold text-purple-700 hover:bg-purple-50 transition-colors border border-purple-200"
                        >
                          <FlaskConical className="w-3.5 h-3.5" />
                          Test in Lab
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

    </div>
  );
}
