'use client';

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { 
  UploadCloud, 
  FileCode, 
  CheckCircle2, 
  AlertTriangle, 
  Trash2, 
  Plus, 
  Search, 
  RefreshCw, 
  X,
  BookOpen,
  FolderTree,
  Filter,
  Sparkles,
  Layers
} from 'lucide-react';
import { 
  importLedgers, 
  getUserLedgers, 
  getUserGroups,
  addSingleLedger, 
  deleteLedger, 
  ImportedLedger, 
  ImportedGroup,
  LedgerImportResult 
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

interface LedgerImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLedgersUpdated?: (count: number) => void;
}

export default function LedgerImportModal({ isOpen, onClose, onLedgersUpdated }: LedgerImportModalProps) {
  const [ledgers, setLedgers] = useState<ImportedLedger[]>([]);
  const [groups, setGroups] = useState<ImportedGroup[]>([]);
  const [activeTab, setActiveTab] = useState<'ledgers' | 'groups'>('ledgers');
  const [selectedGroupFilter, setSelectedGroupFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [importResult, setImportResult] = useState<LedgerImportResult | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  
  // Add single ledger form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newLedgerName, setNewLedgerName] = useState('');
  const [newLedgerGroup, setNewLedgerGroup] = useState('Primary');
  const [savingSingle, setSavingSingle] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadLedgers();
    }
  }, [isOpen]);

  const loadLedgers = async (search?: string) => {
    setLoading(true);
    setErrorMsg('');
    try {
      const [ledgerData, groupData] = await Promise.all([
        getUserLedgers(search),
        getUserGroups()
      ]);
      setLedgers(ledgerData);
      setGroups(groupData);
      if (onLedgersUpdated) {
        onLedgersUpdated(ledgerData.length);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load ledgers');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const result = await importLedgers(file);
      setImportResult(result);
      const ledgerCount = result.total_ledgers ?? result.total_imported;
      const groupCount = result.total_groups ?? (result.groups?.length || 0);
      const msg = groupCount > 0
        ? `Successfully imported ${ledgerCount} ledgers and ${groupCount} groups from ${result.detected_format} file.`
        : `Successfully imported ${ledgerCount} ledgers from ${result.detected_format} file.`;
      setSuccessMsg(msg);
      await loadLedgers();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to import ledgers');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleAddSingle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLedgerName.trim()) return;
    setSavingSingle(true);
    setErrorMsg('');
    try {
      await addSingleLedger(newLedgerName.trim(), newLedgerGroup.trim() || 'Primary');
      setNewLedgerName('');
      setNewLedgerGroup('Primary');
      setShowAddForm(false);
      setSuccessMsg(`Added ledger "${newLedgerName.trim()}"`);
      await loadLedgers();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add ledger');
    } finally {
      setSavingSingle(false);
    }
  };

  const handleDeleteLedger = async (name: string) => {
    try {
      await deleteLedger(name);
      setLedgers(prev => prev.filter(l => l.name !== name));
      if (onLedgersUpdated) {
        onLedgersUpdated(ledgers.length - 1);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete ledger');
    }
  };

  // Extract unique ledger groups for filter dropdown
  const uniqueLedgerGroups = Array.from(
    new Set(ledgers.map(l => l.group || 'Primary'))
  ).sort();

  const filteredLedgers = ledgers.filter(l => {
    if (selectedGroupFilter !== 'ALL' && (l.group || 'Primary') !== selectedGroupFilter) {
      return false;
    }
    return true;
  });

  const filteredGroups = groups.filter(g => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      g.name.toLowerCase().includes(q) ||
      (g.parent && g.parent.toLowerCase().includes(q))
    );
  });

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[100] overflow-y-auto">
      <div
        className="fixed inset-0 bg-navy-950/70 backdrop-blur-sm transition-opacity animate-fadeIn"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="flex min-h-full items-center justify-center p-3 sm:p-4 md:p-6 pointer-events-none">
        <div className="relative w-full max-w-4xl my-auto bg-white rounded-2xl sm:rounded-3xl shadow-modal border border-slate-200/80 overflow-hidden flex flex-col max-h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-3.5rem)] pointer-events-auto z-10 animate-slideUp text-left">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-800/50">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <span>Tally Master Import</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                  {ledgers.length + groups.length} Masters
                </span>
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Upload your Tally Master XML (All Masters) to view, verify, and match party accounts automatically.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          
          {/* Messages */}
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 text-xs text-red-700 dark:text-red-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 text-xs text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Upload Dropzone */}
          <div 
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-blue-500 dark:hover:border-blue-500 rounded-2xl p-5 text-center cursor-pointer bg-slate-50/50 dark:bg-slate-800/20 hover:bg-blue-50/20 dark:hover:bg-blue-950/10 transition-all duration-150"
          >
            <input 
              ref={fileInputRef}
              type="file" 
              accept=".xml,.json,.html,.htm" 
              className="hidden" 
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileUpload(f);
              }}
            />
            <div className="flex flex-col items-center gap-1.5">
              <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 flex items-center justify-center">
                {uploading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <UploadCloud className="w-5 h-5" />
                )}
              </div>
              <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                {uploading ? 'Parsing & Indexing All Masters...' : 'Click or Drag & Drop Tally Master XML'}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-md">
                Authoritative Master.xml structure supported: imports all <strong>Groups</strong>, <strong>Ledgers</strong>, Opening Balances, and GSTINs.
              </p>
            </div>
          </div>

          {/* Import Result Badge Bar */}
          {importResult && (
            <div className="flex flex-col gap-1 p-3 rounded-xl bg-blue-50/60 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-900/50">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
                <div className="text-xs text-blue-800 dark:text-blue-300 font-medium">
                  Detected Format: <strong>{importResult.detected_format}</strong> &bull; Total Ledgers: <strong>{importResult.total_ledgers ?? importResult.total_imported}</strong>
                  {(importResult.total_groups ?? 0) > 0 && (
                    <> &bull; Total Groups: <strong>{importResult.total_groups}</strong></>
                  )}
                  {(importResult.duplicates ?? 0) > 0 && (
                    <> &bull; Merged Duplicates: <strong>{importResult.duplicates}</strong></>
                  )}
                </div>
              </div>
              {importResult.conflicts && importResult.conflicts.length > 0 && (
                <div className="text-[11px] text-amber-700 dark:text-amber-400 pl-6">
                  Note: {importResult.conflicts.length} duplicate entry conflicts safely resolved without data loss.
                </div>
              )}
            </div>
          )}

          {/* Master Type Segmented Tabs & Filters */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1.5 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl">
              <button
                type="button"
                onClick={() => setActiveTab('ledgers')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                  activeTab === 'ledgers'
                    ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>All Ledgers ({ledgers.length})</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('groups')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ${
                  activeTab === 'groups'
                    ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                }`}
              >
                <FolderTree className="w-3.5 h-3.5" />
                <span>All Groups ({groups.length})</span>
              </button>
            </div>

            {/* Filter by Group (when in Ledgers tab) */}
            {activeTab === 'ledgers' && uniqueLedgerGroups.length > 0 && (
              <div className="flex items-center gap-2">
                <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <select
                  value={selectedGroupFilter}
                  onChange={(e) => setSelectedGroupFilter(e.target.value)}
                  className="px-2.5 py-1.5 text-xs rounded-xl bg-slate-100 dark:bg-slate-800 border-none text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-blue-500 font-medium cursor-pointer"
                >
                  <option value="ALL">All Groups ({ledgers.length})</option>
                  {uniqueLedgerGroups.map((grp) => {
                    const count = ledgers.filter(l => (l.group || 'Primary') === grp).length;
                    return (
                      <option key={grp} value={grp}>
                        {grp} ({count})
                      </option>
                    );
                  })}
                </select>
              </div>
            )}
          </div>

          {/* Search & Actions Bar */}
          <div className="flex items-center gap-2.5">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder={activeTab === 'ledgers' ? "Search ledgers by name, GSTIN, or alias..." : "Search groups..."}
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (activeTab === 'ledgers') {
                    loadLedgers(e.target.value);
                  }
                }}
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-slate-100 dark:bg-slate-800 border-none focus:ring-2 focus:ring-blue-500 dark:text-slate-100"
              />
            </div>
            {activeTab === 'ledgers' && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowAddForm(!showAddForm)}
                className="text-xs h-9 gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Ledger</span>
              </Button>
            )}
          </div>

          {/* Inline Add Ledger Form */}
          {showAddForm && activeTab === 'ledgers' && (
            <form onSubmit={handleAddSingle} className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
              <div className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Add Single Ledger to Your Master List
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-medium text-slate-500 mb-1 block">
                    Ledger Name in Tally *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. ABC TRADERS PVT LTD"
                    value={newLedgerName}
                    onChange={(e) => setNewLedgerName(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-500 mb-1 block">
                    Group (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Sundry Debtors"
                    value={newLedgerGroup}
                    onChange={(e) => setNewLedgerGroup(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <Button 
                  type="button" 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => setShowAddForm(false)}
                  className="text-xs h-8"
                >
                  Cancel
                </Button>
                <Button 
                  type="submit" 
                  variant="primary" 
                  size="sm" 
                  disabled={savingSingle || !newLedgerName.trim()}
                  className="text-xs h-8 gap-1.5"
                >
                  {savingSingle ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  <span>Save Ledger</span>
                </Button>
              </div>
            </form>
          )}

          {/* TAB 1: LEDGERS TABLE PREVIEW */}
          {activeTab === 'ledgers' && (
            <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 bg-slate-100/70 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-700 text-[11px] font-semibold text-slate-600 dark:text-slate-400 flex items-center justify-between">
                <span>All Tally Ledgers ({filteredLedgers.length}{selectedGroupFilter !== 'ALL' ? ` of ${ledgers.length}` : ''})</span>
                <span>Group & Parent Group</span>
              </div>

              <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[380px] overflow-y-auto">
                {loading ? (
                  <div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />
                    <span>Loading all ledgers...</span>
                  </div>
                ) : filteredLedgers.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-400">
                    {ledgers.length === 0 
                      ? 'No ledgers imported yet. Upload an XML, JSON, or HTML file above to populate.'
                      : 'No ledgers match your search query or group filter.'}
                  </div>
                ) : (
                  filteredLedgers.map((l, idx) => (
                    <div key={idx} className="px-4 py-2.5 flex items-center justify-between text-xs hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                      <div className="flex items-center gap-2 font-medium text-slate-800 dark:text-slate-200 flex-wrap">
                        <span className="text-slate-400 text-[10px] w-6">{idx + 1}.</span>
                        <span className="font-semibold">{l.name}</span>
                        {l.party_gstin && (
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-900/50">
                            GST: {l.party_gstin}
                          </span>
                        )}
                        {l.opening_balance !== undefined && l.opening_balance !== null && (
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/50">
                            ₹{Number(l.opening_balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </span>
                        )}
                        {l.state && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-50 dark:bg-slate-800/60 text-slate-500 border border-slate-200 dark:border-slate-700">
                            {l.state}
                          </span>
                        )}
                        {l.aliases && l.aliases.length > 0 && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-900/50" title={l.aliases.join(', ')}>
                            Alias: {l.aliases[0]}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex flex-col items-end">
                          <span className="text-[11px] text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800/50 px-2 py-0.5 rounded-md font-medium">
                            {l.group || 'Primary'}
                          </span>
                          {l.parent_group && l.parent_group !== l.group && (
                            <span className="text-[9px] text-slate-400">
                              {l.parent_group}
                            </span>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleDeleteLedger(l.name)}
                          className="text-slate-400 hover:text-red-500 p-1 transition-colors"
                          title="Delete ledger"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* TAB 2: GROUPS TABLE PREVIEW */}
          {activeTab === 'groups' && (
            <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 bg-slate-100/70 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-700 text-[11px] font-semibold text-slate-600 dark:text-slate-400 flex items-center justify-between">
                <span>All Tally Groups ({filteredGroups.length})</span>
                <span>Parent in Chart of Accounts</span>
              </div>

              <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[380px] overflow-y-auto">
                {filteredGroups.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-400">
                    {groups.length === 0 
                      ? 'No groups imported yet. Upload Master.xml above to populate the group hierarchy.'
                      : 'No groups match your search query.'}
                  </div>
                ) : (
                  filteredGroups.map((g, idx) => (
                    <div key={idx} className="px-4 py-2.5 flex items-center justify-between text-xs hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                      <div className="flex items-center gap-2 font-medium text-slate-800 dark:text-slate-200">
                        <span className="text-slate-400 text-[10px] w-6">{idx + 1}.</span>
                        <span className="font-semibold">{g.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {g.parent ? (
                          <span className="text-[11px] text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900/50 px-2 py-0.5 rounded-md font-medium">
                            Sub-group of {g.parent}
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800/50 px-2 py-0.5 rounded-md font-medium">
                            Primary Group
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex items-center justify-between">
          <div className="text-xs text-slate-600 dark:text-slate-400 font-medium flex items-center gap-2">
            <span><strong>{ledgers.length}</strong> Ledgers</span>
            <span>&bull;</span>
            <span><strong>{groups.length}</strong> Groups</span>
            <span>&bull;</span>
            <span className="text-blue-600 dark:text-blue-400 font-bold">({ledgers.length + groups.length} Total Masters Active)</span>
          </div>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={onClose}
            className="text-xs h-9 px-4 font-semibold"
          >
            Done & Continue
          </Button>
        </div>

      </div>
    </div>
  </div>,
  document.body
);
}
