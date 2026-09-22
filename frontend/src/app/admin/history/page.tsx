'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { getAdminConversionHistory, getConversionDiagnostics } from '@/lib/api';
import { 
  FileSpreadsheet, 
  Download, 
  Search, 
  X, 
  Eye, 
  Sparkles, 
  Clock, 
  CheckCircle2, 
  AlertTriangle,
  ArrowRight
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';

export default function AdminConversionHistoryPage() {
  const [history, setHistory] = useState<any[]>([]);
  const [filterBank, setFilterBank] = useState('');
  const [loading, setLoading] = useState(true);

  // Diagnostic Modal
  const [diagData, setDiagData] = useState<any>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [isDiagOpen, setIsDiagOpen] = useState(false);

  useEffect(() => {
    getAdminConversionHistory()
      .then((data) => {
        setHistory(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const openDiagnostics = async (jobId: string) => {
    setIsDiagOpen(true);
    setDiagLoading(true);
    try {
      const data = await getConversionDiagnostics(jobId);
      setDiagData(data);
    } catch {
      alert('Failed to load diagnostics');
    } finally {
      setDiagLoading(false);
    }
  };

  const filtered = history.filter((h) =>
    filterBank ? h.bank_name.toLowerCase().includes(filterBank.toLowerCase()) : true
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Admin Conversion History
            </h1>
            <Badge variant="purple" size="sm">
              ADMIN / QUOTA EXEMPT
            </Badge>
            <Badge variant="success" size="sm">
              PRD Section 10
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Audit history of statements converted under administrator privileges without consuming daily quotas
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Filter by bank..."
              value={filterBank}
              onChange={(e) => setFilterBank(e.target.value)}
              className="w-full pl-10 pr-8 py-2 bg-white rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
            />
            {filterBank && (
              <button
                onClick={() => setFilterBank('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <Link href="/admin/convert">
            <Button
              variant="primary"
              size="md"
              className="bg-brand-600 hover:bg-brand-700"
              icon={<Sparkles className="w-4 h-4" />}
            >
              Convert New Statement
            </Button>
          </Link>
        </div>
      </div>

      {/* History Table */}
      <Card className="shadow-card overflow-hidden">
        {loading ? (
          <div className="p-20 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading admin conversion history...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<FileSpreadsheet className="w-6 h-6" />}
            title="No admin conversions recorded yet"
            description={filterBank ? `No conversions match bank "${filterBank}".` : 'Upload statements via the Admin Converter to populate this history log.'}
          />
        ) : (
          <div className="overflow-x-auto">\n<Table>
            <TableHeader>
              <tr>
                <TableHead>Date / Job</TableHead>
                <TableHead>Statement & Bank</TableHead>
                <TableHead align="center">Scope</TableHead>
                <TableHead>Parser Adapter</TableHead>
                <TableHead align="center">Math Audit</TableHead>
                <TableHead align="center">Processing</TableHead>
                <TableHead>Status</TableHead>
                <TableHead align="right">Actions</TableHead>
              </tr>
            </TableHeader>
            <TableBody>
              {filtered.map((j) => (
                <TableRow key={j.id}>
                  <TableCell>
                    <div className="font-mono font-bold text-slate-900 text-xs">
                      {new Date(j.created_at).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {new Date(j.created_at).toLocaleTimeString('en-IN', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })} • {j.id}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-bold text-slate-900 text-xs">
                      {j.bank_name}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono truncate max-w-[180px]">
                      {j.file_name}
                    </div>
                  </TableCell>
                  <TableCell align="center">
                    <div className="font-mono font-bold text-slate-800 text-xs">
                      {j.page_count} pgs
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      {j.transaction_count} txs
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-[11px] font-mono text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                      {j.parser_name}
                    </span>
                  </TableCell>
                  <TableCell align="center">
                    <span className={`font-mono font-bold text-[11px] px-2 py-0.5 rounded ${
                      j.balance_status === 'VALID'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-rose-50 text-rose-700 border border-rose-200'
                    }`}>
                      {j.balance_status === 'VALID' ? '100% BALANCED' : 'DISCREPANCY'}
                    </span>
                  </TableCell>
                  <TableCell align="center">
                    <span className="font-mono text-xs text-slate-600">
                      {j.duration_ms ? `${j.duration_ms} ms` : '—'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={j.status === 'COMPLETED' ? 'success' : 'warning'}
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
                      {j.has_xml && (
                        <a
                          href={`/api/conversions/${j.id}/download`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold text-brand-600 hover:bg-brand-50 transition-colors border border-transparent hover:border-brand-200"
                        >
                          <Download className="w-3.5 h-3.5" />
                          XML
                        </a>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>\n</div>
        )}
      </Card>

      {/* Deep Diagnostics Modal */}
      <Modal
        isOpen={isDiagOpen}
        onClose={() => {
          setIsDiagOpen(false);
          setDiagData(null);
        }}
        title="Admin Statement Diagnostic Dossier"
        size="lg"
        className="max-h-[90vh] overflow-y-auto"
      >
        {diagLoading || !diagData ? (
          <div className="p-16 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-3">
            <div className="w-8 h-8 rounded-full border-4 border-brand-500 border-t-transparent animate-spin" />
            Loading diagnostic dossier...
          </div>
        ) : (
          <div className="space-y-5 text-xs animate-fadeIn">
            <div className="p-4 rounded-2xl bg-gradient-to-br from-slate-50 to-white border border-slate-200 flex flex-wrap items-center justify-between gap-4 shadow-sm">
              <div>
                <strong className="text-base text-navy-900 block font-black">{diagData.bank_name}</strong>
                <span className="text-slate-500 text-xs font-mono">{diagData.file_name}</span>
              </div>
              <Badge variant={diagData.confidence_tier === 'HIGH' ? 'success' : 'warning'} size="md">
                {diagData.confidence_tier} ({diagData.confidence_score}%)
              </Badge>
            </div>

            <div className="p-4 bg-navy-950 text-slate-200 rounded-2xl shadow-inner space-y-3">
              <div className="text-emerald-400 font-bold uppercase text-[10px] tracking-wider flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" /> Balance Verification Equation:
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                <div className="bg-navy-900/50 p-2.5 rounded-xl border border-navy-800">
                  <span className="text-slate-400 block text-[10px] uppercase font-sans font-bold">Opening</span>
                  ₹{diagData.opening_balance || '0.00'}
                </div>
                <div className="bg-emerald-900/20 p-2.5 rounded-xl border border-emerald-900/50">
                  <span className="text-emerald-500 block text-[10px] uppercase font-sans font-bold">Credits (+)</span>
                  <span className="text-emerald-400">+₹{Number(diagData.total_credit || 0).toFixed(2)}</span>
                </div>
                <div className="bg-rose-900/20 p-2.5 rounded-xl border border-rose-900/50">
                  <span className="text-rose-500 block text-[10px] uppercase font-sans font-bold">Debits (-)</span>
                  <span className="text-rose-400">-₹{Number(diagData.total_debit || 0).toFixed(2)}</span>
                </div>
                <div className="bg-navy-900/50 p-2.5 rounded-xl border border-navy-800">
                  <span className="text-slate-400 block text-[10px] uppercase font-sans font-bold">Closing</span>
                  ₹{diagData.closing_balance || '0.00'}
                </div>
              </div>
            </div>

            {diagData.detection_reasons && (
              <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 shadow-sm">
                <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider block mb-2">Matched Signatures:</span>
                <div className="flex flex-wrap gap-2">
                  {diagData.detection_reasons.map((r: string, idx: number) => (
                    <span key={idx} className="px-2.5 py-1 bg-white border border-slate-200 rounded-lg text-[10px] text-slate-700 font-mono shadow-xs">
                      ✓ {r}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
              <Button
                variant="outline"
                size="md"
                onClick={() => setIsDiagOpen(false)}
                className="font-bold hover:bg-slate-100"
              >
                Close Inspector
              </Button>

              <a
                href={`/api/conversions/${diagData.job_id}/download`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 shadow-glow-brand transition-all hover:scale-105"
              >
                <Download className="w-4 h-4" />
                Download Validated XML
              </a>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
}
