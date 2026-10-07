'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
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
  Info,
  ChevronDown
} from 'lucide-react';
import { MasterModalShell } from './ui/MasterModalShell';
import { PortalDropdown, DropdownItem } from './ui/PortalDropdown';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
import { Modal } from './ui/Modal';
import {
  getLedgerTallyPreview,
  createLedgerMaster,
  getUserLedgers,
  ImportedLedger,
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

export const TALLY_CANONICAL_STATES = [
  'Andaman & Nicobar Islands',
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chandigarh',
  'Chhattisgarh',
  'Dadra & Nagar Haveli and Daman & Diu',
  'Delhi',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jammu & Kashmir',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Ladakh',
  'Lakshadweep',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Other Territory',
  'Puducherry',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal'
];

export const TALLY_REGISTRATION_TYPES = [
  'Regular',
  'Composition',
  'Unregistered/Consumer',
  'Unknown'
];

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

  // Dirty state and validation
  const [isDirty, setIsDirty] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Portal Dropdowns
  const [isGroupDropdownOpen, setIsGroupDropdownOpen] = useState(false);
  const [isStateDropdownOpen, setIsStateDropdownOpen] = useState(false);
  const [isRegTypeDropdownOpen, setIsRegTypeDropdownOpen] = useState(false);

  const groupTriggerRef = useRef<HTMLButtonElement | null>(null);
  const stateTriggerRef = useRef<HTMLButtonElement | null>(null);
  const regTypeTriggerRef = useRef<HTMLButtonElement | null>(null);
  const nameInputRef = useRef<HTMLTextAreaElement | null>(null);

  // Preview state
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<LedgerTallyPreview | null>(null);
  const [previewXml, setPreviewXml] = useState<string>('');
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewTab, setPreviewTab] = useState<'screen' | 'xml'>('screen');
  const [copiedXml, setCopiedXml] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Ledger groups from API / existing
  const [availableLedgerGroups, setAvailableLedgerGroups] = useState<string[]>([
    'Sundry Creditors',
    'Sundry Debtors',
  ]);

  useEffect(() => {
    if (isOpen) {
      getUserLedgers('', 1000)
        .then((ledgers) => {
          const grpSet = new Set<string>(['Sundry Creditors', 'Sundry Debtors']);
          ledgers.forEach((l) => {
            if (l.group && l.group.trim()) grpSet.add(l.group.trim());
            if (l.parent_group && l.parent_group.trim()) grpSet.add(l.parent_group.trim());
          });
          setAvailableLedgerGroups(Array.from(grpSet).sort());
        })
        .catch(() => {});
    }
  }, [isOpen]);

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

      setValidationError(null);
      setIsDirty(false);

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
    setIsDirty(true);

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
    setIsDirty(true);
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
    if (!name.trim()) {
      setValidationError('Party Name cannot be empty.');
      nameInputRef.current?.focus();
      return;
    }

    setValidationError(null);
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
      setIsDirty(false);
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
      <MasterModalShell
        isOpen={isOpen}
        onClose={onClose}
        title="Create Party Ledger in Tally"
        badge={
          <Badge variant="neutral" size="sm" className="font-semibold text-[11px] bg-teal-50 text-teal-800 border-teal-200">
            {parentGroup}
          </Badge>
        }
        subtitle="Mirrors TallyPrime Ledger Creation screen with real statutory and GST registration tags."
        onSaveShortcut={handleSave}
        isDirty={isDirty}
        isSubmitting={isSubmitting}
        tipText="Tip: Press Ctrl+A to save, like in Tally."
        headerAction={
          savedTime ? (
            <Badge variant="success" size="sm" className="text-[10px] font-mono mr-2">
              {savedTime}
            </Badge>
          ) : undefined
        }
        footer={
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 w-full">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={handleResetToInvoice}
                className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1.5"
                title="Reset fields to original values extracted from invoice"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset to invoice</span>
              </Button>

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
                <span>Tally preview</span>
              </Button>
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
              <span className="text-[11px] text-slate-400 font-mono hidden md:inline">
                Esc: Close
              </span>

              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="text-xs"
              >
                Cancel
              </Button>

              <Button
                variant="primary"
                size="sm"
                type="button"
                onClick={handleSave}
                disabled={isSubmitting || !name.trim()}
                className="font-bold bg-teal-600 hover:bg-teal-700 text-white shadow-xs text-xs flex items-center gap-1.5"
                title="Save party ledger (Ctrl+A)"
              >
                <span>Save Ledger Master</span>
                <span className="text-[10px] text-teal-100 font-mono font-normal">
                  (Ctrl+A)
                </span>
              </Button>
            </div>
          </div>
        }
      >
        <div className="space-y-4 text-xs">
          {/* Validation Error Banner */}
          {validationError && (
            <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-rose-800 font-semibold text-xs animate-in fade-in duration-150">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          {/* Main 2-column layout mirroring Tally (5fr : 7fr) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* LEFT COLUMN: Name, Alias, Under, Mailing Details (5/12 width) */}
            <div className="lg:col-span-5 space-y-3.5 p-4 bg-white border border-slate-200 rounded-xl shadow-2xs">
              <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider pb-1.5 border-b border-slate-100 flex items-center justify-between">
                <span>General & Mailing Details</span>
                <span className="text-[10px] text-slate-400 font-normal">Section 1</span>
              </div>

              {/* Name - Auto-growing textarea for full visibility */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  Party Name <span className="text-rose-500">*</span>
                </label>
                <textarea
                  ref={nameInputRef}
                  rows={2}
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    setIsDirty(true);
                    if (validationError) setValidationError(null);
                  }}
                  placeholder="Full Party Name (e.g. M/S Kangra Distributors)"
                  required
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-bold font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 shadow-2xs resize-y min-h-[52px]"
                />
              </div>

              {/* Alias */}
              <div>
                <label className="block font-bold text-slate-700 mb-1 text-xs">
                  (alias)
                </label>
                <Input
                  value={alias}
                  onChange={(e) => {
                    setAlias(e.target.value);
                    setIsDirty(true);
                  }}
                  placeholder="Optional short code or vendor code"
                  className="text-xs h-[42px]"
                />
              </div>

              {/* Under (Parent Group) - Portal Dropdown */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  Under <span className="text-rose-500">*</span>
                </label>

                <button
                  ref={groupTriggerRef}
                  type="button"
                  onClick={() => setIsGroupDropdownOpen((prev) => !prev)}
                  className="w-full h-[42px] px-3 bg-white border border-slate-300 rounded-lg text-xs font-semibold text-slate-800 flex items-center justify-between hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 shadow-2xs text-left"
                >
                  <span className="truncate">{parentGroup}</span>
                  <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-2" />
                </button>

                <PortalDropdown
                  isOpen={isGroupDropdownOpen}
                  onClose={() => setIsGroupDropdownOpen(false)}
                  triggerRef={groupTriggerRef}
                  items={availableLedgerGroups.map((g) => ({
                    name: g,
                    isPinned: g === 'Sundry Creditors' || g === 'Sundry Debtors',
                  }))}
                  selectedItem={parentGroup}
                  onSelect={(grp) => {
                    setParentGroup(grp);
                    setIsDirty(true);
                  }}
                  headerText="Ledger Groups from Tally"
                  searchPlaceholder="Search ledger groups..."
                  bottomAction={{
                    label: '+ Create new group in Tally',
                    onClick: () => {
                      const typed = prompt('Enter new Ledger Group name:');
                      if (typed && typed.trim()) {
                        setParentGroup(typed.trim());
                        setIsDirty(true);
                      }
                    },
                  }}
                />
              </div>

              {/* Address - Inner scroll if long */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  Address
                </label>
                <textarea
                  rows={2}
                  value={address}
                  onChange={(e) => {
                    setAddress(e.target.value);
                    setIsDirty(true);
                  }}
                  placeholder="Street address, shop number, road..."
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 shadow-2xs resize-none overflow-y-auto max-h-[72px]"
                />
              </div>

              {/* State & Country */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-800 mb-1 text-xs">
                    State
                  </label>

                  <button
                    ref={stateTriggerRef}
                    type="button"
                    onClick={() => setIsStateDropdownOpen((prev) => !prev)}
                    className="w-full h-[42px] px-3 bg-white border border-slate-300 rounded-lg text-xs font-semibold text-slate-800 flex items-center justify-between shadow-2xs text-left"
                  >
                    <span className="truncate">{state}</span>
                    <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-1" />
                  </button>

                  <PortalDropdown
                    isOpen={isStateDropdownOpen}
                    onClose={() => setIsStateDropdownOpen(false)}
                    triggerRef={stateTriggerRef}
                    items={TALLY_CANONICAL_STATES.map((s) => ({ name: s }))}
                    selectedItem={state}
                    onSelect={(s) => {
                      setState(s);
                      setIsDirty(true);
                    }}
                    headerText="Indian States & UTs (Tally Standard)"
                    searchPlaceholder="Search state..."
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1 text-xs">
                    Country
                  </label>
                  <Input
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="text-xs font-medium bg-slate-100 h-[42px]"
                    readOnly
                  />
                </div>
              </div>

              {/* Pincode */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  Pincode
                </label>
                <Input
                  value={pincode}
                  onChange={(e) => {
                    setPincode(e.target.value.replace(/\D/g, '').substring(0, 6));
                    setIsDirty(true);
                  }}
                  placeholder="6-digit PIN"
                  maxLength={6}
                  className="text-xs font-mono h-[42px]"
                />
              </div>
            </div>

            {/* RIGHT COLUMN: Tax Registration Details (7/12 width) */}
            <div className="lg:col-span-7 space-y-3.5 p-4 bg-teal-50/40 border border-teal-200/90 rounded-xl shadow-2xs">
              <div className="text-[11px] font-bold text-teal-950 uppercase tracking-wider pb-1.5 border-b border-teal-200 flex items-center justify-between">
                <span>Tax Registration Details</span>
                <Badge variant="neutral" size="sm" className="bg-teal-100 text-teal-800 text-[10px] font-semibold">
                  Tally Statutory
                </Badge>
              </div>

              {/* Registration Type - Portal Dropdown */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  Registration Type
                </label>

                <button
                  ref={regTypeTriggerRef}
                  type="button"
                  onClick={() => setIsRegTypeDropdownOpen((prev) => !prev)}
                  className="w-full h-[42px] px-3 bg-white border border-slate-300 rounded-lg text-xs font-semibold text-slate-800 flex items-center justify-between shadow-2xs text-left"
                >
                  <span className="truncate">{registrationType}</span>
                  <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-2" />
                </button>

                <PortalDropdown
                  isOpen={isRegTypeDropdownOpen}
                  onClose={() => setIsRegTypeDropdownOpen(false)}
                  triggerRef={regTypeTriggerRef}
                  items={TALLY_REGISTRATION_TYPES.map((t) => ({ name: t }))}
                  selectedItem={registrationType}
                  onSelect={(t) => {
                    setRegistrationType(t);
                    setIsDirty(true);
                  }}
                  headerText="GST Registration Type"
                  searchPlaceholder="Select type..."
                  enableSearch={false}
                />
              </div>

              {/* GSTIN / UIN */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-800 text-xs">
                    GSTIN / UIN
                  </label>
                  {gstin && gstin.length === 15 && (
                    <Badge variant="success" size="sm" className="text-[10px] bg-emerald-100 text-emerald-800 font-semibold">
                      15-Digit Format Valid
                    </Badge>
                  )}
                </div>
                <Input
                  value={gstin}
                  onChange={(e) => handleGstinChange(e.target.value)}
                  placeholder="15-digit GSTIN (e.g. 02AAACP1234F1Z5)"
                  maxLength={15}
                  className="text-xs font-mono font-bold uppercase bg-white h-[42px]"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  State and PAN are automatically extracted from the first 12 characters of GSTIN.
                </p>
              </div>

              {/* PAN / IT No. */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  PAN / IT No.
                </label>
                <Input
                  value={pan}
                  onChange={(e) => {
                    setPan(e.target.value.toUpperCase().substring(0, 10));
                    setIsDirty(true);
                  }}
                  placeholder="10-digit PAN (e.g. AAACP1234F)"
                  maxLength={10}
                  className="text-xs font-mono uppercase bg-white h-[42px]"
                />
              </div>

              {/* Informative Box */}
              <div className="p-3.5 bg-white border border-teal-200 rounded-xl space-y-1.5 text-xs text-slate-700">
                <div className="flex items-center gap-1.5 font-bold text-teal-900">
                  <CheckCircle className="w-4 h-4 text-teal-600 shrink-0" />
                  <span>Authoritative Tally Master Generator</span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Generates full Tally XML ledger masters with <code>SRCOFGSTDETAILS</code>, <code>LEDSTATENAME</code>, and <code>PARTYGSTIN</code> strictly matching authentic Tally exports.
                </p>
              </div>
            </div>
          </div>
        </div>
      </MasterModalShell>

      {/* HOW IT WILL LOOK IN TALLY MODAL */}
      {isPreviewOpen && (
        <Modal
          isOpen={isPreviewOpen}
          onClose={() => setIsPreviewOpen(false)}
          title={
            <div className="flex items-center justify-between w-full pr-6">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-teal-600 text-white font-bold flex items-center justify-center text-xs">
                  T
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">
                    TallyPrime Ledger Creation Preview
                  </h3>
                  <p className="text-[10px] text-slate-500">
                    Parsed directly from generated XML snippet — verifying exact Tally fields
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
                  {/* Left Column */}
                  <div className="space-y-2 border-r border-[#d4af37]/30 pr-3">
                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Name:</span>
                      <span className="font-bold text-sm text-[#111]">{previewData?.name || name}</span>
                    </div>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Under:</span>
                      <span className="font-bold text-teal-900 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                        {previewData?.parent_group || parentGroup}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Mailing Details:</span>
                      <div className="text-[11px] text-[#333] pl-2 border-l-2 border-[#d4af37]/40 space-y-0.5">
                        <p className="font-bold">{previewData?.name || name}</p>
                        {address && (
                          <p className="whitespace-pre-line text-[#555]">{address}</p>
                        )}
                        <p>
                          <strong>State:</strong> {previewData?.state || state}
                        </p>
                        <p>
                          <strong>Country:</strong> {previewData?.country || country}
                        </p>
                        {pincode && (
                          <p>
                            <strong>Pincode:</strong> {pincode}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right Column */}
                  <div className="space-y-2 pl-1">
                    <div className="p-2 bg-amber-50/70 border border-amber-300 rounded space-y-1">
                      <span className="text-[10px] font-bold text-amber-900 block">Tax Registration Details:</span>
                      <div>
                        <strong>PAN/IT No.:</strong> {previewData?.pan || pan || 'None'}
                      </div>
                      <div>
                        <strong>Registration type:</strong>{' '}
                        <span className="font-bold text-teal-800">
                          {previewData?.registration_type || registrationType}
                        </span>
                      </div>
                      <div>
                        <strong>GSTIN/UIN:</strong>{' '}
                        <span className="font-bold font-mono">
                          {previewData?.gstin || gstin || 'None'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="relative">
                <button
                  type="button"
                  onClick={copyXmlToClipboard}
                  className="absolute right-3 top-3 p-1.5 rounded bg-slate-800 text-white hover:bg-slate-700 text-xs font-semibold flex items-center gap-1 shadow-md"
                >
                  {copiedXml ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedXml ? 'Copied' : 'Copy XML'}</span>
                </button>
                <pre className="p-3.5 bg-slate-900 text-teal-400 rounded-xl text-[11px] font-mono overflow-x-auto max-h-96 leading-relaxed">
                  {previewXml}
                </pre>
              </div>
            )}
          </div>
        </Modal>
      )}
    </>
  );
};
