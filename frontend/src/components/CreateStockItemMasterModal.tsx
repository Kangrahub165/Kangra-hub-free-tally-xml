'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Package,
  Layers,
  Sparkles,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  Info,
  X,
  Plus,
  Eye,
  Code,
  Check,
  Copy,
  ChevronDown
} from 'lucide-react';
import { MasterModalShell } from './ui/MasterModalShell';
import { PortalDropdown, DropdownItem } from './ui/PortalDropdown';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
import { Modal } from './ui/Modal';
import {
  getStockItemGroups,
  getStockItemUnits,
  getStockItemTallyPreview,
  StockGroupItem,
  StockUnitItem,
  ImportedStockItem,
  StockItemTallyPreview
} from '@/lib/api';

export interface CreateStockItemMasterModalProps {
  isOpen: boolean;
  onClose: () => void;
  item: {
    item_name: string;
    alias?: string;
    hsn_sac?: string;
    hsn_description?: string;
    uom?: string;
    gst_rate?: number;
    cgst_rate?: number;
    sgst_rate?: number;
    igst_rate?: number;
    parent_group?: string;
    taxability?: string;
    type_of_supply?: string;
    alternate_uom?: string;
    pack_multiplier?: number;
    matched_stock_item?: string;
    saved_draft_version?: number;
  } | null;
  initialInvoiceValues?: {
    item_name: string;
    hsn_sac?: string;
    uom?: string;
    gst_rate?: number;
  } | null;
  existingStockItems: ImportedStockItem[];
  allNewItems?: Array<{ item_name: string; originalIndex: number }>;
  currentNewItemIndex?: number;
  isInterstate?: boolean;
  onSaveMaster: (
    savedData: {
      name: string;
      alias?: string;
      parent_group: string;
      uom: string;
      hsn?: string;
      hsn_description?: string;
      gst_rate: number;
      taxability: string;
      type_of_supply: string;
      additional_units?: string;
      conversion?: number;
      saved_draft_version?: number;
    },
    saveAndNext?: boolean,
    applyToAllNew?: boolean
  ) => Promise<void>;
  onUseExistingItem?: (existingName: string) => void;
}

const COMMON_GST_SLABS = [0, 5, 12, 18, 28, 40];

export const CreateStockItemMasterModal: React.FC<CreateStockItemMasterModalProps> = ({
  isOpen,
  onClose,
  item,
  initialInvoiceValues,
  existingStockItems = [],
  allNewItems = [],
  currentNewItemIndex = 0,
  isInterstate = false,
  onSaveMaster,
  onUseExistingItem,
}) => {
  // Form fields (Left column: General & Units)
  const [name, setName] = useState('');
  const [alias, setAlias] = useState('');
  const [parentGroup, setParentGroup] = useState('Primary');
  const [baseUnit, setBaseUnit] = useState('');
  const [hasAltUnit, setHasAltUnit] = useState(false);
  const [altUnit, setAltUnit] = useState('');
  const [conversion, setConversion] = useState<number | string>('1');

  // Statutory Details (Right column)
  const [hsn, setHsn] = useState('');
  const [hsnDescription, setHsnDescription] = useState('');
  const [taxability, setTaxability] = useState('Taxable');
  const [gstRate, setGstRate] = useState<number>(18);
  const [typeOfSupply, setTypeOfSupply] = useState('Goods');
  const [reportingUqc, setReportingUqc] = useState('');
  const [applyToAll, setApplyToAll] = useState(false);

  // Version tracking & dirty tracking
  const [version, setVersion] = useState<number>(1);
  const [savedTime, setSavedTime] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Groups and Units lists from API
  const [apiGroups, setApiGroups] = useState<StockGroupItem[]>([]);
  const [apiUnits, setApiUnits] = useState<StockUnitItem[]>([]);
  const [importDateStr, setImportDateStr] = useState<string>('');

  // Dropdown portal states and refs
  const [isGroupDropdownOpen, setIsGroupDropdownOpen] = useState(false);
  const [isBaseUnitDropdownOpen, setIsBaseUnitDropdownOpen] = useState(false);
  const [isAltUnitDropdownOpen, setIsAltUnitDropdownOpen] = useState(false);
  const [isTaxabilityDropdownOpen, setIsTaxabilityDropdownOpen] = useState(false);
  const [isSupplyDropdownOpen, setIsSupplyDropdownOpen] = useState(false);

  const groupTriggerRef = useRef<HTMLButtonElement | null>(null);
  const baseUnitTriggerRef = useRef<HTMLButtonElement | null>(null);
  const altUnitTriggerRef = useRef<HTMLButtonElement | null>(null);
  const taxabilityTriggerRef = useRef<HTMLButtonElement | null>(null);
  const supplyTriggerRef = useRef<HTMLButtonElement | null>(null);
  const nameInputRef = useRef<HTMLTextAreaElement | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);

  // Tally Preview state
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<StockItemTallyPreview | null>(null);
  const [previewXml, setPreviewXml] = useState<string>('');
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewTab, setPreviewTab] = useState<'screen' | 'xml'>('screen');
  const [copiedXml, setCopiedXml] = useState(false);

  // Load groups & units from API on modal open
  useEffect(() => {
    if (isOpen) {
      loadGroupsAndUnits();
    }
  }, [isOpen]);

  const loadGroupsAndUnits = async () => {
    try {
      const [groups, units] = await Promise.all([
        getStockItemGroups().catch(() => []),
        getStockItemUnits().catch(() => []),
      ]);
      setApiGroups(groups);
      setApiUnits(units);
      if (groups.length > 0 && (groups[0] as any).imported_at) {
        setImportDateStr((groups[0] as any).imported_at);
      } else {
        const d = new Date();
        setImportDateStr(d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }));
      }
    } catch {
      // Graceful fallback
    }
  };

  // Extract authoritatively from existingStockItems prop + api
  const tallyUnitsList = useMemo(() => {
    const counts: Record<string, number> = {};

    // 1. Scan existingStockItems prop
    existingStockItems.forEach((si) => {
      if (si.base_units) {
        const u = si.base_units.trim().toUpperCase();
        if (u && !u.startsWith('NOT')) {
          counts[u] = (counts[u] || 0) + 1;
        }
      }
      if (si.additional_units) {
        const alt = si.additional_units.trim().toUpperCase();
        if (alt && !alt.startsWith('NOT')) {
          counts[alt] = (counts[alt] || 0) + 1;
        }
      }
    });

    // 2. Merge apiUnits
    apiUnits.forEach((u) => {
      const uname = u.name.trim().toUpperCase();
      if (uname && !uname.startsWith('NOT')) {
        counts[uname] = Math.max(counts[uname] || 0, u.item_count || 1);
      }
    });

    return Object.entries(counts)
      .map(([name, count]) => ({ name, item_count: count }))
      .sort((a, b) => b.item_count - a.item_count || a.name.localeCompare(b.name));
  }, [existingStockItems, apiUnits]);

  const tallyGroupsList = useMemo(() => {
    const counts: Record<string, number> = {};

    // 1. Scan existingStockItems prop
    existingStockItems.forEach((si) => {
      const p = (si.parent || 'Primary').trim();
      if (p) {
        counts[p] = (counts[p] || 0) + 1;
      }
    });

    // 2. Merge apiGroups
    apiGroups.forEach((g) => {
      const gname = g.name.trim();
      if (gname) {
        counts[gname] = Math.max(counts[gname] || 0, g.item_count || 1);
      }
    });

    const hasAnyGroups = Object.keys(counts).length > 0;
    if (!hasAnyGroups) {
      return [];
    }

    if (!counts['Primary']) {
      counts['Primary'] = 0;
    }

    const result: DropdownItem[] = [
      { name: 'Primary', item_count: counts['Primary'], isPinned: true },
    ];

    Object.keys(counts)
      .filter((g) => g !== 'Primary')
      .sort((a, b) => a.localeCompare(b))
      .forEach((g) => {
        result.push({ name: g, item_count: counts[g] });
      });

    return result;
  }, [existingStockItems, apiGroups]);

  // Pre-fill form from item when opening
  useEffect(() => {
    if (item && isOpen) {
      const rawName = (item.item_name || '').trim();
      setName(rawName);
      setAlias(item.alias || '');

      // Suggest group from existing or default to Primary
      setParentGroup(item.parent_group || 'Primary');

      // Base unit auto-fill rule (PRD §2.3):
      // Only auto-fill if the invoice UOM exists in Tally units!
      const invoiceUom = (item.uom || '').trim().toUpperCase();
      const unitMatches = tallyUnitsList.some((u) => u.name.toUpperCase() === invoiceUom);
      if (unitMatches) {
        setBaseUnit(invoiceUom);
      } else {
        // If not in Tally, leave empty so user picks a valid unit
        setBaseUnit('');
      }

      // Alternate unit
      if (item.alternate_uom && item.pack_multiplier && item.pack_multiplier >= 1) {
        setHasAltUnit(true);
        const altUpper = item.alternate_uom.trim().toUpperCase();
        setAltUnit(altUpper);
        setConversion(item.pack_multiplier);
      } else {
        setHasAltUnit(false);
        // Default altUnit to second available unit if exists
        const fallbackAlt = tallyUnitsList.find((u) => u.name !== invoiceUom)?.name || '';
        setAltUnit(fallbackAlt);
        setConversion('1');
      }

      // HSN
      setHsn((item.hsn_sac || '').trim());
      setHsnDescription((item.hsn_description || '').trim());

      // Taxability & GST rate
      const taxMode = item.taxability || 'Taxable';
      setTaxability(taxMode);

      let calcRate = 18;
      if (item.gst_rate !== undefined && item.gst_rate !== null) {
        calcRate = Number(item.gst_rate);
      } else if (item.igst_rate && item.igst_rate > 0) {
        calcRate = Number(item.igst_rate);
      } else if ((item.cgst_rate || 0) > 0 || (item.sgst_rate || 0) > 0) {
        calcRate = Number(item.cgst_rate || 0) + Number(item.sgst_rate || 0);
      }
      setGstRate(calcRate);

      setTypeOfSupply(item.type_of_supply || 'Goods');
      setApplyToAll(false);
      setValidationError(null);

      if (item.saved_draft_version) {
        setVersion(item.saved_draft_version);
        setSavedTime('Previously Saved');
      } else {
        setVersion(1);
        setSavedTime(null);
      }
      setIsDirty(false);
    }
  }, [item, isOpen, tallyUnitsList]);

  // Invoice unit mismatch check
  const invoiceUom = (item?.uom || '').trim().toUpperCase();
  const isInvoiceUomMissingInTally = Boolean(
    invoiceUom && tallyUnitsList.length > 0 && !tallyUnitsList.some((u) => u.name.toUpperCase() === invoiceUom)
  );

  // Duplicate Check
  const duplicateMatch = useMemo(() => {
    if (!name.trim()) return null;
    const clean = name.trim().toLowerCase().replace(/\s+/g, ' ');
    return existingStockItems.find(
      (si) => si.name.trim().toLowerCase().replace(/\s+/g, ' ') === clean
    );
  }, [name, existingStockItems]);

  // Reset to Invoice Values
  const handleResetToInvoice = () => {
    if (!initialInvoiceValues && !item) return;
    const source = initialInvoiceValues || item!;
    setName(source.item_name || '');
    setAlias('');
    setHsn(source.hsn_sac || '');
    setHsnDescription('');
    const rawU = (source.uom || '').trim().toUpperCase();
    const matches = tallyUnitsList.some((u) => u.name.toUpperCase() === rawU);
    setBaseUnit(matches ? rawU : '');
    setGstRate(source.gst_rate !== undefined ? Number(source.gst_rate) : 18);
    setParentGroup('Primary');
    setTaxability('Taxable');
    setTypeOfSupply('Goods');
    setHasAltUnit(false);
    setIsDirty(true);
  };

  // Open "How it will look in Tally" preview
  const handleOpenTallyPreview = async () => {
    if (!name.trim()) return;
    setIsLoadingPreview(true);
    setIsPreviewOpen(true);
    try {
      const convNum = hasAltUnit && conversion ? Number(conversion) : undefined;
      const res = await getStockItemTallyPreview({
        name: name.trim(),
        hsn: hsn.trim() || undefined,
        hsn_description: hsnDescription.trim() || undefined,
        uom: (baseUnit || 'NOS').trim().toUpperCase(),
        parent_group: (parentGroup || 'Primary').trim(),
        gst_rate: taxability === 'Taxable' ? Number(gstRate) || 0 : 0,
        taxability,
        type_of_supply: typeOfSupply,
        additional_units: hasAltUnit && altUnit.trim() ? altUnit.trim().toUpperCase() : undefined,
        conversion: convNum,
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

  // Validate and submit
  const handleSubmit = async (andNext: boolean = false) => {
    if (!name.trim()) {
      setValidationError('Item Name cannot be empty.');
      nameInputRef.current?.focus();
      return;
    }

    if (!baseUnit.trim()) {
      setValidationError('Please select a valid Base Unit from your Tally units.');
      baseUnitTriggerRef.current?.focus();
      return;
    }

    if (hasAltUnit && (!altUnit.trim() || altUnit.trim().toUpperCase() === baseUnit.trim().toUpperCase())) {
      setValidationError('Alternate unit must be distinct from base unit.');
      altUnitTriggerRef.current?.focus();
      return;
    }

    const convVal = Number(conversion);
    if (hasAltUnit && (!convVal || convVal <= 0)) {
      setValidationError('Conversion quantity must be at least 1.');
      return;
    }

    setValidationError(null);
    setIsSubmitting(true);
    try {
      const newVer = version + 1;
      const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      const dataToSave = {
        name: name.trim(),
        alias: alias.trim() || undefined,
        parent_group: (parentGroup || 'Primary').trim(),
        uom: baseUnit.trim().toUpperCase(),
        hsn: hsn.trim() || undefined,
        hsn_description: hsnDescription.trim() || undefined,
        gst_rate: taxability === 'Taxable' ? Number(gstRate) || 0 : 0,
        taxability,
        type_of_supply: typeOfSupply,
        additional_units: hasAltUnit && altUnit.trim() ? altUnit.trim().toUpperCase() : undefined,
        conversion: hasAltUnit && conversion ? Number(conversion) : undefined,
        saved_draft_version: newVer,
      };

      await onSaveMaster(dataToSave, andNext, applyToAll);
      setVersion(newVer);
      setSavedTime(`Saved v${newVer}, ${nowStr}`);
      setIsDirty(false);

      if (!andNext) {
        onClose();
      }
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

  const totalNewCount = allNewItems.length;
  const isMultiNew = totalNewCount > 1;
  const hasNext = isMultiNew && currentNewItemIndex < totalNewCount - 1;

  // Split rate preview
  const halfRate = (Number(gstRate) / 2).toFixed(2);

  return (
    <>
      <MasterModalShell
        isOpen={isOpen}
        onClose={onClose}
        title="Create Stock Item Master in Tally"
        badge={
          isMultiNew ? (
            <Badge variant="neutral" size="sm" className="font-bold text-[11px] bg-slate-100 text-slate-700">
              Item {currentNewItemIndex + 1} of {totalNewCount}
            </Badge>
          ) : undefined
        }
        subtitle="Mirrors TallyPrime Stock Item Creation. Saved values go verbatim into XML without alteration."
        onSaveShortcut={() => handleSubmit(hasNext)}
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
                className="text-xs font-semibold text-emerald-800 border-emerald-300 hover:bg-emerald-50 flex items-center gap-1.5"
                title="Preview how this item appears in TallyPrime parsed from the generated XML"
              >
                <Eye className="w-3.5 h-3.5 text-emerald-600" />
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

              {hasNext && (
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => handleSubmit(true)}
                  disabled={isSubmitting || !name.trim()}
                  className="font-bold border-emerald-300 text-emerald-800 hover:bg-emerald-50 flex items-center gap-1.5 text-xs shadow-2xs"
                  title="Save current item and move to next item (Ctrl+A)"
                >
                  <span>Save & Next</span>
                  <span className="text-[10px] text-emerald-600 font-mono font-normal">(Ctrl+A)</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              )}

              <Button
                variant="primary"
                size="sm"
                type="button"
                onClick={() => handleSubmit(false)}
                disabled={isSubmitting || !name.trim()}
                className="font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs text-xs flex items-center gap-1.5"
                title="Save master to invoice and close (Ctrl+A)"
              >
                <span>{hasNext ? 'Save Item' : 'Save Master'}</span>
                <span className="text-[10px] text-emerald-100 font-mono font-normal">
                  ({hasNext ? 'Enter' : 'Ctrl+A'})
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

          {/* Duplicate warning banner */}
          {duplicateMatch && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start justify-between gap-3 text-amber-900 animate-in fade-in duration-200">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-amber-800">
                    Item already exists in Tally masters: &quot;{duplicateMatch.name}&quot;
                  </p>
                  <p className="text-[11px] text-amber-700 mt-0.5">
                    Group: {duplicateMatch.parent || 'Primary'} &bull; Unit: {duplicateMatch.base_units} &bull; GST: {duplicateMatch.gst_rate || 0}%
                  </p>
                </div>
              </div>
              {onUseExistingItem && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    onUseExistingItem(duplicateMatch.name);
                    onClose();
                  }}
                  className="shrink-0 text-xs font-bold text-amber-800 border-amber-300 hover:bg-amber-100 bg-white"
                >
                  Use Existing Item
                </Button>
              )}
            </div>
          )}

          {/* MAIN 2-COLUMN LAYOUT MIRRORING TALLY PRIME (5fr : 7fr) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* LEFT COLUMN: Name, Alias, Under (Group), Units, Alternate Units (5/12 width) */}
            <div className="lg:col-span-5 space-y-3.5 p-4 bg-white border border-slate-200 rounded-xl shadow-2xs">
              <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider pb-1.5 border-b border-slate-100 flex items-center justify-between">
                <span>Item Identity & Units</span>
                <span className="text-[10px] text-slate-400 font-normal">Section 1</span>
              </div>

              {/* Item Name - Auto-growing textarea up to 3 lines so full name is visible */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                    <span>Item Name</span>
                    <span className="text-rose-500 font-bold">*</span>
                  </label>
                  <Badge variant="neutral" size="sm" className="text-[10px] bg-slate-100 text-slate-600 flex items-center gap-1">
                    <Sparkles className="w-2.5 h-2.5 text-emerald-600" />
                    From invoice
                  </Badge>
                </div>
                <textarea
                  ref={nameInputRef}
                  rows={2}
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    setIsDirty(true);
                    if (validationError) setValidationError(null);
                  }}
                  placeholder="Full item name as printed on bill or in Tally..."
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-bold font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-2xs resize-y min-h-[52px]"
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
                  placeholder="Optional item shorthand or SKU"
                  className="text-xs h-[42px]"
                />
              </div>

              {/* Stock Group (Parent) - Portal Dropdown */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                    <Layers className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Under (Stock Group)</span>
                    <span className="text-rose-500 font-bold">*</span>
                  </label>
                  <span className="text-[10.5px] font-semibold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200">
                    {parentGroup === 'Primary' ? 'Primary' : 'Selected Group'}
                  </span>
                </div>

                <button
                  ref={groupTriggerRef}
                  type="button"
                  onClick={() => setIsGroupDropdownOpen((prev) => !prev)}
                  className="w-full h-[42px] px-3 bg-white border border-slate-300 rounded-lg text-xs font-semibold text-slate-800 flex items-center justify-between hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs text-left"
                >
                  <span className="truncate">{parentGroup || 'Primary'}</span>
                  <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-2" />
                </button>

                <PortalDropdown
                  isOpen={isGroupDropdownOpen}
                  onClose={() => setIsGroupDropdownOpen(false)}
                  triggerRef={groupTriggerRef}
                  items={tallyGroupsList}
                  selectedItem={parentGroup}
                  onSelect={(grp) => {
                    setParentGroup(grp);
                    setIsDirty(true);
                  }}
                  headerText={
                    tallyGroupsList.length > 0
                      ? `${tallyGroupsList.length} groups from Tally · imported ${importDateStr}`
                      : 'No groups imported yet'
                  }
                  emptyMessage="No groups imported yet. Import your Tally stock items."
                  searchPlaceholder="Search or type stock group..."
                  bottomAction={{
                    label: '+ Create new group in Tally',
                    onClick: () => {
                      const typed = prompt('Enter new Stock Group name:');
                      if (typed && typed.trim()) {
                        setParentGroup(typed.trim());
                        setIsDirty(true);
                      }
                    },
                  }}
                />
              </div>

              {/* Units (Base Unit = SMALL Unit) - Portal Dropdown */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-800 text-xs">
                    Units (Base Unit) <span className="text-rose-500">*</span>
                  </label>
                  {baseUnit && (
                    <span className="text-[10px] font-mono text-emerald-800 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200 font-semibold">
                      Tally Unit
                    </span>
                  )}
                </div>

                <button
                  ref={baseUnitTriggerRef}
                  type="button"
                  onClick={() => setIsBaseUnitDropdownOpen((prev) => !prev)}
                  className={`w-full h-[42px] px-3 bg-white border rounded-lg text-xs font-mono font-bold flex items-center justify-between shadow-2xs text-left ${
                    !baseUnit
                      ? 'border-amber-300 bg-amber-50/40 text-amber-900'
                      : 'border-slate-300 text-slate-900'
                  }`}
                >
                  <span className="truncate">{baseUnit || '-- Select Tally Unit --'}</span>
                  <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-2" />
                </button>

                {/* Amber Warning when invoice UOM is missing in Tally */}
                {isInvoiceUomMissingInTally && !baseUnit && (
                  <p className="text-[11px] text-amber-800 font-semibold mt-1 bg-amber-50/80 border border-amber-200 px-2 py-1 rounded-md">
                    Unit &apos;{invoiceUom}&apos; from the invoice is not in Tally. Select a Tally unit.
                  </p>
                )}

                <p className="text-[11px] text-slate-400 mt-1">
                  Base unit is the smaller unit.
                </p>

                <PortalDropdown
                  isOpen={isBaseUnitDropdownOpen}
                  onClose={() => setIsBaseUnitDropdownOpen(false)}
                  triggerRef={baseUnitTriggerRef}
                  items={tallyUnitsList}
                  selectedItem={baseUnit}
                  onSelect={(u) => {
                    setBaseUnit(u);
                    setIsDirty(true);
                    if (validationError) setValidationError(null);
                  }}
                  headerText={
                    tallyUnitsList.length > 0
                      ? `${tallyUnitsList.length} units from Tally · imported ${importDateStr}`
                      : 'No units found. Import your Tally stock items first'
                  }
                  emptyMessage="No units found. Import your Tally stock items first."
                  searchPlaceholder="Search Tally units..."
                  bottomAction={{
                    label: '+ Create new unit in Tally',
                    onClick: () => {
                      const typed = prompt('Enter new unit symbol (e.g. PKT, PCS):');
                      if (typed && typed.trim()) {
                        setBaseUnit(typed.trim().toUpperCase());
                        setIsDirty(true);
                      }
                    },
                  }}
                />
              </div>

              {/* Alternate Units & Pack Conversion (PRD Rule 4 & Section 5) */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2.5">
                <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-800 text-xs">
                  <input
                    type="checkbox"
                    checked={hasAltUnit}
                    onChange={(e) => {
                      setHasAltUnit(e.target.checked);
                      setIsDirty(true);
                    }}
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 w-4 h-4"
                  />
                  <span>Alternate units (BIG unit, e.g. CASE, BOX)</span>
                </label>

                {hasAltUnit && (
                  <div className="space-y-3 pt-2 border-t border-slate-200 animate-in fade-in duration-150">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                        Alternate unit (BIG)
                      </label>

                      <button
                        ref={altUnitTriggerRef}
                        type="button"
                        onClick={() => setIsAltUnitDropdownOpen((prev) => !prev)}
                        className="w-full h-[40px] px-3 bg-white border border-slate-300 rounded-lg text-xs font-mono font-bold text-slate-900 flex items-center justify-between shadow-2xs text-left"
                      >
                        <span className="truncate">{altUnit || '-- Select Alternate Unit --'}</span>
                        <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-2" />
                      </button>

                      <PortalDropdown
                        isOpen={isAltUnitDropdownOpen}
                        onClose={() => setIsAltUnitDropdownOpen(false)}
                        triggerRef={altUnitTriggerRef}
                        // PRD Section 2: Alternate unit excludes the unit chosen as base!
                        items={tallyUnitsList.filter((u) => u.name.toUpperCase() !== baseUnit.toUpperCase())}
                        selectedItem={altUnit}
                        onSelect={(u) => {
                          setAltUnit(u);
                          setIsDirty(true);
                        }}
                        headerText={
                          tallyUnitsList.length > 0
                            ? `${tallyUnitsList.length} units from Tally · imported ${importDateStr}`
                            : 'No units found'
                        }
                        emptyMessage="No matching alternate units found."
                        searchPlaceholder="Search alternate units..."
                        bottomAction={{
                          label: '+ Create new unit in Tally',
                          onClick: () => {
                            const typed = prompt('Enter new alternate unit symbol (e.g. CASE, BOX):');
                            if (typed && typed.trim()) {
                              setAltUnit(typed.trim().toUpperCase());
                              setIsDirty(true);
                            }
                          },
                        }}
                      />
                    </div>

                    {/* PRD Rule 4 Conversion Line: where 1 [ALT] = [N] [BASE] */}
                    <div className="p-3 bg-emerald-50/80 border border-emerald-200 rounded-lg space-y-1.5">
                      <label className="block text-[11px] font-bold text-emerald-950">
                        where 1 {altUnit || 'CASE'} = [N] {baseUnit || 'PKT'}
                      </label>
                      <div className="flex items-center gap-2 font-mono">
                        <span className="text-xs font-bold text-slate-700 bg-white px-3 py-2 rounded-md border border-slate-300 shrink-0">
                          1 {altUnit || 'CASE'} =
                        </span>
                        <Input
                          type="number"
                          min="1"
                          step="1"
                          value={conversion}
                          onChange={(e) => {
                            setConversion(e.target.value);
                            setIsDirty(true);
                          }}
                          placeholder="192"
                          className="text-xs font-mono font-bold w-28 text-center bg-white h-[38px]"
                        />
                        <span className="text-xs font-bold text-slate-800 shrink-0">
                          {baseUnit || 'PKT'}
                        </span>
                      </div>
                      <p className="text-[10.5px] text-emerald-800 mt-1 leading-relaxed">
                        Formula in Tally: <strong>1 {altUnit || 'CASE'} = {conversion || 1} {baseUnit || 'PKT'}</strong> (Denominator: {conversion || 1}, Conversion: 1)
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT COLUMN: Statutory Details (7/12 width) */}
            <div className="lg:col-span-7 space-y-3.5 p-4 bg-emerald-50/40 border border-emerald-200/90 rounded-xl shadow-2xs">
              <div className="text-[11px] font-bold text-emerald-950 uppercase tracking-wider pb-1.5 border-b border-emerald-200 flex items-center justify-between">
                <span>Statutory Details</span>
                <Badge variant="neutral" size="sm" className="bg-emerald-100 text-emerald-800 text-[10px] font-semibold">
                  Specify Details Here
                </Badge>
              </div>

              {/* GST Applicability */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  GST Applicability
                </label>
                <div className="w-full rounded-lg border border-slate-200 bg-slate-100/80 px-3 py-2 text-xs font-semibold text-slate-700">
                  Applicable
                </div>
              </div>

              {/* HSN/SAC Code & Description */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="font-bold text-slate-800 text-xs">
                    HSN/SAC Details: <span className="text-emerald-700 font-semibold text-[11px]">Specify Details Here</span>
                  </label>
                  {hsn && (
                    <Badge variant="neutral" size="sm" className="text-[10px] bg-white text-slate-600">
                      From invoice
                    </Badge>
                  )}
                </div>
                <div className="grid grid-cols-12 gap-2">
                  <div className="col-span-4 min-w-[140px]">
                    <Input
                      value={hsn}
                      onChange={(e) => {
                        setHsn(e.target.value.replace(/\D/g, ''));
                        setIsDirty(true);
                      }}
                      placeholder="HSN (8 digits)"
                      maxLength={8}
                      className="text-xs font-mono font-bold bg-white h-[42px]"
                    />
                  </div>
                  <div className="col-span-8">
                    <Input
                      value={hsnDescription}
                      onChange={(e) => {
                        setHsnDescription(e.target.value);
                        setIsDirty(true);
                      }}
                      placeholder="HSN Description (e.g. Biscuits, Soft Drinks)"
                      className="text-xs bg-white h-[42px]"
                    />
                  </div>
                </div>
              </div>

              {/* Taxability and Type of Supply */}
              <div>
                <label className="block font-bold text-slate-800 mb-1 text-xs">
                  GST Rate Details: <span className="text-emerald-700 font-semibold text-[11px]">Specify Details Here</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Taxability
                    </label>
                    <select
                      value={taxability}
                      onChange={(e) => {
                        setTaxability(e.target.value);
                        setIsDirty(true);
                      }}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold shadow-2xs h-[42px] focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                    >
                      <option value="Taxable">Taxable</option>
                      <option value="Exempt">Exempt</option>
                      <option value="Nil Rated">Nil Rated</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Type of Supply
                    </label>
                    <select
                      value={typeOfSupply}
                      onChange={(e) => {
                        setTypeOfSupply(e.target.value);
                        setIsDirty(true);
                      }}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold shadow-2xs h-[42px] focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                    >
                      <option value="Goods">Goods</option>
                      <option value="Services">Services</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* GST Rate % with Wrap Chips (Never cut off) */}
              {taxability === 'Taxable' ? (
                <div className="p-3.5 bg-white border border-emerald-200 rounded-xl space-y-2.5">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <label className="font-bold text-slate-800 text-xs">GST Rate %</label>
                    <div className="flex items-center flex-wrap gap-1.5">
                      {COMMON_GST_SLABS.map((slab) => (
                        <button
                          key={slab}
                          type="button"
                          onClick={() => {
                            setGstRate(slab);
                            setIsDirty(true);
                          }}
                          className={`px-2.5 py-1 rounded-md text-[11px] font-mono font-bold transition-all ${
                            gstRate === slab
                              ? 'bg-emerald-600 text-white shadow-2xs'
                              : 'bg-slate-50 border border-slate-200 text-slate-700 hover:bg-slate-100'
                          }`}
                        >
                          {slab}%
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 items-center">
                    <div>
                      <Input
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={gstRate}
                        onChange={(e) => {
                          setGstRate(parseFloat(e.target.value) || 0);
                          setIsDirty(true);
                        }}
                        className="text-xs font-mono font-bold bg-white h-[40px]"
                      />
                    </div>

                    <div className="p-2.5 bg-emerald-50 rounded-lg border border-emerald-200 text-[11px] font-mono text-emerald-950">
                      {isInterstate ? (
                        <div>
                          <span className="font-bold text-indigo-700">IGST:</span> {gstRate}%
                        </div>
                      ) : (
                        <div className="flex items-center justify-between">
                          <span>
                            <strong>CGST:</strong> {halfRate}%
                          </span>
                          <span>
                            <strong>SGST:</strong> {halfRate}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-3 bg-slate-100 rounded-xl text-slate-600 text-xs flex items-center gap-2">
                  <Info className="w-4 h-4 text-slate-500 shrink-0" />
                  <span>Tax rate is 0% (Taxability: {taxability}). Emitted as Specify Details Here.</span>
                </div>
              )}

              {/* Batch Apply Checkbox */}
              {isMultiNew && (
                <div className="p-3 bg-purple-50/80 border border-purple-200 rounded-xl">
                  <label className="flex items-center gap-2.5 cursor-pointer font-bold text-purple-950 text-xs">
                    <input
                      type="checkbox"
                      checked={applyToAll}
                      onChange={(e) => setApplyToAll(e.target.checked)}
                      className="rounded border-purple-300 text-purple-600 focus:ring-purple-500 w-4 h-4"
                    />
                    <span>
                      Apply Group &apos;{parentGroup || 'Primary'}&apos; & Taxability to all {totalNewCount} new items
                    </span>
                  </label>
                </div>
              )}
            </div>
          </div>
        </div>
      </MasterModalShell>

      {/* HOW IT WILL LOOK IN TALLY PREVIEW MODAL */}
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
                    TallyPrime Stock Item Alteration Preview
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
                    previewTab === 'screen' ? 'bg-white shadow-2xs text-emerald-900' : 'text-slate-600'
                  }`}
                >
                  Tally Screen
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewTab('xml')}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold flex items-center gap-1 ${
                    previewTab === 'xml' ? 'bg-white shadow-2xs text-emerald-900' : 'text-slate-600'
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
                    Stock Item Alteration (Secondary)
                  </span>
                  <span className="text-[10px] bg-[#d4af37]/20 px-2 py-0.5 rounded text-[#5c470a] font-bold">
                    TallyPrime Gold Import
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Left Side */}
                  <div className="space-y-2 border-r border-[#d4af37]/30 pr-3">
                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">English:</span>
                      <span className="font-bold text-sm text-[#111]">{previewData?.name || name}</span>
                    </div>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Under:</span>
                      <span className="font-bold text-indigo-900 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200">
                        {previewData?.parent_group || parentGroup}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Units:</span>
                      <span className="font-bold text-[#111]">{previewData?.base_unit || baseUnit}</span>
                    </div>

                    {Boolean(previewData?.alternate_unit) && (
                      <div>
                        <span className="text-[10px] text-[#7a6a43] block">Alternate units:</span>
                        <span className="font-bold text-[#111]">{previewData.alternate_unit}</span>
                        <div className="text-[11px] text-[#555] mt-0.5 font-bold">
                          where {previewData.conversion_formula}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right Side */}
                  <div className="space-y-2 pl-1">
                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">GST Applicability:</span>
                      <span className="font-bold text-[#111]">{previewData?.gst_applicability || 'Applicable'}</span>
                    </div>

                    <div className="p-2 bg-emerald-50/70 border border-emerald-300 rounded">
                      <span className="text-[10px] font-bold text-emerald-900 block">HSN/SAC Details:</span>
                      <span className="font-bold text-emerald-800 text-[11px] block">
                        {previewData?.hsn_source || 'Specify Details Here'}
                      </span>
                      <div className="text-[11px] mt-0.5">
                        HSN/SAC: <strong>{previewData?.hsn_code || hsn || 'None'}</strong>
                      </div>
                    </div>

                    <div className="p-2 bg-emerald-50/70 border border-emerald-300 rounded">
                      <span className="text-[10px] font-bold text-emerald-900 block">GST Rate Details:</span>
                      <span className="font-bold text-emerald-800 text-[11px] block">
                        {previewData?.gst_source || previewData?.gst_rate_source || 'Specify Details Here'}
                      </span>
                      <div className="text-[11px] mt-0.5">
                        Taxability: <strong>{previewData?.taxability || taxability}</strong> &bull; Rate:{' '}
                        <strong>{previewData?.gst_rate !== undefined ? previewData.gst_rate : gstRate}%</strong>
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
                <pre className="p-3.5 bg-slate-900 text-emerald-400 rounded-xl text-[11px] font-mono overflow-x-auto max-h-96 leading-relaxed">
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
