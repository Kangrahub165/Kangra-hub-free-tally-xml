'use client';

import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import { Coffee, QrCode, Save, CheckCircle2, ShieldAlert } from 'lucide-react';
import { getSection129Settings, updateSection129Settings } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

export default function Section129Page() {
  const [data, setData] = useState<any>({
    buy_coffee_enabled: true,
    buy_coffee_upi_id: '9418250639@ybl',
    buy_coffee_payment_url: 'https://buymeacoffee.com',
    buy_coffee_button_text: 'Support Kangra Hub',
    buy_coffee_message: 'Voluntary developer support contribution.'
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    getSection129Settings().then(setData).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSection129Settings(data);
      setMsg('Section 129 configuration saved successfully.');
    } catch (err: any) {
      setMsg('Update failed: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-card">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-black text-slate-900">Section 129: Voluntary Support (Admin Only)</h1>
          <Badge variant="warning" size="sm">Strictly Confined to Admin</Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Configuration and high-resolution display of administrative voluntary support QR codes. This section is strictly restricted and never displayed on public pages or normal user dashboards.
        </p>
      </div>

      {msg && (
        <div className="p-4 bg-brand-50 border border-brand-200 rounded-2xl text-xs text-brand-800 font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-brand-600 flex-shrink-0" />
          <span>{msg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Settings Form */}
        <Card className="p-6 space-y-4 shadow-card">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
            <Coffee className="w-4 h-4 text-amber-600" />
            Support Parameters
          </h2>

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">UPI Identifier</label>
            <input
              type="text"
              value={data.buy_coffee_upi_id}
              onChange={(e) => setData({ ...data, buy_coffee_upi_id: e.target.value })}
              className="w-full px-3 py-2 text-xs font-mono rounded-xl border border-slate-300"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">Button Label</label>
            <input
              type="text"
              value={data.buy_coffee_button_text}
              onChange={(e) => setData({ ...data, buy_coffee_button_text: e.target.value })}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">Message Description</label>
            <textarea
              rows={2}
              value={data.buy_coffee_message}
              onChange={(e) => setData({ ...data, buy_coffee_message: e.target.value })}
              className="w-full p-2.5 text-xs rounded-xl border border-slate-300"
            />
          </div>

          <Button variant="primary" size="md" onClick={handleSave} loading={saving} icon={<Save className="w-4 h-4" />}>
            Save Section 129 Config
          </Button>
        </Card>

        {/* High-Resolution QR Display */}
        <Card className="p-6 shadow-card text-center space-y-4 flex flex-col items-center justify-center">
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mb-1">
            <QrCode className="w-5 h-5" />
          </div>
          <h2 className="text-sm font-bold text-slate-900">High-Resolution Google Pay QR Code</h2>
          <div className="p-3 bg-white border-2 border-slate-200 rounded-2xl shadow-card inline-block">
            <Image
              src="/buy-a-coffee/googlepay_qr.png"
              alt="Google Pay QR Code"
              width={200}
              height={200}
              className="rounded-xl object-contain mx-auto"
            />
          </div>
          <div className="font-mono text-xs font-bold text-slate-800">
            UPI: {data.buy_coffee_upi_id}
          </div>
          <p className="text-[10px] text-slate-400 max-w-xs leading-relaxed">
            Verified compliant with PRD Section 46. Never surfaced on public routes.
          </p>
        </Card>
      </div>
    </div>
  );
}
