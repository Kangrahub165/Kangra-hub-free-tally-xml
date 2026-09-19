import { MetadataRoute } from 'next';
import { SEO_CONFIG } from '@/lib/seo.config';

export default function robots(): MetadataRoute.Robots {
  const baseUrl = SEO_CONFIG.siteUrl;

  return {
    rules: {
      userAgent: '*',
      allow: [
        '/',
        '/supported-banks',
        '/how-it-works',
        '/faq',
        '/privacy',
        '/terms',
        '/contact'
      ],
      disallow: [
        '/dashboard/',
        '/convert/',
        '/history/',
        '/settings/',
        '/admin/',
        '/api/'
      ],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
