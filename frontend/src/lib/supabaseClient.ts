import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

let supabaseInstance: SupabaseClient | null = null;

/**
 * Returns an initialized Supabase client if public environment variables are set,
 * otherwise returns null for graceful fallback to backend authentication.
 */
export function getSupabaseClient(): SupabaseClient | null {
  if (supabaseInstance) return supabaseInstance;

  if (supabaseUrl && supabaseAnonKey) {
    try {
      supabaseInstance = createClient(supabaseUrl, supabaseAnonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
        },
      });
      return supabaseInstance;
    } catch (err) {
      console.warn('Failed to initialize Supabase client:', err);
      return null;
    }
  }

  return null;
}

/**
 * Sends a password reset email via Supabase Auth for an administrator account.
 */
export async function sendAdminPasswordReset(email: string): Promise<{ success: boolean; message: string }> {
  const client = getSupabaseClient();
  if (!client) {
    return {
      success: false,
      message: 'Supabase client is not configured. Please verify NEXT_PUBLIC_SUPABASE_URL in your environment.',
    };
  }

  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const { error } = await client.auth.resetPasswordForEmail(email.trim(), {
    redirectTo: `${origin}/admin/reset-password`,
  });

  if (error) {
    return {
      success: false,
      message: error.message || 'Failed to send password reset email.',
    };
  }

  return {
    success: true,
    message: `Password reset instructions have been dispatched to ${email.trim()}. Please check your inbox.`,
  };
}
