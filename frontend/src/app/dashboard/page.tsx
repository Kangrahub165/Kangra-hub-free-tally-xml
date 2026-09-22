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
import { Skeleton } from '@/components/ui/Skeleton';

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
    <div className="py-10 bg-slate-50 min-h-screen animate-fadeIn">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Top Header / Welcome Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-navy-900 text-white p-6 sm:p-7 rounded-3xl border border-navy-800 shadow-glow-brand relative overflow-hidden group">
          <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 rounded-full bg-brand-500/20 blur-3xl pointer-events-none transition-transform duration-700 group-hover:scale-110" />
          <div className="relative z-10 space-y-1">
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-black text-white tracking-tight">
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
            <p className="text-xs text-navy-200">
              Daily quota resets automatically at midnight (Timezone:{' '}
              <span className="font-semibold text-white">{usage?.timezone || 'Asia/Kolkata'}</span>)
            </p>
          </div>

          <div className="relative z-10 flex flex-wrap items-center gap-3">
            <Link href="/unlock-pdf">
              <Button
                variant="dark"
                size="md"
                className="bg-navy-800/80 hover:bg-navy-700 text-white font-semibold"
                icon={<Lock className="w-4 h-4 text-amber-400" />}
              >
                Unlock Protected PDF
              </Button>
            </Link>
            <Link href="/convert">
              <Button variant="primary" size="md" className="shadow-glow-brand" iconRight={<ArrowRight className="w-4 h-4" />}>
                Convert Bank Statement
              </Button>
            </Link>
          </div>
        </div>

        {/* 4 Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5 animate-slideUp" style={{ animationDelay: '100ms', animationFillMode: 'both' }}>
          
          {/* Card 1: Today's Usage */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 relative overflow-hidden group bg-gradient-to-br from-white to-slate-50/50">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Today's Usage
                </span>
                <div className="mt-2 text-2xl font-black text-slate-900 tabular-nums">
                  {usage?.is_unlimited ? 'Unlimited' : `${usedPages} / ${dailyLimit}`}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <Layers className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100">
              {!usage?.is_unlimited && (
                <div className="w-full bg-slate-100 rounded-full h-2 mb-2 overflow-hidden shadow-inner">
                  <div
                    className="bg-brand-500 h-full rounded-full transition-all duration-1000 ease-out relative overflow-hidden"
                    style={{ width: `${usagePercent}%` }}
                  >
                    <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full animate-shimmer" />
                  </div>
                </div>
              )}
              <span className="text-[11px] text-slate-500">
                {usage?.is_unlimited ? 'Exempt from page constraints' : `${remainingPages} pages remaining today`}
              </span>
            </div>
          </Card>

          {/* Card 2: Remaining Pages */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 bg-gradient-to-br from-white to-slate-50/50 group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Remaining Allowance
                </span>
                <div className="mt-2 text-2xl font-black text-emerald-600 tabular-nums flex items-baseline flex-wrap gap-1">
                  <span>{usage?.is_unlimited ? '∞' : remainingPages}</span>
                  {usage?.additional_page_balance && usage.additional_page_balance > 0 ? (
                    <span className="text-xs text-accent-600 font-bold font-sans">
                      (+{usage.additional_page_balance} paid)
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <Sparkles className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
              {usage?.is_unlimited ? 'Bypasses standard quota' : 'Pages available to convert today'}
            </div>
          </Card>

          {/* Card 3: Account Status */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 bg-gradient-to-br from-white to-slate-50/50 group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Account Status
                </span>
                <div className="mt-2 text-lg font-bold text-slate-900 leading-tight">
                  {usage?.account_status || 'Free Account'}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center border border-purple-100/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
              {usage?.is_unlimited ? 'Special Access Approved' : 'Free standard membership'}
            </div>
          </Card>

          {/* Card 4: Total Conversions */}
          <Card className="p-5 flex flex-col justify-between shadow-card hover:shadow-card-hover transition-all duration-300 bg-gradient-to-br from-white to-slate-50/50 group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Total Conversions
                </span>
                <div className="mt-2 text-2xl font-black text-slate-900 tabular-nums">
                  {totalConversions}
                </div>
              </div>
              <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center border border-slate-200/70 shadow-xs group-hover:scale-110 transition-transform duration-300">
                <FileText className="w-5 h-5" />
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
        <Card className="shadow-elevated overflow-hidden border-slate-200/80 animate-slideUp" style={{ animationDelay: '200ms', animationFillMode: 'both' }}>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-slate-50/50 border-b border-slate-100">
            <div>
              <CardTitle className="text-lg">Recent Statement Conversions</CardTitle>
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
            <div className="p-8 space-y-4">
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-10 w-full rounded-xl" />
              <Skeleton className="h-10 w-full rounded-xl" />
            </div>
          ) : conversions.length === 0 ? (
            <EmptyState
              icon={<FileText className="w-8 h-8 text-brand-400" />}
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
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-slate-50/50">
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
                    <TableRow key={job.id} className="hover:bg-slate-50/80 transition-colors group">
                      <TableCell className="font-mono text-slate-500 text-[11px] group-hover:text-slate-700 transition-colors">
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
                      <TableCell align="center" className="font-mono font-medium text-slate-700">
                        {job.page_count}
                      </TableCell>
                      <TableCell align="center" className="font-mono font-medium text-slate-700">
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
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-brand-600 hover:text-brand-700 hover:bg-brand-50 transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Download
                        </a>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </Card>

      </div>
    </div>
  );
}
