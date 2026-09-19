import React from 'react';
import { ShieldCheck, Lock, Trash2, EyeOff, Server, KeyRound } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';

export const metadata = {
  title: 'Privacy Policy – Kangra Hub Free Tally XML',
  description: 'Learn how Kangra Hub Free Tally XML protects your financial documents and sensitive bank statement information.',
};

export default function PrivacyPolicyPage() {
  return (
    <div className="py-16 bg-slate-50 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header */}
        <div className="text-center mb-12">
          <Badge variant="success" size="sm" className="mb-3" pulse>
            Zero Permanent Storage Guarantee
          </Badge>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            Privacy & Document Security Policy
          </h1>
          <p className="mt-3 text-sm text-slate-600 max-w-xl mx-auto leading-relaxed">
            Bank statements contain sensitive financial data. Our conversion pipeline is engineered from the ground up to ensure total confidentiality and immediate document cleanup.
          </p>
        </div>

        <div className="space-y-5">
          
          {/* Section 1 */}
          <Card className="p-6 sm:p-7 border border-slate-200/90">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center flex-shrink-0 border border-brand-200/60 shadow-xs">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900 mb-1.5">
                  1. Ephemeral In-Memory & Temporary Processing
                </h2>
                <p className="text-xs text-slate-600 leading-relaxed">
                  When you upload a bank statement PDF, it is processed strictly within volatile memory or a short-lived temporary disk directory isolated to your conversion session. Once the transactions are extracted and the Tally XML is generated, original PDF files are automatically purged. We never store bank statements on long-term cloud buckets.
                </p>
              </div>
            </div>
          </Card>

          {/* Section 2 */}
          <Card className="p-6 sm:p-7 border border-slate-200/90">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center flex-shrink-0 border border-amber-200/60 shadow-xs">
                <KeyRound className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900 mb-1.5">
                  2. Statement Password Decryption
                </h2>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Many Indian banks (e.g., PNB, SBI, HDFC, ICICI, Axis) encrypt statements using customer PAN cards or birth dates. When you provide a password to unlock the document, decryption occurs entirely in volatile RAM. PDF passwords are never logged, never persisted to a database, and never transmitted to any third party.
                </p>
              </div>
            </div>
          </Card>

          {/* Section 3 */}
          <Card className="p-6 sm:p-7 border border-slate-200/90">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center flex-shrink-0 border border-emerald-200/60 shadow-xs">
                <EyeOff className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900 mb-1.5">
                  3. Zero Data Monetization & No Third-Party Analytics
                </h2>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Kangra Hub does not sell, license, analyze, or train machine learning models on your financial statements or accounting ledgers. All voucher records belong exclusively to you and your business.
                </p>
              </div>
            </div>
          </Card>

          {/* Section 4 */}
          <Card className="p-6 sm:p-7 border border-slate-200/90">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center flex-shrink-0 border border-purple-200/60 shadow-xs">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900 mb-1.5">
                  4. Account Credentials & Mapping Rules
                </h2>
                <p className="text-xs text-slate-600 leading-relaxed">
                  We store basic account credentials (Name, verified Email, and Mobile Number) to administer your daily 50-page allowance and save your customized party-to-ledger mapping preferences. You may request account deletion or data wipe at any time through our support channel.
                </p>
              </div>
            </div>
          </Card>

        </div>

      </div>
    </div>
  );
}
