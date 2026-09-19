'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { 
  UploadCloud, 
  CheckCircle2, 
  AlertTriangle, 
  AlertCircle,
  Download, 
  ArrowRight, 
  Lock, 
  RefreshCw, 
  Edit2, 
  Check, 
  Building2,
  FileCode,
  ShieldAlert,
  Search,
  FileText,
  Sparkles,
  Layers,
  ChevronRight,
  Info,
  Filter,
  HelpCircle,
  BookOpen,
  Plus,
  Tag,
  CheckSquare,
  Square,
  CornerDownRight,
  X,
  CreditCard,
  FileSpreadsheet,
  QrCode,
  Copy,
  ExternalLink,
  MessageCircle
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { 
  uploadStatementPdf, 
  reviewTransactions, 
  selectBankForJob,
  generateXml,
  generateExcel,
  getUserUsage, 
  getSupportedBanks,
  getUserLedgers,
  getUserGroups,
  getUserBankLedgers,
  getUserBankConfigs,
  setUserBankConfig,
  updateTransactionRow,
  bulkAssignLedgers,
  BankInfo, 
  UsageInfo, 
  ConversionJobSummary, 
  TransactionItem,
  ImportedLedger,
  ImportedGroup,
  getAuthToken,
  setAuthToken,
  downloadFileBlob,
  getPaymentConfig,
  submitPaymentRequest,
  processRemainingPages,
  PaymentConfig,
  PaymentRequest
} from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { ProgressSteps } from '@/components/ui/ProgressSteps';
import LedgerImportModal from '@/components/LedgerImportModal';

const WORKFLOW_STEPS = [
  { number: 1, label: 'Upload Statement' },
  { number: 2, label: 'Bank Detection' },
  { number: 3, label: 'Balance Math Audit' },
  { number: 4, label: 'Review Transactions' },
  { number: 5, label: 'Ledger Mapping' },
  { number: 6, label: 'Generate Tally XML' },
];

export default function ConvertPage() {
  const router = useRouter();

  // Current active step: 1 (Upload), 2 (Detecting/Processing), 4 (Review/Mapping), 6 (Completed)
  const [currentStep, setCurrentStep] = useState(1);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [supportedBanks, setSupportedBanks] = useState<BankInfo[]>([]);
  const [userLedgers, setUserLedgers] = useState<ImportedLedger[]>([]);
  const [userGroups, setUserGroups] = useState<ImportedGroup[]>([]);
  const [userBankLedgers, setUserBankLedgers] = useState<ImportedLedger[]>([]);
  const [isLedgerModalOpen, setIsLedgerModalOpen] = useState(false);
  
  // File & Encryption
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [modalPasswordError, setModalPasswordError] = useState('');
  const [bankOverride, setBankOverride] = useState('');
  const [dragActive, setDragActive] = useState(false);
  
  // Bank & Cash Tally Ledger Configurations (Mandatory User Configs)
  const [bankLedgerName, setBankLedgerName] = useState('Bank Account');
  const [cashLedgerName, setCashLedgerName] = useState('Cash');
  const [savingBankConfig, setSavingBankConfig] = useState(false);
  // Result data
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);

  // Processing status
  const [processingStep, setProcessingStep] = useState('Uploading PDF statement...');
  const [job, setJob] = useState<ConversionJobSummary | null>(null);
  const [generatingXml, setGeneratingXml] = useState(false);
  const [selectedManualBank, setSelectedManualBank] = useState('');
  const [resolvingAmbiguous, setResolvingAmbiguous] = useState(false);
  
  // Search & Filter within Review Table
  const [txSearch, setTxSearch] = useState('');
  const [filterTab, setFilterTab] = useState<'ALL' | 'SUSPENSE' | 'MAPPED' | 'PAYMENT' | 'RECEIPT' | 'CONTRA' | 'WARNING' | 'ERROR' | 'DUPLICATE'>('ALL');
  
  // Multi-row Selection & Bulk Actions Bar
  const [selectedRowIndices, setSelectedRowIndices] = useState<Set<number>>(new Set());
  const [bulkLedger, setBulkLedger] = useState('');
  const [bulkVoucher, setBulkVoucher] = useState('');
  const [applyToSimilar, setApplyToSimilar] = useState(false);
  const [isBulkAssigning, setIsBulkAssigning] = useState(false);
  
  // Quick Add Ledger Modal
  const [quickAddModalRow, setQuickAddModalRow] = useState<number | null>(null);
  const [quickLedgerName, setQuickLedgerName] = useState('');
  
  // XML Download & Feedback
  const [xmlResult, setXmlResult] = useState<{ filename: string; download_url: string } | null>(null);
  const [excelResult, setExcelResult] = useState<{ filename: string; download_url: string } | null>(null);
  const [generatingExcel, setGeneratingExcel] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [referenceId, setReferenceId] = useState('');

  // Paid Extra Pages via UPI / QR State
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentConfig, setPaymentConfig] = useState<PaymentConfig | null>(null);
  const [paymentPages, setPaymentPages] = useState<number>(50);
  const [paymentNotes, setPaymentNotes] = useState('');
  const [paymentScreenshot, setPaymentScreenshot] = useState<File | null>(null);
  const [submittingPayment, setSubmittingPayment] = useState(false);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [paymentError, setPaymentError] = useState('');
  const [copiedUpi, setCopiedUpi] = useState(false);
  const [processingRemaining, setProcessingRemaining] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      router.push('/login?redirect=/convert');
      return;
    }
    getUserUsage().then(setUsage).catch(() => {});
    getSupportedBanks().then(setSupportedBanks).catch(() => {});
    getPaymentConfig().then(setPaymentConfig).catch(() => {});
    loadUserLedgers();
    getUserBankConfigs().then((configs) => {
      if (configs['__cash__']) {
        setCashLedgerName(configs['__cash__']);
      }
    }).catch(() => {});
  }, [router]);

  const loadUserLedgers = async () => {
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

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (selectedFile: File) => {
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Only bank-generated PDF statements are supported. Please upload a PDF file.');
      return;
    }
    setFile(selectedFile);
    setErrorMsg('');
  };

  const startConversion = async (pdfPassword?: string) => {
    if (!file) return;
    setErrorMsg('');
    setCurrentStep(2);
    setProcessingStep('Analyzing PDF structure & checking page quota...');

    try {
      setTimeout(() => {
        setCurrentStep(3);
        setProcessingStep('Detecting bank signature & column boundaries...');
      }, 700);

      setTimeout(() => {
        setProcessingStep('Extracting transactions, party names, and instrument numbers...');
      }, 1400);

      const jobData = await uploadStatementPdf(
        file, 
        pdfPassword || password, 
        bankOverride,
        bankLedgerName,
        cashLedgerName
      );
      setJob(jobData);
      setShowPasswordModal(false);

      if (jobData.bank_ledger_name) {
        setBankLedgerName(jobData.bank_ledger_name);
      } else if (jobData.bank_name) {
        setBankLedgerName(`${jobData.bank_name} A/C`);
      }
      if (jobData.cash_ledger_name) {
        setCashLedgerName(jobData.cash_ledger_name);
      }

      if (jobData.status === 'AMBIGUOUS_BANK' || jobData.is_ambiguous) {
        setCurrentStep(2);
        setSelectedManualBank(jobData.bank_name !== 'Unable to confidently identify' ? jobData.bank_name : '');
      } else {
        setTransactions(jobData.transactions || []);
        setCurrentStep(4);
      }

      if (jobData.remaining_pages && jobData.remaining_pages > 0) {
        setPaymentPages(jobData.remaining_pages);
      } else if (jobData.pages_skipped && jobData.pages_skipped > 0) {
        setPaymentPages(jobData.pages_skipped);
      } else if (jobData.status === 'QUOTA_EXHAUSTED' && jobData.total_pdf_pages) {
        setPaymentPages(jobData.total_pdf_pages);
      }

      getUserUsage().then(setUsage).catch(() => {});
    } catch (err: any) {
      setCurrentStep(1);
      const isPasswordIssue =
        err.code === 'ERR_PDF_PASSWORD_REQUIRED' ||
        err.code === 'ERR_PDF_ENCRYPTED' ||
        err.code === 'ERR_INVALID_PASSWORD' ||
        err.status === 401 ||
        (err.message && /password|encrypt|protected/i.test(err.message));

      if (isPasswordIssue) {
        setShowPasswordModal(true);
        if (err.message && /incorrect/i.test(err.message)) {
          setModalPasswordError(err.message);
        } else {
          setModalPasswordError('');
        }
      } else {
        setErrorMsg(err.message || 'Statement conversion failed.');
        setReferenceId(err.reference_id || '');
      }
    }
  };

  const handleConfirmManualBank = async () => {
    if (!job || !selectedManualBank) return;
    setResolvingAmbiguous(true);
    setErrorMsg('');
    try {
      const updatedJob = await selectBankForJob(job.id, selectedManualBank);
      setJob(updatedJob);
      setTransactions(updatedJob.transactions || []);
      if (updatedJob.bank_ledger_name) {
        setBankLedgerName(updatedJob.bank_ledger_name);
      } else {
        setBankLedgerName(`${updatedJob.bank_name} A/C`);
      }
      setCurrentStep(4);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to parse statement with selected bank.');
    } finally {
      setResolvingAmbiguous(false);
    }
  };

  const handleTransactionChange = async (index: number, field: keyof TransactionItem, value: any) => {
    const updated = [...transactions];
    const oldRow = updated[index];
    const newRow = { ...oldRow, [field]: value };
    
    // If ledger name was changed, update mapping status
    if (field === 'ledger_name') {
      newRow.mapping_status = (value === 'Suspense' || !value) ? 'Suspense' : 'Mapped';
      newRow.mapping_confidence = 100;
    }
    
    updated[index] = newRow;
    setTransactions(updated);

    // Sync with backend if job exists
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
          await updateTransactionRow(job.id, index, payload, false);
        }
      } catch {
        // Local state already updated, will be pushed during review/generate
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
    const isAllFilteredSelected = filteredTransactions.length > 0 && filteredTransactions.every(tx => {
      const idx = transactions.indexOf(tx);
      return idx !== -1 && selectedRowIndices.has(idx);
    });

    const next = new Set(selectedRowIndices);
    if (isAllFilteredSelected) {
      filteredTransactions.forEach(tx => {
        const idx = transactions.indexOf(tx);
        if (idx !== -1) next.delete(idx);
      });
    } else {
      filteredTransactions.forEach(tx => {
        const idx = transactions.indexOf(tx);
        if (idx !== -1) next.add(idx);
      });
    }
    setSelectedRowIndices(next);
  };

  const handleBulkAssign = async () => {
    if (!bulkLedger.trim() || selectedRowIndices.size === 0) return;
    setIsBulkAssigning(true);
    setErrorMsg('');

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
        const nMatch = Array.from(targetParties).some(p => t.narration.toUpperCase().includes(p));
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
          false,
          txIds
        );
        setJob(res);
        if (res.transactions && res.transactions.length > 0) {
          setTransactions(res.transactions);
        }
      } catch (err: any) {
        console.warn('Server sync notice:', err);
      }
    }

    setIsBulkAssigning(false);
  };

  const handleAutoResolveFallback = async (indicesToResolve?: number[]) => {
    setIsBulkAssigning(true);
    setErrorMsg('');

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
          false,
          txIds,
          'AUTO_RESOLVE'
        );
        setJob(res);
        if (res.transactions && res.transactions.length > 0) {
          setTransactions(res.transactions);
        }
      } catch (err: any) {
        console.warn('Server sync notice:', err);
      }
    }
    setIsBulkAssigning(false);
  };

  const handleIgnoreWarnings = async (indicesToIgnore?: number[]) => {
    setIsBulkAssigning(true);
    setErrorMsg('');

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
          false,
          txIds,
          'IGNORE_WARNINGS'
        );
        setJob(res);
        if (res.transactions && res.transactions.length > 0) {
          setTransactions(res.transactions);
        }
      } catch (err: any) {
        console.warn('Server sync notice:', err);
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
      // Also add to userLedgers for reuse
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

  const handleDownloadExcel = async () => {
    if (!job) return;
    setErrorMsg('');
    setGeneratingExcel(true);
    try {
      // Ensure backend has final user edits
      await reviewTransactions(job.id, transactions, bankLedgerName, cashLedgerName);
      const res = await generateExcel(job.id, bankLedgerName, cashLedgerName);
      setExcelResult(res);
      setSuccessMsg(`Excel file "${res.filename}" generated successfully.`);
      setTimeout(() => setSuccessMsg(''), 5000);
      try {
        await downloadFileBlob(res.download_url, res.filename);
      } catch (dlErr: any) {
        setSuccessMsg(`Excel file "${res.filename}" is ready. Please click Download Excel to save.`);
      }
    } catch (err: any) {
      const msg = err.message || 'Excel generation failed. Please verify transactions and balance math.';
      if (/not found|404|expired/i.test(msg)) {
        setErrorMsg('Conversion session expired. Please re-upload your bank statement PDF to generate files.');
      } else {
        setErrorMsg(msg);
      }
    } finally {
      setGeneratingExcel(false);
    }
  };

  const handleGenerateXml = async () => {
    if (!job) return;
    setErrorMsg('');
    setGeneratingXml(true);
    try {
      setCurrentStep(5);
      // Ensure backend has final edits
      await reviewTransactions(job.id, transactions, bankLedgerName, cashLedgerName);
      
      const res = await generateXml(job.id, bankLedgerName, cashLedgerName);
      setXmlResult(res);
      try {
        const resXls = await generateExcel(job.id, bankLedgerName, cashLedgerName);
        setExcelResult(resXls);
      } catch {
        // Excel can also be generated on demand
      }
      setCurrentStep(6);
      try {
        await downloadFileBlob(res.download_url, res.filename);
      } catch {
        // Fallback to manual download button on step 6
      }
    } catch (err: any) {
      const msg = err.message || 'XML generation failed. Please verify transactions and balance math.';
      if (/not found|404|expired/i.test(msg)) {
        setErrorMsg('Conversion session expired. Please re-upload your bank statement PDF to generate files.');
      } else {
        setErrorMsg(msg);
      }
      setCurrentStep(4);
    } finally {
      setGeneratingXml(false);
    }
  };

  const handleOpenPaymentModal = (suggestedPages?: number) => {
    if (suggestedPages && suggestedPages > 0) {
      setPaymentPages(suggestedPages);
    } else if (job?.remaining_pages && job.remaining_pages > 0) {
      setPaymentPages(job.remaining_pages);
    } else if (job?.pages_skipped && job.pages_skipped > 0) {
      setPaymentPages(job.pages_skipped);
    } else if (job?.total_pdf_pages && job.total_pdf_pages > 0) {
      setPaymentPages(job.total_pdf_pages);
    }
    setPaymentSuccess(false);
    setPaymentError('');
    setPaymentScreenshot(null);
    setPaymentNotes('');
    setShowPaymentModal(true);
  };

  const handleCopyUpi = () => {
    const upi = paymentConfig?.upi_id || '9418250639@ybl';
    navigator.clipboard.writeText(upi);
    setCopiedUpi(true);
    setTimeout(() => setCopiedUpi(false), 2500);
  };

  const handleSubmitPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paymentScreenshot) {
      setPaymentError('Please attach a screenshot of your successful UPI transfer.');
      return;
    }
    if (paymentPages <= 0) {
      setPaymentError('Please enter at least 1 page.');
      return;
    }
    setSubmittingPayment(true);
    setPaymentError('');
    try {
      const amount = paymentPages * (paymentConfig?.price_per_page || 2.0);
      await submitPaymentRequest(paymentPages, amount, paymentScreenshot, paymentNotes);
      setPaymentSuccess(true);
      getUserUsage().then(setUsage).catch(() => {});
    } catch (err: any) {
      setPaymentError(err.message || 'Failed to submit payment request.');
    } finally {
      setSubmittingPayment(false);
    }
  };

  const handleProcessRemaining = async () => {
    if (!job) return;
    setProcessingRemaining(true);
    setErrorMsg('');
    try {
      const updatedJob = await processRemainingPages(job.id);
      setJob(updatedJob);
      setTransactions(updatedJob.transactions || []);
      setSuccessMsg(`Successfully processed remaining pages! Total pages processed: ${updatedJob.pages_processed}.`);
      setTimeout(() => setSuccessMsg(''), 6000);
      getUserUsage().then(setUsage).catch(() => {});
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process remaining pages.');
      if (err.message && /quota|balance|credit/i.test(err.message)) {
        handleOpenPaymentModal(job.remaining_pages || job.pages_skipped);
      }
    } finally {
      setProcessingRemaining(false);
    }
  };

  // Metrics
  const suspenseCount = transactions.filter(
    t => t.ledger_name === 'Suspense' || t.mapping_status === 'Suspense' || !t.ledger_name
  ).length;
  const mappedCount = transactions.length - suspenseCount;
  const errorCount = transactions.filter(t => t.validation_status === 'ERROR').length;
  const warningCount = transactions.filter(t => t.validation_status === 'WARNING').length;
  const duplicateCount = transactions.filter(t => Boolean(t.is_duplicate_suspect)).length;
  const readyForExport = errorCount === 0;

  // Filtered transactions for the review table
  const filteredTransactions = transactions.filter((t) => {
    const matchesSearch =
      txSearch === '' ||
      t.narration.toLowerCase().includes(txSearch.toLowerCase()) ||
      (t.party_name && t.party_name.toLowerCase().includes(txSearch.toLowerCase())) ||
      (t.reference && t.reference.toLowerCase().includes(txSearch.toLowerCase())) ||
      (t.cheque_number && t.cheque_number.toLowerCase().includes(txSearch.toLowerCase())) ||
      (t.instrument_number && t.instrument_number.toLowerCase().includes(txSearch.toLowerCase())) ||
      (t.ledger_name && t.ledger_name.toLowerCase().includes(txSearch.toLowerCase()));

    if (!matchesSearch) return false;

    if (filterTab === 'SUSPENSE') {
      return t.ledger_name === 'Suspense' || t.mapping_status === 'Suspense' || !t.ledger_name;
    }
    if (filterTab === 'MAPPED') {
      return t.ledger_name !== 'Suspense' && t.mapping_status !== 'Suspense' && Boolean(t.ledger_name);
    }
    if (filterTab === 'PAYMENT') {
      return (t.voucher_type || '').toUpperCase() === 'PAYMENT';
    }
    if (filterTab === 'RECEIPT') {
      return (t.voucher_type || '').toUpperCase() === 'RECEIPT';
    }
    if (filterTab === 'CONTRA') {
      return (t.voucher_type || '').toUpperCase() === 'CONTRA';
    }
    if (filterTab === 'DUPLICATE') {
      return Boolean(t.is_duplicate_suspect);
    }
    if (filterTab === 'ERROR') {
      return t.validation_status === 'ERROR';
    }
    if (filterTab === 'WARNING') {
      return t.validation_status === 'WARNING';
    }

    return true;
  });

  return (
    <div className="py-10 bg-slate-50 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Top Studio Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 sm:p-7 rounded-3xl border border-slate-200 shadow-card">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Conversion Studio
              </h1>
              <Badge variant="primary" size="sm">
                Accounting Workspace
              </Badge>
            </div>
            <p className="text-xs text-slate-500">
              Upload bank statement PDF → Verify transactions & running balance math → Export verified Tally XML
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Import My Tally Ledgers Quick Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsLedgerModalOpen(true)}
              icon={<BookOpen className="w-4 h-4 text-blue-600" />}
              className="border-slate-300 hover:border-blue-500 text-slate-700"
            >
              Import My Tally Ledgers
              {userLedgers.length > 0 && (
                <span className="ml-1.5 px-2 py-0.2 bg-blue-100 text-blue-800 text-[10px] font-bold rounded-full">
                  {userLedgers.length} Ledgers{userGroups.length > 0 ? ` & ${userGroups.length} Groups` : ''}
                </span>
              )}
            </Button>

            {/* Daily Quota Counter Badge & Buy Pages */}
            <div className="bg-slate-50 border border-slate-200/80 rounded-2xl px-3.5 py-2 flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <div className="text-xs font-semibold text-slate-700 flex items-center gap-1.5 flex-wrap">
                <span>Free Daily:</span>
                <strong className="text-brand-600 font-extrabold tabular-nums">
                  {usage?.is_unlimited ? 'Unlimited' : `${usage?.pages_remaining_today ?? 50} / ${usage?.daily_limit ?? 50}`}
                </strong>
                {usage?.additional_page_balance && usage.additional_page_balance > 0 ? (
                  <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold">
                    +{usage.additional_page_balance} Extra
                  </span>
                ) : null}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleOpenPaymentModal(50)}
                icon={<CreditCard className="w-3.5 h-3.5 text-amber-600" />}
                className="ml-1 text-[11px] h-7 px-2.5 border-amber-300 bg-amber-50/50 hover:bg-amber-100/70 text-amber-900 font-bold"
              >
                + Buy Pages
              </Button>
            </div>
          </div>
        </div>

        {/* 6-Stage Progress Steps */}
        <Card className="p-4 sm:p-5 shadow-xs overflow-hidden">
          <ProgressSteps
            steps={WORKFLOW_STEPS}
            currentStep={currentStep}
          />
        </Card>

        {/* Error Alert */}
        {errorMsg && (
          <StatusAlert
            type="error"
            title="Conversion Notice"
            message={
              <div>
                <span>{errorMsg}</span>
                {referenceId && (
                  <div className="mt-1 font-mono text-[11px] text-rose-700 font-semibold">
                    Reference ID: <code>{referenceId}</code> (Provide this code to technical support)
                  </div>
                )}
              </div>
            }
            onDismiss={() => setErrorMsg('')}
          />
        )}

        {/* Success Alert */}
        {successMsg && (
          <StatusAlert
            type="success"
            message={successMsg}
            onDismiss={() => setSuccessMsg('')}
          />
        )}

        {/* STAGE 1: UPLOAD ZONE */}
        {currentStep === 1 && (
          <div className="max-w-3xl mx-auto space-y-6">
            
            {/* Tally Master Ledgers Pre-Configuration Card */}
            <Card className="p-6 shadow-xs border-blue-100 bg-blue-50/20 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                        Tally Ledger Name Configuration
                      </h3>
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
                    <p className="text-[11px] text-slate-500">
                      Specify the exact ledger names used in your Tally company. Preserved verbatim in generated XML.
                    </p>
                  </div>
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Bank Ledger Name in Tally
                  </label>
                  <input
                    type="text"
                    list="user-bank-ledgers-step1"
                    value={bankLedgerName}
                    onChange={(e) => setBankLedgerName(e.target.value)}
                    placeholder="e.g. SBI Current Account"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                  <datalist id="user-bank-ledgers-step1">
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
                          onClick={() => setBankLedgerName(b.name)}
                          className={`px-2 py-0.5 text-[10px] rounded-lg border transition-all ${
                            bankLedgerName === b.name
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
                    value={cashLedgerName}
                    onChange={(e) => setCashLedgerName(e.target.value)}
                    placeholder="e.g. Cash or Cash A/C"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    Applied to cash deposits and withdrawals (Default: Cash)
                  </span>
                </div>
              </div>
            </Card>

            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`p-10 sm:p-14 rounded-3xl border-2 border-dashed text-center cursor-pointer transition-all bg-white shadow-card ${
                dragActive
                  ? 'border-brand-500 bg-brand-50/40 scale-[1.005]'
                  : 'border-slate-300 hover:border-brand-400 hover:bg-slate-50/60'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="w-16 h-16 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center mx-auto mb-4 shadow-xs border border-brand-100">
                <UploadCloud className="w-8 h-8" />
              </div>
              <h2 className="text-lg font-bold text-slate-900 mb-1">
                {file ? file.name : 'Upload Bank Statement PDF'}
              </h2>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mb-5 leading-relaxed">
                Drag and drop your digital statement PDF here, or browse files from your device
              </p>
              
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">
                Supports 38+ Banks • Up to 25 MB • Max 200 Pages
              </div>
            </div>

            {/* Statement Password / Unlock PDF (If Encrypted) */}
            <Card className="p-5 shadow-xs">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center flex-shrink-0 border border-amber-100">
                    <Lock className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                      <span>Statement Password (If Encrypted)</span>
                      <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200/60">
                        In-Memory Unlock
                      </span>
                    </div>
                    <div className="text-xs text-slate-500">
                      Leave blank if unencrypted. Typical password: DOB (DDMMYYYY), PAN, or Account Number.
                    </div>
                  </div>
                </div>

                <div className="w-full sm:w-72">
                  <Input
                    type="password"
                    placeholder="Enter statement password..."
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="text-xs"
                  />
                </div>
              </div>
            </Card>

            {/* Optional Manual Bank Selection Override */}
            <Card className="p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center flex-shrink-0">
                  <Building2 className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Bank Detection Override
                  </div>
                  <div className="text-xs text-slate-500">
                    Automatic detection is recommended, or select your bank manually
                  </div>
                </div>
              </div>

              <select
                value={bankOverride}
                onChange={(e) => setBankOverride(e.target.value)}
                className="w-full sm:w-64 px-3 py-2 rounded-xl border border-slate-300 text-xs font-semibold text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
              >
                <option value="">Auto-Detect Bank (Recommended)</option>
                {supportedBanks.map((b) => (
                  <option key={b.parser_key} value={b.bank_name}>
                    {b.bank_name}
                  </option>
                ))}
              </select>
            </Card>

            {file && (
              <div className="text-center pt-2">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={() => startConversion()}
                  iconRight={<ArrowRight className="w-4 h-4" />}
                >
                  Start Bank Statement Conversion
                </Button>
              </div>
            )}
          </div>
        )}

        {/* STAGES 2 & 3: DETECTION & EXTRACTION PROGRESS LOADER OR AMBIGUOUS RESOLUTION */}
        {(currentStep === 2 || currentStep === 3) && job && (job.status === 'AMBIGUOUS_BANK' || job.is_ambiguous) ? (
          <Card className="max-w-xl mx-auto p-8 sm:p-10 shadow-elevated border-amber-200 bg-white text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto border border-amber-200 shadow-xs">
              <HelpCircle className="w-8 h-8" />
            </div>

            <div className="space-y-1.5">
              <Badge variant="warning" size="md">
                Confidence: {job.confidence_score}% (Ambiguous)
              </Badge>
              <h2 className="text-xl font-extrabold text-slate-900 tracking-tight mt-2">
                Bank Confirmation Required
              </h2>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                {job.runner_up_bank
                  ? `We detected signatures of both ${job.bank_name} and ${job.runner_up_bank}. To guarantee strict double-entry accuracy, please select your bank:`
                  : "We could not determine the exact issuing bank format from the statement header with high confidence. Please confirm your bank to proceed:"}
              </p>
            </div>

            <div className="max-w-sm mx-auto space-y-4 text-left">
              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Confirm Issuing Bank
                </label>
                <select
                  value={selectedManualBank}
                  onChange={(e) => setSelectedManualBank(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-300 text-xs font-semibold text-slate-800 bg-white focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                >
                  <option value="">-- Select Your Bank --</option>
                  {supportedBanks.map((b) => (
                    <option key={b.parser_key} value={b.bank_name}>
                      {b.bank_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex gap-2.5 pt-2">
                <Button
                  variant="outline"
                  size="md"
                  className="w-1/3"
                  onClick={() => {
                    setJob(null);
                    setFile(null);
                    setCurrentStep(1);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  className="w-2/3"
                  disabled={!selectedManualBank || resolvingAmbiguous}
                  loading={resolvingAmbiguous}
                  onClick={handleConfirmManualBank}
                  iconRight={<ArrowRight className="w-4 h-4" />}
                >
                  Confirm & Extract
                </Button>
              </div>
            </div>
          </Card>
        ) : (currentStep === 2 || currentStep === 3) && (
          <div className="max-w-md mx-auto bg-white p-8 sm:p-10 rounded-3xl border border-slate-200 shadow-elevated text-center space-y-6">
            <div className="w-14 h-14 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center mx-auto border border-brand-100 shadow-xs">
              <RefreshCw className="w-7 h-7 animate-spin" />
            </div>

            <div className="space-y-1">
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                Processing Bank Statement
              </h2>
              <p className="text-xs text-brand-700 font-semibold animate-pulse">
                {processingStep}
              </p>
            </div>

            <div className="space-y-2.5 text-left bg-slate-50 p-4 rounded-2xl border border-slate-200/80 text-xs text-slate-700">
              <div className="flex items-center gap-2 text-emerald-700 font-semibold">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>PDF digital integrity validated</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700 font-semibold">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Extracting party entities & cheques</span>
              </div>
              <div className="flex items-center gap-2 text-brand-700 font-semibold">
                <div className="w-4 h-4 rounded-full border-2 border-brand-600 border-t-transparent animate-spin flex-shrink-0" />
                <span>Auditing debit/credit balance equations</span>
              </div>
            </div>
          </div>
        )}

        {/* STAGES 4 & 5: REVIEW TRANSACTIONS & LEDGER MAPPING */}
        {(currentStep === 4 || currentStep === 5) && job && (
          <div className="space-y-6">
            
            {/* Quota Exhausted Banner */}
            {job.status === 'QUOTA_EXHAUSTED' && (
              <div className="bg-amber-500/10 border-2 border-amber-500/40 rounded-3xl p-6 sm:p-7 shadow-card space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-800 flex items-center justify-center flex-shrink-0">
                      <AlertTriangle className="w-6 h-6 text-amber-700" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="warning" size="sm">Daily Quota Exhausted</Badge>
                        <span className="text-xs font-bold text-amber-900">0 Free Pages Remaining Today</span>
                      </div>
                      <h3 className="text-lg font-black text-slate-900 mt-1">
                        Statement Contains {job.total_pdf_pages || job.page_count} Pages
                      </h3>
                      <p className="text-xs text-slate-600 mt-0.5 max-w-2xl">
                        Your free daily quota of 50 pages has already been utilized today. To process this {job.total_pdf_pages || job.page_count}-page statement right now, you can purchase extra pages for only ₹2 per page via Google Pay / UPI.
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      variant="primary"
                      size="md"
                      onClick={() => handleOpenPaymentModal(job.remaining_pages || job.total_pdf_pages || 50)}
                      icon={<CreditCard className="w-4 h-4" />}
                      className="bg-amber-600 hover:bg-amber-700 text-white font-bold"
                    >
                      Buy {job.total_pdf_pages || job.page_count} Pages (₹{((job.total_pdf_pages || job.page_count) * 2)})
                    </Button>
                    <a
                      href="https://wa.me/919418250639?text=Hello%2C%20I%20need%20extra%20pages%20for%20my%20bank%20statement%20conversion."
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
                    >
                      <MessageCircle className="w-4 h-4" />
                      WhatsApp Support
                    </a>
                  </div>
                </div>
              </div>
            )}

            {/* Partial Processing Active Banner */}
            {(job.is_partial_conversion || job.status === 'PARTIALLY_COMPLETED' || (job.pages_skipped && job.pages_skipped > 0)) && job.status !== 'QUOTA_EXHAUSTED' && (
              <div className="bg-gradient-to-r from-amber-50 via-orange-50/60 to-amber-50 border-2 border-amber-400/60 rounded-3xl p-6 sm:p-7 shadow-card space-y-4">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-amber-500 text-white flex items-center justify-center flex-shrink-0 shadow-md">
                      <Sparkles className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="warning" size="sm">
                          Partial Conversion Active
                        </Badge>
                        <span className="text-xs font-bold text-slate-800">
                          Pages 1 to {job.pages_processed} Converted
                        </span>
                        <span className="text-xs font-semibold text-amber-800 bg-amber-100/80 px-2 py-0.5 rounded-full">
                          {job.pages_skipped} Pages Skipped (Daily Quota Reached)
                        </span>
                      </div>
                      
                      <h3 className="text-base sm:text-lg font-black text-slate-900 mt-1.5">
                        Pages 1–{job.pages_processed} of {job.total_pdf_pages || ((job.pages_processed || 0) + (job.pages_skipped || 0))} Ready for Export
                      </h3>
                      
                      <p className="text-xs text-slate-600 mt-1 max-w-2xl leading-relaxed">
                        You never lose your daily allowance. The first {job.pages_processed} pages have been fully parsed with running balances balanced. The remaining {job.pages_skipped} pages were skipped. You can export these transactions now, or buy extra pages (₹2/page) to seamlessly process the remaining pages.
                      </p>

                      <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                        <span>Free Quota Used: <strong className="text-slate-900">{job.free_quota_used || 0}</strong></span>
                        <span>•</span>
                        <span>Purchased Quota Used: <strong className="text-slate-900">{job.additional_quota_used || 0}</strong></span>
                        {usage?.additional_page_balance !== undefined && (
                          <>
                            <span>•</span>
                            <span>Purchased Balance: <strong className="text-blue-700 font-bold">{usage.additional_page_balance} pages</strong></span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 lg:flex-col lg:items-end">
                    {usage?.additional_page_balance && usage.additional_page_balance >= (job.remaining_pages || job.pages_skipped || 0) ? (
                      <Button
                        variant="primary"
                        size="md"
                        onClick={handleProcessRemaining}
                        loading={processingRemaining}
                        icon={<Sparkles className="w-4 h-4" />}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold shadow-sm"
                      >
                        Process Remaining {job.remaining_pages || job.pages_skipped} Pages
                      </Button>
                    ) : (
                      <>
                        <Button
                          variant="primary"
                          size="md"
                          onClick={() => handleOpenPaymentModal(job.remaining_pages || job.pages_skipped)}
                          icon={<CreditCard className="w-4 h-4" />}
                          className="bg-amber-600 hover:bg-amber-700 text-white font-bold shadow-sm"
                        >
                          Buy Remaining {job.remaining_pages || job.pages_skipped} Pages (₹{job.suggested_additional_price || ((job.remaining_pages || job.pages_skipped || 0) * 2)})
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleProcessRemaining}
                          loading={processingRemaining}
                          className="border-slate-300 hover:bg-slate-100 text-slate-700 text-xs"
                        >
                          I Already Paid / Process Now
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Bank Signature & Ledger Config Summary Bar */}
            <Card className="p-6 shadow-card space-y-6">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                
                {/* Bank metadata */}
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-700 flex items-center justify-center flex-shrink-0 border border-brand-200/80 shadow-xs">
                    <Building2 className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-bold text-slate-900">
                        {job.bank_name}
                      </h2>
                      {job.confidence_tier === 'HIGH' || job.confidence_score >= 85 ? (
                        <Badge variant="success" size="sm">
                          HIGH CONFIDENCE ({job.confidence_score}%)
                        </Badge>
                      ) : job.confidence_tier === 'MEDIUM' || job.confidence_score >= 60 ? (
                        <Badge variant="primary" size="sm">
                          MEDIUM CONFIDENCE ({job.confidence_score}%)
                        </Badge>
                      ) : (
                        <Badge variant="warning" size="sm">
                          {job.confidence_tier || 'AUDITED'} ({job.confidence_score}%)
                        </Badge>
                      )}
                      {job.parser_name && (
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-semibold border border-slate-200">
                          {job.parser_name}
                        </span>
                      )}
                      {warningCount > 0 ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                          <AlertTriangle className="w-3.5 h-3.5" /> {warningCount} Math Warnings
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                          <CheckCircle2 className="w-3.5 h-3.5" /> 100% Reconciled
                        </span>
                      )}
                    </div>
                    
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                      <span>Pages: <strong className="text-slate-800 font-mono">{job.page_count}</strong></span>
                      <span>•</span>
                      <span>Total Rows: <strong className="text-slate-800 font-mono">{transactions.length}</strong></span>
                      <span>•</span>
                      <span>Total Debit: <strong className="text-rose-600 font-mono font-bold">₹{Number(job.total_debit).toFixed(2)}</strong></span>
                      <span>•</span>
                      <span>Total Credit: <strong className="text-emerald-600 font-mono font-bold">₹{Number(job.total_credit).toFixed(2)}</strong></span>
                      {duplicateCount > 0 && (
                        <>
                          <span>•</span>
                          <span className="text-purple-700 font-semibold">{duplicateCount} duplicate candidate{duplicateCount > 1 ? 's' : ''}</span>
                        </>
                      )}
                      {job.detected_ifsc && (
                        <>
                          <span>•</span>
                          <span>IFSC: <strong className="text-slate-800 font-mono">{job.detected_ifsc}</strong></span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Ledger Mapping Actions & Import */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsLedgerModalOpen(true)}
                    icon={<BookOpen className="w-3.5 h-3.5 text-blue-600" />}
                  >
                    Ledger Masters ({userLedgers.length}{userGroups.length > 0 ? ` + ${userGroups.length} Groups` : ''})
                  </Button>
                </div>
              </div>

              {/* PRD Summary Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-2">
                <div className="p-3.5 rounded-2xl bg-white border border-slate-200 shadow-xs">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block mb-1">
                    Total Transactions
                  </span>
                  <strong className="text-xl font-black text-slate-900 font-mono">
                    {transactions.length}
                  </strong>
                </div>

                <div className="p-3.5 rounded-2xl bg-white border border-emerald-200 bg-emerald-50/30 shadow-xs">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-700 block mb-1">
                    Auto Mapped
                  </span>
                  <strong className="text-xl font-black text-emerald-800 font-mono">
                    {mappedCount}
                  </strong>
                </div>

                <div className={`p-3.5 rounded-2xl border shadow-xs ${
                  suspenseCount > 0 ? 'bg-amber-50/40 border-amber-300' : 'bg-white border-slate-200'
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
                </div>

                <div className={`p-3.5 rounded-2xl border shadow-xs ${
                  warningCount > 0 ? 'bg-amber-50/40 border-amber-300' : 'bg-white border-slate-200'
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
                </div>

                <div className={`p-3.5 rounded-2xl border shadow-xs ${
                  errorCount > 0 ? 'bg-rose-50/50 border-rose-300' : 'bg-white border-slate-200'
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
                </div>

                <div className={`p-3.5 rounded-2xl border shadow-xs ${
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
                </div>
              </div>

              {/* Tally Master Ledger Name Configurations */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-3 text-xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200/80 pb-2.5">
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-brand-600" />
                    <span className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
                      Voucher Ledger Assignment
                    </span>
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
                    icon={<Sparkles className="w-3 h-3 text-brand-600" />}
                    className="text-[11px] h-7 border-slate-300 hover:border-brand-500"
                  >
                    Upload / Manage Master XML
                  </Button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                      Bank Ledger Name in Tally
                    </label>
                    <input
                      type="text"
                      list="user-bank-ledgers-step4"
                      value={bankLedgerName}
                      onChange={(e) => setBankLedgerName(e.target.value)}
                      placeholder="e.g. SBI Current Account"
                      className="w-full px-3 py-1.5 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white focus:ring-2 focus:ring-brand-500/20"
                    />
                    <datalist id="user-bank-ledgers-step4">
                      {userBankLedgers.map((b) => (
                        <option key={b.name} value={b.name}>
                          {b.name} ({b.group || 'Bank Accounts'})
                        </option>
                      ))}
                    </datalist>
                    {userBankLedgers.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1">
                        <span className="text-[10px] text-slate-400 font-medium">Bank Accounts:</span>
                        {userBankLedgers.slice(0, 5).map((b) => (
                          <button
                            key={b.name}
                            type="button"
                            onClick={() => setBankLedgerName(b.name)}
                            className={`px-2 py-0.5 text-[10px] rounded-lg border transition-all ${
                              bankLedgerName === b.name
                                ? 'bg-brand-50 border-brand-500 text-brand-700 font-bold shadow-xs'
                                : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'
                            }`}
                          >
                            🏦 {b.name}
                          </button>
                        ))}
                      </div>
                    )}
                    <span className="text-[10px] text-slate-400 mt-0.5 block">Used for bank line in all vouchers</span>
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                      Cash Ledger Name in Tally
                    </label>
                    <input
                      type="text"
                      value={cashLedgerName}
                      onChange={(e) => setCashLedgerName(e.target.value)}
                      placeholder="e.g. Cash"
                      className="w-full px-3 py-1.5 rounded-xl border border-slate-300 text-xs font-bold text-slate-900 bg-white focus:ring-2 focus:ring-brand-500/20"
                    />
                    <span className="text-[10px] text-slate-400 mt-0.5 block">Used for cash deposits and withdrawals</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* GROUPED WARNINGS & BULK RESOLUTION SUMMARY SECTION */}
            {(errorCount > 0 || warningCount > 0 || suspenseCount > 0 || duplicateCount > 0) && (
              <div className="p-5 rounded-3xl bg-white border border-slate-200 shadow-card space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-black text-slate-900 tracking-tight">
                        Transaction Health & Warning Resolution
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
                          onClick={() => setFilterTab('ERROR')}
                          className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[11px] font-bold transition-all shadow-xs"
                        >
                          Filter Errors ({errorCount})
                        </button>
                      ) : warningCount > 0 ? (
                        <button
                          type="button"
                          onClick={() => setFilterTab('WARNING')}
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
                            onClick={() => setFilterTab('SUSPENSE')}
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
                          onClick={() => setFilterTab('DUPLICATE')}
                          className="px-2.5 py-1 bg-purple-700 hover:bg-purple-800 text-white rounded-lg text-[11px] font-bold transition-all shadow-xs"
                        >
                          Review Duplicates ({duplicateCount})
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Filter Tabs & Search Toolbar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
              
              {/* Filter Tabs */}
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
                    onClick={() => setFilterTab(tab.key)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                      filterTab === tab.key
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

              {/* Search Box */}
              <div className="relative w-full md:w-72">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search narration, party, cheque..."
                  value={txSearch}
                  onChange={(e) => setTxSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600"
                />
              </div>
            </div>

            {/* STICKY BULK ACTIONS BAR (When 1 or more rows selected) */}
            {selectedRowIndices.size > 0 && (
              <div className="sticky top-4 z-30 p-4 rounded-2xl bg-slate-900 text-white shadow-elevated border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-in slide-in-from-top-2">
                <div className="flex items-center gap-3">
                  <div className="px-2.5 py-1 rounded-lg bg-brand-500 text-white font-black text-xs font-mono">
                    {selectedRowIndices.size}
                  </div>
                  <span className="text-xs font-bold">
                    rows selected for bulk action
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2.5">
                  <input
                    type="text"
                    list="user-ledgers-datalist"
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
            <datalist id="user-ledgers-datalist">
              <option value="Suspense" />
              <option value={cashLedgerName || "Cash"} />
              {userLedgers.map((l, i) => (
                <option key={i} value={l.name} />
              ))}
            </datalist>

            {/* Editable Transactions Table */}
            <Card className="shadow-card overflow-hidden">
              <div className="p-4 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between text-xs">
                <div className="font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                  <Edit2 className="w-4 h-4 text-brand-600" />
                  Review & Map Transactions ({filteredTransactions.length} of {transactions.length})
                </div>
                <span className="text-slate-500 text-[11px] hidden sm:inline">
                  Edit ledgers, vouchers, party names, and instrument numbers directly
                </span>
              </div>

              <div className="overflow-x-auto max-h-[620px] divide-y divide-slate-100">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-100/90 text-slate-600 font-bold uppercase tracking-wider text-[10px] sticky top-0 z-20 border-b border-slate-200 backdrop-blur-xs">
                    <tr>
                      <th className="px-3 py-3 text-center w-8">
                        <input
                          type="checkbox"
                          checked={filteredTransactions.length > 0 && filteredTransactions.every(tx => {
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
                    {filteredTransactions.map((tx, fIdx) => {
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
                                  list="user-ledgers-datalist"
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

              {/* FINAL RECONCILIATION SUMMARY CARD */}
              <div className="p-5 sm:p-6 bg-slate-50/80 border-t border-slate-200 space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
                  <div className="p-3 bg-white rounded-xl border border-slate-200/80">
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Tally Bank Ledger</span>
                    <strong className="text-slate-900 font-bold truncate block">{bankLedgerName}</strong>
                  </div>
                  <div className="p-3 bg-white rounded-xl border border-slate-200/80">
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Tally Cash Ledger</span>
                    <strong className="text-slate-900 font-bold truncate block">{cashLedgerName}</strong>
                  </div>
                  <div className="p-3 bg-white rounded-xl border border-slate-200/80">
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Mapped Ledgers</span>
                    <strong className="text-emerald-700 font-bold block">{mappedCount} Mapped</strong>
                  </div>
                  <div className="p-3 bg-white rounded-xl border border-slate-200/80">
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Suspense / Unmapped</span>
                    <strong className={`font-bold block ${suspenseCount > 0 ? 'text-amber-700' : 'text-slate-700'}`}>
                      {suspenseCount} Suspense
                    </strong>
                  </div>
                  <div className="p-3 bg-white rounded-xl border border-slate-200/80">
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Running Balance Audit</span>
                    {errorCount === 0 ? (
                      <span className="font-bold text-emerald-700 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> {warningCount > 0 ? `${warningCount} Warnings` : '100% Balanced'}
                      </span>
                    ) : (
                      <span className="font-bold text-rose-700 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" /> {errorCount} Math Errors
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
                  <span className="text-xs text-slate-500">
                    Double-entry balancing guaranteed. Every debit row has a credit counterpart.
                  </span>

                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      variant="outline"
                      size="lg"
                      onClick={handleDownloadExcel}
                      loading={generatingExcel}
                      disabled={generatingExcel || transactions.length === 0}
                      icon={<FileSpreadsheet className="w-4 h-4 text-emerald-600" />}
                      className="border-emerald-600/50 hover:bg-emerald-50 text-emerald-700 font-bold px-6"
                    >
                      Download Excel
                    </Button>

                    <Button
                      variant="primary"
                      size="lg"
                      onClick={handleGenerateXml}
                      loading={generatingXml}
                      disabled={generatingXml || transactions.length === 0}
                      iconRight={<Download className="w-4 h-4" />}
                      className="bg-brand-600 hover:bg-brand-700 text-white font-bold px-8"
                    >
                      Generate & Download Tally XML
                    </Button>
                  </div>
                </div>
              </div>
            </Card>

            {errorMsg && (
              <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-xs font-semibold flex items-center justify-between shadow-xs mt-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
                <button onClick={() => setErrorMsg('')} className="text-rose-500 hover:text-rose-700 font-bold text-sm px-2">✕</button>
              </div>
            )}

            {successMsg && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center justify-between shadow-xs mt-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>{successMsg}</span>
                </div>
                <button onClick={() => setSuccessMsg('')} className="text-emerald-500 hover:text-emerald-700 font-bold text-sm px-2">✕</button>
              </div>
            )}

          </div>
        )}

        {/* STAGE 6: COMPLETED & DOWNLOAD */}
        {currentStep === 6 && (xmlResult || excelResult) && job && (
          <div className="max-w-xl mx-auto bg-white p-8 sm:p-10 rounded-3xl border border-slate-200 shadow-elevated text-center space-y-6 animate-fadeIn">
            <div className="w-16 h-16 rounded-3xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto border border-emerald-100 shadow-xs">
              <CheckCircle2 className="w-9 h-9" />
            </div>

            <div>
              <Badge variant={job.is_partial_conversion ? "warning" : "success"} size="md" className="mb-2">
                {job.is_partial_conversion ? `Partial Conversion (${job.pages_processed} Pages)` : 'Conversion Complete'}
              </Badge>
              <h2 className="text-2xl font-black text-slate-900 tracking-tight">
                {job.is_partial_conversion ? 'Partial Statement Ready' : 'Conversion Complete'}
              </h2>
              <p className="text-xs text-slate-500 mt-1">
                {job.is_partial_conversion 
                  ? `Processed pages 1–${job.pages_processed} with calibrated closing balance. ${job.pages_skipped} pages skipped.`
                  : 'Both Excel and XML represent the exact same final reviewed conversion dataset'}
              </p>
            </div>

            {job.is_partial_conversion && (
              <div className="bg-amber-50 border border-amber-200 p-4 rounded-2xl text-left text-xs space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-amber-900 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-600" />
                    Remaining {job.remaining_pages || job.pages_skipped} Pages Skipped
                  </span>
                  <span className="text-[11px] font-bold text-amber-700 font-mono">
                    ₹{job.suggested_additional_price || ((job.remaining_pages || job.pages_skipped || 0) * 2)}
                  </span>
                </div>
                <p className="text-slate-600">
                  You can download your XML/Excel for the first {job.pages_processed} pages right now. To process the rest of the statement, recharge your account balance at ₹2/page.
                </p>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleOpenPaymentModal(job.remaining_pages || job.pages_skipped)}
                  icon={<CreditCard className="w-3.5 h-3.5" />}
                  className="w-full bg-amber-600 hover:bg-amber-700 text-white font-bold"
                >
                  Buy Remaining {job.remaining_pages || job.pages_skipped} Pages via UPI
                </Button>
              </div>
            )}

            <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200/80 text-left text-xs space-y-2.5">
              <div className="flex justify-between">
                <span className="text-slate-500">Bank Name:</span>
                <strong className="text-slate-900">{job.bank_name}</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Bank Ledger as Tally:</span>
                <strong className="text-slate-900 font-mono">{bankLedgerName}</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Cash Ledger as Tally:</span>
                <strong className="text-slate-900 font-mono">{cashLedgerName}</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Total Transactions:</span>
                <strong className="text-slate-900 font-mono">{transactions.length}</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Mapped vs Suspense:</span>
                <span className="font-bold text-slate-800">
                  {mappedCount} Mapped / {suspenseCount} Suspense
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Double-Entry & Parity Audit:</span>
                <span className="text-emerald-700 font-bold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 100% Balanced & Verified
                </span>
              </div>
            </div>

            <div className="pt-2 flex flex-col gap-3">
              {/* Review Data */}
              <Button
                variant="outline"
                size="md"
                onClick={() => setCurrentStep(4)}
                icon={<Edit2 className="w-4 h-4 text-blue-600" />}
                className="w-full border-slate-300 hover:border-blue-500 text-slate-700 font-bold py-3"
              >
                Review Data
              </Button>

              {/* Download Excel */}
              <Button
                variant="outline"
                size="lg"
                onClick={() => {
                  if (excelResult) {
                    downloadFileBlob(excelResult.download_url, excelResult.filename);
                  } else {
                    handleDownloadExcel();
                  }
                }}
                loading={generatingExcel}
                icon={<FileSpreadsheet className="w-4 h-4 text-emerald-600" />}
                className="w-full border-emerald-600/60 hover:bg-emerald-50 text-emerald-700 font-bold py-3.5 shadow-xs"
              >
                Download Excel
              </Button>

              {/* Download Tally XML */}
              {xmlResult && (
                <Button
                  variant="success"
                  size="lg"
                  onClick={() => downloadFileBlob(xmlResult.download_url, xmlResult.filename)}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3.5 shadow-md"
                  icon={<Download className="w-4 h-4" />}
                >
                  Download Tally XML
                </Button>
              )}

              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setCurrentStep(1);
                  setFile(null);
                  setTransactions([]);
                  setJob(null);
                  setXmlResult(null);
                  setExcelResult(null);
                }}
              >
                Convert Another Statement
              </Button>
            </div>
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

        {/* Password Decryption Modal */}
        <Modal
          isOpen={showPasswordModal}
          onClose={() => {
            setShowPasswordModal(false);
            setModalPasswordError('');
          }}
          title="Unlock Password-Protected PDF"
          description="This bank statement is encrypted. Enter your password to unlock and convert transactions."
          maxWidth="sm"
        >
          <div className="space-y-4">
            <Input
              type="password"
              label="Statement Password"
              placeholder="Enter password (e.g. PAN, DOB, or A/C No.)..."
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setModalPasswordError('');
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && password) {
                  startConversion(password);
                }
              }}
              autoFocus
            />

            {modalPasswordError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{modalPasswordError}</span>
              </div>
            )}

            <div className="flex gap-2.5 pt-2">
              <Button
                variant="outline"
                size="md"
                className="w-1/2"
                onClick={() => {
                  setShowPasswordModal(false);
                  setModalPasswordError('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="md"
                className="w-1/2 bg-brand-600 hover:bg-brand-700 font-bold"
                onClick={() => startConversion(password)}
                icon={<Lock className="w-4 h-4" />}
              >
                Unlock & Convert
              </Button>
            </div>

            <p className="text-[11px] text-slate-400 text-center leading-normal pt-1">
              🔒 Decrypted in volatile memory. Never stored on disk or logged.
            </p>
          </div>
        </Modal>

        {/* Import My Tally Ledgers Modal */}
        <LedgerImportModal
          isOpen={isLedgerModalOpen}
          onClose={() => {
            setIsLedgerModalOpen(false);
            loadUserLedgers();
          }}
          onLedgersUpdated={() => loadUserLedgers()}
        />

        {/* Purchase Extra Pages via Google Pay / UPI Modal */}
        <Modal
          isOpen={showPaymentModal}
          onClose={() => {
            setShowPaymentModal(false);
            setPaymentSuccess(false);
            setPaymentError('');
          }}
          title="Buy Extra Pages (₹2 / Page)"
          description="Kangra Hub offers manual Google Pay / UPI instant recharge. Your pages never expire."
          maxWidth="lg"
        >
          {paymentSuccess ? (
            <div className="text-center py-6 space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-bold text-slate-900">Payment Submitted for Approval!</h3>
              <p className="text-xs text-slate-600 max-w-md mx-auto leading-relaxed">
                Thank you! Your payment screenshot for <strong className="text-slate-900">{paymentPages} pages (₹{paymentPages * (paymentConfig?.price_per_page || 2.0)})</strong> has been sent to our verification team.
              </p>
              <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-2xl text-xs text-emerald-800 text-left space-y-2">
                <div className="font-bold flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-emerald-600" />
                  Need Instant Verification?
                </div>
                <p>
                  Send a quick ping on WhatsApp to our verification line at <strong className="font-mono text-emerald-950">+91 9418250639</strong> and our team will approve your balance in minutes.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-3 pt-3">
                <a
                  href={`https://wa.me/919418250639?text=${encodeURIComponent(
                    `Hello Kangra Hub Support, I just submitted a payment of ₹${paymentPages * (paymentConfig?.price_per_page || 2.0)} for ${paymentPages} extra pages. Please verify and approve.`
                  )}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition-colors"
                >
                  <MessageCircle className="w-4 h-4" />
                  WhatsApp Direct Verification
                </a>
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => {
                    setShowPaymentModal(false);
                    setPaymentSuccess(false);
                    if (job && (job.is_partial_conversion || job.status === 'PARTIALLY_COMPLETED')) {
                      handleProcessRemaining();
                    }
                  }}
                  className="flex-1"
                >
                  Close & Continue
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmitPayment} className="space-y-6 pt-1">
              {/* Payment Details & QR Code Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center bg-slate-50 p-5 rounded-2xl border border-slate-200/80">
                {/* QR Code Section */}
                <div className="flex flex-col items-center text-center space-y-2.5">
                  <div className="p-3 bg-white rounded-2xl border border-slate-200 shadow-xs">
                    <img
                      src="/buy-a-coffee/googlepay_qr.png"
                      alt="Google Pay / UPI QR Code"
                      className="w-44 h-44 object-contain rounded-xl"
                    />
                  </div>
                  <span className="text-[11px] font-semibold text-slate-500">
                    Scan using Google Pay, PhonePe, Paytm, or any UPI App
                  </span>
                </div>

                {/* UPI ID & Pricing Details */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
                      UPI ID (Copy & Pay)
                    </label>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 font-mono text-xs font-extrabold text-slate-900 bg-white px-3.5 py-2.5 rounded-xl border border-slate-300">
                        {paymentConfig?.upi_id || '9418250639@ybl'}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleCopyUpi}
                        icon={copiedUpi ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                        className="border-slate-300 text-xs whitespace-nowrap"
                      >
                        {copiedUpi ? 'Copied!' : 'Copy'}
                      </Button>
                    </div>
                  </div>

                  <div className="bg-white p-3.5 rounded-xl border border-slate-200 text-xs space-y-2">
                    <div className="flex justify-between text-slate-600">
                      <span>Rate:</span>
                      <strong className="text-slate-900">₹{paymentConfig?.price_per_page || 2.0} per page</strong>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Validity:</span>
                      <strong className="text-emerald-700">Lifetime (Never Expires)</strong>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Priority Verification:</span>
                      <strong className="text-slate-900 font-mono">+91 9418250639</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Calculator & Form */}
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Number of Pages to Buy
                    </label>
                    <Input
                      type="number"
                      min="1"
                      max="10000"
                      value={paymentPages}
                      onChange={(e) => setPaymentPages(Math.max(1, parseInt(e.target.value) || 1))}
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Total Amount to Pay
                    </label>
                    <div className="h-10 px-3.5 rounded-xl bg-amber-50/80 border border-amber-200 flex items-center font-mono font-extrabold text-amber-900 text-base">
                      ₹{(paymentPages * (paymentConfig?.price_per_page || 2.0)).toFixed(2)}
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Upload Payment Screenshot <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="file"
                    accept="image/*"
                    required
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setPaymentScreenshot(e.target.files[0]);
                      }
                    }}
                    className="block w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3.5 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 cursor-pointer border border-slate-300 rounded-xl p-1 bg-white"
                  />
                  {paymentScreenshot && (
                    <span className="text-[11px] text-emerald-600 font-semibold mt-1 block">
                      ✓ Selected: {paymentScreenshot.name} ({(paymentScreenshot.size / 1024).toFixed(1)} KB)
                    </span>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    UPI Reference / UTR / Remarks (Optional)
                  </label>
                  <Input
                    type="text"
                    placeholder="e.g. UTR 412389102482 or your UPI name"
                    value={paymentNotes}
                    onChange={(e) => setPaymentNotes(e.target.value)}
                  />
                </div>
              </div>

              {paymentError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs font-semibold flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                  <span>{paymentError}</span>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="md"
                  onClick={() => setShowPaymentModal(false)}
                  className="w-1/3"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  loading={submittingPayment}
                  disabled={submittingPayment || !paymentScreenshot}
                  className="w-2/3 bg-brand-600 hover:bg-brand-700 font-bold"
                  icon={<Check className="w-4 h-4" />}
                >
                  Submit Payment for Verification
                </Button>
              </div>
            </form>
          )}
        </Modal>

      </div>
    </div>
  );
}
