'use client';

import React, { useState, useEffect } from 'react';
import { getAdminSettings, updateAdminSettings } from '@/lib/api';
import { Save, Check, Settings as SettingsIcon, Coffee, ShieldAlert } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { StatusAlert } from '@/components/ui/StatusAlert';

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getAdminSettings()
      .then((data) => {
        setSettings(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    try {
      await updateAdminSettings(settings);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch {
      alert('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-20 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
        <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        Loading system configuration parameters...
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            System & Support Settings
          </h1>
          <p className="text-xs text-slate-500">
            Configure global daily page quotas, upload bounds, and Section 129 project support parameters
          </p>
        </div>
      </div>

      {savedSuccess && (
        <StatusAlert
          type="success"
          message="System settings updated and synchronized across server instances."
          onDismiss={() => setSavedSuccess(false)}
        />
      )}

      <form onSubmit={handleSave} className="space-y-6">
        
        {/* Conversion Engine Quotas */}
        <Card className="shadow-card border-t-4 border-t-brand-500 rounded-3xl overflow-hidden">
          <CardHeader className="bg-slate-50/50 border-b border-slate-100 pb-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-50 to-white text-brand-600 flex items-center justify-center border border-brand-200 shadow-sm">
                <SettingsIcon className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-lg font-black text-navy-900">Conversion Engine Limits</CardTitle>
                <CardDescription className="text-xs text-slate-500 font-medium mt-0.5">
                  Configure the default allowances and file constraints applied across user accounts
                </CardDescription>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-5 pt-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Free Daily Page Limit (Per User)</label>
                <Input
                  type="number"
                  value={settings.free_daily_page_limit}
                  onChange={(e) => setSettings({ ...settings, free_daily_page_limit: Number(e.target.value) })}
                  className="h-11 shadow-inner focus:ring-brand-500/20 focus:border-brand-500 text-sm font-bold"
                />
                <p className="text-[10px] text-slate-500 font-medium">Standard default: 50 pages per calendar day</p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Max Upload Size (MB)</label>
                <Input
                  type="number"
                  value={settings.max_upload_size_mb}
                  onChange={(e) => setSettings({ ...settings, max_upload_size_mb: Number(e.target.value) })}
                  className="h-11 shadow-inner focus:ring-brand-500/20 focus:border-brand-500 text-sm font-bold"
                />
                <p className="text-[10px] text-slate-500 font-medium">Maximum allowed PDF statement file size (Default: 25 MB)</p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Max Pages Per Statement File</label>
                <Input
                  type="number"
                  value={settings.max_pages_per_file}
                  onChange={(e) => setSettings({ ...settings, max_pages_per_file: Number(e.target.value) })}
                  className="h-11 shadow-inner focus:ring-brand-500/20 focus:border-brand-500 text-sm font-bold"
                />
                <p className="text-[10px] text-slate-500 font-medium">Maximum statement page count before rejection (Default: 200)</p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">System Maintenance Mode</label>
                <Select
                  value={settings.maintenance_mode ? 'true' : 'false'}
                  onChange={(e) => setSettings({ ...settings, maintenance_mode: e.target.value === 'true' })}
                  className="h-11 shadow-inner focus:ring-amber-500/20 focus:border-amber-500 text-sm font-bold bg-white"
                >
                  <option value="false">Disabled (Normal Operations)</option>
                  <option value="true">Enabled (Under Maintenance)</option>
                </Select>
                <p className="text-[10px] text-slate-500 font-medium">When enabled, non-admin conversions are paused with a notice</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Section 129: Buy Me a Coffee Support Parameters */}
        <Card className="shadow-card border-t-4 border-t-amber-500 rounded-3xl overflow-hidden">
          <CardHeader className="bg-slate-50/50 border-b border-slate-100 pb-5">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-50 to-white text-amber-600 flex items-center justify-center border border-amber-200 shadow-sm">
                  <Coffee className="w-5 h-5" />
                </div>
                <div>
                  <CardTitle className="text-lg font-black text-navy-900">Section 129: Project Support Settings</CardTitle>
                  <CardDescription className="text-xs text-slate-500 font-medium mt-0.5">
                    Configure the voluntary support widget shown exclusively inside the administrator portal
                  </CardDescription>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200 flex items-center gap-1 shadow-sm">
                <ShieldAlert className="w-3 h-3" /> Owner Only
              </span>
            </div>
          </CardHeader>

          <CardContent className="space-y-5 pt-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Widget Visibility</label>
                <Select
                  value={settings.buy_coffee_enabled ? 'true' : 'false'}
                  onChange={(e) => setSettings({ ...settings, buy_coffee_enabled: e.target.value === 'true' })}
                  className="h-11 shadow-inner focus:ring-amber-500/20 focus:border-amber-500 text-sm font-bold bg-white"
                >
                  <option value="true">Enabled (Visible in Admin Console)</option>
                  <option value="false">Disabled</option>
                </Select>
                <p className="text-[10px] text-slate-500 font-medium">Controls display inside the Admin Console</p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Owner UPI ID</label>
                <Input
                  placeholder="e.g. name@bank"
                  value={settings.buy_coffee_upi_id || ''}
                  onChange={(e) => setSettings({ ...settings, buy_coffee_upi_id: e.target.value })}
                  className="h-11 shadow-inner focus:ring-amber-500/20 focus:border-amber-500 text-sm font-bold"
                />
                <p className="text-[10px] text-slate-500 font-medium">Displayed with one-click copy button inside the support modal</p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Card Action Button Text</label>
                <Input
                  value={settings.buy_coffee_button_text || 'Support Project ☕'}
                  onChange={(e) => setSettings({ ...settings, buy_coffee_button_text: e.target.value })}
                  className="h-11 shadow-inner focus:ring-amber-500/20 focus:border-amber-500 text-sm font-bold"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Support Pitch Message</label>
                <Input
                  value={settings.buy_coffee_message || ''}
                  onChange={(e) => setSettings({ ...settings, buy_coffee_message: e.target.value })}
                  className="h-11 shadow-inner focus:ring-amber-500/20 focus:border-amber-500 text-sm font-bold"
                />
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex justify-end bg-slate-50/50 border-t border-slate-100 p-5 mt-4">
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={saving}
              icon={<Save className="w-4 h-4" />}
              className="bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 shadow-glow-brand font-bold px-6"
            >
              Save Configuration Settings
            </Button>
          </CardFooter>
        </Card>

      </form>
    </div>
  );
}
