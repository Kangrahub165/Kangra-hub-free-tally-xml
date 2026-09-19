'use client';

import React from 'react';
import { Settings, Cpu, HardDrive, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';

export default function AdminSystemSettingsPage() {
  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-black text-slate-900">Admin Technical Settings & Runtime</h1>
          <Badge variant="primary" size="sm">Uvicorn + Next.js Engine</Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Low-level platform configuration, database connection pools, and backend runtime environments.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <Card className="p-5 space-y-2">
          <div className="font-bold text-slate-900 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-brand-600" />
            Backend FastAPI Runtime
          </div>
          <div className="text-slate-600">Framework: <strong className="font-mono text-slate-800">FastAPI 0.115+ (Python 3.12)</strong></div>
          <div className="text-slate-600">Server: <strong className="font-mono text-slate-800">Uvicorn Workers (Port 8000)</strong></div>
          <div className="text-slate-600">Status: <span className="text-emerald-600 font-bold">● Healthy & Active</span></div>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="font-bold text-slate-900 flex items-center gap-2">
            <HardDrive className="w-4 h-4 text-purple-600" />
            Database & Store
          </div>
          <div className="text-slate-600">Database: <strong className="font-mono text-slate-800">Supabase PostgreSQL</strong></div>
          <div className="text-slate-600">Storage: <strong className="font-mono text-slate-800">Volatile OS Temp Dir</strong></div>
          <div className="text-slate-600">Isolation: <span className="text-emerald-600 font-bold">● Strict Row-Level Security</span></div>
        </Card>
      </div>
    </div>
  );
}
