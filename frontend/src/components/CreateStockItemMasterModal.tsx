import React, { useState, useEffect, useMemo } from 'react';
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
  Copy
} from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
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

const STANDARD_UNITS = [
  'PKT', 'PCS', 'NOS', 'BTL', 'CAN', 'CASE', 'BOX', 'BAG',
  'CTN', 'KG', 'LTR', 'GM', 'DOZ', 'SET', 'UNT'
];

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
  const [baseUnit, setBaseUnit] = useState('NOS');
  const [hasAltUnit, setHasAltUnit] = useState(false);
  const [altUnit, setAltUnit] = useState('CASE');
  const [conversion, setConversion] = useState<number | string>('1');

  // Statutory Details (Right column)
  const [hsn, setHsn] = useState('');
  const [hsnDescription, setHsnDescription] = useState('');
  const [taxability, setTaxability] = useState('Taxable');
  const [gstRate, setGstRate] = useState<number>(18);
  const [typeOfSupply, setTypeOfSupply] = useState('Goods');
  const [reportingUqc, setReportingUqc] = useState('');
  const [applyToAll, setApplyToAll] = useState(false);

  // Version tracking
  const [version, setVersion] = useState<number>(1);
  const [savedTime, setSavedTime] = useState<string | null>(null);

  // Groups and Units lists
  const [availableGroups, setAvailableGroups] = useState<StockGroupItem[]>([]);
  const [availableUnits, setAvailableUnits] = useState<StockUnitItem[]>([]);
  const [isGroupDropdownOpen, setIsGroupDropdownOpen] = useState(false);
  const [groupSearchQuery, setGroupSearchQuery] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Tally Preview state
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<StockItemTallyPreview | null>(null);
  const [previewXml, setPreviewXml] = useState<string>('');
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewTab, setPreviewTab] = useState<'screen' | 'xml'>('screen');
  const [copiedXml, setCopiedXml] = useState(false);

  // Load groups & units on open
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
      setAvailableGroups(groups);
      setAvailableUnits(units);
    } catch {
      // Graceful fallback
    }
  };

  // Pre-fill form from item
  useEffect(() => {
    if (item && isOpen) {
      const rawName = (item.item_name || '').trim();
      setName(rawName);
      setAlias(item.alias || '');

      // Best suggestion for group or fallback to Primary
      setParentGroup(item.parent_group || 'Primary');
      setGroupSearchQuery(item.parent_group || 'Primary');

      // Base unit = SMALL unit (PRD Rule 4)
      const u = (item.uom || 'NOS').toUpperCase();
      setBaseUnit(u);

      // Alternate unit = BIG unit (PRD Rule 4)
      if (item.alternate_uom && item.pack_multiplier && item.pack_multiplier >= 1) {
        setHasAltUnit(true);
        setAltUnit(item.alternate_uom.toUpperCase());
        setConversion(item.pack_multiplier);
      } else {
        setHasAltUnit(false);
        setAltUnit('CASE');
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

      if (item.saved_draft_version) {
        setVersion(item.saved_draft_version);
        setSavedTime('Previously Saved');
      } else {
        setVersion(1);
        setSavedTime(null);
      }
    }
  }, [item, isOpen]);

  // Duplicate Check
  const duplicateMatch = useMemo(() => {
    if (!name.trim()) return null;
    const clean = name.trim().toLowerCase().replace(/\s+/g, ' ');
    return existingStockItems.find(
      (si) => si.name.trim().toLowerCase().replace(/\s+/g, ' ') === clean
    );
  }, [name, existingStockItems]);

  // Unit existence checks
  const existingUnitNames = useMemo(() => {
    return new Set(availableUnits.map((u) => u.name.toUpperCase()));
  }, [availableUnits]);

  const isBaseUnitInTally = useMemo(() => {
    return existingUnitNames.size === 0 || existingUnitNames.has(baseUnit.toUpperCase());
  }, [baseUnit, existingUnitNames]);

  const isAltUnitInTally = useMemo(() => {
    if (!hasAltUnit || !altUnit) return true;
    return existingUnitNames.size === 0 || existingUnitNames.has(altUnit.toUpperCase());
  }, [hasAltUnit, altUnit, existingUnitNames]);

  // Filtered groups for combobox
  const filteredGroups = useMemo(() => {
    const q = groupSearchQuery.trim().toLowerCase();
    const list = availableGroups.map((g) => g.name);
    if (!list.includes('Primary')) list.unshift('Primary');

    if (!q) return list;
    return list.filter((g) => g.toLowerCase().includes(q));
  }, [availableGroups, groupSearchQuery]);

  // Reset to Invoice Values
  const handleResetToInvoice = () => {
    if (!initialInvoiceValues && !item) return;
    const source = initialInvoiceValues || item!;
    setName(source.item_name || '');
    setAlias('');
    setHsn(source.hsn_sac || '');
    setHsnDescription('');
    setBaseUnit((source.uom || 'NOS').toUpperCase());
    setGstRate(source.gst_rate !== undefined ? Number(source.gst_rate) : 18);
    setParentGroup('Primary');
    setGroupSearchQuery('Primary');
    setTaxability('Taxable');
    setTypeOfSupply('Goods');
    setHasAltUnit(false);
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
        uom: baseUnit.trim().toUpperCase(),
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

  // Submit Handler
  const handleSubmit = async (andNext: boolean = false) => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      const newVer = version + 1;
      const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      const dataToSave = {
        name: name.trim(),
        alias: alias.trim() || undefined,
        parent_group: (parentGroup || 'Primary').trim(),
        uom: (baseUnit || 'NOS').trim().toUpperCase(),
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

  // Split preview
  const halfRate = (Number(gstRate) / 2).toFixed(2);

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={
          <div className="flex items-center justify-between w-full pr-6">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700">
                <Package className="w-4 h-4" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span>Create Stock Item Master in Tally</span>
                  {isMultiNew && (
                    <Badge variant="neutral" size="sm" className="font-semibold text-[11px]">
                      Item {currentNewItemIndex + 1} of {totalNewCount}
                    </Badge>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 font-normal">
                  Mirrors TallyPrime Stock Item Creation. Saved values go verbatim into XML without modification.
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

          {/* MAIN 2-COLUMN LAYOUT MIRRORING TALLY PRIME */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* LEFT COLUMN: Name, Alias, Under (Group), Units, Pack Conversion */}
            <div className="space-y-3 p-3 bg-slate-50/70 border border-slate-200 rounded-xl">
              <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider pb-1 border-b border-slate-200">
                Item Identity & Units
              </div>

              {/* Item Name */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-700 flex items-center gap-1.5">
                    <span>Item Name *</span>
                    <span className="text-rose-500 font-bold">*</span>
                  </label>
                  <Badge variant="neutral" size="sm" className="text-[10px] bg-slate-100 text-slate-600 flex items-center gap-1">
                    <Sparkles className="w-2.5 h-2.5 text-emerald-600" />
                    From invoice
                  </Badge>
                </div>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Clean item name as it will appear in Tally"
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
                  placeholder="Optional item code or shorthand"
                  className="text-xs"
                />
              </div>

              {/* Stock Group (Parent) - Searchable Combobox */}
              <div className="relative">
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-700 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Under (Stock Group) *</span>
                  </label>
                  <Badge variant="neutral" size="sm" className="text-[10px] bg-indigo-50 text-indigo-700 border-indigo-200">
                    {parentGroup === 'Primary' ? 'Default: Primary' : 'Selected Group'}
                  </Badge>
                </div>
                <div className="relative">
                  <Input
                    value={groupSearchQuery}
                    onChange={(e) => {
                      setGroupSearchQuery(e.target.value);
                      setParentGroup(e.target.value);
                      setIsGroupDropdownOpen(true);
                    }}
                    onFocus={() => setIsGroupDropdownOpen(true)}
                    placeholder="Search or type Stock Group (e.g. Biscuits, Primary)..."
                    className="text-xs font-medium pr-8"
                  />
                  {groupSearchQuery && (
                    <button
                      type="button"
                      onClick={() => {
                        setGroupSearchQuery('');
                        setParentGroup('Primary');
                      }}
                      className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Group Suggestions Dropdown */}
                {isGroupDropdownOpen && (
                  <div className="absolute z-20 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-lg text-xs py-1">
                    {filteredGroups.map((g) => (
                      <button
                        key={g}
                        type="button"
                        onClick={() => {
                          setParentGroup(g);
                          setGroupSearchQuery(g);
                          setIsGroupDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center justify-between transition-colors ${
                          parentGroup === g ? 'bg-indigo-50 font-bold text-indigo-700' : 'text-slate-700'
                        }`}
                      >
                        <span>{g}</span>
                        {g === 'Primary' && (
                          <span className="text-[10px] text-slate-400">Default</span>
                        )}
                      </button>
                    ))}

                    {groupSearchQuery.trim() && !filteredGroups.includes(groupSearchQuery.trim()) && (
                      <button
                        type="button"
                        onClick={() => {
                          setParentGroup(groupSearchQuery.trim());
                          setIsGroupDropdownOpen(false);
                        }}
                        className="w-full text-left px-3 py-2 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-bold flex items-center gap-1.5 border-t border-emerald-100"
                      >
                        <Plus className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Create new group: &quot;{groupSearchQuery.trim()}&quot;</span>
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Base Unit (SMALL unit) */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="font-bold text-slate-700">
                    Units (Base Unit = SMALL unit) *
                  </label>
                  {!isBaseUnitInTally && (
                    <span className="text-[10px] text-amber-700 font-bold bg-amber-100 px-1.5 py-0.2 rounded">
                      Will auto-create in Tally
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <select
                    value={baseUnit}
                    onChange={(e) => setBaseUnit(e.target.value.toUpperCase())}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono font-bold uppercase focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-2xs"
                  >
                    {STANDARD_UNITS.concat(
                      availableUnits
                        .map((u) => u.name.toUpperCase())
                        .filter((u) => !STANDARD_UNITS.includes(u))
                    ).map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5">
                  Base unit is always the smaller unit (e.g. PKT, PCS, BTL).
                </p>
              </div>

              {/* Alternate Units & Pack Conversion (PRD Rule 4 & Section 5) */}
              <div className="p-3 bg-white border border-slate-200 rounded-xl space-y-2">
                <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-700">
                  <input
                    type="checkbox"
                    checked={hasAltUnit}
                    onChange={(e) => setHasAltUnit(e.target.checked)}
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Alternate units (BIG unit, e.g. CASE, BOX)</span>
                </label>

                {hasAltUnit && (
                  <div className="space-y-2.5 pt-2 border-t border-slate-100 animate-in fade-in duration-150">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-[11px] font-semibold text-slate-600">
                          Alternate unit (BIG)
                        </label>
                        {!isAltUnitInTally && (
                          <span className="text-[10px] text-amber-700 font-bold bg-amber-100 px-1 py-0.2 rounded">
                            Will auto-create
                          </span>
                        )}
                      </div>
                      <select
                        value={altUnit}
                        onChange={(e) => setAltUnit(e.target.value.toUpperCase())}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-mono font-bold uppercase"
                      >
                        {['CASE', 'BOX', 'CTN', 'BAG', 'CRATE', 'DOZ', 'SET']
                          .concat(
                            availableUnits
                              .map((u) => u.name.toUpperCase())
                              .filter((u) => !['CASE', 'BOX', 'CTN', 'BAG', 'CRATE', 'DOZ', 'SET'].includes(u))
                          )
                          .map((u) => (
                            <option key={u} value={u}>
                              {u}
                            </option>
                          ))}
                      </select>
                    </div>

                    {/* PRD Rule 4 Conversion Line: where 1 [ALT] = [N] [BASE] */}
                    <div className="p-2.5 bg-emerald-50/70 border border-emerald-200 rounded-lg">
                      <label className="block text-[11px] font-bold text-emerald-900 mb-1">
                        where 1 {altUnit || 'CASE'} = [N] {baseUnit || 'NOS'}
                      </label>
                      <div className="flex items-center gap-2 font-mono">
                        <span className="text-xs font-bold text-slate-700 bg-slate-100 px-2.5 py-1.5 rounded border border-slate-300">
                          1 {altUnit} =
                        </span>
                        <Input
                          type="number"
                          min="1"
                          step="1"
                          value={conversion}
                          onChange={(e) => setConversion(e.target.value)}
                          placeholder="e.g. 192"
                          className="text-xs font-mono font-bold w-24 text-center bg-white"
                        />
                        <span className="text-xs font-bold text-slate-700">
                          {baseUnit}
                        </span>
                      </div>
                      <p className="text-[10px] text-emerald-800 mt-1">
                        Formula in Tally: <strong>1 {altUnit} = {conversion || 1} {baseUnit}</strong> (Denominator: {conversion || 1}, Conversion: 1)
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT COLUMN: Statutory & GST Details */}
            <div className="space-y-3 p-3 bg-emerald-50/40 border border-emerald-200/80 rounded-xl">
              <div className="text-[11px] font-bold text-emerald-900 uppercase tracking-wider pb-1 border-b border-emerald-200 flex items-center justify-between">
                <span>Statutory Details</span>
                <Badge variant="neutral" size="sm" className="bg-emerald-100 text-emerald-800 text-[10px]">
                  Specify Details Here
                </Badge>
              </div>

              {/* GST Applicability */}
              <div>
                <label className="block font-bold text-slate-800 mb-1">
                  GST Applicability
                </label>
                <div className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700">
                  Applicable
                </div>
              </div>

              {/* HSN/SAC Code & Description */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="font-bold text-slate-800">
                    HSN/SAC Details: <span className="text-emerald-700 font-semibold text-[11px]">Specify Details Here</span>
                  </label>
                  {hsn && (
                    <Badge variant="neutral" size="sm" className="text-[10px] bg-white text-slate-600">
                      From invoice
                    </Badge>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-1">
                    <Input
                      value={hsn}
                      onChange={(e) => setHsn(e.target.value.replace(/\D/g, ''))}
                      placeholder="HSN (e.g. 2202)"
                      maxLength={8}
                      className="text-xs font-mono font-bold bg-white"
                    />
                  </div>
                  <div className="col-span-2">
                    <Input
                      value={hsnDescription}
                      onChange={(e) => setHsnDescription(e.target.value)}
                      placeholder="Description (e.g. Cold Drinks)"
                      className="text-xs bg-white"
                    />
                  </div>
                </div>
              </div>

              {/* GST Rate Details (Specify Details Here) */}
              <div>
                <label className="block font-bold text-slate-800 mb-1">
                  GST Rate Details: <span className="text-emerald-700 font-semibold text-[11px]">Specify Details Here</span>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {/* Taxability */}
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Taxability Type
                    </label>
                    <select
                      value={taxability}
                      onChange={(e) => setTaxability(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold shadow-2xs"
                    >
                      <option value="Taxable">Taxable</option>
                      <option value="Exempt">Exempt</option>
                      <option value="Nil Rated">Nil Rated</option>
                    </select>
                  </div>

                  {/* Type of Supply */}
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      Type of Supply
                    </label>
                    <select
                      value={typeOfSupply}
                      onChange={(e) => setTypeOfSupply(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold shadow-2xs"
                    >
                      <option value="Goods">Goods</option>
                      <option value="Services">Services</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* GST Rate % with split */}
              {taxability === 'Taxable' ? (
                <div className="p-3 bg-white border border-emerald-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="font-bold text-slate-800">GST Rate %</label>
                    <div className="flex items-center gap-1">
                      {COMMON_GST_SLABS.map((slab) => (
                        <button
                          key={slab}
                          type="button"
                          onClick={() => setGstRate(slab)}
                          className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold transition-all ${
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
                        onChange={(e) => setGstRate(parseFloat(e.target.value) || 0)}
                        className="text-xs font-mono font-bold bg-white"
                      />
                    </div>

                    <div className="p-2 bg-emerald-50 rounded-lg border border-emerald-200 text-[11px] font-mono text-emerald-900">
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
                <div className="p-2.5 bg-slate-100 rounded-xl text-slate-600 text-[11px] flex items-center gap-2">
                  <Info className="w-4 h-4 text-slate-500" />
                  <span>Tax rate is 0% (Taxability: {taxability}). Emitted as Specify Details Here.</span>
                </div>
              )}

              {/* Batch Apply Checkbox */}
              {isMultiNew && (
                <div className="p-2.5 bg-purple-50/70 border border-purple-200 rounded-xl">
                  <label className="flex items-center gap-2 cursor-pointer font-bold text-purple-900">
                    <input
                      type="checkbox"
                      checked={applyToAll}
                      onChange={(e) => setApplyToAll(e.target.checked)}
                      className="rounded border-purple-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span>
                      Apply Group &apos;{parentGroup || 'Primary'}&apos; & Taxability to all {totalNewCount} new items
                    </span>
                  </label>
                </div>
              )}
            </div>
          </div>

          {/* Footer actions */}
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
                className="text-xs font-semibold text-emerald-800 border-emerald-300 hover:bg-emerald-50 flex items-center gap-1.5"
                title="Preview how this item appears in TallyPrime parsed from the generated XML"
              >
                <Eye className="w-3.5 h-3.5 text-emerald-600" />
                <span>How it will look in Tally</span>
              </Button>

              <Button variant="outline" size="sm" type="button" onClick={onClose} disabled={isSubmitting}>
                Cancel
              </Button>

              {hasNext && (
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => handleSubmit(true)}
                  disabled={isSubmitting || !name.trim()}
                  className="font-bold border-emerald-300 text-emerald-800 hover:bg-emerald-50 flex items-center gap-1"
                >
                  <span>Save and Next</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              )}

              <Button
                variant="primary"
                size="sm"
                type="button"
                onClick={() => handleSubmit(false)}
                disabled={isSubmitting || !name.trim()}
                className="font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs"
              >
                {isSubmitting ? 'Saving...' : 'Save & Map Master'}
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

                    {previewData?.alternate_unit && (
                      <div className="pt-1 border-t border-[#d4af37]/20 space-y-1">
                        <div>
                          <span className="text-[10px] text-[#7a6a43] block">Alternate units:</span>
                          <span className="font-bold text-[#111]">{previewData.alternate_unit}</span>
                        </div>
                        <div className="p-1.5 bg-white/70 rounded border border-[#d4af37]/30">
                          <span className="text-[10px] text-[#7a6a43] block">Conversion:</span>
                          <span className="font-bold text-emerald-800">
                            where {previewData.conversion_formula || `1 ${previewData.alternate_unit} = ${previewData.conversion} ${previewData.base_unit}`}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right Side: Statutory Details */}
                  <div className="space-y-2 pl-1">
                    <span className="text-[10px] font-bold text-[#8a6d1c] block">
                      Statutory Details
                    </span>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">GST Applicability:</span>
                      <span className="font-bold text-[#111]">Applicable</span>
                    </div>

                    <div className="p-1.5 bg-white/70 rounded border border-[#d4af37]/30 space-y-0.5">
                      <span className="text-[10px] text-[#7a6a43] block">HSN/SAC Details:</span>
                      <span className="font-bold text-emerald-800 block">
                        {previewData?.hsn_source || 'Specify Details Here'}
                      </span>
                      <span className="text-[11px] font-semibold text-slate-800 block">
                        HSN: {previewData?.hsn_code || '(Not specified)'} {previewData?.hsn_description ? `(${previewData.hsn_description})` : ''}
                      </span>
                    </div>

                    <div className="p-1.5 bg-white/70 rounded border border-[#d4af37]/30 space-y-0.5">
                      <span className="text-[10px] text-[#7a6a43] block">GST Rate Details:</span>
                      <span className="font-bold text-emerald-800 block">
                        {previewData?.gst_source || 'Specify Details Here'}
                      </span>
                      <span className="text-[11px] font-semibold text-slate-800 block">
                        Taxability: {previewData?.taxability || taxability} &bull; Rate: {previewData?.gst_rate || 0}%
                      </span>
                      {Number(previewData?.gst_rate || 0) > 0 && (
                        <div className="text-[10px] text-slate-600 flex justify-between pt-0.5 border-t border-[#d4af37]/20">
                          <span>Integrated: {previewData?.gst_rate}%</span>
                          <span>Central: {previewData?.cgst_rate}%</span>
                          <span>State: {previewData?.sgst_rate}%</span>
                        </div>
                      )}
                    </div>

                    <div>
                      <span className="text-[10px] text-[#7a6a43] block">Type of Supply:</span>
                      <span className="font-semibold">{previewData?.type_of_supply || typeOfSupply}</span>
                    </div>

                    <div className="mt-2 p-2 bg-emerald-50/80 border border-emerald-200 rounded text-[10px] text-emerald-900 space-y-0.5">
                      <div className="font-bold flex items-center gap-1">
                        <CheckCircle className="w-3 h-3 text-emerald-600" />
                        <span>Round-Trip Verification Passed</span>
                      </div>
                      <p className="text-[9px] text-emerald-700">
                        Parsed directly from &lt;STOCKITEM&gt; XML message without loss.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-slate-500">Tally XML &lt;STOCKITEM&gt; Master Snippet</span>
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
