import { getDeviceId } from './fingerprint';

export interface PublicSettings {
  site_name: string;
  site_mode: 'FREE' | 'PAID';
  free_daily_page_limit: number;
  maintenance_mode: boolean;
  allow_new_signups: boolean;
  max_upload_size_mb: number;
  max_pages_per_file: number;
}

export interface BankInfo {
  parser_key: string;
  bank_name: string;
  format_name: string;
  version: string;
  is_active: boolean;
}

export interface UsageInfo {
  user_id: string;
  daily_limit: number;
  effective_daily_quota?: number;
  pages_used_today: number;
  pages_remaining_today: number;
  additional_page_balance?: number;
  bills_used_today?: number;
  bills_remaining_today?: number;
  free_daily_bill_limit?: number;
  additional_bill_balance?: number;
  price_per_bill?: number;
  total_allowed_pages?: number;
  price_per_page?: number;
  is_unlimited: boolean;
  account_status: string;
  quota_mode?: 'GLOBAL' | 'CUSTOM' | 'UNLIMITED';
  quota_source?: string;
  global_limit?: number;
  global_quota?: number;
  custom_limit?: number | null;
  custom_quota?: number | null;
  timezone: string;
  reset_at_ist?: string;
  conversion_count?: number;
}

export interface PaymentConfig {
  upi_id: string;
  price_per_page: number;
  qr_path: string;
  whatsapp_number: string;
  support_message: string;
  razorpay_key_id?: string;
  razorpay_configured?: boolean;
  is_test_mode?: boolean;
}

export interface PaymentRequest {
  id: string;
  user_id: string;
  user_email: string;
  user_name?: string;
  requested_pages: number;
  granted_pages: number;
  amount_paid: number;
  amount_inr?: number;
  job_id?: string;
  notes?: string;
  user_notes?: string;
  screenshot_url: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  created_at: string;
  updated_at: string;
  admin_notes?: string;
  approved_by?: string;
  approved_at?: string;
  reviewed_at?: string;
}

export interface TransactionItem {
  id?: string;
  row_index: number;
  date: string;
  value_date?: string;
  posting_date?: string;
  narration: string;
  full_narration?: string;
  original_narration?: string;
  reference?: string;
  cheque_number?: string;
  instrument_number?: string;
  utr?: string;
  upi_ref?: string;
  debit: string | number;
  credit: string | number;
  balance?: string | number;
  confidence_score: number;
  party_name?: string;
  suggested_ledger?: string;
  mapping_confidence?: number;
  mapping_status?: 'Auto' | 'Previously Mapped' | 'Suspense' | 'User Confirmed' | string;
  ledger_name?: string;
  original_ledger_name?: string;
  voucher_type: string;
  original_voucher_type?: string;
  is_cash_transaction?: boolean;
  cash_transaction_type?: string;
  validation_status: string;
  validation_notes?: string;
  is_duplicate_suspect?: boolean;
  duplicate_reason?: string;
  source_page?: number;
  source_lines?: string[];
}

export interface PageDiagnosticSummary {
  page_number: number;
  detected_candidate_count: number;
  extracted_transaction_count: number;
  unparsed_candidate_lines?: string[];
}

export interface ConversionJobSummary {
  id: string;
  user_id: string;
  user_email?: string;
  file_name: string;
  bank_name: string;
  statement_format: string;
  page_count: number;
  total_pdf_pages?: number;
  pages_processed?: number;
  pages_skipped?: number;
  pages_pending?: number;
  page_statuses?: Record<string, string>;
  free_quota_used?: number;
  additional_quota_used?: number;
  is_partial_conversion?: boolean;
  remaining_pages?: number;
  suggested_additional_price?: number;
  transaction_count: number;
  rejected_transaction_count?: number;
  raw_transaction_count?: number;
  suspense_count?: number;
  mapped_count?: number;
  duplicate_count?: number;
  warning_count?: number;
  error_count?: number;
  ready_for_export?: boolean;
  page_diagnostics?: PageDiagnosticSummary[];
  bank_ledger_name?: string;
  cash_ledger_name?: string;
  status: 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'NEEDS_REVIEW' | 'AMBIGUOUS_BANK' | 'QUOTA_EXHAUSTED' | string;
  confidence_score: number;
  confidence_tier?: 'HIGH' | 'MEDIUM' | 'LOW' | 'AMBIGUOUS';
  is_ambiguous?: boolean;
  parser_name?: string;
  detected_ifsc?: string;
  runner_up_bank?: string;
  runner_up_confidence?: number;
  detection_reasons?: string[];
  balance_status?: 'VALID' | 'MISMATCH' | 'PENDING_SELECTION';
  statement_from?: string;
  statement_to?: string;
  opening_balance?: string | number;
  closing_balance?: string | number;
  total_debit: string | number;
  total_credit: string | number;
  created_at: string;
  override_warning?: string;
  candidates?: any[];
  transactions?: TransactionItem[];
}

export interface ImportedGroup {
  name: string;
  parent?: string;
  guid?: string;
}

export interface ImportedLedger {
  name: string;
  normalized_name: string;
  group?: string;
  parent_group?: string;
  opening_balance?: number | string;
  party_gstin?: string;
  state?: string;
  country?: string;
  pincode?: string;
  guid?: string;
  aliases?: string[];
  source_format?: string;
}

export interface LedgerImportResult {
  detected_format: string;
  total_imported: number;
  total_ledgers?: number;
  total_groups?: number;
  groups?: ImportedGroup[];
  ledgers: ImportedLedger[];
  duplicates?: number;
  conflicts?: string[];
  needs_review?: boolean;
  error?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || 'http://localhost:8000/api';

export function getAuthToken(): string {
  if (typeof window !== 'undefined') {
    const directToken = localStorage.getItem('kh_auth_token');
    if (directToken) return directToken;

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith('sb-') && key.endsWith('-auth-token') || key === 'supabase.auth.token')) {
        try {
          const item = localStorage.getItem(key);
          if (item) {
            const parsed = JSON.parse(item);
            const token = parsed?.access_token || parsed?.currentSession?.access_token;
            if (token) {
              localStorage.setItem('kh_auth_token', token);
              return token;
            }
          }
        } catch {}
      }
    }
  }
  return '';
}

export function getRefreshToken(): string {
  if (typeof window !== 'undefined') {
    const directToken = localStorage.getItem('kh_refresh_token');
    if (directToken) return directToken;

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith('sb-') && key.endsWith('-auth-token') || key === 'supabase.auth.token')) {
        try {
          const item = localStorage.getItem(key);
          if (item) {
            const parsed = JSON.parse(item);
            const refreshToken = parsed?.refresh_token || parsed?.currentSession?.refresh_token;
            if (refreshToken) {
              localStorage.setItem('kh_refresh_token', refreshToken);
              return refreshToken;
            }
          }
        } catch {}
      }
    }
  }
  return '';
}

export function setAuthToken(token: string, isAdmin: boolean = false, refreshToken?: string) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('kh_auth_token', token);
    const isSecure = window.location.protocol === 'https:';
    const secureFlag = isSecure ? '; Secure' : '';
    document.cookie = `kh_auth_token=${encodeURIComponent(token)}; path=/; max-age=604800; SameSite=Lax${secureFlag}`;
    if (refreshToken) {
      localStorage.setItem('kh_refresh_token', refreshToken);
    }
    if (isAdmin) {
      localStorage.setItem('kh_is_admin', 'true');
      document.cookie = `kh_is_admin=true; path=/; max-age=604800; SameSite=Lax${secureFlag}`;
    } else {
      localStorage.removeItem('kh_is_admin');
      document.cookie = `kh_is_admin=; path=/; max-age=0; SameSite=Lax${secureFlag}`;
    }
    window.dispatchEvent(new Event('kh_auth_changed'));
  }
}

export function clearAuthToken() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('kh_auth_token');
    localStorage.removeItem('kh_refresh_token');
    localStorage.removeItem('kh_is_admin');
    const isSecure = window.location.protocol === 'https:';
    const secureFlag = isSecure ? '; Secure' : '';
    document.cookie = `kh_auth_token=; path=/; max-age=0; SameSite=Lax${secureFlag}`;
    document.cookie = `kh_is_admin=; path=/; max-age=0; SameSite=Lax${secureFlag}`;
    window.dispatchEvent(new Event('kh_auth_changed'));
  }
}

export function getUserRole(): 'ADMIN' | 'USER' | 'GUEST' {
  if (typeof window !== 'undefined') {
    const token = getAuthToken();
    if (!token) return 'GUEST';
    const isAdmin = localStorage.getItem('kh_is_admin') === 'true';
    if (isAdmin) return 'ADMIN';

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('sb-') && key.endsWith('-auth-token')) {
        try {
          const item = localStorage.getItem(key);
          if (item) {
            const parsed = JSON.parse(item);
            const role = parsed?.user?.user_metadata?.role || parsed?.user?.app_metadata?.role;
            if (role === 'ADMIN') {
              localStorage.setItem('kh_is_admin', 'true');
              return 'ADMIN';
            }
          }
        } catch {}
      }
    }
    return 'USER';
  }
  return 'GUEST';
}

let refreshPromise: Promise<string | null> | null = null;

export async function refreshSessionToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      // 1. First attempt to refresh via Supabase Client if configured
      try {
        const { getSupabaseClient } = await import('@/lib/supabaseClient');
        const supabase = getSupabaseClient();
        if (supabase) {
          const { data, error } = await supabase.auth.refreshSession();
          if (!error && data?.session?.access_token) {
            const isUserAdmin = getUserRole() === 'ADMIN' || data.session.user?.user_metadata?.role === 'ADMIN';
            setAuthToken(data.session.access_token, isUserAdmin, data.session.refresh_token);
            return data.session.access_token;
          }
        }
      } catch (sbErr) {
        // Fallback to backend refresh
      }

      // 2. Fallback to backend refresh endpoint using stored refresh token
      const refreshToken = getRefreshToken();
      if (refreshToken) {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.token) {
            setAuthToken(data.token, getUserRole() === 'ADMIN', data.refresh_token);
            return data.token;
          }
        }
      }
    } catch {
      // Refresh error handled safely
    } finally {
      refreshPromise = null;
    }
    return null;
  })();

  return refreshPromise;
}

export async function verifyAdmin(): Promise<{ status: string; is_admin: boolean; user: any }> {
  return apiFetch<{ status: string; is_admin: boolean; user: any }>('/admin/verify');
}

export async function userLogin(email: string, password: string): Promise<{ token: string; refresh_token?: string; user: any }> {
  // Clear any existing stale or mock tokens before attempting login
  clearAuthToken();

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  if (!res.ok) {
    clearAuthToken();
    let errData: any = {};
    let errorDetail = 'Invalid credentials / Login failed. Please check your email and password.';
    try {
      errData = await res.json();
      errorDetail = typeof errData.detail === 'string' ? errData.detail : (errData.detail?.message || errData.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    const detailObj = typeof errData.detail === 'object' ? errData.detail : errData;
    err.code = detailObj.code || detailObj.error || (res.status === 403 ? 'ACCOUNT_SUSPENDED' : 'AUTH_FAILED');
    err.suspension_reason = detailObj.suspension_reason;
    err.suspended_at = detailObj.suspended_at;
    err.suspension_delete_at = detailObj.suspension_delete_at;
    err.user_id = detailObj.user_id;
    err.full_name = detailObj.full_name;
    err.email = detailObj.email || email;
    throw err;
  }
  const data = await res.json();
  if (!data || !data.token || typeof data.token !== 'string' || data.token.trim().length === 0) {
    clearAuthToken();
    const err: any = new Error('Invalid credentials / Login failed: No valid authorization token received.');
    err.status = 401;
    throw err;
  }
  setAuthToken(data.token, data.user?.role === 'ADMIN', data.refresh_token);
  return data;
}

export async function adminLogin(email: string, password: string): Promise<{ token: string; is_admin: boolean; user: any }> {
  // Clear any existing stale or mock tokens before attempting admin login
  clearAuthToken();

  const res = await fetch(`${API_BASE}/system/admin-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  if (!res.ok) {
    clearAuthToken();
    let errorDetail = 'Invalid credentials / Login failed: Access denied. This portal is restricted to authorized administrators.';
    try {
      const err = await res.json();
      errorDetail = typeof err.detail === 'string' ? err.detail : (err.detail?.message || err.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  const data = await res.json();
  if (!data || !data.token || !data.is_admin) {
    clearAuthToken();
    const err: any = new Error('Invalid credentials / Login failed: Unauthorized administrator credentials.');
    err.status = 401;
    throw err;
  }
  setAuthToken(data.token, true);
  return data;
}

export async function adminForgotPassword(email: string): Promise<{ success: boolean; message: string; recovery_email: string }> {
  const res = await fetch(`${API_BASE}/system/admin-forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim() }),
  });
  if (!res.ok) {
    let errorDetail = 'Failed to process password recovery request';
    try {
      const err = await res.json();
      errorDetail = err.detail || err.message || errorDetail;
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function submitAccountRecovery(payload: {
  account_identifier: string;
  known_email?: string;
  known_mobile?: string;
  requested_new_email?: string;
  requested_new_mobile?: string;
  reason: string;
  identity_verification_info?: string;
}): Promise<{ success: boolean; request_id: string; reference_id: string; message: string; status: string }> {
  const res = await fetch(`${API_BASE}/auth/recovery/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let errorDetail = 'Failed to submit account recovery request';
    try {
      const err = await res.json();
      errorDetail = typeof err.detail === 'string' ? err.detail : (err.detail?.message || err.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function getAccountRecoveryStatus(requestId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/recovery/status/${encodeURIComponent(requestId.trim())}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    let errorDetail = 'Recovery request not found';
    try {
      const err = await res.json();
      errorDetail = typeof err.detail === 'string' ? err.detail : (err.detail?.message || err.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function sendSignupOtp(payload: {
  email: string;
  mobile_number: string;
  full_name: string;
  password?: string;
  channel?: 'EMAIL' | 'SMS';
}): Promise<{ success: boolean; message: string; destination_masked: string; cooldown_seconds: number; reference_id: string; channel?: string }> {
  const res = await fetch(`${API_BASE}/auth/signup/send-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let errorDetail = 'Failed to send verification code';
    try {
      const err = await res.json();
      errorDetail = typeof err.detail === 'string' ? err.detail : (err.detail?.message || err.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function verifySignupOtp(payload: {
  email: string;
  mobile_number: string;
  otp: string;
  channel?: 'EMAIL' | 'SMS';
  full_name?: string;
  password?: string;
}): Promise<{ success: boolean; message: string; token?: string; email_verified?: boolean; user?: any }> {
  const res = await fetch(`${API_BASE}/auth/signup/verify-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let errorDetail = 'Verification failed';
    try {
      const err = await res.json();
      errorDetail = typeof err.detail === 'string' ? err.detail : (err.detail?.message || err.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function resendSignupOtp(payload: {
  destination: string;
  channel?: 'EMAIL' | 'SMS';
}): Promise<{ success: boolean; message: string; cooldown_seconds: number; reference_id: string; channel?: string }> {
  const res = await fetch(`${API_BASE}/auth/signup/resend-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let errorDetail = 'Failed to resend verification code';
    try {
      const err = await res.json();
      errorDetail = typeof err.detail === 'string' ? err.detail : (err.detail?.message || err.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  let token = getAuthToken();
  const hadToken = !!token;
  const headers = new Headers(options.headers || {});
  if (!headers.has('Authorization') && token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('X-Device-Id')) {
    try {
      const devId = getDeviceId();
      if (devId) {
        headers.set('X-Device-Id', devId);
      }
    } catch {}
  }

  let res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized with automatic session refresh
  if (res.status === 401) {
    const refreshedToken = await refreshSessionToken();
    if (refreshedToken) {
      headers.set('Authorization', `Bearer ${refreshedToken}`);
      res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
      });
    } else {
      const err: any = new Error(hadToken ? 'Your session has expired. Please log in again to continue.' : 'Authentication required.');
      err.status = 401;
      err.code = hadToken ? 'ERR_TOKEN_EXPIRED' : 'ERR_UNAUTHORIZED';
      throw err;
    }
  }

  if (!res.ok) {
    let errData: any;
    try {
      errData = await res.json();
    } catch {
      errData = { message: res.statusText };
    }
    let message = 'Request failed';
    if (typeof errData?.detail === 'string') {
      message = errData.detail;
    } else if (errData?.detail?.message) {
      message = errData.detail.message;
    } else if (Array.isArray(errData?.detail) && errData.detail.length > 0) {
      message = errData.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
    } else if (errData?.message) {
      message = errData.message;
    } else if (res.statusText) {
      message = res.statusText;
    }

    // Never disclose raw internal JWT parsing errors to normal users
    if (message.toLowerCase().includes('token is expired') || message.toLowerCase().includes('jwt')) {
      message = 'Your session has expired. Please log in again to continue.';
    }

    // Intercept 403 Account Suspended responses to evict active sessions (PRD Sections 4 & 22)
    const detailObj = typeof errData?.detail === 'object' ? errData.detail : errData;
    const isSuspended =
      res.status === 403 && (
        detailObj?.error === 'ACCOUNT_SUSPENDED' ||
        detailObj?.code === 'ACCOUNT_SUSPENDED' ||
        errData?.error === 'ACCOUNT_SUSPENDED' ||
        message.toLowerCase().includes('suspended')
      );

    if (isSuspended && typeof window !== 'undefined') {
      const currentPath = window.location.pathname;
      if (currentPath !== '/suspended' && !currentPath.startsWith('/suspended')) {
        const reason = encodeURIComponent(detailObj?.suspension_reason || '');
        const email = encodeURIComponent(detailObj?.email || '');
        const suspendedAt = encodeURIComponent(detailObj?.suspended_at || '');
        const deleteAt = encodeURIComponent(detailObj?.suspension_delete_at || '');
        window.location.href = `/suspended?email=${email}&reason=${reason}&suspended_at=${suspendedAt}&delete_at=${deleteAt}`;
      }
    }

    const code = detailObj?.code || detailObj?.error || errData?.code || 'UNKNOWN_ERROR';
    const refId = errData?.detail?.reference_id || errData?.reference_id || '';
    const error: any = new Error(message);
    error.code = code;
    error.reference_id = refId;
    error.status = res.status;
    error.suspension_reason = detailObj?.suspension_reason;
    error.suspended_at = detailObj?.suspended_at;
    error.suspension_delete_at = detailObj?.suspension_delete_at;
    error.user_id = detailObj?.user_id;
    throw error;
  }

  return res.json();
}

// Client API Methods
let cachedPublicSettings: PublicSettings | null = null;
let cachedPublicSettingsTimestamp = 0;

export async function getPublicSettings(): Promise<PublicSettings> {
  const now = Date.now();
  if (cachedPublicSettings && (now - cachedPublicSettingsTimestamp < 60000)) {
    return cachedPublicSettings;
  }
  const data = await apiFetch<PublicSettings>('/system/public-settings');
  cachedPublicSettings = data;
  cachedPublicSettingsTimestamp = now;
  return data;
}

export async function getSupportedBanks(): Promise<BankInfo[]> {
  return apiFetch<BankInfo[]>('/banks');
}

let cachedUsage: UsageInfo | null = null;
let cachedUsageTimestamp = 0;
let usageFetchPromise: Promise<UsageInfo> | null = null;

export async function getUserUsage(): Promise<UsageInfo> {
  const now = Date.now();
  if (cachedUsage && (now - cachedUsageTimestamp < 4000)) {
    return cachedUsage;
  }
  if (usageFetchPromise) {
    return usageFetchPromise;
  }
  usageFetchPromise = (async () => {
    try {
      const data = await apiFetch<UsageInfo>('/usage');
      cachedUsage = data;
      cachedUsageTimestamp = Date.now();
      return data;
    } finally {
      usageFetchPromise = null;
    }
  })();
  return usageFetchPromise;
}

export async function uploadStatementPdf(
  file: File,
  password?: string,
  bankOverride?: string,
  bankLedgerName?: string,
  cashLedgerName?: string
): Promise<ConversionJobSummary> {
  const formData = new FormData();
  formData.append('file', file);
  if (password) formData.append('password', password);
  if (bankOverride) formData.append('bank_override', bankOverride);
  if (bankLedgerName) formData.append('bank_ledger_name', bankLedgerName);
  if (cashLedgerName) formData.append('cash_ledger_name', cashLedgerName);

  const token = getAuthToken();
  const res = await fetch(`${API_BASE}/conversions/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    let err: any = {};
    try {
      err = await res.json();
    } catch {
      err = { message: res.statusText || 'Upload failed' };
    }
    const message =
      err?.message ||
      err?.detail?.message ||
      (typeof err?.detail === 'string' ? err.detail : '') ||
      'Upload failed';
    const code =
      err?.code ||
      err?.detail?.code ||
      (res.status === 401 ? 'ERR_PDF_PASSWORD_REQUIRED' : 'UPLOAD_FAILED');
    const refId = err?.reference_id || err?.detail?.reference_id || '';
    const error: any = new Error(message);
    error.code = code;
    error.details = err?.details || err?.detail?.details;
    error.reference_id = refId;
    error.status = res.status;
    throw error;
  }

  return res.json();
}

export async function unlockPdfFile(file: File, password: string): Promise<Blob> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('password', password);

  const token = getAuthToken();
  const res = await fetch(`${API_BASE}/conversions/unlock-pdf`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!res.ok) {
    let err: any = {};
    try {
      err = await res.json();
    } catch {
      err = { message: res.statusText || 'PDF unlock failed' };
    }
    const message =
      err?.message ||
      err?.detail?.message ||
      (typeof err?.detail === 'string' ? err.detail : '') ||
      'Failed to unlock PDF';
    const code = err?.code || err?.detail?.code || 'ERR_UNLOCK_FAILED';
    const error: any = new Error(message);
    error.code = code;
    throw error;
  }

  return res.blob();
}

export async function selectBankForJob(
  jobId: string,
  bankName: string
): Promise<ConversionJobSummary> {
  return apiFetch<ConversionJobSummary>(`/conversions/${jobId}/select-bank`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bank_name: bankName }),
  });
}

export async function reviewTransactions(
  jobId: string,
  transactions: TransactionItem[],
  bankLedgerName?: string,
  cashLedgerName?: string
): Promise<ConversionJobSummary> {
  return apiFetch<ConversionJobSummary>(`/conversions/${jobId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      transactions,
      bank_ledger_name: bankLedgerName,
      cash_ledger_name: cashLedgerName
    }),
  });
}

export async function updateTransactionRow(
  jobId: string,
  rowIndex: number,
  updates: {
    ledger_name?: string;
    voucher_type?: string;
    instrument_number?: string;
    narration?: string;
    save_as_rule?: boolean;
  },
  isAdmin: boolean = false
): Promise<ConversionJobSummary> {
  const endpoint = isAdmin ? `/admin/conversions/${jobId}/update-row` : `/conversions/${jobId}/update-row`;
  return apiFetch<ConversionJobSummary>(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ row_index: rowIndex, ...updates }),
  });
}

export async function bulkAssignLedgers(
  jobId: string,
  rowIndices: number[],
  ledgerName: string,
  voucherType?: string,
  applyToSimilar: boolean = false,
  isAdmin: boolean = false,
  txIds?: string[],
  action?: string
): Promise<ConversionJobSummary> {
  const endpoint = isAdmin ? `/admin/conversions/${jobId}/bulk-assign-ledger` : `/conversions/${jobId}/bulk-assign-ledger`;
  return apiFetch<ConversionJobSummary>(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      row_indices: rowIndices,
      ledger_name: ledgerName,
      voucher_type: voucherType,
      apply_to_similar: applyToSimilar,
      tx_ids: txIds,
      action: action || 'ASSIGN',
    }),
  });
}

export async function generateXml(
  jobId: string,
  bankLedgerName?: string,
  cashLedgerName?: string
): Promise<{ success: boolean; filename: string; download_url: string }> {
  return apiFetch(`/conversions/${jobId}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bank_ledger_name: bankLedgerName,
      cash_ledger_name: cashLedgerName,
      confirm_suspense: true
    }),
  });
}

export async function generateExcel(
  jobId: string,
  bankLedgerName?: string,
  cashLedgerName?: string
): Promise<{ success: boolean; filename: string; download_url: string }> {
  return apiFetch(`/conversions/${jobId}/generate-excel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bank_ledger_name: bankLedgerName,
      cash_ledger_name: cashLedgerName,
    }),
  });
}

export async function downloadFileBlob(downloadUrl: string, filename: string): Promise<void> {
  const token = getAuthToken();
  let fullUrl = downloadUrl;
  if (!fullUrl.startsWith('http://') && !fullUrl.startsWith('https://')) {
    const base = API_BASE.replace(/\/api$/, '');
    fullUrl = `${base}${downloadUrl.startsWith('/') ? '' : '/'}${downloadUrl}`;
  }

  // Append token to query parameter for maximum browser compatibility
  if (token && !fullUrl.includes('token=')) {
    const sep = fullUrl.includes('?') ? '&' : '?';
    fullUrl = `${fullUrl}${sep}token=${encodeURIComponent(token)}`;
  }

  const res = await fetch(fullUrl, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    let errMsg = `Download failed (${res.status})`;
    try {
      const err = await res.json();
      errMsg = err.detail?.message || err.detail || err.message || errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  const blob = await res.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();

  // Safely delay cleanup so Chrome/Edge doesn't abort download before processing blob stream
  setTimeout(() => {
    try {
      if (document.body.contains(a)) {
        document.body.removeChild(a);
      }
      window.URL.revokeObjectURL(objectUrl);
    } catch {
      // ignore
    }
  }, 2000);
}

export async function getUserConversions(): Promise<ConversionJobSummary[]> {
  return apiFetch<ConversionJobSummary[]>('/conversions');
}

// Ledger Management & Import API Methods
export async function importLedgers(file: File): Promise<LedgerImportResult> {
  const formData = new FormData();
  formData.append('file', file);
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/ledgers/import`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) {
    let errDetail = 'Failed to import ledgers';
    try {
      const err = await res.json();
      errDetail = err.detail || err.message || errDetail;
    } catch {}
    const error: any = new Error(errDetail);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

export async function getUserLedgers(search?: string, limit?: number): Promise<ImportedLedger[]> {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (limit) params.append('limit', limit.toString());
  const queryStr = params.toString() ? `?${params.toString()}` : '';
  return apiFetch<ImportedLedger[]>(`/ledgers${queryStr}`);
}

export async function getUserGroups(): Promise<ImportedGroup[]> {
  return apiFetch<ImportedGroup[]>('/ledgers/groups');
}

export async function getUserBankLedgers(): Promise<ImportedLedger[]> {
  return apiFetch<ImportedLedger[]>('/ledgers/banks');
}

export async function addSingleLedger(name: string, group: string = 'Primary'): Promise<ImportedLedger> {
  return apiFetch<ImportedLedger>('/ledgers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, group }),
  });
}

export async function createLedger(data: {
  name: string;
  group?: string;
  party_gstin?: string;
  state?: string;
}): Promise<ImportedLedger> {
  return apiFetch<ImportedLedger>('/ledgers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deleteLedger(name: string): Promise<any> {
  return apiFetch(`/ledgers/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

export async function getUserBankConfigs(): Promise<Record<string, string>> {
  return apiFetch<Record<string, string>>('/ledgers/config');
}

export async function setUserBankConfig(
  bankName: string,
  bankLedgerName: string,
  cashLedgerName: string = 'Cash'
): Promise<any> {
  return apiFetch('/ledgers/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bank_name: bankName,
      bank_ledger_name: bankLedgerName,
      cash_ledger_name: cashLedgerName,
    }),
  });
}

// Admin API Methods
export async function getAdminMetrics() {
  return apiFetch<any>('/admin/metrics');
}

export async function getAdminUsers(search?: string) {
  const qs = search ? `?search=${encodeURIComponent(search)}` : '';
  return apiFetch<any[]>(`/admin/users${qs}`);
}

export async function grantUserUnlimited(userId: string) {
  return apiFetch(`/admin/users/${userId}/unlimited`, { method: 'POST' });
}

export async function revokeUserUnlimited(userId: string) {
  return apiFetch(`/admin/users/${userId}/unlimited`, { method: 'DELETE' });
}

export async function getUserQuota(userId: string) {
  return apiFetch<{
    user_id: string;
    mode: 'GLOBAL' | 'CUSTOM';
    custom_daily_limit: number | null;
    effective_daily_limit: number;
    global_daily_limit: number;
  }>(`/admin/users/${userId}/quota`);
}

export async function updateUserQuota(userId: string, payload: { mode: 'GLOBAL' | 'CUSTOM'; custom_daily_limit?: number }) {
  return apiFetch<{ success: boolean; message: string; quota: any }>(`/admin/users/${userId}/quota`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getAdminConversions() {
  return apiFetch<any[]>('/admin/conversions');
}

export async function getAdminSettings() {
  return apiFetch<any>('/admin/settings');
}

export async function updateAdminSettings(settings: any) {
  return apiFetch('/admin/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
}

export async function getAdminParsers() {
  return apiFetch<any[]>('/admin/parsers');
}

export async function getAdminSystemStatus() {
  return apiFetch<any>('/admin/system/status');
}

export async function getAdminLogs(limit: number = 100) {
  return apiFetch<any[]>(`/admin/logs?limit=${limit}`);
}

export async function getAdminLedgerMappings() {
  return apiFetch<any[]>('/admin/accounting/mappings');
}

export async function saveAdminLedgerMapping(data: any) {
  return apiFetch('/admin/accounting/mappings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deleteAdminLedgerMapping(id: string) {
  return apiFetch(`/admin/accounting/mappings/${id}`, {
    method: 'DELETE',
  });
}

export async function getAdminNotifications() {
  return apiFetch<any[]>('/admin/notifications');
}

export async function saveAdminNotification(data: any) {
  return apiFetch('/admin/notifications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deleteAdminNotification(id: string) {
  return apiFetch(`/admin/notifications/${id}`, {
    method: 'DELETE',
  });
}

export async function getAdminAuditFlags() {
  return apiFetch<any[]>('/admin/section-129/flags');
}

export async function updateAdminAuditFlag(flagId: string, data: any) {
  return apiFetch(`/admin/section-129/flags/${flagId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

// Admin Converter API Methods
export async function uploadAdminStatement(
  file: File,
  password?: string,
  bankOverride?: string,
  bankLedgerName?: string,
  cashLedgerName?: string
): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  if (password) formData.append('password', password);
  if (bankOverride) formData.append('bank_override', bankOverride);
  if (bankLedgerName) formData.append('bank_ledger_name', bankLedgerName);
  if (cashLedgerName) formData.append('cash_ledger_name', cashLedgerName);

  const token = getAuthToken();
  const res = await fetch(`${API_BASE}/admin/conversions/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    let err: any = {};
    try {
      err = await res.json();
    } catch {
      err = { message: res.statusText || 'Conversion upload failed' };
    }
    const message =
      err?.message ||
      err?.detail?.message ||
      (typeof err?.detail === 'string' ? err.detail : '') ||
      'Conversion upload failed';
    const code =
      err?.code ||
      err?.detail?.code ||
      (res.status === 401 ? 'ERR_PDF_PASSWORD_REQUIRED' : 'UPLOAD_FAILED');
    const refId = err?.reference_id || err?.detail?.reference_id || '';
    const error: any = new Error(message);
    error.code = code;
    error.reference_id = refId;
    error.status = res.status;
    throw error;
  }

  return res.json();
}

export async function overrideAdminBank(jobId: string, bankName: string): Promise<any> {
  return apiFetch(`/admin/conversions/${jobId}/override-bank`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bank_name: bankName }),
  });
}

export async function reviewAdminTransactions(
  jobId: string,
  transactions: any[],
  bankLedgerName?: string,
  cashLedgerName?: string
): Promise<any> {
  return apiFetch(`/admin/conversions/${jobId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      transactions,
      bank_ledger_name: bankLedgerName,
      cash_ledger_name: cashLedgerName
    }),
  });
}

export async function generateAdminTallyXml(
  jobId: string,
  bankLedgerName?: string,
  cashLedgerName?: string,
  suspenseLedgerName?: string
): Promise<any> {
  return apiFetch(`/admin/conversions/${jobId}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bank_ledger_name: bankLedgerName || 'Bank Account',
      cash_ledger_name: cashLedgerName || 'Cash',
      suspense_ledger_name: suspenseLedgerName || 'Suspense',
      confirm_suspense: true
    }),
  });
}

export async function generateAdminExcel(
  jobId: string,
  bankLedgerName?: string,
  cashLedgerName?: string
): Promise<{ success: boolean; filename: string; download_url: string; voucher_count: number }> {
  return apiFetch(`/admin/conversions/${jobId}/generate-excel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bank_ledger_name: bankLedgerName || 'Bank Account',
      cash_ledger_name: cashLedgerName || 'Cash',
    }),
  });
}

export async function getAdminConversionHistory(): Promise<any[]> {
  return apiFetch<any[]>('/admin/conversions/history');
}

export async function getAdminUserDetails(userId: string): Promise<any> {
  return apiFetch<any>('/admin/users/' + userId);
}

export async function toggleUserSuspension(userId: string): Promise<any> {
  return apiFetch<any>('/admin/users/' + userId + '/toggle-suspend', { method: 'POST' });
}

export async function updateUserAccountStatus(userId: string, status: string, reason?: string): Promise<any> {
  return apiFetch<any>(`/admin/users/${encodeURIComponent(userId)}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, reason }),
  });
}

export async function resetUserDailyUsage(userId: string): Promise<any> {
  return apiFetch<any>('/admin/users/' + userId + '/reset-usage', { method: 'POST' });
}

export async function getConversionDiagnostics(jobId: string): Promise<any> {
  return apiFetch<any>('/admin/conversions/' + jobId + '/diagnostics');
}

export async function getAdminUsageOverview(): Promise<any> {
  return apiFetch<any>('/admin/usage');
}

export async function getAdminProcessingStatus(): Promise<any> {
  return apiFetch<any>('/admin/processing');
}

export async function triggerManualFileCleanup(): Promise<any> {
  return apiFetch<any>('/admin/processing/cleanup', { method: 'POST' });
}

export async function getAdminParsersHealth(): Promise<any[]> {
  return apiFetch<any[]>('/admin/parsers/health');
}

export async function testParserStatementInLab(file: File, password?: string): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  if (password) formData.append('password', password);
  const token = getAuthToken();
  const res = await fetch(`${API_BASE}/admin/parsers/test`, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + token },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Testing lab run failed' }));
    throw new Error(err.detail || err.message || 'Testing lab run failed');
  }
  return res.json();
}

export async function getAdminAccountingRules(): Promise<any> {
  return apiFetch<any>('/admin/accounting');
}

export async function updateAdminNotifications(data: any): Promise<any> {
  return apiFetch<any>('/admin/notifications', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function getAdminAnalytics(): Promise<any> {
  return apiFetch<any>('/admin/analytics');
}

export async function getAdminSecurityOverview(): Promise<any> {
  return apiFetch<any>('/admin/security');
}

export async function getSection129Settings(): Promise<any> {
  return apiFetch<any>('/admin/section-129');
}

export async function updateSection129Settings(data: any): Promise<any> {
  return apiFetch<any>('/admin/section-129', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Email Uniqueness & Duplicate Signup Checks
// ---------------------------------------------------------------------------
export async function checkEmailStatus(email: string, mobileNumber?: string): Promise<{ exists: boolean; verified: boolean; message?: string; pending_active?: boolean; same_mobile?: boolean; remaining_seconds?: number }> {
  try {
    const res = await fetch(`${API_BASE}/auth/check-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), mobile_number: mobileNumber?.trim() }),
    });
    if (res.ok) {
      return res.json();
    }
  } catch {}
  return { exists: false, verified: false };
}

export interface PendingStatusResponse {
  active: boolean;
  email?: string;
  mobile_number?: string;
  full_name?: string;
  masked_email?: string;
  remaining_seconds: number;
  expires_at?: number;
  reason?: string;
}

export interface SupabaseSignupResponse {
  success: boolean;
  status: 'OTP_SENT' | 'PENDING_OTP_ACTIVE';
  message: string;
  email: string;
  mobile_number: string;
  masked_email: string;
  remaining_seconds: number;
  expires_at: number;
}

export async function initiateSupabaseSignup(data: {
  email: string;
  mobile_number: string;
  full_name: string;
  gender?: string;
  password: string;
}): Promise<SupabaseSignupResponse> {
  const res = await fetch(`${API_BASE}/auth/signup/supabase-initiate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Failed to initiate signup verification.');
  }
  return res.json();
}

export async function getSignupPendingStatus(
  email: string,
  mobileNumber?: string
): Promise<PendingStatusResponse> {
  try {
    const q = new URLSearchParams({ email: email.trim() });
    if (mobileNumber) q.append('mobile_number', mobileNumber.trim());
    const res = await fetch(`${API_BASE}/auth/signup/pending-status?${q.toString()}`);
    if (res.ok) {
      return res.json();
    }
  } catch {}
  return { active: false, remaining_seconds: 0 };
}

export async function verifySupabaseEmailOtp(data: {
  email: string;
  otp: string;
  mobile_number?: string;
}): Promise<{ success: boolean; message: string; token: string; refresh_token: string; user: any }> {
  const res = await fetch(`${API_BASE}/auth/signup/verify-email-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Verification code is incorrect or expired.');
  }
  return res.json();
}

export async function resendSupabaseEmailOtp(data: {
  email: string;
  mobile_number?: string;
}): Promise<{ success: boolean; message: string; remaining_seconds: number; expires_at: number; cooldown_seconds: number }> {
  const res = await fetch(`${API_BASE}/auth/signup/resend-email-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Unable to resend verification code right now.');
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Two-Step Account Recovery API Helpers (PRD Sections 24-30)
// ---------------------------------------------------------------------------
export async function getAdminRecoveryRequests(status?: string): Promise<any[]> {
  const q = status && status !== 'ALL' ? `?status=${encodeURIComponent(status)}` : '';
  return apiFetch<any[]>(`/admin/recovery/requests${q}`);
}

export async function adminStep1Review(requestId: string, result: string, notes?: string): Promise<any> {
  return apiFetch<any>(`/admin/recovery/requests/${requestId}/step1`, {
    method: 'POST',
    body: JSON.stringify({ result, notes }),
  });
}

export async function adminSendStep2Code(requestId: string, proposedNewEmail: string): Promise<any> {
  return apiFetch<any>(`/admin/recovery/requests/${requestId}/step2/send-code`, {
    method: 'POST',
    body: JSON.stringify({ proposed_new_email: proposedNewEmail }),
  });
}

export async function adminVerifyStep2Code(requestId: string, otp: string): Promise<any> {
  return apiFetch<any>(`/admin/recovery/requests/${requestId}/step2/verify-code`, {
    method: 'POST',
    body: JSON.stringify({ otp }),
  });
}

export async function adminCompleteRecovery(requestId: string): Promise<any> {
  return apiFetch<any>(`/admin/recovery/requests/${requestId}/complete`, {
    method: 'POST',
  });
}

export async function adminRejectRecovery(requestId: string, reason: string): Promise<any> {
  return apiFetch<any>(`/admin/recovery/requests/${requestId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function adminCreateRecoveryRequest(payload: {
  account_identifier: string;
  reason: string;
  known_email?: string;
  requested_new_email?: string;
}): Promise<any> {
  return apiFetch<any>(`/admin/recovery/requests`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// Account Appeals & Suspension API Helpers (PRD Sections 7, 8, 11-15, 18)
// ---------------------------------------------------------------------------
export async function submitAccountAppeal(payload: {
  email: string;
  user_id?: string;
  user_name?: string;
  subject?: string;
  message: string;
}): Promise<{ success: boolean; request_id: string; message: string; status: string }> {
  const res = await fetch(`${API_BASE}/appeals/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let errorDetail = 'Failed to submit appeal';
    try {
      const err = await res.json();
      errorDetail = typeof err.detail === 'string' ? err.detail : (err.detail?.message || err.message || errorDetail);
    } catch {}
    const err: any = new Error(errorDetail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function getUserAppealStatus(emailOrId: string): Promise<{ has_appeal: boolean; appeal: any }> {
  try {
    const q = encodeURIComponent(emailOrId.trim());
    const res = await fetch(`${API_BASE}/appeals/status?email=${q}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (res.ok) {
      return res.json();
    }
  } catch {}
  return { has_appeal: false, appeal: null };
}

export async function getAdminAppeals(status?: string, search?: string): Promise<any[]> {
  const params = new URLSearchParams();
  if (status && status !== 'ALL') params.set('status', status);
  if (search) params.set('search', search);
  const q = params.toString() ? `?${params.toString()}` : '';
  return apiFetch<any[]>(`/admin/appeals${q}`);
}

export async function getAdminAppealDetails(appealId: string): Promise<any> {
  return apiFetch<any>(`/admin/appeals/${encodeURIComponent(appealId)}`);
}

export async function adminRecoverAppeal(appealId: string): Promise<any> {
  return apiFetch<any>(`/admin/appeals/${encodeURIComponent(appealId)}/recover`, {
    method: 'POST',
  });
}

export async function adminRejectAppeal(appealId: string, reason?: string, adminResponse?: string): Promise<any> {
  return apiFetch<any>(`/admin/appeals/${encodeURIComponent(appealId)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, admin_response: adminResponse || reason }),
  });
}

// ============================================================================
// ADMIN NOTIFICATION CENTER & SUPPORT INQUIRIES API (PRD Section 5-12)
// ============================================================================

export interface UnreadNotificationCounts {
  total_unread: number;
  categories: {
    contact_messages: number;
    account_appeals: number;
    conversion_reviews: number;
    support_requests: number;
  };
}

export interface NotificationFeedItem {
  id: string;
  category: 'CONTACT' | 'APPEAL' | 'REVIEW' | 'RECOVERY' | 'PAYMENT';
  category_label: string;
  title: string;
  snippet: string;
  created_at: string;
  is_read: boolean;
  action_url: string;
  urgency: 'normal' | 'high' | 'urgent';
  metadata?: Record<string, any>;
}

export async function getAdminUnreadCounts(): Promise<UnreadNotificationCounts> {
  return apiFetch<UnreadNotificationCounts>('/admin/notifications/unread-counts');
}

export async function getAdminNotificationsFeed(): Promise<{ items: NotificationFeedItem[] }> {
  return apiFetch<{ items: NotificationFeedItem[] }>('/admin/notifications/feed');
}

export async function markAdminNotificationsRead(payload: {
  notification_id?: string;
  category?: string;
  mark_all?: boolean;
}): Promise<{ success: boolean; counts: UnreadNotificationCounts }> {
  return apiFetch<{ success: boolean; counts: UnreadNotificationCounts }>('/admin/notifications/mark-read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getAdminContactMessages(): Promise<{ messages: any[] }> {
  return apiFetch<{ messages: any[] }>('/admin/contact-messages');
}

export async function deleteAdminContactMessage(messageId: string): Promise<any> {
  return apiFetch<any>(`/admin/contact-messages/${encodeURIComponent(messageId)}`, {
    method: 'DELETE',
  });
}

export async function submitPublicContact(payload: {
  name: string;
  email: string;
  subject_type?: string;
  job_id?: string;
  bank_name?: string;
  message: string;
}): Promise<{ success: boolean; message: string; reference_id: string }> {
  const res = await fetch(`${API_BASE}/system/contact`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let errDetail = 'Failed to submit contact request';
    try {
      const err = await res.json();
      errDetail = err.detail || errDetail;
    } catch {}
    const error: any = new Error(errDetail);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

// ============================================================================
// MANUAL UPI PAYMENT & PAGE QUOTA PURCHASE API (PRD ₹2/page)
// ============================================================================

export async function getPaymentConfig(): Promise<PaymentConfig> {
  return apiFetch<PaymentConfig>('/payments/config');
}

export async function submitPaymentRequest(
  formDataOrPages: FormData | number,
  amount_paid?: number,
  screenshot?: File | null,
  notes?: string,
  job_id?: string
): Promise<PaymentRequest> {
  let body: FormData;
  if (formDataOrPages instanceof FormData) {
    body = formDataOrPages;
  } else {
    body = new FormData();
    body.append('requested_pages', String(formDataOrPages));
    body.append('amount_paid', String(amount_paid || 0));
    if (screenshot) {
      body.append('screenshot', screenshot);
    }
    if (notes) {
      body.append('notes', notes);
    }
    if (job_id) {
      body.append('job_id', job_id);
    }
  }
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/payments/requests`, {
    method: 'POST',
    headers,
    body,
  });
  if (!res.ok) {
    let errDetail = 'Failed to submit payment request';
    try {
      const err = await res.json();
      errDetail = err.detail || errDetail;
    } catch {}
    const error: any = new Error(errDetail);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

export async function getUserPaymentRequests(): Promise<PaymentRequest[]> {
  return apiFetch<PaymentRequest[]>('/payments/requests/me');
}

export async function getAdminPaymentRequests(status?: string): Promise<PaymentRequest[]> {
  const url = status && status !== 'ALL'
    ? `/admin/payments/requests?status=${encodeURIComponent(status)}`
    : '/admin/payments/requests';
  return apiFetch<PaymentRequest[]>(url);
}

export async function approvePaymentRequest(
  requestId: string,
  granted_pages?: number,
  admin_notes?: string
): Promise<{ success: boolean; message: string; request: PaymentRequest; new_balance: number }> {
  return apiFetch<any>(`/admin/payments/requests/${encodeURIComponent(requestId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ granted_pages, admin_notes }),
  });
}

export async function rejectPaymentRequest(
  requestId: string,
  reason?: string
): Promise<{ success: boolean; message: string; request: PaymentRequest }> {
  return apiFetch<any>(`/admin/payments/requests/${encodeURIComponent(requestId)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
}

export async function processRemainingPages(jobId: string): Promise<ConversionJobSummary> {
  return apiFetch<ConversionJobSummary>(`/conversions/${encodeURIComponent(jobId)}/process-remaining`, {
    method: 'POST',
  });
}

export async function getRecentActiveConversion(): Promise<ConversionJobSummary | null> {
  try {
    return await apiFetch<ConversionJobSummary | null>('/conversions/active/recent');
  } catch {
    return null;
  }
}

export async function getMyPaymentRequests(): Promise<PaymentRequest[]> {
  try {
    return await apiFetch<PaymentRequest[]>('/payments/requests/me');
  } catch {
    return [];
  }
}

// ==========================================
// INVOICES (SALES & PURCHASE JPG/PDF TO TALLY XML)
// ==========================================

export interface InvoiceItem {
  id?: string;
  item_index?: number;
  serial?: string;
  description: string;
  item_name: string;
  hsn_sac: string;
  quantity: number;
  invoice_qty?: number;
  pack_multiplier?: number;
  effective_qty?: number;
  shipped_qty?: number;
  billed_qty?: number;
  uom: string;
  invoice_uom?: string;
  tally_uom?: string;
  rate: number;
  discount: number;
  discount_pct?: number;
  discount_amount?: number;
  taxable_amount: number;
  gst_rate?: number;
  cgst_rate: number;
  cgst_amount: number;
  sgst_rate: number;
  sgst_amount: number;
  igst_rate: number;
  igst_amount: number;
  cess_rate: number;
  cess_amount: number;
  total_amount: number;
  confidence?: number;
  confidence_level?: 'HIGH' | 'MEDIUM' | 'LOW';
  matched_stock_item?: string;
  requires_item_creation?: boolean;
  is_description_wrapped?: boolean;
  tax_mode?: 'exclusive' | 'inclusive' | 'unknown';
  is_tax_inclusive?: boolean;
  raw_row_text?: string;
  mrp?: number;
  pack_size?: string;
  item_size?: string;
  free_qty?: number;
  secondary_quantity?: number;
  secondary_unit?: string;
  gross_amount?: number;
  unit_source?: string;
  printed_rate?: number;
  printed_taxable?: number;
  validation_errors?: string[];
  source_text?: string;
  mapping_confidence?: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNMATCHED';
  mapping_status?: 'AUTO_MAPPED' | 'PLEASE_CHECK' | 'POSSIBLE_MATCH' | 'UNMATCHED' | 'NEW_ITEM' | 'VERIFIED';
  match_suggestions?: Array<{
    name: string;
    similarity_score: number;
    confidence: string;
    hsn_code?: string;
    base_units?: string;
  }>;
  quantity_option_a?: number;
  uom_option_a?: string;
  rate_option_a?: number;
  quantity_option_b?: number;
  uom_option_b?: string;
  rate_option_b?: number;
  selected_qty_option?: 'A' | 'B';
  has_dual_qty?: boolean;
  alternate_quantity?: number;
  alternate_uom?: string;
  needs_review?: boolean;
  review_reason?: string;
  is_reconstructed?: boolean;
  math_check_passed?: boolean;
  rate_source?: string;
  gst_rate_source?: string;
  can_convert_to_pieces?: boolean;
  pack_size_multiplier?: number;
  is_converted_to_pieces?: boolean;
  discount_pattern?: string;
  is_free_item?: boolean;
}

export interface PartyInfo {
  name: string;
  gstin: string;
  address?: string;
  state?: string;
  state_code?: string;
  phone?: string;
  email?: string;
  pan?: string;
  role_evidence?: string;
  source_text?: string;
  repaired_gstin?: string;
  matched_ledger_name?: string;
  ledger_type?: string;
  auto_create?: boolean;
  requires_ledger_creation?: boolean;
  mapping_confidence?: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNMATCHED';
  mapping_status?: 'AUTO_MAPPED' | 'PLEASE_CHECK' | 'POSSIBLE_MATCH' | 'UNMATCHED' | 'NEW_LEDGER' | 'VERIFIED';
  match_suggestions?: Array<{
    name: string;
    similarity_score: number;
    confidence: string;
    party_gstin?: string;
    group?: string;
  }>;
}

export interface DetectedGstinCandidate {
  gstin: string;
  suggested_role: string;
  location: string;
  confidence: number;
}

export interface InvoiceValidationViolation {
  rule_id: string;
  field_path: string;
  expected?: string | null;
  actual?: string | null;
  severity: 'ERROR' | 'WARN';
  message: string;
}

export interface InvoiceDocument {
  id: string;
  source_file?: string;
  source_filename?: string;
  page_number?: number;
  page_numbers?: number[];
  doc_type?: string;
  doc_type_evidence?: string;
  invoice_type: 'PURCHASE' | 'SALES';
  type_confidence?: number | string;
  type_rationale?: string;
  is_type_manual_override?: boolean;
  own_company_name?: string;
  own_gstin?: string;
  own_state?: string;
  invoice_number: string;
  bill_number?: string;
  invoice_date: string;
  due_date?: string;
  po_number?: string;
  eway_bill_number?: string;
  irn?: string;
  tax_mode?: 'exclusive' | 'inclusive' | 'unknown';
  tax_mode_evidence?: string;
  supplier: PartyInfo;
  buyer: PartyInfo;
  detected_gstins?: DetectedGstinCandidate[];
  gstin_role_needs_review?: boolean;
  place_of_supply?: string;
  reverse_charge?: boolean;
  items: InvoiceItem[];
  table_columns?: Array<Record<string, any>>;
  page_notes?: string[];
  items_detected_count?: number;
  item_count_reconciliation_note?: string;
  taxable_total: number;
  cgst_total: number;
  sgst_total: number;
  igst_total: number;
  cess_total: number;
  discount_total?: number;
  other_charges?: number;
  round_off: number;
  grand_total: number;
  calculated_total: number;
  discrepancy: number;
  is_balanced: boolean;
  totals?: Record<string, any>;
  field_confidences?: Record<string, number>;
  low_confidence_fields?: string[];
  duplicate_warning?: string | null;
  overall_confidence: number;
  validation_warnings?: string[];
  validation_violations?: InvoiceValidationViolation[];
  errors?: string[];
  warnings?: string[];
  is_valid?: boolean;
  has_page_continuation?: boolean;
  continuation_note?: string;
  narration?: string;
  amount_in_words?: string;
  reconciliation_passed?: boolean;
  reconciliation_flags?: string[];
  needs_review?: boolean;
  ai_extracted?: boolean;
  ai_model_used?: string;
  ai_status_message?: string;
  discount_pattern?: string;
  discount_pattern_note?: string;
  post_tax_discount?: number;
  pack_quantity_option?: 'pieces' | 'bulk';
}

export interface LedgerMappingConfig {
  purchase_ledger: string;
  sales_ledger: string;
  cgst_ledger: string;
  sgst_ledger: string;
  igst_ledger: string;
  cess_ledger: string;
  round_off_ledger: string;
  other_charges_ledger?: string;
  discount_ledger?: string;
}

export interface FinalInvoiceSnapshot {
  invoices: InvoiceDocument[];
  ledger_mapping: LedgerMappingConfig;
  auto_create_items: boolean;
  auto_create_parties: boolean;
}

export interface InvoiceBatchSummary {
  total_documents: number;
  purchase_count?: number;
  sales_count?: number;
  total_purchase_invoices?: number;
  total_sales_invoices?: number;
  total_taxable?: number;
  total_taxable_value?: number;
  total_cgst?: number;
  total_sgst?: number;
  total_igst?: number;
  total_cess?: number;
  total_grand?: number;
  total_invoice_value?: number;
  missing_masters_count?: number;
  items_requiring_creation_count?: number;
  parties_requiring_creation_count?: number;
  has_discrepancies?: boolean;
}

export interface InvoiceBatchResult {
  job_id: string;
  invoices: InvoiceDocument[];
  summary: InvoiceBatchSummary;
  ledger_mapping: LedgerMappingConfig;
}

export interface InvoiceXmlGenerationResult {
  success: boolean;
  filename: string;
  is_valid: boolean;
  validation_errors: string[];
  xml_content: string;
  summary: InvoiceBatchSummary;
}

export async function getInvoiceConfig(): Promise<{
  default_ledger_mapping: LedgerMappingConfig;
  supported_file_types: string[];
  max_upload_size_mb: number;
}> {
  return apiFetch('/invoices/config');
}

export async function uploadInvoices(
  files: File[],
  defaultInvoiceType: 'AUTO' | 'PURCHASE' | 'SALES' = 'AUTO'
): Promise<InvoiceBatchResult> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  formData.append('default_invoice_type', defaultInvoiceType);

  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/invoices/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    let errDetail = 'Failed to process invoice files';
    try {
      const err = await res.json();
      errDetail = err.detail || err.message || errDetail;
    } catch {}
    const error: any = new Error(errDetail);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

export async function validateInvoices(
  snapshot: FinalInvoiceSnapshot
): Promise<InvoiceBatchResult> {
  return apiFetch<InvoiceBatchResult>('/invoices/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshot),
  });
}

export async function generateInvoiceXml(
  snapshot: FinalInvoiceSnapshot
): Promise<InvoiceXmlGenerationResult> {
  return apiFetch<InvoiceXmlGenerationResult>('/invoices/generate-xml', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshot),
  });
}

export async function downloadInvoiceXml(
  snapshot: FinalInvoiceSnapshot
): Promise<{ blob: Blob; filename: string }> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/invoices/download-xml`, {
    method: 'POST',
    headers,
    body: JSON.stringify(snapshot),
  });

  if (!res.ok) {
    let errDetail = 'Failed to download Tally XML';
    try {
      const err = await res.json();
      errDetail = err.detail || err.message || errDetail;
    } catch {}
    const error: any = new Error(errDetail);
    error.status = res.status;
    throw error;
  }

  const cd = res.headers.get('Content-Disposition') || '';
  let filename = 'KangraHub_Invoices_Tally.xml';
  const match = cd.match(/filename="?([^";]+)"?/);
  if (match && match[1]) {
    filename = match[1];
  }

  const blob = await res.blob();
  return { blob, filename };
}

// ==========================================
// STOCK ITEMS (TALLY STOCK MASTERS IMPORT & MATCHING)
// ==========================================

export interface ImportedStockItem {
  name: string;
  normalized_name: string;
  parent?: string;
  base_units: string;
  additional_units?: string;
  hsn_code?: string;
  gst_rate?: number;
  gst_type_of_supply?: string;
  description?: string;
  guid?: string;
  source_format?: string;
}

export interface StockItemImportResult {
  detected_format: string;
  total_imported: number;
  items: ImportedStockItem[];
  duplicates: number;
  conflicts: string[];
  error?: string;
}

export interface StockItemMatchSuggestion {
  invoice_item_name: string;
  matched_stock_item?: ImportedStockItem;
  similarity_score: number;
  match_type: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
}

export async function importStockItems(file: File): Promise<StockItemImportResult> {
  const formData = new FormData();
  formData.append('file', file);
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/stock-items/import`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    let errDetail = 'Failed to import stock items file.';
    try {
      const err = await res.json();
      errDetail = err.detail || err.message || errDetail;
    } catch {}
    const error: any = new Error(errDetail);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

export async function listStockItems(search?: string, limit: number = 50): Promise<ImportedStockItem[]> {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  params.append('limit', limit.toString());
  return apiFetch<ImportedStockItem[]>(`/stock-items?${params.toString()}`);
}

export async function matchStockItemsBatch(
  items: Array<{ name: string; hsn?: string }>
): Promise<StockItemMatchSuggestion[]> {
  return apiFetch<StockItemMatchSuggestion[]>('/stock-items/match', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  });
}

export interface StockGroupItem {
  name: string;
  item_count: number;
}

export interface StockUnitItem {
  name: string;
  item_count: number;
}

export async function getStockItemGroups(): Promise<StockGroupItem[]> {
  return apiFetch<StockGroupItem[]>('/stock-items/groups');
}

export async function getStockItemUnits(): Promise<StockUnitItem[]> {
  return apiFetch<StockUnitItem[]>('/stock-items/units');
}

export async function createNewStockItem(data: {
  name: string;
  hsn?: string;
  hsn_description?: string;
  uom?: string;
  parent_group?: string;
  gst_rate?: number;
  taxability?: string;
  type_of_supply?: string;
  additional_units?: string;
  conversion?: number;
}): Promise<{ success: boolean; item: ImportedStockItem; xml_snippet: string }> {
  return apiFetch('/stock-items/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export interface StockItemTallyPreview {
  name: string;
  parent_group: string;
  base_unit: string;
  alternate_unit?: string | null;
  has_alternate_units?: boolean;
  conversion?: number | null;
  conversion_formula?: string | null;
  hsn_code?: string | null;
  hsn_description?: string | null;
  hsn_source: string;
  taxability: string;
  gst_applicability?: string;
  gst_source: string;
  gst_rate_source?: string;
  gst_rate: number;
  cgst_rate: number;
  sgst_rate: number;
  type_of_supply: string;
}

export async function getStockItemTallyPreview(data: {
  name: string;
  hsn?: string;
  hsn_description?: string;
  uom?: string;
  parent_group?: string;
  gst_rate?: number;
  taxability?: string;
  type_of_supply?: string;
  additional_units?: string;
  conversion?: number;
}): Promise<{ success: boolean; preview: StockItemTallyPreview; xml_snippet: string }> {
  return apiFetch('/stock-items/tally-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export interface LedgerTallyPreview {
  name: string;
  parent_group: string;
  state: string;
  country: string;
  pan?: string | null;
  gstin?: string | null;
  registration_type: string;
  pincode?: string | null;
  address_lines: string[];
}

export async function getLedgerTallyPreview(data: {
  name: string;
  alias?: string;
  parent_group?: string;
  address_lines?: string[];
  state?: string;
  country?: string;
  pincode?: string;
  gstin?: string;
  pan?: string;
  registration_type?: string;
}): Promise<{ success: boolean; preview: LedgerTallyPreview; xml_snippet: string }> {
  return apiFetch('/ledgers/tally-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function createLedgerMaster(data: {
  name: string;
  alias?: string;
  parent_group?: string;
  address_lines?: string[];
  state?: string;
  country?: string;
  pincode?: string;
  gstin?: string;
  pan?: string;
  registration_type?: string;
}): Promise<{ success: boolean; ledger: any; xml_snippet: string }> {
  return apiFetch('/ledgers/create-master', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

// ==========================================
// USER PROFILE & REVIEWS
// ==========================================

export interface UserProfileData {
  id: string;
  email: string;
  full_name: string;
  mobile_number?: string;
  gender?: string;
  role: string;
  is_unlimited: boolean;
  is_staff?: boolean;
  is_gold?: boolean;
  staff_source?: string;
  subscription_expiry?: string;
  account_status?: string;
  email_verified?: boolean;
  avatar_url?: string;
  created_at?: string;
}

export interface ReviewItem {
  id: string;
  user_id?: string;
  user_name: string;
  user_email?: string;
  masked_email?: string;
  rating: number;
  review_text?: string;
  moderation_status?: string;
  created_at: string;
}

export interface PublicReviewsResponse {
  average_rating: number;
  total_reviews: number;
  stars_breakdown: Record<string, number>;
  reviews: ReviewItem[];
}

export async function getUserProfile(): Promise<UserProfileData> {
  return apiFetch<UserProfileData>('/auth/me');
}

export async function updateUserProfile(payload: {
  full_name?: string;
  mobile_number?: string;
  gender?: string;
}): Promise<{ success: boolean; message: string; user: UserProfileData }> {
  return apiFetch('/auth/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function uploadProfilePicture(file: File): Promise<{ success: boolean; avatar_url: string; message: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/auth/profile/picture`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) {
    let errMessage = 'Failed to upload profile picture';
    try {
      const err = await res.json();
      errMessage = err.detail || err.message || errMessage;
    } catch {}
    throw new Error(errMessage);
  }
  return res.json();
}

export async function removeProfilePicture(): Promise<{ success: boolean; avatar_url: null; message: string }> {
  return apiFetch('/auth/profile/picture', {
    method: 'DELETE',
  });
}

export async function submitReview(payload: {
  rating: number;
  review_text?: string;
}): Promise<{ success: boolean; message: string; review_id: string; rating: number }> {
  return apiFetch('/reviews', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getMyReview(): Promise<{ has_review: boolean; review: ReviewItem | null }> {
  return apiFetch('/reviews/my');
}

export async function getPublicReviews(limit: number = 20): Promise<PublicReviewsResponse> {
  return apiFetch<PublicReviewsResponse>(`/reviews/public?limit=${limit}`);
}

// ==========================================
// MAIN WEBSITE ADMIN DASHBOARD APIS
// ==========================================

export interface WebsiteAdminUser {
  id: string;
  email: string;
  full_name: string;
  mobile_number: string;
  gender: string;
  role: string;
  is_unlimited: boolean;
  account_status: string;
  email_verified: boolean;
  mobile_verified: boolean;
  registration_date: string;
  last_login?: string;
  total_conversions: number;
}

export interface UserActivityLog {
  id: string;
  user_id: string;
  user_email: string;
  action: string;
  module: string;
  resource_id?: string;
  status: string;
  metadata?: any;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}

export interface SecurityAuditLog {
  id: string;
  actor_id?: string;
  actor_email?: string;
  event_type: string;
  severity: string;
  module?: string;
  details?: any;
  ip_address?: string;
  created_at: string;
}

export interface AdminSystemNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  severity: string;
  is_read: number;
  related_user_id?: string;
  created_at: string;
}

export async function getAdminWebsiteUsers(search?: string, status?: string): Promise<{ users: WebsiteAdminUser[]; total: number }> {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (status) params.append('status', status);
  return apiFetch(`/admin/website-users?${params.toString()}`);
}

export async function getAdminUserActivity(userId: string, limit: number = 50): Promise<{ user_id: string; user: any; activities: UserActivityLog[] }> {
  return apiFetch(`/admin/users/${encodeURIComponent(userId)}/activity?limit=${limit}`);
}

export async function getAdminActivityLogs(params?: {
  user_id?: string;
  action?: string;
  module?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<{ logs: UserActivityLog[]; count: number }> {
  const q = new URLSearchParams();
  if (params?.user_id) q.append('user_id', params.user_id);
  if (params?.action) q.append('action', params.action);
  if (params?.module) q.append('module', params.module);
  if (params?.status) q.append('status', params.status);
  if (params?.limit) q.append('limit', params.limit.toString());
  if (params?.offset) q.append('offset', params.offset.toString());
  return apiFetch(`/admin/activity-logs?${q.toString()}`);
}

export async function getAdminSecurityLogs(params?: {
  severity?: string;
  limit?: number;
  offset?: number;
}): Promise<{ logs: SecurityAuditLog[]; count: number }> {
  const q = new URLSearchParams();
  if (params?.severity) q.append('severity', params.severity);
  if (params?.limit) q.append('limit', params.limit.toString());
  if (params?.offset) q.append('offset', params.offset.toString());
  return apiFetch(`/admin/security-audit-logs?${q.toString()}`);
}

export async function getAdminReviews(status?: string, limit: number = 100): Promise<{ reviews: ReviewItem[]; total: number; average_rating: number }> {
  const q = new URLSearchParams();
  if (status) q.append('status', status);
  q.append('limit', limit.toString());
  return apiFetch(`/admin/reviews?${q.toString()}`);
}

export async function moderateReview(reviewId: string, status: string, notes?: string): Promise<{ success: boolean; message: string }> {
  return apiFetch(`/admin/reviews/${encodeURIComponent(reviewId)}/moderate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, notes }),
  });
}

export async function getAdminSystemNotifications(unreadOnly: boolean = false, limit: number = 50): Promise<{ notifications: AdminSystemNotification[]; count: number }> {
  return apiFetch(`/admin/system-notifications?unread_only=${unreadOnly}&limit=${limit}`);
}

export async function markAdminSystemNotificationRead(notifId: string): Promise<{ success: boolean; notification_id: string }> {
  return apiFetch(`/admin/system-notifications/${encodeURIComponent(notifId)}/read`, {
    method: 'POST',
  });
}

// ==========================================
// STAFF MANAGEMENT & ANTI-ABUSE APIs
// ==========================================

export interface StaffUserItem {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_unlimited: boolean;
  is_gold: boolean;
  staff_source: string;
  subscription_expiry?: string;
  account_status: string;
  registration_date?: string;
}

export interface StaffAuditLogItem {
  id: string;
  admin_id: string;
  admin_name: string;
  action: string;
  target_user_id: string;
  target_user_email: string;
  details: string;
  created_at: string;
}

export interface SuspiciousActivityItem {
  type: string;
  severity: string;
  details: string;
  timestamp: string;
  device_id?: string;
  accounts_count?: number;
  bill_number?: string;
  company_name?: string;
}

export async function getStaffList(): Promise<{ success: boolean; count: number; staff: StaffUserItem[] }> {
  return apiFetch('/staff/list');
}

export async function addStaffMember(payload: {
  user_id_or_email: string;
  is_gold?: boolean;
  expiry_days?: number;
  notes?: string;
}): Promise<{ success: boolean; message: string; role: string; is_gold: boolean }> {
  return apiFetch('/staff/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function removeStaffMember(payload: {
  user_id_or_email: string;
  reason?: string;
}): Promise<{ success: boolean; message: string }> {
  return apiFetch('/staff/remove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function toggleGoldTick(payload: {
  user_id: string;
  is_gold: boolean;
}): Promise<{ success: boolean; message: string; is_gold: boolean }> {
  return apiFetch('/staff/toggle-gold', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function extendStaffExpiry(payload: {
  user_id: string;
  days: number;
}): Promise<{ success: boolean; message: string }> {
  return apiFetch('/staff/extend-expiry', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getStaffAuditLogs(limit: number = 50, offset: number = 0): Promise<{ success: boolean; logs: StaffAuditLogItem[] }> {
  return apiFetch(`/staff/audit-logs?limit=${limit}&offset=${offset}`);
}

export async function getSuspiciousActivity(): Promise<{ success: boolean; signals: SuspiciousActivityItem[] }> {
  return apiFetch('/staff/suspicious-activity');
}

export async function whitelistDevice(payload: {
  device_id: string;
  is_whitelisted: boolean;
}): Promise<{ success: boolean; message: string }> {
  return apiFetch('/staff/whitelist-device', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

// ==========================================
// SUBSCRIPTION & VERIFIED TIER APIs
// ==========================================

export interface UserSubscriptionItem {
  id: string;
  user_id: string;
  user_email: string;
  plan_name: string;
  amount: number;
  status: 'PENDING' | 'ACTIVE' | 'EXPIRED' | 'REJECTED';
  payment_method: string;
  txn_id?: string;
  start_date?: string;
  end_date?: string;
  grace_until?: string;
  created_at: string;
  admin_notes?: string;
}

export interface StaffMembershipRecord {
  id: string;
  user_id: string;
  user_email?: string;
  staff_status: 'ACTIVE' | 'EXPIRED' | 'INACTIVE';
  membership_started_at: string;
  membership_expires_at: string;
  last_valid_day: string;
  display_wording: string;
  is_gold?: number | boolean;
  is_active?: boolean;
}

export interface RenewalHistoryItem {
  id: string;
  payment_id: string;
  renewal_type: 'NEW' | 'EARLY_RENEWAL' | 'RENEWAL_AFTER_EXPIRY';
  previous_expiry?: string;
  new_expiry: string;
  days_added: number;
  created_at: string;
}

export interface StaffMembershipResponse {
  success: boolean;
  is_staff: boolean;
  is_gold: boolean;
  staff_status: 'ACTIVE' | 'EXPIRED' | 'INACTIVE';
  staff_source?: string;
  membership?: StaffMembershipRecord;
  renewal_history?: RenewalHistoryItem[];
  notification_alert?: {
    milestone: string;
    message: string;
    is_new: boolean;
  };
  config?: {
    price_inr: number;
    price_paise: number;
    duration_days: number;
    payment_button_id: string;
  };
}

export async function getMySubscription(): Promise<StaffMembershipResponse> {
  return apiFetch('/subscriptions/my');
}

export async function verifyRazorpayPayment(payload: {
  payment_id: string;
  order_id?: string;
  signature?: string;
}): Promise<{
  success: boolean;
  idempotent?: boolean;
  message: string;
  renewal_type?: string;
  membership_expires_at?: string;
  display_wording?: string;
  payment_id?: string;
}> {
  return apiFetch('/subscriptions/razorpay/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function submitManualSubscription(formData: FormData): Promise<{
  success: boolean;
  subscription_id: string;
  status: string;
  message: string;
}> {
  return apiFetch('/subscriptions/manual-qr', {
    method: 'POST',
    body: formData,
  });
}

export async function getAdminSubscriptions(): Promise<{
  success: boolean;
  count: number;
  subscriptions: UserSubscriptionItem[];
}> {
  return apiFetch('/subscriptions/admin/list');
}

export async function approveSubscription(payload: {
  subscription_id: string;
  admin_notes?: string;
}): Promise<{ success: boolean; message: string; end_date: string; grace_until: string }> {
  return apiFetch('/subscriptions/admin/approve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function rejectSubscription(payload: {
  subscription_id: string;
  admin_notes: string;
}): Promise<{ success: boolean; message: string }> {
  return apiFetch('/subscriptions/admin/reject', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export interface PaymentOrderResponse {
  orderId: string;
  amount: number;
  currency: string;
  keyId: string;
}

export interface CreatePaymentOrderPayload {
  planId?: string;
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
}

export async function createPaymentOrder(payload?: CreatePaymentOrderPayload): Promise<PaymentOrderResponse> {
  return apiFetch('/payments/create-order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || { planId: 'gold_monthly' }),
  });
}

export async function verifyPayment(payload: {
  razorpay_payment_id: string;
  razorpay_order_id?: string;
  razorpay_signature?: string;
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
}): Promise<{
  ok: boolean;
  success: boolean;
  message: string;
  membership_expires_at?: string;
  last_valid_day?: string;
  display_wording?: string;
  payment_id?: string;
}> {
  return apiFetch('/payments/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
