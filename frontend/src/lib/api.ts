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
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  if (!res.ok) {
    let errData: any = {};
    let errorDetail = 'Authentication failed';
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
  if (data.token) {
    setAuthToken(data.token, data.user?.role === 'ADMIN', data.refresh_token);
  }
  return data;
}

export async function adminLogin(email: string, password: string): Promise<{ token: string; is_admin: boolean; user: any }> {
  const res = await fetch(`${API_BASE}/system/admin-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  if (!res.ok) {
    let errorDetail = 'Authentication failed';
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
export async function getPublicSettings(): Promise<PublicSettings> {
  return apiFetch<PublicSettings>('/system/public-settings');
}

export async function getSupportedBanks(): Promise<BankInfo[]> {
  return apiFetch<BankInfo[]>('/banks');
}

export async function getUserUsage(): Promise<UsageInfo> {
  return apiFetch<UsageInfo>('/usage');
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
  const res = await fetch(`${API_BASE}/ledgers/import`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to import ledgers' }));
    throw new Error(err.detail || 'Failed to import ledgers');
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
export async function checkEmailStatus(email: string): Promise<{ exists: boolean; verified: boolean; message?: string }> {
  try {
    const res = await fetch(`${API_BASE}/auth/check-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim() }),
    });
    if (res.ok) {
      return res.json();
    }
  } catch {}
  return { exists: false, verified: false };
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





