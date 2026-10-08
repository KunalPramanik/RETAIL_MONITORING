"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { safeFetch } from "./api-client";

export interface AuthUser {
  id: string;
  user_id: string;
  email: string;
  username: string;
  role: "ADMIN" | "SUPERVISOR" | "VIEWER" | string;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (identifier: string, password: string, remember?: boolean) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = "secops_token";
const USER_KEY = "secops_user";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  const fetchProfile = useCallback(async (authToken: string): Promise<AuthUser | null> => {
    try {
      const res = await safeFetch("/api/auth/me", {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        const profile: AuthUser = {
          id: data.id || data.user_id,
          user_id: data.user_id || data.id,
          email: data.email,
          username: data.username || data.email,
          role: data.role || "VIEWER",
        };
        setUser(profile);
        try {
          localStorage.setItem(USER_KEY, JSON.stringify(profile));
        } catch (_) {}
        return profile;
      } else {
        if (res.status === 401 || res.status === 403) {
          // Token invalid or expired
          try {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
          } catch (_) {}
          setToken(null);
          setUser(null);
        }
        return null;
      }
    } catch (err) {
      console.warn("[SEC-OPS Auth] Profile fetch error:", err);
      return null;
    }
  }, []);

  // Initialize from localStorage on mount
  useEffect(() => {
    let storedToken: string | null = null;
    let cachedUser: AuthUser | null = null;

    try {
      storedToken = localStorage.getItem(TOKEN_KEY);
      const cached = localStorage.getItem(USER_KEY);
      if (cached) {
        cachedUser = JSON.parse(cached);
      }
    } catch (_) {}

    if (storedToken) {
      setToken(storedToken);
      if (cachedUser) {
        setUser(cachedUser);
      }
      fetchProfile(storedToken).finally(() => {
        setIsLoading(false);
      });
    } else {
      setIsLoading(false);
    }

    // Listen for unauthorized events dispatched by API client
    const handleUnauthorized = () => {
      try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      } catch (_) {}
      setToken(null);
      setUser(null);
      router.push("/login");
    };

    window.addEventListener("secops:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("secops:unauthorized", handleUnauthorized);
    };
  }, [fetchProfile, router]);

  const login = async (
    identifier: string,
    password: string,
    remember: boolean = true
  ): Promise<{ success: boolean; error?: string }> => {
    setIsLoading(true);
    try {
      const res = await safeFetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: identifier.trim(),
          password: password,
        }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setIsLoading(false);
        const errMsg = data?.detail || data?.message || "Authentication failed. Please check your credentials.";
        return { success: false, error: errMsg };
      }

      const receivedToken = data.access_token;
      if (!receivedToken) {
        setIsLoading(false);
        return { success: false, error: "Invalid response from authentication server." };
      }

      setToken(receivedToken);
      if (remember) {
        try {
          localStorage.setItem(TOKEN_KEY, receivedToken);
        } catch (_) {}
      } else {
        try {
          sessionStorage.setItem(TOKEN_KEY, receivedToken);
        } catch (_) {}
      }

      await fetchProfile(receivedToken);
      setIsLoading(false);
      return { success: true };
    } catch (err: any) {
      setIsLoading(false);
      return {
        success: false,
        error: err?.message || "Network error connecting to SEC-OPS authentication service.",
      };
    }
  };

  const logout = async (): Promise<void> => {
    if (token) {
      try {
        await safeFetch("/api/auth/logout", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (_) {}
    }

    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    } catch (_) {}

    setToken(null);
    setUser(null);
    router.push("/login");
  };

  const refreshUser = async (): Promise<void> => {
    if (token) {
      await fetchProfile(token);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!token && !!user,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
