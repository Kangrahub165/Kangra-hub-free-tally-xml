'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Search, Check, Plus, ChevronDown, X } from 'lucide-react';

export interface DropdownItem {
  name: string;
  item_count?: number;
  badge?: string;
  isPinned?: boolean;
  disabled?: boolean;
}

export interface PortalDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  triggerRef: React.RefObject<HTMLElement | null>;
  items: DropdownItem[];
  selectedItem?: string;
  onSelect: (name: string) => void;
  headerText?: string;
  emptyMessage?: string;
  searchPlaceholder?: string;
  bottomAction?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
  };
  enableSearch?: boolean;
  align?: 'left' | 'right';
  className?: string;
}

export const PortalDropdown: React.FC<PortalDropdownProps> = ({
  isOpen,
  onClose,
  triggerRef,
  items,
  selectedItem,
  onSelect,
  headerText,
  emptyMessage = 'No matching items found',
  searchPlaceholder = 'Search...',
  bottomAction,
  enableSearch = true,
  className = '',
}) => {
  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState(0);
  const [position, setPosition] = useState<{
    top?: number;
    bottom?: number;
    left: number;
    width: number;
    isFlippedUp: boolean;
  } | null>(null);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Compute fixed position relative to trigger element
  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const dropdownHeight = 280; // approximate max dropdown height
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;

    const isFlippedUp = spaceBelow < dropdownHeight && spaceAbove > dropdownHeight;

    if (isFlippedUp) {
      setPosition({
        bottom: window.innerHeight - rect.top + 4,
        left: Math.max(8, rect.left),
        width: rect.width,
        isFlippedUp: true,
      });
    } else {
      setPosition({
        top: rect.bottom + 4,
        left: Math.max(8, rect.left),
        width: rect.width,
        isFlippedUp: false,
      });
    }
  }, [triggerRef]);

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      setSearchQuery('');
      setHighlightIndex(0);

      // Focus search input after portal mounts
      const timer = setTimeout(() => {
        if (searchInputRef.current) {
          searchInputRef.current.focus();
        }
      }, 50);

      window.addEventListener('resize', updatePosition);
      window.addEventListener('scroll', updatePosition, true);

      return () => {
        clearTimeout(timer);
        window.removeEventListener('resize', updatePosition);
        window.removeEventListener('scroll', updatePosition, true);
      };
    }
  }, [isOpen, updatePosition]);

  // Filter items based on searchQuery
  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) => it.name.toLowerCase().includes(q));
  }, [items, searchQuery]);

  // Adjust highlightIndex when filtered list changes
  useEffect(() => {
    setHighlightIndex(0);
  }, [filteredItems.length]);

  // Auto-scroll highlighted option into view
  useEffect(() => {
    if (listRef.current && filteredItems.length > 0) {
      const activeEl = listRef.current.children[highlightIndex] as HTMLElement;
      if (activeEl) {
        activeEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightIndex, filteredItems.length]);

  // Click outside to close
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(target) &&
        triggerRef.current &&
        !triggerRef.current.contains(target)
      ) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside, true);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true);
    };
  }, [isOpen, onClose, triggerRef]);

  // Keyboard navigation within the dropdown
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      e.stopPropagation();
      setHighlightIndex((prev) => (prev < filteredItems.length - 1 ? prev + 1 : prev));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      e.stopPropagation();
      setHighlightIndex((prev) => (prev > 0 ? prev - 1 : 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      if (filteredItems[highlightIndex]) {
        onSelect(filteredItems[highlightIndex].name);
        onClose();
      } else if (bottomAction && searchQuery.trim()) {
        bottomAction.onClick();
        onClose();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      onClose();
    }
  };

  if (!isOpen || !mounted || !position) return null;

  return createPortal(
    <div
      ref={dropdownRef}
      data-portal-dropdown-open="true"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
      className={`fixed z-[99999] bg-white rounded-xl shadow-2xl border border-slate-200/90 overflow-hidden flex flex-col text-xs text-slate-800 animate-in fade-in-50 zoom-in-95 duration-100 ${className}`}
      style={{
        width: Math.max(position.width, 220),
        left: position.left,
        top: position.top,
        bottom: position.bottom,
        maxHeight: 280,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Header text line (e.g. "23 groups from Tally · imported 07 Oct") */}
      {headerText && (
        <div className="flex-none px-3 py-1.5 bg-slate-50/90 border-b border-slate-100 text-[10.5px] font-semibold text-slate-500 tracking-tight flex items-center justify-between select-none">
          <span>{headerText}</span>
          <span className="text-[10px] text-slate-400 font-mono">↑↓ Enter</span>
        </div>
      )}

      {/* Search Input Box */}
      {enableSearch && (
        <div className="flex-none p-2 border-b border-slate-100 bg-white">
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full pl-8 pr-7 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-800 focus:outline-none focus:bg-white focus:ring-1 focus:ring-indigo-500/30 focus:border-indigo-500 transition-colors"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2 p-0.5 text-slate-400 hover:text-slate-600 rounded"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Scrollable Items List */}
      <div
        ref={listRef}
        className="flex-1 min-h-0 overflow-y-auto divide-y divide-slate-50 py-1"
        style={{ maxHeight: 200 }}
      >
        {filteredItems.length > 0 ? (
          filteredItems.map((item, idx) => {
            const isSelected = selectedItem?.toUpperCase() === item.name.toUpperCase();
            const isHighlighted = idx === highlightIndex;

            return (
              <button
                key={`${item.name}-${idx}`}
                type="button"
                onMouseEnter={() => setHighlightIndex(idx)}
                onClick={() => {
                  if (!item.disabled) {
                    onSelect(item.name);
                    onClose();
                  }
                }}
                disabled={item.disabled}
                className={`w-full text-left px-3 py-1.5 flex items-center justify-between gap-2 transition-colors cursor-pointer select-none ${
                  isHighlighted ? 'bg-indigo-50/80 text-indigo-950 font-semibold' : 'text-slate-700'
                } ${isSelected ? 'font-bold text-indigo-700 bg-indigo-50/40' : ''}`}
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="truncate">{item.name}</span>
                  {item.badge && (
                    <span className="shrink-0 text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-normal">
                      {item.badge}
                    </span>
                  )}
                  {item.isPinned && (
                    <span className="shrink-0 text-[9.5px] bg-amber-50 text-amber-700 border border-amber-200 px-1 rounded font-semibold">
                      Primary
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 shrink-0 text-slate-400">
                  {item.item_count !== undefined && item.item_count > 0 && (
                    <span className="text-[10px] font-mono font-normal bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-full">
                      {item.item_count}
                    </span>
                  )}
                  {isSelected && <Check className="w-3.5 h-3.5 text-indigo-600 stroke-[2.5]" />}
                </div>
              </button>
            );
          })
        ) : (
          <div className="p-3 text-center text-slate-400 text-xs italic">
            {emptyMessage}
          </div>
        )}
      </div>

      {/* Bottom Action (e.g. "+ Create new group" or "+ Create new unit in Tally") */}
      {bottomAction && (
        <div className="flex-none p-1.5 bg-slate-50 border-t border-slate-100">
          <button
            type="button"
            onClick={() => {
              bottomAction.onClick();
              onClose();
            }}
            className="w-full text-left px-2.5 py-1.5 rounded-lg text-emerald-800 bg-emerald-50/70 hover:bg-emerald-100 font-bold text-xs flex items-center gap-1.5 transition-colors"
          >
            {bottomAction.icon || <Plus className="w-3.5 h-3.5 text-emerald-600" />}
            <span className="truncate">{bottomAction.label}</span>
          </button>
        </div>
      )}
    </div>,
    document.body
  );
};
