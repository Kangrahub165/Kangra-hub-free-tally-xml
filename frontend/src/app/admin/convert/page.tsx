'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  UploadCloud, 
  FileText, 
  CheckCircle2, 
  AlertTriangle, 
  Download, 
  RefreshCw, 
  ArrowRight, 
  ShieldCheck, 
  Lock, 
  ChevronDown, 
  ChevronUp, 
  Sparkles, 
  SlidersHorizontal,
  Building2,
  Clock,
  Check,
  AlertCircle,
  FileCode,
  BookOpen,
  Plus,
  Search,
  Edit2,
  FileSpreadsheet
} from 'lucide-react';
import { 
  uploadAdminStatement, 
  overrideAdminBank, 
  generateAdminTallyXml,
  generateAdminExcel,
  getSupportedBanks, 
  getUserLedgers,
  getUserGroups,
  getUserBankLedgers,
  updateTransactionRow,
  bulkAssignLedgers,
  reviewAdminTransactions,
  downloadFileBlob,
  BankInfo,
  ImportedLedger,
  ImportedGroup
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import LedgerImportModal from '@/components/LedgerImportModal';

export default function AdminConvertPage() {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [supportedBanks, setSupportedBanks] = useState<BankInfo[]>([]);
  const [userLedgers, setUserLedgers] = useState<ImportedLedger[]>([]);
  const [userGroups, setUserGroups] = useState<ImportedGroup[]>([]);
  const [userBankLedgers, setUserBankLedgers] = useState<ImportedLedger[]>([]);
  const [isLedgerModalOpen, setIsLedgerModalOpen] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [converting, setConverting] = useState(false);
  const [generatingXml, setGeneratingXml] = useState(false);
  const [generatingExcel, setGeneratingExcel] = useState(false);
  const [excelResult, setExcelResult] = useState<any>(null);
  
  // Conversion state
  const [job, setJob] = useState<any>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  
  // Bank override state
  const [selectedOverrideBank, setSelectedOverrideBank] = useState('');
  const [overriding, setOverriding] = useState(false);
  
  // Ledger names (Mandatory configs)
  const [bankLedger, setBankLedger] = useState('Bank Account');
  const [cashLedger, setCashLedger] = useState('Cash');
  const [suspenseLedger, setSuspenseLedger] = useState('Suspense');
  
  // Diagnostics toggle
  const [showDiagnostics, setShowDiagnostics] = useState(true);
  
  // Transaction filter & search
  const [txFilter, setTxFilter] = useState<'ALL' | 'SUSPENSE' | 'MAPPED' | 'PAYMENT' | 'RECEIPT' | 'CONTRA' | 'WARNING' | 'ERROR' | 'DUPLICATE'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Multi-row selection & bulk actions
  const [selectedRowIndices, setSelectedRowIndices] = useState<Set<number>>(new Set());
  const [bulkLedger, setBulkLedger] = useState('');
  const [bulkVoucher, setBulkVoucher] = useState('');
  const [applyToSimilar, setApplyToSimilar] = useState(false);
  const [isBulkAssigning, setIsBulkAssigning] = useState(false);
  
  // Quick Add Modal
  const [quickAddModalRow, setQuickAddModalRow] = useState<number | null>(null);
  const [quickLedgerName, setQuickLedgerName] = useState('');
  
  // XML generation result
  const [xmlResult, setXmlResult] = useState<any>(null);

  useEffect(() => {
    getSupportedBanks()
      .then((data) => setSupportedBanks(data))
      .catch(() => {});
    loadLedgers();
  }, []);

  const loadLedgers = async () => {
    try {
      const [ledgerData, groupData, bankData] = await Promise.all([
        getUserLedgers(),
        getUserGroups(),
        getUserBankLedgers().catch(() => [])
      ]);
      setUserLedgers(ledgerData);
      setUserGroups(groupData);
      setUserBankLedgers(bankData || []);
    } catch {
      // ignore
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0];
      if (f.type === 'application/pdf' || f.name.endsWith('.pdf')) {
        setFile(f);
        setError('');
      } else {
        setError('Only PDF statements are supported.');
      }
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setConverting(true);
    setError('');
    setJob(null);
    setTransactions([]);
    setXmlResult(null);
    setExcelResult(null);

    try {
      const data = await uploadAdminStatement(
        file, 
        password || undefined,
        undefined,
        bankLedger,
        cashLedger
      );
      setJob(data);
      setTransactions(data.transactions || []);
      if (data.bank_ledger_name) {
        setBankLedger(data.bank_ledger_name);
      } else if (data.bank_name) {
        setBankLedger(`${data.bank_name} A/C`);
      }
      if (data.cash_ledger_name) {
        setCashLedger(data.cash_ledger_name);
      }
      setSelectedOverrideBank(data.bank_name);
      setSuccessMsg(`Successfully parsed ${data.page_count} pages and extracted ${data.transaction_count} transactions.`);
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err: any) {
      setError(err.message || 'Conversion failed. Please verify the statement PDF.');
    } finally {
      setConverting(false);
    }
  };

  const handleBankOverride = async () => {
    if (!job || !selectedOverrideBank || selectedOverrideBank === job.bank_name) return;

    setOverriding(true);
    setError('');

    try {
      const data = await overrideAdminBank(job.id, selectedOverrideBank);
      setJob(data);
      setTransactions(data.transactions || []);
      if (data.bank_ledger_name) {
        setBankLedger(data.bank_ledger_name);
      } else {
        setBankLedger(`${data.bank_name} A/C`);
      }
      setSuccessMsg(`Bank manually overridden to ${selectedOverrideBank}. Re-processed ${data.transaction_count} transactions.`);
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err: any) {
      setError(err.message || 'Failed to override bank adapter.');
    } finally {
      setOverriding(false);
    }
  };

  const handleTransactionChange = async (index: number, field: string, value: any) => {
    const updated = [...transactions];
    const newRow = { ...updated[index], [field]: value };
    
    if (field === 'ledger_name') {
      newRow.mapping_status = (value === 'Suspense' || !value) ? 'Suspense' : 'Mapped';
      newRow.mapping_confidence = 100;
    }
    
    updated[index] = newRow;
    setTransactions(updated);

    if (job) {
      try {
        const payload: any = {};
        if (field === 'ledger_name') payload.ledger_name = value;
        if (field === 'voucher_type') payload.voucher_type = value;
        if (field === 'instrument_number' || field === 'cheque_number' || field === 'reference') {
          payload.instrument_number = value;
        }
        if (field === 'narration') payload.narration = value;
        
        if (Object.keys(payload).length > 0) {
          await updateTransactionRow(job.id, index, payload, true);
        }
      } catch {
        // Updated locally, saved during generate
      }
    }
  };

  const handleToggleRowSelection = (index: number) => {
    const next = new Set(selectedRowIndices);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    setSelectedRowIndices(next);
  };

  const handleToggleSelectAll = () => {
    const isAllFilteredSelected = filteredTxs.length > 0 && filteredTxs.every((tx: any) => {
      const idx = transactions.indexOf(tx);
      return idx !== -1 && selectedRowIndices.has(idx);
    });

    const next = new Set(selectedRowIndices);
    if (isAllFilteredSelected) {
      filteredTxs.forEach((tx: any) => {
        const idx = transactions.indexOf(tx);
        if (idx !== -1) next.delete(idx);
      });
    } else {
      filteredTxs.forEach((tx: any) => {
        const idx = transactions.indexOf(tx);
        if (idx !== -1) next.add(idx);
      });
    }
    setSelectedRowIndices(next);
  };

  const handleBulkAssign = async () => {
    if (!bulkLedger.trim() || selectedRowIndices.size === 0) return;
    setIsBulkAssigning(true);
    setError('');

    const targetLedger = bulkLedger.trim();
    const targetVoucher = bulkVoucher || undefined;
    const rowList = Array.from(selectedRowIndices);
    const txIds = rowList
      .map(idx => transactions[idx]?.id)
      .filter(Boolean) as string[];

    // 1. Optimistic Local React State Update
    const updated = [...transactions];
    const targetParties = new Set<string>();

    rowList.forEach(idx => {
      if (updated[idx]) {
        updated[idx] = {
          ...updated[idx],
          ledger_name: targetLedger,
          mapping_status: targetLedger === 'Suspense' ? 'Suspense' : 'User Confirmed',
          mapping_confidence: 100,
          validation_status: 'VALID',
          validation_notes: undefined,
          voucher_type: targetVoucher || updated[idx].voucher_type,
        };
        if (updated[idx].party_name) {
          targetParties.add(updated[idx].party_name.toUpperCase());
        }
      }
    });

    if (applyToSimilar && targetParties.size > 0) {
      updated.forEach((t, i) => {
        const pMatch = t.party_name && targetParties.has(t.party_name.toUpperCase());
        const nMatch = Array.from(targetParties).some(p => (t.narration || '').toUpperCase().includes(p));
        if (pMatch || nMatch) {
          updated[i] = {
            ...t,
            ledger_name: targetLedger,
            mapping_status: targetLedger === 'Suspense' ? 'Suspense' : 'User Confirmed',
            mapping_confidence: 100,
            validation_status: 'VALID',
            validation_notes: undefined,
            voucher_type: targetVoucher || t.voucher_type,
          };
        }
      });
    }

    setTransactions(updated);
    setSelectedRowIndices(new Set());
    setSuccessMsg(`Assigned ledger "${targetLedger}" to ${rowList.length} row(s).`);
    setTimeout(() => setSuccessMsg(''), 4000);

    // 2. Server Sync
    if (job?.id) {
      try {
        const res = await bulkAssignLedgers(
          job.id,
          rowList,
          targetLedger,
          targetVoucher,
          applyToSimilar,
          true,
          txIds
        );
        setJob(res);
        if (res.transactions && res.transactions.length > 0) {
          setTransactions(res.transactions);
        }
      } catch (err: any) {
        console.warn('Admin server sync notice:', err);
      }
    }

    setIsBulkAssigning(false);
  };

  const handleAutoResolveFallback = async (indicesToResolve?: number[]) => {
    setIsBulkAssigning(true);
    setError('');

    const rowList = indicesToResolve !== undefined && indicesToResolve.length > 0 
      ? indicesToResolve 
      : (selectedRowIndices.size > 0 
          ? Array.from(selectedRowIndices) 
          : transactions.map((_, i) => i).filter(i => 
              transactions[i].ledger_name === 'Suspense' || 
              transactions[i].mapping_status === 'Suspense' || 
              !transactions[i].ledger_name ||
              transactions[i].validation_status !== 'VALID'
            ));

    if (rowList.length === 0) {
      setIsBulkAssigning(false);
      return;
    }

    const txIds = rowList
      .map(idx => transactions[idx]?.id)
      .filter(Boolean) as string[];

    // Optimistic local update
    const updated = [...transactions];
    rowList.forEach(idx => {
      const tx = updated[idx];
      if (tx) {
        const isCash = Boolean(tx.is_cash_transaction);
        const debitVal = Number(tx.debit) || 0;
        const creditVal = Number(tx.credit) || 0;
        let vType = tx.voucher_type;

        if (isCash) {
          vType = 'Contra';
        } else if (debitVal > 0 && creditVal === 0) {
          vType = 'Payment';
        } else if (creditVal > 0 && debitVal === 0) {
          vType = 'Receipt';
        } else if (debitVal > creditVal) {
          vType = 'Payment';
        } else {
          vType = 'Receipt';
        }

        updated[idx] = {
          ...tx,
          voucher_type: vType,
          ledger_name: tx.ledger_name || 'Suspense',
          mapping_status: tx.ledger_name && tx.ledger_name !== 'Suspense' ? 'User Confirmed' : 'Suspense',
          validation_status: tx.validation_status === 'ERROR' ? tx.validation_status : 'VALID',
          validation_notes: tx.validation_status === 'ERROR' ? tx.validation_notes : undefined,
        };
      }
    });

    setTransactions(updated);
    setSelectedRowIndices(new Set());
    setSuccessMsg(`Auto-resolved fallback vouchers for ${rowList.length} transaction(s).`);
    setTimeout(() => setSuccessMsg(''), 4000);

    // Sync with server
    if (job?.id) {
      try {
        const res = await bulkAssignLedgers(
          job.id,
          rowList,
          '__AUTO_RESOLVE__',
          undefined,
          false,
          true,
          txIds,
          'AUTO_RESOLVE'
        );
        setJob(res);
        if (res.transactions && res.transactions.length > 0) {
          setTransactions(res.transactions);
        }
      } catch (err: any) {
        console.warn('Admin server sync notice:', err);
      }
    }
    setIsBulkAssigning(false);
  };

  const handleIgnoreWarnings = async (indicesToIgnore?: number[]) => {
    setIsBulkAssigning(true);
    setError('');

    const rowList = indicesToIgnore !== undefined && indicesToIgnore.length > 0 
      ? indicesToIgnore 
      : (selectedRowIndices.size > 0 
          ? Array.from(selectedRowIndices) 
          : transactions.map((_, i) => i).filter(i => transactions[i].validation_status !== 'VALID'));

    if (rowList.length === 0) {
      setIsBulkAssigning(false);
      return;
    }

    const txIds = rowList
      .map(idx => transactions[idx]?.id)
      .filter(Boolean) as string[];

    // Optimistic local update
    const updated = [...transactions];
    rowList.forEach(idx => {
      if (updated[idx]) {
        updated[idx] = {
          ...updated[idx],
          validation_status: 'VALID',
          validation_notes: undefined,
        };
      }
    });

    setTransactions(updated);
    setSelectedRowIndices(new Set());
    setSuccessMsg(`Marked warnings as resolved for ${rowList.length} transaction(s).`);
    setTimeout(() => setSuccessMsg(''), 4000);

    // Sync with server
    if (job?.id) {
      try {
        const res = await bulkAssignLedgers(
          job.id,
          rowList,
          '__IGNORE_WARNINGS__',
          undefined,
          false,
          true,
          txIds,
          'IGNORE_WARNINGS'
        );
        setJob(res);
        if (res.transactions && res.transactions.length > 0) {
          setTransactions(res.transactions);
        }
      } catch (err: any) {
        console.warn('Admin server sync notice:', err);
      }
    }
    setIsBulkAssigning(false);
  };

  const handleQuickAddLedger = (index: number) => {
    setQuickAddModalRow(index);
    setQuickLedgerName(transactions[index]?.party_name || '');
  };

  const handleConfirmQuickAdd = () => {
    if (quickAddModalRow !== null && quickLedgerName.trim()) {
      handleTransactionChange(quickAddModalRow, 'ledger_name', quickLedgerName.trim());
      if (!userLedgers.some(l => l.name.toLowerCase() === quickLedgerName.trim().toLowerCase())) {
        setUserLedgers(prev => [...prev, { 
          name: quickLedgerName.trim(), 
          normalized_name: quickLedgerName.trim().toUpperCase(), 
          group: 'Sundry Debtors/Creditors' 
        }]);
      }
    }
    setQuickAddModalRow(null);
    setQuickLedgerName('');
  };

  const handleGenerateExcel = async () => {
    if (!job) return;

    setGeneratingExcel(true);
    setError('');

    try {
      await reviewAdminTransactions(job.id, transactions, bankLedger, cashLedger);
      const res = await generateAdminExcel(job.id, bankLedger, cashLedger);
      setExcelResult(res);
      setSuccessMsg(`Excel successfully generated (${res.voucher_count} vouchers). Download started.`);
      
      try {
        await downloadFileBlob(res.download_url, res.filename);
      } catch (dlErr: any) {
        setSuccessMsg(`Excel successfully generated (${res.voucher_count} vouchers). Click Download Excel to save.`);
      }
    } catch (err: any) {
      const msg = err.message || 'Failed to generate Excel.';
      if (/not found|404|expired/i.test(msg)) {
        setError('Conversion session expired. Please click "New Statement" to re-upload your PDF.');
      } else {
        setError(msg);
      }
    } finally {
      setGeneratingExcel(false);
    }
  };

  const handleGenerateXml = async () => {
    if (!job) return;

    setGeneratingXml(true);
    setError('');

    try {
      // Push any unsaved transaction edits first
      await reviewAdminTransactions(job.id, transactions, bankLedger, cashLedger);
      
      const res = await generateAdminTallyXml(job.id, bankLedger, cashLedger, suspenseLedger);
      setXmlResult(res);
      setSuccessMsg(`Tally XML successfully generated (${res.voucher_count} vouchers). Starting download...`);
      
      try {
        await downloadFileBlob(res.download_url, res.filename);
      } catch (dlErr: any) {
        setSuccessMsg(`Tally XML successfully generated (${res.voucher_count} vouchers). Click Download Tally XML to save.`);
      }
    } catch (err: any) {
      const msg = err.message || 'Failed to generate Tally XML.';
      if (/not found|404|expired/i.test(msg)) {
        setError('Conversion session expired. Please click "New Statement" to re-upload your PDF.');
      } else {
        setError(msg);
      }
    } finally {
      setGeneratingXml(false);
    }
  };

  const handleDownloadXml = async () => {
    if (!job) return;
    try {
      const url = xmlResult?.download_url || `/api/conversions/${job.id}/download`;
      const filename = xmlResult?.filename || `${job.bank_name}_Statement.xml`;
      await downloadFileBlob(url, filename);
      setSuccessMsg(`Tally XML file "${filename}" downloaded successfully.`);
    } catch (err: any) {
      setError(err.message || 'Failed to download Tally XML.');
    }
  };

  const resetAll = () => {
    setFile(null);
    setPassword('');
    setJob(null);
    setTransactions([]);
    setXmlResult(null);
    setExcelResult(null);
    setError('');
    setSuccessMsg('');
    setSelectedRowIndices(new Set());
  };

  // Metrics
  const suspenseCount = transactions.filter(
    t => t.ledger_name === 'Suspense' || t.mapping_status === 'Suspense' || !t.ledger_name
  ).length;
  const mappedCount = transactions.length - suspenseCount;
  const errorCount = transactions.filter(t => t.validation_status === 'ERROR').length;
  const warningCount = transactions.filter(t => t.validation_status === 'WARNING').length;
  const duplicateCount = transactions.filter((t: any) => Boolean(t.is_duplicate_suspect)).length;
  const readyForExport = errorCount === 0;

  // Filtered transactions
  const filteredTxs = transactions.filter((t: any) => {
    const matchesSearch =
      searchQuery === '' ||
      t.narration.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.party_name && t.party_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (t.reference && t.reference.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (t.cheque_number && t.cheque_number.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (t.instrument_number && t.instrument_number.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (t.ledger_name && t.ledger_name.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (txFilter === 'SUSPENSE') {
      return t.ledger_name === 'Suspense' || t.mapping_status === 'Suspense' || !t.ledger_name;
    }
    if (txFilter === 'MAPPED') {
      return t.ledger_name !== 'Suspense' && t.mapping_status !== 'Suspense' && Boolean(t.ledger_name);
    }
    if (txFilter === 'PAYMENT') {
      return (t.voucher_type || '').toUpperCase() === 'PAYMENT';
    }
    if (txFilter === 'RECEIPT') {
      return (t.voucher_type || '').toUpperCase() === 'RECEIPT';
    }
    if (txFilter === 'CONTRA') {
      return (t.voucher_type || '').toUpperCase() === 'CONTRA';
    }
    if (txFilter === 'DUPLICATE') {
      return Boolean(t.is_duplicate_suspect);
    }
    if (txFilter === 'ERROR') {
      return t.validation_status === 'ERROR';
    }
    if (txFilter === 'WARNING') {
      return t.validation_status === 'WARNING';
    }

    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Admin Converter Studio
            </h1>
            <Badge variant="purple" size="sm">
              ADMIN • UNLIMITED
            </Badge>
            <Badge variant="success" size="sm">
              QUOTA EXEMPT
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            Enterprise conversion pipeline with master ledger mapping, directional voucher classifications, and deep telemetry.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsLedgerModalOpen(true)}
            icon={<BookOpen className="w-4 h-4 text-blue-600" />}
          >
            Import Tally Masters
            {userLedgers.length > 0 && (
              <span className="ml-1.5 px-2 py-0.2 bg-blue-100 text-blue-800 text-[10px] font-bold rounded-full">
                {userLedgers.length} Ledgers{userGroups.length > 0 ? ` & ${userGroups.length} Groups` : ''}
              </span>
            )}
          </Button>

          {job && (
            <Button
              variant="outline"
              size="sm"
              onClick={resetAll}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              New Statement
            </Button>
          )}
        </div>
      </div>

      {error && (
        <StatusAlert
          type="error"
          message={error}
          onDismiss={() => setError('')}
        />
      )}

      {successMsg && (
        <StatusAlert
          type="success"
          message={successMsg}
          onDismiss={() => setSuccessMsg('')}
        />
      )}

      {/* Step 1: Ingestion Form */}
      {!job && (
        <Card className="shadow-card overflow-hidden">
          <CardHeader className="bg-slate-50/70 border-b border-slate-100">
            <CardTitle>Bank Statement Ingestion (Admin Workspace)</CardTitle>
            <CardDescription>
              Upload any bank statement PDF. Configure target Tally bank and cash ledgers before or after processing.
            </CardDescription>
          </CardHeader>

          <CardContent className="p-6 sm:p-8 space-y-6">
            
            {/* Tally Master Pre-Configuration */}
            <div className="p-5 rounded-2xl bg-blue-50/30 border border-blue-100 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Target Tally Ledger Configuration
                  </span>
                  {userBankLedgers.length > 0 ? (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                      Master XML ({userBankLedgers.length} Banks)
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-semibold">
                      Default / Manual
                    </span>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsLedgerModalOpen(true)}
                  icon={<Sparkles className="w-3.5 h-3.5 text-blue-600" />}
                >
                  {userLedgers.length > 0 
                    ? `${userLedgers.length} Ledgers & ${userGroups.length} Groups Loaded` 
                    : 'Import Masters'}
                </Button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Bank Ledger Name in Tally
                  </label>
                  <input
                    type="text"
                    list="admin-bank-ledgers-step1"
                    value={bankLedger}
                    onChange={(e) => setBankLedger(e.target.value)}
                    placeholder="e.g. SBI Current Account"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                  <datalist id="admin-bank-ledgers-step1">
                    {userBankLedgers.map((b) => (
                      <option key={b.name} value={b.name}>
                        {b.name} ({b.group || 'Bank Accounts'})
                      </option>
                    ))}
                  </datalist>
                  {userBankLedgers.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-slate-400 font-medium">Quick Pick:</span>
                      {userBankLedgers.slice(0, 5).map((b) => (
                        <button
                          key={b.name}
                          type="button"
                          onClick={() => setBankLedger(b.name)}
                          className={`px-2 py-0.5 text-[10px] rounded-lg border transition-all ${
                            bankLedger === b.name
                              ? 'bg-brand-50 border-brand-500 text-brand-700 font-bold shadow-xs'
                              : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'
                          }`}
                        >
                          🏦 {b.name}
                        </button>
                      ))}
                    </div>
                  )}
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    Exact ledger created under Bank Accounts in Tally Prime
                  </span>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Cash Ledger Name in Tally
                  </label>
                  <input
                    type="text"
                    value={cashLedger}
                    onChange={(e) => setCashLedger(e.target.value)}
                    placeholder="e.g. Cash"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    Used for directional cash deposits and withdrawals (Default: Cash)
                  </span>
                </div>
              </div>
            </div>

            <form onSubmit={handleUpload} className="space-y-6">
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                onClick={() => document.getElementById('admin-file-input')?.click()}
                className={`p-10 border-2 border-dashed rounded-3xl text-center cursor-pointer transition-all ${
                  file
                    ? 'border-brand-500 bg-brand-50/20'
                    : 'border-slate-300 hover:border-brand-400 bg-slate-50/60 hover:bg-slate-50'
                }`}
              >
                <input
                  id="admin-file-input"
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setFile(e.target.files[0]);
                      setError('');
                    }
                  }}
                />

                <div className="w-14 h-14 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center mx-auto mb-3 border border-brand-200 shadow-xs">
                  <UploadCloud className="w-7 h-7" />
                </div>

                <div className="text-sm font-bold text-slate-800">
                  {file ? file.name : 'Drag and drop statement PDF here, or click to browse'}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  {file
                    ? `${(file.size / (1024 * 1024)).toFixed(2)} MB • PDF Ready for processing`
                    : 'Supports all Indian commercial bank statement formats (State Bank of India, PNB, HDFC, ICICI, etc.)'}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  type="password"
                  label="Statement Password (If Encrypted)"
                  placeholder="e.g. DOB, PAN, Account No."
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  helperText="Leave empty if statement PDF is not password-protected"
                />

                <div className="flex items-end">
                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    className="w-full bg-brand-600 hover:bg-brand-700"
                    disabled={!file || converting}
                    loading={converting}
                    icon={<Sparkles className="w-4 h-4" />}
                  >
                    {converting ? 'Processing Bank Statement...' : 'Convert Statement (Admin Bypass)'}
                  </Button>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Conversion Studio Result */}
      {job && (
        <div className="space-y-6 animate-fadeIn">
          
          {/* Overridden Bank Warning Banner */}
          {job.override_warning && (
            <div className="p-4 rounded-2xl bg-amber-50 border border-amber-300 text-amber-900 flex items-start gap-3 shadow-xs">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs">
                <strong className="font-bold block text-sm mb-0.5">Manual Bank Override Active:</strong>
                {job.override_warning}
              </div>
            </div>
          )}

          {/* PRD Summary Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Card className="p-3.5 shadow-xs">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block mb-1">
                Total Transactions
              </span>
              <strong className="text-xl font-black text-slate-900 font-mono">
                {transactions.length}
              </strong>
            </Card>

            <Card className="p-3.5 bg-emerald-50/30 border-emerald-200 shadow-xs">
              <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-700 block mb-1">
                Auto Mapped
              </span>
              <strong className="text-xl font-black text-emerald-800 font-mono">
                {mappedCount}
              </strong>
            </Card>

            <Card className={`p-3.5 shadow-xs ${
              suspenseCount > 0 ? 'bg-amber-50/40 border-amber-300' : 'bg-white'
            }`}>
              <span className={`text-[10px] uppercase font-bold tracking-wider block mb-1 ${
                suspenseCount > 0 ? 'text-amber-800' : 'text-slate-500'
              }`}>
                Requires Review
              </span>
              <strong className={`text-xl font-black font-mono ${
                suspenseCount > 0 ? 'text-amber-900' : 'text-slate-900'
              }`}>
                {suspenseCount}
              </strong>
            </Card>

            <Card className={`p-3.5 shadow-xs ${
              warningCount > 0 ? 'bg-amber-50/40 border-amber-300' : 'bg-white'
            }`}>
              <span className={`text-[10px] uppercase font-bold tracking-wider block mb-1 ${
                warningCount > 0 ? 'text-amber-800' : 'text-slate-500'
              }`}>
                Warnings
              </span>
              <strong className={`text-xl font-black font-mono ${
                warningCount > 0 ? 'text-amber-900' : 'text-slate-600'
              }`}>
                {warningCount}
              </strong>
            </Card>

            <Card className={`p-3.5 shadow-xs ${
              errorCount > 0 ? 'bg-rose-50/50 border-rose-300' : 'bg-white'
            }`}>
              <span className={`text-[10px] uppercase font-bold tracking-wider block mb-1 ${
                errorCount > 0 ? 'text-rose-700' : 'text-slate-500'
              }`}>
                Errors
              </span>
              <strong className={`text-xl font-black font-mono ${
                errorCount > 0 ? 'text-rose-700' : 'text-emerald-700'
              }`}>
                {errorCount}
              </strong>
            </Card>

            <Card className={`p-3.5 shadow-xs ${
              readyForExport ? 'bg-emerald-50/60 border-emerald-300' : 'bg-rose-50/60 border-rose-300'
            }`}>
              <span className={`text-[10px] uppercase font-bold tracking-wider block mb-1 ${
                readyForExport ? 'text-emerald-800' : 'text-rose-800'
              }`}>
                Ready for Export
              </span>
              <div className="flex items-center gap-1.5">
                {readyForExport ? (
                  <span className="inline-flex items-center gap-1 text-sm font-black text-emerald-800">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" /> READY
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-sm font-black text-rose-800">
                    <AlertCircle className="w-4 h-4 text-rose-600" /> BLOCKED ({errorCount})
                  </span>
                )}
              </div>
            </Card>
          </div>

          {/* Manual Bank Override Control */}
          <Card className="p-5 bg-slate-50/70 border border-slate-200">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-brand-600" />
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Manual Bank Parser Override
                  </h3>
                </div>
                <p className="text-[11px] text-slate-500">
                  Select a different bank adapter to re-process transactions with full custom rules.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={selectedOverrideBank}
                  onChange={(e) => setSelectedOverrideBank(e.target.value)}
                  className="px-3 py-2 bg-white rounded-xl border border-slate-300 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {supportedBanks.map((b) => (
                    <option key={b.parser_key} value={b.bank_name}>
                      {b.bank_name}
                    </option>
                  ))}
                </select>

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleBankOverride}
                  disabled={overriding || selectedOverrideBank === job.bank_name}
                  loading={overriding}
                >
                  Apply Override
                </Button>
              </div>
            </div>
          </Card>

          {/* Expandable Deep Diagnostics Drawer */}
          <Card className="overflow-hidden border border-slate-200">
            <div
              onClick={() => setShowDiagnostics(!showDiagnostics)}
              className="p-4 bg-slate-900 text-white flex items-center justify-between cursor-pointer hover:bg-slate-800 transition-colors"
            >
              <div className="flex items-center gap-2.5 text-xs font-bold">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Administrative Deep Diagnostics Telemetry (Admin Only)</span>
                <Badge variant="purple" size="sm">
                  {job.duration_ms} ms Latency
                </Badge>
              </div>
              <div className="text-slate-400">
                {showDiagnostics ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </div>
            </div>

            {showDiagnostics && (
              <div className="p-6 bg-slate-950 text-slate-200 text-xs space-y-6 font-mono border-t border-slate-800">
                
                {/* Mathematical Equation Breakdown */}
                <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                  <div className="text-emerald-400 font-bold uppercase text-[11px] tracking-wider">
                    Running Balance Verification Equation:
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 bg-slate-800/80 rounded-xl">
                      <span className="text-slate-400 text-[10px] block">Opening Balance</span>
                      <strong className="text-white text-sm">₹{job.opening_balance}</strong>
                    </div>
                    <div className="p-3 bg-slate-800/80 rounded-xl">
                      <span className="text-emerald-400 text-[10px] block">Total Credits (+)</span>
                      <strong className="text-emerald-400 text-sm">+₹{Number(job.total_credit).toFixed(2)}</strong>
                    </div>
                    <div className="p-3 bg-slate-800/80 rounded-xl">
                      <span className="text-rose-400 text-[10px] block">Total Debits (-)</span>
                      <strong className="text-rose-400 text-sm">-₹{Number(job.total_debit).toFixed(2)}</strong>
                    </div>
                    <div className="p-3 bg-slate-800/80 rounded-xl">
                      <span className="text-slate-400 text-[10px] block">Closing Balance</span>
                      <strong className="text-white text-sm">₹{job.closing_balance}</strong>
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-400 pt-1">
                    Mathematical Check: <span className="text-emerald-400 font-bold">₹{job.opening_balance} + ₹{Number(job.total_credit).toFixed(2)} - ₹{Number(job.total_debit).toFixed(2)} = ₹{job.closing_balance} (0.00 Discrepancy)</span>
                  </div>
                </div>

                {/* Candidate Detection Scores */}
                {job.candidates && job.candidates.length > 0 && (
                  <div>
                    <span className="text-slate-400 uppercase text-[10px] block mb-2 font-bold">Candidate Banks Evaluated:</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                      {job.candidates.map((c: any, i: number) => (
                        <div key={i} className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                          <span className="truncate text-slate-300">{c.bank_name || c.bank}</span>
                          <span className="text-brand-400 font-bold ml-2">{c.score}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Matched Signatures */}
                {job.detection_reasons && job.detection_reasons.length > 0 && (
                  <div>
                    <span className="text-slate-400 uppercase text-[10px] block mb-2 font-bold">Matched Header Signatures:</span>
                    <div className="flex flex-wrap gap-2">
                      {job.detection_reasons.map((r: string, i: number) => (
                        <span key={i} className="px-2.5 py-1 bg-slate-900 border border-slate-800 text-brand-300 rounded-lg text-[11px]">
                          ✓ {r}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Pipeline Stats */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-slate-800 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Pages Scanned</span>
                    <strong className="text-white">{job.page_count}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Transactions Detected</span>
                    <strong className="text-white">{transactions.length}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Mapped Rows</span>
                    <strong className="text-emerald-400">{mappedCount}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Suspense Rows</span>
                    <strong className="text-amber-400">{suspenseCount}</strong>
                  </div>
                </div>

              </div>
            )}
          </Card>

          {/* Double-Entry Ledger Mapping Configurations */}
          <Card className="p-6 shadow-card space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-brand-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Double-Entry Tally Ledger Configuration
                </h3>
                {userBankLedgers.length > 0 ? (
                  <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                    Master XML ({userBankLedgers.length} Banks)
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-semibold">
                    Default Ledgers
                  </span>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsLedgerModalOpen(true)}
                icon={<Sparkles className="w-3.5 h-3.5 text-brand-600" />}
                className="text-xs"
              >
                Upload / Manage Master XML
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Bank Account Ledger (Tally Master)
                </label>
                <input
                  type="text"
                  list="admin-bank-ledgers-step2"
                  value={bankLedger}
                  onChange={(e) => setBankLedger(e.target.value)}
                  placeholder="e.g. SBI Current Account"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                />
                <datalist id="admin-bank-ledgers-step2">
                  {userBankLedgers.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name} ({b.group || 'Bank Accounts'})
                    </option>
                  ))}
                </datalist>
                {userBankLedgers.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1">
                    <span className="text-[10px] text-slate-400 font-medium">Bank Accounts:</span>
                    {userBankLedgers.slice(0, 4).map((b) => (
                      <button
                        key={b.name}
                        type="button"
                        onClick={() => setBankLedger(b.name)}
                        className={`px-2 py-0.5 text-[10px] rounded-lg border transition-all ${
                          bankLedger === b.name
                            ? 'bg-brand-50 border-brand-500 text-brand-700 font-bold shadow-xs'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'
                        }`}
                      >
                        🏦 {b.name}
                      </button>
                    ))}
                  </div>
                )}
                <span className="text-[10px] text-slate-400 mt-1 block">
                  Primary ledger created under Bank Accounts in Tally
                </span>
              </div>
              <Input
                label="Cash Ledger (Tally Master)"
                value={cashLedger}
                onChange={(e) => setCashLedger(e.target.value)}
                helperText="Used for directional cash withdrawals & deposits"
              />
              <Input
                label="Default Suspense Ledger"
                value={suspenseLedger}
                onChange={(e) => setSuspenseLedger(e.target.value)}
                helperText="Applied to uncategorized counterparty transactions"
              />
            </div>
          </Card>

          {/* GROUPED WARNINGS & BULK RESOLUTION SUMMARY SECTION */}
          {(errorCount > 0 || warningCount > 0 || suspenseCount > 0 || duplicateCount > 0) && (
            <Card className="p-5 shadow-card space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-black text-slate-900 tracking-tight">
                      Administrative Transaction Health & Warning Resolution
                    </h3>
                    {errorCount === 0 && (
                      <Badge variant="success" size="sm">Zero Blocking Errors</Badge>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">
                    Grouped by root cause. Resolve unmapped ledgers, review balance math, or ignore non-critical warnings in bulk.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleAutoResolveFallback()}
                    loading={isBulkAssigning}
                    icon={<Sparkles className="w-3.5 h-3.5" />}
                    className="bg-brand-600 hover:bg-brand-700 text-white font-bold"
                  >
                    Auto-Resolve Fallback (Dr→Pmt, Cr→Rcpt)
                  </Button>
                  {(warningCount > 0 || errorCount > 0) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleIgnoreWarnings()}
                      loading={isBulkAssigning}
                      className="border-slate-300 text-slate-700 hover:bg-slate-100 font-bold"
                    >
                      Ignore Non-Critical Warnings
                    </Button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                {/* Group 1: Running Balance Math */}
                <div className={`p-4 rounded-2xl border ${
                  errorCount > 0 ? 'bg-rose-50/50 border-rose-200 text-rose-900' : warningCount > 0 ? 'bg-amber-50/50 border-amber-200 text-amber-900' : 'bg-emerald-50/40 border-emerald-200 text-emerald-900'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-bold uppercase tracking-wider text-[10px]">
                      1. Balance Math Audit
                    </span>
                    {errorCount > 0 ? (
                      <Badge variant="danger" size="sm">{errorCount} Errors</Badge>
                    ) : warningCount > 0 ? (
                      <Badge variant="warning" size="sm">{warningCount} Warnings</Badge>
                    ) : (
                      <Badge variant="success" size="sm">100% Verified</Badge>
                    )}
                  </div>
                  <p className="text-[11px] mb-3 leading-relaxed opacity-90">
                    {errorCount > 0
                      ? `${errorCount} row(s) have running balance variance > ₹1.00. Review or override to enable Tally export.`
                      : warningCount > 0
                      ? `${warningCount} row(s) have minor sub-rupee rounding differences (non-blocking).`
                      : 'All row balances verified chronologically.'}
                  </p>
                  <div className="flex items-center gap-2">
                    {errorCount > 0 ? (
                      <button
                        type="button"
                        onClick={() => setTxFilter('ERROR')}
                        className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-bold transition-all shadow-xs"
                      >
                        Filter Errors ({errorCount})
                      </button>
                    ) : warningCount > 0 ? (
                      <button
                        type="button"
                        onClick={() => setTxFilter('WARNING')}
                        className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-[11px] font-bold transition-all shadow-xs"
                      >
                        Filter Warnings ({warningCount})
                      </button>
                    ) : null}
                    {(errorCount > 0 || warningCount > 0) && (
                      <button
                        type="button"
                        onClick={() => handleIgnoreWarnings()}
                        className="px-2.5 py-1 bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg text-[11px] font-semibold"
                      >
                        Ignore Math Flags
                      </button>
                    )}
                  </div>
                </div>

                {/* Group 2: Requires Review / Suspense */}
                <div className={`p-4 rounded-2xl border ${
                  suspenseCount > 0 ? 'bg-amber-50/50 border-amber-200 text-amber-900' : 'bg-emerald-50/40 border-emerald-200 text-emerald-900'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-bold uppercase tracking-wider text-[10px]">
                      2. Ledger Allocation
                    </span>
                    <span className="font-mono font-bold text-xs">{suspenseCount} Unmapped</span>
                  </div>
                  <p className="text-[11px] mb-3 leading-relaxed opacity-90">
                    {suspenseCount > 0
                      ? `${suspenseCount} transaction(s) routed to Suspense without automatic high-confidence party match.`
                      : 'All transactions successfully mapped to verified ledger accounts.'}
                  </p>
                  <div className="flex items-center gap-2">
                    {suspenseCount > 0 && (
                      <>
                        <button
                          type="button"
                          onClick={() => setTxFilter('SUSPENSE')}
                          className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-[11px] font-bold transition-all shadow-xs"
                        >
                          Review Suspense ({suspenseCount})
                        </button>
                        <button
                          type="button"
                          onClick={() => handleAutoResolveFallback()}
                          className="px-2.5 py-1 bg-white border border-amber-300 text-amber-900 hover:bg-amber-100/50 rounded-lg text-[11px] font-bold"
                        >
                          Auto-Resolve
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Group 3: Duplicate Suspects */}
                <div className={`p-4 rounded-2xl border ${
                  duplicateCount > 0 ? 'bg-purple-50/50 border-purple-200 text-purple-900' : 'bg-slate-50 border-slate-200 text-slate-700'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-bold uppercase tracking-wider text-[10px]">
                      3. Duplicate Audit
                    </span>
                    <span className="font-mono font-bold text-xs">{duplicateCount} Candidates</span>
                  </div>
                  <p className="text-[11px] mb-3 leading-relaxed opacity-90">
                    {duplicateCount > 0
                      ? `${duplicateCount} transaction(s) share identical date, amount, and narration.`
                      : 'No duplicate candidate transactions detected in this statement.'}
                  </p>
                  <div className="flex items-center gap-2">
                    {duplicateCount > 0 && (
                      <button
                        type="button"
                        onClick={() => setTxFilter('DUPLICATE')}
                        className="px-2.5 py-1 bg-purple-700 hover:bg-purple-800 text-white rounded-lg text-[11px] font-bold transition-all shadow-xs"
                      >
                        Review Duplicates ({duplicateCount})
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Filter Tabs & Search Toolbar */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { key: 'ALL', label: `All (${transactions.length})` },
                { key: 'SUSPENSE', label: `Requires Review (${suspenseCount})`, alert: suspenseCount > 0 },
                ...(errorCount > 0 ? [{ key: 'ERROR', label: `Errors (${errorCount})`, isError: true }] : []),
                ...(warningCount > 0 ? [{ key: 'WARNING', label: `Warnings (${warningCount})`, isWarn: true }] : []),
                { key: 'MAPPED', label: `Mapped (${mappedCount})` },
                { key: 'PAYMENT', label: 'Payment' },
                { key: 'RECEIPT', label: 'Receipt' },
                { key: 'CONTRA', label: 'Contra' },
                ...(duplicateCount > 0 ? [{ key: 'DUPLICATE', label: `Duplicates (${duplicateCount})`, isDup: true }] : []),
              ].map((tab: any) => (
                <button
                  key={tab.key}
                  onClick={() => setTxFilter(tab.key)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                    txFilter === tab.key
                      ? tab.isError
                        ? 'bg-rose-700 text-white shadow-xs'
                        : tab.isWarn
                        ? 'bg-amber-600 text-white shadow-xs'
                        : tab.alert
                        ? 'bg-amber-600 text-white shadow-xs'
                        : tab.isDup
                        ? 'bg-purple-700 text-white shadow-xs'
                        : 'bg-slate-900 text-white shadow-xs'
                      : tab.isError
                      ? 'bg-rose-50 text-rose-800 border border-rose-300 hover:bg-rose-100'
                      : tab.isWarn
                      ? 'bg-amber-50 text-amber-800 border border-amber-300 hover:bg-amber-100'
                      : tab.alert
                      ? 'bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100'
                      : tab.isDup
                      ? 'bg-purple-50 text-purple-800 border border-purple-200 hover:bg-purple-100'
                      : 'bg-slate-100/70 text-slate-700 hover:bg-slate-200/80 border border-slate-200/60'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="relative w-full md:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search narration, party, cheque..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>
          </div>

          {/* STICKY BULK ACTIONS BAR */}
          {selectedRowIndices.size > 0 && (
            <div className="sticky top-4 z-30 p-4 rounded-2xl bg-slate-900 text-white shadow-elevated border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-in slide-in-from-top-2">
              <div className="flex items-center gap-3">
                <div className="px-2.5 py-1 rounded-lg bg-brand-500 text-white font-black text-xs font-mono">
                  {selectedRowIndices.size}
                </div>
                <span className="text-xs font-bold">rows selected for bulk action</span>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <input
                  type="text"
                  list="admin-ledgers-datalist"
                  placeholder="Assign Ledger Name..."
                  value={bulkLedger}
                  onChange={(e) => setBulkLedger(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleBulkAssign();
                    }
                  }}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-xs text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />

                <select
                  value={bulkVoucher}
                  onChange={(e) => setBulkVoucher(e.target.value)}
                  className="px-2.5 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-xs text-white focus:outline-none"
                >
                  <option value="">Keep Voucher Type</option>
                  <option value="Payment">Payment</option>
                  <option value="Receipt">Receipt</option>
                  <option value="Contra">Contra</option>
                  <option value="Journal">Journal</option>
                </select>

                <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={applyToSimilar}
                    onChange={(e) => setApplyToSimilar(e.target.checked)}
                    className="rounded text-brand-500"
                  />
                  <span>Apply to similar narrations</span>
                </label>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleBulkAssign}
                  disabled={!bulkLedger.trim() || isBulkAssigning}
                  loading={isBulkAssigning}
                  className="bg-brand-500 hover:bg-brand-600 text-white font-bold"
                >
                  Assign Ledger
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleAutoResolveFallback(Array.from(selectedRowIndices))}
                  disabled={isBulkAssigning}
                  className="border-slate-700 text-slate-200 hover:bg-slate-800 text-xs"
                >
                  Auto-Resolve Fallback
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleIgnoreWarnings(Array.from(selectedRowIndices))}
                  disabled={isBulkAssigning}
                  className="border-slate-700 text-slate-200 hover:bg-slate-800 text-xs"
                >
                  Ignore Warnings
                </Button>

                <button
                  onClick={() => setSelectedRowIndices(new Set())}
                  className="text-xs text-slate-400 hover:text-white px-2 py-1"
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {/* Datalist for Ledger Autocomplete */}
          <datalist id="admin-ledgers-datalist">
            <option value="Suspense" />
            <option value={cashLedger || "Cash"} />
            {userLedgers.map((l, i) => (
              <option key={i} value={l.name} />
            ))}
          </datalist>

          {/* Transaction Review Table */}
          <Card className="shadow-card overflow-hidden">
            <div className="p-4 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between text-xs">
              <div className="font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                <Edit2 className="w-4 h-4 text-brand-600" />
                Review & Map Transactions ({filteredTxs.length} of {transactions.length})
              </div>
              <span className="text-slate-500 text-[11px] hidden sm:inline">
                Click any cell to edit narration, date, amount, cheque, or Tally ledger
              </span>
            </div>

            <div className="overflow-x-auto max-h-[600px] divide-y divide-slate-100">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-100/90 text-slate-600 font-bold uppercase tracking-wider text-[10px] sticky top-0 z-20 border-b border-slate-200 backdrop-blur-xs">
                  <tr>
                    <th className="px-3 py-3 text-center w-8">
                      <input
                        type="checkbox"
                        checked={filteredTxs.length > 0 && filteredTxs.every((tx: any) => {
                          const idx = transactions.indexOf(tx);
                          return idx !== -1 && selectedRowIndices.has(idx);
                        })}
                        onChange={handleToggleSelectAll}
                        className="rounded text-brand-600 focus:ring-0"
                      />
                    </th>
                    <th className="px-2.5 py-3 text-center w-10">#</th>
                    <th className="px-3 py-3 w-28">Date</th>
                    <th className="px-3 py-3 min-w-[280px]">Narration & Entity</th>
                    <th className="px-3 py-3 w-28">Cheque / Ref</th>
                    <th className="px-3 py-3 text-right w-24 text-rose-600">Debit (Dr)</th>
                    <th className="px-3 py-3 text-right w-24 text-emerald-600">Credit (Cr)</th>
                    <th className="px-3 py-3 text-right w-24">Balance</th>
                    <th className="px-3 py-3 w-48">Counterparty Ledger</th>
                    <th className="px-3 py-3 w-28">Voucher Type</th>
                    <th className="px-3 py-3 text-center w-20">Audit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {filteredTxs.map((tx: any, fIdx: number) => {
                    const origIndex = transactions.indexOf(tx);
                    const isSelected = selectedRowIndices.has(origIndex);
                    const isSuspense = tx.ledger_name === 'Suspense' || tx.mapping_status === 'Suspense' || !tx.ledger_name;

                    return (
                      <tr
                        key={tx.id || origIndex}
                        className={`hover:bg-slate-50/80 transition-colors ${
                          isSelected ? 'bg-brand-50/30' : isSuspense ? 'bg-amber-50/20' : ''
                        }`}
                      >
                        <td className="px-3 py-2.5 text-center">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleRowSelection(origIndex)}
                            className="rounded text-brand-600 focus:ring-0"
                          />
                        </td>
                        <td className="px-2.5 py-2.5 text-center text-slate-400 font-mono text-[11px]">
                          {origIndex + 1}
                        </td>
                        <td className="px-3 py-2.5">
                          <input
                            type="text"
                            value={tx.date}
                            onChange={(e) => handleTransactionChange(origIndex, 'date', e.target.value)}
                            className="w-full px-1.5 py-1 rounded border border-transparent hover:border-slate-300 focus:border-brand-500 font-mono text-xs bg-transparent focus:bg-white"
                          />
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="space-y-1">
                            <textarea
                              rows={Math.min(4, Math.max(1, Math.ceil((tx.narration || '').length / 42)))}
                              value={tx.narration}
                              onChange={(e) => handleTransactionChange(origIndex, 'narration', e.target.value)}
                              className="w-full px-1.5 py-1 rounded border border-transparent hover:border-slate-300 focus:border-brand-500 text-xs bg-transparent focus:bg-white resize-y font-medium text-slate-900 leading-snug break-words whitespace-pre-wrap transition-all"
                              title={tx.full_narration || tx.original_narration || tx.narration}
                            />
                            <div className="flex flex-wrap items-center gap-1.5">
                              {tx.is_duplicate_suspect && (
                                <span
                                  className="inline-flex items-center gap-1 text-[10px] font-bold text-purple-800 bg-purple-100 px-1.5 py-0.2 rounded border border-purple-200"
                                  title={tx.duplicate_reason || 'Duplicate candidate: Identical date, amount, and narration'}
                                >
                                  Duplicate
                                </span>
                              )}
                              {tx.party_name && (
                                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-brand-800 bg-brand-50 px-2 py-0.2 rounded border border-brand-200">
                                  Party: {tx.party_name}
                                </span>
                              )}
                              {tx.is_cash_transaction && (
                                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-800 bg-amber-100 px-1.5 py-0.2 rounded">
                                  Cash: {tx.cash_transaction_type || 'Cash'}
                                </span>
                              )}
                              {tx.upi_ref && (
                                <span className="text-[10px] text-slate-400 font-mono">
                                  UPI: {tx.upi_ref}
                                </span>
                              )}
                              {tx.utr && (
                                <span className="text-[10px] text-slate-400 font-mono">
                                  UTR: {tx.utr}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <input
                            type="text"
                            value={tx.instrument_number || tx.cheque_number || tx.reference || ''}
                            onChange={(e) => {
                              handleTransactionChange(origIndex, 'instrument_number', e.target.value);
                              handleTransactionChange(origIndex, 'reference', e.target.value);
                            }}
                            placeholder="—"
                            className="w-full px-1.5 py-1 rounded border border-transparent hover:border-slate-300 focus:border-brand-500 font-mono text-xs bg-transparent focus:bg-white text-slate-700"
                          />
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={Number(tx.debit)}
                            onChange={(e) => handleTransactionChange(origIndex, 'debit', e.target.value)}
                            className="w-20 text-right px-1.5 py-1 rounded border border-transparent hover:border-slate-300 focus:border-brand-500 font-mono font-bold text-rose-600 bg-transparent focus:bg-white"
                          />
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={Number(tx.credit)}
                            onChange={(e) => handleTransactionChange(origIndex, 'credit', e.target.value)}
                            className="w-20 text-right px-1.5 py-1 rounded border border-transparent hover:border-slate-300 focus:border-brand-500 font-mono font-bold text-emerald-600 bg-transparent focus:bg-white"
                          />
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono font-medium text-slate-700 tabular-nums text-xs">
                          {tx.balance !== undefined && tx.balance !== null ? `₹${Number(tx.balance).toFixed(2)}` : '—'}
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="space-y-1">
                            <div className="flex items-center gap-1">
                              <input
                                type="text"
                                list="admin-ledgers-datalist"
                                value={tx.ledger_name || ''}
                                onChange={(e) => handleTransactionChange(origIndex, 'ledger_name', e.target.value)}
                                placeholder="Type or select ledger..."
                                className={`w-full px-2 py-1 rounded-lg border text-xs font-semibold focus:ring-1 focus:ring-brand-500 bg-white ${
                                  isSuspense 
                                    ? 'border-amber-300 text-amber-900 bg-amber-50/50' 
                                    : 'border-slate-300 text-slate-900'
                                }`}
                              />
                              <button
                                type="button"
                                title="Add new ledger name"
                                onClick={() => handleQuickAddLedger(origIndex)}
                                className="p-1 rounded hover:bg-slate-200 text-slate-500"
                              >
                                <Plus className="w-3.5 h-3.5" />
                              </button>
                            </div>
                            <div className="flex items-center gap-1.5">
                              {isSuspense ? (
                                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                                  Suspense
                                </span>
                              ) : (
                                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                                  Mapped
                                </span>
                              )}
                              {tx.suggested_ledger && tx.suggested_ledger !== tx.ledger_name && (
                                <button
                                  type="button"
                                  onClick={() => handleTransactionChange(origIndex, 'ledger_name', tx.suggested_ledger)}
                                  className="text-[10px] text-blue-600 hover:underline truncate max-w-[120px]"
                                  title={`Click to apply: ${tx.suggested_ledger}`}
                                >
                                  Suggest: {tx.suggested_ledger}
                                </button>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <select
                            value={tx.voucher_type}
                            onChange={(e) => handleTransactionChange(origIndex, 'voucher_type', e.target.value)}
                            className="w-full px-2 py-1 rounded-lg border border-slate-200 text-xs font-semibold bg-white text-slate-700"
                          >
                            <option value="Payment">Payment</option>
                            <option value="Receipt">Receipt</option>
                            <option value="Contra">Contra</option>
                            <option value="Journal">Journal</option>
                          </select>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          {tx.validation_status === 'VALID' ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-600">
                              <Check className="w-3.5 h-3.5" /> Balanced
                            </span>
                          ) : tx.validation_status === 'ERROR' ? (
                            <span
                              title={tx.validation_notes || 'Severe math balance mismatch'}
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-700 bg-rose-100/80 px-2 py-0.5 rounded cursor-help border border-rose-300"
                            >
                              <AlertCircle className="w-3.5 h-3.5" /> Error
                            </span>
                          ) : (
                            <span
                              title={tx.validation_notes || 'Minor rounding or boundary warning'}
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700 bg-amber-100/70 px-2 py-0.5 rounded cursor-help border border-amber-200"
                            >
                              <AlertTriangle className="w-3.5 h-3.5" /> Warning
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Action Footer: Generate & Download Tally XML */}
          <div className="p-6 bg-white rounded-3xl border border-slate-200 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <FileCode className="w-5 h-5 text-brand-600" />
                <h3 className="font-bold text-slate-900 text-sm">
                  Production Double-Entry Tally XML Generation
                </h3>
              </div>
              <p className="text-xs text-slate-500">
                Preserves verbatim ledger masters, directional cash vouchers, and strict double-entry balance.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                size="lg"
                onClick={handleGenerateExcel}
                disabled={generatingExcel || transactions.length === 0}
                loading={generatingExcel}
                className="border-emerald-600/50 hover:bg-emerald-50 text-emerald-700 font-bold"
                icon={<FileSpreadsheet className="w-4 h-4 text-emerald-600" />}
              >
                Download Excel
              </Button>

              <Button
                variant="primary"
                size="lg"
                onClick={handleGenerateXml}
                disabled={generatingXml || transactions.length === 0}
                loading={generatingXml}
                className="bg-brand-600 hover:bg-brand-700 font-bold"
                icon={<Sparkles className="w-4 h-4" />}
              >
                Generate Tally XML
              </Button>

              {(xmlResult || job.xml_content) && (
                <Button
                  variant="success"
                  size="lg"
                  onClick={handleDownloadXml}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  icon={<Download className="w-4 h-4" />}
                >
                  Download Tally XML
                </Button>
              )}
            </div>
          </div>

          {error && (
            <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-xs font-semibold flex items-center justify-between shadow-xs">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{error}</span>
              </div>
              <button onClick={() => setError('')} className="text-rose-500 hover:text-rose-700 font-bold text-sm px-2">✕</button>
            </div>
          )}

          {successMsg && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center justify-between shadow-xs">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>{successMsg}</span>
              </div>
              <button onClick={() => setSuccessMsg('')} className="text-emerald-500 hover:text-emerald-700 font-bold text-sm px-2">✕</button>
            </div>
          )}

        </div>
      )}

      {/* Quick Add Ledger Modal */}
      <Modal
        isOpen={quickAddModalRow !== null}
        onClose={() => setQuickAddModalRow(null)}
        title="Add / Assign Ledger"
        description="Assign a custom ledger name to this transaction row and save it to your masters."
        maxWidth="sm"
      >
        <div className="space-y-4">
          <Input
            label="Ledger Name in Tally"
            placeholder="e.g. ABC Traders Pvt Ltd"
            value={quickLedgerName}
            onChange={(e) => setQuickLedgerName(e.target.value)}
            autoFocus
          />

          <div className="flex gap-2.5 pt-2">
            <Button
              variant="outline"
              size="md"
              className="w-1/2"
              onClick={() => setQuickAddModalRow(null)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="md"
              className="w-1/2"
              disabled={!quickLedgerName.trim()}
              onClick={handleConfirmQuickAdd}
            >
              Apply Ledger
            </Button>
          </div>
        </div>
      </Modal>

      {/* Import My Tally Ledgers Modal */}
      <LedgerImportModal
        isOpen={isLedgerModalOpen}
        onClose={() => {
          setIsLedgerModalOpen(false);
          loadLedgers();
        }}
        onLedgersUpdated={() => loadLedgers()}
      />

    </div>
  );
}
