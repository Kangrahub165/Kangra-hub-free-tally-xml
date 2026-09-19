'use client';

import React, { useState } from 'react';
import { 
  User, 
  Bookmark, 
  Plus, 
  Trash2, 
  CheckCircle2, 
  Save, 
  Lock, 
  ShieldCheck, 
  CreditCard, 
  SlidersHorizontal,
  Sparkles,
  KeyRound
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Tabs } from '@/components/ui/Tabs';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { useRouter } from 'next/navigation';
import { getAuthToken } from '@/lib/api';

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('mappings');
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [successMsg, setSuccessMsg] = useState('Settings updated successfully.');

  React.useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      router.push('/login?redirect=/settings');
    }
  }, [router]);

  // Ledger mappings state
  const [mappings, setMappings] = useState([
    { pattern: 'TATAPLAYDIRECT', ledger: 'Postage And Telephone' },
    { pattern: 'APY CONTRI', ledger: 'APY Contribution' },
    { pattern: 'CASH DEPOSIT', ledger: 'Cash' },
    { pattern: 'SWIGGY', ledger: 'Staff Welfare Expenses' },
    { pattern: 'ZOMATO', ledger: 'Staff Welfare Expenses' },
    { pattern: 'INDIAN OIL', ledger: 'Fuel & Conveyance' },
  ]);

  const [newPattern, setNewPattern] = useState('');
  const [newLedger, setNewLedger] = useState('');

  // Profile fields
  const [profileName, setProfileName] = useState('Kangra Hub User');
  const [profileEmail, setProfileEmail] = useState('user@kangrahub.com');
  const [profileMobile, setProfileMobile] = useState('+91 98160 00000');
  const [profileTimezone, setProfileTimezone] = useState('Asia/Kolkata');

  // Security fields
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Preference fields
  const [dateFormat, setDateFormat] = useState('DD-MM-YYYY');
  const [defaultVoucher, setDefaultVoucher] = useState('Payment');
  const [autoMapLedgers, setAutoMapLedgers] = useState(true);

  const handleAddMapping = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPattern || !newLedger) return;
    setMappings([...mappings, { pattern: newPattern.trim().toUpperCase(), ledger: newLedger.trim() }]);
    setNewPattern('');
    setNewLedger('');
    triggerSuccess('New ledger mapping rule added.');
  };

  const handleDelete = (index: number) => {
    setMappings(mappings.filter((_, i) => i !== index));
    triggerSuccess('Mapping rule deleted.');
  };

  const triggerSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 2800);
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: <User className="w-3.5 h-3.5" /> },
    { id: 'security', label: 'Security', icon: <Lock className="w-3.5 h-3.5" /> },
    { id: 'mappings', label: 'Ledger Mappings', icon: <Bookmark className="w-3.5 h-3.5" />, count: mappings.length },
    { id: 'account', label: 'Account & Quota', icon: <CreditCard className="w-3.5 h-3.5" /> },
    { id: 'preferences', label: 'Preferences', icon: <SlidersHorizontal className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="py-12 bg-slate-50 min-h-screen">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
          <div className="space-y-1">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Settings & Ledger Preferences
            </h1>
            <p className="text-xs text-slate-500">
              Manage personal credentials, party-to-ledger mapping rules, and conversion preferences
            </p>
          </div>
        </div>

        {savedSuccess && (
          <StatusAlert
            type="success"
            title="Success"
            message={successMsg}
            onDismiss={() => setSavedSuccess(false)}
          />
        )}

        {/* Tab Navigation */}
        <Tabs
          tabs={tabs}
          activeTab={activeTab}
          onChange={setActiveTab}
          className="bg-white p-1.5 shadow-xs"
        />

        {/* SECTION 1: PROFILE */}
        {activeTab === 'profile' && (
          <Card className="shadow-card">
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Personal and contact credentials used for account verification
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Full Name"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                />
                <Input
                  label="Email Address"
                  type="email"
                  value={profileEmail}
                  disabled
                  helperText="Contact support to change your verified primary email."
                />
                <Input
                  label="Mobile Number"
                  value={profileMobile}
                  onChange={(e) => setProfileMobile(e.target.value)}
                />
                <Select
                  label="Timezone"
                  value={profileTimezone}
                  onChange={(e) => setProfileTimezone(e.target.value)}
                  helperText="Your daily 50-page quota resets at 00:00 Asia/Kolkata."
                >
                  <option value="Asia/Kolkata">Asia/Kolkata (IST +05:30)</option>
                  <option value="UTC">UTC (Universal Coordinated Time)</option>
                  <option value="America/New_York">America/New_York (EST)</option>
                  <option value="Europe/London">Europe/London (GMT)</option>
                </Select>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button
                variant="primary"
                size="md"
                onClick={() => triggerSuccess('Profile details saved successfully.')}
                icon={<Save className="w-4 h-4" />}
              >
                Save Changes
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* SECTION 2: SECURITY */}
        {activeTab === 'security' && (
          <Card className="shadow-card">
            <CardHeader>
              <CardTitle>Security & Authentication</CardTitle>
              <CardDescription>
                Manage your account password and review two-factor OTP security
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="max-w-md space-y-4">
                <Input
                  type="password"
                  label="Current Password"
                  placeholder="••••••••"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
                <Input
                  type="password"
                  label="New Password"
                  placeholder="At least 6 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
                <Input
                  type="password"
                  label="Confirm New Password"
                  placeholder="Re-enter new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>

              <div className="pt-4 border-t border-slate-100">
                <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 border border-slate-200/80">
                  <div className="space-y-0.5">
                    <div className="text-xs font-bold text-slate-800">Email OTP Verification</div>
                    <div className="text-[11px] text-slate-500">Active for all new signups and password resets</div>
                  </div>
                  <Badge variant="success" size="sm">
                    Enforced
                  </Badge>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button
                variant="primary"
                size="md"
                onClick={() => {
                  setCurrentPassword('');
                  setNewPassword('');
                  setConfirmPassword('');
                  triggerSuccess('Password updated successfully.');
                }}
                icon={<KeyRound className="w-4 h-4" />}
              >
                Update Password
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* SECTION 3: LEDGER MAPPINGS */}
        {activeTab === 'mappings' && (
          <Card className="shadow-card">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <CardTitle>Saved Party-to-Ledger Mappings</CardTitle>
                  <CardDescription>
                    Automatically assign recurring transaction narration keywords to your target Tally ledger names.
                  </CardDescription>
                </div>
                <Badge variant="primary" size="sm">
                  {mappings.length} Active Rules
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-6">
              {/* Add New Rule Form */}
              <form
                onSubmit={handleAddMapping}
                className="bg-slate-50 p-4 rounded-2xl border border-slate-200/80 flex flex-col sm:flex-row items-center gap-3"
              >
                <div className="w-full sm:w-1/2">
                  <input
                    type="text"
                    placeholder="Narration keyword (e.g. SWIGGY, APY, TATAPLAY)"
                    value={newPattern}
                    onChange={(e) => setNewPattern(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600 font-mono uppercase"
                  />
                </div>
                <div className="w-full sm:w-1/2">
                  <input
                    type="text"
                    placeholder="Tally Ledger (e.g. Staff Welfare, Utility)"
                    value={newLedger}
                    onChange={(e) => setNewLedger(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  className="w-full sm:w-auto flex-shrink-0"
                  icon={<Plus className="w-4 h-4" />}
                >
                  Add Rule
                </Button>
              </form>

              {/* Rules List */}
              <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden bg-white">
                {mappings.map((m, idx) => (
                  <div key={idx} className="p-3.5 flex items-center justify-between hover:bg-slate-50/70 transition-colors text-xs">
                    <div className="flex items-center gap-4">
                      <span className="font-mono font-bold text-slate-800 bg-slate-100 px-2.5 py-1 rounded-lg border border-slate-200/70 text-[11px]">
                        {m.pattern}
                      </span>
                      <span className="text-slate-400">→</span>
                      <span className="font-semibold text-slate-900">
                        {m.ledger}
                      </span>
                    </div>

                    <button
                      onClick={() => handleDelete(idx)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                      title="Delete rule"
                      aria-label={`Delete mapping rule ${m.pattern}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* SECTION 4: ACCOUNT & QUOTA */}
        {activeTab === 'account' && (
          <Card className="shadow-card">
            <CardHeader>
              <CardTitle>Account Tier & Allowance Details</CardTitle>
              <CardDescription>
                Review your daily page processing quota and tier specifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Account Level</div>
                  <div className="text-lg font-black text-slate-900 mt-1">Standard Free</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">Complimentary community tier</div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Daily Allowance</div>
                  <div className="text-lg font-black text-brand-600 mt-1">50 Pages / Day</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">Calculated on actual parsed pages</div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Quota Reset Time</div>
                  <div className="text-lg font-black text-slate-900 mt-1">00:00 Midnight</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">Asia/Kolkata timezone</div>
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-brand-50/50 border border-brand-200/80 mt-2 text-xs text-brand-900 flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-brand-600 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold">Need unlimited daily conversion volume?</div>
                  <p className="text-slate-600 text-[11px] leading-relaxed">
                    Chartered accountant firms and high-volume businesses can contact platform administration through the Contact page to request exemption from daily page limits.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* SECTION 5: PREFERENCES */}
        {activeTab === 'preferences' && (
          <Card className="shadow-card">
            <CardHeader>
              <CardTitle>Conversion & Export Preferences</CardTitle>
              <CardDescription>
                Customize default voucher behavior and date parsing preferences
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Select
                  label="Display Date Format"
                  value={dateFormat}
                  onChange={(e) => setDateFormat(e.target.value)}
                  helperText="Tally XML files automatically format dates to YYYYMMDD internally."
                >
                  <option value="DD-MM-YYYY">DD-MM-YYYY (Indian Standard)</option>
                  <option value="YYYY-MM-DD">YYYY-MM-DD (ISO)</option>
                  <option value="MM/DD/YYYY">MM/DD/YYYY (US)</option>
                </Select>

                <Select
                  label="Default Voucher Type for Outflow"
                  value={defaultVoucher}
                  onChange={(e) => setDefaultVoucher(e.target.value)}
                  helperText="Default classification applied to debit (withdrawal) transactions."
                >
                  <option value="Payment">Payment</option>
                  <option value="Journal">Journal</option>
                  <option value="Contra">Contra</option>
                </Select>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200/70">
                <div className="space-y-0.5">
                  <div className="text-xs font-bold text-slate-800">Auto-Apply Saved Ledger Mappings</div>
                  <div className="text-[11px] text-slate-500">Automatically prefill counter ledger cells when keywords match</div>
                </div>
                <input
                  type="checkbox"
                  checked={autoMapLedgers}
                  onChange={(e) => setAutoMapLedgers(e.target.checked)}
                  className="w-4 h-4 rounded text-brand-600 border-slate-300 focus:ring-brand-500"
                />
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button
                variant="primary"
                size="md"
                onClick={() => triggerSuccess('Preferences saved successfully.')}
                icon={<Save className="w-4 h-4" />}
              >
                Save Preferences
              </Button>
            </CardFooter>
          </Card>
        )}

      </div>
    </div>
  );
}
