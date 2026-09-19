'use client';

import React, { useState, useEffect } from 'react';
import { Calculator, BookOpen, Layers, CheckCircle2 } from 'lucide-react';
import { getAdminAccountingRules } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';

export default function AdminAccountingPage() {
  const [rules, setRules] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminAccountingRules()
      .then((data) => {
        setRules(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-black text-slate-900">Ledger & Accounting Rulebook</h1>
          <Badge variant="success" size="sm">Double-Entry Certified</Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Administrative visibility into party-to-ledger mapping dictionaries, automatic counter-ledger heuristic engines, and voucher classification algorithms.
        </p>
      </div>

      {/* Voucher Classification Logic */}
      <Card className="p-6 shadow-card space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900 flex items-center gap-2">
          <Calculator className="w-4 h-4 text-brand-600" />
          Voucher Classification Logic
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          {rules?.voucher_classification_logic?.map((r: any, idx: number) => (
            <div key={idx} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <span className="font-mono text-slate-700">{r.condition}</span>
              <Badge variant="primary" size="sm">➔ {r.voucher_type}</Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Keyword Mapping Dictionary */}
      <Card className="p-6 shadow-card space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900 flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-brand-600" />
          Keyword to Counter Ledger Mappings
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold">
                <th className="py-2.5 px-3">Narration Keyword</th>
                <th className="py-2.5 px-3">Target Ledger</th>
                <th className="py-2.5 px-3">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rules?.keyword_mapping_rules?.map((k: any, idx: number) => (
                <tr key={idx} className="hover:bg-slate-50">
                  <td className="py-2 px-3 font-mono font-bold text-brand-700">{k.keyword}</td>
                  <td className="py-2 px-3 font-bold text-slate-800">{k.ledger}</td>
                  <td className="py-2 px-3 text-slate-500">{k.category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
