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
        <Card className="shadow-card">
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center border border-brand-200/60 shadow-xs">
                <SettingsIcon className="w-4 h-4" />
              </div>
              <div>
                <CardTitle>Conversion Engine Limits</CardTitle>
                <CardDescription>
                  Configure the default allowances and file constraints applied across user accounts
                </CardDescription>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                type="number"
                label="Free Daily Page Limit (Per User)"
                value={settings.free_daily_page_limit}
                onChange={(e) => setSettings({ ...settings, free_daily_page_limit: Number(e.target.value) })}
                helperText="Standard default: 50 pages per calendar day"
              />

              <Input
                type="number"
                label="Max Upload Size (MB)"
                value={settings.max_upload_size_mb}
                onChange={(e) => setSettings({ ...settings, max_upload_size_mb: Number(e.target.value) })}
                helperText="Maximum allowed PDF statement file size (Default: 25 MB)"
              />

              <Input
                type="number"
                label="Max Pages Per Statement File"
                value={settings.max_pages_per_file}
                onChange={(e) => setSettings({ ...settings, max_pages_per_file: Number(e.target.value) })}
                helperText="Maximum statement page count before rejection (Default: 200)"
              />

              <Select
                label="System Maintenance Mode"
                value={settings.maintenance_mode ? 'true' : 'false'}
                onChange={(e) => setSettings({ ...settings, maintenance_mode: e.target.value === 'true' })}
                helperText="When enabled, non-admin conversions are paused with a notice"
              >
                <option value="false">Disabled (Normal Operations)</option>
                <option value="true">Enabled (Under Maintenance)</option>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Section 129: Buy Me a Coffee Support Parameters */}
        <Card className="shadow-card">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-200/60 shadow-xs">
                  <Coffee className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle>Section 129: Project Support Settings (Admin Only)</CardTitle>
                  <CardDescription>
                    Configure the voluntary support widget shown exclusively inside the administrator portal
                  </CardDescription>
                </div>
              </div>
              <Badge variant="warning" size="sm">
                Owner Only
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label="Widget Visibility"
                value={settings.buy_coffee_enabled ? 'true' : 'false'}
                onChange={(e) => setSettings({ ...settings, buy_coffee_enabled: e.target.value === 'true' })}
                helperText="Controls display inside the Admin Console"
              >
                <option value="true">Enabled (Visible in Admin Console)</option>
                <option value="false">Disabled</option>
              </Select>

              <Input
                label="Owner UPI ID"
                placeholder="e.g. name@bank"
                value={settings.buy_coffee_upi_id || ''}
                onChange={(e) => setSettings({ ...settings, buy_coffee_upi_id: e.target.value })}
                helperText="Displayed with one-click copy button inside the support modal"
              />

              <Input
                label="Card Action Button Text"
                value={settings.buy_coffee_button_text || 'Support Project ☕'}
                onChange={(e) => setSettings({ ...settings, buy_coffee_button_text: e.target.value })}
              />

              <Input
                label="Support Pitch Message"
                value={settings.buy_coffee_message || ''}
                onChange={(e) => setSettings({ ...settings, buy_coffee_message: e.target.value })}
              />
            </div>
          </CardContent>

          <CardFooter className="flex justify-end">
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={saving}
              icon={<Save className="w-4 h-4" />}
            >
              Save Configuration Settings
            </Button>
          </CardFooter>
        </Card>

      </form>
    </div>
  );
}
