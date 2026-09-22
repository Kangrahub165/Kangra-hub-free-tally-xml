import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { SEO_CONFIG } from '@/lib/seo.config';
import { PwaInstallManager } from '@/components/pwa/PwaInstallManager';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  metadataBase: new URL(SEO_CONFIG.siteUrl),
  title: {
    default: SEO_CONFIG.defaultTitle,
    template: `%s | ${SEO_CONFIG.siteName}`,
  },
  description: SEO_CONFIG.defaultDescription,
  applicationName: SEO_CONFIG.siteName,
  authors: [{ name: 'Kangra Hub' }],
  keywords: [
    'bank statement to tally xml',
    'bank statement pdf to tally xml',
    'pdf to tally xml converter',
    'free tally xml converter',
    'bank statement converter',
    'tally xml generator',
    'bank statement to tally'
  ],
  openGraph: {
    type: 'website',
    locale: 'en_IN',
    url: SEO_CONFIG.siteUrl,
    siteName: SEO_CONFIG.siteName,
    title: SEO_CONFIG.defaultTitle,
    description: SEO_CONFIG.defaultDescription,
    images: [
      {
        url: `${SEO_CONFIG.siteUrl}/og-image.png`,
        width: 1200,
        height: 630,
        alt: 'Kangra Hub Free Tally XML',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: SEO_CONFIG.defaultTitle,
    description: SEO_CONFIG.defaultDescription,
    creator: SEO_CONFIG.twitterHandle,
    images: [`${SEO_CONFIG.siteUrl}/og-image.png`],
  },
  icons: {
    icon: [
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon.ico' },
    ],
    apple: [
      { url: '/apple-touch-icon.png' },
    ],
  },
  manifest: '/manifest.webmanifest',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased min-h-screen flex flex-col justify-between">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
        <PwaInstallManager mode="USER" />
      </body>
    </html>
  );
}
