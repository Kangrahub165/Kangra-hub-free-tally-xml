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

      {/* Hero Section — Premium Dark Gradient */}
      <section className="relative overflow-hidden pt-16 pb-24 md:pt-24 md:pb-32 gradient-hero">
        {/* Decorative background elements */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(14,165,233,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(14,165,233,0.03)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-brand-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-accent-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          
          {/* Service Guarantee Pill */}
          <div className="inline-flex items-center gap-2 mb-8">
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold tracking-wide">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              FREE FOR ACCOUNTANTS & BUSINESSES • 50 PAGES DAILY
            </span>
          </div>

          {/* Primary H1 */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight max-w-5xl mx-auto leading-[1.08]">
            <span className="text-white">Free Bank Statement PDF to </span>
            <span className="text-gradient-hero">Tally XML</span>
            <span className="text-white"> Converter</span>
          </h1>

          <p className="mt-6 text-base sm:text-lg text-slate-400 max-w-2xl mx-auto font-normal leading-relaxed">
            Eliminate manual voucher entry. Automatically extract bank statement PDFs, audit running balance math, map counter ledgers, and download verified double-entry XML for TallyPrime and Tally.ERP 9.
          </p>

          {/* CTA Group */}
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3.5 max-w-md mx-auto">
            <Link href="/convert" className="w-full sm:w-auto">
              <Button variant="primary" size="lg" className="w-full sm:w-auto bg-brand-500 hover:bg-brand-400 shadow-glow-brand border-brand-400/20 text-white font-bold" iconRight={<ArrowRight className="w-4 h-4" />}>
                Start Free Conversion
              </Button>
            </Link>
            <Link href="/supported-banks" className="w-full sm:w-auto">
              <Button
                variant="outline-dark"
                size="lg"
                className="w-full sm:w-auto bg-white/5 border-slate-600 text-slate-200 hover:bg-white/10 hover:border-slate-500 hover:text-white"
              >
                Supported Banks (38+)
              </Button>
            </Link>
          </div>

          {/* Trust Metrics Strip */}
          <div className="mt-16 grid grid-cols-2 lg:grid-cols-4 gap-3.5 max-w-4xl mx-auto text-left">
            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-brand-500/15 text-brand-400 flex items-center justify-center flex-shrink-0">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">38+ Banks</div>
                <div className="text-[11px] text-slate-400 mt-0.5">PSU, Private & MNC</div>
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">100% Balanced</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Double-entry verified</div>
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-purple-500/15 text-purple-400 flex items-center justify-center flex-shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">50 Pages / Day</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Daily free allowance</div>
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center flex-shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">Privacy First</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Zero permanent storage</div>
              </div>
            </div>
          </div>

          {/* Interactive Flow Visual Card */}
          <div className="mt-16 max-w-4xl mx-auto bg-white/[0.04] backdrop-blur-sm rounded-3xl border border-white/10 p-6 sm:p-8 text-left">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 mb-5 border-b border-white/10 gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Automated Conversion Pipeline
                  </h3>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Visual representation of the secure statement processing workflow
                </p>
              </div>
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-brand-500/15 border border-brand-500/25 text-brand-300 text-[11px] font-bold">
                Tally Standard XML
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-brand-500/30 transition-colors">
                <div className="text-[10px] font-bold text-brand-400 uppercase mb-1.5">Stage 01</div>
                <div className="font-bold text-white text-sm mb-1.5">Bank PDF Ingestion</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Decrypted in volatile memory. Checks daily quota & file integrity.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-brand-500/30 transition-colors">
                <div className="text-[10px] font-bold text-brand-400 uppercase mb-1.5">Stage 02</div>
                <div className="font-bold text-white text-sm mb-1.5">Layout & Parser</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Identifies 1 of 38 bank signature templates and extracts table rows.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-brand-500/30 transition-colors">
                <div className="text-[10px] font-bold text-brand-400 uppercase mb-1.5">Stage 03</div>
                <div className="font-bold text-white text-sm mb-1.5">Running Balance Audit</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Verifies mathematical formula: Prev + Cr - Dr = Current Balance.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-accent-500/30 transition-colors">
                <div className="text-[10px] font-bold text-emerald-400 uppercase mb-1.5">Stage 04</div>
                <div className="font-bold text-white text-sm mb-1.5">Tally XML Export</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Balanced debit/credit vouchers ready for TallyPrime (Alt + O) import.
                </p>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* How It Works (4 Steps) */}
      <section className="py-20 md:py-26 gradient-surface border-b border-slate-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-brand-600 mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              Streamlined Workflow
            </span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
              Convert Statements in 4 Simple Steps
            </h2>
            <p className="text-sm text-slate-600 mt-3 leading-relaxed">
              Designed to save accountants and business owners hours of error-prone manual ledger entry.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { num: '01', title: 'Upload Statement', desc: 'Drag and drop your bank PDF. Supports password-protected PDFs with zero on-disk retention.', color: 'brand' },
              { num: '02', title: 'Detect & Extract', desc: 'Engine matches bank column structures and joins multi-line UPI narrations into single transactions.', color: 'brand' },
              { num: '03', title: 'Review & Map', desc: 'Inspect mathematical balances and map counter parties to your specific Tally chart of accounts.', color: 'brand' },
              { num: '04', title: 'Download Tally XML', desc: 'Download certified, balanced XML vouchers ready to import into TallyPrime or Tally.ERP 9.', color: 'emerald' },
            ].map((step) => (
              <Card key={step.num} hoverEffect className="relative group">
                <CardContent className="p-6">
                  <div className={`w-10 h-10 rounded-xl bg-${step.color === 'emerald' ? 'emerald' : 'brand'}-50 text-${step.color === 'emerald' ? 'emerald' : 'brand'}-600 font-bold text-sm flex items-center justify-center mb-4 border border-${step.color === 'emerald' ? 'emerald' : 'brand'}-100 group-hover:shadow-glow-${step.color === 'emerald' ? 'success' : 'brand'} transition-shadow`}>
                    {step.num}
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-1.5">{step.title}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">{step.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Supported Banks Grid Preview */}
      <section className="py-20 md:py-26 bg-white border-b border-slate-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-12 gap-4">
            <div>
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-brand-600 mb-3">
                <Building2 className="w-3.5 h-3.5" />
                Extensive Coverage
              </span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
                38 Supported Banks & Institutions
              </h2>
              <p className="text-sm text-slate-600 mt-2">
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
                className="bg-slate-50/80 p-3.5 rounded-xl border border-slate-200/80 shadow-xs hover:border-brand-300 hover:shadow-card hover:bg-white transition-all duration-200 text-xs font-semibold text-slate-800 flex items-center gap-2.5 group cursor-default"
              >
                <span className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0 group-hover:bg-brand-400 transition-colors" />
                <span className="truncate">{bank}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Accounting Precision Section — Premium Dark */}
      <section className="py-20 md:py-26 gradient-hero-radial text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-accent-400 mb-3">
              <ShieldCheck className="w-3.5 h-3.5" />
              Financial Rigor
            </span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight">
              Engineered for Accounting Accuracy
            </h2>
            <p className="text-sm text-slate-400 mt-3 leading-relaxed">
              Every XML document is mathematically audited before export to guarantee error-free import.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/[0.04] backdrop-blur-sm border border-white/10 p-7 rounded-2xl hover:bg-white/[0.06] hover:border-white/15 transition-all duration-200 group">
              <div className="w-11 h-11 rounded-xl bg-brand-500/15 text-brand-400 flex items-center justify-center mb-5 border border-brand-500/20 group-hover:shadow-glow-brand transition-shadow">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Double-Entry Balancing</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Every generated voucher strictly conforms to Tally XML standards where total debits algebraically balance total credits with proper ISDEEMEDPOSITIVE flags.
              </p>
            </div>

            <div className="bg-white/[0.04] backdrop-blur-sm border border-white/10 p-7 rounded-2xl hover:bg-white/[0.06] hover:border-white/15 transition-all duration-200 group">
              <div className="w-11 h-11 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center mb-5 border border-emerald-500/20 group-hover:shadow-glow-success transition-shadow">
                <Cpu className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Running Balance Audit</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                The engine checks that previous balance + credit - debit equals current running balance on every transaction row, highlighting math anomalies.
              </p>
            </div>

            <div className="bg-white/[0.04] backdrop-blur-sm border border-white/10 p-7 rounded-2xl hover:bg-white/[0.06] hover:border-white/15 transition-all duration-200 group">
              <div className="w-11 h-11 rounded-xl bg-accent-500/15 text-accent-400 flex items-center justify-center mb-5 border border-accent-500/20 group-hover:shadow-glow-accent transition-shadow">
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
      <section className="py-20 md:py-26 gradient-surface border-b border-slate-200/60">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-xl mx-auto mb-14">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-brand-600 mb-3">
              <HelpCircle className="w-3.5 h-3.5" />
              Common Inquiries
            </span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
              Frequently Asked Questions
            </h2>
            <p className="text-sm text-slate-600 mt-2">
              Everything you need to know about limits, security, and Tally integration.
            </p>
          </div>

          <div className="space-y-3.5">
            {FAQ_ITEMS.map((faq, i) => (
              <div
                key={i}
                className="p-5 rounded-2xl border border-slate-200/80 bg-white shadow-card hover:shadow-card-hover transition-all duration-200"
              >
                <h3 className="text-sm font-bold text-slate-900 flex items-start gap-2.5 mb-2">
                  <div className="w-6 h-6 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <HelpCircle className="w-3.5 h-3.5" />
                  </div>
                  {faq.question}
                </h3>
                <p className="text-xs text-slate-600 pl-8.5 leading-relaxed">
                  {faq.answer}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* High-Impact Bottom CTA */}
      <section className="py-20 md:py-26 gradient-hero text-white text-center relative overflow-hidden">
        {/* Decorative glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight mb-4">
            Ready to convert your bank statements?
          </h2>
          <p className="text-slate-400 text-sm sm:text-base mb-8 max-w-lg mx-auto leading-relaxed">
            Convert up to 50 pages every day for free. Save hours on manual accounting entry today.
          </p>
          <Link href="/convert">
            <Button
              variant="white"
              size="lg"
              className="font-bold px-8"
              iconRight={<ArrowRight className="w-4 h-4 text-navy-950" />}
            >
              Start Conversion Now
            </Button>
          </Link>
        </div>
      </section>
    </>
  );
}
