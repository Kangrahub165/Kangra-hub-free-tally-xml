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
  Plus
} from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
import {
  getStockItemGroups,
  getStockItemUnits,
  createNewStockItem,
  StockGroupItem,
  StockUnitItem,
  ImportedStockItem
} from '@/lib/api';

export interface CreateStockItemMasterModalProps {
  isOpen: boolean;
  onClose: () => void;
  item: {
    item_name: string;
    hsn_sac?: string;
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
      parent_group: string;
      uom: string;
      hsn?: string;
      gst_rate: number;
      taxability: string;
      type_of_supply: string;
      additional_units?: string;
      conversion?: number;
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
  // Form fields
  const [name, setName] = useState('');
  const [parentGroup, setParentGroup] = useState('Primary');
  const [baseUnit, setBaseUnit] = useState('NOS');
  const [hasAltUnit, setHasAltUnit] = useState(false);
  const [altUnit, setAltUnit] = useState('');
  const [conversion, setConversion] = useState<number | string>('');
  const [hsn, setHsn] = useState('');
  const [taxability, setTaxability] = useState('Taxable');
  const [gstRate, setGstRate] = useState<number>(18);
  const [typeOfSupply, setTypeOfSupply] = useState('Goods');
  const [applyToAll, setApplyToAll] = useState(false);

  // Groups and Units lists
  const [availableGroups, setAvailableGroups] = useState<StockGroupItem[]>([]);
  const [availableUnits, setAvailableUnits] = useState<StockUnitItem[]>([]);
  const [isGroupDropdownOpen, setIsGroupDropdownOpen] = useState(false);
  const [groupSearchQuery, setGroupSearchQuery] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

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

      // Best suggestion for group or fallback to Primary
      setParentGroup(item.parent_group || 'Primary');
      setGroupSearchQuery(item.parent_group || 'Primary');

      // Unit
      setBaseUnit((item.uom || 'NOS').toUpperCase());

      // Alternate unit
      if (item.alternate_uom && item.pack_multiplier && item.pack_multiplier > 1) {
        setHasAltUnit(true);
        setAltUnit(item.alternate_uom.toUpperCase());
        setConversion(item.pack_multiplier);
      } else {
        setHasAltUnit(false);
        setAltUnit('');
        setConversion('');
      }

      // HSN
      setHsn((item.hsn_sac || '').trim());

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
    setHsn(source.hsn_sac || '');
    setBaseUnit((source.uom || 'NOS').toUpperCase());
    setGstRate(source.gst_rate !== undefined ? Number(source.gst_rate) : 18);
    setParentGroup('Primary');
    setGroupSearchQuery('Primary');
    setTaxability('Taxable');
    setTypeOfSupply('Goods');
    setHasAltUnit(false);
  };

  // Submit Handler
  const handleSubmit = async (andNext: boolean = false) => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      const dataToSave = {
        name: name.trim(),
        parent_group: (parentGroup || 'Primary').trim(),
        uom: (baseUnit || 'NOS').trim().toUpperCase(),
        hsn: hsn.trim() || undefined,
        gst_rate: taxability === 'Taxable' ? Number(gstRate) || 0 : 0,
        taxability,
        type_of_supply: typeOfSupply,
        additional_units: hasAltUnit && altUnit.trim() ? altUnit.trim().toUpperCase() : undefined,
        conversion: hasAltUnit && conversion ? Number(conversion) : undefined,
      };

      await onSaveMaster(dataToSave, andNext, applyToAll);
      if (!andNext) {
        onClose();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const totalNewCount = allNewItems.length;
  const isMultiNew = totalNewCount > 1;
  const hasNext = isMultiNew && currentNewItemIndex < totalNewCount - 1;

  // Split preview
  const halfRate = (Number(gstRate) / 2).toFixed(2);

  return (
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
                Pre-filled from invoice. Saves as complete Tally master with Stock Group & GST details.
              </p>
            </div>
          </div>
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

        {/* 1. Item Name */}
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
          <p className="text-[10px] text-slate-400 mt-0.5">
            Original wording preserved. Double spaces and OCR artifacts cleaned.
          </p>
        </div>

        {/* 2. Stock Group (Parent) - Searchable Combobox */}
        <div className="relative">
          <div className="flex items-center justify-between mb-1">
            <label className="font-bold text-slate-700 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              <span>Stock Group (Parent)</span>
            </label>
            <Badge variant="neutral" size="sm" className="text-[10px] bg-indigo-50 text-indigo-700 border-indigo-200">
              {parentGroup === 'Primary' ? 'Default: Primary' : 'Custom Group'}
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
              placeholder="Search or type a new Stock Group (e.g. Biscuits, Primary)..."
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
          <p className="text-[10px] text-slate-400 mt-0.5">
            Select an existing Tally Stock Group or type a new one. (Default: Primary)
          </p>
        </div>

        {/* 3. Base Unit & HSN Code */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Base Unit */}
          <div>
            <label className="block font-bold text-slate-700 mb-1">Base Unit (UOM) *</label>
            <select
              value={baseUnit}
              onChange={(e) => setBaseUnit(e.target.value.toUpperCase())}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono font-bold uppercase focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-2xs"
            >
              {['NOS', 'PCS', 'CASE', 'BOX', 'BTL', 'KG', 'LTR', 'PKT', 'DOZ', 'BAG', 'CAN', 'SET', 'GM']
                .concat(availableUnits.map((u) => u.name.toUpperCase()).filter((u) => !['NOS', 'PCS', 'CASE', 'BOX', 'BTL', 'KG', 'LTR', 'PKT', 'DOZ', 'BAG', 'CAN', 'SET', 'GM'].includes(u)))
                .map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
            </select>
            <p className="text-[10px] text-slate-400 mt-0.5">Primary unit of invoice items.</p>
          </div>

          {/* HSN Code */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="font-bold text-slate-700">HSN / SAC Code</label>
              {hsn && (
                <Badge variant="neutral" size="sm" className="text-[10px] bg-slate-100 text-slate-600">
                  From invoice
                </Badge>
              )}
            </div>
            <Input
              value={hsn}
              onChange={(e) => setHsn(e.target.value.replace(/\D/g, ''))}
              placeholder="e.g. 22021010"
              maxLength={8}
              className="text-xs font-mono"
            />
            <p className="text-[10px] text-slate-400 mt-0.5">4, 6, or 8 digits. Optional but recommended.</p>
          </div>
        </div>

        {/* 4. Alternate Unit Toggle & Conversion */}
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
          <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-700">
            <input
              type="checkbox"
              checked={hasAltUnit}
              onChange={(e) => setHasAltUnit(e.target.checked)}
              className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            <span>Enable Alternate Unit & Pack Conversion (e.g. 1 CASE = 24 BTL)</span>
          </label>

          {hasAltUnit && (
            <div className="grid grid-cols-2 gap-3 pt-2 animate-in fade-in duration-150">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Alternate Unit
                </label>
                <Input
                  value={altUnit}
                  onChange={(e) => setAltUnit(e.target.value.toUpperCase())}
                  placeholder="e.g. BTL, PCS"
                  className="text-xs font-mono uppercase font-bold"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Pack Conversion Multiplier
                </label>
                <Input
                  type="number"
                  min="1"
                  step="1"
                  value={conversion}
                  onChange={(e) => setConversion(e.target.value)}
                  placeholder="e.g. 24"
                  className="text-xs font-mono font-bold"
                />
              </div>
              {altUnit && conversion && (
                <div className="col-span-2 text-[11px] text-emerald-700 font-semibold bg-emerald-50 p-2 rounded-lg border border-emerald-100 flex items-center gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>
                    Formula: 1 {baseUnit} = {conversion} {altUnit}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 5. Taxability & GST Rate */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Taxability */}
          <div>
            <label className="block font-bold text-slate-700 mb-1">Taxability</label>
            <select
              value={taxability}
              onChange={(e) => setTaxability(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-2xs"
            >
              <option value="Taxable">Taxable</option>
              <option value="Exempt">Exempt</option>
              <option value="Nil Rated">Nil Rated</option>
            </select>
          </div>

          {/* Type of Supply */}
          <div>
            <label className="block font-bold text-slate-700 mb-1">Type of Supply</label>
            <select
              value={typeOfSupply}
              onChange={(e) => setTypeOfSupply(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-2xs"
            >
              <option value="Goods">Goods</option>
              <option value="Services">Services</option>
            </select>
          </div>
        </div>

        {/* 6. GST Rate Selector & Split Preview */}
        {taxability === 'Taxable' ? (
          <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-xl space-y-2.5">
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
                        : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
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

              {/* Live Rate Split Preview */}
              <div className="p-2 bg-white rounded-lg border border-emerald-200 text-[11px] font-mono text-emerald-800">
                {isInterstate ? (
                  <div>
                    <span className="font-bold text-indigo-700">IGST:</span> {gstRate}%
                  </div>
                ) : (
                  <div className="flex items-center justify-between">
                    <span>
                      <strong className="text-emerald-700">CGST:</strong> {halfRate}%
                    </span>
                    <span>
                      <strong className="text-emerald-700">SGST:</strong> {halfRate}%
                    </span>
                    <span className="text-slate-400">Total: {gstRate}%</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-3 bg-slate-100 rounded-xl text-slate-600 text-[11px] flex items-center gap-2">
            <Info className="w-4 h-4 text-slate-500" />
            <span>Tax rate is 0% because taxability is set to {taxability}.</span>
          </div>
        )}

        {/* 7. Apply to All New Items Checkbox */}
        {isMultiNew && (
          <div className="p-3 bg-purple-50/70 border border-purple-200 rounded-xl">
            <label className="flex items-center gap-2 cursor-pointer font-bold text-purple-900">
              <input
                type="checkbox"
                checked={applyToAll}
                onChange={(e) => setApplyToAll(e.target.checked)}
                className="rounded border-purple-300 text-purple-600 focus:ring-purple-500"
              />
              <span>
                Apply Stock Group &apos;{parentGroup || 'Primary'}&apos; and Taxability to all {totalNewCount} new items
              </span>
            </label>
            <p className="text-[10px] text-purple-700 mt-0.5 ml-5">
              Saves time when all new items on this invoice belong to the same category.
            </p>
          </div>
        )}

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
  );
};
