"use client";

import React, { useState, useEffect } from "react";
import { safeFetch } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  ShieldAlert,
  Building,
  Plus,
  RefreshCw,
  Server,
  Lock,
  CheckCircle,
  AlertTriangle,
  Users,
  Search,
  Database,
  Key,
} from "lucide-react";

interface TenantItem {
  tenantId: string;
  name: string;
  slug: string;
  dbUri: string;
  status: "ACTIVE" | "SUSPENDED";
  createdAt: string;
}

interface AuditLogItem {
  logId: string;
  action: string;
  actor: string;
  tenantId?: string;
  timestamp: string;
  details?: any;
}

export default function PlatformFleetPage() {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [tenantName, setTenantName] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  const fetchData = async () => {
    try {
      setLoading(true);
      const [resTenants, resLogs] = await Promise.all([
        safeFetch("/api/platform/tenants"),
        safeFetch("/api/platform/audit-logs"),
      ]);

      if (resTenants.ok) {
        const data = await resTenants.json();
        setTenants(data);
      }
      if (resLogs.ok) {
        const logs = await resLogs.json();
        setAuditLogs(logs);
      }
    } catch (e) {
      console.warn("Failed to fetch platform fleet:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenantName.trim() || !tenantSlug.trim() || !adminEmail.trim() || !adminPassword.trim()) {
      alert("All fields are required.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await safeFetch("/api/platform/tenants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: tenantName.trim(),
          slug: tenantSlug.trim(),
          adminEmail: adminEmail.trim(),
          adminPassword: adminPassword.trim(),
        }),
      });

      if (res.ok) {
        setShowCreateModal(false);
        setTenantName("");
        setTenantSlug("");
        setAdminEmail("");
        setAdminPassword("");
        fetchData();
        alert("New tenant provisioned with isolated database!");
      } else {
        const err = await res.json();
        alert(err.detail || "Tenant provisioning failed");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (tenantId: string, currentStatus: string) => {
    const nextStatus = currentStatus === "ACTIVE" ? "SUSPENDED" : "ACTIVE";
    if (!confirm(`Are you sure you want to change tenant status to ${nextStatus}?`)) return;

    try {
      const res = await safeFetch(`/api/platform/tenants/${tenantId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (res.ok) {
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to update tenant status");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    }
  };

  if (user && user.role !== "SUPER_ADMIN") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center p-8 bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl my-6">
        <div className="w-16 h-16 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 mb-4">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-[var(--text-primary)] tracking-wide">Access Restricted</h2>
        <p className="text-sm text-[var(--text-secondary)] max-w-md mt-2 leading-relaxed">
          Platform Fleet & Multi-Tenant Governance controls are strictly reserved for the Software Owner (SUPER_ADMIN). Store administrators manage operations through the Store Onboarding and Settings pages.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <ShieldAlert className="text-[#38BDF8]" /> Master Super Admin — Multi-Tenant Control Plane
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Platform-level tenant isolation, isolated database provisioning, company access governance, and fleet telemetry.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3.5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all font-mono"
          >
            <Plus size={15} /> Provision Tenant
          </button>
          <button
            onClick={fetchData}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </div>

      {/* Global Analytics KPIs (Section A-6) */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Total Enterprises</span>
          <div className="text-2xl font-bold font-mono text-[#38BDF8] mt-1">{tenants.length}</div>
          <span className="text-[11px] text-[var(--text-muted)] mt-1 block">Provisioned SaaS clients</span>
        </div>
        <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Active Tenants</span>
          <div className="text-2xl font-bold font-mono text-[#4FD1B3] mt-1">
            {tenants.filter((t) => t.status === "ACTIVE").length}
          </div>
          <span className="text-[11px] text-[var(--text-muted)] mt-1 block">Operational data planes online</span>
        </div>
        <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Suspended Tenants</span>
          <div className="text-2xl font-bold font-mono text-[#E5484D] mt-1">
            {tenants.filter((t) => t.status !== "ACTIVE").length}
          </div>
          <span className="text-[11px] text-[var(--text-muted)] mt-1 block">Access revoked / halted</span>
        </div>
        <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
          <span className="text-xs font-mono text-[var(--text-secondary)] uppercase">Control Plane DB</span>
          <div className="text-sm font-bold font-mono text-emerald-400 mt-2 flex items-center gap-1.5">
            <CheckCircle size={15} /> ISOLATED & ACTIVE
          </div>
          <span className="text-[11px] text-[var(--text-muted)] mt-1 block">data/platform/control_plane.db</span>
        </div>
      </div>

      {/* Isolation Architecture Notice */}
      <div className="bg-[#38BDF8]/10 border border-[#38BDF8]/30 rounded-xl p-4 text-xs font-mono flex items-start gap-3">
        <Database size={20} className="text-[#38BDF8] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="font-bold text-[#38BDF8]">STRICT MULTI-TENANT ISOLATION ARCHITECTURE</div>
          <p className="text-[var(--text-secondary)] leading-relaxed">
            Each tenant enterprise operates on a dedicated SQLite/PostgreSQL operational database. Platform credentials, tenant billing, and administrative audits reside strictly in the Platform Control Plane DB (<code className="text-white">data/platform/control_plane.db</code>). Cross-tenant queries are blocked at the engine layer.
          </p>
        </div>
      </div>

      {/* Tenant Fleet Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-[var(--border-hairline)] flex justify-between items-center bg-[var(--bg-canvas)]">
          <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2">
            <Building size={16} className="text-[#4FD1B3]" /> ACTIVE ENTERPRISE TENANTS ({tenants.length})
          </h3>
          <span className="text-xs font-mono text-[var(--text-secondary)]">Zero cross-tenant data leakage guaranteed</span>
        </div>

        {tenants.length === 0 && !loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <Building size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">No tenants provisioned yet</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Click Provision Tenant to register a new client enterprise and automatically generate their isolated database.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm font-mono">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-4">STATUS</th>
                  <th className="p-4">COMPANY NAME</th>
                  <th className="p-4">TENANT SLUG</th>
                  <th className="p-4">TENANT ID</th>
                  <th className="p-4">ISOLATED DATABASE</th>
                  <th className="p-4">PROVISIONED AT</th>
                  <th className="p-4 text-right">GOVERNANCE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {tenants.map((t) => (
                  <tr key={t.tenantId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold ${
                          t.status === "ACTIVE"
                            ? "bg-[#4FD1B3]/15 text-[#4FD1B3] border border-[#4FD1B3]/30"
                            : "bg-[#E5484D]/15 text-[#E5484D] border border-[#E5484D]/30"
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                        {t.status}
                      </span>
                    </td>
                    <td className="p-4 font-sans font-bold text-white">{t.name}</td>
                    <td className="p-4 text-[#38BDF8] font-bold">{t.slug}</td>
                    <td className="p-4 text-xs text-[var(--text-secondary)]">{t.tenantId}</td>
                    <td className="p-4 text-xs text-[#E8A33D] max-w-xs truncate" title={t.dbUri}>
                      {t.dbUri}
                    </td>
                    <td className="p-4 text-xs text-[var(--text-secondary)]">
                      {new Date(t.createdAt).toLocaleDateString()}
                    </td>
                    <td className="p-4 text-right">
                      <button
                        onClick={() => handleToggleStatus(t.tenantId, t.status)}
                        className={`px-3 py-1 rounded text-xs font-bold transition-colors border ${
                          t.status === "ACTIVE"
                            ? "bg-[var(--bg-canvas)] hover:bg-[#E5484D]/20 text-[#E5484D] border-[#E5484D]/30"
                            : "bg-[var(--bg-canvas)] hover:bg-[#4FD1B3]/20 text-[#4FD1B3] border-[#4FD1B3]/30"
                        }`}
                      >
                        {t.status === "ACTIVE" ? "Suspend Access" : "Activate Access"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Platform Audit Logs */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-[var(--border-hairline)] flex justify-between items-center bg-[var(--bg-canvas)]">
          <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2">
            <Lock size={16} className="text-[#E8A33D]" /> PLATFORM PROVISIONING AUDIT LOGS
          </h3>
          <span className="text-xs font-mono text-[var(--text-secondary)]">Immutable ledger of platform actions</span>
        </div>

        {auditLogs.length === 0 ? (
          <div className="p-8 text-center text-[var(--text-muted)] text-xs font-mono">
            No platform audit events recorded.
          </div>
        ) : (
          <div className="divide-y divide-[var(--border-hairline)] text-xs font-mono">
            {auditLogs.map((log) => (
              <div key={log.logId} className="p-3 flex justify-between items-center hover:bg-[var(--bg-panel-raised)]">
                <div className="space-y-0.5">
                  <span className="text-[#38BDF8] font-bold">{log.action}</span>
                  <div className="text-[var(--text-secondary)]">
                    Actor: <span className="text-white">{log.actor}</span>
                    {log.tenantId && ` | Tenant ID: ${log.tenantId}`}
                  </div>
                </div>
                <div className="text-[var(--text-secondary)]">{new Date(log.timestamp).toLocaleString()}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Provision Tenant Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Building size={18} className="text-[#38BDF8]" /> Provision New Enterprise Tenant
              </h3>
              <button onClick={() => setShowCreateModal(false)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTenant} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">ENTERPRISE NAME *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Reliance Retail Logistics"
                  value={tenantName}
                  onChange={(e) => {
                    setTenantName(e.target.value);
                    if (!tenantSlug) {
                      setTenantSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, "-"));
                    }
                  }}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-white outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">TENANT SLUG (SUBDOMAIN) *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. reliance-retail"
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[#38BDF8] font-mono outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">INITIAL ADMIN EMAIL *</label>
                <input
                  type="email"
                  required
                  placeholder="admin@enterprise.com"
                  value={adminEmail}
                  onChange={(e) => setAdminEmail(e.target.value)}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-white font-mono outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">INITIAL ADMIN PASSWORD *</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  placeholder="••••••••••••"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-white font-mono outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-bold shadow-lg shadow-blue-900/30 disabled:opacity-50"
                >
                  {submitting ? "Provisioning Database..." : "Provision Tenant"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

