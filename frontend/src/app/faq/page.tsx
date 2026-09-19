'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { HelpCircle, ArrowRight, Search, ChevronDown } from 'lucide-react';
import { JsonLd } from '@/components/JsonLd';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

const ALL_FAQS = [
  {
    category: 'GENERAL',
    question: "What is Kangra Hub Free Tally XML?",
    answer: "Kangra Hub Free Tally XML is an automated web platform that converts bank statement PDFs into Tally-compatible XML files that can be directly imported into TallyPrime and Tally.ERP 9 without manual voucher entry."
  },
  {
    category: 'LIMITS',
    question: "How does the 50 pages per day free limit work?",
    answer: "Every registered user receives a free allowance of 50 PDF pages per calendar day based on the Asia/Kolkata timezone. The calculation is based on actual PDF pages, not file count. For example, if you upload a 20-page statement and a 15-page statement, you have used 35 pages and have 15 pages remaining."
  },
  {
    category: 'LIMITS',
    question: "What happens if my statement has more pages than my remaining daily limit?",
    answer: "If your uploaded statement exceeds your remaining daily pages (e.g. you have 10 pages remaining but upload a 25-page PDF), the system alerts you before processing begins. We do not partially convert or silently drop transactions to ensure your accounting records remain complete."
  },
  {
    category: 'LIMITS',
    question: "Can I get unlimited access?",
    answer: "Yes. The platform administrator can manually grant unlimited access to verified accounts. If you require higher volume for your CA firm or business, contact the administration."
  },
  {
    category: 'SECURITY',
    question: "Does the converter support password-protected bank PDFs?",
    answer: "Yes. If your statement is encrypted with a password, you will be prompted to enter it. The password is used solely in volatile memory during extraction and is never stored on disk or logged in server logs."
  },
  {
    category: 'GENERAL',
    question: "How are multi-line narrations handled?",
    answer: "Our parsing engine recognizes date boundaries and automatically combines multi-line descriptions (such as UPI IDs, invoice numbers, and vendor names) into a clean, complete narration for each Tally voucher."
  },
  {
    category: 'SECURITY',
    question: "How does the system ensure accounting accuracy?",
    answer: "The engine runs a running balance validation formula: Previous Balance + Credit - Debit = Current Balance. If any bank math discrepancy occurs, it flags the row for your review. Furthermore, generated XML files are mathematically validated to ensure double-entry debit and credit totals balance to zero."
  },
  {
    category: 'IMPORT',
    question: "How do I import the generated XML into Tally?",
    answer: "In TallyPrime, open your company, navigate to 'Import' (Alt + O) -> 'Bank Transactions' or 'Transactions', select XML format, and specify the downloaded XML file path. In Tally.ERP 9, go to 'Import of Data' -> 'Vouchers' and provide the file name."
  },
  {
    category: 'SECURITY',
    question: "Are my bank statements stored on the server?",
    answer: "No. Bank statements contain private financial data. They are stored only temporarily during processing and are immediately removed. No financial PDFs are kept on permanent storage."
  }
];

export default function FAQPage() {
  const [activeCategory, setActiveCategory] = useState<'ALL' | 'GENERAL' | 'LIMITS' | 'SECURITY' | 'IMPORT'>('ALL');
  const [openItems, setOpenItems] = useState<number[]>([0, 1]); // Open first two by default

  const toggleItem = (index: number) => {
    setOpenItems((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const filtered = ALL_FAQS.filter((f) => {
    if (activeCategory === 'ALL') return true;
    return f.category === activeCategory;
  });

  return (
    <>
      <JsonLd type="FAQPage" faqs={ALL_FAQS} />
      <div className="py-16 bg-slate-50 min-h-screen">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          
          {/* Header */}
          <div className="text-center mb-10">
            <Badge variant="primary" size="sm" className="mb-3">
              Knowledge Base
            </Badge>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Frequently Asked Questions
            </h1>
            <p className="mt-3 text-sm text-slate-600 max-w-lg mx-auto leading-relaxed">
              Clear answers regarding bank PDF statement conversions, Tally XML import specs, daily page allowances, and privacy guarantees.
            </p>

            {/* Category Filter Pills */}
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              {[
                { id: 'ALL', label: 'All Questions' },
                { id: 'GENERAL', label: 'Platform & Parsing' },
                { id: 'LIMITS', label: 'Daily 50-Page Quota' },
                { id: 'SECURITY', label: 'Privacy & Passwords' },
                { id: 'IMPORT', label: 'Tally Import Guide' },
              ].map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveCategory(c.id as any)}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                    activeCategory === c.id
                      ? 'bg-slate-900 text-white shadow-xs'
                      : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300'
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Accordion List */}
          <div className="space-y-3.5">
            {filtered.map((faq, i) => {
              const isOpen = openItems.includes(i);
              return (
                <Card
                  key={i}
                  className="border border-slate-200/90 overflow-hidden transition-all duration-150"
                >
                  <button
                    onClick={() => toggleItem(i)}
                    className="w-full p-5 text-left flex items-start justify-between gap-4 focus:outline-none"
                    aria-expanded={isOpen}
                  >
                    <div className="flex items-start gap-3">
                      <HelpCircle className="w-4 h-4 text-brand-600 flex-shrink-0 mt-0.5" />
                      <span className="text-sm font-bold text-slate-900 leading-snug">
                        {faq.question}
                      </span>
                    </div>
                    <ChevronDown
                      className={`w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5 transition-transform duration-200 ${
                        isOpen ? 'rotate-180 text-slate-700' : ''
                      }`}
                    />
                  </button>

                  {isOpen && (
                    <div className="px-5 pb-5 pt-0 text-xs text-slate-600 leading-relaxed pl-12 border-t border-slate-50">
                      {faq.answer}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>

          {/* Bottom Callout */}
          <div className="mt-14 text-center bg-white rounded-2xl border border-slate-200 p-8 shadow-card">
            <h3 className="text-sm font-bold text-slate-900 mb-1">
              Still have a question or need a new bank format?
            </h3>
            <p className="text-xs text-slate-500 mb-5 max-w-sm mx-auto">
              Our support team reviews customer queries and statement formats regularly.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link href="/contact">
                <Button variant="outline" size="sm">
                  Contact Support
                </Button>
              </Link>
              <Link href="/convert">
                <Button variant="primary" size="sm" iconRight={<ArrowRight className="w-3.5 h-3.5" />}>
                  Convert Statement Now
                </Button>
              </Link>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
