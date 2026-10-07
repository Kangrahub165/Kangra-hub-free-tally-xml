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
  FileCheck2,
  Receipt,
  ShoppingCart,
  Calculator,
  Percent,
  Coins
} from 'lucide-react';
import { JsonLd } from '@/components/JsonLd';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';

const FAQ_ITEMS = [
  {
    question: "What is Kangra Hub — Sales & Purchase?",
    answer: "Kangra Hub — Sales & Purchase is a specialized accounting tool that converts Sales and Purchase invoice PDFs into structured, balanced Tally-compatible XML vouchers ready for instant import into TallyPrime and Tally.ERP 9."
  },
  {
    question: "How many invoices can I process for free?",
    answer: "Every registered user receives 5 free bills per day. The quota resets automatically each midnight (IST). If you need higher conversion limits, upgrade to a Staff Membership subscription for unlimited daily processing."
  },
  {
    question: "Does it support GST calculation and HSN breakdown?",
    answer: "Yes! The extraction engine automatically captures item-level HSN/SAC codes, quantities, units, rates, taxable amounts, and separate CGST, SGST, and IGST components."
  },
  {
    question: "How do I import the generated XML into Tally?",
    answer: "In TallyPrime, press Alt + O (Import) → Transactions → select the downloaded XML file. In Tally.ERP 9, navigate to Import of Data → Vouchers. All entries are created with balanced debit and credit ledgers."
  },
  {
    question: "Where can I convert bank statements?",
    answer: "Bank statement conversion has been moved to our dedicated Bank Import platform at https://kangrahubtallyxml.netlify.app/. You can click the 'Bank Statement Import' link anytime to navigate there directly."
  },
  {
    question: "Is my invoice data stored permanently?",
    answer: "No. Invoices are parsed in secure volatile memory. We do not retain your sensitive commercial documents or store confidential invoice details permanently on our servers."
  }
];

export default function HomePage() {
  return (
    <>
      <JsonLd type="Organization" />
      <JsonLd type="WebApplication" isFree={true} />
      <JsonLd type="FAQPage" faqs={FAQ_ITEMS} />

      {/* Hero Section — Premium Dark Gradient */}
      <section className="relative overflow-hidden pt-16 pb-24 md:pt-24 md:pb-32 gradient-hero">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(14,165,233,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(14,165,233,0.03)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-brand-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-accent-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          
          {/* Quota & Service Pill */}
          <div className="inline-flex items-center gap-2 mb-8">
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold tracking-wide">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              5 FREE BILLS DAILY FOR REGISTERED USERS • STAFF MEMBERSHIP FOR UNLIMITED ACCESS
            </span>
          </div>

          {/* Primary H1 */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight max-w-5xl mx-auto leading-[1.08]">
            <span className="text-white">Sales & Purchase Invoice PDF to </span>
            <span className="text-gradient-hero">Tally XML</span>
            <span className="text-white"> Converter</span>
          </h1>

          <p className="mt-6 text-base sm:text-lg text-slate-400 max-w-2xl mx-auto font-normal leading-relaxed">
            Eliminate manual invoice entry. Extract GST Sales & Purchase invoices with OCR, verify tax breakdowns, map counter party ledgers & stock items, and download TallyPrime-ready XML vouchers in seconds.
          </p>

          {/* CTA Group */}
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3.5 max-w-2xl mx-auto">
            <Link href="/sales" className="w-full sm:w-auto">
              <Button
                variant="primary"
                size="lg"
                className="w-full sm:w-auto bg-brand-500 hover:bg-brand-400 shadow-glow-brand border-brand-400/20 text-white font-bold"
                iconRight={<ArrowRight className="w-4 h-4" />}
              >
                Sales Invoice → XML
              </Button>
            </Link>
            <Link href="/purchase" className="w-full sm:w-auto">
              <Button
                variant="outline-dark"
                size="lg"
                className="w-full sm:w-auto bg-emerald-600/20 border-emerald-500/40 text-emerald-200 hover:bg-emerald-600/30 hover:text-white font-bold"
                iconRight={<ArrowRight className="w-4 h-4" />}
              >
                Purchase Invoice → XML
              </Button>
            </Link>
            <a href="https://kangrahubtallyxml.netlify.app/" className="w-full sm:w-auto">
              <Button
                variant="outline-dark"
                size="lg"
                className="w-full sm:w-auto bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white font-semibold"
                iconRight={<ArrowRight className="w-4 h-4" />}
              >
                Bank Statement Import →
              </Button>
            </a>
          </div>

          {/* Trust Metrics Strip */}
          <div className="mt-16 grid grid-cols-2 lg:grid-cols-4 gap-3.5 max-w-4xl mx-auto text-left">
            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-brand-500/15 text-brand-400 flex items-center justify-center flex-shrink-0">
                <Receipt className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">Sales & Purchase</div>
                <div className="text-[11px] text-slate-400 mt-0.5">GST B2B & B2C Invoices</div>
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center flex-shrink-0">
                <Percent className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">GST Breakdown</div>
                <div className="text-[11px] text-slate-400 mt-0.5">CGST, SGST, IGST & Cess</div>
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-purple-500/15 text-purple-400 flex items-center justify-center flex-shrink-0">
                <Coins className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">5 Free Bills / Day</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Staff Subscription available</div>
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-sm p-4 rounded-2xl border border-white/10 flex items-center gap-3.5 hover:bg-white/[0.07] transition-colors">
              <div className="w-10 h-10 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center flex-shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white leading-tight">Privacy First</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Ephemeral processing</div>
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
                    Automated Invoice Processing Pipeline
                  </h3>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  High-speed OCR, GST tax audit, and Tally voucher generation
                </p>
              </div>
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-brand-500/15 border border-brand-500/25 text-brand-300 text-[11px] font-bold">
                Tally Standard XML
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-brand-500/30 transition-colors">
                <div className="text-[10px] font-bold text-brand-400 uppercase mb-1.5">Stage 01</div>
                <div className="font-bold text-white text-sm mb-1.5">Invoice PDF Ingestion</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Upload Sales or Purchase PDFs. Checks your 5 free bills/day quota.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-brand-500/30 transition-colors">
                <div className="text-[10px] font-bold text-brand-400 uppercase mb-1.5">Stage 02</div>
                <div className="font-bold text-white text-sm mb-1.5">OCR & Table Extraction</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Extracts item description, HSN/SAC, quantity, rate, and taxable amount.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-brand-500/30 transition-colors">
                <div className="text-[10px] font-bold text-brand-400 uppercase mb-1.5">Stage 03</div>
                <div className="font-bold text-white text-sm mb-1.5">GST & Ledger Audit</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Matches party ledgers, tax ledgers (CGST/SGST/IGST), and stock item names.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 hover:border-accent-500/30 transition-colors">
                <div className="text-[10px] font-bold text-emerald-400 uppercase mb-1.5">Stage 04</div>
                <div className="font-bold text-white text-sm mb-1.5">Tally XML Export</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Balanced Sales & Purchase vouchers ready for direct TallyPrime import.
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
              Simple Workflow
            </span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
              Process Invoices in 4 Easy Steps
            </h2>
            <p className="text-sm text-slate-600 mt-3 leading-relaxed">
              Engineered to save accountants and tax practitioners hours of manual data entry.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { num: '01', title: 'Upload Invoices', desc: 'Select Sales or Purchase mode and upload one or multiple PDF bills with instant format verification.', color: 'brand' },
              { num: '02', title: 'Intelligent OCR', desc: 'Our layout engine extracts header details, line items, quantities, rates, and GST tax columns.', color: 'brand' },
              { num: '03', title: 'Verify & Map', desc: 'Confirm supplier or customer party names, map stock items, and audit tax totals against your invoices.', color: 'brand' },
              { num: '04', title: 'Download XML', desc: 'Download verified, balanced Tally XML vouchers ready to import into TallyPrime or Tally.ERP 9.', color: 'emerald' },
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

      {/* Accounting Precision Section — Premium Dark */}
      <section className="py-20 md:py-26 gradient-hero-radial text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-accent-400 mb-3">
              <ShieldCheck className="w-3.5 h-3.5" />
              Accounting Rigor
            </span>
            <h2 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight">
              Engineered for TallyPrime Accuracy
            </h2>
            <p className="text-sm text-slate-400 mt-3 leading-relaxed">
              Every XML document is audited to guarantee zero import rejections in Tally.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/[0.04] backdrop-blur-sm border border-white/10 p-7 rounded-2xl hover:bg-white/[0.06] hover:border-white/15 transition-all duration-200 group">
              <div className="w-11 h-11 rounded-xl bg-brand-500/15 text-brand-400 flex items-center justify-center mb-5 border border-brand-500/20 group-hover:shadow-glow-brand transition-shadow">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Double-Entry Balancing</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Party account totals algebraically balance item sales/purchases, tax ledgers, and round-off amounts with full ISDEEMEDPOSITIVE precision.
              </p>
            </div>

            <div className="bg-white/[0.04] backdrop-blur-sm border border-white/10 p-7 rounded-2xl hover:bg-white/[0.06] hover:border-white/15 transition-all duration-200 group">
              <div className="w-11 h-11 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center mb-5 border border-emerald-500/20 group-hover:shadow-glow-success transition-shadow">
                <Calculator className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Mathematical Tax Audit</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Audits (Taxable Amount × Rate%) against billed CGST/SGST/IGST values to detect rounding mismatches before generating XML.
              </p>
            </div>

            <div className="bg-white/[0.04] backdrop-blur-sm border border-white/10 p-7 rounded-2xl hover:bg-white/[0.06] hover:border-white/15 transition-all duration-200 group">
              <div className="w-11 h-11 rounded-xl bg-accent-500/15 text-accent-400 flex items-center justify-center mb-5 border border-accent-500/20 group-hover:shadow-glow-accent transition-shadow">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Inventory & Ledger Mapping</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Map raw invoice item descriptions to your exact Tally Stock Items or General Ledgers. Export with stock units, rates, and quantities intact.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing & Quota Section */}
      <section className="py-20 md:py-26 bg-white border-b border-slate-200/60">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-brand-600 mb-3">
            <Coins className="w-3.5 h-3.5" />
            Transparent Quota
          </span>
          <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
            Free Daily Allowance & Fair Paid Add-ons
          </h2>
          <p className="text-sm text-slate-600 mt-2 max-w-xl mx-auto">
            Every business and accountant gets free daily processing with complete freedom to scale.
          </p>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-8 text-left max-w-3xl mx-auto">
            {/* Free Tier Card */}
            <div className="p-8 rounded-3xl border-2 border-brand-500 bg-brand-50/20 shadow-lg relative">
              <div className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-brand-600 text-white mb-4">
                DAILY FREE TIER
              </div>
              <h3 className="text-2xl font-black text-slate-900">5 Bills / Day</h3>
              <p className="text-xs text-slate-600 mt-2">
                Included automatically with every verified free account.
              </p>
              <ul className="mt-6 space-y-3 text-xs text-slate-700">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>5 Sales or Purchase invoices every day</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>Automatic midnight IST quota reset</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>Full OCR & GST tax breakdown</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>Standard Tally XML download</span>
                </li>
              </ul>
              <div className="mt-8">
                <Link href="/signup">
                  <Button variant="primary" size="md" className="w-full font-bold">
                    Create Free Account
                  </Button>
                </Link>
              </div>
            </div>

            {/* Staff Membership Subscription Card */}
            <div className="p-8 rounded-3xl border-2 border-amber-500 bg-gradient-to-b from-slate-900 to-slate-950 text-white shadow-xl hover:shadow-2xl transition-all relative overflow-hidden">
              <span className="absolute top-4 right-4 px-3 py-0.5 rounded-full bg-amber-400/20 text-amber-300 border border-amber-400/30 text-[10px] font-extrabold uppercase tracking-wider">
                Recommended
              </span>
              <div className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 mb-4">
                STAFF MEMBERSHIP
              </div>
              <h3 className="text-3xl font-black text-amber-400">
                ₹499 <span className="text-xs font-normal text-slate-400">/ 30 Days</span>
              </h3>
              <p className="text-xs text-slate-300 mt-2">
                High-capacity bill conversion for professional accountants & businesses.
              </p>
              <ul className="mt-6 space-y-3 text-xs text-slate-200">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <strong>Unlimited bill conversions (zero daily limits)</strong>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <strong>Official Kangra Hub Gold Tick verified crest</strong>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>Automatic multi-page bill consolidation</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>Dual UOM & Tally unit preservation</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>Priority OCR & high-speed XML pipeline</span>
                </li>
              </ul>
              <div className="mt-8">
                <Link href="/checkout">
                  <Button variant="primary" size="md" className="w-full font-black bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-slate-950 border-none shadow-md">
                    <Sparkles className="w-4 h-4 mr-1.5" /> Get Staff Membership
                  </Button>
                </Link>
              </div>
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
              Everything you need to know about invoices, limits, and Tally compatibility.
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
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight mb-4">
            Ready to convert your Sales & Purchase invoices?
          </h2>
          <p className="text-slate-400 text-sm sm:text-base mb-8 max-w-lg mx-auto leading-relaxed">
            Process 5 bills every day for free. Save hours on manual GST invoice voucher entry today.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link href="/sales">
              <Button
                variant="white"
                size="lg"
                className="font-bold px-8"
                iconRight={<ArrowRight className="w-4 h-4 text-navy-950" />}
              >
                Convert Sales Invoice
              </Button>
            </Link>
            <Link href="/purchase">
              <Button
                variant="outline-dark"
                size="lg"
                className="font-bold px-8 bg-white/10 hover:bg-white/20 text-white border-white/20"
                iconRight={<ArrowRight className="w-4 h-4" />}
              >
                Convert Purchase Invoice
              </Button>
            </Link>
            <a href="https://kangrahubtallyxml.netlify.app/">
              <Button
                variant="outline-dark"
                size="lg"
                className="font-semibold px-6 bg-slate-800/80 border-slate-700 text-slate-300 hover:text-white"
                iconRight={<ArrowRight className="w-4 h-4" />}
              >
                Bank Statement Import →
              </Button>
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
