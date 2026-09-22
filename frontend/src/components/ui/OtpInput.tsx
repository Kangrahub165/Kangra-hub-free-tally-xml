'use client';

import React, { useRef, useEffect } from 'react';

interface OtpInputProps {
  value: string;
  onChange: (value: string) => void;
  onComplete?: (code: string) => void;
  length?: number;
  disabled?: boolean;
  hasError?: boolean;
  autoFocus?: boolean;
}

export function OtpInput({
  value,
  onChange,
  onComplete,
  length = 8,
  disabled = false,
  hasError = false,
  autoFocus = true,
}: OtpInputProps) {
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = value.padEnd(length, '').slice(0, length).split('');

  useEffect(() => {
    if (autoFocus && inputRefs.current[0]) {
      inputRefs.current[0]?.focus();
    }
  }, [autoFocus]);

  const handleChange = (index: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.replace(/[^0-9]/g, '');
    if (!val) {
      // Empty / deleted
      const nextDigits = [...digits];
      nextDigits[index] = '';
      const newOtp = nextDigits.join('').trim();
      onChange(newOtp);
      return;
    }

    // Handle single digit or multiple digits (e.g. autofill)
    if (val.length === 1) {
      const nextDigits = [...digits];
      nextDigits[index] = val;
      const newOtp = nextDigits.join('').slice(0, length);
      onChange(newOtp);

      // Move focus to next input
      if (index < length - 1 && inputRefs.current[index + 1]) {
        inputRefs.current[index + 1]?.focus();
      }

      if (newOtp.length === length && onComplete) {
        onComplete(newOtp);
      }
    } else {
      // Multiple digits entered (e.g. mobile keyboard autofill or paste)
      const cleanVal = val.slice(0, length);
      onChange(cleanVal);
      const targetIndex = Math.min(cleanVal.length, length - 1);
      inputRefs.current[targetIndex]?.focus();
      if (cleanVal.length === length && onComplete) {
        onComplete(cleanVal);
      }
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      if (!digits[index] && index > 0) {
        // Current box is empty, delete previous and move focus back
        const nextDigits = [...digits];
        nextDigits[index - 1] = '';
        onChange(nextDigits.join('').trim());
        inputRefs.current[index - 1]?.focus();
        e.preventDefault();
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
      e.preventDefault();
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
      e.preventDefault();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasteData = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, length);
    if (!pasteData) return;

    onChange(pasteData);
    const targetIdx = Math.min(pasteData.length, length - 1);
    inputRefs.current[targetIdx]?.focus();

    if (pasteData.length === length && onComplete) {
      onComplete(pasteData);
    }
  };

  const boxSizeClasses = length > 6
    ? "w-8.5 h-11 sm:w-11 sm:h-14 text-lg sm:text-2xl"
    : "w-11 h-13 sm:w-12 sm:h-14 text-xl sm:text-2xl";

  const gapClasses = length > 6
    ? "gap-1.5 sm:gap-2.5"
    : "gap-2 sm:gap-3";

  return (
    <div className={`flex items-center justify-center ${gapClasses} my-2`} role="group" aria-label={`${length}-digit verification code`}>
      {Array.from({ length }, (_, idx) => {
        const digit = digits[idx] || '';
        return (
          <input
            key={idx}
            ref={(el) => { inputRefs.current[idx] = el; }}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={idx === 0 ? length : 1}
            autoComplete={idx === 0 ? 'one-time-code' : 'off'}
            value={digit}
            onChange={(e) => handleChange(idx, e)}
            onKeyDown={(e) => handleKeyDown(idx, e)}
            onPaste={handlePaste}
            disabled={disabled}
            className={`${boxSizeClasses} text-center font-bold font-mono rounded-xl sm:rounded-2xl border transition-all duration-200 outline-none select-all ${
              hasError
                ? 'border-rose-300 bg-rose-50/40 text-rose-700 focus:ring-2 focus:ring-rose-500/25 focus:border-rose-500'
                : digit
                ? 'border-brand-500 bg-brand-50/20 text-slate-900 shadow-sm focus:ring-2 focus:ring-brand-500/25 focus:border-brand-500'
                : 'border-slate-300 bg-white text-slate-900 focus:ring-2 focus:ring-brand-500/25 focus:border-brand-500 shadow-sm hover:border-slate-400'
            } ${disabled ? 'opacity-40 cursor-not-allowed bg-slate-100' : ''}`}
          />
        );
      })}
    </div>
  );
}
