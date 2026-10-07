import React, { useState, useEffect, useMemo } from 'react';
import {
  Building2,
  Sparkles,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  Eye,
  Code,
  Check,
  Copy,
  Info
} from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
import {
  getLedgerTallyPreview,
  createLedgerMaster,
  LedgerTallyPreview
} from '@/lib/api';

export interface CreateLedgerMasterModalProps {
  isOpen: boolean;
  onClose: () => void;
  party: {
    name: string;
    alias?: string;
    gstin?: string;
    pan?: string;
    address?: string;
    state?: string;
    pincode?: string;
    country?: string;
    registration_type?: string;
    parent_group?: string;
    saved_draft_version?: number;
  } | null;
  initialInvoiceValues?: {
    name: string;
    gstin?: string;
    state?: string;
    address?: string;
  } | null;
  defaultParentGroup?: 'Sundry Creditors' | 'Sundry Debtors';
  onSaveMaster: (savedData: {
    name: string;
    alias?: string;
    parent_group: string;
    address_lines: string[];
    state: string;
    country: string;
    pincode?: string;
    gstin?: string;
    pan?: string;
    registration_type: string;
    saved_draft_version?: number;
  }) => Promise<void>;
}

const GSTIN_STATE_MAP: Record<string, string> = {
  '01': 'Jammu & Kashmir',
  '02': 'Himachal Pradesh',
  '03': 'Punjab',
  '04': 'Chandigarh',
  '05': 'Uttarakhand',
  '06': 'Haryana',
  '07': 'Delhi',
  '08': 'Rajasthan',
  '09': 'Uttar Pradesh',
  '10': 'Bihar',
  '11': 'Sikkim',
  '12': 'Arunachal Pradesh',
  '13': 'Nagaland',
  '14': 'Manipur',
  '15': 'Mizoram',
  '16': 'Tripura',
  '17': 'Meghalaya',
  '18': 'Assam',
  '19': 'West Bengal',
  '20': 'Jharkhand',
  '21': 'Odisha',
  '22': 'Chhattisgarh',
  '23': 'Madhya Pradesh',
  '24': 'Gujarat',
  '26': 'Dadra & Nagar Haveli and Daman & Diu',
  '27': 'Maharashtra',
  '28': 'Andhra Pradesh',
  '29': 'Karnataka',
  '30': 'Goa',
  '31': 'Lakshadweep',
  '32': 'Kerala',
  '33': 'Tamil Nadu',
  '34': 'Puducherry',
  '35': 'Andaman & Nicobar Islands',
  '36': 'Telangana',
  '37': 'Andhra Pradesh',
  '38': 'Ladakh'
};

export const CreateLedgerMasterModal: React.FC<CreateLedgerMasterModalProps> = ({
  isOpen,
  onClose,
  party,
  initialInvoiceValues,
  defaultParentGroup = 'Sundry Creditors',
  onSaveMaster,
}) => {
  // Form state
  const [name, setName] = useState('');
  const [alias, setAlias] = useState('');
  const [parentGroup, setParentGroup] = useState<string>(defaultParentGroup);
  const [address, setAddress] = useState('');
  const [state, setState] = useState('Himachal Pradesh');
  const [country, setCountry] = useState('India');
  const [pincode, setPincode] = useState('');
  const [gstin, setGstin] = useState('');
  const [pan, setPan] = useState('');
  const [registrationType, setRegistrationType] = useState('Regular');
  const [version, setVersion] = useState<number>(1);
  const [savedTime, setSavedTime] = useState<string | null>(null);

  // Preview state
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<LedgerTallyPreview | null>(null);
  const [previewXml, setPreviewXml] = useState<string>('');
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewTab, setPreviewTab] = useState<'screen' | 'xml'>('screen');
  const [copiedXml, setCopiedXml] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Initialize from party or default
  useEffect(() => {
    if (isOpen && party) {
      setName(party.name || '');
      setAlias(party.alias || '');
      setParentGroup(party.parent_group || defaultParentGroup);

      const rawGstin = (party.gstin || '').trim().toUpperCase();
      setGstin(rawGstin);

      // Extract PAN and state if GSTIN available
      if (rawGstin.length >= 2) {
        const code = rawGstin.substring(0, 2);
        if (GSTIN_STATE_MAP[code]) {
          setState(GSTIN_STATE_MAP[code]);
        } else if (party.state) {
          setState(party.state);
        }
      } else if (party.state) {
        setState(party.state);
      } else {
        setState('Himachal Pradesh');
      }

      if (rawGstin.length === 15) {
        setPan(rawGstin.substring(2, 12));
      } else {
        setPan(party.pan || '');
      }

      setAddress(party.address || '');
      setPincode(party.pincode || '');
      setCountry(party.country || 'India');

      if (party.registration_type) {
        setRegistrationType(party.registration_type);
      } else {
        setRegistrationType(rawGstin ? 'Regular' : 'Unregistered/Consumer');
      }

      if (party.saved_draft_version) {
        setVersion(party.saved_draft_version);
        setSavedTime('Previously Saved');
      } else {
        setVersion(1);
        setSavedTime(null);
      }
    }
  }, [isOpen, party, defaultParentGroup]);

  // Auto update PAN and State when GSTIN changes
  const handleGstinChange = (raw: string) => {
    const clean = raw.trim().toUpperCase();
    setGstin(clean);

    if (clean.length >= 2) {
      const code = clean.substring(0, 2);
      if (GSTIN_STATE_MAP[code]) {
        setState(GSTIN_STATE_MAP[code]);
      }
    }

    if (clean.length === 15) {
      setPan(clean.substring(2, 12));
      setRegistrationType('Regular');
    } else if (clean.length === 0) {
      setRegistrationType('Unregistered/Consumer');
    }
  };

  // Reset to invoice values
  const handleResetToInvoice = () => {
    if (!initialInvoiceValues && !party) return;
    const source = initialInvoiceValues || party!;
    setName(source.name || '');
    setAlias('');
    setParentGroup(defaultParentGroup);
    setAddress(source.address || '');

    const rawG = (source.gstin || '').trim().toUpperCase();
    setGstin(rawG);
    if (rawG.length >= 2 && GSTIN_STATE_MAP[rawG.substring(0, 2)]) {
      setState(GSTIN_STATE_MAP[rawG.substring(0, 2)]);
    } else {
      setState(source.state || 'Himachal Pradesh');
    }

    if (rawG.length === 15) {
      setPan(rawG.substring(2, 12));
      setRegistrationType('Regular');
    } else {
      setPan('');
      setRegistrationType(rawG ? 'Regular' : 'Unregistered/Consumer');
    }

    setPincode('');
    setCountry('India');
  };

  // Fetch "How it will look in Tally" preview
  const handleOpenTallyPreview = async () => {
    if (!name.trim()) return;
    setIsLoadingPreview(true);
    setIsPreviewOpen(true);
    try {
      const lines = address ? address.split('\n').map((l) => l.trim()).filter(Boolean) : [];
      const res = await getLedgerTallyPreview({
        name: name.trim(),
        alias: alias.trim() || undefined,
        parent_group: parentGroup,
        address_lines: lines,
        state,
        country,
        pincode: pincode.trim() || undefined,
        gstin: gstin.trim() || undefined,
        pan: pan.trim() || undefined,
        registration_type: registrationType,
      });

      if (res.success) {
        setPreviewData(res.preview);
        setPreviewXml(res.xml_snippet);
      }
    } catch (e: any) {
      alert(`Preview failed: ${e?.message || 'Could not parse generated XML.'}`);
      setIsPreviewOpen(false);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  // Save handler
  const handleSave = async () => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      const lines = address ? address.split('\n').map((l) => l.trim()).filter(Boolean) : [];
      const newVer = version + 1;
      const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      await onSaveMaster({
        name: name.trim(),
        alias: alias.trim() || undefined,
        parent_group: parentGroup,
        address_lines: lines,
        state,
        country,
        pincode: pincode.trim() || undefined,
        gstin: gstin.trim() || undefined,
        pan: pan.trim() || undefined,
        registration_type: registrationType,
        saved_draft_version: newVer,
      });

      setVersion(newVer);
      setSavedTime(`Saved v${newVer}, ${nowStr}`);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyXmlToClipboard = () => {
    navigator.clipboard.writeText(previewXml);
    setCopiedXml(true);
    setTimeout(() => setCopiedXml(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={
          <div className="flex items-center justify-between w-full pr-6">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
                <Building2 className="w-4 h-4" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span>Create Party Ledger in Tally</span>
                  <Badge variant="neutral" size="sm" className="font-semibold text-[11px] bg-teal-50 text-teal-800 border-teal-200">
                    {parentGroup}
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-500 font-normal">
                  Mirrors TallyPrime Ledger Creation screen with real statutory and GST registration tags.
                </p>
              </div>
            </div>
            {savedTime && (
              <Badge variant="success" size="sm" className="text-[10px] font-mono">
                {savedTime}
              </Badge>
            )}
          </div>
        }
        size="lg"
      >
        <div className="space-y-4 text-xs pt-1">
          {/* Main 2-column layout mirroring Tally */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* LEFT COLUMN: Name, Alias, Under, Mailing Details */}
            <div className="space-y-3 p-3 bg-slate-50/70 border border-slate-200 rounded-xl">
              <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider pb-1 border-b border-slate-200">
                General & Mailing Details
              </div>

              {/* Name */}
              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Name <span className="text-rose-500">*</span>
                </label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Full Party Name"
                  required
                  className="text-xs font-bold font-mono"
                />
              </div>

              {/* Alias */}
              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  (alias)
                </label>
                <Input
                  value={alias}
                  onChange={(e) => setAlias(e.target.value)}
                  placeholder="Optional short code or alias"
                  className="text-xs"
                />
              </div>

              {/* Under */}
              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Under <span className="text-rose-500">*</span>
                </label>
                <select
                  value={parentGroup}
                  onChange={(e) => setParentGroup(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 shadow-2xs"
                >
                  <option value="Sundry Creditors">Sundry Creditors (Suppliers / Vendors)</option>
                  <option value="Sundry Debtors">Sundry Debtors (Customers / Buyers)</option>
                </select>
              </div>

              {/* Address */}
              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Address
                </label>
                <textarea
                  rows={2}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="Street address / locality"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 shadow-2xs resize-none"
                />
              </div>

              {/* State & Country */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    State
                  </label>
                  <Input
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    placeholder="State"
                    className="text-xs font-medium"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Country
                  </label>
                  <Input
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="text-xs font-medium bg-slate-100"
                    readOnly
                  />
                </div>
              </div>

              {/* Pincode */}
              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Pincode
                </label>
                <Input
                  value={pincode}
                  onChange={(e) => setPincode(e.target.value.replace(/\D/g, '').substring(0, 6))}
                  placeholder="6-digit PIN"
                  maxLength={6}
                  className="text-xs font-mono"
                />
              </div>
            </div>

            {/* RIGHT COLUMN: Tax Registration Details */}
            <div className="space-y-3 p-3 bg-teal-50/40 border border-teal-200/80 rounded-xl">
              <div className="text-[11px] font-bold text-teal-900 uppercase tracking-wider pb-1 border-b border-teal-200 flex items-center justify-between">
                <span>Tax Registration Details</span>
                <Badge variant="neutral" size="sm" className="bg-teal-100 text-teal-800 text-[10px]">
                  Tally Statutory
                </Badge>
              </div>

              {/* GSTIN / UIN */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-800">
                    GSTIN / UIN
                  </label>
                  {gstin && (
                    <Badge variant="neutral" size="sm" className="text-[10px] bg-white text-slate-600">
                      Auto-validated
                    </Badge>
                  )}
                </div>
                <Input
                  value={gstin}
                  onChange={(e) => handleGstinChange(e.target.value)}
                  placeholder="15-character GSTIN"
                  maxLength={15}
                  className="text-xs font-mono uppercase font-bold tracking-wider"
                />
                <p className="text-[10px] text-slate-500 mt-0.5">
                  State code (first 2 digits) automatically populates the State.
                </p>
              </div>

              {/* PAN / IT No. */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-800">
                    PAN / IT No.
                  </label>
                  {pan && gstin.length === 15 && (
                    <span className="text-[10px] text-teal-700 font-semibold">
                      Extracted from GSTIN
                    </span>
                  )}
                </div>
                <Input
                  value={pan}
                  onChange={(e) => setPan(e.target.value.toUpperCase())}
                  placeholder="10-character PAN"
                  maxLength={10}
                  className="text-xs font-mono uppercase font-bold"
                />
                <p className="text-[10px] text-slate-500 mt-0.5">
                  Characters 3 to 12 of the party&apos;s GSTIN.
                </p>
              </div>

              {/* Registration Type */}
              <div>
                <label className="block font-bold text-slate-800 mb-1">
                  Registration type <span className="text-rose-500">*</span>
                </label>
                <select
                  value={registrationType}
                  onChange={(e) => setRegistrationType(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 shadow-2xs"
                >
                  <option value="Regular">Regular</option>
                  <option value="Unregistered/Consumer">Unregistered/Consumer</option>
                  <option value="Composition">Composition</option>
                </select>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  Used by Tally for GST compliance & GSTR returns matching.
                </p>
              </div>

              {/* Live Statutory Status Banner */}
              <div className="p-2.5 bg-white rounded-lg border border-teal-200 text-[11px] space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Party Type:</span>
                  <span className="font-bold text-teal-900">{registrationType}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">State / Territory:</span>
                  <span className="font-semibold text-slate-800">{state}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Parent Master:</span>
                  <span className="font-semibold text-slate-800">{parentGroup}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-slate-200">
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={handleResetToInvoice}
              className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1.5"
              title="Reset fields to original values extracted from invoice"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset to invoice values</span>
            </Button>

            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={handleOpenTallyPreview}
                disabled={isLoadingPreview || !name.trim()}
                className="text-xs font-semibold text-teal-800 border-teal-300 hover:bg-teal-50 flex items-center gap-1.5"
                title="Preview how this ledger appears in TallyPrime parsed from the generated XML"
              >
                <Eye className="w-3.5 h-3.5 text-teal-600" />
                <span>How it will look in Tally</span>
              </Button>

              <Button variant="outline" size="sm" type="button" onClick={onClose} disabled={isSubmitting}>
                Cancel
              </Button>

              <Button
                variant="primary"
                size="sm"
                type="button"
                onClick={handleSave}
                disabled={isSubmitting || !name.trim()}
                className="font-bold bg-teal-600 hover:bg-teal-700 text-white shadow-xs"
              >
                {isSubmitting ? 'Saving...' : 'Save & Map Ledger'}
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* HOW IT WILL LOOK IN TALLY MODAL */}
      {isPreviewOpen && (
        <Modal
          isOpen={isPreviewOpen}
          onClose={() => setIsPreviewOpen(false)}
          title={
            <div className="flex items-center justify-between w-full pr-6">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-amber-400 text-slate-900 font-bold flex items-center justify-center text-xs">
                  T
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">
                    TallyPrime Ledger Alteration Preview
                  </h3>
                  <p className="text-[10px] text-slate-500">
                    Parsed directly from generated XML snippet — what you see is what Tally gets
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                <button
                  type="button"
                  onClick={() => setPreviewTab('screen')}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                    previewTab === 'screen' ? 'bg-white shadow-2xs text-teal-900' : 'text-slate-600'
                  }`}
                >
                  Tally Screen
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewTab('xml')}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold flex items-center gap-1 ${
                    previewTab === 'xml' ? 'bg-white shadow-2xs text-teal-900' : 'text-slate-600'
                  }`}
                >
                  <Code className="w-3 h-3" />
                  <span>XML</span>
                </button>
              </div>
            </div>
          }
          size="lg"
        >
          <div className="space-y-3 pt-1">
            {previewTab === 'screen' ? (
              <div className="bg-[#fef8eb] border-2 border-[#d4af37] rounded-xl p-4 font-mono text-xs text-[#222] shadow-inner space-y-3">
                <div className="flex items-center justify-between border-b border-[#d4af37]/40 pb-2">
                  <span className="text-[11px] font-bold text-[#8a6d1c] uppercase">
                    Ledger Creation (Secondary)
                  </span>
                  <span className="text-[10px] bg-[#d4af37]/20 px-2 py-0.5 rounded text-[#5c470a] font-bold">
                    TallyPrime Gold Import
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Left Side */}
                  <div className="space-y-2 border-r border-[#d4af37]/30 pr-3">
                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Name:</span>
                      <span className="font-bold text-sm text-[#111]">{previewData?.name || name}</span>
                    </div>

                    {alias && (
                      <div>
                        <span className="text-[10px] text-[#7a6a43] block">(alias):</span>
                        <span className="font-semibold text-slate-800">{alias}</span>
                      </div>
                    )}

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Under:</span>
                      <span className="font-bold text-teal-900 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                        {previewData?.parent_group || parentGroup}
                      </span>
                    </div>

                    <div className="pt-2 border-t border-[#d4af37]/20 space-y-1">
                      <span className="text-[10px] font-bold text-[#8a6d1c] block">Mailing Details</span>
                      <div>
                        <span className="text-[10px] text-[#7a6a43]">Name: </span>
                        <span className="font-semibold">{previewData?.name || name}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#7a6a43]">Address: </span>
                        <span>{previewData?.address_lines?.join(', ') || address || '(Not provided)'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#7a6a43]">State: </span>
                        <span className="font-bold text-slate-900">{previewData?.state || state}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#7a6a43]">Country: </span>
                        <span>{previewData?.country || country}</span>
                      </div>
                      {previewData?.pincode && (
                        <div>
                          <span className="text-[10px] text-[#7a6a43]">Pincode: </span>
                          <span className="font-bold">{previewData.pincode}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Side: Tax Registration Details */}
                  <div className="space-y-2 pl-1">
                    <span className="text-[10px] font-bold text-[#8a6d1c] block">
                      Tax Registration Details
                    </span>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">PAN/IT No.:</span>
                      <span className="font-bold font-mono text-slate-900">
                        {previewData?.pan || 'Not Available'}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Registration type:</span>
                      <span className="font-bold text-emerald-800">
                        {previewData?.registration_type || registrationType}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">GSTIN/UIN:</span>
                      <span className="font-bold font-mono tracking-wider text-slate-900">
                        {previewData?.gstin || 'Not Available'}
                      </span>
                    </div>

                    <div className="mt-3 p-2 bg-emerald-50/80 border border-emerald-200 rounded text-[10px] text-emerald-900 space-y-0.5">
                      <div className="font-bold flex items-center gap-1">
                        <CheckCircle className="w-3 h-3 text-emerald-600" />
                        <span>Round-Trip Verification Passed</span>
                      </div>
                      <p className="text-[9px] text-emerald-700">
                        Parsed directly from &lt;LEDGER&gt; XML message without loss.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-slate-500">Tally XML &lt;LEDGER&gt; Master Snippet</span>
                  <Button variant="outline" size="sm" onClick={copyXmlToClipboard} className="text-xs h-7 gap-1">
                    {copiedXml ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedXml ? 'Copied' : 'Copy'}</span>
                  </Button>
                </div>
                <pre className="p-3 bg-slate-900 text-slate-100 rounded-xl text-[10px] font-mono overflow-x-auto max-h-72 leading-relaxed">
                  {previewXml}
                </pre>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <Button variant="outline" size="sm" onClick={() => setIsPreviewOpen(false)}>
                Back to Edit
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
};
