'use client';

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { SEO_CONFIG } from '@/lib/seo.config';
import { ShieldCheck, Lock, ExternalLink, Shield } from 'lucide-react';
import { Badge } from './ui/Badge';

export function Footer() {
  const pathname = usePathname();
  const { socialProfiles } = SEO_CONFIG;

  // Admin routes have their own dedicated workspace view
  if (pathname?.startsWith('/admin')) {
    return null;
  }

  return (
    <footer className="bg-navy-950 text-navy-300 pt-16 pb-12 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-accent-500 to-transparent opacity-50"></div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 mb-14">
          
          {/* Brand Column (5 cols) */}
          <div className="md:col-span-4 space-y-4">
            <Link href="/" className="flex items-center gap-3 group inline-flex">
              <div className="relative w-9 h-9 flex-shrink-0">
                <Image
                  src="/logo.webp"
                  alt="Kangra Hub Free Tally XML"
                  width={36}
                  height={36}
                  className="rounded-xl shadow-xs"
                />
              </div>
              <div className="flex flex-col">
                <span className="font-extrabold text-base text-white tracking-tight leading-tight">
                  Kangra Hub
                </span>
                <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase">
                  Free Tally XML Converter
                </span>
              </div>
            </Link>

            <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
              Automated financial converter transforming bank statement PDFs into mathematically verified, balanced Tally XML files ready for instant import into TallyPrime and Tally.ERP 9.
            </p>

            <div className="pt-1 flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Free to Everyone • 50 Pages Daily
              </span>
            </div>
          </div>

          {/* Quick Links (2.5 cols) */}
          <div className="md:col-span-3">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-4">
              Platform Features
            </h4>
            <ul className="space-y-2.5 text-xs">
              <li>
                <Link href="/" className="hover:text-white transition-colors">
                  Home Overview
                </Link>
              </li>
              <li>
                <Link href="/convert" className="hover:text-white transition-colors">
                  Conversion Studio
                </Link>
              </li>
              <li>
                <Link href="/unlock-pdf" className="hover:text-white transition-colors">
                  Unlock Bank Statement PDF
                </Link>
              </li>
              <li>
                <Link href="/how-it-works" className="hover:text-white transition-colors">
                  How It Works (4 Steps)
                </Link>
              </li>
              <li>
                <Link href="/supported-banks" className="hover:text-white transition-colors">
                  Supported Banks (38+ Parsers)
                </Link>
              </li>
              <li>
                <Link href="/faq" className="hover:text-white transition-colors">
                  Frequently Asked Questions
                </Link>
              </li>

            </ul>
          </div>

          {/* Legal & Privacy Guarantee (2.5 cols) */}
          <div className="md:col-span-3">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-4">
              Security & Compliance
            </h4>
            <ul className="space-y-2.5 text-xs">
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  Privacy Policy (Zero Storage)
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-white transition-colors">
                  Terms of Service & Usage
                </Link>
              </li>
              <li>
                <Link href="/contact" className="hover:text-white transition-colors">
                  Support & Issue Reporting
                </Link>
              </li>
            </ul>

            <div className="mt-4 p-3 rounded-xl bg-slate-900 border border-slate-800/90 text-[11px] text-slate-400 leading-normal flex items-start gap-2.5">
              <Lock className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <strong className="text-slate-200">Ephemeral In-Memory:</strong> Statements are processed in temporary volatile memory and automatically purged.
              </div>
            </div>
          </div>

          {/* Official Community Channels (2 cols) */}
          <div className="md:col-span-2">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-4">
              Community Channels
            </h4>
            <p className="text-xs text-slate-400 mb-3 leading-relaxed">
              Official Kangra Hub social profiles for guides & updates:
            </p>
            <div className="flex items-center gap-2">
              {/* Facebook */}
              <a
                href={socialProfiles.facebook}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Kangra Hub on Facebook"
                className="w-8 h-8 rounded-xl bg-white/5 flex items-center justify-center text-navy-300 hover:text-white hover:bg-white/10 transition-all shadow-xs"
              >
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
              </a>

              {/* Instagram */}
              <a
                href={socialProfiles.instagram}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Kangra Hub on Instagram"
                className="w-8 h-8 rounded-xl bg-white/5 flex items-center justify-center text-navy-300 hover:text-white hover:bg-white/10 transition-all shadow-xs"
              >
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                </svg>
              </a>

              {/* X / Twitter */}
              <a
                href={socialProfiles.x}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Kangra Hub on X"
                className="w-8 h-8 rounded-xl bg-white/5 flex items-center justify-center text-navy-300 hover:text-white hover:bg-white/10 transition-all shadow-xs"
              >
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
              </a>

              {/* YouTube */}
              <a
                href={socialProfiles.youtube}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Kangra Hub on YouTube"
                className="w-8 h-8 rounded-xl bg-white/5 flex items-center justify-center text-navy-300 hover:text-white hover:bg-white/10 transition-all shadow-xs"
              >
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
              </a>
            </div>
          </div>

        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <p>© {new Date().getFullYear()} Kangra Hub Free Tally XML. Built for professional accountants and businesses.</p>
          <p className="text-[11px] text-slate-600">
            Tally, TallyPrime, and Tally.ERP 9 are registered trademarks of Tally Solutions Pvt. Ltd.
          </p>
        </div>
      </div>
    </footer>
  );
}
