"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { safeFetch } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import StoreDashboard from "@/components/dashboard/store-dashboard";
import {
  ShieldAlert,
  Building,
  Store,
  CreditCard,
  Camera,
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Plus,
  RefreshCw,
  Server,
  Database,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  Clock,
  Layers,
  Lock,
} from "lucide-react";

interface DashboardSummary {
  tenants: {
    total: number;
    active: number;
    suspended: number;
  };
  stores: {
    total: number;
    active: number;
    suspended: number;
    withBillingIssues: number;
  };
  billing: {
    unpaidInvoicesCount: number;
    unpaidAmountCents: number;
    currency: string;
    activeSubscriptionsByPlan: Array<{
      tierId: string;
      name: string;
      count: number;
      maxCameras: number;
      priceCents: number;
    }>;
  };
  cameraFleet: {
    total: number;
    online: number;
    offline: number;
    degraded: number;
    pendingSetup: number;
    storesExceedingLimit: number;
  };
  recentActivities: Array<{
    id: string;
    action: string;
    actor: string;
    tenantId?: string;
    storeId?: string;
    timestamp: string;
    severity?: string;
  }>;
  systemHealth: {
    apiStatus: string;
    dbConnected: boolean;
    version: string;
    serverTime: string;
  };
}

function SoftwareOwnerDashboardView() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async (isManual = false) => {
    try {
      if (isManual) setRefreshing(true);
      setError(null);
      const res = await safeFetch("/api/platform/dashboard/summary");
      if (res.ok) {
        const data = await res.json();
        setSummary(data);
      } else {
        const err = await res.json().catch(() => null);
        setError(err?.detail || "Failed to load platform summary.");
      }
    } catch (e: any) {
      setError(e.message || "Network error loading platform metrics.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchSummary();
    const interval = setInterval(() => fetchSummary(false), 30000);
    return () => clearInterval(interval);
  }, []);

  const formatCurrency = (cents: number, currency: string = "INR") => {
    const amount = cents / 100;
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: currency,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Header & Quick Actions */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-2xl border border-[var(--border-hairline)] shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-[#38BDF8] border border-blue-500/20 font-bold uppercase tracking-wider">
              SAAS COMMAND CENTER
            </span>
            <span className="text-xs text-[var(--text-muted)] font-mono">
              SEC-OPS V8 v{summary?.systemHealth?.version || "2.0.0"}
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-2.5">
            Software Owner Control Panel
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Centralized governance for enterprises, store deployments, camera fleet health, and billing subscriptions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/platform?tab=tenants"
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all font-mono"
          >
            <Plus size={15} /> Provision Tenant
          </Link>

          <button
            onClick={() => fetchSummary(true)}
            disabled={refreshing}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-xl text-xs font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
            title="Refresh Metrics"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin text-[#38BDF8]" : ""} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl border border-[var(--status-high)]/40 bg-[var(--status-high)]/10 text-[var(--status-high)] text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchSummary(true)}
            className="underline font-bold hover:text-[var(--text-primary)]"
          >
            Retry
          </button>
        </div>
      )}

      {/* 2. Top-Level Core Metric Cards (Section 7.2) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Companies / Tenants */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-2xl border border-[var(--border-hairline)] shadow-lg hover:border-[#38BDF8]/40 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--text-secondary)] uppercase tracking-wider">
              Companies / Tenants
            </span>
            <div className="p-2 rounded-xl bg-blue-500/10 text-[#38BDF8]">
              <Building size={18} />
            </div>
          </div>
          <div className="text-3xl font-bold font-mono text-[var(--text-primary)] mt-3">
            {summary ? summary.tenants.total : "—"}
          </div>
          <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--border-hairline)] text-xs">
            <span className="flex items-center gap-1 text-[var(--status-ok)] font-medium">
              <CheckCircle2 size={13} /> {summary?.tenants.active || 0} Active
            </span>
            {summary && summary.tenants.suspended > 0 && (
              <span className="flex items-center gap-1 text-[var(--status-high)] font-medium">
                <XCircle size={13} /> {summary.tenants.suspended} Suspended
              </span>
            )}
          </div>
        </div>

        {/* Physical Stores Fleet */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-2xl border border-[var(--border-hairline)] shadow-lg hover:border-[#4FD1B3]/40 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--text-secondary)] uppercase tracking-wider">
              Physical Stores
            </span>
            <div className="p-2 rounded-xl bg-emerald-500/10 text-[#4FD1B3]">
              <Store size={18} />
            </div>
          </div>
          <div className="text-3xl font-bold font-mono text-[var(--text-primary)] mt-3">
            {summary ? summary.stores.total : "—"}
          </div>
          <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--border-hairline)] text-xs">
            <span className="flex items-center gap-1 text-[var(--status-ok)] font-medium">
              <CheckCircle2 size={13} /> {summary?.stores.active || 0} Operational
            </span>
            {summary && summary.stores.suspended > 0 && (
              <span className="flex items-center gap-1 text-[var(--status-high)] font-medium">
                <XCircle size={13} /> {summary.stores.suspended} Suspended
              </span>
            )}
            {summary && summary.stores.withBillingIssues > 0 && (
              <span className="flex items-center gap-1 text-amber-400 font-medium">
                <AlertTriangle size={13} /> {summary.stores.withBillingIssues} Overdue
              </span>
            )}
          </div>
        </div>

        {/* Camera Fleet Overview */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-2xl border border-[var(--border-hairline)] shadow-lg hover:border-[#E8A33D]/40 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--text-secondary)] uppercase tracking-wider">
              Global Camera Fleet
            </span>
            <div className="p-2 rounded-xl bg-amber-500/10 text-[#E8A33D]">
              <Camera size={18} />
            </div>
          </div>
          <div className="text-3xl font-bold font-mono text-[var(--text-primary)] mt-3">
            {summary ? summary.cameraFleet.total : "—"}
          </div>
          <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--border-hairline)] text-xs">
            <span className="flex items-center gap-1 text-[var(--status-ok)] font-medium">
              <CheckCircle2 size={13} /> {summary?.cameraFleet.online || 0} Online
            </span>
            <span className="flex items-center gap-1 text-[var(--text-muted)] font-medium">
              {summary?.cameraFleet.offline || 0} Offline
            </span>
            {summary && summary.cameraFleet.storesExceedingLimit > 0 && (
              <span className="flex items-center gap-1 text-[var(--status-high)] font-medium">
                <AlertTriangle size={13} /> {summary.cameraFleet.storesExceedingLimit} Over Limit
              </span>
            )}
          </div>
        </div>

        {/* Subscriptions & Invoicing */}
        <div className="bg-[var(--bg-panel)] p-5 rounded-2xl border border-[var(--border-hairline)] shadow-lg hover:border-indigo-500/40 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--text-secondary)] uppercase tracking-wider">
              Billing & Subscriptions
            </span>
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <CreditCard size={18} />
            </div>
          </div>
          <div className="text-3xl font-bold font-mono text-[var(--text-primary)] mt-3">
            {summary
              ? summary.billing.activeSubscriptionsByPlan.reduce((acc, p) => acc + p.count, 0)
              : "—"}{" "}
            <span className="text-xs font-normal text-[var(--text-muted)]">Active Plans</span>
          </div>
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--border-hairline)] text-xs">
            <span className="text-[var(--text-secondary)]">Unpaid Invoices:</span>
            <span
              className={`font-mono font-bold ${
                summary?.billing.unpaidInvoicesCount === 0
                  ? "text-[var(--status-ok)]"
                  : "text-[var(--status-high)]"
              }`}
            >
              {summary?.billing.unpaidInvoicesCount || 0} (
              {formatCurrency(summary?.billing.unpaidAmountCents || 0, summary?.billing.currency)})
            </span>
          </div>
        </div>
      </div>

      {/* 3. Mid Section: Subscription Plans Breakdown + System Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Subscription Catalog & Active Stores Breakdown */}
        <div className="lg:col-span-2 bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] p-6 shadow-xl space-y-4">
          <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-4">
            <div>
              <h2 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <CreditCard size={18} className="text-[#38BDF8]" /> Active Subscriptions by Tier
              </h2>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Current tenant distribution across provisioned SaaS plans and camera capacity limits.
              </p>
            </div>
            <Link
              href="/platform?tab=billing"
              className="text-xs text-[#38BDF8] hover:underline flex items-center gap-1 font-mono"
            >
              Manage Billing <ArrowRight size={13} />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {summary?.billing.activeSubscriptionsByPlan && summary.billing.activeSubscriptionsByPlan.length > 0 ? (
              summary.billing.activeSubscriptionsByPlan.map((tier) => (
                <div
                  key={tier.tierId}
                  className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-4 space-y-3"
                >
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                      {tier.name}
                    </span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-500/10 text-[#38BDF8] border border-blue-500/20 font-bold">
                      {tier.count} {tier.count === 1 ? "Store" : "Stores"}
                    </span>
                  </div>
                  <div className="text-xl font-bold font-mono text-[var(--text-primary)]">
                    {formatCurrency(tier.priceCents, summary.billing.currency)}
                    <span className="text-[10px] text-[var(--text-muted)] font-normal"> / mo</span>
                  </div>
                  <div className="text-xs text-[var(--text-secondary)] font-mono space-y-1 pt-2 border-t border-[var(--border-hairline)]">
                    <div>Limit: {tier.maxCameras} cameras/store</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-3 p-6 text-center text-xs font-mono text-[var(--text-muted)]">
                No subscription tiers provisioned yet.
              </div>
            )}
          </div>
        </div>

        {/* Database & Application System Diagnostics */}
        <div className="bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] p-6 shadow-xl space-y-4">
          <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-4">
            <div>
              <h2 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Database size={18} className="text-[#4FD1B3]" /> Platform Diagnostics
              </h2>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Core database connectivity and application integrity.
              </p>
            </div>
          </div>

          <div className="space-y-3 text-xs font-mono">
            <div className="flex justify-between items-center p-3 rounded-xl bg-[var(--bg-canvas)] border border-[var(--border-hairline)]">
              <span className="text-[var(--text-secondary)]">Database Engine</span>
              <span className="flex items-center gap-1.5 text-[var(--status-ok)] font-bold">
                <CheckCircle2 size={14} /> PostgreSQL / Supabase
              </span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-xl bg-[var(--bg-canvas)] border border-[var(--border-hairline)]">
              <span className="text-[var(--text-secondary)]">Multi-Tenant Isolation</span>
              <span className="text-[#38BDF8] font-bold">TENANT_ID PARTITIONING</span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-xl bg-[var(--bg-canvas)] border border-[var(--border-hairline)]">
              <span className="text-[var(--text-secondary)]">Identity Provider</span>
              <span className="text-[var(--text-primary)] font-bold">platform_super_admin (Strict)</span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-xl bg-[var(--bg-canvas)] border border-[var(--border-hairline)]">
              <span className="text-[var(--text-secondary)]">Software Build</span>
              <span className="text-[var(--text-primary)] font-bold">SEC-OPS V8 (2.0.0)</span>
            </div>

            <div className="flex justify-between items-center p-3 rounded-xl bg-[var(--bg-canvas)] border border-[var(--border-hairline)]">
              <span className="text-[var(--text-secondary)]">Initial Owner</span>
              <span className="text-[#4FD1B3] font-bold">{user?.email || "ces@gmail.com"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Quick Navigation Hub to Detailed Owner Sections */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          href="/platform?tab=tenants"
          className="bg-[var(--bg-panel)] p-5 rounded-2xl border border-[var(--border-hairline)] hover:border-[#38BDF8]/60 transition-all group block shadow-md"
        >
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-blue-500/10 text-[#38BDF8] group-hover:bg-[#38BDF8] group-hover:text-black transition-colors">
                <Building size={20} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">Company & Tenant Fleet</h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  Manage company accounts, store owners & access status
                </p>
              </div>
            </div>
            <ArrowRight size={16} className="text-[var(--text-muted)] group-hover:text-white transition-colors" />
          </div>
        </Link>

        <Link
          href="/platform?tab=stores"
          className="bg-[var(--bg-panel)] p-5 rounded-2xl border border-[var(--border-hairline)] hover:border-[#4FD1B3]/60 transition-all group block shadow-md"
        >
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-[#4FD1B3] group-hover:bg-[#4FD1B3] group-hover:text-black transition-colors">
                <Store size={20} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">Store Deployments</h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  Activate, suspend or inspect store camera capacities
                </p>
              </div>
            </div>
            <ArrowRight size={16} className="text-[var(--text-muted)] group-hover:text-white transition-colors" />
          </div>
        </Link>

        <Link
          href="/platform?tab=audit"
          className="bg-[var(--bg-panel)] p-5 rounded-2xl border border-[var(--border-hairline)] hover:border-amber-500/60 transition-all group block shadow-md"
        >
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 group-hover:bg-amber-400 group-hover:text-black transition-colors">
                <ShieldCheck size={20} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">Platform Audit Ledger</h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  View administrative events, logins, and governance logs
                </p>
              </div>
            </div>
            <ArrowRight size={16} className="text-[var(--text-muted)] group-hover:text-white transition-colors" />
          </div>
        </Link>
      </div>

      {/* 5. Recent Platform Activities Table */}
      <div className="bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] overflow-hidden shadow-xl">
        <div className="p-5 border-b border-[var(--border-hairline)] flex justify-between items-center bg-[var(--bg-canvas)]">
          <div>
            <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2">
              <Clock size={16} className="text-[#38BDF8]" /> RECENT PLATFORM AUDIT TRAIL
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Real-time audit records for platform owner logins, tenant provisioning, and store governance.
            </p>
          </div>
          <Link
            href="/platform?tab=audit"
            className="text-xs font-mono text-[#38BDF8] hover:underline flex items-center gap-1"
          >
            View All Logs <ArrowRight size={12} />
          </Link>
        </div>

        {summary && summary.recentActivities.length > 0 ? (
          <div className="divide-y divide-[var(--border-hairline)] text-xs font-mono">
            {summary.recentActivities.map((act) => (
              <div
                key={act.id}
                className="p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 hover:bg-[var(--bg-panel-raised)] transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-[#38BDF8]">{act.action}</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-white/5 border border-white/10 text-[var(--text-muted)]">
                      {act.actor}
                    </span>
                  </div>
                  {act.tenantId && (
                    <div className="text-[var(--text-secondary)] text-[11px]">
                      Tenant: <span className="text-[var(--text-primary)]">{act.tenantId}</span>
                    </div>
                  )}
                </div>
                <div className="text-[var(--text-muted)] text-[11px]">
                  {new Date(act.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-12 text-center text-xs font-mono text-[var(--text-muted)] space-y-2">
            <ShieldCheck size={32} className="mx-auto text-[var(--text-muted)] opacity-40 mb-2" />
            <div>No recent platform administrative events recorded yet.</div>
            <div className="text-[11px] text-[var(--text-muted)]">
              All platform actions (tenant provisioning, store suspensions, tier changes) will log here automatically.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DashboardRouterPage() {
  const { user, isLoading } = useAuth();
  const role = (user?.role || "ADMIN").toUpperCase();
  const isSoftwareOwner = role === "SUPER_ADMIN" || user?.isPlatformOwner === true;

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center font-mono text-xs text-[var(--text-muted)] gap-2">
        <RefreshCw size={16} className="animate-spin text-[#38BDF8]" />
        Loading console...
      </div>
    );
  }

  if (isSoftwareOwner) {
    return <SoftwareOwnerDashboardView />;
  }

  return <StoreDashboard />;
}

