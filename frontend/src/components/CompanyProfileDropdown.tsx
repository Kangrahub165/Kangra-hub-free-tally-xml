'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Building2, Check, ChevronDown, Plus, Search, X, BookOpen } from 'lucide-react';
import { CompanyProfile, getCompanyProfiles, saveCompanyProfile } from '@/lib/stockItemsMasterXml';
import { ImportedLedger, getUserLedgers } from '@/lib/api';

interface CompanyProfileDropdownProps {
  onSelectCompany: (company: CompanyProfile) => void;
  currentCompanyName?: string;
  currentGstin?: string;
  currentState?: string;
  currentAddress?: string;
  theme?: 'emerald' | 'indigo';
  ledgers?: ImportedLedger[];
}

export function CompanyProfileDropdown({
  onSelectCompany,
  currentCompanyName,
  currentGstin,
  currentState,
  currentAddress,
  theme = 'emerald',
  ledgers: propLedgers,
}: CompanyProfileDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [internalLedgers, setInternalLedgers] = useState<ImportedLedger[]>([]);
  const [savedProfiles, setSavedProfiles] = useState<CompanyProfile[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [newCompName, setNewCompName] = useState('');
  const [newGstin, setNewGstin] = useState('');
  const [newState, setNewState] = useState('');
  const [newAddress, setNewAddress] = useState('');

  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Load saved profiles from localStorage
  useEffect(() => {
    setSavedProfiles(getCompanyProfiles());
  }, []);

  // If propLedgers is not provided or empty, fetch from API on open
  useEffect(() => {
    if (isOpen && (!propLedgers || propLedgers.length === 0) && internalLedgers.length === 0) {
      getUserLedgers('', 1000)
        .then((data) => {
          if (Array.isArray(data)) {
            setInternalLedgers(data);
          }
        })
        .catch(() => {});
    }
  }, [isOpen, propLedgers, internalLedgers.length]);

  // Focus search input on open
  useEffect(() => {
    if (isOpen && !isAddingNew) {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    }
  }, [isOpen, isAddingNew]);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setIsAddingNew(false);
        setSearchQuery('');
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const activeLedgers = (propLedgers && propLedgers.length > 0) ? propLedgers : internalLedgers;

  // Filter ledgers by search query
  const filteredLedgers = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return activeLedgers.slice(0, 50);
    }
    const qTokens = q.split(/\s+/).filter(Boolean);
    return activeLedgers.filter((l) => {
      const name = (l.name || '').toLowerCase();
      const gstin = (l.party_gstin || '').toLowerCase();
      const state = (l.state || '').toLowerCase();
      const group = (l.group || '').toLowerCase();
      return qTokens.every(
        (t) => name.includes(t) || gstin.includes(t) || state.includes(t) || group.includes(t)
      );
    }).slice(0, 50);
  }, [activeLedgers, searchQuery]);

  const handleSelectLedger = (ledger: ImportedLedger) => {
    onSelectCompany({
      id: ledger.guid || `ledger-${ledger.name}`,
      name: ledger.name,
      gstin: ledger.party_gstin || '',
      state: ledger.state || '',
      address: [ledger.state, ledger.pincode].filter(Boolean).join(' '),
    });
    setIsOpen(false);
    setSearchQuery('');
  };

  const handleSelectSavedProfile = (profile: CompanyProfile) => {
    onSelectCompany(profile);
    setIsOpen(false);
    setSearchQuery('');
  };

  const handleSaveCurrentAsProfile = () => {
    if (!currentCompanyName?.trim()) return;
    const saved = saveCompanyProfile({
      name: currentCompanyName.trim(),
      gstin: (currentGstin || '').trim().toUpperCase(),
      state: currentState || '',
      address: currentAddress || '',
    });
    setSavedProfiles(getCompanyProfiles());
    onSelectCompany(saved);
    setIsOpen(false);
  };

  const handleCreateNewProfile = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompName.trim()) return;
    const saved = saveCompanyProfile({
      name: newCompName.trim(),
      gstin: newGstin.trim().toUpperCase(),
      state: newState.trim(),
      address: newAddress.trim(),
    });
    setSavedProfiles(getCompanyProfiles());
    onSelectCompany(saved);
    setIsAddingNew(false);
    setIsOpen(false);
    setNewCompName('');
    setNewGstin('');
    setNewState('');
    setNewAddress('');
  };

  const isEmerald = theme === 'emerald';
  const buttonBorder = isEmerald
    ? 'border-emerald-300 text-emerald-800 bg-emerald-50 hover:bg-emerald-100'
    : 'border-indigo-300 text-indigo-800 bg-indigo-50 hover:bg-indigo-100';

  return (
    <div className="relative inline-block" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`px-2.5 py-1 text-xs font-bold rounded-lg border flex items-center gap-1.5 shadow-xs transition-colors ${buttonBorder}`}
        title="Search and select company from uploaded Tally ledgers"
      >
        <Building2 className="w-3.5 h-3.5" />
        <span>Select from Ledgers</span>
        <ChevronDown className="w-3 h-3 text-slate-500" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-80 sm:w-96 bg-white rounded-xl shadow-elevated border border-slate-200 z-50 overflow-hidden text-xs animate-in fade-in zoom-in-95 duration-100">
          <div className="p-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <span className="font-extrabold text-slate-800 text-[11px] uppercase tracking-wider flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-teal-600" />
              Uploaded Tally Ledgers ({activeLedgers.length})
            </span>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setIsAddingNew(false);
                setSearchQuery('');
              }}
              className="text-slate-400 hover:text-slate-600 p-0.5 rounded"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {!isAddingNew ? (
            <div>
              {/* Search Box */}
              <div className="p-2 border-b border-slate-100 bg-white">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search ledger by name, GSTIN, state..."
                    className="w-full pl-8 pr-7 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg outline-none focus:bg-white focus:border-teal-500 font-medium"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2 top-2 text-slate-400 hover:text-slate-600"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Uploaded Ledgers List */}
              <div className="max-h-64 overflow-y-auto p-1.5 space-y-1">
                {filteredLedgers.length > 0 ? (
                  filteredLedgers.map((l, lIdx) => {
                    const isSelected =
                      currentCompanyName?.trim().toLowerCase() === l.name.trim().toLowerCase();
                    return (
                      <button
                        key={l.guid || `${l.name}-${lIdx}`}
                        type="button"
                        onClick={() => handleSelectLedger(l)}
                        className={`w-full text-left p-2.5 rounded-lg border transition-all flex items-start justify-between gap-2 ${
                          isSelected
                            ? 'bg-teal-50/80 border-teal-300 text-teal-950 font-bold ring-1 ring-teal-400/30'
                            : 'border-transparent hover:bg-slate-50 hover:border-slate-200 text-slate-800'
                        }`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-900 truncate block text-[11.5px]">
                              {l.name}
                            </span>
                            {l.group && (
                              <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-medium flex-shrink-0">
                                {l.group}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono mt-0.5">
                            <span>{l.party_gstin || 'No GSTIN'}</span>
                            {l.state && <span>• {l.state}</span>}
                          </div>
                        </div>
                        {isSelected && (
                          <Check className="w-4 h-4 text-teal-600 flex-shrink-0 mt-0.5" />
                        )}
                      </button>
                    );
                  })
                ) : (
                  <div className="py-6 text-center text-xs text-slate-500 space-y-1">
                    <p className="font-semibold">
                      {searchQuery ? `No ledgers matching "${searchQuery}"` : 'No ledgers found'}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      Upload your Tally ledgers via "Manage Ledgers" or add a custom profile below.
                    </p>
                  </div>
                )}
              </div>

              {/* Saved User Profiles (if any custom saved) */}
              {savedProfiles.length > 0 && !searchQuery && (
                <div className="border-t border-slate-100 p-1.5 bg-slate-50/50">
                  <div className="px-2 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    Saved Custom Profiles
                  </div>
                  {savedProfiles.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleSelectSavedProfile(p)}
                      className="w-full text-left p-1.5 rounded hover:bg-white text-slate-700 text-xs flex items-center justify-between"
                    >
                      <span className="font-semibold truncate">{p.name}</span>
                      <span className="text-[10px] text-slate-400 font-mono">{p.gstin}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Footer Actions */}
              <div className="p-2 bg-slate-50 border-t border-slate-200 flex flex-col gap-1.5">
                {currentCompanyName &&
                  !activeLedgers.some(
                    (l) => l.name.trim().toLowerCase() === currentCompanyName.trim().toLowerCase()
                  ) && (
                    <button
                      type="button"
                      onClick={handleSaveCurrentAsProfile}
                      className="w-full text-left px-2.5 py-1.5 text-[11px] font-bold text-teal-700 hover:bg-teal-50 rounded-lg border border-dashed border-teal-300 flex items-center gap-1.5 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5 text-teal-600" />
                      <span>Save "{currentCompanyName}" as Profile</span>
                    </button>
                  )}

                <button
                  type="button"
                  onClick={() => setIsAddingNew(true)}
                  className="w-full text-center px-2.5 py-1.5 text-[11px] font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  + Add Custom Company / Party
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleCreateNewProfile} className="p-3 space-y-2.5">
              <div>
                <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                  Company Name *
                </label>
                <input
                  type="text"
                  required
                  value={newCompName}
                  onChange={(e) => setNewCompName(e.target.value)}
                  placeholder="e.g. Your Company Name"
                  className="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs font-bold text-slate-900 outline-none focus:border-teal-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                    GSTIN
                  </label>
                  <input
                    type="text"
                    value={newGstin}
                    onChange={(e) => setNewGstin(e.target.value.toUpperCase())}
                    placeholder="15 digits"
                    className="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs font-mono font-bold uppercase text-slate-900 outline-none focus:border-teal-500"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                    State
                  </label>
                  <input
                    type="text"
                    value={newState}
                    onChange={(e) => setNewState(e.target.value)}
                    placeholder="e.g. Himachal Pradesh"
                    className="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 outline-none focus:border-teal-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                  Address
                </label>
                <textarea
                  rows={2}
                  value={newAddress}
                  onChange={(e) => setNewAddress(e.target.value)}
                  placeholder="Complete registered address"
                  className="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 outline-none focus:border-teal-500 resize-none"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-1 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddingNew(false)}
                  className="px-3 py-1.5 text-xs font-bold text-slate-600 hover:text-slate-800 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 rounded-lg shadow-xs"
                >
                  Save & Apply
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
