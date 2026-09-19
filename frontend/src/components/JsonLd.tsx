import React from 'react';
import { SEO_CONFIG } from '@/lib/seo.config';

interface JsonLdProps {
  type?: 'Organization' | 'WebApplication' | 'FAQPage';
  faqs?: Array<{ question: string; answer: string }>;
  isFree?: boolean;
}

export function JsonLd({ type = 'Organization', faqs, isFree = true }: JsonLdProps) {
  let schema: Record<string, any> = {};

  if (type === 'Organization') {
    schema = {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: SEO_CONFIG.siteName,
      url: SEO_CONFIG.siteUrl,
      logo: `${SEO_CONFIG.siteUrl}/logo.webp`,
      sameAs: SEO_CONFIG.sameAs,
    };
  } else if (type === 'WebApplication') {
    schema = {
      '@context': 'https://schema.org',
      '@type': 'WebApplication',
      name: SEO_CONFIG.siteName,
      url: SEO_CONFIG.siteUrl,
      description: SEO_CONFIG.defaultDescription,
      applicationCategory: 'FinanceApplication',
      operatingSystem: 'All',
      offers: {
        '@type': 'Offer',
        price: isFree ? '0.00' : '99.00',
        priceCurrency: 'INR',
      },
    };
  } else if (type === 'FAQPage' && faqs) {
    schema = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faqs.map((f) => ({
        '@type': 'Question',
        name: f.question,
        acceptedAnswer: {
          '@type': 'Answer',
          text: f.answer,
        },
      })),
    };
  }

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
