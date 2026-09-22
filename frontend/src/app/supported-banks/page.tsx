'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Search, Building2, CheckCircle2, ArrowRight, X, ShieldCheck } from 'lucide-react';
import { getSupportedBanks, BankInfo } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';

export default function SupportedBanksPage() {
  const [banks, setBanks] = useState<BankInfo[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<'ALL' | 'PUBLIC' | 'PRIVATE' | 'FOREIGN'>('ALL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSupportedBanks()
      .then((data) => {
        setBanks(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const publicBanks = [
    'punjab national bank', 'state bank of india', 'bank of baroda', 'canara bank',
    'union bank of india', 'bank of india', 'indian bank', 'central bank of india',
    'indian overseas bank', 'uco bank', 'bank of maharashtra', 'punjab & sind bank'
  ];

  const foreignBanks = [
    'standard chartered', 'citibank', 'hsbc', 'dbs bank', 'barclays', 'deutsche bank'
  ];

  const filtered = banks.filter((b) => {
    const matchesSearch =
      b.bank_name.toLowerCase().includes(search.toLowerCase()) ||
      b.format_name.toLowerCase().includes(search.toLowerCase()) ||
      b.parser_key.toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;

    if (category === 'PUBLIC') {
      return publicBanks.some((pb) => b.bank_name.toLowerCase().includes(pb));
    }
    if (category === 'FOREIGN') {
      return foreignBanks.some((fb) => b.bank_name.toLowerCase().includes(fb));
    }
    if (category === 'PRIVATE') {
      return (
        !publicBanks.some((pb) => b.bank_name.toLowerCase().includes(pb)) &&
        !foreignBanks.some((fb) => b.bank_name.toLowerCase().includes(fb))
      );
    }
    return true;
  });

  return (
    <div className="py-16 bg-navy-50 gradient-surface min-h-screen">
      <div className="max-w-7xl animate-fadeIn mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-10">
          <Badge variant="primary" size="sm" className="mb-3">
            Banking Coverage
          </Badge>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-navy-900 tracking-tight">
            Supported Banks & Statement Formats
          </h1>
          <p className="mt-3 text-sm text-navy-600 leading-relaxed">
            Kangra Hub maintains dedicated, tested parsers for 38 leading Indian public, private, and international banks with automatic column detection, multi-line narration joining, and running balance audits.
          </p>

          {/* Search Bar */}
          <div className="mt-8 max-w-lg mx-auto relative">
            <Search className="w-4 h-4 text-navy-400 absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by bank name or statement format (e.g. PNB, SBI, HDFC)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-white glass-card pl-11 pr-10 py-3 rounded-2xl border border-navy-300/60 text-sm text-navy-900 placeholder:text-navy-400 shadow-card focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-accent-500 focus:ring-accent-500/20 transition-all"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-navy-400 hover:text-navy-600 p-1"
                aria-label="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Category Filter Pills */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            {(
              [
                { id: 'ALL', label: 'All Banks (38)' },
                { id: 'PUBLIC', label: 'Public Sector (PSU)' },
                { id: 'PRIVATE', label: 'Private Sector' },
                { id: 'FOREIGN', label: 'MNC & Foreign' },
              ] as const
            ).map((cat) => (
              <button
                key={cat.id}
                onClick={() => setCategory(cat.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  category === cat.id
                    ? 'bg-navy-900 text-white shadow-glow-brand'
                    : 'bg-white text-navy-600 border border-navy-200/60 hover:border-navy-300/60'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* Banks Grid */}
        {loading ? (
          <div className="text-center py-24 text-navy-400 text-xs flex items-center justify-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            Loading registered bank parser catalog...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Building2 className="w-6 h-6" />}
            title="No banks matching your filter"
            description={`No supported banks matched "${search}". Clear your query to see all 38 available institutions.`}
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearch('');
                  setCategory('ALL');
                }}
              >
                Reset Filters
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((bank, i) => (
              <Card
                key={bank.parser_key || i}
                data-testid="bank-card"
                hoverEffect
                className="p-5 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center flex-shrink-0 border border-brand-100/80 shadow-glow-brand">
                      <Building2 className="w-5 h-5" />
                    </div>
                    <Badge variant="success" size="sm">
                      Active v{bank.version}
                    </Badge>
                  </div>

                  <h2 className="text-sm font-bold text-navy-900 mt-3 leading-snug">
                    {bank.bank_name}
                  </h2>
                  <p className="text-[11px] text-navy-500 mt-1">
                    Layout: <span className="font-medium text-navy-700">{bank.format_name}</span>
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-navy-100 flex items-center justify-between text-[11px] text-navy-500">
                  <span className="font-mono text-[10px] text-navy-400 truncate max-w-[150px]">
                    {bank.parser_key}
                  </span>
                  <span className="text-emerald-700 font-semibold flex items-center gap-1 text-[10px]">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Tested
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Bottom CTA Card */}
        <Card className="mt-14 max-w-2xl mx-auto p-8 text-center shadow-card">
          <h3 className="text-base font-bold text-navy-900 mb-1.5">
            Have a statement ready to convert?
          </h3>
          <p className="text-xs text-navy-500 mb-6 max-w-md mx-auto leading-relaxed">
            Convert your statement into balanced Tally XML vouchers in under 30 seconds.
          </p>
          <Link href="/convert">
            <Button variant="primary" size="md" iconRight={<ArrowRight className="w-4 h-4" />}>
              Start Conversion Studio
            </Button>
          </Link>
        </Card>

      </div>
    </div>
  );
}
