'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthProvider';
import { GoldTick } from '@/components/ui/GoldTick';
import {
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Download,
  RefreshCw,
  FileText,
  Sparkles,
  Plus,
  Trash2,
  Eye,
  Settings2,
  FileCode,
  Check,
  X,
  ChevronRight,
  Copy,
  ArrowLeft,
  ShieldCheck,
  FileCheck,
  Package,
  BookOpen,
  Search,
  ArrowUpDown,
  Filter,
  CheckCheck,
  HelpCircle,
  FolderOpen,
  RotateCcw,
  Save,
  Tag
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { StatusAlert } from '@/components/ui/StatusAlert';
import { KangraLoader } from '@/components/ui/KangraLoader';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { AlertDialog } from '@/components/ui/AlertDialog';
import {
  InvoiceDocument,
  InvoiceItem,
  LedgerMappingConfig,
  FinalInvoiceSnapshot,
  InvoiceBatchSummary,
  InvoiceXmlGenerationResult,
  ImportedStockItem,
  ImportedLedger,
  getInvoiceConfig,
  uploadInvoices,
  generateInvoiceXml,
  downloadInvoiceXml,
  importStockItems,
  listStockItems,
  createNewStockItem,
  getUserLedgers,
  importLedgers,
  createLedger,
  createLedgerMaster
} from '@/lib/api';
import { CompanyProfileDropdown } from '@/components/CompanyProfileDropdown';
import { StockItemSearchModal } from '@/components/StockItemSearchModal';
import { CreateStockItemMasterModal } from '@/components/CreateStockItemMasterModal';
import { CreateLedgerMasterModal } from '@/components/CreateLedgerMasterModal';
import { convertQuantityAndRate } from '@/lib/unitConverter';
import { mergeSizeIntoItemName } from '@/lib/utils';
import { downloadStockItemsMasterXmlFile, CompanyProfile } from '@/lib/stockItemsMasterXml';
import { normalizeState } from '@/lib/stateNormalizer';

const DEFAULT_SALES_MAPPING: LedgerMappingConfig = {
  purchase_ledger: 'PURCHASE GST',
  sales_ledger: 'SALE GST',
  cgst_ledger: 'CGST',
  sgst_ledger: 'SGST',
  igst_ledger: 'IGST',
  cess_ledger: 'Cess',
  round_off_ledger: 'Round Off.',
};

const SALES_SESSION_KEY = 'kangra_sales_invoice_session_v1';

export default function SalesPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, isStaff, isAdmin, isGold } = useAuth();

  // Mandatory Login-Gate (PRD Section 1: Sales & Purchase require active authentication)
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login?redirect=/sales');
    }
  }, [isLoading, isAuthenticated, router]);

  // Step workflow: 1: Upload (with Pre-Import), 2: Review & Edit, 3: Completed / Download
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [hasRestoredSession, setHasRestoredSession] = useState(false);

  // Upload state
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadSectionRef = useRef<HTMLDivElement>(null);

  // Batch data
  const [invoices, setInvoices] = useState<InvoiceDocument[]>([]);
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [summary, setSummary] = useState<InvoiceBatchSummary | null>(null);
  const [ledgerMapping, setLedgerMapping] = useState<LedgerMappingConfig>(DEFAULT_SALES_MAPPING);
  const [autoCreateItems, setAutoCreateItems] = useState(true);
  const [autoCreateParties, setAutoCreateParties] = useState(true);

  // Stock Items & Ledgers Masters
  const [stockItems, setStockItems] = useState<ImportedStockItem[]>([]);
  const [ledgers, setLedgers] = useState<ImportedLedger[]>([]);
  const [stockItemSearch, setStockItemSearch] = useState('');
  const [ledgerSearch, setLedgerSearch] = useState('');
  const [isStockModalOpen, setIsStockModalOpen] = useState(false);
  const [isLedgerModalOpen, setIsLedgerModalOpen] = useState(false);
  const [isNewItemModalOpen, setIsNewItemModalOpen] = useState(false);
  const [isNewLedgerModalOpen, setIsNewLedgerModalOpen] = useState(false);
  const [newItemData, setNewItemData] = useState({ name: '', hsn: '', uom: 'NOS', group: 'Primary', gst_rate: 18.0 });
  const [newLedgerData, setNewLedgerData] = useState({ name: '', group: 'Sundry Debtors', gstin: '', state: '' });
  const [targetItemIdxForMapping, setTargetItemIdxForMapping] = useState<number | null>(null);

  // Filter & Search inside line items table
  const [itemStatusFilter, setItemStatusFilter] = useState<'ALL' | 'PLEASE_CHECK' | 'VERIFIED' | 'UNMATCHED' | 'NEW_ITEM'>('ALL');
  const [itemQueryFilter, setItemQueryFilter] = useState('');
  const [isStockSearchModalOpen, setIsStockSearchModalOpen] = useState(false);
  const [activeStockSearchIdx, setActiveStockSearchIdx] = useState<number | null>(null);
  const [itemUpdatedToast, setItemUpdatedToast] = useState<string | null>(null);
  const [isDownloadingItemsXml, setIsDownloadingItemsXml] = useState(false);
  const [itemsXmlDownloadedMsg, setItemsXmlDownloadedMsg] = useState<string | null>(null);

  // XML Preview & Download
  const [xmlResult, setXmlResult] = useState<InvoiceXmlGenerationResult | null>(null);
  const [isXmlModalOpen, setIsXmlModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [copiedXml, setCopiedXml] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isReviewConfirmed, setIsReviewConfirmed] = useState(false);

  // 1. Session Storage: Restore saved draft on mount
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(SALES_SESSION_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.invoices && parsed.invoices.length > 0) {
          const processedInvoices = parsed.invoices.map((inv: InvoiceDocument) => ({
            ...inv,
            items: (inv.items || []).map((it) => ({
              ...it,
              item_name: mergeSizeIntoItemName(it.item_name, it.item_size || it.pack_size),
            })),
          }));
          setInvoices(processedInvoices);
          if (parsed.currentStep) setCurrentStep(parsed.currentStep);
          if (parsed.activeIndex !== undefined) setActiveIndex(parsed.activeIndex);
          if (parsed.summary) setSummary(parsed.summary);
          if (parsed.ledgerMapping) setLedgerMapping(parsed.ledgerMapping);
          if (parsed.autoCreateItems !== undefined) setAutoCreateItems(parsed.autoCreateItems);
          if (parsed.autoCreateParties !== undefined) setAutoCreateParties(parsed.autoCreateParties);
          setHasRestoredSession(true);
        }
      }
    } catch (e) {
      console.warn('Could not restore sales session:', e);
    }
  }, []);

  // 2. Session Storage: Save draft whenever invoice data or step changes
  useEffect(() => {
    if (invoices.length > 0) {
      try {
        sessionStorage.setItem(
          SALES_SESSION_KEY,
          JSON.stringify({
            currentStep,
            invoices,
            activeIndex,
            summary,
            ledgerMapping,
            autoCreateItems,
            autoCreateParties,
          })
        );
      } catch (e) {
        console.warn('Could not persist sales session:', e);
      }
    }
  }, [currentStep, invoices, activeIndex, summary, ledgerMapping, autoCreateItems, autoCreateParties]);

  // Load backend configuration & existing masters on mount
  useEffect(() => {
    getInvoiceConfig()
      .then((cfg) => {
        if (cfg?.default_ledger_mapping) {
          setLedgerMapping(cfg.default_ledger_mapping);
        }
      })
      .catch(() => {});

    loadMasters();
  }, []);

  const loadMasters = () => {
    listStockItems('', 5000).then(setStockItems).catch(() => {});
    getUserLedgers('', 5000).then(setLedgers).catch(() => {});
  };

  // Confirmation Dialog State
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: React.ReactNode;
    confirmText?: string;
    cancelText?: string;
    variant?: 'danger' | 'warning' | 'primary' | 'info';
    onConfirm: () => void | Promise<void>;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });

  // Alert Dialog State
  const [alertDialog, setAlertDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: React.ReactNode;
    buttonText?: string;
    variant?: 'error' | 'success' | 'info' | 'warning';
  }>({
    isOpen: false,
    title: '',
    message: '',
  });

  const showAlert = (
    title: string,
    message: React.ReactNode,
    variant: 'error' | 'success' | 'info' | 'warning' = 'info',
    buttonText = 'Okay'
  ) => {
    setAlertDialog({
      isOpen: true,
      title,
      message,
      variant,
      buttonText,
    });
  };

  const executeResetSession = () => {
    try {
      sessionStorage.removeItem(SALES_SESSION_KEY);
    } catch (e) {}
    setInvoices([]);
    setSelectedFiles([]);
    setSummary(null);
    setCurrentStep(1);
    setActiveIndex(0);
    setXmlResult(null);
    setHasRestoredSession(false);
    setErrorMsg(null);
  };

  // Reset current session / start new batch
  const handleResetSession = () => {
    if (invoices.length > 0) {
      setConfirmDialog({
        isOpen: true,
        title: 'Start New Sales Invoice Batch?',
        message: 'Starting a new batch will clear your current extracted sales invoices and unsaved item mappings. Are you sure you want to proceed?',
        confirmText: 'Start New Batch',
        cancelText: 'Keep Current Batch',
        variant: 'warning',
        onConfirm: () => {
          setConfirmDialog((prev) => ({ ...prev, isOpen: false }));
          executeResetSession();
        },
      });
      return;
    }
    executeResetSession();
  };

  // Handle Drag & Drop
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
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const addFiles = (files: File[]) => {
    const validFiles = files.filter((f) => {
      const ext = f.name.toLowerCase().split('.').pop() || '';
      return ['pdf', 'jpg', 'jpeg', 'png', 'webp'].includes(ext);
    });
    if (validFiles.length < files.length) {
      setErrorMsg('Some files were ignored. Supported: PDF, JPG, JPEG, PNG, WebP.');
    } else {
      setErrorMsg(null);
    }
    setSelectedFiles((prev) => [...prev, ...validFiles]);
  };

  const removeFile = (idx: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // Upload and parse sales invoices
  const handleUploadAndProcess = async () => {
    if (selectedFiles.length === 0) {
      setErrorMsg('Please select at least one sales invoice file (JPG or PDF).');
      return;
    }

    setIsProcessing(true);
    setErrorMsg(null);
    setProcessingStatus('Uploading and extracting Sales Invoices with dual OCR layout engine...');

    try {
      const res = await uploadInvoices(selectedFiles, 'SALES');
      if (!res.invoices || res.invoices.length === 0) {
        throw new Error('No readable sales invoice content found in uploaded files.');
      }
      const processedInvoices = (res.invoices || []).map((inv: InvoiceDocument) => ({
        ...inv,
        items: (inv.items || []).map((it) => ({
          ...it,
          item_name: mergeSizeIntoItemName(it.item_name, it.item_size || it.pack_size),
        })),
      }));
      setInvoices(processedInvoices);
      setSummary(res.summary);
      if (res.ledger_mapping) {
        setLedgerMapping(res.ledger_mapping);
      }
      setActiveIndex(0);
      setCurrentStep(2);
      setHasRestoredSession(false);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err: any) {
      console.error('Sales extraction error:', err);
      let msg = err.message || 'Failed to extract sales invoice data. Please check file clarity.';
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        msg = 'Cannot connect to backend server. Please verify backend is running on http://localhost:8000.';
      }
      setErrorMsg(msg);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
      setIsProcessing(false);
      setProcessingStatus('');
    }
  };

  // Current active invoice
  const currentInvoice = invoices[activeIndex] || null;

  const updateCurrentInvoice = (updater: (prev: InvoiceDocument) => InvoiceDocument) => {
    setInvoices((prev) => {
      const updated = [...prev];
      const nextInv = updater({ ...updated[activeIndex] });

      let taxableSum = 0;
      let cgstSum = 0;
      let sgstSum = 0;
      let igstSum = 0;
      let cessSum = 0;

      nextInv.items.forEach((it) => {
        taxableSum += Number(it.taxable_amount || 0);
        cgstSum += Number(it.cgst_amount || 0);
        sgstSum += Number(it.sgst_amount || 0);
        igstSum += Number(it.igst_amount || 0);
        cessSum += Number(it.cess_amount || 0);
      });

      nextInv.taxable_total = Number(taxableSum.toFixed(2));
      nextInv.cgst_total = Number(cgstSum.toFixed(2));
      nextInv.sgst_total = Number(sgstSum.toFixed(2));
      nextInv.igst_total = Number(igstSum.toFixed(2));
      nextInv.cess_total = Number(cessSum.toFixed(2));

      const calcTotal = Number(
        (
          taxableSum +
          cgstSum +
          sgstSum +
          igstSum +
          cessSum +
          Number(nextInv.other_charges || 0) -
          Number(nextInv.discount_total || 0) +
          Number(nextInv.round_off || 0)
        ).toFixed(2)
      );
      nextInv.calculated_total = calcTotal;

      const diff = Math.abs(calcTotal - Number(nextInv.grand_total || 0));
      nextInv.discrepancy = Number(diff.toFixed(2));
      nextInv.is_balanced = diff <= 0.05;

      updated[activeIndex] = nextInv;
      return updated;
    });
  };

  // Auto-balance round off
  const handleAutoBalanceRoundOff = () => {
    if (!currentInvoice) return;
    updateCurrentInvoice((inv) => {
      const subTotal =
        Number(inv.taxable_total || 0) +
        Number(inv.cgst_total || 0) +
        Number(inv.sgst_total || 0) +
        Number(inv.igst_total || 0) +
        Number(inv.cess_total || 0) +
        Number(inv.other_charges || 0) -
        Number(inv.discount_total || 0);
      const ro = Number((Number(inv.grand_total || 0) - subTotal).toFixed(2));
      return {
        ...inv,
        round_off: ro,
      };
    });
  };

  // Apply discrepancy as Discount
  const handleApplyDiscountDifference = () => {
    if (!currentInvoice) return;
    updateCurrentInvoice((inv) => {
      const itemsSum =
        Number(inv.taxable_total || 0) +
        Number(inv.cgst_total || 0) +
        Number(inv.sgst_total || 0) +
        Number(inv.igst_total || 0) +
        Number(inv.cess_total || 0) +
        Number(inv.other_charges || 0) +
        Number(inv.round_off || 0);
      const billTotal = Number(inv.grand_total || 0);
      const diff = Math.abs(billTotal - itemsSum);
      return {
        ...inv,
        discount_total: Number(diff.toFixed(2)),
      };
    });
  };

  // Sync Bill Grand Total to match computed items sum
  const handleSyncBillTotalToItems = () => {
    if (!currentInvoice) return;
    updateCurrentInvoice((inv) => ({
      ...inv,
      grand_total: Number(inv.calculated_total || 0),
    }));
  };

  // Swap Seller and Customer if user reviews GSTIN roles
  const handleSwapSellerCustomer = () => {
    updateCurrentInvoice((inv) => ({
      ...inv,
      supplier: { ...inv.buyer },
      buyer: { ...inv.supplier },
      gstin_role_needs_review: false,
    }));
  };

  // Update line item
  const handleLineItemChange = (itemIdx: number, field: keyof InvoiceItem, value: any) => {
    updateCurrentInvoice((inv) => {
      const updatedItems = [...inv.items];
      const item = { ...updatedItems[itemIdx], [field]: value };

      if (field === 'quantity') {
        const q = Number(value || 0);
        item.quantity = value;
        const taxable = Number(item.taxable_amount || 0);
        // PRD Rule: Rate = Taxable Value ÷ Quantity
        // Support decimal quantities, prevent division by zero, Taxable Value remains unchanged
        if (q > 0) {
          const calcRate = taxable / q;
          item.rate = Number(calcRate.toFixed(4));
        }
        const d = Number(item.discount ?? item.discount_amount ?? 0);
        item.gross_amount = Number((taxable + d).toFixed(2));
      }

      if (
        field === 'rate' ||
        field === 'discount' ||
        field === 'discount_amount'
      ) {
        const q = Number(item.quantity || 0);
        const r = Number(item.rate || 0);
        const d = Number(item.discount ?? item.discount_amount ?? 0);
        const gross = Number((q * r).toFixed(2));
        const taxable = Number(Math.max(0, gross - d).toFixed(2));
        item.gross_amount = gross;
        item.taxable_amount = taxable;

        if (Number(item.cgst_rate) > 0) {
          item.cgst_amount = Number(((item.taxable_amount * Number(item.cgst_rate)) / 100).toFixed(2));
        }
        if (Number(item.sgst_rate) > 0) {
          item.sgst_amount = Number(((item.taxable_amount * Number(item.sgst_rate)) / 100).toFixed(2));
        }
        if (Number(item.igst_rate) > 0) {
          item.igst_amount = Number(((item.taxable_amount * Number(item.igst_rate)) / 100).toFixed(2));
        }
        item.total_amount = Number(
          (
            item.taxable_amount +
            Number(item.cgst_amount || 0) +
            Number(item.sgst_amount || 0) +
            Number(item.igst_amount || 0) +
            Number(item.cess_amount || 0)
          ).toFixed(2)
        );
      }

      if (field === 'taxable_amount') {
        const taxable = Number(value || 0);
        item.taxable_amount = taxable;
        if (Number(item.cgst_rate) > 0) {
          item.cgst_amount = Number(((taxable * Number(item.cgst_rate)) / 100).toFixed(2));
        }
        if (Number(item.sgst_rate) > 0) {
          item.sgst_amount = Number(((taxable * Number(item.sgst_rate)) / 100).toFixed(2));
        }
        if (Number(item.igst_rate) > 0) {
          item.igst_amount = Number(((taxable * Number(item.igst_rate)) / 100).toFixed(2));
        }
        item.total_amount = Number(
          (
            taxable +
            Number(item.cgst_amount || 0) +
            Number(item.sgst_amount || 0) +
            Number(item.igst_amount || 0) +
            Number(item.cess_amount || 0)
          ).toFixed(2)
        );
      }

      if (field === 'gst_rate') {
        const newRate = Number(value || 0);
        item.gst_rate = newRate;
        const isInterstate =
          Number(item.igst_rate) > 0 ||
          Number(inv.igst_total) > 0 ||
          (inv.supplier?.state && inv.buyer?.state && inv.supplier.state !== inv.buyer.state);

        if (isInterstate) {
          item.igst_rate = newRate;
          item.cgst_rate = 0;
          item.sgst_rate = 0;
          item.igst_amount = Number(((Number(item.taxable_amount || 0) * newRate) / 100).toFixed(2));
          item.cgst_amount = 0;
          item.sgst_amount = 0;
        } else {
          const halfRate = Number((newRate / 2).toFixed(2));
          item.cgst_rate = halfRate;
          item.sgst_rate = halfRate;
          item.igst_rate = 0;
          item.cgst_amount = Number(((Number(item.taxable_amount || 0) * halfRate) / 100).toFixed(2));
          item.sgst_amount = Number(((Number(item.taxable_amount || 0) * halfRate) / 100).toFixed(2));
          item.igst_amount = 0;
        }
        item.total_amount = Number(
          (
            Number(item.taxable_amount || 0) +
            Number(item.cgst_amount || 0) +
            Number(item.sgst_amount || 0) +
            Number(item.igst_amount || 0) +
            Number(item.cess_amount || 0)
          ).toFixed(2)
        );
      }

      if (field === 'cgst_rate') {
        const rVal = Number(value || 0);
        item.cgst_rate = rVal;
        item.cgst_amount = Number(((Number(item.taxable_amount || 0) * rVal) / 100).toFixed(2));
        item.gst_rate = Number(item.igst_rate || 0) > 0 ? Number(item.igst_rate) : (rVal + Number(item.sgst_rate || 0));
        item.total_amount = Number(
          (
            Number(item.taxable_amount || 0) +
            Number(item.cgst_amount || 0) +
            Number(item.sgst_amount || 0) +
            Number(item.igst_amount || 0) +
            Number(item.cess_amount || 0)
          ).toFixed(2)
        );
      }
      if (field === 'sgst_rate') {
        const rVal = Number(value || 0);
        item.sgst_rate = rVal;
        item.sgst_amount = Number(((Number(item.taxable_amount || 0) * rVal) / 100).toFixed(2));
        item.gst_rate = Number(item.igst_rate || 0) > 0 ? Number(item.igst_rate) : (Number(item.cgst_rate || 0) + rVal);
        item.total_amount = Number(
          (
            Number(item.taxable_amount || 0) +
            Number(item.cgst_amount || 0) +
            Number(item.sgst_amount || 0) +
            Number(item.igst_amount || 0) +
            Number(item.cess_amount || 0)
          ).toFixed(2)
        );
      }
      if (field === 'igst_rate') {
        const rVal = Number(value || 0);
        item.igst_rate = rVal;
        item.igst_amount = Number(((Number(item.taxable_amount || 0) * rVal) / 100).toFixed(2));
        item.gst_rate = rVal;
        item.total_amount = Number(
          (
            Number(item.taxable_amount || 0) +
            Number(item.cgst_amount || 0) +
            Number(item.sgst_amount || 0) +
            Number(item.igst_amount || 0) +
            Number(item.cess_amount || 0)
          ).toFixed(2)
        );
      }

      if (field === 'item_size') {
        item.pack_size = value;
      }
      if (field === 'pack_size') {
        item.item_size = value;
      }

      updatedItems[itemIdx] = item;

      // Recalculate invoice-level totals
      const calcTaxable = Number(updatedItems.reduce((acc, it) => acc + Number(it.taxable_amount || 0), 0).toFixed(2));
      const calcCgst = Number(updatedItems.reduce((acc, it) => acc + Number(it.cgst_amount || 0), 0).toFixed(2));
      const calcSgst = Number(updatedItems.reduce((acc, it) => acc + Number(it.sgst_amount || 0), 0).toFixed(2));
      const calcIgst = Number(updatedItems.reduce((acc, it) => acc + Number(it.igst_amount || 0), 0).toFixed(2));
      const roundOff = Number(inv.round_off || inv.totals?.round_off || 0);
      const calcGrand = Number((calcTaxable + calcCgst + calcSgst + calcIgst + roundOff).toFixed(2));

      return {
        ...inv,
        items: updatedItems,
        taxable_total: calcTaxable,
        cgst_total: calcCgst,
        sgst_total: calcSgst,
        igst_total: calcIgst,
        grand_total: calcGrand,
        totals: {
          ...inv.totals,
          taxable_total: calcTaxable,
          cgst_total: calcCgst,
          sgst_total: calcSgst,
          igst_total: calcIgst,
          grand_total: calcGrand,
        },
      };
    });
  };

  // PRD §1-11: Dual Quantity Column Option Selection
  const handleSelectDualQtyOption = (itemIdx: number, option: 'A' | 'B') => {
    updateCurrentInvoice((inv) => {
      const updatedItems = [...inv.items];
      const it = { ...updatedItems[itemIdx] };
      if (!it || !it.has_dual_qty) return inv;

      // MANDATORY RULE 4: Taxable Value MUST Remain Unchanged
      const originalTaxable = Number(it.taxable_amount || 0);

      if (option === 'A') {
        const chosenQty = Number(it.quantity_option_a || it.quantity);
        const chosenUom = it.uom_option_a || it.uom || 'NOS';
        const recalculatedRate = chosenQty > 0 ? originalTaxable / chosenQty : Number(it.rate);

        it.selected_qty_option = 'A';
        it.quantity = chosenQty;
        it.uom = chosenUom;
        it.invoice_uom = chosenUom;
        it.tally_uom = it.tally_uom && it.tally_uom === it.uom_option_b ? chosenUom : (it.tally_uom || chosenUom);
        it.rate = it.rate_option_a != null ? Number(it.rate_option_a) : Math.round(recalculatedRate * 100) / 100;
        it.alternate_quantity = it.quantity_option_b;
        it.alternate_uom = it.uom_option_b;
      } else {
        const chosenQty = Number(it.quantity_option_b || it.secondary_quantity || it.quantity);
        const chosenUom = it.uom_option_b || it.secondary_unit || 'PCS';
        const recalculatedRate = chosenQty > 0 ? originalTaxable / chosenQty : Number(it.rate);

        it.selected_qty_option = 'B';
        it.quantity = chosenQty;
        it.uom = chosenUom;
        it.invoice_uom = chosenUom;
        it.tally_uom = it.tally_uom && it.tally_uom === it.uom_option_a ? chosenUom : (it.tally_uom || chosenUom);
        it.rate = it.rate_option_b != null ? Number(it.rate_option_b) : Math.round(recalculatedRate * 100) / 100;
        it.alternate_quantity = it.quantity_option_a;
        it.alternate_uom = it.uom_option_a;
      }

      // Preserve exact taxable amount and update GST and line total
      it.taxable_amount = originalTaxable;
      it.gross_amount = originalTaxable;

      const cgstR = Number(it.cgst_rate || 0);
      const sgstR = Number(it.sgst_rate || 0);
      const igstR = Number(it.igst_rate || 0);
      const cessR = Number(it.cess_rate || 0);

      it.cgst_amount = Number(((originalTaxable * cgstR) / 100).toFixed(2));
      it.sgst_amount = Number(((originalTaxable * sgstR) / 100).toFixed(2));
      it.igst_amount = Number(((originalTaxable * igstR) / 100).toFixed(2));
      it.cess_amount = Number(((originalTaxable * cessR) / 100).toFixed(2));
      it.total_amount = Number(
        (
          originalTaxable +
          it.cgst_amount +
          it.sgst_amount +
          it.igst_amount +
          it.cess_amount
        ).toFixed(2)
      );

      updatedItems[itemIdx] = it;
      return { ...inv, items: updatedItems };
    });
  };

  // PRD V2 Section 5.3 & 13: Pack-Size Conversion Toggle per line (Option A vs Option B)
  const handleTogglePackConversion = (itemIdx: number) => {
    updateCurrentInvoice((inv) => {
      const updatedItems = [...inv.items];
      const it = { ...updatedItems[itemIdx] };
      const mult = Number(it.pack_size_multiplier || it.pack_multiplier || 0);
      if (mult <= 1) return inv;

      const originalTaxable = Number(it.taxable_amount || 0);

      if (!it.is_converted_to_pieces) {
        // Option A (bulk) -> Option B (pieces)
        const baseQty = Number(it.invoice_qty || it.quantity || 1);
        const piecesQty = Number((baseQty * mult).toFixed(3));
        const recalculatedRate = piecesQty > 0 ? originalTaxable / piecesQty : Number(it.rate);

        it.quantity = piecesQty;
        it.rate = Math.round(recalculatedRate * 10000) / 10000;
        it.uom = 'Pcs';
        it.tally_uom = 'Pcs';
        it.is_converted_to_pieces = true;
      } else {
        // Option B (pieces) -> Option A (bulk)
        const bulkQty = Number(it.invoice_qty || (Number(it.quantity || mult) / mult).toFixed(3));
        const recalculatedRate = bulkQty > 0 ? originalTaxable / bulkQty : Number(it.rate);

        it.quantity = bulkQty;
        it.rate = Math.round(recalculatedRate * 100) / 100;
        it.uom = it.invoice_uom || 'CASE';
        it.tally_uom = it.invoice_uom || 'CASE';
        it.is_converted_to_pieces = false;
      }

      it.taxable_amount = originalTaxable;
      it.gross_amount = originalTaxable;
      updatedItems[itemIdx] = it;
      return { ...inv, items: updatedItems };
    });
  };

  // PRD Addendum 1 Section 2.7: Live "Amounts include GST" Toggle Handler
  const handleToggleTaxInclusiveMode = () => {
    updateCurrentInvoice((inv) => {
      const isCurrentlyInclusive = inv.tax_mode === 'inclusive';
      const newMode = isCurrentlyInclusive ? 'exclusive' : 'inclusive';
      const isInterstate = Number(inv.igst_total || 0) > 0 || (
        Boolean(inv.supplier.state && inv.buyer.state && inv.supplier.state.toLowerCase() !== inv.buyer.state.toLowerCase())
      );

      const updatedItems = inv.items.map((it) => {
        const item = { ...it };
        const gstRate = Number(item.gst_rate) > 0
          ? Number(item.gst_rate)
          : Number(item.igst_rate || 0) > 0
          ? Number(item.igst_rate)
          : Number(item.cgst_rate || 0) + Number(item.sgst_rate || 0);

        if (newMode === 'inclusive') {
          const lineAmount = Number(item.total_amount || item.taxable_amount || 0);
          if (gstRate > 0) {
            const factor = 1 + gstRate / 100;
            const taxable = Number((lineAmount / factor).toFixed(2));
            const taxAmt = Number((lineAmount - taxable).toFixed(2));
            item.taxable_amount = taxable;
            item.gross_amount = taxable;
            item.total_amount = lineAmount;
            if (Number(item.quantity) > 0) {
              item.rate = Number((taxable / Number(item.quantity)).toFixed(4));
            }
            if (isInterstate) {
              item.igst_amount = taxAmt;
              item.cgst_amount = 0;
              item.sgst_amount = 0;
            } else {
              const halfTax = Number((taxAmt / 2).toFixed(2));
              item.cgst_amount = halfTax;
              item.sgst_amount = Number((taxAmt - halfTax).toFixed(2));
              item.igst_amount = 0;
            }
          }
          item.is_tax_inclusive = true;
          item.tax_mode = 'inclusive';
        } else {
          const taxable = Number(item.total_amount || item.taxable_amount || 0);
          item.taxable_amount = taxable;
          item.gross_amount = taxable;
          if (Number(item.quantity) > 0) {
            item.rate = Number((taxable / Number(item.quantity)).toFixed(4));
          }
          if (gstRate > 0) {
            const taxAmt = Number(((taxable * gstRate) / 100).toFixed(2));
            if (isInterstate) {
              item.igst_amount = taxAmt;
              item.cgst_amount = 0;
              item.sgst_amount = 0;
            } else {
              const halfTax = Number((taxAmt / 2).toFixed(2));
              item.cgst_amount = halfTax;
              item.sgst_amount = Number((taxAmt - halfTax).toFixed(2));
              item.igst_amount = 0;
            }
            item.total_amount = Number((taxable + taxAmt).toFixed(2));
          } else {
            item.total_amount = taxable;
          }
          item.is_tax_inclusive = false;
          item.tax_mode = 'exclusive';
        }
        return item;
      });

      const nextTaxableSum = updatedItems.reduce((acc, it) => acc + Number(it.taxable_amount || 0), 0);
      const nextCgstSum = updatedItems.reduce((acc, it) => acc + Number(it.cgst_amount || 0), 0);
      const nextSgstSum = updatedItems.reduce((acc, it) => acc + Number(it.sgst_amount || 0), 0);
      const nextIgstSum = updatedItems.reduce((acc, it) => acc + Number(it.igst_amount || 0), 0);
      const nextGrand = Number((nextTaxableSum + nextCgstSum + nextSgstSum + nextIgstSum + Number(inv.other_charges || 0) + Number(inv.round_off || 0)).toFixed(2));

      return {
        ...inv,
        tax_mode: newMode,
        is_tax_inclusive: newMode === 'inclusive',
        tax_mode_evidence: `User manually set tax mode to ${newMode}`,
        items: updatedItems,
        taxable_total: Number(nextTaxableSum.toFixed(2)),
        cgst_total: Number(nextCgstSum.toFixed(2)),
        sgst_total: Number(nextSgstSum.toFixed(2)),
        igst_total: Number(nextIgstSum.toFixed(2)),
        grand_total: nextGrand,
      };
    });
  };

  const handleAddLineItem = () => {
    updateCurrentInvoice((inv) => ({
      ...inv,
      items: [
        ...inv.items,
        {
          item_name: `New Sales Item ${inv.items.length + 1}`,
          description: `New Sales Item ${inv.items.length + 1}`,
          hsn_sac: '',
          quantity: 1,
          uom: 'NOS',
          rate: 0,
          discount: 0,
          taxable_amount: 0,
          cgst_rate: 0,
          cgst_amount: 0,
          sgst_rate: 0,
          sgst_amount: 0,
          igst_rate: 0,
          igst_amount: 0,
          cess_rate: 0,
          cess_amount: 0,
          total_amount: 0,
          confidence: 1,
          requires_item_creation: true,
          mapping_status: 'NEW_ITEM',
          mapping_confidence: 'UNMATCHED',
        },
      ],
    }));
  };

  const handleRemoveLineItem = (idx: number) => {
    updateCurrentInvoice((inv) => ({
      ...inv,
      items: inv.items.filter((_, i) => i !== idx),
    }));
  };

  // Accept a suggested item match
  const handleAcceptItemSuggestion = (itemIdx: number, matchedName: string) => {
    updateCurrentInvoice((inv) => {
      const updatedItems = [...inv.items];
      const cur = updatedItems[itemIdx];
      const foundStock = stockItems.find((s) => s.name === matchedName);
      const targetUom = foundStock?.base_units || cur.tally_uom || cur.uom || 'NOS';
      updatedItems[itemIdx] = {
        ...cur,
        matched_stock_item: matchedName,
        tally_uom: targetUom,
        uom: targetUom,
        invoice_uom: cur.invoice_uom || cur.uom || 'NOS',
        mapping_status: 'AUTO_MAPPED',
        mapping_confidence: 'HIGH',
        requires_item_creation: false,
      };
      return { ...inv, items: updatedItems };
    });
  };

  // Accept a suggested customer ledger match
  const handleAcceptLedgerSuggestion = (ledgerName: string) => {
    updateCurrentInvoice((inv) => ({
      ...inv,
      buyer: {
        ...inv.buyer,
        matched_ledger_name: ledgerName,
        mapping_status: 'AUTO_MAPPED',
        mapping_confidence: 'HIGH',
        requires_ledger_creation: false,
      },
    }));
  };

  // Verify / Approve an individual item mapping
  const handleVerifyItem = (itemIdx: number) => {
    updateCurrentInvoice((inv) => {
      const updatedItems = [...inv.items];
      if (updatedItems[itemIdx]) {
        const cur = updatedItems[itemIdx];
        const isVerified = cur.mapping_status === 'VERIFIED';
        updatedItems[itemIdx] = {
          ...cur,
          mapping_status: isVerified ? 'PLEASE_CHECK' : 'VERIFIED',
          matched_stock_item: cur.matched_stock_item || cur.item_name,
          confidence: isVerified ? 0.7 : 1.0,
        };
      }
      return { ...inv, items: updatedItems };
    });
  };

  // Verify all pending items in current invoice
  const handleVerifyAllItems = () => {
    updateCurrentInvoice((inv) => {
      const updatedItems = inv.items.map((it) => ({
        ...it,
        mapping_status: 'VERIFIED' as const,
        matched_stock_item: it.matched_stock_item || it.item_name,
        confidence: 1.0,
      }));
      return { ...inv, items: updatedItems };
    });
  };

  // Open Stock Item Search Modal for specific line item
  const handleOpenStockSearch = (idx: number) => {
    setActiveStockSearchIdx(idx);
    setIsStockSearchModalOpen(true);
  };

  // Callback when user picks a stock item from the uploaded stock items search modal:
  // Automatically changes item_name, matched_stock_item, UOM, HSN, preserves invoice quantity and marks verified
  const handleSelectStockItemFromModal = (selectedItem: ImportedStockItem, itemIdx: number) => {
    updateCurrentInvoice((inv) => {
      const updatedItems = [...inv.items];
      if (updatedItems[itemIdx]) {
        const cur = updatedItems[itemIdx];
        const targetUom = selectedItem.base_units || cur.tally_uom || cur.uom || 'NOS';
        const conv = convertQuantityAndRate(
          Number(cur.quantity || 1),
          cur.invoice_uom || cur.uom || 'NOS',
          targetUom,
          Number(cur.rate || 0)
        );

        updatedItems[itemIdx] = {
          ...cur,
          item_name: selectedItem.name,
          matched_stock_item: selectedItem.name,
          quantity: conv.finalQuantity, // Invoice quantity is strictly preserved
          rate: conv.finalRate,
          uom: targetUom,
          tally_uom: targetUom,
          invoice_uom: cur.invoice_uom || cur.uom || 'NOS',
          hsn_sac: selectedItem.hsn_code || cur.hsn_sac,
          mapping_status: 'VERIFIED',
          confidence: 1.0,
          confidence_level: 'HIGH',
          requires_item_creation: false,
        };
      }
      return { ...inv, items: updatedItems };
    });
    setIsStockSearchModalOpen(false);
    setItemUpdatedToast(`✓ Line #${itemIdx + 1} updated to "${selectedItem.name}" (UOM: ${selectedItem.base_units || 'NOS'})`);
    setTimeout(() => setItemUpdatedToast(null), 5000);
  };

  // Quick Select / Switch Company Profile (Seller / Our Company in Sales)
  const handleSelectSellerCompany = (profile: CompanyProfile) => {
    updateCurrentInvoice((inv) => ({
      ...inv,
      supplier: {
        ...inv.supplier,
        name: profile.name,
        gstin: profile.gstin,
        state: profile.state,
        address: profile.address,
      },
      own_company_name: profile.name,
      own_gstin: profile.gstin,
      own_state: profile.state,
    }));
  };

  // Download Stock Items Master XML (strictly conforming to stock items list sample.xml)
  const handleDownloadStockItemsMasterXml = async (onlyNew = false) => {
    if (!currentInvoice || !currentInvoice.items.length) {
      showAlert('No Items to Export', 'There are no invoice items available to export in this document.', 'warning');
      return;
    }
    setIsDownloadingItemsXml(true);
    try {
      const itemsToExport = onlyNew
        ? currentInvoice.items.filter((it) => it.requires_item_creation || it.mapping_status === 'NEW_ITEM' || !it.matched_stock_item)
        : currentInvoice.items;
      const targetItems = itemsToExport.length > 0 ? itemsToExport : currentInvoice.items;

      const res = await downloadStockItemsMasterXmlFile(
        currentInvoice.supplier.name || 'Kartar Singh & Sons - (from 1-Apr-25)',
        targetItems,
        currentInvoice.invoice_number || 'SALES_INVOICE'
      );
      setItemsXmlDownloadedMsg(
        `✓ Downloaded "${res.filename}" (${res.itemCount} items). Import in Tally: Alt + O -> Import -> Masters.`
      );
      setTimeout(() => setItemsXmlDownloadedMsg(null), 10000);
    } catch (err: any) {
      showAlert('Stock Items XML Notice', err.message || 'Failed to generate Stock Items Master XML.', 'error');
    } finally {
      setIsDownloadingItemsXml(false);
    }
  };

  // Toggle Tax Mode (Exclusive vs Inclusive)
  const handleToggleTaxMode = (mode: 'exclusive' | 'inclusive') => {
    if (!currentInvoice) return;
    updateCurrentInvoice((inv) => {
      const updatedItems = inv.items.map((it) => {
        const gstRate = Number(it.igst_rate || 0) > 0 ? Number(it.igst_rate) : (Number(it.cgst_rate || 0) + Number(it.sgst_rate || 0));
        if (mode === 'inclusive') {
          const baseRate = it.rate;
          const exclRate = gstRate > 0 ? Number((baseRate * 100 / (100 + gstRate)).toFixed(2)) : baseRate;
          const exclTaxable = Number((it.quantity * exclRate).toFixed(2));
          const taxAmount = Number((exclTaxable * (gstRate / 100)).toFixed(2));
          const total = Number((exclTaxable + taxAmount).toFixed(2));
          return {
            ...it,
            tax_mode: 'inclusive' as const,
            is_tax_inclusive: true,
            printed_rate: it.printed_rate || baseRate,
            rate: exclRate,
            taxable_amount: exclTaxable,
            total_amount: total,
            cgst_amount: Number(it.cgst_rate) > 0 ? Number((taxAmount / 2).toFixed(2)) : 0,
            sgst_amount: Number(it.sgst_rate) > 0 ? Number((taxAmount / 2).toFixed(2)) : 0,
            igst_amount: Number(it.igst_rate) > 0 ? taxAmount : 0,
          };
        } else {
          const baseRate = it.printed_rate || it.rate;
          const taxable = Number((it.quantity * baseRate).toFixed(2));
          const taxAmount = Number((taxable * (gstRate / 100)).toFixed(2));
          const total = Number((taxable + taxAmount).toFixed(2));
          return {
            ...it,
            tax_mode: 'exclusive' as const,
            is_tax_inclusive: false,
            rate: baseRate,
            taxable_amount: taxable,
            total_amount: total,
            cgst_amount: Number(it.cgst_rate) > 0 ? Number((taxAmount / 2).toFixed(2)) : 0,
            sgst_amount: Number(it.sgst_rate) > 0 ? Number((taxAmount / 2).toFixed(2)) : 0,
            igst_amount: Number(it.igst_rate) > 0 ? taxAmount : 0,
          };
        }
      });

      const newTaxable = updatedItems.reduce((acc, i) => acc + Number(i.taxable_amount || 0), 0);
      const newCgst = updatedItems.reduce((acc, i) => acc + Number(i.cgst_amount || 0), 0);
      const newSgst = updatedItems.reduce((acc, i) => acc + Number(i.sgst_amount || 0), 0);
      const newIgst = updatedItems.reduce((acc, i) => acc + Number(i.igst_amount || 0), 0);
      const newGrand = updatedItems.reduce((acc, i) => acc + Number(i.total_amount || 0), 0);

      return {
        ...inv,
        tax_mode: mode,
        items: updatedItems,
        taxable_total: Number(newTaxable.toFixed(2)),
        cgst_total: Number(newCgst.toFixed(2)),
        sgst_total: Number(newSgst.toFixed(2)),
        igst_total: Number(newIgst.toFixed(2)),
        grand_total: Number(newGrand.toFixed(2)),
        calculated_total: Number(newGrand.toFixed(2)),
      };
    });
  };

  // Toggle Pack Quantity Option (PRD Addendum 2: Pieces vs Bulk)
  const handleTogglePackQuantityOption = (mode: 'pieces' | 'bulk') => {
    if (!currentInvoice) return;
    updateCurrentInvoice((inv) => {
      const updatedItems = inv.items.map((it) => {
        if (!it.has_dual_qty && !it.can_convert_to_pieces) return it;
        if (mode === 'pieces' && it.quantity_option_b !== undefined) {
          return {
            ...it,
            selected_qty_option: 'B' as const,
            quantity: it.quantity_option_b,
            uom: it.uom_option_b || it.uom,
            rate: it.rate_option_b !== undefined ? it.rate_option_b : it.rate,
            is_converted_to_pieces: true,
            alternate_quantity: it.quantity_option_a,
            alternate_uom: it.uom_option_a,
          };
        } else if (mode === 'bulk' && it.quantity_option_a !== undefined) {
          return {
            ...it,
            selected_qty_option: 'A' as const,
            quantity: it.quantity_option_a,
            uom: it.uom_option_a || it.uom,
            rate: it.rate_option_a !== undefined ? it.rate_option_a : it.rate,
            is_converted_to_pieces: false,
          };
        }
        return it;
      });
      return {
        ...inv,
        pack_quantity_option: mode,
        items: updatedItems,
      };
    });
  };

  // Validate mappings and item count before generating XML
  const validateBeforeXmlGeneration = (): boolean => {
    if (!currentInvoice) return false;

    // 1. Item Count Validation: Never silently drop items
    if (currentInvoice.items_detected_count && currentInvoice.items_detected_count > currentInvoice.items.length) {
      setErrorMsg(
        `Item Count Mismatch: Invoice contains ${currentInvoice.items_detected_count} item rows but only ${currentInvoice.items.length} are present in the table. Please review before generating XML.`
      );
      return false;
    }

    // 2. Unresolved mappings validation
    const unresolvedItems = currentInvoice.items.filter(
      (it) => !it.matched_stock_item && !it.requires_item_creation
    );
    if (unresolvedItems.length > 0) {
      setErrorMsg(`${unresolvedItems.length} Sales Items require review or mapping before XML generation.`);
      return false;
    }

    // 3. PRD Error Confirmation Gate (Section 5.10)
    const hasUnconfirmedErrors = (currentInvoice.errors && currentInvoice.errors.length > 0) ||
      (currentInvoice.validation_violations && currentInvoice.validation_violations.some(v => v.severity === 'ERROR'));
    if (hasUnconfirmedErrors && !isReviewConfirmed) {
      setErrorMsg("Invoice contains validation errors. Please review the highlighted issues and tick 'I have checked these values' to confirm XML generation.");
      return false;
    }

    return true;
  };

  // Preview XML
  const handlePreviewXml = async () => {
    if (!validateBeforeXmlGeneration()) return;
    setIsProcessing(true);
    try {
      const snapshot: FinalInvoiceSnapshot = {
        invoices,
        ledger_mapping: ledgerMapping,
        auto_create_items: autoCreateItems,
        auto_create_parties: autoCreateParties,
      };
      const res = await generateInvoiceXml(snapshot);
      setXmlResult(res);
      setIsXmlModalOpen(true);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate Sales Tally XML preview.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Download XML
  const handleDownloadXml = async () => {
    if (!validateBeforeXmlGeneration()) return;
    setIsDownloading(true);
    try {
      const snapshot: FinalInvoiceSnapshot = {
        invoices,
        ledger_mapping: ledgerMapping,
        auto_create_items: autoCreateItems,
        auto_create_parties: autoCreateParties,
      };
      const { blob, filename } = await downloadInvoiceXml(snapshot);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'Sales_Invoices_Tally.xml';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setCurrentStep(3);
    } catch (err: any) {
      const msg = err.message || 'Failed to download Sales Tally XML.';
      setErrorMsg(msg);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
      setIsDownloading(false);
    }
  };

  const copyToClipboard = () => {
    if (!xmlResult?.xml_content) return;
    navigator.clipboard.writeText(xmlResult.xml_content);
    setCopiedXml(true);
    setTimeout(() => setCopiedXml(false), 2000);
  };

  // Stock Item File Import
  const handleStockFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    try {
      const res = await importStockItems(file);
      showAlert(
        'Stock Items Imported',
        `Successfully imported ${res.total_imported} stock items from ${res.detected_format} file!`,
        'success'
      );
      loadMasters();
      setIsStockModalOpen(false);
    } catch (err: any) {
      showAlert('Stock Import Failed', `Stock item import failed: ${err.message}`, 'error');
    }
  };

  // Ledger File Import
  const handleLedgerFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    try {
      const res = await importLedgers(file);
      showAlert(
        'Customer Ledgers Imported',
        `Successfully imported ${res.total_imported} ledgers from ${res.detected_format} file!`,
        'success'
      );
      loadMasters();
      setIsLedgerModalOpen(false);
    } catch (err: any) {
      showAlert('Ledger Import Failed', `Ledger import failed: ${err.message}`, 'error');
    }
  };

  // PRD Addendum 5: All new items needing master creation
  const allNewItems = useMemo(() => {
    if (!currentInvoice) return [];
    return currentInvoice.items
      .map((it, idx) => ({ ...it, originalIndex: idx }))
      .filter((it) => it.requires_item_creation || it.mapping_status === 'NEW_ITEM' || !it.matched_stock_item);
  }, [currentInvoice]);

  const currentNewItemPos = useMemo(() => {
    if (targetItemIdxForMapping === null) return 0;
    const pos = allNewItems.findIndex((it) => it.originalIndex === targetItemIdxForMapping);
    return pos >= 0 ? pos : 0;
  }, [allNewItems, targetItemIdxForMapping]);

  // PRD Addendum 5: Live Slab Summary Verification Box
  const slabVerification = useMemo(() => {
    if (!currentInvoice || !currentInvoice.items.length) return null;
    const slabs: Record<string, { rate: number; label: string; taxable: number; tax: number; count: number }> = {};
    let totalTaxable = 0;
    let totalTax = 0;

    for (const it of currentInvoice.items) {
      const rate = Number(it.igst_rate && it.igst_rate > 0 ? it.igst_rate : (Number(it.cgst_rate || 0) + Number(it.sgst_rate || 0)));
      const key = `${rate.toFixed(1)}%`;
      if (!slabs[key]) {
        slabs[key] = { rate, label: key, taxable: 0, tax: 0, count: 0 };
      }
      const taxable = Number(it.taxable_amount || 0);
      const tax = Number(it.cgst_amount || 0) + Number(it.sgst_amount || 0) + Number(it.igst_amount || 0);
      slabs[key].taxable += taxable;
      slabs[key].tax += tax;
      slabs[key].count += 1;
      totalTaxable += taxable;
      totalTax += tax;
    }

    const printedTaxable = Number(currentInvoice.taxable_total || 0);
    const printedTax = Number(currentInvoice.cgst_total || 0) + Number(currentInvoice.sgst_total || 0) + Number(currentInvoice.igst_total || 0);
    const taxableDiff = Math.abs(totalTaxable - printedTaxable);
    const taxDiff = Math.abs(totalTax - printedTax);
    const isBalanced = (printedTaxable === 0 || taxableDiff <= 1.05) && (printedTax === 0 || taxDiff <= 1.05);

    return {
      slabs: Object.values(slabs).sort((a, b) => a.rate - b.rate),
      totalTaxable,
      totalTax,
      printedTaxable,
      printedTax,
      taxableDiff,
      taxDiff,
      isBalanced,
    };
  }, [currentInvoice]);

  // PRD Addendum 5: Save Stock Item Master with group, unit, alternate unit, taxability, and GST rate
  const handleSaveStockItemMaster = async (
    savedData: {
      name: string;
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
    saveAndNext: boolean = false,
    applyToAllNew: boolean = false
  ) => {
    try {
      const res = await createNewStockItem({
        name: savedData.name,
        hsn: savedData.hsn,
        hsn_description: savedData.hsn_description,
        uom: savedData.uom,
        parent_group: savedData.parent_group,
        gst_rate: savedData.gst_rate,
        taxability: savedData.taxability,
        type_of_supply: savedData.type_of_supply,
        additional_units: savedData.additional_units,
        conversion: savedData.conversion,
      });

      if (targetItemIdxForMapping !== null && currentInvoice) {
        updateCurrentInvoice((inv) => {
          const updatedItems = inv.items.map((it, idx) => {
            if (idx === targetItemIdxForMapping) {
              return {
                ...it,
                matched_stock_item: res.item.name,
                item_name: res.item.name,
                uom: res.item.base_units || it.uom,
                hsn_sac: res.item.hsn_code || it.hsn_sac,
                hsn_description: savedData.hsn_description || (it as any).hsn_description,
                parent_group: savedData.parent_group,
                taxability: savedData.taxability,
                type_of_supply: savedData.type_of_supply,
                gst_rate: savedData.gst_rate,
                alternate_uom: savedData.additional_units || it.alternate_uom,
                pack_multiplier: savedData.conversion ? savedData.conversion : it.pack_multiplier,
                saved_draft_version: savedData.saved_draft_version || 1,
                requires_item_creation: true,
                mapping_status: 'VERIFIED' as const,
                mapping_confidence: 'HIGH' as const,
              };
            }
            if (applyToAllNew && (it.requires_item_creation || it.mapping_status === 'NEW_ITEM' || !it.matched_stock_item)) {
              return {
                ...it,
                parent_group: savedData.parent_group,
                taxability: savedData.taxability,
                type_of_supply: savedData.type_of_supply,
              };
            }
            return it;
          });
          return { ...inv, items: updatedItems };
        });
      }

      showAlert('Stock Item Master Created', `Stock item "${res.item.name}" created under "${savedData.parent_group}"!`, 'success');
      loadMasters();

      if (saveAndNext) {
        const nextItem = allNewItems.find((it) => it.originalIndex > (targetItemIdxForMapping ?? -1));
        if (nextItem) {
          setTargetItemIdxForMapping(nextItem.originalIndex);
          return;
        }
      }
      setIsNewItemModalOpen(false);
    } catch (err: any) {
      showAlert('Creation Failed', `Failed to create stock item: ${err.message}`, 'error');
    }
  };

  const handleUseExistingStockItem = (existingName: string) => {
    if (targetItemIdxForMapping !== null && currentInvoice) {
      handleLineItemChange(targetItemIdxForMapping, 'matched_stock_item', existingName);
      handleLineItemChange(targetItemIdxForMapping, 'requires_item_creation', false);
      handleLineItemChange(targetItemIdxForMapping, 'mapping_status', 'VERIFIED');
      handleLineItemChange(targetItemIdxForMapping, 'mapping_confidence', 'HIGH');
      showAlert('Item Mapped', `Mapped item to existing Tally stock item "${existingName}"!`, 'success');
      setIsNewItemModalOpen(false);
    }
  };

  // Create new Customer Ledger action (PRD Addendum 6)
  const handleSaveLedgerMaster = async (savedData: {
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
  }) => {
    try {
      await createLedgerMaster(savedData);

      if (currentInvoice) {
        updateCurrentInvoice((inv) => ({
          ...inv,
          buyer: {
            ...inv.buyer,
            name: savedData.name,
            matched_ledger_name: savedData.name,
            gstin: savedData.gstin,
            pan: savedData.pan,
            state: savedData.state,
            pincode: savedData.pincode,
            address: savedData.address_lines.join(', '),
            registration_type: savedData.registration_type,
            parent_group: savedData.parent_group,
            saved_draft_version: savedData.saved_draft_version || 1,
            requires_ledger_creation: false,
            mapping_status: 'AUTO_MAPPED',
            mapping_confidence: 'HIGH',
          },
        }));
      }

      showAlert('Customer Ledger Created', `Customer Ledger "${savedData.name}" created and verified in Tally masters!`, 'success');
      loadMasters();
      setIsNewLedgerModalOpen(false);
    } catch (err: any) {
      showAlert('Failed to Create Ledger', `Failed to create ledger: ${err.message}`, 'error');
    }
  };

  // Mapping Summary calculation for current invoice
  const mappingSummary = currentInvoice
    ? {
        itemsAutoMapped: currentInvoice.items.filter((it) => it.mapping_status === 'AUTO_MAPPED').length,
        itemsVerified: currentInvoice.items.filter((it) => it.mapping_status === 'VERIFIED' || it.mapping_status === 'AUTO_MAPPED').length,
        itemsPleaseCheck: currentInvoice.items.filter((it) => it.mapping_status === 'PLEASE_CHECK' || it.mapping_status === 'POSSIBLE_MATCH').length,
        itemsPossibleMatch: currentInvoice.items.filter((it) => it.mapping_status === 'POSSIBLE_MATCH').length,
        itemsUnmatched: currentInvoice.items.filter((it) => (it.mapping_status === 'UNMATCHED' || !it.matched_stock_item) && it.mapping_status !== 'VERIFIED' && it.mapping_status !== 'AUTO_MAPPED').length,
        itemsNew: currentInvoice.items.filter((it) => it.requires_item_creation || it.mapping_status === 'NEW_ITEM').length,
        partyStatus: currentInvoice.buyer.mapping_status || (currentInvoice.buyer.matched_ledger_name ? 'AUTO_MAPPED' : 'NEW_LEDGER'),
      }
    : null;

  // Filtered line items
  const filteredItems = currentInvoice
    ? currentInvoice.items.map((it, idx) => ({ ...it, originalIndex: idx })).filter((it) => {
        if (itemStatusFilter !== 'ALL') {
          if (itemStatusFilter === 'NEW_ITEM' && !it.requires_item_creation && it.mapping_status !== 'NEW_ITEM') return false;
          if (itemStatusFilter === 'PLEASE_CHECK' && it.mapping_status !== 'PLEASE_CHECK' && it.mapping_status !== 'POSSIBLE_MATCH') return false;
          if (itemStatusFilter === 'VERIFIED' && it.mapping_status !== 'VERIFIED' && it.mapping_status !== 'AUTO_MAPPED') return false;
          if (itemStatusFilter === 'UNMATCHED' && it.mapping_status !== 'UNMATCHED' && it.matched_stock_item) return false;
        }
        if (itemQueryFilter.trim()) {
          const q = itemQueryFilter.toLowerCase();
          const matchName = it.item_name.toLowerCase().includes(q);
          const matchMapped = (it.matched_stock_item || '').toLowerCase().includes(q);
          const matchHsn = (it.hsn_sac || '').toLowerCase().includes(q);
          const matchUom = (it.uom || '').toLowerCase().includes(q);
          if (!matchName && !matchMapped && !matchHsn && !matchUom) return false;
        }
        return true;
      })
    : [];

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <KangraLoader message="Checking authentication status..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/70 pb-24">
      {/* Header Section */}
      <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="w-9 h-9 rounded-xl border border-slate-200 bg-white shadow-xs flex items-center justify-center text-slate-500 hover:text-slate-900 hover:border-slate-300 transition-all"
                title="Return to Home"
              >
                <ArrowLeft className="w-4 h-4" />
              </Link>
              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                    SALES INVOICE → TALLY XML
                  </h1>
                  <Badge variant="primary" size="sm" className="bg-indigo-600 text-white font-bold shadow-xs">
                    SALES ONLY
                  </Badge>
                  {(isStaff || isAdmin) && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/10 text-amber-800 border border-amber-500/30 shadow-xs">
                      <GoldTick size="sm" />
                      <span>{isAdmin ? 'ADMIN UNLIMITED' : 'STAFF UNLIMITED'}</span>
                    </span>
                  )}
                  {hasRestoredSession && (
                    <span className="text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 px-2.5 py-0.5 rounded-full flex items-center gap-1 shadow-xs">
                      <Save className="w-3 h-3 text-indigo-600" />
                      Session Restored
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Convert Sales Invoice JPG/PNG/PDF into Tally-compatible XML (Outward Supply).
                </p>
              </div>
            </div>

            {/* Quick Action Masters & Settings */}
            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              {invoices.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResetSession}
                  className="text-xs flex items-center gap-1.5 text-rose-600 border-rose-200 hover:bg-rose-50 shadow-xs font-bold"
                  title="Clear current data and start a new batch"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Start New Batch</span>
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsStockModalOpen(true)}
                className="text-xs flex items-center gap-1.5 shadow-xs font-semibold"
              >
                <Package className="w-3.5 h-3.5 text-indigo-600" />
                <span>Stock Items ({stockItems.length})</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsLedgerModalOpen(true)}
                className="text-xs flex items-center gap-1.5 shadow-xs font-semibold"
              >
                <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                <span>Customer Ledgers ({ledgers.length})</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsSettingsModalOpen(true)}
                className="text-xs flex items-center gap-1.5 shadow-xs font-semibold"
              >
                <Settings2 className="w-3.5 h-3.5 text-slate-500" />
                <span>Settings</span>
              </Button>
            </div>
          </div>

          {/* Workflow Step Indicators */}
          <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-100 text-xs font-semibold">
            <span
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full transition-all ${
                currentStep === 1 ? 'bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs font-bold' : 'text-slate-400'
              }`}
            >
              <span className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold ${
                currentStep === 1 ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-500'
              }`}>
                1
              </span>
              Pre-Import & Upload Sales Invoices
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
            <span
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full transition-all ${
                currentStep === 2 ? 'bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs font-bold' : 'text-slate-400'
              }`}
            >
              <span className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold ${
                currentStep === 2 ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-500'
              }`}>
                2
              </span>
              Review Seller, Customer & Sales Items
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
            <span
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full transition-all ${
                currentStep === 3 ? 'bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs font-bold' : 'text-slate-400'
              }`}
            >
              <span className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold ${
                currentStep === 3 ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-500'
              }`}>
                3
              </span>
              Generate Sales Tally XML
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        {errorMsg && (
          <div className="mb-6">
            <StatusAlert
              type="error"
              title="Sales Extraction / Processing Notice"
              message={errorMsg}
              onDismiss={() => setErrorMsg(null)}
            />
          </div>
        )}

        {/* STEP 1: PRE-IMPORT (OPTIONAL) + UPLOAD SALES INVOICES */}
        {currentStep === 1 && (
          <div className="space-y-6">
            {/* PRE-IMPORT OPTIONS FIRST */}
            <Card className="border-brand-200 shadow-sm bg-gradient-to-br from-brand-50/40 via-white to-slate-50/50">
              <CardHeader className="pb-3 border-b border-brand-100">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <FolderOpen className="w-5 h-5 text-brand-600" />
                    <CardTitle className="text-sm sm:text-base font-extrabold text-navy-900">
                      IMPORT TALLY MASTERS (OPTIONAL)
                    </CardTitle>
                    <Badge variant="neutral" size="sm">
                      Optional — you can skip this step
                    </Badge>
                  </div>
                  {(stockItems.length > 0 || ledgers.length > 0) && (
                    <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
                      <CheckCheck className="w-4 h-4 text-emerald-600" />
                      <span>{stockItems.length} Stock Items & {ledgers.length} Ledgers Loaded</span>
                    </div>
                  )}
                </div>
                <CardDescription className="text-xs text-slate-600 mt-1">
                  Already have Tally Ledgers or Stock Items? Import them before uploading your sales invoice for automated 100% accurate mapping.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4 sm:p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsLedgerModalOpen(true)}
                      className="text-xs font-bold flex items-center gap-1.5 border-brand-300 hover:bg-brand-50 text-brand-800"
                    >
                      <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                      Import Ledgers ({ledgers.length})
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsStockModalOpen(true)}
                      className="text-xs font-bold flex items-center gap-1.5 border-brand-300 hover:bg-brand-50 text-brand-800"
                    >
                      <Package className="w-3.5 h-3.5 text-brand-600" />
                      Import Stock Items ({stockItems.length})
                    </Button>
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      uploadSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
                      fileInputRef.current?.click();
                    }}
                    className="text-xs font-bold flex items-center gap-1.5"
                  >
                    <span>Continue Without Import</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* INVOICE UPLOAD ZONE */}
            <div ref={uploadSectionRef}>
              <Card className="border-slate-200 shadow-sm bg-white overflow-hidden">
                <CardHeader className="bg-slate-50/50 border-b border-slate-100">
                  <CardTitle className="text-base text-navy-900 flex items-center gap-2">
                    <UploadCloud className="w-5 h-5 text-brand-600" />
                    Upload Sales Invoices (JPG, JPEG, PNG, or PDF)
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Select or drag your outward supply invoices. The OCR engine will extract Seller, Customer, Invoice details, and Sales line items.
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-6">
                  <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-colors cursor-pointer ${
                      dragActive
                        ? 'border-brand-500 bg-brand-50/30'
                        : 'border-slate-300 hover:border-slate-400 bg-slate-50/30'
                    }`}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.jpg,.jpeg,.png,.webp"
                      className="hidden"
                      onChange={handleFileInputChange}
                    />

                    <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-4 border border-indigo-100 shadow-xs">
                      <UploadCloud className="w-8 h-8" />
                    </div>

                    <h3 className="text-base font-bold text-slate-900 mb-1">
                      Drag & drop your Sales Invoice files here
                    </h3>
                    <p className="text-xs text-slate-500 mb-4">
                      Supports photos (JPG/PNG), scanned PDFs, and multi-page digital PDFs.
                    </p>

                    <Button
                      variant="outline"
                      size="sm"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        fileInputRef.current?.click();
                      }}
                      className="text-xs font-semibold rounded-xl shadow-xs"
                    >
                      Browse Files
                    </Button>
                  </div>

                  {/* Selected Files List & Extract Action */}
                  <div className="mt-6 space-y-4">
                    {selectedFiles.length > 0 && (
                      <>
                        <div className="flex items-center justify-between text-xs font-bold text-slate-900">
                          <span>Selected Documents ({selectedFiles.length})</span>
                          <button
                            type="button"
                            onClick={() => setSelectedFiles([])}
                            className="text-rose-600 hover:underline"
                          >
                            Clear All
                          </button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                          {selectedFiles.map((file, idx) => (
                            <div
                              key={idx}
                              className="flex items-center justify-between p-3 rounded-xl border border-slate-200/90 bg-white shadow-xs hover:shadow-card transition-all"
                            >
                              <div className="flex items-center gap-2.5 overflow-hidden">
                                <FileText className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                                <div className="truncate">
                                  <p className="text-xs font-semibold text-slate-900 truncate">{file.name}</p>
                                  <span className="text-[10px] text-slate-400">
                                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                                  </span>
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => removeFile(idx)}
                                className="text-slate-400 hover:text-rose-600 p-1"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </>
                    )}

                    {errorMsg && (
                      <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-semibold flex items-center gap-2 shadow-xs">
                        <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                        <span>{errorMsg}</span>
                      </div>
                    )}

                    <div className="pt-2 flex justify-end">
                      <Button
                        variant="primary"
                        size="md"
                        onClick={handleUploadAndProcess}
                        disabled={selectedFiles.length === 0 || isProcessing}
                        className="w-full sm:w-auto font-bold flex items-center gap-2 px-8 bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 rounded-xl shadow-xs"
                      >
                        {isProcessing ? (
                          <>
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            {processingStatus || 'Extracting Sales Invoices...'}
                          </>
                        ) : selectedFiles.length > 0 ? (
                          <>
                            <Sparkles className="w-4 h-4" />
                            Extract & Review Sales Invoices ({selectedFiles.length})
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4" />
                            Extract & Review Sales Invoices (Select file first)
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {isProcessing && (
          <KangraLoader
            fullScreen
            size="lg"
            text={processingStatus || 'Extracting Sales Invoices...'}
            subtext="Analyzing invoice headers, dual quantities, tax breakdown and line items"
          />
        )}

        {/* STEP 2: REVIEW & EDIT SALES INVOICE WORKFLOW */}
        {currentStep === 2 && currentInvoice && (
          <div className="space-y-6">
            {/* Batch Metrics Bar */}
            {summary && (
              <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-card">
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-4 text-center sm:text-left">
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Invoices</span>
                    <p className="text-base font-extrabold text-slate-900">{summary.total_documents ?? invoices.length}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Taxable Total</span>
                    <p className="text-base font-extrabold text-slate-900 font-mono">
                      ₹{Number(summary.total_taxable ?? summary.total_taxable_value ?? 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">CGST</span>
                    <p className="text-base font-extrabold text-blue-600 font-mono">
                      ₹{Number(summary.total_cgst ?? 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">SGST</span>
                    <p className="text-base font-extrabold text-blue-600 font-mono">
                      ₹{Number(summary.total_sgst ?? 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">IGST</span>
                    <p className="text-base font-extrabold text-purple-600 font-mono">
                      ₹{Number(summary.total_igst ?? 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Grand Total</span>
                    <p className="text-base font-extrabold text-emerald-600 font-mono">
                      ₹{Number(summary.total_grand ?? summary.total_invoice_value ?? 0).toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* MAPPING QUALITY & SUMMARY BAR */}
            {mappingSummary && (
              <Card className="border-slate-200/90 bg-white shadow-card rounded-2xl">
                <CardContent className="p-4 sm:p-5">
                  <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 text-xs">
                    <div>
                      <h4 className="font-extrabold text-slate-900 flex items-center gap-1.5">
                        <CheckCheck className="w-4 h-4 text-indigo-600" />
                        Tally Masters Mapping Summary:
                      </h4>
                      <div className="flex flex-wrap items-center gap-2 mt-1.5">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200 text-[11px]">
                          ✓ {mappingSummary.itemsAutoMapped} Auto-Mapped
                        </span>
                        {mappingSummary.itemsPleaseCheck > 0 && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 font-semibold border border-amber-200 text-[11px]">
                            ⚠ {mappingSummary.itemsPleaseCheck} Please Check
                          </span>
                        )}
                        {mappingSummary.itemsPossibleMatch > 0 && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-orange-50 text-orange-700 font-semibold border border-orange-200 text-[11px]">
                            ⚠ {mappingSummary.itemsPossibleMatch} Possible Match
                          </span>
                        )}
                        {mappingSummary.itemsUnmatched > 0 && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 font-semibold border border-rose-200 text-[11px]">
                            ❌ {mappingSummary.itemsUnmatched} Unmatched
                          </span>
                        )}
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-semibold border border-purple-200 text-[11px]">
                          ➕ {mappingSummary.itemsNew} New Items
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsStockModalOpen(true)}
                        className="text-xs font-semibold"
                      >
                        <Package className="w-3.5 h-3.5 mr-1 text-brand-600" />
                        Manage Stock Items ({stockItems.length})
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsLedgerModalOpen(true)}
                        className="text-xs font-semibold"
                      >
                        <BookOpen className="w-3.5 h-3.5 mr-1 text-blue-600" />
                        Manage Ledgers ({ledgers.length})
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* PRD Section 7 & 13: 6-Point Reconciliation Status Banner */}
            {currentInvoice.reconciliation_flags && currentInvoice.reconciliation_flags.length > 0 ? (
              <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex flex-col gap-2 shadow-xs">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-[12px] text-amber-900">Reconciliation flags — Please verify highlighted lines</span>
                      <span className="text-[10px] font-bold text-amber-800 bg-amber-200/80 px-2 py-0.5 rounded-full">
                        Needs Review
                      </span>
                    </div>
                    <ul className="mt-1 list-disc list-inside space-y-0.5 text-[11px] text-amber-800">
                      {currentInvoice.reconciliation_flags.map((flag, fIdx) => (
                        <li key={fIdx}>{flag}</li>
                      ))}
                    </ul>
                    <div className="mt-1.5 pt-1.5 border-t border-amber-200/60 text-[11px] font-mono text-amber-800 flex items-center justify-between">
                      <span>Formula: {currentInvoice.tax_mode === 'inclusive' ? 'Inclusive Mode: Sum of Lines ≈ Grand Total' : 'Exclusive Mode: Taxable + GST ≈ Grand Total'}</span>
                      <span>Tax Mode: <strong className="uppercase">{currentInvoice.tax_mode || 'exclusive'}</strong></span>
                    </div>
                  </div>
                </div>
              </div>
            ) : currentInvoice.reconciliation_passed ? (
              <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center justify-between shadow-xs">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span className="font-bold text-[11.5px]">
                    Reconciliation passed — all 6 checks match ({currentInvoice.tax_mode === 'inclusive' ? 'Sum of Lines ≈ Grand Total' : 'Taxable + GST = Grand Total'})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-full border border-purple-200">
                    {currentInvoice.tax_mode === 'inclusive' ? 'Tax-Inclusive' : 'Tax-Exclusive'}
                  </span>
                  <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full border border-emerald-300">
                    ✓ 100% Balanced
                  </span>
                </div>
              </div>
            ) : null}

            {/* Reconciliation Note & GSTIN Role Review Banner */}
            {currentInvoice.item_count_reconciliation_note && (
              <div className="p-3 rounded-xl bg-blue-50/70 border border-blue-200 text-blue-900 text-xs flex items-center justify-between">
                <span className="font-semibold flex items-center gap-1.5">
                  <FileCheck className="w-4 h-4 text-blue-600" />
                  Item Count Check: {currentInvoice.item_count_reconciliation_note}
                </span>
                <span className="text-[11px] text-blue-600 font-mono">Row integrity validated</span>
              </div>
            )}

            {currentInvoice.gstin_role_needs_review && (
              <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <div>
                    <p className="font-bold">GSTIN Role Requires Review</p>
                    <p className="text-[11px] text-amber-800">
                      Multiple GSTINs detected. In Sales, please verify that Seller is Our Company and Buyer is Customer.
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSwapSellerCustomer}
                  className="text-xs bg-white font-bold flex items-center gap-1 border-amber-300 hover:bg-amber-100"
                >
                  <ArrowUpDown className="w-3.5 h-3.5 text-amber-700" />
                  Swap Seller ⇄ Customer
                </Button>
              </div>
            )}

            {/* PRD Validation Engine Diagnostic Strip (Rules V01 - V23) */}
            {currentInvoice.validation_violations && currentInvoice.validation_violations.length > 0 && (
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-extrabold text-navy-900 text-[11px] flex items-center gap-1.5 uppercase tracking-wider">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    GST Validation & Arithmetic Checks ({currentInvoice.validation_violations.length} notices)
                  </span>
                  <div className="flex items-center gap-2">
                    {currentInvoice.validation_violations.filter(v => v.severity === 'ERROR').length > 0 && (
                      <span className="text-[10px] font-bold text-rose-700 bg-rose-100 px-2 py-0.5 rounded border border-rose-200">
                        {currentInvoice.validation_violations.filter(v => v.severity === 'ERROR').length} Errors
                      </span>
                    )}
                    {currentInvoice.validation_violations.filter(v => v.severity === 'WARN').length > 0 && (
                      <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded border border-amber-200">
                        {currentInvoice.validation_violations.filter(v => v.severity === 'WARN').length} Warnings
                      </span>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                  {currentInvoice.validation_violations.map((violation, vIdx) => (
                    <div
                      key={vIdx}
                      className={`p-2 rounded-lg text-[11px] flex items-start gap-2 border ${
                        violation.severity === 'ERROR'
                          ? 'bg-rose-50/80 border-rose-200 text-rose-900'
                          : 'bg-amber-50/80 border-amber-200 text-amber-900'
                      }`}
                    >
                      <span className={`font-mono font-extrabold text-[10px] px-1.5 py-0.2 rounded flex-shrink-0 ${
                        violation.severity === 'ERROR' ? 'bg-rose-200 text-rose-800' : 'bg-amber-200 text-amber-800'
                      }`}>
                        {violation.rule_id}
                      </span>
                      <span className="font-medium leading-tight">{violation.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Invoices Tab Selector for Multi-invoice batch */}
            {invoices.length > 1 && (
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {invoices.map((inv, idx) => (
                  <button
                    key={inv.id || idx}
                    type="button"
                    onClick={() => setActiveIndex(idx)}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap flex items-center gap-2 border ${
                      idx === activeIndex
                        ? 'bg-slate-900 text-white border-slate-900 shadow-xs'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <span>
                      {inv.invoice_number || `Invoice #${idx + 1}`}
                    </span>
                    <span className="text-[10px] opacity-80 font-mono">
                      ₹{Number(inv.grand_total || 0).toFixed(2)}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {/* Extraction Engine & Accuracy Diagnostic Bar */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 p-3.5 rounded-2xl bg-white border border-slate-200/90 shadow-xs text-xs">
              <div className="flex items-center gap-2.5 flex-wrap">
                {currentInvoice.ai_extracted ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-800 border border-blue-200 font-extrabold text-[11px]">
                    <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                    Google Gemini AI ({currentInvoice.ai_model_used || 'gemini-3.1-flash-lite'})
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-900 border border-amber-300 font-extrabold text-[11px]">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
                    Local OCR Fallback (RapidOCR Engine)
                  </span>
                )}
                <span className="text-slate-600 font-medium text-xs">
                  {currentInvoice.source_filename ? `File: ${currentInvoice.source_filename}` : 'Uploaded Bill'}
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-semibold text-slate-500">
                  {currentInvoice.items?.length || 0} items extracted
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-blue-50 border border-blue-200 text-blue-700">
                  Q × R = Taxable ✓
                </span>
              </div>
            </div>

            {/* SELLER vs BUYER / CUSTOMER Identification */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* OUR COMPANY / SELLER */}
              <Card className="border-slate-200/90 shadow-card bg-white rounded-2xl overflow-hidden">
                <CardHeader className="bg-gradient-to-r from-slate-50/80 to-white border-b border-slate-200/80 px-5 py-3.5">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-extrabold text-slate-900 flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center">
                        <ShieldCheck className="w-4 h-4 text-indigo-600" />
                      </div>
                      OUR COMPANY / SELLER
                    </CardTitle>
                    <span className="text-[10px] font-bold uppercase bg-slate-100 text-slate-700 px-2.5 py-1 rounded-full border border-slate-200">
                      Outward Supplier
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="p-5 space-y-3.5 text-xs">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                        Company / Seller Name
                      </label>
                      <CompanyProfileDropdown
                        onSelectCompany={handleSelectSellerCompany}
                        currentCompanyName={currentInvoice.supplier.name}
                        currentGstin={currentInvoice.supplier.gstin}
                        currentState={currentInvoice.supplier.state}
                        currentAddress={currentInvoice.supplier.address}
                        theme="indigo"
                        ledgers={ledgers}
                      />
                    </div>
                    <Input
                      value={currentInvoice.supplier.name}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          supplier: { ...inv.supplier, name: e.target.value },
                        }))
                      }
                      title={currentInvoice.supplier.name}
                      className="text-xs sm:text-sm font-bold text-slate-900 h-10 rounded-xl px-3"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                        Seller GSTIN
                      </label>
                      <Input
                        value={currentInvoice.supplier.gstin || ''}
                        onChange={(e) =>
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            supplier: { ...inv.supplier, gstin: e.target.value.toUpperCase() },
                          }))
                        }
                        title={currentInvoice.supplier.gstin || ''}
                        className="text-xs sm:text-sm font-mono font-bold uppercase tracking-wider h-10 rounded-xl px-3"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                        State
                      </label>
                      <Input
                        value={currentInvoice.supplier.state || ''}
                        onChange={(e) =>
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            supplier: { ...inv.supplier, state: e.target.value },
                          }))
                        }
                        title={currentInvoice.supplier.state || ''}
                        className="text-xs sm:text-sm h-10 rounded-xl px-3"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      Address
                    </label>
                    <Input
                      value={currentInvoice.supplier.address || ''}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          supplier: { ...inv.supplier, address: e.target.value },
                        }))
                      }
                      placeholder="Seller registered address"
                      title={currentInvoice.supplier.address || ''}
                      className="text-xs sm:text-sm h-10 rounded-xl px-3"
                    />
                  </div>
                </CardContent>
              </Card>

              {/* CUSTOMER / BUYER */}
              <Card className="border-indigo-200/90 shadow-card bg-white rounded-2xl overflow-hidden">
                <CardHeader className="bg-gradient-to-r from-indigo-50/80 via-blue-50/40 to-white border-b border-indigo-100/80 px-5 py-3.5">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-extrabold text-slate-900 flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center">
                        <BookOpen className="w-4 h-4 text-indigo-600" />
                      </div>
                      CUSTOMER / BUYER
                    </CardTitle>
                    <span className="text-[10px] font-bold uppercase bg-indigo-100/80 text-indigo-800 px-2.5 py-1 rounded-full border border-indigo-200">
                      Customer / Debtor
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="p-5 space-y-3.5 text-xs">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                        Customer Name
                      </label>
                      <CompanyProfileDropdown
                        onSelectCompany={(profile) => {
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            buyer: {
                              ...inv.buyer,
                              name: profile.name,
                              matched_ledger_name: profile.name,
                              gstin: profile.gstin,
                              state: profile.state,
                              address: profile.address,
                              mapping_status: 'AUTO_MAPPED',
                            },
                          }));
                        }}
                        currentCompanyName={currentInvoice.buyer.name}
                        currentGstin={currentInvoice.buyer.gstin}
                        currentState={currentInvoice.buyer.state}
                        currentAddress={currentInvoice.buyer.address}
                        theme="indigo"
                        ledgers={ledgers}
                      />
                    </div>
                    <Input
                      value={currentInvoice.buyer.name}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          buyer: { ...inv.buyer, name: e.target.value },
                        }))
                      }
                      title={currentInvoice.buyer.name}
                      className="text-xs sm:text-sm font-bold text-slate-900 h-10 rounded-xl px-3"
                    />
                  </div>

                  {/* Customer Tally Ledger Matching Bar */}
                  <div className="p-3 rounded-xl bg-gradient-to-r from-indigo-50/60 to-blue-50/40 border border-indigo-200/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-indigo-950 text-[11px]">Customer Tally Ledger:</span>
                      {currentInvoice.buyer.matched_ledger_name ? (
                        <span className="text-[10px] text-emerald-800 bg-emerald-100 border border-emerald-300 px-2 py-0.5 rounded-md font-bold flex items-center gap-1 shadow-xs">
                          <Check className="w-3 h-3 text-emerald-600" />
                          Mapped: {currentInvoice.buyer.matched_ledger_name}
                        </span>
                      ) : (
                        <span className="text-[10px] text-purple-700 bg-purple-100/80 border border-purple-200 px-2 py-0.5 rounded-md font-bold">
                          ➕ Create New Ledger in Tally
                        </span>
                      )}
                    </div>

                    {/* Suggestions if uncertain */}
                    {currentInvoice.buyer.match_suggestions && currentInvoice.buyer.match_suggestions.length > 0 && !currentInvoice.buyer.matched_ledger_name && (
                      <div className="text-[11px] space-y-1 pt-1 border-t border-indigo-200/60">
                        <span className="text-slate-500 font-semibold">Suggested Matches from Tally:</span>
                        <div className="flex flex-wrap gap-1.5">
                          {currentInvoice.buyer.match_suggestions.map((sug, sIdx) => (
                            <button
                              key={sIdx}
                              type="button"
                              onClick={() => handleAcceptLedgerSuggestion(sug.name)}
                              className="px-2 py-1 bg-white hover:bg-indigo-50 text-indigo-800 border border-indigo-300 rounded-lg text-[10px] font-semibold flex items-center gap-1 transition-colors shadow-xs"
                            >
                              <span>{sug.name}</span>
                              <span className="text-[9px] text-indigo-600">({sug.similarity_score}%)</span>
                              <Check className="w-3 h-3 text-emerald-600" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-2 pt-0.5">
                      <button
                        type="button"
                        onClick={() => {
                          setNewLedgerData({
                            name: currentInvoice.buyer.name,
                            group: 'Sundry Debtors',
                            gstin: currentInvoice.buyer.gstin || '',
                            state: currentInvoice.buyer.state || '',
                          });
                          setIsNewLedgerModalOpen(true);
                        }}
                        className="text-[11px] text-indigo-700 hover:text-indigo-800 hover:underline font-bold"
                      >
                        [+ Create Customer Ledger in Masters]
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                        CUSTOMER GSTIN
                      </label>
                      <Input
                        value={currentInvoice.buyer.gstin || ''}
                        onChange={(e) =>
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            buyer: { ...inv.buyer, gstin: e.target.value.toUpperCase() },
                          }))
                        }
                        title={currentInvoice.buyer.gstin || ''}
                        className="text-xs sm:text-sm font-mono font-bold uppercase tracking-wider h-10 rounded-xl px-3"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                        State
                      </label>
                      <Input
                        value={currentInvoice.buyer.state || ''}
                        onChange={(e) =>
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            buyer: { ...inv.buyer, state: e.target.value },
                          }))
                        }
                        title={currentInvoice.buyer.state || ''}
                        className="text-xs sm:text-sm h-10 rounded-xl px-3"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                      Address
                    </label>
                    <Input
                      value={currentInvoice.buyer.address || ''}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          buyer: { ...inv.buyer, address: e.target.value },
                        }))
                      }
                      placeholder="Customer billing address"
                      title={currentInvoice.buyer.address || ''}
                      className="text-xs sm:text-sm h-10 rounded-xl px-3"
                    />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* INVOICE METADATA DETAILS */}
            <Card className="border-slate-200/90 shadow-card bg-white rounded-2xl overflow-hidden">
              <CardHeader className="bg-gradient-to-r from-slate-50/80 to-white border-b border-slate-100 px-5 py-3">
                <CardTitle className="text-xs font-extrabold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-slate-500" />
                  Sales Invoice & Tax Metadata
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3.5 text-xs">
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">SALES INVOICE NO</label>
                    <Input
                      value={currentInvoice.invoice_number}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          invoice_number: e.target.value,
                        }))
                      }
                      title={currentInvoice.invoice_number}
                      className="text-xs sm:text-sm font-mono font-bold text-indigo-700 h-10 rounded-xl px-3"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Bill No</label>
                    <Input
                      value={currentInvoice.bill_number || currentInvoice.invoice_number}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          bill_number: e.target.value,
                        }))
                      }
                      title={currentInvoice.bill_number || currentInvoice.invoice_number}
                      className="text-xs sm:text-sm font-mono font-semibold h-10 rounded-xl px-3"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Invoice Date</label>
                    <Input
                      type="date"
                      value={currentInvoice.invoice_date}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          invoice_date: e.target.value,
                        }))
                      }
                      title={currentInvoice.invoice_date}
                      className="text-xs sm:text-sm font-mono h-10 rounded-xl px-3"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Due Date</label>
                    <Input
                      type="date"
                      value={currentInvoice.due_date || ''}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          due_date: e.target.value,
                        }))
                      }
                      title={currentInvoice.due_date || ''}
                      className="text-xs sm:text-sm font-mono h-10 rounded-xl px-3"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">P.O. Number</label>
                    <Input
                      value={currentInvoice.po_number || ''}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          po_number: e.target.value,
                        }))
                      }
                      placeholder="PO reference"
                      title={currentInvoice.po_number || ''}
                      className="text-xs sm:text-sm font-mono h-10 rounded-xl px-3"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">E-Way Bill</label>
                    <Input
                      value={currentInvoice.eway_bill_number || ''}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          eway_bill_number: e.target.value,
                        }))
                      }
                      placeholder="12 digits"
                      title={currentInvoice.eway_bill_number || ''}
                      className="text-xs sm:text-sm font-mono h-10 rounded-xl px-3"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Place of Supply</label>
                    <Input
                      value={currentInvoice.place_of_supply || ''}
                      onChange={(e) =>
                        updateCurrentInvoice((inv) => ({
                          ...inv,
                          place_of_supply: e.target.value,
                        }))
                      }
                      onBlur={(e) => {
                        const norm = normalizeState(e.target.value);
                        if (norm) {
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            place_of_supply: norm.name,
                          }));
                        }
                      }}
                      title={currentInvoice.place_of_supply || ''}
                      className="text-xs sm:text-sm font-semibold h-10 rounded-xl px-3"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* PRD ADDENDUM 5: REVIEW NEW ITEMS BANNER */}
            {allNewItems.length > 0 && (
              <div className="p-4 bg-gradient-to-r from-amber-500/10 via-orange-500/5 to-amber-50 border border-amber-200/90 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-400/40 flex items-center justify-center text-amber-800 shrink-0 shadow-2xs">
                    <Sparkles className="w-4 h-4 text-amber-600" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-xs sm:text-sm font-extrabold text-amber-950">
                        {allNewItems.length} new {allNewItems.length === 1 ? 'stock item' : 'stock items'} will be created automatically in Tally
                      </p>
                      <Badge variant="warning" size="sm" className="font-bold text-[10px] bg-amber-100 text-amber-800 border-amber-300">
                        One-File Import
                      </Badge>
                    </div>
                    <p className="text-[11px] text-amber-800/90 mt-0.5">
                      New items are built directly into your download file. You can review or customize Stock Groups (Parent) and GST rates before export.
                    </p>
                  </div>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    if (allNewItems.length > 0) {
                      setTargetItemIdxForMapping(allNewItems[0].originalIndex);
                      setIsNewItemModalOpen(true);
                    }
                  }}
                  className="bg-amber-600 hover:bg-amber-700 text-white font-extrabold text-xs shrink-0 shadow-xs flex items-center gap-1.5"
                >
                  <Package className="w-3.5 h-3.5" />
                  <span>Review New Items ({allNewItems.length})</span>
                </Button>
              </div>
            )}

            {/* PRD ADDENDUM 5: SLAB SUMMARY VERIFICATION BOX */}
            {slabVerification && slabVerification.slabs.length > 0 && (
              <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs space-y-3">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-200/60 font-bold text-xs">
                      %
                    </div>
                    <div>
                      <h4 className="text-xs sm:text-sm font-extrabold text-slate-900 flex items-center gap-2">
                        <span>GST Slab Breakdown & Verification</span>
                        {slabVerification.isBalanced ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Slabs Balanced (&plusmn;&#8377;1.00)
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                            <AlertTriangle className="w-3 h-3 text-amber-600" />
                            Diff: &#8377;{slabVerification.taxableDiff.toFixed(2)} taxable / &#8377;{slabVerification.taxDiff.toFixed(2)} tax
                          </span>
                        )}
                      </h4>
                      <p className="text-[10px] sm:text-[11px] text-slate-500">
                        Line rates are isolated per item. Taxable value & tax verified against bill summary.
                      </p>
                    </div>
                  </div>

                  <div className="text-right text-[11px] font-mono text-slate-600">
                    <span>Total Taxable: <strong>&#8377;{slabVerification.totalTaxable.toFixed(2)}</strong></span>
                    <span className="mx-1.5 text-slate-300">|</span>
                    <span>Total Tax: <strong>&#8377;{slabVerification.totalTax.toFixed(2)}</strong></span>
                  </div>
                </div>

                {/* Slabs Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                  {slabVerification.slabs.map((slab) => (
                    <div
                      key={slab.label}
                      className="p-2.5 rounded-xl border border-slate-100 bg-slate-50/70 hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                        <span className="text-emerald-700">{slab.label}</span>
                        <span className="text-[10px] text-slate-500 font-normal">{slab.count} {slab.count === 1 ? 'item' : 'items'}</span>
                      </div>
                      <div className="mt-1.5 text-[11px] font-mono text-slate-600 space-y-0.5">
                        <div className="flex justify-between">
                          <span className="text-slate-400 text-[10px]">Taxable:</span>
                          <span>&#8377;{slab.taxable.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400 text-[10px]">Tax:</span>
                          <span className="font-semibold text-slate-700">&#8377;{slab.tax.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ATOMIC SALES ITEMS TABLE WITH FILTER & SEARCH */}
            <Card className="border-slate-200/90 shadow-card bg-white rounded-2xl overflow-hidden">
              <CardHeader className="bg-gradient-to-r from-slate-50/90 via-slate-50/50 to-white border-b border-slate-100 p-4 sm:p-5">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm font-extrabold text-slate-900 flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                        <Package className="w-4 h-4" />
                      </div>
                      SALES ITEMS ({currentInvoice.items.length})
                    </CardTitle>
                    <CardDescription className="text-xs text-slate-500">
                      Atomic item records. Check mappings, accept suggestions, or create missing stock items in Tally.
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap items-center gap-2.5">
                    {/* Tax Mode Segment Control (PRD 5.10) */}
                    <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200/80 shadow-xs">
                      <span className="text-[10px] font-bold text-slate-500 px-1.5 uppercase tracking-wider">Tax Mode:</span>
                      <button
                        type="button"
                        onClick={() => handleToggleTaxMode('exclusive')}
                        className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                          (currentInvoice.tax_mode || 'exclusive') === 'exclusive'
                            ? 'bg-white text-slate-900 shadow-xs border border-slate-200/60'
                            : 'text-slate-500 hover:text-slate-900'
                        }`}
                      >
                        Exclusive
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleTaxMode('inclusive')}
                        className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                          currentInvoice.tax_mode === 'inclusive'
                            ? 'bg-purple-600 text-white shadow-xs'
                            : 'text-slate-500 hover:text-purple-700'
                        }`}
                      >
                        Inclusive
                      </button>
                    </div>

                    {/* Pack Quantity Mode Control (PRD Addendum 2) */}
                    {currentInvoice.items.some((it) => it.has_dual_qty || it.can_convert_to_pieces) && (
                      <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200/80 shadow-xs">
                        <span className="text-[10px] font-bold text-slate-500 px-1.5 uppercase tracking-wider">Pack Qty:</span>
                        <button
                          type="button"
                          onClick={() => handleTogglePackQuantityOption('pieces')}
                          className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                            (currentInvoice.pack_quantity_option || 'pieces') === 'pieces'
                              ? 'bg-blue-600 text-white shadow-xs'
                              : 'text-slate-500 hover:text-blue-700'
                          }`}
                          title="Option 2: Multiplied quantity into pieces for Tally stock tracking"
                        >
                          Pieces (Opt 2)
                        </button>
                        <button
                          type="button"
                          onClick={() => handleTogglePackQuantityOption('bulk')}
                          className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                            currentInvoice.pack_quantity_option === 'bulk'
                              ? 'bg-white text-slate-900 shadow-xs border border-slate-200/60'
                              : 'text-slate-500 hover:text-slate-900'
                          }`}
                          title="Option 1: Bulk quantity and unit as printed on the bill"
                        >
                          Bulk (Opt 1)
                        </button>
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      {currentInvoice.items.some((it) => it.requires_item_creation || it.mapping_status === 'NEW_ITEM' || !it.matched_stock_item) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDownloadStockItemsMasterXml(true)}
                          disabled={isDownloadingItemsXml}
                          className="text-xs font-extrabold flex items-center gap-1.5 rounded-xl border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-950 shadow-xs"
                          title="Download Tally Master XML containing only newly detected / unmapped stock items"
                        >
                          <Download className="w-3.5 h-3.5 text-amber-700" />
                          {isDownloadingItemsXml
                            ? 'Generating...'
                            : `Download New Items XML (${currentInvoice.items.filter((it) => it.requires_item_creation || it.mapping_status === 'NEW_ITEM' || !it.matched_stock_item).length})`}
                        </Button>
                      )}

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDownloadStockItemsMasterXml(false)}
                        disabled={isDownloadingItemsXml || currentInvoice.items.length === 0}
                        className="text-xs font-bold flex items-center gap-1.5 rounded-xl border-purple-300 bg-purple-50 hover:bg-purple-100 text-purple-900 shadow-xs"
                        title="Download Tally Master XML to import all stock items into Tally before importing sales vouchers"
                      >
                        <Download className="w-3.5 h-3.5 text-purple-700" />
                        {isDownloadingItemsXml ? 'Generating...' : `Download All Stock Items XML (${currentInvoice.items.length})`}
                      </Button>

                      <Button variant="outline" size="sm" onClick={handleAddLineItem} className="text-xs font-bold flex items-center gap-1.5 rounded-xl border-slate-300 hover:bg-slate-50 shadow-xs">
                        <Plus className="w-3.5 h-3.5 text-indigo-600" />
                        Add Sales Item
                      </Button>
                    </div>
                  </div>
                </div>

                {/* NOTIFICATION: MASTER XML DOWNLOADED */}
                {itemsXmlDownloadedMsg && (
                  <div className="p-3 bg-purple-50 border border-purple-200 text-purple-900 rounded-xl text-xs flex items-center justify-between gap-3 shadow-xs mt-3 animate-in fade-in duration-150">
                    <div className="flex items-center gap-2">
                      <Package className="w-4 h-4 text-purple-600 flex-shrink-0" />
                      <span className="font-semibold">{itemsXmlDownloadedMsg}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setItemsXmlDownloadedMsg(null)}
                      className="text-purple-600 hover:text-purple-900 font-bold text-xs p-1"
                    >
                      ✕
                    </button>
                  </div>
                )}

                {/* NOTIFICATION: ITEM AUTOMATICALLY CHANGED FROM STOCK CATALOG */}
                {itemUpdatedToast && (
                  <div className="p-3 bg-emerald-50 border border-emerald-300 text-emerald-950 rounded-xl text-xs flex items-center justify-between gap-3 shadow-xs mt-3 animate-in fade-in duration-150">
                    <div className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-emerald-600 flex-shrink-0 stroke-[3]" />
                      <span className="font-bold">{itemUpdatedToast}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setItemUpdatedToast(null)}
                      className="text-emerald-700 hover:text-emerald-950 font-bold text-xs p-1"
                    >
                      ✕
                    </button>
                  </div>
                )}

                {/* FILTER MAPPING RESULTS & SEARCH */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-3 mt-3 border-t border-slate-200/70">
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
                    <Filter className="w-3.5 h-3.5 text-slate-400 mr-1 flex-shrink-0" />
                    <button
                      type="button"
                      onClick={() => setItemStatusFilter('ALL')}
                      className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
                        itemStatusFilter === 'ALL'
                          ? 'bg-slate-900 text-white shadow-xs'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      All ({currentInvoice.items.length})
                    </button>
                    <button
                      type="button"
                      onClick={() => setItemStatusFilter('PLEASE_CHECK')}
                      className={`px-3 py-1.5 rounded-lg font-bold transition-colors flex items-center gap-1.5 ${
                        itemStatusFilter === 'PLEASE_CHECK'
                          ? 'bg-amber-600 text-white shadow-xs ring-2 ring-amber-400/40'
                          : currentInvoice.items.some((i) => i.mapping_status === 'PLEASE_CHECK' || i.mapping_status === 'POSSIBLE_MATCH')
                          ? 'bg-amber-100/90 text-amber-900 hover:bg-amber-200 border border-amber-300 font-extrabold'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      <span>⚠ Needs Verification</span>
                      <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-200 text-amber-900 font-black">
                        {currentInvoice.items.filter((i) => i.mapping_status === 'PLEASE_CHECK' || i.mapping_status === 'POSSIBLE_MATCH').length}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setItemStatusFilter('VERIFIED')}
                      className={`px-3 py-1.5 rounded-lg font-bold transition-colors flex items-center gap-1.5 ${
                        itemStatusFilter === 'VERIFIED'
                          ? 'bg-emerald-700 text-white shadow-xs ring-2 ring-emerald-400/40'
                          : 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200/60'
                      }`}
                    >
                      <span>✓ Verified</span>
                      <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-200 text-emerald-900 font-black">
                        {currentInvoice.items.filter((i) => i.mapping_status === 'VERIFIED' || i.mapping_status === 'AUTO_MAPPED').length}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setItemStatusFilter('UNMATCHED')}
                      className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
                        itemStatusFilter === 'UNMATCHED'
                          ? 'bg-rose-600 text-white shadow-xs'
                          : 'bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200/60'
                      }`}
                    >
                      Unmatched ({currentInvoice.items.filter((i) => (i.mapping_status === 'UNMATCHED' || !i.matched_stock_item) && i.mapping_status !== 'VERIFIED' && i.mapping_status !== 'AUTO_MAPPED').length})
                    </button>
                    <button
                      type="button"
                      onClick={() => setItemStatusFilter('NEW_ITEM')}
                      className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
                        itemStatusFilter === 'NEW_ITEM'
                          ? 'bg-purple-600 text-white shadow-xs'
                          : 'bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200/60'
                      }`}
                    >
                      New Items ({currentInvoice.items.filter((i) => i.requires_item_creation || i.mapping_status === 'NEW_ITEM').length})
                    </button>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {/* PRD Addendum 1 Section 2.7: Amounts include GST Toggle */}
                    <button
                      type="button"
                      onClick={handleToggleTaxInclusiveMode}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-extrabold flex items-center gap-1.5 transition-all shadow-xs border ${
                        currentInvoice.tax_mode === 'inclusive'
                          ? 'bg-purple-600 text-white border-purple-700 ring-2 ring-purple-300'
                          : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                      }`}
                      title="Toggle whether invoice line amounts already include GST"
                    >
                      <span className={`w-2 h-2 rounded-full ${currentInvoice.tax_mode === 'inclusive' ? 'bg-white' : 'bg-slate-400'}`} />
                      <span>Amounts include GST</span>
                      <span className="text-[10px] opacity-80 uppercase font-mono">
                        ({currentInvoice.tax_mode === 'inclusive' ? 'ON' : 'OFF'})
                      </span>
                    </button>

                    {currentInvoice.items.some((i) => i.mapping_status === 'PLEASE_CHECK' || i.mapping_status === 'POSSIBLE_MATCH') && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleVerifyAllItems}
                        className="text-xs font-bold flex items-center gap-1.5 rounded-lg border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 shadow-xs flex-shrink-0"
                        title="Click to approve all items that need verification"
                      >
                        <Check className="w-3.5 h-3.5 text-emerald-600 stroke-[3]" />
                        Verify All ({currentInvoice.items.filter((i) => i.mapping_status === 'PLEASE_CHECK' || i.mapping_status === 'POSSIBLE_MATCH').length})
                      </Button>
                    )}

                    <div className="relative w-full sm:w-60">
                      <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                      <Input
                        value={itemQueryFilter}
                        onChange={(e) => setItemQueryFilter(e.target.value)}
                        placeholder="Search Sales Item / HSN..."
                        className="pl-8 text-xs h-8 rounded-lg"
                      />
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0 overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse min-w-[1220px]">
                  <thead>
                    <tr className="bg-slate-50/90 border-b border-slate-200 text-slate-600 uppercase text-[10px] tracking-wider font-extrabold">
                      <th className="py-3 px-3 w-10 text-center text-slate-400 font-mono">#</th>
                      <th className="py-3 px-3 min-w-[320px] lg:min-w-[360px]">Sales Item Name & Tally Mapping</th>
                      <th className="py-3 px-2.5 w-28 min-w-[105px] text-center">HSN/SAC</th>
                      <th className="py-3 px-2.5 w-28 min-w-[100px] text-right">Qty</th>
                      <th className="py-3 px-2 w-20 min-w-[80px] text-center" title="Extracted unit from the invoice">Inv UOM</th>
                      <th className="py-3 px-2 w-20 min-w-[80px] text-center" title="Tally master unit (Source of Truth)">Tally UOM</th>
                      <th className="py-3 px-2.5 w-32 min-w-[115px] text-right">Rate (₹)</th>
                      <th className="py-3 px-2.5 w-28 min-w-[100px] text-right" title="Discount Amount">Disc (₹)</th>
                      <th className="py-3 px-3 w-36 min-w-[130px] text-right">Taxable (₹)</th>
                      <th className="py-3 px-2.5 w-28 min-w-[110px] text-right">GST %</th>
                      <th className="py-3 px-3 w-36 min-w-[130px] text-right">Total (₹)</th>
                      <th className="py-3 px-2 w-10 text-center"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredItems.map((it) => {
                      const idx = it.originalIndex;
                      const gstRate =
                        Number(it.igst_rate || 0) > 0
                          ? Number(it.igst_rate)
                          : Number(it.cgst_rate || 0) + Number(it.sgst_rate || 0);

                      return (
                        <tr key={it.id || idx} className="hover:bg-slate-50/70 transition-colors border-b border-slate-100">
                          <td className="py-3 px-3 text-center text-slate-400 font-mono text-[11px]">
                            {idx + 1}
                          </td>
                          <td className="py-3 px-3">
                            <div className="space-y-1.5">
                              <div>
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-[10px] font-bold text-slate-400 block uppercase tracking-wider">Invoice Item:</span>
                                  <button
                                    type="button"
                                    onClick={() => handleOpenStockSearch(it.originalIndex !== undefined ? it.originalIndex : idx)}
                                    className="text-[10px] font-bold text-indigo-700 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100 border border-indigo-300 rounded px-2 py-0.5 flex items-center gap-1 shadow-xs transition-colors"
                                    title="Search and select from uploaded stock items"
                                  >
                                    <Search className="w-3 h-3 text-indigo-600" />
                                    <span>Search Stock Items</span>
                                  </button>
                                </div>
                                <input
                                  type="text"
                                  value={it.item_name}
                                  onChange={(e) => handleLineItemChange(idx, 'item_name', e.target.value)}
                                  placeholder="Item Name"
                                  title={it.item_name}
                                  className="w-full min-w-[280px] font-bold text-slate-900 bg-white border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-3 py-2 text-xs sm:text-sm transition-all shadow-xs outline-none"
                                />
                                {(Boolean(it.mrp && Number(it.mrp) > 0) || Boolean(it.free_qty && Number(it.free_qty) > 0)) && (
                                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                    {it.mrp && Number(it.mrp) > 0 && (
                                      <span className="text-[9.5px] font-semibold text-blue-800 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded font-mono shadow-2xs">
                                        MRP: ₹{Number(it.mrp).toFixed(2)}
                                      </span>
                                    )}
                                    {it.free_qty && Number(it.free_qty) > 0 && (
                                      <span className="text-[9.5px] font-semibold text-indigo-800 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded shadow-2xs">
                                        Free: {Number(it.free_qty)}
                                      </span>
                                    )}
                                  </div>
                                )}

                                {/* Dual Quantity Available Pill (PRD §1-11) */}
                                {it.has_dual_qty && it.quantity_option_a && it.quantity_option_b && it.quantity_option_a !== it.quantity_option_b && (
                                  <div className="pt-1 flex items-center gap-1.5 flex-wrap">
                                    <span className="text-[9.5px] font-extrabold text-indigo-800 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-md inline-flex items-center gap-1 shadow-2xs">
                                      <ArrowUpDown className="w-2.5 h-2.5 text-indigo-600" />
                                      Dual Quantity:
                                      <span className={it.selected_qty_option === 'A' || !it.selected_qty_option ? 'font-black text-indigo-900 underline' : 'opacity-70'}>
                                        Option A ({it.quantity_option_a} {it.uom_option_a})
                                      </span>
                                      <span>|</span>
                                      <span className={it.selected_qty_option === 'B' ? 'font-black text-indigo-900 underline' : 'opacity-70'}>
                                        Option B ({it.quantity_option_b} {it.uom_option_b})
                                      </span>
                                    </span>
                                  </div>
                                )}

                                {/* PRD Section 13: Needs review & Reconstructed Badges */}
                                {(it.needs_review || it.is_reconstructed) && (
                                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                    {it.needs_review && (
                                      <span
                                        className="text-[9.5px] font-extrabold text-amber-800 bg-amber-100 border border-amber-300 px-2 py-0.5 rounded-md inline-flex items-center gap-1 shadow-2xs"
                                        title={it.review_reason || 'Math check or rate mismatch requires review'}
                                      >
                                        <AlertTriangle className="w-2.5 h-2.5 text-amber-600" />
                                        Needs review
                                      </span>
                                    )}
                                    {it.is_reconstructed && (
                                      <span
                                        className="text-[9.5px] font-extrabold text-sky-800 bg-sky-100 border border-sky-300 px-2 py-0.5 rounded-md inline-flex items-center gap-1 shadow-2xs"
                                        title="Quantity or rate was reconstructed from printed line amount"
                                      >
                                        <Sparkles className="w-2.5 h-2.5 text-sky-600" />
                                        Reconstructed
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>

                              {/* Mapping Status & Suggestion Bar */}
                              <div className="flex flex-wrap items-center gap-2 pt-0.5">
                                {it.matched_stock_item ? (
                                  <div className="flex flex-wrap items-center gap-1.5">
                                    <span className="text-[10px] text-emerald-800 font-semibold bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200 flex items-center gap-1 shadow-xs">
                                      <Check className="w-3 h-3 text-emerald-600" />
                                      Mapped: <span className="font-bold">{it.matched_stock_item}</span>
                                    </span>

                                    <button
                                      type="button"
                                      onClick={() => handleOpenStockSearch(it.originalIndex !== undefined ? it.originalIndex : idx)}
                                      className="text-[9.5px] font-extrabold text-indigo-800 hover:text-indigo-950 bg-indigo-50 hover:bg-indigo-100 border border-indigo-300 rounded px-2 py-0.5 flex items-center gap-1 shadow-xs transition-colors"
                                      title="Search uploaded stock items to change this mapping"
                                    >
                                      <Search className="w-2.5 h-2.5 text-indigo-600" />
                                      <span>Change</span>
                                    </button>

                                    {it.mapping_status === 'VERIFIED' ? (
                                      <span className="text-emerald-800 bg-emerald-100 border border-emerald-300 px-2 py-0.5 rounded-md text-[9px] font-bold flex items-center gap-1 shadow-xs">
                                        ✓ Verified
                                        <button
                                          type="button"
                                          onClick={() => handleVerifyItem(it.originalIndex !== undefined ? it.originalIndex : idx)}
                                          className="ml-1 text-[8.5px] text-slate-500 hover:text-slate-800 underline font-normal"
                                          title="Undo verification"
                                        >
                                          (undo)
                                        </button>
                                      </span>
                                    ) : it.mapping_status === 'PLEASE_CHECK' || it.mapping_status === 'POSSIBLE_MATCH' ? (
                                      <div className="flex items-center gap-1.5">
                                        <span className="text-amber-800 bg-amber-100 border border-amber-300 px-2 py-0.5 rounded-md text-[9px] font-extrabold flex items-center gap-1 shadow-xs">
                                          ⚠ Please Verify
                                        </span>
                                        <button
                                          type="button"
                                          onClick={() => handleVerifyItem(it.originalIndex !== undefined ? it.originalIndex : idx)}
                                          className="px-2.5 py-0.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[9.5px] font-extrabold flex items-center gap-1 shadow-xs transition-colors"
                                          title="Click to approve and mark this item as verified"
                                        >
                                          <Check className="w-3 h-3 stroke-[3]" />
                                          Verify
                                        </button>
                                      </div>
                                    ) : (
                                      <span className="text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded text-[9px] font-bold">
                                        ✓ Auto-Mapped
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <div className="flex flex-wrap items-center gap-1.5">
                                    <span className="text-[10px] text-purple-700 bg-purple-50 px-2 py-0.5 rounded-md border border-purple-200 font-semibold shadow-xs">
                                      ➕ New Stock Item
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => handleOpenStockSearch(it.originalIndex !== undefined ? it.originalIndex : idx)}
                                      className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-[10px] font-extrabold flex items-center gap-1.5 shadow-xs transition-colors"
                                      title="Search and select from uploaded stock items"
                                    >
                                      <Search className="w-3 h-3" />
                                      <span>Search Stock Items</span>
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleVerifyItem(it.originalIndex !== undefined ? it.originalIndex : idx)}
                                      className="px-2 py-0.5 bg-slate-100 hover:bg-emerald-50 text-slate-700 hover:text-emerald-800 border border-slate-300 hover:border-emerald-300 rounded text-[9.5px] font-bold flex items-center gap-1 shadow-xs"
                                      title="Mark verified as new item"
                                    >
                                      <Check className="w-3 h-3 text-emerald-600" />
                                      Verify as is
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setTargetItemIdxForMapping(idx);
                                        setNewItemData({
                                          name: it.item_name,
                                          hsn: it.hsn_sac || '',
                                          uom: it.uom || 'NOS',
                                          group: 'Primary',
                                          gst_rate: gstRate || 18,
                                        });
                                        setIsNewItemModalOpen(true);
                                      }}
                                      className="text-[10px] text-indigo-700 hover:text-indigo-800 hover:underline font-bold bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-md shadow-xs"
                                    >
                                      + Create in Masters
                                    </button>
                                  </div>
                                )}

                                {/* Suggestions if available and not yet auto-confirmed */}
                                {it.match_suggestions && it.match_suggestions.length > 0 && !it.matched_stock_item && (
                                  <div className="flex items-center gap-1">
                                    <span className="text-[10px] text-slate-400 font-medium">Suggested:</span>
                                    {it.match_suggestions.slice(0, 2).map((sug, sIdx) => (
                                      <button
                                        key={sIdx}
                                        type="button"
                                        onClick={() => handleAcceptItemSuggestion(idx, sug.name)}
                                        className="text-[10px] bg-slate-50 hover:bg-indigo-50 text-slate-700 hover:text-indigo-800 border border-slate-200 hover:border-indigo-300 px-2 py-0.5 rounded-md transition-colors flex items-center gap-1 font-semibold shadow-xs"
                                      >
                                        <span>{sug.name}</span>
                                        <span className="text-[9px] text-slate-400">({sug.similarity_score}%)</span>
                                        <span className="text-indigo-600 font-bold ml-0.5">[Accept]</span>
                                      </button>
                                    ))}
                                  </div>
                                )}

                                {/* Row-Level Validation Warnings (PRD 5.10) */}
                                {it.validation_errors && it.validation_errors.length > 0 && (
                                  <div className="space-y-1 pt-1 w-full">
                                    {it.validation_errors.map((vErr, vIdx) => (
                                      <div key={vIdx} className="text-[10px] text-amber-800 bg-amber-50/80 border border-amber-200 px-2.5 py-1 rounded-md flex items-center gap-1.5 font-medium shadow-xs">
                                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                                        <span>{vErr}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-2.5 min-w-[105px]">
                            <input
                              type="text"
                              value={it.hsn_sac || ''}
                              onChange={(e) => handleLineItemChange(idx, 'hsn_sac', e.target.value)}
                              placeholder="HSN"
                              title={`HSN/SAC: ${it.hsn_sac || ''}`}
                              className="w-full min-w-[95px] font-mono text-center font-semibold text-slate-800 bg-white border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-2 py-2 text-xs transition-all shadow-xs outline-none"
                            />
                          </td>
                          <td className="py-3 px-2.5 min-w-[100px] text-right">
                            <input
                              type="number"
                              step="0.01"
                              value={it.quantity}
                              onChange={(e) => handleLineItemChange(idx, 'quantity', parseFloat(e.target.value) || 0)}
                              title={`Quantity: ${it.quantity}`}
                              className="w-full min-w-[90px] text-right font-mono font-bold text-slate-900 bg-white border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-2.5 py-2 text-xs sm:text-sm transition-all shadow-xs outline-none"
                            />
                            {/* PRD §1-11 Dual Quantity Option Selector */}
                            {it.has_dual_qty && it.quantity_option_a && it.quantity_option_b && it.quantity_option_a !== it.quantity_option_b && (
                              <div className="mt-1.5 flex flex-col items-end gap-1">
                                <div className="inline-flex rounded-lg border border-indigo-300 p-0.5 bg-indigo-50/80 shadow-2xs">
                                  <button
                                    type="button"
                                    onClick={() => handleSelectDualQtyOption(it.originalIndex !== undefined ? it.originalIndex : idx, 'A')}
                                    className={`px-2 py-0.5 rounded font-extrabold transition-all text-[9.5px] ${
                                      it.selected_qty_option === 'A' || !it.selected_qty_option
                                        ? 'bg-indigo-600 text-white shadow-xs'
                                        : 'text-indigo-900 hover:bg-indigo-100'
                                    }`}
                                    title={`Select Option A: ${it.quantity_option_a} ${it.uom_option_a} (@ ₹${Number(it.rate_option_a ?? (Number(it.taxable_amount) / Number(it.quantity_option_a))).toFixed(2)})`}
                                  >
                                    {it.quantity_option_a} {it.uom_option_a}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleSelectDualQtyOption(it.originalIndex !== undefined ? it.originalIndex : idx, 'B')}
                                    className={`px-2 py-0.5 rounded font-extrabold transition-all text-[9.5px] ${
                                      it.selected_qty_option === 'B'
                                        ? 'bg-indigo-600 text-white shadow-xs'
                                        : 'text-indigo-900 hover:bg-indigo-100'
                                    }`}
                                    title={`Select Option B: ${it.quantity_option_b} ${it.uom_option_b} (@ ₹${Number(it.rate_option_b ?? (Number(it.taxable_amount) / Number(it.quantity_option_b))).toFixed(2)})`}
                                  >
                                    {it.quantity_option_b} {it.uom_option_b}
                                  </button>
                                </div>
                                <span className="text-[9px] text-slate-500 font-mono">
                                  Rate: ₹{Number(it.rate).toFixed(2)}/{it.uom}
                                </span>
                              </div>
                            )}
                            {it.pack_multiplier && Number(it.pack_multiplier) > 1 && !it.has_dual_qty && (
                              <div className="mt-1 text-right">
                                <span
                                  className="inline-block text-[9.5px] font-mono font-semibold text-indigo-800 bg-indigo-50 border border-indigo-300 rounded px-1.5 py-0.5 whitespace-nowrap shadow-2xs"
                                  title={`Invoice Qty: ${it.invoice_qty ?? Math.round(Number(it.quantity) / Number(it.pack_multiplier))} × Multiplier: ${it.pack_multiplier} = ${it.quantity}`}
                                >
                                  {it.invoice_qty ?? Math.round(Number(it.quantity) / Number(it.pack_multiplier))} × {it.pack_multiplier}
                                </span>
                              </div>
                            )}

                            {/* PRD Section 5.3 & 13: Pack-Size Conversion Toggle Button */}
                            {(it.can_convert_to_pieces || (it.pack_size_multiplier && Number(it.pack_size_multiplier) > 1)) && (
                              <div className="mt-1.5 flex items-center justify-end">
                                <button
                                  type="button"
                                  onClick={() => handleTogglePackConversion(it.originalIndex !== undefined ? it.originalIndex : idx)}
                                  className={`text-[9.5px] font-bold px-2 py-0.5 rounded-md border flex items-center gap-1 transition-colors shadow-2xs ${
                                    it.is_converted_to_pieces
                                      ? 'bg-purple-100 text-purple-900 border-purple-300 hover:bg-purple-200'
                                      : 'bg-indigo-50 text-indigo-800 border-indigo-200 hover:bg-indigo-100'
                                  }`}
                                  title={
                                    it.is_converted_to_pieces
                                      ? `Currently in pieces (${it.quantity} Pcs). Click to revert to bulk ${it.invoice_uom || 'cases'}`
                                      : `Convert to pieces: ${it.pack_size_multiplier}x pack size. Click to switch to pieces.`
                                  }
                                >
                                  <ArrowUpDown className="w-2.5 h-2.5" />
                                  {it.is_converted_to_pieces
                                    ? `Revert to Bulk (${it.invoice_uom || 'Case'})`
                                    : `Convert to Pieces (${it.pack_size_multiplier}x)`}
                                </button>
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-2 min-w-[80px]">
                            <input
                              type="text"
                              value={it.invoice_uom || it.uom || 'NOS'}
                              onChange={(e) => handleLineItemChange(idx, 'invoice_uom', e.target.value)}
                              placeholder="Inv Unit"
                              title={`Extracted invoice unit: ${it.invoice_uom || it.uom || 'NOS'}`}
                              className="w-full min-w-[70px] text-center uppercase font-mono font-semibold text-slate-700 bg-slate-50/70 border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-1.5 py-2 text-xs transition-all shadow-xs outline-none"
                            />
                          </td>
                          <td className="py-3 px-2 min-w-[80px]">
                            <input
                              type="text"
                              value={it.tally_uom || it.uom || 'NOS'}
                              onChange={(e) => {
                                handleLineItemChange(idx, 'tally_uom', e.target.value);
                                handleLineItemChange(idx, 'uom', e.target.value);
                              }}
                              placeholder="Tally Unit"
                              title={`Tally master unit: ${it.tally_uom || it.uom || 'NOS'}`}
                              className="w-full min-w-[70px] text-center uppercase font-mono font-bold text-indigo-800 bg-indigo-50/50 border border-indigo-300/80 hover:border-indigo-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-1.5 py-2 text-xs transition-all shadow-xs outline-none"
                            />
                          </td>
                          <td className="py-3 px-2.5 min-w-[115px] text-right">
                            <input
                              type="number"
                              step="0.01"
                              value={it.rate}
                              onChange={(e) => handleLineItemChange(idx, 'rate', parseFloat(e.target.value) || 0)}
                              title={`Rate: ₹${it.rate}`}
                              className="w-full min-w-[105px] text-right font-mono font-bold text-slate-900 bg-white border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-2.5 py-2 text-xs sm:text-sm transition-all shadow-xs outline-none"
                            />
                          </td>
                          <td className="py-3 px-2.5 min-w-[100px] text-right">
                            <input
                              type="number"
                              step="0.01"
                              value={it.discount ?? it.discount_amount ?? ''}
                              onChange={(e) => {
                                const val = parseFloat(e.target.value) || 0;
                                handleLineItemChange(idx, 'discount', val);
                                handleLineItemChange(idx, 'discount_amount', val);
                              }}
                              placeholder="0.00"
                              title={`Discount: ₹${it.discount ?? it.discount_amount ?? 0}`}
                              className="w-full min-w-[90px] text-right font-mono font-semibold text-slate-800 bg-white border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-2.5 py-2 text-xs transition-all shadow-xs outline-none"
                            />
                          </td>
                          <td className="py-3 px-3 min-w-[130px] text-right">
                            <input
                              type="number"
                              step="0.01"
                              value={it.taxable_amount || 0}
                              onChange={(e) => handleLineItemChange(idx, 'taxable_amount', parseFloat(e.target.value) || 0)}
                              title={`Taxable Value: ₹${Number(it.taxable_amount || 0).toFixed(2)}`}
                              className="w-full min-w-[115px] text-right font-mono font-bold text-slate-900 bg-slate-50/70 hover:bg-white border border-slate-200 hover:border-slate-300 focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-2.5 py-2 text-xs sm:text-sm transition-all shadow-xs outline-none"
                            />
                            {(it.is_tax_inclusive || currentInvoice.tax_mode === 'inclusive') && (
                              <span className="text-[9.5px] font-mono text-purple-700 font-semibold block text-right mt-0.5 whitespace-nowrap" title={`Printed line invoice amount including GST: ₹${Number(it.total_amount || 0).toFixed(2)}`}>
                                (Inv: ₹{Number(it.total_amount || 0).toFixed(2)})
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-2.5 min-w-[110px] text-right">
                            <div className="space-y-1">
                              <div className="flex items-center gap-1">
                                <input
                                  type="number"
                                  step="0.1"
                                  value={gstRate}
                                  onChange={(e) => {
                                    const val = parseFloat(e.target.value) || 0;
                                    if (Number(it.igst_rate) > 0 || Number(currentInvoice.igst_total) > 0) {
                                      handleLineItemChange(idx, 'igst_rate', val);
                                    } else {
                                      handleLineItemChange(idx, 'cgst_rate', val / 2);
                                      handleLineItemChange(idx, 'sgst_rate', val / 2);
                                    }
                                  }}
                                  title={`GST Rate: ${gstRate}%`}
                                  className="w-full min-w-[65px] text-right font-mono font-bold text-slate-800 bg-white border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-2 py-2 text-xs sm:text-sm transition-all shadow-xs outline-none"
                                />
                                <span className="text-[11px] font-bold text-slate-500">%</span>
                              </div>
                              {(Number(it.cgst_amount || 0) > 0 || Number(it.sgst_amount || 0) > 0 || Number(it.igst_amount || 0) > 0) && (
                                <div className="text-[9.5px] font-mono text-right whitespace-nowrap">
                                  {Number(it.igst_amount || 0) > 0 ? (
                                    <span className="text-purple-700 font-semibold" title={`IGST: ₹${Number(it.igst_amount).toFixed(2)}`}>
                                      IGST: ₹{Number(it.igst_amount).toFixed(2)}
                                    </span>
                                  ) : (
                                    <span title={`CGST: ₹${Number(it.cgst_amount || 0).toFixed(2)} + SGST: ₹${Number(it.sgst_amount || 0).toFixed(2)}`}>
                                      <span className="text-blue-700 font-semibold">C: ₹{Number(it.cgst_amount || 0).toFixed(2)}</span>
                                      <span className="text-slate-400 mx-0.5">+</span>
                                      <span className="text-blue-700 font-semibold">S: ₹{Number(it.sgst_amount || 0).toFixed(2)}</span>
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-3 min-w-[130px] text-right">
                            <div
                              className="w-full min-w-[115px] text-right font-mono font-extrabold text-emerald-700 bg-emerald-50/70 border border-emerald-200/80 rounded-lg px-2.5 py-2 text-xs sm:text-sm"
                              title={`Line Total Amount: ₹${Number(it.total_amount || 0).toFixed(2)}`}
                            >
                              ₹{Number(it.total_amount || 0).toFixed(2)}
                            </div>
                          </td>
                          <td className="py-3 px-2 text-center">
                            <button
                              type="button"
                              onClick={() => handleRemoveLineItem(idx)}
                              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                              title="Delete row"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                {/* Totals & Round-Off Box */}
                <div className="p-5 bg-gradient-to-br from-slate-50 via-slate-50/60 to-white border-t border-slate-200">
                  <div className="max-w-md ml-auto space-y-2.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-600 font-semibold">Taxable Subtotal:</span>
                      <span className="font-mono font-bold text-slate-900 text-sm">
                        ₹{Number(currentInvoice.taxable_total || 0).toFixed(2)}
                      </span>
                    </div>

                    {Number(currentInvoice.cgst_total || 0) > 0 && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 font-medium">CGST Total:</span>
                        <span className="font-mono font-bold text-blue-700">
                          ₹{Number(currentInvoice.cgst_total || 0).toFixed(2)}
                        </span>
                      </div>
                    )}

                    {Number(currentInvoice.sgst_total || 0) > 0 && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 font-medium">SGST Total:</span>
                        <span className="font-mono font-bold text-blue-700">
                          ₹{Number(currentInvoice.sgst_total || 0).toFixed(2)}
                        </span>
                      </div>
                    )}

                    {Number(currentInvoice.igst_total || 0) > 0 && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 font-medium">IGST Total:</span>
                        <span className="font-mono font-bold text-purple-700">
                          ₹{Number(currentInvoice.igst_total || 0).toFixed(2)}
                        </span>
                      </div>
                    )}

                    {/* Discount / Scheme Row */}
                    <div className="flex items-center justify-between pt-1">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-600 font-medium">Discount / Scheme:</span>
                        {Math.abs(Number(currentInvoice.grand_total || 0) - Number(currentInvoice.calculated_total || 0)) > 2.50 && (
                          <button
                            type="button"
                            onClick={handleApplyDiscountDifference}
                            className="px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-200 text-[10px] font-bold hover:bg-purple-100 transition-colors"
                            title="Auto-fill discount from difference between bill total and items"
                          >
                            Apply Diff
                          </button>
                        )}
                      </div>
                      <input
                        type="number"
                        step="0.01"
                        value={currentInvoice.discount_total || 0}
                        onChange={(e) =>
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            discount_total: parseFloat(e.target.value) || 0,
                          }))
                        }
                        className="w-36 sm:w-40 text-right font-mono text-xs sm:text-sm font-bold text-purple-700 bg-white border border-purple-200 hover:border-purple-300 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 rounded-lg px-3 py-1.5 shadow-xs outline-none"
                      />
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-600 font-medium">Round Off:</span>
                        <button
                          type="button"
                          onClick={handleAutoBalanceRoundOff}
                          className="px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 text-[10px] font-bold hover:bg-indigo-100 transition-colors"
                        >
                          Auto-Balance
                        </button>
                      </div>
                      <input
                        type="number"
                        step="0.01"
                        value={currentInvoice.round_off}
                        onChange={(e) =>
                          updateCurrentInvoice((inv) => ({
                            ...inv,
                            round_off: parseFloat(e.target.value) || 0,
                          }))
                        }
                        className="w-36 sm:w-40 text-right font-mono text-xs sm:text-sm font-bold bg-white border border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-lg px-3 py-1.5 shadow-xs outline-none"
                      />
                    </div>

                    <div className="border-t border-slate-200 pt-2.5 flex items-center justify-between font-bold">
                      <span className="text-slate-600">Calculated Sum:</span>
                      <span className="font-mono font-bold text-slate-900">
                        ₹{Number(currentInvoice.calculated_total || 0).toFixed(2)}
                      </span>
                    </div>

                    <div className="border-t-2 border-slate-300 pt-2.5 flex items-center justify-between font-extrabold text-sm">
                      <span className="text-slate-900 font-black">Invoice Grand Total:</span>
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-600 font-bold">₹</span>
                        <input
                          type="number"
                          step="0.01"
                          value={currentInvoice.grand_total}
                          onChange={(e) =>
                            updateCurrentInvoice((inv) => ({
                              ...inv,
                              grand_total: parseFloat(e.target.value) || 0,
                            }))
                          }
                          className="w-36 sm:w-44 text-right font-mono font-black text-slate-900 bg-white border-2 border-indigo-500 rounded-lg px-3 py-1.5 text-sm sm:text-base shadow-xs outline-none"
                        />
                      </div>
                    </div>

                    {/* PRD Totals Check Strip (Section 5.10) */}
                    <div className="pt-2">
                      {Math.abs(Number(currentInvoice.grand_total || 0) - Number(currentInvoice.calculated_total || 0)) <= 0.05 ? (
                        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center justify-between shadow-xs">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                            <span>Totals Reconciled: Sum matches invoice grand total (Net delta ₹0.00).</span>
                          </div>
                          <span className="text-[10px] font-mono text-emerald-700 font-bold bg-emerald-100 px-2 py-0.5 rounded shadow-xs">
                            ✓ Balanced
                          </span>
                        </div>
                      ) : (
                        <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs font-semibold flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-xs">
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                            <span>Discrepancy: Calculated ₹{Number(currentInvoice.calculated_total || 0).toFixed(2)} vs Invoice ₹{Number(currentInvoice.grand_total || 0).toFixed(2)} (Delta: ₹{Math.abs(Number(currentInvoice.grand_total || 0) - Number(currentInvoice.calculated_total || 0)).toFixed(2)})</span>
                          </div>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <button
                              type="button"
                              onClick={handleApplyDiscountDifference}
                              className="bg-purple-600 hover:bg-purple-700 text-white px-2.5 py-1 rounded-lg text-xs font-bold shadow-xs transition-colors"
                              title="Apply this difference as invoice discount"
                            >
                              Apply as Discount (₹{Math.abs(Number(currentInvoice.grand_total || 0) - Number(currentInvoice.calculated_total || 0)).toFixed(2)})
                            </button>
                            <button
                              type="button"
                              onClick={handleSyncBillTotalToItems}
                              className="bg-sky-600 hover:bg-sky-700 text-white px-2.5 py-1 rounded-lg text-xs font-bold shadow-xs transition-colors"
                              title="Set invoice grand total to match items sum"
                            >
                              Sync Bill Total
                            </button>
                            <button
                              type="button"
                              onClick={handleAutoBalanceRoundOff}
                              className="bg-amber-600 hover:bg-amber-700 text-white px-2.5 py-1 rounded-lg text-xs font-bold shadow-xs transition-colors"
                            >
                              Auto-Balance
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* PRD Addendum 2: Discount Pattern Badge */}
                    {currentInvoice.discount_pattern && (
                      <div className="pt-2">
                        <div className="p-3 rounded-xl bg-purple-50/90 border border-purple-200 text-purple-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shadow-xs">
                          <div className="flex items-center gap-2">
                            <Tag className="w-4 h-4 text-purple-600 flex-shrink-0" />
                            <span className="font-bold">
                              Discount Pattern: {currentInvoice.discount_pattern.replace(/_/g, ' ')}
                            </span>
                          </div>
                          {currentInvoice.discount_pattern_note && (
                            <span className="text-[11px] text-purple-700 font-medium">
                              {currentInvoice.discount_pattern_note}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* PRD Review Confirmation Gate (Section 5.10) */}
            {((currentInvoice.errors && currentInvoice.errors.length > 0) || (currentInvoice.validation_violations && currentInvoice.validation_violations.some(v => v.severity === 'ERROR'))) && (
              <div className="p-4 bg-amber-50/90 border border-amber-300 rounded-2xl flex items-center justify-between gap-3 shadow-card">
                <div className="flex items-center gap-2.5">
                  <input
                    type="checkbox"
                    id="review-confirmed-sales"
                    checked={isReviewConfirmed}
                    onChange={(e) => setIsReviewConfirmed(e.target.checked)}
                    className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                  />
                  <label htmlFor="review-confirmed-sales" className="text-xs font-bold text-amber-950 cursor-pointer">
                    I have checked and confirmed these values (Allow XML generation with flagged warnings/discrepancies)
                  </label>
                </div>
                <span className="text-[10px] text-amber-800 font-bold bg-amber-100 px-2.5 py-1 rounded-full border border-amber-200">
                  Confirmation Gate
                </span>
              </div>
            )}

            {/* Action Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-200">
              <Button variant="outline" size="md" onClick={() => setCurrentStep(1)} className="text-xs font-bold rounded-xl shadow-xs">
                <ArrowLeft className="w-3.5 h-3.5 mr-1" />
                Upload More Files
              </Button>

              <div className="flex items-center gap-3 w-full sm:w-auto">
                <Button
                  variant="outline"
                  size="md"
                  onClick={handlePreviewXml}
                  disabled={isProcessing}
                  className="w-full sm:w-auto text-xs font-bold flex items-center gap-1.5 rounded-xl shadow-xs"
                >
                  <Eye className="w-3.5 h-3.5 text-slate-500" />
                  Preview Sales Tally XML
                </Button>

                <Button
                  variant="primary"
                  size="md"
                  onClick={handleDownloadXml}
                  disabled={isDownloading}
                  className="w-full sm:w-auto text-xs font-bold flex items-center gap-2 px-6 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-card transition-all"
                >
                  {isDownloading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Generating Sales XML...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4" />
                      Download Sales Tally XML (One-File Import)
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: COMPLETED SUCCESS SCREEN */}
        {currentStep === 3 && (
          <Card className="border-slate-200 shadow-sm bg-white text-center py-12 px-6 max-w-2xl mx-auto">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-10 h-10" />
            </div>
            <h2 className="text-xl font-extrabold text-navy-900">
              Sales Tally XML Successfully Generated!
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 mt-2 max-w-md mx-auto">
              Your Sales bills have been exported as a single, self-contained Tally XML file with complete stock items, groups, units, and customer ledgers.
            </p>

            <div className="mt-6 text-left bg-emerald-50/70 rounded-xl p-4 border border-emerald-200 text-xs space-y-2">
              <h4 className="font-extrabold text-emerald-950 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                One-File Import Instructions (Tally Prime / ERP 9):
              </h4>
              <p className="text-[11px] text-emerald-800">
                Your downloaded XML file contains both your vouchers and any missing stock items, units, and customer ledgers.
                You only need to import this single file!
              </p>
              <ol className="list-decimal list-inside space-y-1 text-slate-700 pl-1 font-medium">
                <li>Open your company in Tally Prime.</li>
                <li>Press <kbd className="px-1.5 py-0.5 rounded bg-white border border-slate-200 font-mono text-[11px]">Alt + O</kbd> (Import Menu).</li>
                <li>Select <strong>Transactions</strong> (or <strong>All Masters</strong>).</li>
                <li>Select your downloaded XML file and press Enter.</li>
              </ol>
            </div>

            {/* OPTIONAL: DOWNLOAD STOCK ITEMS MASTER XML */}
            <div className="mt-4 p-4 rounded-xl bg-purple-50/80 border border-purple-200 text-left text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
              <div className="flex items-center gap-2.5">
                <Package className="w-5 h-5 text-purple-600 flex-shrink-0" />
                <div>
                  <p className="font-extrabold text-purple-950">Need Stock Items Created in Tally First?</p>
                  <p className="text-[11px] text-purple-700">Import Master XML before sales vouchers via Alt + O &rarr; Import &rarr; Masters.</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {currentInvoice && currentInvoice.items.some((it) => it.requires_item_creation || it.mapping_status === 'NEW_ITEM' || !it.matched_stock_item) && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDownloadStockItemsMasterXml(true)}
                    disabled={isDownloadingItemsXml}
                    className="bg-white hover:bg-amber-100 text-amber-950 border-amber-300 font-extrabold text-xs flex items-center gap-1.5 shadow-xs whitespace-nowrap"
                  >
                    <Download className="w-3.5 h-3.5 text-amber-700" />
                    {isDownloadingItemsXml ? 'Generating...' : 'Download New Items XML'}
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownloadStockItemsMasterXml(false)}
                  disabled={isDownloadingItemsXml}
                  className="bg-white hover:bg-purple-100 text-purple-900 border-purple-300 font-bold text-xs flex items-center gap-1.5 shadow-xs whitespace-nowrap"
                >
                  <Download className="w-3.5 h-3.5 text-purple-700" />
                  {isDownloadingItemsXml ? 'Generating...' : 'Download All Stock Items XML'}
                </Button>
              </div>
            </div>

            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button variant="primary" size="md" onClick={handleDownloadXml} className="w-full sm:w-auto font-bold flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white">
                <Download className="w-4 h-4" />
                Download Again
              </Button>
              <Button
                variant="outline"
                size="md"
                onClick={handleResetSession}
                className="w-full sm:w-auto font-semibold"
              >
                Convert Another Batch
              </Button>
            </div>
          </Card>
        )}
      </div>

      {/* MODAL: STOCK ITEMS MANAGER */}
      <Modal
        isOpen={isStockModalOpen}
        onClose={() => setIsStockModalOpen(false)}
        title="Imported Tally Stock Items"
        size="lg"
      >
        <div className="space-y-4 text-xs">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div>
              <p className="font-bold text-navy-900">Upload Tally Stock Item Master File</p>
              <p className="text-slate-500 text-[11px]">Accepts Tally XML (conforming to stock items list sample.xml), JSON, or HTML.</p>
            </div>
            <label className="cursor-pointer bg-brand-600 hover:bg-brand-700 text-white font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors">
              <UploadCloud className="w-3.5 h-3.5" />
              Upload Stock XML/JSON
              <input type="file" accept=".xml,.json,.htm,.html" className="hidden" onChange={handleStockFileUpload} />
            </label>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <Input
              value={stockItemSearch}
              onChange={(e) => setStockItemSearch(e.target.value)}
              placeholder="Search stock item name or HSN..."
              className="pl-8 text-xs"
            />
          </div>

          <div className="max-h-72 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-xl">
            {stockItems
              .filter((it) => !stockItemSearch || it.name.toLowerCase().includes(stockItemSearch.toLowerCase()) || (it.hsn_code && it.hsn_code.includes(stockItemSearch)))
              .slice(0, 50)
              .map((it, idx) => (
                <div key={idx} className="p-2.5 hover:bg-slate-50 flex items-center justify-between">
                  <div>
                    <p className="font-bold text-navy-900">{it.name}</p>
                    <p className="text-[10px] text-slate-500">
                      Group: {it.parent || 'Primary'} • UOM: {it.base_units} {it.hsn_code ? `• HSN: ${it.hsn_code}` : ''}
                    </p>
                  </div>
                  <Badge variant="neutral" size="sm">
                    {it.source_format || 'TALLY'}
                  </Badge>
                </div>
              ))}
            {stockItems.length === 0 && (
              <p className="text-center py-6 text-slate-400">No stock items imported yet. Upload your Tally XML above.</p>
            )}
          </div>
        </div>
      </Modal>

      {/* MODAL: CUSTOMER LEDGER MANAGER */}
      <Modal
        isOpen={isLedgerModalOpen}
        onClose={() => setIsLedgerModalOpen(false)}
        title="Imported Customer Tally Ledgers"
        size="lg"
      >
        <div className="space-y-4 text-xs">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div>
              <p className="font-bold text-navy-900">Upload Tally Ledger Master File</p>
              <p className="text-slate-500 text-[11px]">Accepts Tally Master XML (ledgers sample.xml), JSON, or HTML.</p>
            </div>
            <label className="cursor-pointer bg-blue-600 hover:bg-blue-700 text-white font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors">
              <UploadCloud className="w-3.5 h-3.5" />
              Upload Ledger XML
              <input type="file" accept=".xml,.json,.htm,.html" className="hidden" onChange={handleLedgerFileUpload} />
            </label>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <Input
              value={ledgerSearch}
              onChange={(e) => setLedgerSearch(e.target.value)}
              placeholder="Search ledger name or GSTIN..."
              className="pl-8 text-xs"
            />
          </div>

          <div className="max-h-72 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-xl">
            {ledgers
              .filter((l) => !ledgerSearch || l.name.toLowerCase().includes(ledgerSearch.toLowerCase()) || (l.party_gstin && l.party_gstin.includes(ledgerSearch)))
              .slice(0, 50)
              .map((l, idx) => (
                <div key={idx} className="p-2.5 hover:bg-slate-50 flex items-center justify-between">
                  <div>
                    <p className="font-bold text-navy-900">{l.name}</p>
                    <p className="text-[10px] text-slate-500">
                      Group: {l.group || 'Sundry Debtors'} {l.party_gstin ? `• GSTIN: ${l.party_gstin}` : ''}
                    </p>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">{l.source_format}</span>
                </div>
              ))}
            {ledgers.length === 0 && (
              <p className="text-center py-6 text-slate-400">No ledgers imported yet. Upload your Tally XML above.</p>
            )}
          </div>
        </div>
      </Modal>

      {/* SMART CREATE STOCK ITEM MASTER MODAL (PRD Addendum 5) */}
      <CreateStockItemMasterModal
        isOpen={isNewItemModalOpen}
        onClose={() => setIsNewItemModalOpen(false)}
        item={targetItemIdxForMapping !== null && currentInvoice ? currentInvoice.items[targetItemIdxForMapping] : null}
        initialInvoiceValues={targetItemIdxForMapping !== null && currentInvoice ? {
          item_name: currentInvoice.items[targetItemIdxForMapping].item_name,
          hsn_sac: currentInvoice.items[targetItemIdxForMapping].hsn_sac,
          uom: currentInvoice.items[targetItemIdxForMapping].uom,
          gst_rate: currentInvoice.items[targetItemIdxForMapping].gst_rate,
        } : null}
        existingStockItems={stockItems}
        allNewItems={allNewItems}
        currentNewItemIndex={currentNewItemPos}
        isInterstate={currentInvoice ? (currentInvoice.igst_total > 0 || Boolean(currentInvoice.supplier.state && currentInvoice.buyer.state && currentInvoice.supplier.state !== currentInvoice.buyer.state)) : false}
        onSaveMaster={handleSaveStockItemMaster}
        onUseExistingItem={handleUseExistingStockItem}
      />

      {/* SMART CREATE CUSTOMER LEDGER MASTER MODAL (PRD Addendum 6) */}
      <CreateLedgerMasterModal
        isOpen={isNewLedgerModalOpen}
        onClose={() => setIsNewLedgerModalOpen(false)}
        party={currentInvoice ? {
          name: currentInvoice.buyer.name,
          alias: (currentInvoice.buyer as any).alias,
          gstin: currentInvoice.buyer.gstin,
          pan: (currentInvoice.buyer as any).pan,
          address: currentInvoice.buyer.address,
          state: currentInvoice.buyer.state,
          pincode: (currentInvoice.buyer as any).pincode,
          country: (currentInvoice.buyer as any).country,
          registration_type: (currentInvoice.buyer as any).registration_type,
          parent_group: 'Sundry Debtors',
          saved_draft_version: (currentInvoice.buyer as any).saved_draft_version,
        } : null}
        initialInvoiceValues={currentInvoice ? {
          name: currentInvoice.buyer.name,
          gstin: currentInvoice.buyer.gstin,
          state: currentInvoice.buyer.state,
          address: currentInvoice.buyer.address,
        } : null}
        defaultParentGroup="Sundry Debtors"
        onSaveMaster={handleSaveLedgerMaster}
      />

      {/* MODAL: XML PREVIEW */}
      <Modal
        isOpen={isXmlModalOpen}
        onClose={() => setIsXmlModalOpen(false)}
        title="Sales Tally XML Preview & Verification"
        size="lg"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Badge variant={xmlResult?.is_valid ? 'success' : 'danger'} size="sm">
              {xmlResult?.is_valid ? 'XML Schema Valid & Balanced' : 'Validation Errors'}
            </Badge>
            <Button variant="outline" size="sm" onClick={copyToClipboard} className="text-xs flex items-center gap-1 font-semibold">
              {copiedXml ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedXml ? 'Copied!' : 'Copy XML'}
            </Button>
          </div>

          <pre className="bg-navy-950 text-slate-200 p-4 rounded-xl text-[11px] font-mono overflow-x-auto max-h-96 leading-relaxed select-all">
            {xmlResult?.xml_content || 'Generating Sales XML...'}
          </pre>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setIsXmlModalOpen(false)}>
              Close
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setIsXmlModalOpen(false);
                handleDownloadXml();
              }}
              className="flex items-center gap-1.5 font-bold bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              <Download className="w-3.5 h-3.5" />
              Download Sales XML (One-File Import)
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL: SETTINGS */}
      <Modal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        title="Sales Tally Ledger Settings"
        size="md"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-600">Default accounting ledgers allocated to Sales vouchers in Tally.</p>
          <div>
            <label className="block font-semibold text-slate-700 mb-1">SALES LEDGER</label>
            <Input
              value={ledgerMapping.sales_ledger}
              onChange={(e) => setLedgerMapping({ ...ledgerMapping, sales_ledger: e.target.value })}
              className="text-xs font-semibold"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">CGST Ledger</label>
              <Input
                value={ledgerMapping.cgst_ledger}
                onChange={(e) => setLedgerMapping({ ...ledgerMapping, cgst_ledger: e.target.value })}
                className="text-xs"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">SGST Ledger</label>
              <Input
                value={ledgerMapping.sgst_ledger}
                onChange={(e) => setLedgerMapping({ ...ledgerMapping, sgst_ledger: e.target.value })}
                className="text-xs"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">IGST Ledger</label>
              <Input
                value={ledgerMapping.igst_ledger}
                onChange={(e) => setLedgerMapping({ ...ledgerMapping, igst_ledger: e.target.value })}
                className="text-xs"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Round Off Ledger</label>
              <Input
                value={ledgerMapping.round_off_ledger}
                onChange={(e) => setLedgerMapping({ ...ledgerMapping, round_off_ledger: e.target.value })}
                className="text-xs"
              />
            </div>
          </div>
          <div className="flex justify-end pt-3">
            <Button variant="primary" size="sm" onClick={() => setIsSettingsModalOpen(false)}>
              Save Settings
            </Button>
          </div>
        </div>
      </Modal>

      {/* DEDICATED SEARCH & SELECT MODAL OVER UPLOADED STOCK ITEMS */}
      {isStockSearchModalOpen && activeStockSearchIdx !== null && currentInvoice && currentInvoice.items[activeStockSearchIdx] && (
        <StockItemSearchModal
          isOpen={isStockSearchModalOpen}
          onClose={() => {
            setIsStockSearchModalOpen(false);
            setActiveStockSearchIdx(null);
          }}
          itemIndex={activeStockSearchIdx}
          currentInvoiceItemName={currentInvoice.items[activeStockSearchIdx].item_name}
          currentMatchedStockItem={currentInvoice.items[activeStockSearchIdx].matched_stock_item}
          stockItems={stockItems}
          onSelectStockItem={handleSelectStockItemFromModal}
          onCreateNewItem={(initialName, idx) => {
            setTargetItemIdxForMapping(idx);
            const line = currentInvoice.items[idx];
            const gst = line ? (Number(line.igst_rate || 0) > 0 ? Number(line.igst_rate) : (Number(line.cgst_rate || 0) + Number(line.sgst_rate || 0))) : 18;
            setNewItemData({
              name: initialName,
              hsn: line?.hsn_sac || '',
              uom: line?.uom || 'NOS',
              group: 'Primary',
              gst_rate: gst || 18,
            });
            setIsNewItemModalOpen(true);
          }}
        />
      )}

      {/* PROFESSIONAL IN-APP CONFIRMATION DIALOG */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog((prev) => ({ ...prev, isOpen: false }))}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText={confirmDialog.confirmText}
        cancelText={confirmDialog.cancelText}
        variant={confirmDialog.variant}
      />

      {/* PROFESSIONAL IN-APP ALERT DIALOG */}
      <AlertDialog
        isOpen={alertDialog.isOpen}
        onClose={() => setAlertDialog((prev) => ({ ...prev, isOpen: false }))}
        title={alertDialog.title}
        message={alertDialog.message}
        buttonText={alertDialog.buttonText}
        variant={alertDialog.variant}
      />
    </div>
  );
}
