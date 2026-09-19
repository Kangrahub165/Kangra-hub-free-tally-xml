'use client';

import React, { useState, useRef } from 'react';
import Link from 'next/link';
import { 
  UploadCloud, 
  Lock, 
  Unlock, 
  ArrowRight, 
  FileText, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck, 
  Building2 
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { unlockPdfFile } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { StatusAlert } from '@/components/ui/StatusAlert';

const BANK_PASSWORD_HINTS = [
  { bank: 'State Bank of India (SBI)', hint: '11-digit Bank Account Number' },
  { bank: 'HDFC Bank', hint: 'Customer ID or Date of Birth (DDMMYYYY)' },
  { bank: 'Punjab National Bank (PNB)', hint: 'Full 16-digit Account Number' },
  { bank: 'ICICI Bank', hint: 'Date of Birth (DDMMYYYY) or Registered Mobile' },
  { bank: 'Axis Bank', hint: 'Customer ID (9 digits) or First 4 letters of name + DOB' },
  { bank: 'Kotak Mahindra Bank', hint: 'CRN Number or Date of Birth (DDMMYYYY)' },
  { bank: 'Bank of Baroda', hint: 'Full Account Number or Mobile Number' },
  { bank: 'Canara Bank', hint: 'Customer ID or First 4 letters + DOB' },
];

export default function UnlockPdfPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (selectedFile: File) => {
    setError('');
    setSuccess('');
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a valid PDF document.');
      return;
    }
    setFile(selectedFile);
  };

  const handleUnlockAndDownload = async () => {
    if (!file) {
      setError('Please select a PDF statement file.');
      return;
    }
    if (!password.trim()) {
      setError('Please enter the statement password to unlock the document.');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const unlockedBlob = await unlockPdfFile(file, password.trim());
      const objectUrl = window.URL.createObjectURL(unlockedBlob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = objectUrl;
      const baseName = file.name.replace(/\.[^/.]+$/, '');
      a.download = `${baseName}_unlocked.pdf`;
      document.body.appendChild(a);
      a.click();

      setTimeout(() => {
        try {
          if (document.body.contains(a)) {
            document.body.removeChild(a);
          }
          window.URL.revokeObjectURL(objectUrl);
        } catch {}
      }, 2000);

      setSuccess(`Statement PDF unlocked successfully! "${baseName}_unlocked.pdf" downloaded.`);
    } catch (err: any) {
      setError(err.message || 'Failed to unlock PDF. Please check the password and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="py-10 bg-slate-50 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Header Title */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 mb-2">
            <Badge variant="success" size="md">
              FREE SECURE UTILITY • 100% PRIVATE
            </Badge>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">
            Unlock Bank Statement PDF
          </h1>
          <p className="text-sm text-slate-600 max-w-xl mx-auto">
            Remove encryption passwords from protected bank statement PDFs in volatile memory. Download an unlocked copy or convert directly into balanced Tally XML.
          </p>
        </div>

        {error && (
          <StatusAlert
            type="error"
            message={error}
            onDismiss={() => setError('')}
          />
        )}

        {success && (
          <StatusAlert
            type="success"
            message={success}
            onDismiss={() => setSuccess('')}
          />
        )}

        {/* Upload Card */}
        <Card className="p-6 sm:p-8 shadow-card border-slate-200">
          <div className="space-y-6">
            {/* Drop Zone */}
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`p-8 border-2 border-dashed rounded-3xl text-center cursor-pointer transition-all duration-200 ${
                dragActive
                  ? 'border-brand-500 bg-brand-50/60 scale-[0.99]'
                  : file
                  ? 'border-emerald-400 bg-emerald-50/40'
                  : 'border-slate-300 hover:border-brand-400 hover:bg-slate-50/60'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-xs border ${
                file ? 'bg-emerald-100 text-emerald-700 border-emerald-200' : 'bg-brand-50 text-brand-600 border-brand-100'
              }`}>
                {file ? <FileText className="w-8 h-8" /> : <UploadCloud className="w-8 h-8" />}
              </div>
              <h2 className="text-lg font-bold text-slate-900 mb-1">
                {file ? file.name : 'Upload Password-Protected Statement PDF'}
              </h2>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mb-3">
                {file
                  ? `${(file.size / (1024 * 1024)).toFixed(2)} MB • PDF selected. Enter password below.`
                  : 'Drag and drop your encrypted PDF statement here, or click to browse'}
              </p>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">
                Supports PNB, SBI, HDFC, ICICI, Axis & 33+ Banks
              </div>
            </div>

            {/* Password Input Section */}
            <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200/80 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center flex-shrink-0 border border-amber-100">
                  <Lock className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Statement PDF Password
                  </div>
                  <div className="text-xs text-slate-500">
                    Required to decrypt the protected document in volatile RAM
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  type="password"
                  placeholder="Enter statement password..."
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError('');
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleUnlockAndDownload();
                  }}
                />

                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    size="md"
                    className="w-full bg-brand-600 hover:bg-brand-700 font-bold"
                    onClick={handleUnlockAndDownload}
                    loading={loading}
                    disabled={!file || !password.trim() || loading}
                    icon={<Unlock className="w-4 h-4" />}
                  >
                    Unlock & Download PDF
                  </Button>
                </div>
              </div>
            </div>

            {/* Alternative Actions */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-slate-100">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Zero permanent disk storage. Decrypted in ephemeral volatile RAM.</span>
              </div>

              <Link href="/convert">
                <Button
                  variant="outline"
                  size="sm"
                  iconRight={<ArrowRight className="w-4 h-4" />}
                  className="text-xs font-semibold"
                >
                  Go directly to Tally XML Converter
                </Button>
              </Link>
            </div>
          </div>
        </Card>

        {/* Bank Password Quick Reference Guide */}
        <Card className="p-6 shadow-xs border-slate-200">
          <CardHeader className="p-0 pb-4">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-brand-600" />
              <CardTitle className="text-base font-bold text-slate-900">
                Indian Bank Statement Password Formats Guide
              </CardTitle>
            </div>
            <CardDescription className="text-xs text-slate-500">
              Most Indian banks password-protect digital statements using standardized personal identifiers:
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              {BANK_PASSWORD_HINTS.map((b) => (
                <div key={b.bank} className="bg-slate-50 p-3 rounded-xl border border-slate-200/70 text-xs flex flex-col justify-center">
                  <span className="font-bold text-slate-800">{b.bank}</span>
                  <span className="text-slate-500 text-[11px] mt-0.5">{b.hint}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
