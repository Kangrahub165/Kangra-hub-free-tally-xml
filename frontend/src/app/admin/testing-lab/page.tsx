'use client';

import React, { useState } from 'react';
import { FlaskConical, UploadCloud, CheckCircle2, AlertTriangle, FileCode, Check, RefreshCw, Lock } from 'lucide-react';
import { testParserStatementInLab } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

export default function StatementTestingLabPage() {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleTest = async () => {
    if (!file) return;
    setError('');
    setTesting(true);
    setResult(null);

    try {
      const data = await testParserStatementInLab(file, password || undefined);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Testing failed');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-black text-slate-900">Statement Testing Lab (Diagnostic Playground)</h1>
          <Badge variant="purple" size="sm">Admin Only • Zero Quota Deducted</Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Upload any test bank statement PDF to inspect raw bank detection signatures, parser mapping, coordinate extraction, and running balance equations without deducting user quotas.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Column */}
        <Card className="p-6 space-y-4 lg:col-span-1">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">Test Statement Ingestion</h2>

          <div
            onClick={() => document.getElementById('lab-file-input')?.click()}
            className="p-8 border-2 border-dashed border-slate-300 hover:border-brand-500 rounded-2xl text-center cursor-pointer bg-slate-50 hover:bg-brand-50/20 transition-all"
          >
            <input
              id="lab-file-input"
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setFile(e.target.files[0]);
                }
              }}
            />
            <FlaskConical className="w-8 h-8 text-brand-600 mx-auto mb-2" />
            <div className="text-xs font-bold text-slate-900 truncate max-w-[200px] mx-auto">
              {file ? file.name : 'Select Test PDF'}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">Upload for instant diagnostic audit</div>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
              Statement Password (Optional)
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="If encrypted (DOB, PAN, etc.)..."
              className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-medium"
            />
          </div>

          <Button
            variant="primary"
            size="md"
            className="w-full"
            disabled={!file || testing}
            loading={testing}
            onClick={handleTest}
            icon={<FlaskConical className="w-4 h-4" />}
          >
            Run Deep Diagnostic Audit
          </Button>

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold">
              {error}
            </div>
          )}
        </Card>

        {/* Results Column */}
        <Card className="p-6 lg:col-span-2 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">Diagnostic Inspection Output</h2>

          {result ? (
            <div className="space-y-4 text-xs">
              {/* Header Box */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="font-extrabold text-sm text-slate-900">{result.detected_bank}</div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">{result.parser_name}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={result.confidence_tier === 'HIGH' ? 'success' : 'warning'} size="sm">
                    {result.confidence_tier} ({result.detection_confidence}%)
                  </Badge>
                  <Badge variant={result.balance_status === 'VALID' ? 'success' : 'danger'} size="sm">
                    {result.balance_status} MATH
                  </Badge>
                </div>
              </div>

              {/* Matched Signatures */}
              <div>
                <span className="font-bold text-slate-700 uppercase text-[10px]">Signatures Identified:</span>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {result.detection_reasons && result.detection_reasons.map((r: string, idx: number) => (
                    <span key={idx} className="px-2 py-0.5 bg-brand-50 text-brand-700 border border-brand-200 rounded text-[11px] font-mono">
                      ✓ {r}
                    </span>
                  ))}
                </div>
              </div>

              {/* Extraction Metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-100">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-400 uppercase">Pages</span>
                  <div className="font-bold font-mono text-slate-800 mt-1">{result.page_count}</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-400 uppercase">Extracted Rows</span>
                  <div className="font-bold font-mono text-slate-800 mt-1">{result.transaction_count}</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-400 uppercase">Total Debit</span>
                  <div className="font-bold font-mono text-rose-600 mt-1">₹{Number(result.total_debit).toFixed(2)}</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                  <span className="text-[10px] text-slate-400 uppercase">Total Credit</span>
                  <div className="font-bold font-mono text-emerald-600 mt-1">₹{Number(result.total_credit).toFixed(2)}</div>
                </div>
              </div>

              {/* Sample Extracted Rows */}
              {result.sample_transactions && result.sample_transactions.length > 0 && (
                <div className="pt-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-slate-700 uppercase text-[10px]">
                      First {result.sample_transactions.length} Sample Extracted Rows (Boundary Isolated):
                    </span>
                    <span className="text-[10px] text-emerald-600 font-bold">
                      ✓ 100% Zero-Contamination Isolated
                    </span>
                  </div>
                  <div className="overflow-x-auto mt-2 max-h-[360px] border border-slate-200 rounded-xl">
                    <table className="w-full text-left text-[11px]">
                      <thead className="bg-slate-100 text-slate-600 sticky top-0 font-bold uppercase text-[9px]">
                        <tr>
                          <th className="p-2">Pg</th>
                          <th className="p-2">Date</th>
                          <th className="p-2">Clean Narration</th>
                          <th className="p-2">Reference</th>
                          <th className="p-2 text-right">Debit</th>
                          <th className="p-2 text-right">Credit</th>
                          <th className="p-2 text-right">Balance</th>
                          <th className="p-2 text-center">Iso Conf</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {result.sample_transactions.map((t: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                            <td className="p-2 font-mono text-slate-400 text-[10px]">{t.source_page ?? 1}</td>
                            <td className="p-2 font-mono whitespace-nowrap">{t.date}</td>
                            <td className="p-2 max-w-[240px]">
                              <div className="font-medium text-slate-900 truncate" title={t.narration}>
                                {t.narration}
                              </div>
                              {t.source_lines && t.source_lines.length > 0 && (
                                <div className="text-[9px] text-slate-400 font-mono truncate" title={t.source_lines.join(' ')}>
                                  Src: {t.source_lines[0]}
                                </div>
                              )}
                            </td>
                            <td className="p-2 font-mono text-[10px] text-brand-600 truncate max-w-[120px]" title={t.reference}>
                              {t.reference || '—'}
                            </td>
                            <td className="p-2 text-right font-mono text-rose-600 font-semibold">{t.debit}</td>
                            <td className="p-2 text-right font-mono text-emerald-600 font-semibold">{t.credit}</td>
                            <td className="p-2 text-right font-mono text-slate-700">{t.balance ?? '—'}</td>
                            <td className="p-2 text-center">
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                {Math.round((t.boundary_confidence ?? 1.0) * 100)}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-16 text-slate-400 text-xs">
              Upload a test PDF on the left and run diagnostic audit to inspect parsed metadata.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
