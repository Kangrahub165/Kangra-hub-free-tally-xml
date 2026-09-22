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
      <div className="flex flex-wrap items-center gap-2 bg-white p-2 rounded-2xl border border-slate-200 shadow-sm">
        {(['ALL', 'COMPLETED', 'NEEDS_REVIEW', 'AMBIGUOUS', 'FAILED'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setStatusFilter(tab)}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all relative overflow-hidden ${
              statusFilter === tab
                ? 'bg-navy-900 text-white shadow-md'
                : 'bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            {statusFilter === tab && <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-shimmer" />}
            {tab.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Conversions Table Card */}
      <Card className="shadow-card overflow-hidden border-t-4 border-t-brand-500 rounded-3xl">
        {loading ? (
          <div className="p-20 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-3">
            <div className="w-6 h-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading conversion monitor stream...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<FileSpreadsheet className="w-8 h-8 text-brand-300" />}
            title="No conversions recorded"
            description={filterBank ? `No conversions found for bank "${filterBank}".` : 'No statement conversions match the active filter.'}
          />
        ) : (
          <div className="overflow-x-auto">\n<Table>
            <TableHeader>
              <tr className="bg-slate-50/50">
                <TableHead className="font-bold text-slate-700">Job / Timestamp</TableHead>
                <TableHead className="font-bold text-slate-700">File & Bank</TableHead>
                <TableHead align="center" className="font-bold text-slate-700">Scope</TableHead>
                <TableHead align="center" className="font-bold text-slate-700">Confidence</TableHead>
                <TableHead align="center" className="font-bold text-slate-700">Math Audit</TableHead>
                <TableHead className="font-bold text-slate-700">Status</TableHead>
                <TableHead align="right" className="font-bold text-slate-700">Actions</TableHead>
              </tr>
            </TableHeader>
            <TableBody className="divide-y divide-slate-100/80">
              {filtered.map((j) => (
                <TableRow key={j.id} className="hover:bg-slate-50/80 transition-colors">
                  <TableCell>
                    <div className="font-mono text-slate-800 font-bold text-xs uppercase tracking-wider">
                      {j.id.substring(0, 12)}...
                    </div>
                    <div className="text-slate-500 font-mono text-[10px] mt-1 flex items-center gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-slate-300"></div>
                      {new Date(j.created_at).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-black text-navy-900 text-xs">
                      {j.bank_name}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono truncate max-w-[200px] mt-0.5" title={j.file_name}>
                      {j.file_name}
                    </div>
                  </TableCell>
                  <TableCell align="center">
                    <div className="inline-flex flex-col items-center justify-center bg-slate-50 border border-slate-200/60 px-2 py-1 rounded-xl">
                      <div className="font-mono font-black text-navy-900 text-xs">
                        {j.page_count} pgs
                      </div>
                      <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mt-0.5">
                        {j.transaction_count} txs
                      </div>
                    </div>
                  </TableCell>
                  <TableCell align="center">
                    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10px] font-black uppercase tracking-wider ${
                      j.confidence_score >= 85 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                      j.confidence_score >= 70 ? 'bg-brand-50 text-brand-700 border-brand-200' :
                      'bg-amber-50 text-amber-700 border-amber-200'
                    }`}>
                      {j.confidence_score >= 85 && <ShieldCheck className="w-3 h-3" />}
                      {j.confidence_tier || (j.confidence_score >= 85 ? 'HIGH' : 'MEDIUM')} ({j.confidence_score}%)
                    </div>
                  </TableCell>
                  <TableCell align="center">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider shadow-sm ${
                      j.balance_status === 'VALID' 
                        ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-white shadow-emerald-200' 
                        : 'bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-amber-200'
                    }`}>
                      {j.balance_status === 'VALID' ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                      {j.balance_status === 'VALID' ? '100% RECON' : 'DISCREPANCY'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold border ${
                        j.status === 'COMPLETED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : j.status === 'NEEDS_REVIEW' || j.status === 'AMBIGUOUS_BANK'
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-rose-50 text-rose-700 border-rose-200'
                      }`}>
                      {j.status}
                    </span>
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
          </Table>\n</div>
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
        className="max-h-[90vh] overflow-y-auto"
      >
        {diagLoading || !diagData ? (
          <div className="p-16 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-3">
            <div className="w-8 h-8 rounded-full border-4 border-brand-500 border-t-transparent animate-spin" />
            Analyzing extraction pipeline telemetry...
          </div>
        ) : (
          <div className="space-y-6 text-xs animate-fadeIn">
            {/* Top Summary Banner */}
            <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-50 to-white border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider font-semibold">Job ID: {diagData.job_id}</div>
                <div className="font-black text-xl text-navy-900 mt-1">{diagData.bank_name}</div>
                <div className="text-xs text-slate-500 font-mono mt-0.5">{diagData.file_name}</div>
              </div>
              <div className="flex flex-col sm:flex-row items-center gap-2">
                <span className={`px-3 py-1 rounded-full border text-[11px] font-black uppercase tracking-wider ${
                  diagData.confidence_tier === 'HIGH' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}>
                  {diagData.confidence_tier} ({diagData.confidence_score}%)
                </span>
                <span className={`px-3 py-1 rounded-full border text-[11px] font-black uppercase tracking-wider ${
                  diagData.balance_status === 'VALID' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}>
                  {diagData.balance_status === 'VALID' ? '100% RECONCILED' : 'DISCREPANCY DETECTED'}
                </span>
              </div>
            </div>

            {/* Bank Detection Engine Telemetry */}
            <div className="p-5 rounded-2xl bg-brand-50/50 border border-brand-100 shadow-sm space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <ShieldCheck className="w-4 h-4 text-brand-600" />
                <span className="font-bold text-navy-900 uppercase text-xs tracking-wider">
                  Bank Detection Signatures & Intelligence
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-white p-3 rounded-xl border border-brand-100/50">
                  <span className="text-[10px] text-slate-500 block uppercase tracking-wider font-semibold">Assigned Parser Adapter</span>
                  <code className="font-mono font-black text-brand-700 text-sm mt-0.5 block">{diagData.parser_name || 'auto_detected'}</code>
                </div>
                <div className="bg-white p-3 rounded-xl border border-brand-100/50">
                  <span className="text-[10px] text-slate-500 block uppercase tracking-wider font-semibold">Branch IFSC Code Detected</span>
                  <code className="font-mono font-black text-brand-700 text-sm mt-0.5 block">{diagData.detected_ifsc || 'None detected'}</code>
                </div>
              </div>

              {diagData.detection_reasons && diagData.detection_reasons.length > 0 && (
                <div className="pt-2">
                  <span className="text-[10px] text-slate-500 block mb-2 uppercase tracking-wider font-semibold">Matched Header Markers</span>
                  <div className="flex flex-wrap gap-2">
                    {diagData.detection_reasons.map((r: string, idx: number) => (
                      <span key={idx} className="px-2.5 py-1 bg-white text-brand-700 border border-brand-200 rounded-lg text-[10px] font-mono font-bold shadow-xs">
                        ✓ {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Mathematical Running Balance Audit */}
            <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-card space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span className="font-bold text-navy-900 uppercase text-xs tracking-wider">
                    Mathematical Balance Equation
                  </span>
                </div>
                <span className="text-[11px] font-mono text-emerald-700 font-black bg-emerald-50 px-2 py-1 rounded border border-emerald-100">
                  Opening + Credits - Debits = Closing
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 shadow-inner">
                  <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Opening Balance</span>
                  <div className="font-black font-mono text-navy-900 text-sm mt-1">
                    ₹{diagData.opening_balance || '0.00'}
                  </div>
                </div>
                <div className="p-3.5 bg-emerald-50/60 rounded-xl border border-emerald-200/60 shadow-inner">
                  <span className="text-[10px] text-emerald-600 uppercase font-bold tracking-wider">Total Credits (+)</span>
                  <div className="font-black font-mono text-emerald-700 text-sm mt-1">
                    +₹{Number(diagData.total_credit || 0).toFixed(2)}
                  </div>
                </div>
                <div className="p-3.5 bg-rose-50/60 rounded-xl border border-rose-200/60 shadow-inner">
                  <span className="text-[10px] text-rose-600 uppercase font-bold tracking-wider">Total Debits (-)</span>
                  <div className="font-black font-mono text-rose-700 text-sm mt-1">
                    -₹{Number(diagData.total_debit || 0).toFixed(2)}
                  </div>
                </div>
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 shadow-inner">
                  <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Closing Balance</span>
                  <div className="font-black font-mono text-navy-900 text-sm mt-1">
                    ₹{diagData.closing_balance || '0.00'}
                  </div>
                </div>
              </div>
            </div>

            {/* Sample Extracted Transaction Rows */}
            {diagData.sample_transactions && diagData.sample_transactions.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-navy-900 uppercase text-[10px] tracking-wider">
                    First {diagData.sample_transactions.length} Sample Transactions (Double-Entry Validated)
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono font-semibold bg-slate-100 px-2 py-0.5 rounded">
                    Total {diagData.transaction_count} rows
                  </span>
                </div>
                <div className="overflow-x-auto border border-slate-200 rounded-xl max-h-60 shadow-inner">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-100 text-slate-600 font-bold uppercase text-[9px] sticky top-0 tracking-wider">
                      <tr>
                        <th className="p-3 border-b border-slate-200">Date</th>
                        <th className="p-3 border-b border-slate-200">Narration</th>
                        <th className="p-3 text-right border-b border-slate-200">Debit</th>
                        <th className="p-3 text-right border-b border-slate-200">Credit</th>
                        <th className="p-3 text-center border-b border-slate-200">Voucher</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {diagData.sample_transactions.map((t: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                          <td className="p-3 font-mono text-slate-600 font-medium whitespace-nowrap">{t.date}</td>
                          <td className="p-3 truncate max-w-[240px] text-slate-800 font-medium" title={t.narration}>{t.narration}</td>
                          <td className="p-3 text-right font-mono text-rose-600 font-bold">{t.debit ? `₹${t.debit}` : '—'}</td>
                          <td className="p-3 text-right font-mono text-emerald-600 font-bold">{t.credit ? `₹${t.credit}` : '—'}</td>
                          <td className="p-3 text-center">
                            <span className="px-2 py-1 rounded-md text-[10px] font-black bg-slate-100 text-slate-700 tracking-wide">
                              {t.voucher_type || 'PAYMENT'}
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
            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <Button
                variant="outline"
                size="md"
                onClick={() => setIsDiagOpen(false)}
                className="hover:bg-slate-100"
              >
                Close Inspector
              </Button>
              <a
                href={`/api/conversions/${diagData.job_id}/download`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 shadow-glow-brand transition-all hover:scale-105"
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
