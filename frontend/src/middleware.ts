import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Routes that strictly require user authentication
const PROTECTED_USER_ROUTES = ['/convert', '/dashboard', '/history', '/settings'];

// Admin routes that require verified admin role
const ADMIN_ROUTE_PREFIX = '/admin';
const ADMIN_PUBLIC_ROUTES = ['/admin/login', '/admin/reset-password'];

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const token = request.cookies.get('kh_auth_token')?.value;
  const isAdmin = request.cookies.get('kh_is_admin')?.value === 'true';

  // Check for Supabase session cookies as well to support direct Supabase auth persistence
  const allCookies = request.cookies.getAll();
  const hasSbAuthCookie = allCookies.some(
    (c) =>
      (c.name.startsWith('sb-') && (c.name.endsWith('-auth-token') || c.name.includes('-auth-token'))) ||
      c.name === 'supabase-auth-token'
  );

  const hasUserAuth = !!token || hasSbAuthCookie;

  // 1. Enforce protection on private user routes
  const isProtectedUserRoute = PROTECTED_USER_ROUTES.some((route) =>
    pathname === route || pathname.startsWith(`${route}/`)
  );

  if (isProtectedUserRoute) {
    if (!hasUserAuth) {
      const redirectUrl = new URL('/login', request.url);
      redirectUrl.searchParams.set('redirect', pathname + search);
      return NextResponse.redirect(redirectUrl);
    }
  }

  // 2. Enforce admin protection on /admin routes
  if (pathname.startsWith(ADMIN_ROUTE_PREFIX)) {
    const isPublicAdminRoute = ADMIN_PUBLIC_ROUTES.some((route) => pathname === route);

    // If accessing restricted admin console without admin token
    if (!isPublicAdminRoute) {
      if (!hasUserAuth || !isAdmin) {
        const adminLoginUrl = new URL('/admin/login', request.url);
        adminLoginUrl.searchParams.set('next', pathname + search);
        return NextResponse.redirect(adminLoginUrl);
      }
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/convert/:path*',
    '/convert',
    '/dashboard/:path*',
    '/dashboard',
    '/history/:path*',
    '/history',
    '/settings/:path*',
    '/settings',
    '/admin',
    '/admin/:path*',
  ],
};
