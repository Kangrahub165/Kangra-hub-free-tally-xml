'use client';

import React from 'react';

interface GoldTickProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  showTooltip?: boolean;
}

export function GoldTick({ size = 'md', className = '', showTooltip = true }: GoldTickProps) {
  const dimensions = {
    sm: { box: 16, icon: 10, stroke: 2.2 },
    md: { box: 20, icon: 12, stroke: 2.4 },
    lg: { box: 24, icon: 15, stroke: 2.6 },
  }[size];

  return (
    <span
      className={`inline-flex items-center justify-center relative group align-middle select-none ${className}`}
      title={showTooltip ? 'Kangra Hub Verified Staff' : undefined}
    >
      <svg
        width={dimensions.box}
        height={dimensions.box}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="transition-transform duration-200 group-hover:scale-110 drop-shadow-[0_1px_3px_rgba(212,160,23,0.4)]"
      >
        <defs>
          <linearGradient id="khGoldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#F5C542" />
            <stop offset="40%" stopColor="#D4A017" />
            <stop offset="100%" stopColor="#B8860B" />
          </linearGradient>
          <radialGradient id="khGoldGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#FFF2B2" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#D4A017" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Kangra Hub Verified Badge: Ornate 12-Point Starburst / Verified Crest */}
        <path
          d="M12 1.5L14.7 4.2L18.5 3.9L19.7 7.5L23.1 9.2L22.5 13L24.5 16.3L21.3 18.5L20.8 22.3L17 22.6L14.7 25.5L12 23L9.3 25.5L7 22.6L3.2 22.3L2.7 18.5L-0.5 16.3L0.1 13L-0.5 9.2L2.9 7.5L4.1 3.9L7.9 4.2L12 1.5Z"
          transform="scale(0.92) translate(1, -0.5)"
          fill="url(#khGoldGradient)"
          stroke="#996515"
          strokeWidth="0.75"
        />

        {/* Center crisp white checkmark */}
        <path
          d="M7.5 12.2L10.5 15.2L16.8 8.8"
          stroke="#FFFFFF"
          strokeWidth={dimensions.stroke}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {showTooltip && (
        <span className="pointer-events-none absolute bottom-full mb-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-amber-300 opacity-0 shadow-lg transition-opacity group-hover:opacity-100 z-50 border border-amber-500/30">
          Kangra Hub Verified Staff
        </span>
      )}
    </span>
  );
}

export default GoldTick;
