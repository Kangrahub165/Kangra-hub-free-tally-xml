'use client';

import React from 'react';
import Image from 'next/image';

export interface KangraLoaderProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
  message?: string;
  subtext?: string;
  fullScreen?: boolean;
  className?: string;
}

export function KangraLoader({
  size = 'md',
  text = 'Loading Kangra Hub...',
  message,
  subtext,
  fullScreen = false,
  className = '',
}: KangraLoaderProps) {
  const displayText = message || text;
  const sizeMap = {
    sm: {
      container: 'w-16 h-16',
      logo: 36,
      ring: 'border-2',
      title: 'text-xs font-bold',
      sub: 'text-[10px]',
    },
    md: {
      container: 'w-24 h-24',
      logo: 52,
      ring: 'border-3',
      title: 'text-sm font-extrabold',
      sub: 'text-xs',
    },
    lg: {
      container: 'w-32 h-32',
      logo: 70,
      ring: 'border-4',
      title: 'text-base font-black',
      sub: 'text-xs',
    },
  };

  const currentSize = sizeMap[size];

  const content = (
    <div className={`flex flex-col items-center justify-center text-center select-none ${className}`}>
      {/* Outer ambient glow and spinning ring container */}
      <div className="relative flex items-center justify-center">
        {/* Soft radial pulse background */}
        <div className="absolute inset-0 rounded-full bg-brand-500/15 blur-xl animate-pulse" />

        {/* Counter-spinning gradient ring */}
        <div
          className={`absolute rounded-full border-brand-500/20 border-t-brand-600 border-r-brand-400 animate-spin ${currentSize.container} ${currentSize.ring}`}
          style={{ animationDuration: '1.4s' }}
        />

        {/* Secondary subtle pulsing ring */}
        <div
          className={`absolute rounded-full border border-teal-400/30 scale-110 animate-ping opacity-25 ${currentSize.container}`}
          style={{ animationDuration: '2.5s' }}
        />

        {/* Central Logo Container with card background */}
        <div className={`relative rounded-2xl bg-white shadow-lg border border-slate-100 flex items-center justify-center p-2.5 transition-transform duration-300 hover:scale-105 ${currentSize.container}`}>
          <Image
            src="/logo.webp"
            alt="Kangra Hub"
            width={currentSize.logo}
            height={currentSize.logo}
            className="object-contain drop-shadow-sm transition-all"
            priority
          />
        </div>
      </div>

      {/* Branded Loading Message */}
      {text && (
        <div className="mt-5 space-y-1">
          <div className={`text-navy-900 tracking-tight flex items-center justify-center gap-1.5 ${currentSize.title}`}>
            <span>{displayText}</span>
            <span className="flex space-x-1 ml-0.5">
              <span className="w-1.5 h-1.5 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
          </div>
          {subtext && (
            <p className={`text-slate-500 font-medium max-w-xs mx-auto ${currentSize.sub}`}>
              {subtext}
            </p>
          )}
        </div>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-md transition-all animate-fadeIn">
        <div className="bg-white/95 border border-slate-200/80 p-8 rounded-3xl shadow-2xl max-w-sm w-full mx-4 backdrop-blur-sm">
          {content}
        </div>
      </div>
    );
  }

  return content;
}
