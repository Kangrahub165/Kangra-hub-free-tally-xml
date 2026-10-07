'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { getSupabaseClient } from '@/lib/supabaseClient';
import { setAuthToken } from '@/lib/api';

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('Verifying your email and establishing secure session...');

  useEffect(() => {
    let isMounted = true;

    async function handleAuthCallback() {
      try {
        const client = getSupabaseClient();
        if (!client) {
          throw new Error('Supabase client could not be initialized.');
        }

        const code = searchParams.get('code');
        const next = searchParams.get('next') || searchParams.get('redirect') || '/dashboard';

        // 1. If PKCE authorization code is present in URL query
        if (code) {
          setStatus('Exchanging verification code with authentication server...');
          const { data, error: exchangeError } = await client.auth.exchangeCodeForSession(code);
          if (exchangeError) throw exchangeError;

          if (data?.session) {
            setAuthToken(data.session.access_token, false, data.session.refresh_token);
            if (isMounted) setStatus('Authentication verified! Redirecting to dashboard...');
            setTimeout(() => {
              window.location.href = next;
            }, 600);
            return;
          }
        }

        // 2. Check for hash parameters or existing session detected by Supabase client
        const { data: sessionData, error: sessionError } = await client.auth.getSession();
        if (sessionError) throw sessionError;

        if (sessionData?.session) {
          setAuthToken(sessionData.session.access_token, false, sessionData.session.refresh_token);
          if (isMounted) setStatus('Session established! Redirecting to dashboard...');
          setTimeout(() => {
            window.location.href = next;
          }, 600);
          return;
        }

        // 3. Fallback: wait briefly in case onAuthStateChange fires
        const { data: authListener } = client.auth.onAuthStateChange((event, session) => {
          if (session) {
            setAuthToken(session.access_token, false, session.refresh_token);
            authListener.subscription.unsubscribe();
            window.location.href = next;
          }
        });

        // 4. Timeout after 5 seconds if no session is detected
        setTimeout(() => {
          if (isMounted) {
            authListener.subscription.unsubscribe();
            setError('Could not verify your session. The link may have expired or was already used.');
          }
        }, 5000);

      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Authentication link verification failed. Please log in manually.');
        }
      }
    }

    handleAuthCallback();

    return () => {
      isMounted = false;
    };
  }, [searchParams, router]);

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4 text-center text-slate-100 font-sans">
      <div className="max-w-md w-full bg-slate-800/90 border border-slate-700/80 rounded-2xl p-8 shadow-xl backdrop-blur-md">
        {error ? (
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center mx-auto text-rose-400">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-white">Verification Link Issue</h2>
            <p className="text-xs text-rose-300 leading-relaxed">{error}</p>
            <div className="pt-2">
              <button
                type="button"
                onClick={() => router.replace('/login')}
                className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition-colors"
              >
                Go to Sign In
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Loader2 className="w-10 h-10 text-blue-400 animate-spin mx-auto" />
            <h2 className="text-base font-bold text-white">Kangra Hub Authentication</h2>
            <p className="text-xs text-slate-400 leading-relaxed">{status}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    }>
      <AuthCallbackContent />
    </Suspense>
  );
}
