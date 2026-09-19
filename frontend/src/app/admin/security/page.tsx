'use client';

import React, { useState, useEffect } from 'react';
import { Shield, Lock, ShieldCheck, KeyRound, AlertCircle } from 'lucide-react';
import { getAdminSecurityOverview } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';

export default function AdminSecurityPage() {
  const [sec, setSec] = useState<any>(null);

  useEffect(() => {
    getAdminSecurityOverview().then(setSec).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-black text-slate-900">Security & Privileged Access Center</h1>
          <Badge variant="success" size="sm">Strict Isolation Active</Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Server-side access control, session integrity monitoring, and cryptographic memory hygiene policies.
        </p>
      </div>

      {/* Enforced Policies */}
      <Card className="p-6 shadow-card">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900 mb-4 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          Enforced Security & Privacy Policies
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          {sec?.security_policies?.map((p: any, idx: number) => (
            <div key={idx} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-900">{p.policy}</div>
                <div className="text-[10px] text-slate-500 uppercase">{p.type}</div>
              </div>
              <Badge variant="success" size="sm">{p.status}</Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Privileged Admin Accounts */}
      <Card className="p-6 shadow-card">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900 mb-4 flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-brand-600" />
          Authorized Administrator Accounts
        </h2>
        <div className="space-y-2 text-xs">
          {sec?.admin_accounts?.map((a: any, idx: number) => (
            <div key={idx} className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                <span className="font-bold text-slate-800">{a.email}</span>
                <span className="text-[10px] text-slate-400 font-mono ml-2">IP: {a.ip}</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="purple" size="sm">{a.role}</Badge>
                <span className="text-[11px] text-slate-500">{a.last_active}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
