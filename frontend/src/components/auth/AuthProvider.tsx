'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getAuthToken, setAuthToken, clearAuthToken, getUserRole, getRefreshToken, getUserProfile } from '@/lib/api';
import { getSupabaseClient } from '@/lib/supabaseClient';

export interface UserSession {
  id: string;
  email: string;
  role: 'ADMIN' | 'STAFF' | 'USER';
  fullName?: string;
  mobileNumber?: string;
  gender?: string;
  emailVerified?: boolean;
  isStaff?: boolean;
  isGold?: boolean;
  staffSource?: string;
  subscriptionExpiry?: string;
  isExpired?: boolean;
  avatarUrl?: string;
}

interface AuthContextType {
  token: string | null;
  user: UserSession | null;
  isAdmin: boolean;
  isStaff: boolean;
  isGold: boolean;
  isExpired: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, isAdmin?: boolean, refreshToken?: string, user?: any) => void;
  logout: () => void;
  refreshSession: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  user: null,
  isAdmin: false,
  isStaff: false,
  isGold: false,
  isExpired: false,
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: () => {},
  refreshSession: async () => {},
  refreshProfile: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [user, setUser] = useState<UserSession | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const syncStateFromStorage = useCallback(() => {
    if (typeof window === 'undefined') return;
    const storedToken = localStorage.getItem('kh_auth_token');
    if (!storedToken) {
      setTokenState(null);
      setUser(null);
      setIsAdmin(false);
    }
  }, []);

  const initAuth = useCallback(async () => {
    try {
      if (typeof window === 'undefined') {
        setIsLoading(false);
        return;
      }

      const storedToken = getAuthToken();
      if (!storedToken) {
        clearAuthToken();
        setTokenState(null);
        setUser(null);
        setIsAdmin(false);
        setIsLoading(false);
        return;
      }

      // Strictly validate the session token against backend /api/auth/me
      try {
        const profile = await getUserProfile();
        if (
          profile &&
          profile.id &&
          profile.account_status !== 'SUSPENDED' &&
          profile.account_status !== 'BLOCKED' &&
          profile.account_status !== 'DEACTIVATED'
        ) {
          const isUserAdmin = profile.role === 'ADMIN' || profile.role === 'SUPER_ADMIN';
          const isExpired = !isUserAdmin && !!profile.subscription_expiry && new Date(profile.subscription_expiry) < new Date();
          const isUserStaff = isUserAdmin || ((profile.role === 'STAFF' || !!profile.is_staff || profile.staff_source === 'RAZORPAY_STAFF') && !isExpired);
          const userObj: UserSession = {
            id: profile.id,
            email: profile.email,
            role: isUserAdmin ? 'ADMIN' : ((profile.role === 'STAFF' || !!profile.is_staff || profile.staff_source === 'RAZORPAY_STAFF') ? (isExpired ? 'USER' : 'STAFF') : 'USER'),
            fullName: profile.full_name || '',
            mobileNumber: profile.mobile_number || '',
            gender: profile.gender || '',
            emailVerified: profile.email_verified,
            isStaff: isUserStaff,
            isGold: isUserAdmin || isUserStaff || (!!profile.is_gold && !isExpired),
            staffSource: profile.staff_source,
            subscriptionExpiry: profile.subscription_expiry,
            isExpired: isExpired,
            avatarUrl: profile.avatar_url || '',
          };
          setTokenState(storedToken);
          setUser(userObj);
          setIsAdmin(isUserAdmin);
        } else {
          // Account suspended, deactivated, or invalid profile
          clearAuthToken();
          setTokenState(null);
          setUser(null);
          setIsAdmin(false);
        }
      } catch {
        // Backend returned 401 or token is invalid/expired -> strictly revoke session
        clearAuthToken();
        setTokenState(null);
        setUser(null);
        setIsAdmin(false);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    initAuth();

    const handleAuthChanged = () => {
      syncStateFromStorage();
    };
    window.addEventListener('kh_auth_changed', handleAuthChanged);
    window.addEventListener('storage', handleAuthChanged);

    const supabase = getSupabaseClient();
    let sbSubscription: any = null;
    if (supabase) {
      const { data } = supabase.auth.onAuthStateChange((event) => {
        if (event === 'SIGNED_OUT') {
          clearAuthToken();
          setTokenState(null);
          setUser(null);
          setIsAdmin(false);
        }
      });
      sbSubscription = data?.subscription;
    }

    return () => {
      window.removeEventListener('kh_auth_changed', handleAuthChanged);
      window.removeEventListener('storage', handleAuthChanged);
      if (sbSubscription) {
        sbSubscription.unsubscribe();
      }
    };
  }, [initAuth, syncStateFromStorage]);

  const login = (newToken: string, isUserAdmin: boolean = false, refreshToken?: string, userData?: any) => {
    if (!newToken || typeof newToken !== 'string' || newToken.trim().length === 0) {
      clearAuthToken();
      setTokenState(null);
      setUser(null);
      setIsAdmin(false);
      setIsLoading(false);
      return;
    }
    setAuthToken(newToken, isUserAdmin, refreshToken);
    setTokenState(newToken);
    setIsAdmin(isUserAdmin);
    if (userData) {
      const isRoleAdmin = isUserAdmin || userData.role === 'ADMIN' || userData.role === 'SUPER_ADMIN';
      const subExpiry = userData.subscription_expiry || userData.subscriptionExpiry;
      const isExpired = !isRoleAdmin && !!subExpiry && new Date(subExpiry) < new Date();
      const isRoleStaff = isRoleAdmin || ((userData.role === 'STAFF' || !!userData.is_staff || !!userData.isStaff) && !isExpired);
      setUser({
        id: userData.id || userData.user_id || '',
        email: userData.email || '',
        role: isRoleAdmin ? 'ADMIN' : (userData.role === 'STAFF' ? (isExpired ? 'USER' : 'STAFF') : 'USER'),
        fullName: userData.full_name || userData.fullName || userData.user_metadata?.full_name || userData.user_metadata?.name || '',
        mobileNumber: userData.mobile_number || userData.mobileNumber || userData.user_metadata?.mobile_number || userData.user_metadata?.phone || userData.phone || '',
        gender: userData.gender || userData.user_metadata?.gender || '',
        emailVerified: userData.email_verified,
        isStaff: isRoleStaff,
        isGold: isRoleAdmin || ((!!userData.is_gold || !!userData.isGold) && !isExpired),
        staffSource: userData.staff_source || userData.staffSource,
        subscriptionExpiry: subExpiry,
        isExpired: isExpired,
      });
    }
    setIsLoading(false);
  };

  const logout = () => {
    const supabase = getSupabaseClient();
    if (supabase) {
      supabase.auth.signOut().catch(() => {});
    }
    clearAuthToken();
    setTokenState(null);
    setUser(null);
    setIsAdmin(false);
    setIsLoading(false);
  };

  const refreshSession = async () => {
    const supabase = getSupabaseClient();
    if (supabase) {
      const { data } = await supabase.auth.refreshSession();
      if (data?.session) {
        const isUserAdmin = data.session.user?.user_metadata?.role === 'ADMIN' || isAdmin;
        login(data.session.access_token, isUserAdmin, data.session.refresh_token, data.session.user);
      }
    }
  };

  const isStaffComputed = isAdmin || (!!user?.isStaff && !user?.isExpired) || (user?.role === 'STAFF' && !user?.isExpired);
  const isGoldComputed = isAdmin || (!!user?.isGold && !user?.isExpired);
  const isExpiredComputed = !isAdmin && !!user?.isExpired;

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAdmin,
        isStaff: isStaffComputed,
        isGold: isGoldComputed,
        isExpired: isExpiredComputed,
        isAuthenticated: !!token,
        isLoading,
        login,
        logout,
        refreshSession,
        refreshProfile: initAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
