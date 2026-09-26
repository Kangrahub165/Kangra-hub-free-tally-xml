'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FileText, Download, CheckCircle2, AlertTriangle, XCircle, ArrowRight, Search, X } from 'lucide-react';
import { getUserConversions, ConversionJobSummary } from '@/lib/api';
import { useAuth } from '@/components/auth/AuthProvider';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';

export default function HistoryPage() {
  const [conversions, setConversions] = useState<ConversionJobSummary[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.push('/login?redirect=/history');
      return;
    }
    getUserConversions()
      .then((data) => {
        setConversions(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [isLoading, isAuthenticated, router]);

  const filtered = conversions.filter((job) => {
    const matchesSearch =
      search === '' ||
      job.bank_name.toLowerCase().includes(search.toLowerCase()) ||
      job.file_name.toLowerCase().includes(search.toLowerCase());

    const matchesStatus =
      statusFilter === 'ALL' || job.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  return (
    <div className="py-12 bg-slate-50 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
          <div className="space-y-1">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Conversion History
            </h1>
            <p className="text-xs text-slate-500">
              Audit log of all statements converted with instant Tally XML download access
            </p>
          </div>

          <Link href="/convert">
            <Button variant="primary" size="md" iconRight={<ArrowRight className="w-4 h-4" />}>
              Start New Conversion
            </Button>
          </Link>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by bank or file name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-9 py-2 bg-white rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
                aria-label="Clear search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500 font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 bg-white focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="COMPLETED">Completed</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
        </div>

        {/* History Table Card */}
        <Card className="shadow-card overflow-hidden">
          {loading ? (
            <div className="p-20 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
              <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
              Loading conversion records...
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<FileText className="w-6 h-6" />}
              title={search ? 'No matching conversions' : 'No conversion history found'}
              description={
                search
                  ? `No statements matched "${search}". Try resetting your filter.`
                  : 'Any statements you upload and convert will appear here with instant XML download links.'
              }
              action={
                search ? (
                  <Button variant="outline" size="sm" onClick={() => { setSearch(''); setStatusFilter('ALL'); }}>
                    Reset Filters
                  </Button>
                ) : (
                  <Link href="/convert">
                    <Button variant="primary" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                      Convert First Statement
                    </Button>
                  </Link>
                )
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Date & Time</TableHead>
                  <TableHead>Bank</TableHead>
                  <TableHead>File Name</TableHead>
                  <TableHead align="center">Pages</TableHead>
                  <TableHead align="center">Transactions</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead align="right">XML Download</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {filtered.map((job) => (
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
                        Download XML
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
