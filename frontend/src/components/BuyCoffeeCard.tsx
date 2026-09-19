'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import { Coffee, X, ExternalLink, Check, Copy, Heart } from 'lucide-react';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { Modal } from './ui/Modal';

interface BuyCoffeeCardProps {
  upiId?: string;
  paymentUrl?: string;
  buttonText?: string;
  supportMessage?: string;
  qrPath?: string;
}

export function BuyCoffeeCard({
  upiId = '',
  paymentUrl = '',
  buttonText = 'Support Project ☕',
  supportMessage = 'Enjoying Kangra Hub Free Tally XML? Support server costs and ongoing maintenance.',
  qrPath = '/buy-a-coffee/googlepay_qr.png',
}: BuyCoffeeCardProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyUpi = () => {
    if (upiId) {
      navigator.clipboard.writeText(upiId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const effectivePaymentUrl = paymentUrl || (upiId ? `upi://pay?pa=${encodeURIComponent(upiId)}&pn=Kangra%20Hub&cu=INR` : '');

  return (
    <>
      {/* Subtle Admin Console Widget Card (Section 129) */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-card">
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center flex-shrink-0 border border-amber-200/60 shadow-xs">
            <Coffee className="w-5 h-5" />
          </div>

          <div className="flex-1 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                Voluntary Project Support
              </h3>
              <Badge variant="warning" size="sm">
                Admin Section 129
              </Badge>
            </div>

            <p className="text-[11px] text-slate-500 leading-relaxed">
              {supportMessage}
            </p>

            <div className="pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setModalOpen(true)}
                icon={<Coffee className="w-3.5 h-3.5 text-amber-600" />}
              >
                {buttonText}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* QR Code & UPI Support Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        maxWidth="sm"
      >
        <div className="text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 mx-auto flex items-center justify-center border border-amber-200/60 shadow-xs">
            <Coffee className="w-6 h-6" />
          </div>

          <div className="space-y-1">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Support Kangra Hub Project
            </h2>
            <p className="text-xs text-slate-500 leading-relaxed max-w-xs mx-auto">
              {supportMessage}
            </p>
          </div>

          {/* Scannable Official QR Code */}
          <div className="bg-slate-50 border border-slate-200/90 rounded-2xl p-3 inline-block shadow-inner mx-auto">
            <div className="relative w-48 h-48 sm:w-52 sm:h-52 mx-auto">
              <Image
                src={qrPath}
                alt="Official Kangra Hub Support QR Code"
                fill
                className="object-contain"
                priority
              />
            </div>
          </div>

          {/* UPI ID Field with Copy */}
          {upiId ? (
            <div className="space-y-1">
              <span className="text-[11px] text-slate-400 font-medium">
                UPI Identifier:
              </span>
              <div className="flex items-center justify-center gap-2 bg-slate-100 rounded-xl py-2 px-3 border border-slate-200/80 max-w-xs mx-auto">
                <code className="text-xs font-bold text-slate-800 font-mono select-all">
                  {upiId}
                </code>
                <button
                  onClick={handleCopyUpi}
                  className="text-slate-400 hover:text-brand-600 p-1 transition-colors"
                  title="Copy UPI ID"
                  aria-label="Copy UPI ID"
                >
                  {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-slate-400">
              Scan with Google Pay, PhonePe, Paytm, or any UPI banking app
            </p>
          )}

          {/* Direct UPI Intent Link */}
          {effectivePaymentUrl && (
            <div className="pt-2">
              <a
                href={effectivePaymentUrl}
                className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 shadow-sm transition-all"
              >
                <span>Launch UPI App</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          )}

          <div className="pt-1 text-[11px] text-slate-400 flex items-center justify-center gap-1">
            Thank you for supporting Kangra Hub Free Tally XML ❤️
          </div>
        </div>
      </Modal>
    </>
  );
}
