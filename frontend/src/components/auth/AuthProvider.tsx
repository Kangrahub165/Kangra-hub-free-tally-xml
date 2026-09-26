'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getAuthToken, setAuthToken, clearAuthToken, getUserRole, getRefreshToken } from '@/lib/api';
import { getSupabaseClient } from '@/lib/supabaseClient';

export interface UserSession {
  id: string;
  email: string;
  role: 'ADMIN' | 'USER';
  fullName?: string;
}

interface AuthContextType {
  token: string | null;
  user: UserSession | null;
  isAdmin: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, isAdmin?: boolean, refreshToken?: string, user?: any) => void;
  logout: () => void;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  user: null,
  isAdmin: false,
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: () => {},
  refreshSession: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [user, setUser] = useState<UserSession | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const syncStateFromStorage = useCallback(() => {
    if (typeof window === 'undefined') return;
    const storedToken = localStorage.getItem('kh_auth_token');
    const storedRole = getUserRole();
    const isUserAdmin = storedRole === 'ADMIN';

    if (storedToken) {
      setTokenState(storedToken);
      setIsAdmin(isUserAdmin);
      const isSecure = window.location.protocol === 'https:';
      const secureFlag = isSecure ? '; Secure' : '';
      document.cookie = `kh_auth_token=${encodeURIComponent(storedToken)}; path=/; max-age=604800; SameSite=Lax${secureFlag}`;
      if (isUserAdmin) {
        document.cookie = `kh_is_admin=true; path=/; max-age=604800; SameSite=Lax${secureFlag}`;
      }
    } else {
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

      // 1. Initial quick local check from storage
      const existingToken = localStorage.getItem('kh_auth_token');
      const storedRole = getUserRole();
      const initialIsAdmin = storedRole === 'ADMIN';

      if (existingToken) {
        setTokenState(existingToken);
        setIsAdmin(initialIsAdmin);
        // Ensure cookies match storage
        const isSecure = window.location.protocol === 'https:';
        const secureFlag = isSecure ? '; Secure' : '';
        document.cookie = `kh_auth_token=${encodeURIComponent(existingToken)}; path=/; max-age=604800; SameSite=Lax${secureFlag}`;
        if (initialIsAdmin) {
          document.cookie = `kh_is_admin=true; path=/; max-age=604800; SameSite=Lax${secureFlag}`;
        }
      }

      // 2. Query Supabase client if configured
      const supabase = getSupabaseClient();
      if (supabase) {
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (session && session.access_token) {
            const role = (session.user?.user_metadata?.role === 'ADMIN' || storedRole === 'ADMIN') ? 'ADMIN' : 'USER';
            const userObj: UserSession = {
              id: session.user.id,
              email: session.user.email || '',
              role: role,
              fullName: session.user.user_metadata?.full_name || '',
            };
            setAuthToken(session.access_token, role === 'ADMIN', session.refresh_token);
            setTokenState(session.access_token);
            setUser(userObj);
            setIsAdmin(role === 'ADMIN');
          } else if (!existingToken) {
            setTokenState(null);
            setUser(null);
            setIsAdmin(false);
          }
        } catch (sbErr) {
          console.warn('Error querying Supabase session:', sbErr);
        }

        // 3. Register real-time auth listener for token renewals and sign-ins/outs
        const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
          if (session && session.access_token) {
            const role = (session.user?.user_metadata?.role === 'ADMIN' || getUserRole() === 'ADMIN') ? 'ADMIN' : 'USER';
            setAuthToken(session.access_token, role === 'ADMIN', session.refresh_token);
            setTokenState(session.access_token);
            setIsAdmin(role === 'ADMIN');
            setUser({
              id: session.user.id,
              email: session.user.email || '',
              role: role,
              fullName: session.user.user_metadata?.full_name || '',
            });
          } else if (event === 'SIGNED_OUT') {
            clearAuthToken();
            setTokenState(null);
            setUser(null);
            setIsAdmin(false);
          }
        });

        return () => {
          subscription.unsubscribe();
        };
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let cleanup: (() => void) | undefined;
    initAuth().then((c) => {
      cleanup = c;
    });

    const handleAuthChanged = () => {
      syncStateFromStorage();
    };
    window.addEventListener('kh_auth_changed', handleAuthChanged);
    window.addEventListener('storage', handleAuthChanged);

    return () => {
      if (cleanup) cleanup();
      window.removeEventListener('kh_auth_changed', handleAuthChanged);
      window.removeEventListener('storage', handleAuthChanged);
    };
  }, [initAuth, syncStateFromStorage]);

  const login = (newToken: string, isUserAdmin: boolean = false, refreshToken?: string, userData?: any) => {
    setAuthToken(newToken, isUserAdmin, refreshToken);
    setTokenState(newToken);
    setIsAdmin(isUserAdmin);
    if (userData) {
      setUser({
        id: userData.id || userData.user_id || '',
        email: userData.email || '',
        role: isUserAdmin ? 'ADMIN' : 'USER',
        fullName: userData.full_name || userData.fullName || '',
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

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAdmin,
        isAuthenticated: !!token,
        isLoading,
        login,
        logout,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
