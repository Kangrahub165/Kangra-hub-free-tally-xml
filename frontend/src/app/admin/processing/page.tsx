'use client';

import React, { useState, useEffect } from 'react';
import { HardDrive, Trash2, RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import { getAdminProcessingStatus, triggerManualFileCleanup } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

export default function AdminProcessingPage() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const [msg, setMsg] = useState('');

  const loadStatus = () => {
    setLoading(true);
    getAdminProcessingStatus()
      .then((data) => {
        setStatus(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      const res = await triggerManualFileCleanup();
      setMsg(res.message);
      loadStatus();
    } catch (err: any) {
      setMsg('Cleanup failed: ' + err.message);
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-black text-slate-900">File & Ephemeral Processing Engine</h1>
            <Badge variant="success" size="sm">Zero Permanent Storage</Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Volatile processing metrics, temporary document life-cycle status, and automated privacy purge controls.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadStatus} loading={loading} icon={<RefreshCw className="w-3.5 h-3.5" />}>
            Refresh Status
          </Button>
          <Button variant="danger" size="sm" onClick={handleCleanup} loading={cleaning} icon={<Trash2 className="w-3.5 h-3.5" />}>
            Purge Expired Temp Files
          </Button>
        </div>
      </div>

      {msg && (
        <div className="p-4 bg-brand-50 border border-brand-200 rounded-2xl text-xs text-brand-800 font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-brand-600 flex-shrink-0" />
          <span>{msg}</span>
        </div>
      )}

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Temporary Files in Buffer</span>
          <div className="text-2xl font-black text-slate-900 mt-2 font-mono tabular-nums">
            {status?.temp_file_count || 0}
          </div>
          <span className="text-[11px] text-slate-500 mt-1 inline-block">Decrypted in memory</span>
        </Card>

        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Buffer Disk Space</span>
          <div className="text-2xl font-black text-slate-900 mt-2 font-mono tabular-nums">
            {status?.temp_storage_mb || 0} <span className="text-xs font-semibold text-slate-500">MB</span>
          </div>
          <span className="text-[11px] text-emerald-600 font-semibold mt-1 inline-block">Low disk footprint</span>
        </Card>

        <Card className="p-5">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Automated Purge Policy</span>
          <div className="text-sm font-bold text-slate-800 mt-2">
            60-minute Max Retention
          </div>
          <span className="text-[11px] text-slate-500 mt-1 inline-block">Automatic background sweeper</span>
        </Card>
      </div>

      {/* Files List */}
      <Card className="shadow-card p-6">
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-brand-600" />
          Active Ephemeral Documents
        </h2>

        {status?.files && status.files.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold">
                  <th className="py-2.5 px-3">File Identifier</th>
                  <th className="py-2.5 px-3 text-right">Size</th>
                  <th className="py-2.5 px-3 text-right">Last Modified</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {status.files.map((f: any) => (
                  <tr key={f.name} className="hover:bg-slate-50">
                    <td className="py-2 px-3 font-mono font-medium text-slate-800">{f.name}</td>
                    <td className="py-2 px-3 font-mono text-right text-slate-600">{f.size_kb} KB</td>
                    <td className="py-2 px-3 font-mono text-right text-slate-400">{new Date(f.modified_at).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-xs text-slate-500">
            Buffer is completely clear. No temporary files stored.
          </div>
        )}
      </Card>
    </div>
  );
}
