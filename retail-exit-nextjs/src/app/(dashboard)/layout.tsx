"use client";

import { safeFetch } from "@/lib/api-client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/lib/theme-provider";
import {
  Activity,
  Camera,
  Box,
  FileText,
  AlertTriangle,
  Settings,
  ShieldAlert,
  Users,
  Layers,
  CheckCircle,
  FileSpreadsheet,
  LogOut,
  Loader2,
  Sparkles,
} from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [currentTime, setCurrentTime] = useState("");
  const [apiHealth, setApiHealth] = useState<"HEALTHY" | "DEGRADED" | "OFFLINE" | "CHECKING">("CHECKING");

  // Authentication guard
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString());
    }, 1000);

    const checkApi = async () => {
      try {
        const res = await safeFetch("/api/health");
        if (res.ok) {
          const data = await res.json().catch(() => null);
          if (data?.status === "HEALTHY") {
            setApiHealth("HEALTHY");
          } else if (data?.status === "DEGRADED") {
            setApiHealth("DEGRADED");
          } else {
            setApiHealth("HEALTHY");
          }
        } else {
          setApiHealth("DEGRADED");
        }
      } catch {
        setApiHealth("OFFLINE");
      }
    };
    checkApi();
    const apiInterval = setInterval(checkApi, 20000);

    return () => {
      clearInterval(timer);
      clearInterval(apiInterval);
    };
  }, []);

  const role = (user?.role || "OPERATOR").toUpperCase();
  const isSoftwareOwner = role === "SUPER_ADMIN";

  const allNavItems = [
    { label: "Dashboard", href: "/", icon: Activity, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR", "SECURITY", "AUDITOR", "VIEWER"] },
    { label: "Platform Fleet", href: "/platform", icon: ShieldAlert, roles: ["SUPER_ADMIN"] },
    { label: "Store Onboarding", href: "/onboarding", icon: Sparkles, roles: ["SUPER_ADMIN"] },
    { label: "Cameras & Fleet", href: "/settings/cameras", icon: Camera, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "SECURITY"] },
    { label: "Security Alerts", href: "/alerts", icon: AlertTriangle, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "SECURITY"] },
    { label: "Inventory & Ledger", href: "/inventory", icon: Box, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR", "AUDITOR", "VIEWER"] },
    { label: "Products & Pack Math", href: "/products", icon: Layers, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR"] },
    { label: "Employees & Face ID", href: "/employees", icon: Users, roles: ["SUPER_ADMIN", "ADMIN", "SECURITY"] },
    { label: "Invoices & OCR", href: "/invoices", icon: FileText, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR", "AUDITOR", "VIEWER"] },
    { label: "Exit Events", href: "/events", icon: Layers, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR", "SECURITY", "AUDITOR", "VIEWER"] },
    { label: "Reports & PDF", href: "/reports", icon: FileSpreadsheet, roles: ["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "AUDITOR", "VIEWER"] },
    { label: "Settings & Sensors", href: "/settings", icon: Settings, roles: ["SUPER_ADMIN", "ADMIN"] },
  ];

  const navItems = allNavItems.filter((item) => item.roles.includes(role));

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--bg-canvas)] text-[var(--text-primary)]">
        <div className="flex flex-col items-center gap-3">
          <div className="p-3.5 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-xl animate-pulse">
            <ShieldAlert size={32} />
          </div>
          <div className="text-sm font-bold tracking-tight">SEC-OPS V8 CONTROL CONSOLE</div>
          <div className="text-xs font-mono text-[var(--text-muted)] flex items-center gap-2">
            <Loader2 size={14} className="animate-spin text-[#38BDF8]" />
            Verifying operator credentials...
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const userInitial = (user?.username?.[0] || user?.email?.[0] || "O").toUpperCase();
  const displayName = user?.username || user?.email?.split("@")[0] || "Operator";
  const userRole = user?.role || "OPERATOR";

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg-canvas)] text-[var(--text-primary)] select-none transition-colors duration-200">
      {/* 1. Left Navigation Rail */}
      <aside className="w-64 bg-[var(--sidebar-bg)] border-r border-[var(--border-hairline)] flex flex-col z-20 shadow-xl transition-colors duration-200">
        {/* Brand / Logo */}
        <div className="p-5 border-b border-[var(--border-hairline)] flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-lg shadow-blue-900/30">
              <ShieldAlert size={20} />
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-[var(--text-primary)] block leading-none">
                SEC-OPS <span className="text-[#38BDF8] text-xs font-mono">V8</span>
              </span>
              <span className="text-[10px] font-mono text-[var(--text-muted)] tracking-wider block mt-0.5 uppercase">
                Surveillance AI
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(item.href + "/");

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? "bg-[#2563EB] text-white shadow-lg shadow-blue-900/25 font-bold border-l-2 border-[#38BDF8]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-panel-hover)]"
                }`}
              >
                <item.icon size={16} className={isActive ? "text-white" : "text-[var(--text-secondary)]"} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User / Station Footer */}
        <div className="p-4 border-t border-[var(--border-hairline)] bg-[var(--bg-canvas)] transition-colors duration-200">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-full bg-[var(--bg-panel-raised)] border border-[var(--border-hairline)] flex items-center justify-center font-bold text-xs text-[#38BDF8] shrink-0">
                {userInitial}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-[var(--text-primary)] truncate">
                  {displayName}
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold uppercase">
                    {userRole}
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={() => logout()}
              title="Sign Out"
              aria-label="Sign Out"
              className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--status-high)] hover:bg-[var(--bg-panel-hover)] transition-colors shrink-0"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* 2. Main Content View Area */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Top Control Room Header */}
        <header className="px-6 py-3 border-b border-[var(--border-hairline)] flex justify-between items-center bg-[var(--header-bg)] z-10 sticky top-0 shadow-sm transition-colors duration-200">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-[var(--text-muted)]">CONTROL CONSOLE //</span>
            <span className="text-sm font-bold tracking-tight text-[var(--text-primary)]">
              {navItems.find((n) => (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href)))?.label ||
                "Console"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Theme Toggle (System / Dark / Light) */}
            <ThemeToggle />

            {/* Real-time Clock */}
            <div className="text-xs font-mono text-[var(--data-mono-text)] bg-[var(--bg-canvas)] px-3 py-1 rounded-md border border-[var(--border-hairline)] flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[var(--status-ok)] animate-pulse"></span>
              <span>{currentTime || "12:00:00"}</span>
            </div>

            {/* API Health Pill */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border font-medium ${
                apiHealth === "HEALTHY"
                  ? "bg-[var(--status-ok)]/10 text-[var(--status-ok)] border-[var(--status-ok)]/30"
                  : apiHealth === "DEGRADED"
                  ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                  : apiHealth === "CHECKING"
                  ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                  : "bg-[var(--status-high)]/10 text-[var(--status-high)] border-[var(--status-high)]/30"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  apiHealth === "HEALTHY"
                    ? "bg-[var(--status-ok)] animate-pulse"
                    : apiHealth === "DEGRADED"
                    ? "bg-amber-400"
                    : apiHealth === "CHECKING"
                    ? "bg-blue-400 animate-pulse"
                    : "bg-[var(--status-high)]"
                }`}
              />
              <span>
                {apiHealth === "HEALTHY"
                  ? "API: HEALTHY"
                  : apiHealth === "DEGRADED"
                  ? "API: DEGRADED"
                  : apiHealth === "CHECKING"
                  ? "API: CHECKING..."
                  : "API: OFFLINE"}
              </span>
            </div>
          </div>
        </header>

        {/* Page Children Container */}
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
      </main>
    </div>
  );
}
