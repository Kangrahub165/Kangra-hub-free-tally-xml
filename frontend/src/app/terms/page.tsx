import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';

export const metadata = {
  title: 'Terms & Conditions – Kangra Hub Free Tally XML',
  description: 'Terms of service and usage conditions for Kangra Hub Free Tally XML bank statement converter.',
};

export default function TermsPage() {
  const sections = [
    {
      title: '1. Acceptance of Terms',
      content:
        'By accessing or using the Kangra Hub Free Tally XML conversion platform, you agree to be bound by these Terms of Service. If you do not agree with any provision of these terms, you must discontinue use of the converter immediately.',
    },
    {
      title: '2. Daily Allowance & Fair Usage Policy',
      content:
        'Free accounts are granted a daily allowance of 50 PDF pages calculated on actual statement pages parsed. The daily quota resets each midnight at 00:00 Asia/Kolkata timezone. Automated script abuse, denial-of-service attempts, or efforts to bypass rate limits will result in automated account restriction.',
    },
    {
      title: '3. Professional Accounting Verification',
      content:
        'While Kangra Hub executes algorithmic running balance checks and enforces double-entry rules (total debits equal total credits), financial and tax accuracy remains the sole responsibility of the accountant or user. You agree to inspect transactions in our review studio before committing data to your official accounting books.',
    },
    {
      title: '4. Intellectual Property & Trademarks',
      content:
        'Tally, TallyPrime, and Tally.ERP 9 are registered trademarks of Tally Solutions Pvt. Ltd. Kangra Hub is an independent third-party converter tool and is not affiliated with, sponsored by, or officially endorsed by Tally Solutions Pvt. Ltd.',
    },
    {
      title: '5. Limitation of Liability',
      content:
        'The conversion service is provided on an "as is" and "as available" basis without warranty of any kind. Under no circumstances will Kangra Hub be liable for indirect, incidental, or consequential damages resulting from data entry or accounting import operations.',
    },
  ];

  return (
    <div className="py-16 bg-slate-50 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header */}
        <div className="text-center mb-12">
          <Badge variant="neutral" size="sm" className="mb-3">
            Legal & Compliance
          </Badge>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            Terms & Conditions of Service
          </h1>
          <p className="mt-3 text-sm text-slate-600 max-w-xl mx-auto leading-relaxed">
            Please read these terms carefully before converting bank statements on Kangra Hub Free Tally XML.
          </p>
        </div>

        <div className="space-y-4">
          {sections.map((sec, idx) => (
            <Card key={idx} className="p-6 sm:p-7 border border-slate-200/90 shadow-card">
              <h2 className="text-sm font-bold text-slate-900 mb-2">{sec.title}</h2>
              <p className="text-xs text-slate-600 leading-relaxed">{sec.content}</p>
            </Card>
          ))}
        </div>

      </div>
    </div>
  );
}
