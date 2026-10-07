import { getSupabaseClient } from './supabaseClient';
import { getAuthToken } from './api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || 'http://localhost:8000/api';

export interface ActivityPayload {
  action: string;
  module?: string;
  resourceId?: string;
  status?: 'SUCCESS' | 'FAILED' | 'WARNING';
  metadata?: Record<string, any>;
}

/**
 * Universal client-side activity logger.
 * Dispatches audit records to Supabase user_activity_logs table and backend /api/activity/log.
 * Never throws errors to avoid interrupting user flows.
 */
export async function recordUserActivity({
  action,
  module = 'Sales & Purchase',
  resourceId,
  status = 'SUCCESS',
  metadata = {}
}: ActivityPayload): Promise<void> {
  try {
    const supabase = getSupabaseClient();
    const token = getAuthToken();

    // 1. Log to Supabase user_activity_logs if session is active
    if (supabase) {
      const { data: { session } } = await supabase.auth.getSession().catch(() => ({ data: { session: null } }));
      if (session?.user) {
        await supabase.from('user_activity_logs').insert({
          user_id: session.user.id,
          user_email: session.user.email,
          action,
          module,
          resource_id: resourceId || null,
          status,
          metadata,
          created_at: new Date().toISOString()
        });
      }
    }

    // 2. Relay to backend activity endpoint for persistent local server audit logs
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    await fetch(`${API_BASE}/activity/log`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        action,
        module,
        resource_id: resourceId,
        status,
        metadata
      })
    }).catch(() => {});
  } catch (err) {
    // Non-blocking
    console.debug('Activity logging suppressed error:', err);
  }
}
