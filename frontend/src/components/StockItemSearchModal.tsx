'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Package, Search, X, Check, ArrowRight, Tag, Layers, Percent } from 'lucide-react';
import { ImportedStockItem, listStockItems } from '@/lib/api';

interface StockItemSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  itemIndex: number;
  currentInvoiceItemName: string;
  currentMatchedStockItem?: string;
  stockItems: ImportedStockItem[];
  onSelectStockItem: (selectedItem: ImportedStockItem, itemIndex: number) => void;
  onCreateNewItem?: (initialName: string, itemIndex: number) => void;
}

export function StockItemSearchModal({
  isOpen,
  onClose,
  itemIndex,
  currentInvoiceItemName,
  currentMatchedStockItem,
  stockItems,
  onSelectStockItem,
  onCreateNewItem,
}: StockItemSearchModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [backendItems, setBackendItems] = useState<ImportedStockItem[]>([]);
  const [isSearchingBackend, setIsSearchingBackend] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Initialize search query with cleaned invoice item name when opened
  useEffect(() => {
    if (isOpen) {
      // Extract clean words from item name for easy initial search
      const cleanInitial = currentInvoiceItemName
        .replace(/[()\[\]\/\-:]/g, ' ')
        .replace(/\b(rs|lita|liab|dz|pcs|nos|ghee|ml)\b/gi, '')
        .trim();
      setSearchQuery(cleanInitial || currentInvoiceItemName);
      setBackendItems([]);

      setTimeout(() => {
        if (searchInputRef.current) {
          searchInputRef.current.focus();
          searchInputRef.current.select();
        }
      }, 50);
    }
  }, [isOpen, currentInvoiceItemName]);

  // Handle ESC key to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose();
      }
    }
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  // Debounced backend search to fetch items even if client cache didn't load everything
  useEffect(() => {
    if (!isOpen || !searchQuery.trim()) return;

    const timer = setTimeout(() => {
      setIsSearchingBackend(true);
      listStockItems(searchQuery.trim(), 100)
        .then((res) => {
          if (Array.isArray(res)) {
            setBackendItems(res);
          }
        })
        .catch(() => {})
        .finally(() => setIsSearchingBackend(false));
    }, 250);

    return () => clearTimeout(timer);
  }, [isOpen, searchQuery]);

  // Merge client stockItems and backend search results
  const allAvailableItems = useMemo(() => {
    const map = new Map<string, ImportedStockItem>();
    for (const it of stockItems) {
      map.set(it.name.trim().toLowerCase(), it);
    }
    for (const it of backendItems) {
      map.set(it.name.trim().toLowerCase(), it);
    }
    return Array.from(map.values());
  }, [stockItems, backendItems]);

  // Smart multi-token filter and ranking
  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return allAvailableItems.slice(0, 60);
    }

    const qTokens = q
      .replace(/[()\[\]\/\-.,]/g, ' ')
      .split(/\s+/)
      .filter((t) => t.length > 0);

    const exactMatches: ImportedStockItem[] = [];
    const prefixMatches: ImportedStockItem[] = [];
    const allTokensMatches: ImportedStockItem[] = [];
    const anyTokenMatches: ImportedStockItem[] = [];

    for (const it of allAvailableItems) {
      const name = (it.name || '').toLowerCase();
      const norm = (it.normalized_name || '').toLowerCase();
      const hsn = (it.hsn_code || '').toLowerCase();
      const uom = (it.base_units || '').toLowerCase();
      const parent = (it.parent || '').toLowerCase();

      if (name === q || norm === q || hsn === q) {
        exactMatches.push(it);
      } else if (name.startsWith(q) || norm.startsWith(q)) {
        prefixMatches.push(it);
      } else if (
        qTokens.length > 0 &&
        qTokens.every(
          (t) => name.includes(t) || norm.includes(t) || hsn.includes(t) || uom.includes(t) || parent.includes(t)
        )
      ) {
        allTokensMatches.push(it);
      } else if (
        qTokens.length > 1 &&
        qTokens.some((t) => name.includes(t) || norm.includes(t) || hsn.includes(t))
      ) {
        anyTokenMatches.push(it);
      }
    }

    const combined = [...exactMatches, ...prefixMatches, ...allTokensMatches, ...anyTokenMatches];
    // Deduplicate
    const seen = new Set<string>();
    const result: ImportedStockItem[] = [];
    for (const it of combined) {
      const k = it.name.trim().toLowerCase();
      if (!seen.has(k)) {
        seen.add(k);
        result.push(it);
      }
      if (result.length >= 80) break;
    }
    return result;
  }, [allAvailableItems, searchQuery]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 overflow-y-auto animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-elevated border border-slate-200 overflow-hidden flex flex-col max-h-[88vh]">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 bg-gradient-to-r from-emerald-50/80 via-teal-50/40 to-white border-b border-emerald-100 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-xs flex-shrink-0">
              <Package className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-extrabold text-slate-900 flex items-center gap-2">
                <span>Select Stock Item from Uploaded Masters</span>
              </h3>
              <p className="text-xs text-slate-600 mt-0.5">
                Line #{itemIndex + 1}: <span className="font-bold text-slate-900 font-mono">{currentInvoiceItemName}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Input Bar */}
        <div className="p-4 border-b border-slate-100 bg-slate-50/50">
          <div className="relative">
            <Search className="w-4 h-4 text-emerald-600 absolute left-3.5 top-3" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by item name, HSN code, or UOM (e.g. CY AGB, 33074100, DZ)..."
              className="w-full pl-10 pr-10 py-2.5 text-xs sm:text-sm bg-white border border-slate-300 rounded-xl outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 shadow-xs font-semibold text-slate-900"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 p-1 rounded-md"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 px-1">
            <span>
              Showing <strong className="text-slate-800">{filteredItems.length}</strong> matching stock items
              {allAvailableItems.length > 0 && ` (${allAvailableItems.length} loaded masters)`}
            </span>
            {isSearchingBackend && (
              <span className="text-emerald-600 font-medium animate-pulse">Searching catalog...</span>
            )}
          </div>
        </div>

        {/* Results List */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2 divide-y divide-slate-100">
          {filteredItems.length > 0 ? (
            filteredItems.map((item) => {
              const isCurrentlyMapped =
                currentMatchedStockItem?.trim().toLowerCase() === item.name.trim().toLowerCase();

              return (
                <div
                  key={item.guid || item.name}
                  onClick={() => onSelectStockItem(item, itemIndex)}
                  className={`pt-2 first:pt-0 p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                    isCurrentlyMapped
                      ? 'bg-emerald-50/90 border-emerald-300 ring-1 ring-emerald-400/40'
                      : 'border-slate-200/80 hover:border-emerald-300 hover:bg-emerald-50/30'
                  }`}
                >
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-xs sm:text-sm text-slate-900 leading-snug">
                        {item.name}
                      </span>
                      {isCurrentlyMapped && (
                        <span className="px-2 py-0.5 rounded-full text-[9px] bg-emerald-200 text-emerald-900 font-extrabold flex items-center gap-1 flex-shrink-0">
                          <Check className="w-2.5 h-2.5" /> Currently Selected
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                      {item.base_units && (
                        <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-mono font-bold flex items-center gap-1">
                          <Layers className="w-2.5 h-2.5 text-slate-400" />
                          UOM: {item.base_units}
                        </span>
                      )}
                      {item.hsn_code && (
                        <span className="px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 font-mono font-bold border border-blue-200/60 flex items-center gap-1">
                          <Tag className="w-2.5 h-2.5 text-blue-500" />
                          HSN: {item.hsn_code}
                        </span>
                      )}
                      {item.gst_rate !== undefined && item.gst_rate !== null && (
                        <span className="px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-bold border border-purple-200/60 flex items-center gap-1">
                          <Percent className="w-2.5 h-2.5 text-purple-500" />
                          GST: {item.gst_rate}%
                        </span>
                      )}
                      {item.parent && item.parent !== 'Primary' && (
                        <span className="px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 font-semibold border border-amber-200/60">
                          {item.parent}
                        </span>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectStockItem(item, itemIndex);
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 flex-shrink-0 ${
                      isCurrentlyMapped
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'bg-slate-100 hover:bg-emerald-600 text-slate-700 hover:text-white border border-slate-200 hover:border-emerald-600'
                    }`}
                  >
                    <span>{isCurrentlyMapped ? 'Keep Selected' : 'Select'}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              );
            })
          ) : (
            <div className="py-10 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
                <Search className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <p className="font-bold text-sm text-slate-700">
                  No stock items found matching "{searchQuery}"
                </p>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Try typing fewer letters, or search by HSN code. If this is a brand new item not in your Tally masters, you can create it.
                </p>
              </div>

              {onCreateNewItem && (
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      onCreateNewItem(currentInvoiceItemName, itemIndex);
                    }}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-xs inline-flex items-center gap-1.5 transition-colors"
                  >
                    <Package className="w-3.5 h-3.5" />
                    Create "{currentInvoiceItemName}" as New Stock Item
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 sm:p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs">
          <span className="text-[11px] text-slate-500">
            Selecting an item automatically updates both the invoice item name and Tally stock mapping.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 font-bold rounded-xl shadow-xs"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
