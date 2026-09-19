import React from 'react';
import Link from 'next/link';
import { 
  ArrowRight, 
  UploadCloud, 
  CheckCircle2, 
  FileCode, 
  ShieldCheck, 
  Sparkles, 
  Layers, 
  HelpCircle,
  Building2,
  Lock,
  Cpu,
  Check,
  ArrowUpRight,
  FileCheck2,
  Search
} from 'lucide-react';
import { JsonLd } from '@/components/JsonLd';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';

const FAQ_ITEMS = [
  {
    question: "What is Kangra Hub Free Tally XML?",
    answer: "Kangra Hub Free Tally XML is a specialized online converter that transforms supported bank statement PDFs into structured, balanced Tally-compatible XML files ready for direct import into TallyPrime and Tally.ERP 9 without manual voucher entry."
  },
  {
    question: "How do I convert a bank statement PDF to Tally XML?",
    answer: "1. Log into your free Kangra Hub account. 2. Upload your digitally generated bank statement PDF. 3. Review the parsed transactions, ledger mappings, and mathematical running balances. 4. Click 'Generate Tally XML' and download your verified XML file."
  },
  {
    question: "Which banks are currently supported?",
    answer: "The platform provides dedicated parsers for 38 leading Indian and international banks including Punjab National Bank (PNB), State Bank of India (SBI), HDFC Bank, ICICI Bank, Axis Bank, Kotak Mahindra Bank, Bank of Baroda, and 31 others."
  },
  {
    question: "How many pages can I convert for free?",
    answer: "Every free user account receives an allowance of 50 PDF pages per day. The quota resets automatically each midnight based on the Asia/Kolkata timezone."
  },
  {
    question: "Is login required to convert statements?",
    answer: "Yes, authentication is required to protect service stability, preserve custom party-to-ledger mapping rules, and track your daily page allowance."
  },
  {
    question: "Is my bank statement stored permanently?",
    answer: "No. Bank statements are processed using ephemeral volatile memory and are automatically cleaned up after conversion. No sensitive financial documents or PDF passwords are permanently retained."
  }
];

const TARGET_BANKS = [
  "Punjab National Bank", "State Bank of India", "HDFC Bank", "ICICI Bank",
  "Axis Bank", "Kotak Mahindra Bank", "Bank of Baroda", "IDFC FIRST Bank",
  "YES Bank", "RBL Bank", "Union Bank of India", "Canara Bank",
  "Bank of India", "Indian Bank", "Central Bank of India", "Federal Bank",
  "IndusInd Bank", "IDBI Bank"
];

export default function HomePage() {
  return (
    <>
      <JsonLd type="Organization" />
      <JsonLd type="WebApplication" isFree={true} />
      <JsonLd type="FAQPage" faqs={FAQ_ITEMS} />

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-20 md:pt-20 md:pb-28 border-b border-slate-200/80 bg-gradient-to-b from-white via-slate-50/50 to-slate-100/40">
        {/* Subtle grid pattern background */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#e2e8f015_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f015_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          
          {/* Service Guarantee Pill */}
          <div className="inline-flex items-center gap-2 mb-6">
            <Badge variant="success" size="md" pulse>
              FREE FOR ACCOUNTANTS & BUSINESSES • 50 PAGES DAILY
            </Badge>
          </div>

          {/* Primary H1 */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-[1.1]">
            Free Bank Statement PDF to <span className="text-brand-600">Tally XML</span> Converter
          </h1>

          <p className="mt-5 text-base sm:text-lg text-slate-600 max-w-2xl mx-auto font-normal leading-relaxed">
            Eliminate manual voucher entry. Automatically extract bank statement PDFs, audit running balance math, map counter ledgers, and download verified double-entry XML for TallyPrime and Tally.ERP 9.
          </p>

          {/* CTA Group */}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5 max-w-md mx-auto">
            <Link href="/convert" className="w-full sm:w-auto">
              <Button variant="primary" size="lg" className="w-full sm:w-auto shadow-md" iconRight={<ArrowRight className="w-4 h-4" />}>
                Start Free Conversion
              </Button>
            </Link>
            <Link href="/supported-banks" className="w-full sm:w-auto">
              <Button variant="outline" size="lg" className="w-full sm:w-auto">
                Supported Banks (38+)
              </Button>
            </Link>
          </div>

          {/* Trust Metrics Strip */}
          <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-3.5 max-w-4xl mx-auto text-left">
            <div className="bg-white/90 backdrop-blur-xs p-4 rounded-2xl border border-slate-200/90 shadow-card flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 leading-tight">38+ Banks</div>
                <div className="text-[11px] text-slate-500 mt-0.5">PSU, Private & MNC</div>
              </div>
            </div>

            <div className="bg-white/90 backdrop-blur-xs p-4 rounded-2xl border border-slate-200/90 shadow-card flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 leading-tight">100% Balanced</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Double-entry verified</div>
              </div>
            </div>

            <div className="bg-white/90 backdrop-blur-xs p-4 rounded-2xl border border-slate-200/90 shadow-card flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center flex-shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 leading-tight">50 Pages / Day</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Daily free allowance</div>
              </div>
            </div>

            <div className="bg-white/90 backdrop-blur-xs p-4 rounded-2xl border border-slate-200/90 shadow-card flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center flex-shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 leading-tight">Privacy First</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Zero permanent storage</div>
              </div>
            </div>
          </div>

          {/* Interactive Flow Visual Card */}
          <div className="mt-14 max-w-4xl mx-auto bg-white rounded-3xl border border-slate-200 shadow-elevated p-6 sm:p-8 text-left">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 mb-5 border-b border-slate-100 gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                    Automated Conversion Pipeline
                  </h3>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Visual representation of the secure statement processing workflow
                </p>
              </div>
              <Badge variant="primary" size="sm">
                Tally Standard XML
              </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <div className="text-[10px] font-bold text-brand-600 uppercase mb-1">Stage 01</div>
                <div className="font-bold text-slate-800 text-sm mb-1">Bank PDF Ingestion</div>
                <p className="text-slate-500 text-[11px] leading-relaxed">
                  Decrypted in volatile memory. Checks daily quota & file integrity.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <div className="text-[10px] font-bold text-brand-600 uppercase mb-1">Stage 02</div>
                <div className="font-bold text-slate-800 text-sm mb-1">Layout & Parser</div>
                <p className="text-slate-500 text-[11px] leading-relaxed">
                  Identifies 1 of 38 bank signature templates and extracts table rows.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <div className="text-[10px] font-bold text-brand-600 uppercase mb-1">Stage 03</div>
                <div className="font-bold text-slate-800 text-sm mb-1">Running Balance Audit</div>
                <p className="text-slate-500 text-[11px] leading-relaxed">
                  Verifies mathematical formula: Prev + Cr - Dr = Current Balance.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80">
                <div className="text-[10px] font-bold text-emerald-600 uppercase mb-1">Stage 04</div>
                <div className="font-bold text-slate-800 text-sm mb-1">Tally XML Export</div>
                <p className="text-slate-500 text-[11px] leading-relaxed">
                  Balanced debit/credit vouchers ready for TallyPrime (Alt + O) import.
                </p>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* How It Works (4 Steps) */}
      <section className="py-20 bg-white border-b border-slate-200/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-bold uppercase tracking-widest text-brand-600 mb-2 block">
              Streamlined Workflow
            </span>
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
              Convert Statements in 4 Simple Steps
            </h2>
            <p className="text-sm text-slate-600 mt-2">
              Designed to save accountants and business owners hours of error-prone manual ledger entry.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Card hoverEffect className="relative">
              <CardContent className="p-6">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-700 font-bold text-sm flex items-center justify-center mb-4 border border-brand-100">
                  01
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-1.5">Upload Statement</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Drag and drop your bank PDF. Supports password-protected PDFs with zero on-disk retention.
                </p>
              </CardContent>
            </Card>

            <Card hoverEffect className="relative">
              <CardContent className="p-6">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-700 font-bold text-sm flex items-center justify-center mb-4 border border-brand-100">
                  02
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-1.5">Detect & Extract</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Engine matches bank column structures and joins multi-line UPI narrations into single transactions.
                </p>
              </CardContent>
            </Card>

            <Card hoverEffect className="relative">
              <CardContent className="p-6">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-700 font-bold text-sm flex items-center justify-center mb-4 border border-brand-100">
                  03
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-1.5">Review & Map</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Inspect mathematical balances and map counter parties to your specific Tally chart of accounts.
                </p>
              </CardContent>
            </Card>

            <Card hoverEffect className="relative">
              <CardContent className="p-6">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-700 font-bold text-sm flex items-center justify-center mb-4 border border-brand-100">
                  04
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-1.5">Download Tally XML</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Download certified, balanced XML vouchers ready to import into TallyPrime or Tally.ERP 9.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Supported Banks Grid Preview */}
      <section className="py-20 bg-slate-50 border-b border-slate-200/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-12 gap-4">
            <div>
              <span className="text-xs font-bold uppercase tracking-widest text-brand-600 mb-2 block">
                Extensive Coverage
              </span>
              <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
                38 Supported Banks & Institutions
              </h2>
              <p className="text-sm text-slate-600 mt-1">
                Dedicated parsers built and tested for Indian public, private, and foreign banking layouts.
              </p>
            </div>
            <Link href="/supported-banks">
              <Button variant="outline" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                View All 38 Banks
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
            {TARGET_BANKS.map((bank, i) => (
              <div
                key={i}
                className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs hover:border-brand-300 hover:shadow-card transition-all text-xs font-semibold text-slate-800 flex items-center gap-2.5"
              >
                <span className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0" />
                <span className="truncate">{bank}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Accounting Precision Section */}
      <section className="py-20 bg-slate-950 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-bold uppercase tracking-widest text-brand-400 mb-2 block">
              Financial Rigor
            </span>
            <h2 className="text-3xl font-bold text-white tracking-tight">
              Engineered for Accounting Accuracy
            </h2>
            <p className="text-sm text-slate-400 mt-2">
              Every XML document is mathematically audited before export to guarantee error-free import.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-slate-900/90 border border-slate-800 p-7 rounded-2xl">
              <div className="w-10 h-10 rounded-xl bg-brand-500/10 text-brand-400 flex items-center justify-center mb-5 border border-brand-500/20">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Double-Entry Balancing</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Every generated voucher strictly conforms to Tally XML standards where total debits algebraically balance total credits with proper ISDEEMEDPOSITIVE flags.
              </p>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 p-7 rounded-2xl">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-5 border border-emerald-500/20">
                <Cpu className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Running Balance Audit</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                The engine checks that previous balance + credit - debit equals current running balance on every transaction row, highlighting math anomalies.
              </p>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 p-7 rounded-2xl">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center mb-5 border border-purple-500/20">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Multi-Line Aggregation</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Complex Indian bank statements with multi-line UPI, IMPS, and vendor narrations are parsed without truncation or row misalignment.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-20 bg-white border-b border-slate-200/80">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-xl mx-auto mb-14">
            <span className="text-xs font-bold uppercase tracking-widest text-brand-600 mb-2 block">
              Common Inquiries
            </span>
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
              Frequently Asked Questions
            </h2>
            <p className="text-sm text-slate-600 mt-1">
              Everything you need to know about limits, security, and Tally integration.
            </p>
          </div>

          <div className="space-y-4">
            {FAQ_ITEMS.map((faq, i) => (
              <div
                key={i}
                className="p-5 rounded-2xl border border-slate-200/90 bg-slate-50/60 hover:bg-slate-50 transition-colors shadow-xs"
              >
                <h3 className="text-sm font-bold text-slate-900 flex items-start gap-2.5 mb-2">
                  <HelpCircle className="w-4 h-4 text-brand-600 flex-shrink-0 mt-0.5" />
                  {faq.question}
                </h3>
                <p className="text-xs text-slate-600 pl-6.5 leading-relaxed">
                  {faq.answer}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* High-Impact Bottom CTA */}
      <section className="py-18 bg-brand-900 text-white text-center relative overflow-hidden">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight mb-3">
            Ready to convert your bank statements?
          </h2>
          <p className="text-brand-100 text-sm mb-7 max-w-lg mx-auto leading-relaxed">
            Convert up to 50 pages every day for free. Save hours on manual accounting entry today.
          </p>
          <Link href="/convert">
            <Button variant="primary" size="lg" className="bg-white text-slate-900 hover:bg-slate-100 shadow-md font-bold" iconRight={<ArrowRight className="w-4 h-4" />}>
              Start Conversion Now
            </Button>
          </Link>
        </div>
      </section>
    </>
  );
}
