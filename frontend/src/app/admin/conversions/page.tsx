'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { getAdminConversions, getConversionDiagnostics } from '@/lib/api';
import { CheckCircle2, AlertTriangle, XCircle, Download, Search, FileSpreadsheet, X, Eye, ShieldCheck, ArrowUpRight, ArrowDownLeft } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';

function AdminConversionsContent() {
  const searchParams = useSearchParams();
  const urlJobId = searchParams.get('jobId') || searchParams.get('id') || '';

  const [conversions, setConversions] = useState<any[]>([]);
  const [filterBank, setFilterBank] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'COMPLETED' | 'NEEDS_REVIEW' | 'AMBIGUOUS' | 'FAILED'>('ALL');
  const [loading, setLoading] = useState(true);

  // Deep Diagnostic Modal
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [diagData, setDiagData] = useState<any>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [isDiagOpen, setIsDiagOpen] = useState(false);

  useEffect(() => {
    getAdminConversions()
      .then((data) => {
        setConversions(data);
        setLoading(false);
        if (urlJobId) {
          openDiagnostics(urlJobId);
        }
      })
      .catch(() => setLoading(false));
  }, [urlJobId]);

  const openDiagnostics = async (jobId: string) => {
    setSelectedJobId(jobId);
    setIsDiagOpen(true);
    setDiagLoading(true);
    try {
      const data = await getConversionDiagnostics(jobId);
      setDiagData(data);
    } catch {
      alert('Failed to load conversion diagnostics');
    } finally {
      setDiagLoading(false);
    }
  };

  const filtered = conversions.filter((c) => {
    const matchesBank = filterBank ? c.bank_name.toLowerCase().includes(filterBank.toLowerCase()) : true;
    if (!matchesBank) return false;
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'COMPLETED') return c.status === 'COMPLETED';
    if (statusFilter === 'NEEDS_REVIEW') return c.status === 'NEEDS_REVIEW';
    if (statusFilter === 'AMBIGUOUS') return c.status === 'AMBIGUOUS_BANK' || c.is_ambiguous;
    if (statusFilter === 'FAILED') return c.status === 'FAILED';
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Conversions Audit Stream & Deep Diagnostics
            </h1>
            <Badge variant="purple" size="sm">
              PRD Section 58
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Real-time conversion monitor, mathematical balance verification, and diagnostic inspection engine
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Filter by bank name..."
            value={filterBank}
            onChange={(e) => setFilterBank(e.target.value)}
            className="w-full pl-10 pr-9 py-2 bg-white rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
          />
          {filterBank && (
            <button
              onClick={() => setFilterBank('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
              aria-label="Clear filter"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {(['ALL', 'COMPLETED', 'NEEDS_REVIEW', 'AMBIGUOUS', 'FAILED'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setStatusFilter(tab)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              statusFilter === tab
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            {tab.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Conversions Table Card */}
      <Card className="shadow-card overflow-hidden">
        {loading ? (
          <div className="p-20 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading conversion monitor stream...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<FileSpreadsheet className="w-6 h-6" />}
            title="No conversions recorded"
            description={filterBank ? `No conversions found for bank "${filterBank}".` : 'No statement conversions match the active filter.'}
          />
        ) : (
          <Table>
            <TableHeader>
              <tr>
                <TableHead>Job / Timestamp</TableHead>
                <TableHead>File & Bank</TableHead>
                <TableHead align="center">Scope</TableHead>
                <TableHead align="center">Confidence Tier</TableHead>
                <TableHead align="center">Math Audit</TableHead>
                <TableHead>Status</TableHead>
                <TableHead align="right">Diagnostic Actions</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {filtered.map((j) => (
                <TableRow key={j.id}>
                  <TableCell>
                    <div className="font-mono text-slate-800 font-bold text-[11px]">
                      {j.id}
                    </div>
                    <div className="text-slate-400 font-mono text-[10px] mt-0.5">
                      {new Date(j.created_at).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-bold text-slate-900 text-xs">
                      {j.bank_name}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono truncate max-w-[200px]">
                      {j.file_name}
                    </div>
                  </TableCell>
                  <TableCell align="center">
                    <div className="font-mono font-bold text-slate-800 text-xs">
                      {j.page_count} pgs
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {j.transaction_count} tx rows
                    </div>
                  </TableCell>
                  <TableCell align="center">
                    <Badge
                      variant={j.confidence_score >= 85 ? 'success' : j.confidence_score >= 70 ? 'primary' : 'warning'}
                      size="sm"
                    >
                      {j.confidence_tier || (j.confidence_score >= 85 ? 'HIGH' : 'MEDIUM')} ({j.confidence_score}%)
                    </Badge>
                  </TableCell>
                  <TableCell align="center">
                    <span className={`font-mono font-bold text-[11px] px-2 py-0.5 rounded ${
                      j.balance_status === 'VALID' 
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' 
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}>
                      {j.balance_status === 'VALID' ? '100% RECONCILED' : 'DISCREPANCY'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        j.status === 'COMPLETED'
                          ? 'success'
                          : j.status === 'NEEDS_REVIEW'
                          ? 'warning'
                          : j.status === 'AMBIGUOUS_BANK'
                          ? 'warning'
                          : 'danger'
                      }
                      size="sm"
                    >
                      {j.status}
                    </Badge>
                  </TableCell>
                  <TableCell align="right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openDiagnostics(j.id)}
                        icon={<Eye className="w-3.5 h-3.5 text-slate-600" />}
                      >
                        Inspect
                      </Button>
                      <a
                        href={`/api/conversions/${j.id}/download`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold text-brand-600 hover:bg-brand-50 transition-colors border border-transparent hover:border-brand-200"
                        title="Download double-entry Tally XML"
                      >
                        <Download className="w-3.5 h-3.5" />
                        XML
                      </a>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {/* Deep Diagnostic Modal (PRD Section 58) */}
      <Modal
        isOpen={isDiagOpen}
        onClose={() => {
          setIsDiagOpen(false);
          setSelectedJobId(null);
          setDiagData(null);
        }}
        title="Conversion Deep Diagnostics & Audit Inspector"
        size="lg"
      >
        {diagLoading || !diagData ? (
          <div className="p-12 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Analyzing extraction pipeline telemetry...
          </div>
        ) : (
          <div className="space-y-5 text-xs">
            {/* Top Summary Banner */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-[11px] font-mono text-slate-400">Job ID: {diagData.job_id}</div>
                <div className="font-extrabold text-base text-slate-900 mt-0.5">{diagData.bank_name}</div>
                <div className="text-[11px] text-slate-500 font-mono">{diagData.file_name}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={diagData.confidence_tier === 'HIGH' ? 'success' : 'warning'} size="md">
                  {diagData.confidence_tier} ({diagData.confidence_score}%)
                </Badge>
                <Badge variant={diagData.balance_status === 'VALID' ? 'success' : 'danger'} size="md">
                  {diagData.balance_status === 'VALID' ? '100% RECONCILED' : 'DISCREPANCY DETECTED'}
                </Badge>
              </div>
            </div>

            {/* Bank Detection Engine Telemetry */}
            <div className="p-4 rounded-2xl bg-brand-50/40 border border-brand-100 space-y-2.5">
              <span className="font-bold text-slate-800 uppercase text-[10px] tracking-wider">
                Bank Detection Signatures & Intelligence:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <span className="text-[11px] text-slate-500 block">Assigned Parser Adapter:</span>
                  <code className="font-mono font-bold text-slate-900 text-xs">{diagData.parser_name || 'auto_detected'}</code>
                </div>
                <div>
                  <span className="text-[11px] text-slate-500 block">Branch IFSC Code Detected:</span>
                  <code className="font-mono font-bold text-brand-800 text-xs">{diagData.detected_ifsc || 'None detected'}</code>
                </div>
              </div>

              {diagData.detection_reasons && diagData.detection_reasons.length > 0 && (
                <div className="pt-2">
                  <span className="text-[11px] text-slate-500 block mb-1">Matched Header Markers:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {diagData.detection_reasons.map((r: string, idx: number) => (
                      <span key={idx} className="px-2 py-0.5 bg-white text-brand-700 border border-brand-200 rounded text-[11px] font-mono shadow-xs">
                        ✓ {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Mathematical Running Balance Audit */}
            <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-800 uppercase text-[10px] tracking-wider">
                  Mathematical Balance Equation:
                </span>
                <span className="text-[11px] font-mono text-emerald-700 font-bold">
                  Opening + Credits - Debits = Closing
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Opening Balance</span>
                  <div className="font-bold font-mono text-slate-900 text-xs mt-0.5">
                    ₹{diagData.opening_balance || '0.00'}
                  </div>
                </div>
                <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-100">
                  <span className="text-[10px] text-emerald-600 uppercase font-semibold">Total Credits (+)</span>
                  <div className="font-bold font-mono text-emerald-700 text-xs mt-0.5">
                    +₹{Number(diagData.total_credit || 0).toFixed(2)}
                  </div>
                </div>
                <div className="p-3 bg-rose-50/60 rounded-xl border border-rose-100">
                  <span className="text-[10px] text-rose-600 uppercase font-semibold">Total Debits (-)</span>
                  <div className="font-bold font-mono text-rose-700 text-xs mt-0.5">
                    -₹{Number(diagData.total_debit || 0).toFixed(2)}
                  </div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Closing Balance</span>
                  <div className="font-bold font-mono text-slate-900 text-xs mt-0.5">
                    ₹{diagData.closing_balance || '0.00'}
                  </div>
                </div>
              </div>
            </div>

            {/* Sample Extracted Transaction Rows */}
            {diagData.sample_transactions && diagData.sample_transactions.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-700 uppercase text-[10px]">
                    First {diagData.sample_transactions.length} Sample Transactions (Double-Entry Validated):
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    Total {diagData.transaction_count} rows
                  </span>
                </div>
                <div className="overflow-x-auto border border-slate-200 rounded-xl max-h-48">
                  <table className="w-full text-left text-[11px]">
                    <thead className="bg-slate-100 text-slate-600 font-bold uppercase text-[9px] sticky top-0">
                      <tr>
                        <th className="p-2">Date</th>
                        <th className="p-2">Narration</th>
                        <th className="p-2 text-right">Debit</th>
                        <th className="p-2 text-right">Credit</th>
                        <th className="p-2 text-center">Voucher</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {diagData.sample_transactions.map((t: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="p-2 font-mono text-slate-600">{t.date}</td>
                          <td className="p-2 truncate max-w-[240px] text-slate-800">{t.narration}</td>
                          <td className="p-2 text-right font-mono text-rose-600 font-bold">{t.debit ? `₹${t.debit}` : '—'}</td>
                          <td className="p-2 text-right font-mono text-emerald-600 font-bold">{t.credit ? `₹${t.credit}` : '—'}</td>
                          <td className="p-2 text-center">
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">
                              {t.voucher_type || 'Payment'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Modal Bottom Actions */}
            <div className="pt-3 border-t border-slate-200 flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDiagOpen(false)}
              >
                Close Inspector
              </Button>
              <a
                href={`/api/conversions/${diagData.job_id}/download`}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-brand-600 hover:bg-brand-700 shadow-sm"
              >
                <Download className="w-4 h-4" />
                Download Tally XML
              </a>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
}

export default function AdminConversionsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-400">Loading conversions audit stream...</div>}>
      <AdminConversionsContent />
    </Suspense>
  );
}
