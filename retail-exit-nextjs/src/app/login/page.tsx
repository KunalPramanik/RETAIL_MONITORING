"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/lib/theme-provider";
import {
  ShieldAlert,
  Lock,
  User,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  CheckCircle2,
  HelpCircle,
  X,
  Server,
  Terminal,
} from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectPath = searchParams.get("redirect") || "/";

  const { login, isAuthenticated, isLoading: authLoading } = useAuth();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showForgotModal, setShowForgotModal] = useState(false);

  // If already authenticated, redirect to destination
  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      router.replace(redirectPath);
    }
  }, [isAuthenticated, authLoading, redirectPath, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!identifier.trim()) {
      setErrorMessage("Please enter your operator email or username.");
      return;
    }
    if (!password) {
      setErrorMessage("Please enter your password.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await login(identifier, password, rememberMe);
      if (result.success) {
        router.push(redirectPath);
      } else {
        setErrorMessage(result.error || "Authentication failed. Please verify credentials.");
      }
    } catch (err: any) {
      setErrorMessage(err?.message || "An unexpected error occurred during login.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-between bg-[var(--bg-canvas)] text-[var(--text-primary)] transition-colors duration-200 selection:bg-[#38BDF8]/20 selection:text-[#38BDF8]">
      {/* Top Bar with theme toggle & station status */}
      <header className="px-6 py-4 flex justify-between items-center border-b border-[var(--border-hairline)] bg-[var(--header-bg)] backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-md shadow-blue-900/30">
            <ShieldAlert size={20} />
          </div>
          <div>
            <span className="font-bold text-sm tracking-tight text-[var(--text-primary)] block leading-none">
              SEC-OPS <span className="text-[#38BDF8] text-xs font-mono">V8</span>
            </span>
            <span className="text-[10px] font-mono text-[var(--text-muted)] tracking-wider block mt-0.5 uppercase">
              Retail Security & Loss Prevention
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-[var(--text-muted)] px-3 py-1 rounded-md border border-[var(--border-hairline)] bg-[var(--bg-panel-sunken)]">
            <Server size={13} className="text-[var(--status-ok)]" />
            <span>TERMINAL ACCESS // GATEWAY</span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      {/* Main Login Card Area */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 my-auto">
        <div className="w-full max-w-md">
          {/* Card Container */}
          <div className="relative rounded-2xl bg-[var(--bg-panel)] border border-[var(--border-hairline)] p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
            {/* Top accent line */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-600 via-[#38BDF8] to-indigo-600 rounded-t-2xl" />

            {/* Header info */}
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600/20 to-[#38BDF8]/20 border border-[#38BDF8]/30 text-[#38BDF8] mb-3 shadow-inner">
                <ShieldAlert size={28} />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--text-primary)]">
                SEC-OPS <span className="text-[#38BDF8]">V8</span>
              </h1>
              <p className="text-xs text-[var(--text-secondary)] mt-1 font-medium">
                Retail Security & Loss Prevention
              </p>
              <p className="text-[11px] font-mono text-[var(--text-muted)] mt-0.5 uppercase tracking-wider">
                Authorized Personnel Terminal
              </p>
            </div>

            {/* Error Banner */}
            {errorMessage && (
              <div
                role="alert"
                className="mb-5 p-3.5 rounded-xl border border-[var(--status-high)]/40 bg-[var(--status-high)]/10 text-[var(--status-high)] text-xs flex items-start gap-2.5 animate-in fade-in slide-in-from-top-2 duration-200"
              >
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <div className="flex-1 leading-relaxed font-medium">{errorMessage}</div>
                <button
                  type="button"
                  onClick={() => setErrorMessage(null)}
                  className="hover:opacity-75 transition-opacity"
                  aria-label="Dismiss error"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Identifier Input */}
              <div>
                <label
                  htmlFor="identifier"
                  className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-1.5"
                >
                  Email / Username
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[var(--text-muted)]">
                    <User size={16} />
                  </div>
                  <input
                    id="identifier"
                    type="text"
                    autoComplete="username"
                    autoFocus
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="admin or operator@secops.local"
                    disabled={submitting}
                    className="w-full pl-10 pr-4 py-2.5 text-xs sm:text-sm rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-canvas)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[#38BDF8]/50 focus:border-[#38BDF8] transition-all disabled:opacity-50"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="password"
                    className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]"
                  >
                    Password
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowForgotModal(true)}
                    className="text-[11px] font-medium text-[#38BDF8] hover:underline focus:outline-none"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[var(--text-muted)]">
                    <Lock size={16} />
                  </div>
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    disabled={submitting}
                    className="w-full pl-10 pr-11 py-2.5 text-xs sm:text-sm rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-canvas)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[#38BDF8]/50 focus:border-[#38BDF8] transition-all disabled:opacity-50"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors focus:outline-none"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Remember Me Checkbox */}
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    disabled={submitting}
                    className="w-4 h-4 rounded border-[var(--border-hairline)] text-blue-600 focus:ring-[#38BDF8] bg-[var(--bg-canvas)]"
                  />
                  <span className="text-xs text-[var(--text-secondary)] font-medium">
                    Remember me on this station
                  </span>
                </label>
              </div>

              {/* Submit Button */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={submitting || !identifier || !password}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs sm:text-sm font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-[0.99] transition-all shadow-lg shadow-blue-900/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      <span>AUTHENTICATING OPERATOR...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} />
                      <span>LOGIN</span>
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Terminal Security Badge */}
            <div className="mt-6 pt-5 border-t border-[var(--border-hairline)] flex items-center justify-between text-[11px] text-[var(--text-muted)] font-mono">
              <span className="flex items-center gap-1.5">
                <Terminal size={12} className="text-[#38BDF8]" />
                RBAC Level 2 Enforced
              </span>
              <span>TLS 1.3 // ZERO-MOCK</span>
            </div>
          </div>
        </div>
      </main>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl bg-[var(--bg-panel)] border border-[var(--border-hairline)] p-6 shadow-2xl">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2.5 text-[#38BDF8]">
                <HelpCircle size={22} />
                <h3 className="font-bold text-base text-[var(--text-primary)]">
                  Password Recovery Notice
                </h3>
              </div>
              <button
                onClick={() => setShowForgotModal(false)}
                className="p-1 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-panel-hover)]"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 text-xs text-[var(--text-secondary)] leading-relaxed">
              <p>
                In compliance with <strong>SEC-OPS V8 Security Directive ISO/IEC 27001</strong>, self-service automated password resets are disabled on retail surveillance exit consoles to prevent unauthorized lateral escalation.
              </p>
              <div className="p-3 rounded-xl bg-[var(--bg-panel-sunken)] border border-[var(--border-hairline)] font-mono text-[11px] space-y-1">
                <div>• Contact Station Administrator or CSO</div>
                <div>• Enterprise Desk: Ext. 4010</div>
                <div>• Email: admin@secops.local</div>
              </div>
              <p className="text-[11px] text-[var(--text-muted)]">
                Default system credentials for local lab testing are provisioned in the deployment configuration documentation.
              </p>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setShowForgotModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="px-6 py-4 border-t border-[var(--border-hairline)] text-center text-xs text-[var(--text-muted)] font-mono">
        SEC-OPS V8 Surveillance & Loss Prevention Platform // Enterprise Production Gateway
      </footer>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[var(--bg-canvas)] text-[var(--text-primary)]">
          <Loader2 size={28} className="animate-spin text-[#38BDF8]" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
