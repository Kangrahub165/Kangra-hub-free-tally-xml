import React from 'react';
import Link from 'next/link';
import { ArrowRight, UserCheck, UploadCloud, Edit3, Download, ShieldCheck, CheckCircle2, ArrowDown, HelpCircle } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';

export const metadata = {
  title: 'How It Works – Kangra Hub Free Tally XML',
  description: 'Learn the complete step-by-step process of converting bank statement PDFs into Tally XML files with Kangra Hub.',
};

export default function HowItWorksPage() {
  const steps = [
    {
      step: '01',
      title: 'Create Account & Verify Email',
      description:
        'Sign up with your Full Name, Email, and Mobile Number. A fast OTP code verifies your account. Authentication allows the platform to securely store your recurring party-to-ledger mapping preferences and track your 50-page daily allowance.',
      badge: '50 Free Pages Daily',
      details: [
        'Secure OTP verification prevents unauthorized account access',
        'Daily quota resets automatically at midnight Asia/Kolkata',
        'Party-to-ledger rules persist across conversions',
      ],
      icon: <UserCheck className="w-5 h-5 text-brand-600" />,
    },
    {
      step: '02',
      title: 'Upload Bank Statement PDF',
      description:
        'Upload your digitally generated bank statement. If the statement is password-protected (standard for PNB, SBI, HDFC, ICICI, etc.), enter the password in the decryption modal. Password decryption runs entirely in ephemeral volatile memory with zero disk logging.',
      badge: '38+ Bank Signatures',
      details: [
        'Automatic institution detection with 98%+ confidence score',
        'Encrypted PDF memory unlock with instant memory purge',
        'Validation of PDF integrity and daily page quota',
      ],
      icon: <UploadCloud className="w-5 h-5 text-brand-600" />,
    },
    {
      step: '03',
      title: 'Review & Map Transactions',
      description:
        'Inspect extracted rows in an interactive accounting grid. Multi-line UPI and cheque narrations are seamlessly joined into single rows. The engine runs a mathematical verification on every transaction row: Previous Balance + Credit - Debit = Current Balance.',
      badge: 'Running Balance Formula',
      details: [
        'Inline editable cells for dates, amounts, and descriptions',
        'Assign target counter ledgers (e.g. "Utility Expenses", "Sundry Debtors")',
        'Automatic voucher type assignment (Payment, Receipt, Contra, Journal)',
      ],
      icon: <Edit3 className="w-5 h-5 text-brand-600" />,
    },
    {
      step: '04',
      title: 'Download & Import Tally XML',
      description:
        'Click Generate XML. The system creates a balanced Tally-compatible XML document adhering to official Tally XML specifications. Total debits algebraically match total credits with proper ISDEEMEDPOSITIVE tags.',
      badge: 'TallyPrime & ERP 9 Ready',
      details: [
        'In TallyPrime: Press Alt + O -> Select XML File -> Import Bank Transactions',
        'In Tally.ERP 9: Import of Data -> Vouchers -> Enter XML Path',
        'Zero duplicate imports when reference numbers match',
      ],
      icon: <Download className="w-5 h-5 text-brand-600" />,
    },
  ];

  return (
    <div className="py-16 bg-slate-50 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Page Header */}
        <div className="text-center mb-14">
          <Badge variant="primary" size="sm" className="mb-3">
            Workflow Architecture
          </Badge>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            How Kangra Hub Converts Bank PDFs to Tally XML
          </h1>
          <p className="mt-3 text-sm text-slate-600 max-w-xl mx-auto leading-relaxed">
            A fast, mathematically audited workflow engineered to eliminate manual voucher typing and balance discrepancy errors in Tally.
          </p>
        </div>

        {/* 4 Step Cards with Vertical Connecting Lines */}
        <div className="space-y-6">
          {steps.map((s, idx) => (
            <Card key={s.step} hoverEffect className="p-6 sm:p-7 relative overflow-hidden">
              <div className="flex flex-col sm:flex-row items-start gap-5">
                <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-700 font-extrabold text-base flex items-center justify-center flex-shrink-0 border border-brand-200/80 shadow-xs">
                  {s.step}
                </div>

                <div className="flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <h2 className="text-base font-bold text-slate-900">
                      {s.title}
                    </h2>
                    <Badge variant="neutral" size="sm">
                      {s.badge}
                    </Badge>
                  </div>

                  <p className="text-xs text-slate-600 leading-relaxed mb-4">
                    {s.description}
                  </p>

                  <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200/70 space-y-1.5">
                    {s.details.map((detail, dIdx) => (
                      <div key={dIdx} className="flex items-center gap-2 text-xs text-slate-700">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                        <span>{detail}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Tally Import Callout */}
        <div className="mt-12 p-6 rounded-2xl bg-white border border-slate-200 shadow-card flex flex-col sm:flex-row items-center justify-between gap-6 text-left">
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-900">
              Ready to test a bank statement?
            </h3>
            <p className="text-xs text-slate-500">
              Convert any digital bank statement and verify transactions in our live editor.
            </p>
          </div>
          <Link href="/convert" className="flex-shrink-0">
            <Button variant="primary" size="md" iconRight={<ArrowRight className="w-4 h-4" />}>
              Start Free Conversion
            </Button>
          </Link>
        </div>

      </div>
    </div>
  );
}
