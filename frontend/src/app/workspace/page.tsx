'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Layers,
  FileCode,
  Download,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Search,
  Filter,
  ArrowRight,
  Plus,
  RefreshCw,
  Calendar,
  Building2,
  FileText,
  RotateCcw,
  Sparkles,
  ArrowLeft,
  ChevronRight,
  Tag
} from 'lucide-react';
import { GoldTick } from '@/components/ui/GoldTick';
import { useAuth } from '@/components/auth/AuthProvider';
import { getUserConversions, ConversionJobSummary } from '@/lib/api';

export default function BatchWorkspacePage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading, isStaff, isAdmin, isGold } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conversions, setConversions] = useState<ConversionJobSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'COMPLETED' | 'NEEDS_REVIEW' | 'PARTIAL'>('ALL');
  const [selectedBatch, setSelectedBatch] = useState<ConversionJobSummary | null>(null);

  const isAuthorized = isAdmin || isStaff;

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getUserConversions();
      setConversions(data || []);
      if (data && data.length > 0) {
        setSelectedBatch(data[0]);
      } else {
        setSelectedBatch(null);
      }
    } catch (err: any) {
      console.warn('Error fetching batch conversions:', err);
      setError(err.message || 'Failed to load workspace batches. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading) {
      if (!isAuthenticated) {
        router.replace('/login?redirect=/workspace');
      } else {
        loadData();
      }
    }
  }, [authLoading, isAuthenticated, router]);

  // Filter batches based on real user input
  const filteredBatches = conversions.filter((b) => {
    if (statusFilter !== 'ALL') {
      if (statusFilter === 'COMPLETED' && b.status !== 'COMPLETED') return false;
      if (statusFilter === 'NEEDS_REVIEW' && b.status !== 'NEEDS_REVIEW') return false;
      if (statusFilter === 'PARTIAL' && !b.is_partial_conversion && b.status !== 'PARTIALLY_COMPLETED') return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (b.file_name || '').toLowerCase().includes(q);
      const matchBank = (b.bank_name || '').toLowerCase().includes(q);
      const matchId = (b.id || '').toLowerCase().includes(q);
      if (!matchName && !matchBank && !matchId) return false;
    }
    return true;
  });

  // Dynamically compute real stats from database records (PRD Part 4.2.3: Zero Constants)
  const totalBatches = conversions.length;
  const totalPages = conversions.reduce((sum, b) => sum + (b.pages_processed || b.page_count || 0), 0);
  const totalTransactions = conversions.reduce((sum, b) => sum + (b.transaction_count || 0), 0);
  const completedCount = conversions.filter((b) => b.status === 'COMPLETED').length;
  const successRate = totalBatches > 0 ? Math.round((completedCount / totalBatches) * 100) : 100;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top SaaS Workspace Bar */}
      <div className="bg-slate-900 border-b border-slate-800 px-4 sm:px-6 py-3 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="p-1.5 -ml-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Return to home"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex items-center gap-2.5">
            <span className="p-1.5 rounded-lg bg-amber-400/10 border border-amber-400/30 text-amber-400">
              <Layers className="w-4 h-4" />
            </span>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm sm:text-base tracking-tight text-white">
                BATCH WORKSPACE
              </span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-400/10 text-amber-300 border border-amber-400/30 flex items-center gap-1">
                <GoldTick size="sm" />
                {isAdmin ? 'Admin View' : 'Staff SaaS'}
              </span>
            </div>
          </div>
        </div>

        {/* Quick Converter Actions */}
        <div className="flex items-center gap-2">
          <Link
            href="/sales"
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs border border-slate-700 transition-colors flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5 text-blue-400" />
            <span className="hidden sm:inline">New Sales Batch</span>
          </Link>
          <Link
            href="/purchase"
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs border border-slate-700 transition-colors flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden sm:inline">New Purchase Batch</span>
          </Link>
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white border border-slate-700 transition-colors cursor-pointer"
            title="Refresh workspace batches"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Non-Staff Upgrade Prompt (If regular user visits workspace) */}
      {!isAuthorized && !authLoading && (
        <div className="bg-gradient-to-r from-amber-950/80 via-slate-900 to-amber-950/80 border-b border-amber-600/30 px-6 py-3 text-xs text-amber-200 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>
              <strong>Staff Tier Feature:</strong> Batch consolidation, dual UOM, and multi-file processing are fully unlocked with Staff Membership.
            </span>
          </div>
          <Link
            href="/checkout"
            className="px-3 py-1 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 font-black text-xs shadow-xs"
          >
            Upgrade to Gold (₹499)
          </Link>
        </div>
      )}

      {/* Main Workspace Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Real Dynamic Stats Cards (Part 4.2.3: Computed with real count/sum queries) */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Total Batches
            </span>
            {loading ? (
              <div className="h-7 w-16 bg-slate-800 animate-pulse rounded my-1" />
            ) : (
              <span className="text-2xl font-black text-white tracking-tight">{totalBatches}</span>
            )}
            <p className="text-[10px] text-slate-500 font-medium">Real workspace batches</p>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Pages / Invoices
            </span>
            {loading ? (
              <div className="h-7 w-16 bg-slate-800 animate-pulse rounded my-1" />
            ) : (
              <span className="text-2xl font-black text-amber-400 tracking-tight">{totalPages}</span>
            )}
            <p className="text-[10px] text-slate-500 font-medium">Processed documents</p>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Entries Extracted
            </span>
            {loading ? (
              <div className="h-7 w-16 bg-slate-800 animate-pulse rounded my-1" />
            ) : (
              <span className="text-2xl font-black text-blue-400 tracking-tight">{totalTransactions}</span>
            )}
            <p className="text-[10px] text-slate-500 font-medium">Items & transactions</p>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Success Rate
            </span>
            {loading ? (
              <div className="h-7 w-16 bg-slate-800 animate-pulse rounded my-1" />
            ) : (
              <span className="text-2xl font-black text-emerald-400 tracking-tight">{successRate}%</span>
            )}
            <p className="text-[10px] text-slate-500 font-medium">Validation integrity</p>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 sm:p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter batches by filename or bank/party..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            {(['ALL', 'COMPLETED', 'NEEDS_REVIEW', 'PARTIAL'] as const).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors cursor-pointer ${
                  statusFilter === st
                    ? 'bg-amber-400 text-slate-950'
                    : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* 4 Standard States (PRD Part 4.2.6): Loading, Empty, Error, Data */}
        {loading ? (
          /* State 1: Skeleton Loading (No fake numbers) */
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse space-y-3"
              >
                <div className="flex justify-between items-center">
                  <div className="h-5 w-48 bg-slate-800 rounded" />
                  <div className="h-5 w-24 bg-slate-800 rounded-full" />
                </div>
                <div className="h-3 w-64 bg-slate-800 rounded" />
              </div>
            ))}
          </div>
        ) : error ? (
          /* State 3: Error State */
          <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-6 text-center space-y-3">
            <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
            <h3 className="font-bold text-sm text-white">Could Not Load Workspace</h3>
            <p className="text-xs text-rose-300 max-w-md mx-auto">{error}</p>
            <button
              type="button"
              onClick={loadData}
              className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs"
            >
              Retry Loading
            </button>
          </div>
        ) : filteredBatches.length === 0 ? (
          /* State 2: Empty State (PRD Part 4.1: "No batches yet" + clear action, never sample rows) */
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-10 sm:p-14 text-center space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-slate-800/80 border border-slate-700/60 text-slate-400 flex items-center justify-center mx-auto">
              <Layers className="w-7 h-7" />
            </div>
            <div className="space-y-1.5 max-w-md mx-auto">
              <h3 className="text-lg font-black text-white tracking-tight">No Batches Yet</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                When you or your staff convert Sales or Purchase invoices, or bank statement PDFs,
                your real converted batches and generated Tally XML files will appear here.
              </p>
            </div>
            <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/sales"
                className="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md transition-all flex items-center gap-2"
              >
                <span>Convert Sales Invoices</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                href="/purchase"
                className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-md transition-all flex items-center gap-2"
              >
                <span>Convert Purchase Invoices</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        ) : (
          /* State 4: Real Data View */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Batches Table / Cards (7/12) */}
            <div className="lg:col-span-7 space-y-3">
              {filteredBatches.map((batch) => {
                const isSelected = selectedBatch?.id === batch.id;
                return (
                  <div
                    key={batch.id}
                    onClick={() => setSelectedBatch(batch)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-slate-900 border-amber-400/60 shadow-lg ring-1 ring-amber-400/30'
                        : 'bg-slate-900/70 border-slate-800 hover:border-slate-700 hover:bg-slate-900'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-amber-400 flex-shrink-0" />
                          <h4 className="font-bold text-xs text-white tracking-tight truncate max-w-xs sm:max-w-md">
                            {batch.file_name}
                          </h4>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                          <span>{batch.bank_name || 'Invoices'}</span>
                          <span>•</span>
                          <span>{batch.pages_processed || batch.page_count} Pages</span>
                          <span>•</span>
                          <span>{batch.transaction_count} Entries</span>
                          <span>•</span>
                          <span>
                            {new Date(batch.created_at).toLocaleDateString('en-IN', {
                              day: '2-digit',
                              month: 'short',
                              year: 'numeric',
                            })}
                          </span>
                        </div>
                      </div>

                      <span
                        className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border whitespace-nowrap ${
                          batch.status === 'COMPLETED'
                            ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                            : batch.status === 'NEEDS_REVIEW'
                            ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                            : 'bg-slate-800 text-slate-300 border-slate-700'
                        }`}
                      >
                        {batch.status}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Selected Batch Inspector (5/12) */}
            {selectedBatch && (
              <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 space-y-5 sticky top-20">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <h3 className="font-bold text-sm text-white">Batch Inspector</h3>
                  <span className="text-[10px] font-mono text-slate-400">
                    ID: {selectedBatch.id.slice(0, 8)}...
                  </span>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-slate-500 block text-[11px]">Source File</span>
                    <strong className="text-white font-semibold">{selectedBatch.file_name}</strong>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Pages Processed</span>
                      <strong className="text-white font-semibold">
                        {selectedBatch.pages_processed || selectedBatch.page_count}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Extracted Entries</span>
                      <strong className="text-white font-semibold">{selectedBatch.transaction_count}</strong>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Document Type</span>
                      <strong className="text-white font-semibold">
                        {selectedBatch.bank_name || 'Tally Voucher Batch'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Created At</span>
                      <strong className="text-white font-semibold">
                        {new Date(selectedBatch.created_at).toLocaleString('en-IN', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </strong>
                    </div>
                  </div>

                  {selectedBatch.is_partial_conversion && (
                    <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/50 text-[11px] text-amber-300 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                      <span>Partial conversion: Some pages were skipped due to quota limitations.</span>
                    </div>
                  )}
                </div>

                {/* XML Download Action */}
                <div className="pt-2">
                  <a
                    href={`/api/conversions/${selectedBatch.id}/download`}
                    download
                    className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Tally XML</span>
                  </a>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
