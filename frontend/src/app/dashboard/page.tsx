'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  ArrowRight, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  Sparkles, 
  Download,
  AlertTriangle,
  Layers,
  History,
  Clock,
  ChevronRight,
  Lock
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { getUserUsage, getUserConversions, UsageInfo, ConversionJobSummary, getAuthToken } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';

export default function UserDashboardPage() {
  const router = useRouter();
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [conversions, setConversions] = useState<ConversionJobSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      router.push('/login?redirect=/dashboard');
      return;
    }

    Promise.all([getUserUsage(), getUserConversions()])
      .then(([u, c]) => {
        setUsage(u);
        setConversions(c);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [router]);

  const totalConversions = conversions.length;
  const successfulConversions = conversions.filter((c) => c.status === 'COMPLETED').length;
  const needsReviewConversions = conversions.filter((c) => c.status === 'NEEDS_REVIEW').length;
  const failedConversions = conversions.filter((c) => c.status === 'FAILED').length;

  const usedPages = usage?.pages_used_today || 0;
  const dailyLimit = usage?.daily_limit || 50;
  const remainingPages = usage?.is_unlimited ? 999999 : (usage?.pages_remaining_today ?? Math.max(0, dailyLimit - usedPages));
  const usagePercent = usage?.is_unlimited ? 100 : Math.min(100, Math.round((usedPages / dailyLimit) * 100));

  return (
    <div className="py-10 bg-slate-50 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Top Header / Welcome Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Accounting Workspace
              </h1>
              <Badge variant={usage?.is_unlimited ? 'purple' : usage?.quota_mode === 'CUSTOM' ? 'purple' : 'success'} size="sm">
                {usage?.is_unlimited
                  ? 'Unlimited Tier'
                  : usage?.quota_mode === 'CUSTOM'
                  ? `Custom Tier (${dailyLimit} Pgs/Day)`
                  : `Free Daily Tier (${dailyLimit} Pgs/Day)`}
              </Badge>
            </div>
            <p className="text-xs text-slate-500">
              Daily quota resets automatically at midnight (Timezone:{' '}
              <span className="font-semibold text-slate-700">{usage?.timezone || 'Asia/Kolkata'}</span>)
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link href="/unlock-pdf">
              <Button variant="outline" size="md" icon={<Lock className="w-4 h-4 text-amber-600" />}>
                Unlock Protected PDF
              </Button>
            </Link>
            <Link href="/convert">
              <Button variant="primary" size="md" iconRight={<ArrowRight className="w-4 h-4" />}>
                Convert Bank Statement
              </Button>
            </Link>
          </div>
        </div>

        {/* 4 Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
          
          {/* Card 1: Today's Usage */}
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Today's Usage
                </span>
                <div className="mt-2 text-2xl font-black text-slate-900 tabular-nums">
                  {usage?.is_unlimited ? 'Unlimited' : `${usedPages} / ${dailyLimit}`}
                </div>
              </div>
              <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100/70 shadow-xs">
                <Layers className="w-4 h-4" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100">
              {!usage?.is_unlimited && (
                <div className="w-full bg-slate-100 rounded-full h-1.5 mb-2 overflow-hidden">
                  <div
                    className="bg-brand-600 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${usagePercent}%` }}
                  />
                </div>
              )}
              <span className="text-[11px] text-slate-500">
                {usage?.is_unlimited ? 'Exempt from page constraints' : `${remainingPages} pages remaining today`}
              </span>
            </div>
          </Card>

          {/* Card 2: Remaining Pages */}
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Remaining Allowance
                </span>
                <div className="mt-2 text-2xl font-black text-emerald-600 tabular-nums flex items-baseline flex-wrap gap-1">
                  <span>{usage?.is_unlimited ? '∞' : remainingPages}</span>
                  {usage?.additional_page_balance && usage.additional_page_balance > 0 ? (
                    <span className="text-xs text-blue-600 font-bold font-sans">
                      (+{usage.additional_page_balance} paid)
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100/70 shadow-xs">
                <Sparkles className="w-4 h-4" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
              {usage?.is_unlimited ? 'Bypasses standard quota' : 'Pages available to convert today'}
            </div>
          </Card>

          {/* Card 3: Account Status */}
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Account Status
                </span>
                <div className="mt-2 text-lg font-bold text-slate-900 leading-tight">
                  {usage?.account_status || 'Free Account'}
                </div>
              </div>
              <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center border border-purple-100/70 shadow-xs">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
              {usage?.is_unlimited ? 'Special Access Approved' : 'Free standard membership'}
            </div>
          </Card>

          {/* Card 4: Total Conversions */}
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Total Conversions
                </span>
                <div className="mt-2 text-2xl font-black text-slate-900 tabular-nums">
                  {totalConversions}
                </div>
              </div>
              <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center border border-slate-200/70 shadow-xs">
                <FileText className="w-4 h-4" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] flex flex-wrap items-center gap-2">
              <span className="text-emerald-600 font-semibold">{successfulConversions} Successful</span>
              {needsReviewConversions > 0 && (
                <>
                  <span className="text-slate-300">•</span>
                  <span className="text-amber-600 font-semibold">{needsReviewConversions} Needs Review</span>
                </>
              )}
              {failedConversions > 0 && (
                <>
                  <span className="text-slate-300">•</span>
                  <span className="text-rose-600 font-semibold">{failedConversions} Failed</span>
                </>
              )}
            </div>
          </Card>

        </div>

        {/* Recent Conversions Table Card */}
        <Card className="shadow-card overflow-hidden">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <CardTitle>Recent Statement Conversions</CardTitle>
              <CardDescription>
                Review and download your recent Tally XML statements
              </CardDescription>
            </div>
            <Link href="/history">
              <Button variant="ghost" size="sm" iconRight={<ChevronRight className="w-3.5 h-3.5" />}>
                View Complete History
              </Button>
            </Link>
          </CardHeader>

          {loading ? (
            <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
              <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
              Loading conversion records...
            </div>
          ) : conversions.length === 0 ? (
            <EmptyState
              icon={<FileText className="w-6 h-6" />}
              title="No statements converted yet"
              description="Upload your first bank statement PDF to extract transactions and download balanced Tally XML."
              action={
                <Link href="/convert">
                  <Button variant="primary" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                    Convert First Statement
                  </Button>
                </Link>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Date</TableHead>
                  <TableHead>Bank</TableHead>
                  <TableHead>File Name</TableHead>
                  <TableHead align="center">Pages</TableHead>
                  <TableHead align="center">Transactions</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead align="right">Tally XML</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {conversions.slice(0, 5).map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-mono text-slate-600 text-[11px]">
                      {new Date(job.created_at).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </TableCell>
                    <TableCell className="font-bold text-slate-900">
                      {job.bank_name}
                    </TableCell>
                    <TableCell className="text-slate-600 truncate max-w-xs font-mono text-[11px]">
                      {job.file_name}
                    </TableCell>
                    <TableCell align="center" className="font-mono font-medium">
                      {job.page_count}
                    </TableCell>
                    <TableCell align="center" className="font-mono font-medium">
                      {job.transaction_count}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          job.status === 'COMPLETED'
                            ? 'success'
                            : job.status === 'PARTIALLY_COMPLETED' || job.status === 'NEEDS_REVIEW'
                            ? 'warning'
                            : 'danger'
                        }
                        size="sm"
                      >
                        {job.status === 'PARTIALLY_COMPLETED' ? 'PARTIAL' : job.status}
                      </Badge>
                    </TableCell>
                    <TableCell align="right">
                      <a
                        href={`/api/conversions/${job.id}/download`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-brand-600 hover:bg-brand-50 transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </a>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>

      </div>
    </div>
  );
}
