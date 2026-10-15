"use client";

import React, { useState, useEffect, useMemo, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { safeFetch } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  ShieldAlert,
  Building,
  Store,
  CreditCard,
  Camera,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Plus,
  RefreshCw,
  Search,
  Lock,
  UserPlus,
  Clock,
  Eye,
  Sliders,
  DollarSign,
  FileText,
  Filter,
  Check,
  X,
  Radio,
  Server,
  Layers,
} from "lucide-react";

interface TenantItem {
  tenantId: string;
  name: string;
  slug: string;
  contactEmail?: string;
  status: "ACTIVE" | "SUSPENDED";
  createdAt: string;
  storeCount?: number;
  tierName?: string;
}

interface StoreItem {
  storeId: string;
  tenantId?: string;
  tenantName?: string;
  storeName?: string;
  name?: string;
  storeCode?: string;
  address?: string;
  status: "ACTIVE" | "SUSPENDED" | "MAINTENANCE";
  cameraCount: number;
  maxCameras?: number;
  cameraLimit?: number;
  billingStatus?: string;
  paymentStatus?: string;
}

interface PlanItem {
  tierId: string;
  name: string;
  monthlyPriceCents: number;
  maxCameras: number;
  maxStores: number;
  features: string[];
}

interface SubscriptionItem {
  subscriptionId: string;
  tenantId: string;
  tenantName: string;
  tierId: string;
  tierName: string;
  status: string;
  currentPeriodEnd: string;
}

interface InvoiceItem {
  invoiceId: string;
  tenantId: string;
  tenantName: string;
  invoiceNumber: string;
  amountCents: number;
  currency: string;
  status: "PAID" | "PENDING" | "OVERDUE" | "CANCELLED";
  dueDate: string;
  paidAt?: string;
}

interface CameraFleetItem {
  cameraId: string;
  storeId: string;
  storeName: string;
  tenantId: string;
  label: string;
  status: "ONLINE" | "OFFLINE" | "DEGRADED" | "PENDING_SETUP";
  rtspPath?: string;
  resolution?: string;
  fps?: number;
  lastHeartbeatAt?: string;
}

interface AuditLogItem {
  logId: string;
  action: string;
  actor: string;
  tenantId?: string;
  storeId?: string;
  timestamp: string;
  details?: any;
}

function PlatformControlPanelInner() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();

  const tabParam = searchParams.get("tab") || "tenants";
  const [activeTab, setActiveTab] = useState<"tenants" | "stores" | "billing" | "cameras" | "audit">(
    (tabParam as any) || "tenants"
  );

  // Sync activeTab when query param changes
  useEffect(() => {
    if (tabParam && ["tenants", "stores", "billing", "cameras", "audit"].includes(tabParam)) {
      setActiveTab(tabParam as any);
    }
  }, [tabParam]);

  const setTab = (newTab: "tenants" | "stores" | "billing" | "cameras" | "audit") => {
    setActiveTab(newTab);
    router.push(`/platform?tab=${newTab}`);
  };

  // Data states
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [stores, setStores] = useState<StoreItem[]>([]);
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [cameras, setCameras] = useState<CameraFleetItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);

  // Search & Filters
  const [tenantSearch, setTenantSearch] = useState("");
  const [storeSearch, setStoreSearch] = useState("");
  const [storeStatusFilter, setStoreStatusFilter] = useState<string>("ALL");
  const [cameraStatusFilter, setCameraStatusFilter] = useState<string>("ALL");

  // Modals
  const [showCreateTenantModal, setShowCreateTenantModal] = useState(false);
  const [showProvisionOwnerModal, setShowProvisionOwnerModal] = useState<TenantItem | null>(null);
  const [showStatusReasonModal, setShowStatusReasonModal] = useState<{
    type: "tenant" | "store";
    id: string;
    name: string;
    currentStatus: string;
    targetStatus: string;
  } | null>(null);
  const [statusReason, setStatusReason] = useState("");
  const [showRecordPaymentModal, setShowRecordPaymentModal] = useState<InvoiceItem | null>(null);

  // Form states
  const [createTenantForm, setCreateTenantForm] = useState({
    name: "",
    slug: "",
    contactEmail: "",
    tierId: "tier_enterprise_01",
    adminEmail: "",
    adminPassword: "",
  });

  const [provisionOwnerForm, setProvisionOwnerForm] = useState({
    email: "",
    username: "",
    password: "",
  });

  const [paymentForm, setPaymentForm] = useState({
    paymentRef: "",
    paymentMethod: "BANK_TRANSFER",
    notes: "",
  });

  const [actionSubmitting, setActionSubmitting] = useState(false);

  const fetchAllData = async (isManual = false) => {
    try {
      if (isManual) setRefreshing(true);
      else setLoading(true);

      const [resTenants, resStores, resPlans, resSubs, resInvoices, resCameras, resAudit] =
        await Promise.all([
          safeFetch("/api/platform/tenants"),
          safeFetch("/api/platform/stores"),
          safeFetch("/api/platform/billing/plans"),
          safeFetch("/api/platform/subscriptions"),
          safeFetch("/api/platform/billing/invoices"),
          safeFetch("/api/platform/cameras/fleet-health"),
          safeFetch("/api/platform/audit-logs"),
        ]);

      if (resTenants.ok) setTenants(await resTenants.json());
      if (resStores.ok) setStores(await resStores.json());
      if (resPlans.ok) setPlans(await resPlans.json());
      if (resSubs.ok) setSubscriptions(await resSubs.json());
      if (resInvoices.ok) setInvoices(await resInvoices.json());
      if (resCameras.ok) setCameras(await resCameras.json());
      if (resAudit.ok) setAuditLogs(await resAudit.json());
    } catch (e) {
      console.warn("Failed to load platform data:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  // Handlers
  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createTenantForm.name || !createTenantForm.slug) {
      alert("Please provide Company Name and Slug.");
      return;
    }
    setActionSubmitting(true);
    try {
      const res = await safeFetch("/api/platform/tenants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: createTenantForm.name.trim(),
          companyName: createTenantForm.name.trim(),
          slug: createTenantForm.slug.trim(),
          contactEmail: createTenantForm.contactEmail.trim() || undefined,
          tierId: createTenantForm.tierId,
          adminEmail: createTenantForm.adminEmail.trim() || undefined,
          adminPassword: createTenantForm.adminPassword || undefined,
        }),
      });

      if (res.ok) {
        setShowCreateTenantModal(false);
        setCreateTenantForm({
          name: "",
          slug: "",
          contactEmail: "",
          tierId: "tier_enterprise_01",
          adminEmail: "",
          adminPassword: "",
        });
        fetchAllData(true);
        alert("Company / Tenant successfully registered.");
      } else {
        const err = await res.json().catch(() => null);
        alert(err?.detail || "Failed to create tenant.");
      }
    } catch (e: any) {
      alert(e.message || "Request failed.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleApplyStatusChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showStatusReasonModal) return;
    if (showStatusReasonModal.targetStatus === "SUSPENDED" && !statusReason.trim()) {
      alert("A mandatory reason note is required when suspending access.");
      return;
    }

    setActionSubmitting(true);
    try {
      const url =
        showStatusReasonModal.type === "tenant"
          ? `/api/platform/tenants/${showStatusReasonModal.id}/status`
          : `/api/platform/stores/${showStatusReasonModal.id}/status`;

      const res = await safeFetch(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: showStatusReasonModal.targetStatus,
          reason: statusReason.trim() || "Administrative action by Software Owner",
        }),
      });

      if (res.ok) {
        setShowStatusReasonModal(null);
        setStatusReason("");
        fetchAllData(true);
      } else {
        const err = await res.json().catch(() => null);
        alert(err?.detail || "Failed to update status.");
      }
    } catch (e: any) {
      alert(e.message || "Failed to update status.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleProvisionStoreOwner = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showProvisionOwnerModal) return;
    if (!provisionOwnerForm.email || !provisionOwnerForm.password) {
      alert("Email and password are required.");
      return;
    }

    setActionSubmitting(true);
    try {
      const res = await safeFetch(`/api/platform/tenants/${showProvisionOwnerModal.tenantId}/provision-owner`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: provisionOwnerForm.email.trim(),
          username: provisionOwnerForm.username.trim() || provisionOwnerForm.email.split("@")[0],
          password: provisionOwnerForm.password,
        }),
      });

      if (res.ok) {
        setShowProvisionOwnerModal(null);
        setProvisionOwnerForm({ email: "", username: "", password: "" });
        fetchAllData(true);
        alert("Store Owner account created successfully for tenant. Privileges restricted to tenant scope.");
      } else {
        const err = await res.json().catch(() => null);
        alert(err?.detail || "Failed to provision store owner.");
      }
    } catch (e: any) {
      alert(e.message || "Failed to provision owner.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleRecordPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showRecordPaymentModal) return;
    setActionSubmitting(true);
    try {
      const res = await safeFetch(`/api/platform/billing/invoices/${showRecordPaymentModal.invoiceId}/record-payment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paymentRef: paymentForm.paymentRef.trim() || `OFFLINE-PAY-${Date.now()}`,
          paymentMethod: paymentForm.paymentMethod,
          notes: paymentForm.notes.trim() || undefined,
        }),
      });

      if (res.ok) {
        setShowRecordPaymentModal(null);
        setPaymentForm({ paymentRef: "", paymentMethod: "BANK_TRANSFER", notes: "" });
        fetchAllData(true);
        alert("Payment recorded and invoice marked as PAID.");
      } else {
        const err = await res.json().catch(() => null);
        alert(err?.detail || "Failed to record payment.");
      }
    } catch (e: any) {
      alert(e.message || "Failed to record payment.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const formatCurrency = (cents: number, currency: string = "INR") => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: currency,
      maximumFractionDigits: 0,
    }).format(cents / 100);
  };

  // Filtered views
  const filteredTenants = useMemo(() => {
    return (tenants || []).filter((t) => {
      const q = (tenantSearch || "").toLowerCase();
      const name = String(t.name || "").toLowerCase();
      const slug = String(t.slug || "").toLowerCase();
      const email = String(t.contactEmail || "").toLowerCase();
      return name.includes(q) || slug.includes(q) || email.includes(q);
    });
  }, [tenants, tenantSearch]);

  const filteredStores = useMemo(() => {
    return (stores || []).filter((s) => {
      const q = (storeSearch || "").toLowerCase();
      const sName = String(s.storeName || s.name || "").toLowerCase();
      const sCode = String(s.storeCode || s.storeId || "").toLowerCase();
      const tName = String(s.tenantName || "").toLowerCase();
      const matchesSearch = sName.includes(q) || sCode.includes(q) || tName.includes(q);
      const matchesStatus = storeStatusFilter === "ALL" || s.status === storeStatusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [stores, storeSearch, storeStatusFilter]);

  const filteredCameras = useMemo(() => {
    return (cameras || []).filter((c) => {
      if (cameraStatusFilter === "ALL") return true;
      return c.status === cameraStatusFilter;
    });
  }, [cameras, cameraStatusFilter]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-2xl border border-[var(--border-hairline)] shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-[#38BDF8] border border-blue-500/20 font-bold uppercase tracking-wider">
              PLATFORM GOVERNANCE
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-2.5">
            Software Owner Control Panel
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Multi-tenant lifecycle management, physical store fleet governance, billing control, and fleet health.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchAllData(true)}
            disabled={refreshing}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-xl text-xs font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin text-[#38BDF8]" : ""} />
            <span>Refresh Fleet</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-[var(--border-hairline)] gap-2 overflow-x-auto text-xs font-mono font-medium">
        <button
          onClick={() => setTab("tenants")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "tenants"
              ? "border-[#38BDF8] text-[#38BDF8] font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-white"
          }`}
        >
          <Building size={15} /> Companies & Tenants ({tenants.length})
        </button>

        <button
          onClick={() => setTab("stores")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "stores"
              ? "border-[#4FD1B3] text-[#4FD1B3] font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-white"
          }`}
        >
          <Store size={15} /> Stores Fleet ({stores.length})
        </button>

        <button
          onClick={() => setTab("billing")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "billing"
              ? "border-indigo-400 text-indigo-400 font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-white"
          }`}
        >
          <CreditCard size={15} /> Subscriptions & Billing ({subscriptions.length})
        </button>

        <button
          onClick={() => setTab("cameras")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "cameras"
              ? "border-amber-400 text-amber-400 font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-white"
          }`}
        >
          <Camera size={15} /> Camera Fleet Health ({cameras.length})
        </button>

        <button
          onClick={() => setTab("audit")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "audit"
              ? "border-rose-400 text-rose-400 font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-white"
          }`}
        >
          <Clock size={15} /> Audit Ledger ({auditLogs.length})
        </button>
      </div>

      {/* ============================================================ */}
      {/* TAB 1: COMPANIES & TENANTS (Section 7.3) */}
      {/* ============================================================ */}
      {activeTab === "tenants" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="relative w-full sm:w-80">
              <Search size={15} className="absolute left-3 top-3 text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="Search companies by name or slug..."
                value={tenantSearch}
                onChange={(e) => setTenantSearch(e.target.value)}
                className="w-full bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
              />
            </div>

            <button
              onClick={() => setShowCreateTenantModal(true)}
              className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all font-mono shrink-0"
            >
              <Plus size={15} /> Register New Company
            </button>
          </div>

          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl overflow-hidden shadow-xl">
            {filteredTenants.length === 0 ? (
              <div className="p-12 text-center text-xs font-mono text-[var(--text-muted)] space-y-2">
                <Building size={32} className="mx-auto opacity-30 mb-2" />
                <div>No companies found matching criteria.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                    <tr>
                      <th className="p-4">STATUS</th>
                      <th className="p-4">COMPANY / TENANT</th>
                      <th className="p-4">SLUG</th>
                      <th className="p-4">CONTACT EMAIL</th>
                      <th className="p-4">SUBSCRIPTION</th>
                      <th className="p-4">STORES</th>
                      <th className="p-4">CREATED</th>
                      <th className="p-4 text-right">GOVERNANCE</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {filteredTenants.map((t) => (
                      <tr key={t.tenantId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold ${
                              t.status === "ACTIVE"
                                ? "bg-[var(--status-ok)]/15 text-[var(--status-ok)] border border-[var(--status-ok)]/30"
                                : "bg-[var(--status-high)]/15 text-[var(--status-high)] border border-[var(--status-high)]/30"
                            }`}
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                            {t.status}
                          </span>
                        </td>
                        <td className="p-4 font-sans font-bold text-[var(--text-primary)]">{t.name}</td>
                        <td className="p-4 text-[#38BDF8] font-bold">{t.slug}</td>
                        <td className="p-4 text-[var(--text-secondary)]">{t.contactEmail || "—"}</td>
                        <td className="p-4">
                          <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 font-bold">
                            {t.tierName || "Enterprise"}
                          </span>
                        </td>
                        <td className="p-4 text-[var(--text-primary)] font-bold">{t.storeCount || 0}</td>
                        <td className="p-4 text-[var(--text-muted)]">
                          {new Date(t.createdAt).toLocaleDateString()}
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => {
                                setShowProvisionOwnerModal(t);
                                setProvisionOwnerForm({
                                  email: `owner@${t.slug}.com`,
                                  username: `${t.slug}_admin`,
                                  password: "",
                                });
                              }}
                              className="px-2.5 py-1 rounded bg-[var(--bg-canvas)] hover:bg-blue-600/20 text-[#38BDF8] border border-blue-500/30 text-[11px] font-medium flex items-center gap-1"
                              title="Provision Store Owner Account"
                            >
                              <UserPlus size={12} /> Provision Owner
                            </button>

                            <button
                              onClick={() => {
                                setShowStatusReasonModal({
                                  type: "tenant",
                                  id: t.tenantId,
                                  name: t.name,
                                  currentStatus: t.status,
                                  targetStatus: t.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE",
                                });
                              }}
                              className={`px-2.5 py-1 rounded text-[11px] font-bold border transition-colors ${
                                t.status === "ACTIVE"
                                  ? "bg-[var(--bg-canvas)] hover:bg-[var(--status-high)]/20 text-[var(--status-high)] border-[var(--status-high)]/30"
                                  : "bg-[var(--bg-canvas)] hover:bg-[var(--status-ok)]/20 text-[var(--status-ok)] border-[var(--status-ok)]/30"
                              }`}
                            >
                              {t.status === "ACTIVE" ? "Suspend" : "Reactivate"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 2: STORE FLEET MANAGEMENT (Section 7.4) */}
      {/* ============================================================ */}
      {activeTab === "stores" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="relative w-full sm:w-80">
                <Search size={15} className="absolute left-3 top-3 text-[var(--text-muted)]" />
                <input
                  type="text"
                  placeholder="Search stores by name, code or company..."
                  value={storeSearch}
                  onChange={(e) => setStoreSearch(e.target.value)}
                  className="w-full bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#4FD1B3]"
                />
              </div>

              <select
                value={storeStatusFilter}
                onChange={(e) => setStoreStatusFilter(e.target.value)}
                className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl px-3 py-2 text-xs text-[var(--text-primary)] outline-none font-mono"
              >
                <option value="ALL">All Statuses</option>
                <option value="ACTIVE">Active</option>
                <option value="SUSPENDED">Suspended</option>
                <option value="MAINTENANCE">Maintenance</option>
              </select>
            </div>
          </div>

          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl overflow-hidden shadow-xl">
            {filteredStores.length === 0 ? (
              <div className="p-12 text-center text-xs font-mono text-[var(--text-muted)] space-y-2">
                <Store size={32} className="mx-auto opacity-30 mb-2" />
                <div>No physical stores found matching filter criteria.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                    <tr>
                      <th className="p-4">STATUS</th>
                      <th className="p-4">STORE NAME</th>
                      <th className="p-4">STORE CODE</th>
                      <th className="p-4">PARENT COMPANY</th>
                      <th className="p-4">CAMERA CAPACITY</th>
                      <th className="p-4">BILLING HEALTH</th>
                      <th className="p-4 text-right">GOVERNANCE</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {filteredStores.map((s) => {
                      const displayName = s.storeName || s.name || "Store";
                      const displayCode = s.storeCode || s.storeId || "-";
                      const parentCompany = s.tenantName || "Independent";
                      const maxCams = s.maxCameras ?? s.cameraLimit ?? 4;
                      const billStatus = s.billingStatus || s.paymentStatus || "ACTIVE";
                      const isOverLimit = s.cameraCount > maxCams;
                      const isNearLimit = s.cameraCount === maxCams;

                      return (
                        <tr key={s.storeId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                          <td className="p-4">
                            <span
                              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold ${
                                s.status === "ACTIVE"
                                  ? "bg-[var(--status-ok)]/15 text-[var(--status-ok)] border border-[var(--status-ok)]/30"
                                  : s.status === "MAINTENANCE"
                                  ? "bg-amber-500/15 text-amber-500 dark:text-amber-400 border border-amber-500/30"
                                  : "bg-[var(--status-high)]/15 text-[var(--status-high)] border border-[var(--status-high)]/30"
                              }`}
                            >
                              <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                              {s.status}
                            </span>
                          </td>
                          <td className="p-4 font-sans font-bold text-[var(--text-primary)]">
                            {displayName}
                            {s.address && (
                              <div className="text-[11px] font-mono text-[var(--text-muted)] font-normal truncate max-w-xs">
                                {s.address}
                              </div>
                            )}
                          </td>
                          <td className="p-4 text-[#38BDF8] font-bold">{displayCode}</td>
                          <td className="p-4 text-[var(--text-primary)] font-medium">{parentCompany}</td>
                          <td className="p-4">
                            <div className="flex items-center gap-2">
                              <span
                                className={`px-2 py-0.5 rounded text-[11px] font-bold font-mono ${
                                  isOverLimit
                                    ? "bg-rose-500/20 text-rose-500 dark:text-rose-400 border border-rose-500/40"
                                    : isNearLimit
                                    ? "bg-amber-500/20 text-amber-500 dark:text-amber-400 border border-amber-500/40"
                                    : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                                }`}
                              >
                                {s.cameraCount} / {maxCams} Cams
                              </span>
                              {isOverLimit && (
                                <span className="text-[10px] text-rose-500 dark:text-rose-400 font-bold flex items-center gap-0.5" title="Exceeds Subscription Capacity">
                                  <AlertTriangle size={12} /> OVER LIMIT
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="p-4">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                billStatus === "CURRENT" || billStatus === "ACTIVE"
                                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                                  : "bg-rose-500/10 text-rose-500 dark:text-rose-400 border border-rose-500/20"
                              }`}
                            >
                              {billStatus}
                            </span>
                          </td>
                          <td className="p-4 text-right">
                            <button
                              onClick={() => {
                                setShowStatusReasonModal({
                                  type: "store",
                                  id: s.storeId,
                                  name: displayName,
                                  currentStatus: s.status,
                                  targetStatus: s.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE",
                                });
                              }}
                              className={`px-2.5 py-1 rounded text-[11px] font-bold border transition-colors ${
                                s.status === "ACTIVE"
                                  ? "bg-[var(--bg-canvas)] hover:bg-[var(--status-high)]/20 text-[var(--status-high)] border-[var(--status-high)]/30"
                                  : "bg-[var(--bg-canvas)] hover:bg-[var(--status-ok)]/20 text-[var(--status-ok)] border-[var(--status-ok)]/30"
                              }`}
                            >
                              {s.status === "ACTIVE" ? "Suspend Store" : "Reactivate Store"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 3: SUBSCRIPTIONS & BILLING (Section 7.5) */}
      {/* ============================================================ */}
      {activeTab === "billing" && (
        <div className="space-y-6">
          {/* Subscription Tiers Catalog */}
          <div className="bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] p-6 shadow-xl space-y-4">
            <div className="border-b border-[var(--border-hairline)] pb-4">
              <h2 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <CreditCard size={18} className="text-indigo-400" /> SaaS Subscription Tier Catalog
              </h2>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Configured platform pricing tiers, hardware quotas, and feature flags.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {plans.map((p) => (
                <div
                  key={p.tierId}
                  className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-5 space-y-4"
                >
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">{p.name}</span>
                    <span className="text-xs font-mono text-[var(--text-muted)]">Max {p.maxStores} Stores</span>
                  </div>
                  <div className="text-2xl font-bold font-mono text-[var(--text-primary)]">
                    {formatCurrency(p.monthlyPriceCents)}
                    <span className="text-xs text-[var(--text-muted)] font-normal"> / month</span>
                  </div>
                  <div className="text-xs text-[var(--text-secondary)] font-mono space-y-1.5 pt-3 border-t border-[var(--border-hairline)]">
                    <div className="flex items-center gap-1.5">
                      <Camera size={13} className="text-[#38BDF8]" />
                      <span>Up to {p.maxCameras} cameras per store</span>
                    </div>
                    {p.features &&
                      p.features.map((f, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-emerald-500 dark:text-emerald-400">
                          <Check size={13} />
                          <span>{f}</span>
                        </div>
                      ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Invoices List */}
          <div className="bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] overflow-hidden shadow-xl space-y-4">
            <div className="p-5 border-b border-[var(--border-hairline)] flex justify-between items-center bg-[var(--bg-canvas)]">
              <div>
                <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2">
                  <FileText size={16} className="text-[#38BDF8]" /> TENANT INVOICES & REVENUE TRACKING
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  Audit payment statuses, due dates, and record manual offline receipts.
                </p>
              </div>
            </div>

            {invoices.length === 0 ? (
              <div className="p-12 text-center text-xs font-mono text-[var(--text-muted)]">
                No billing invoices generated yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                    <tr>
                      <th className="p-4">STATUS</th>
                      <th className="p-4">INVOICE #</th>
                      <th className="p-4">COMPANY / TENANT</th>
                      <th className="p-4">DUE DATE</th>
                      <th className="p-4">AMOUNT</th>
                      <th className="p-4">PAID AT</th>
                      <th className="p-4 text-right">MANUAL ACTION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {invoices.map((inv) => (
                      <tr key={inv.invoiceId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                        <td className="p-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              inv.status === "PAID"
                                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                                : inv.status === "OVERDUE"
                                ? "bg-rose-500/15 text-rose-500 dark:text-rose-400 border border-rose-500/30"
                                : "bg-amber-500/15 text-amber-500 dark:text-amber-400 border border-amber-500/30"
                            }`}
                          >
                            {inv.status}
                          </span>
                        </td>
                        <td className="p-4 font-bold text-[var(--text-primary)]">{inv.invoiceNumber}</td>
                        <td className="p-4 text-[var(--text-secondary)] font-sans">{inv.tenantName}</td>
                        <td className="p-4 text-[var(--text-muted)]">
                          {new Date(inv.dueDate).toLocaleDateString()}
                        </td>
                        <td className="p-4 font-bold text-[var(--text-primary)]">
                          {formatCurrency(inv.amountCents, inv.currency)}
                        </td>
                        <td className="p-4 text-[var(--text-muted)]">
                          {inv.paidAt ? new Date(inv.paidAt).toLocaleDateString() : "—"}
                        </td>
                        <td className="p-4 text-right">
                          {inv.status !== "PAID" ? (
                            <button
                              onClick={() => {
                                setShowRecordPaymentModal(inv);
                                setPaymentForm({
                                  paymentRef: `REF-${Date.now().toString().slice(-6)}`,
                                  paymentMethod: "BANK_TRANSFER",
                                  notes: "Manual payment recorded by Software Owner",
                                });
                              }}
                              className="px-2.5 py-1 rounded bg-[var(--bg-canvas)] hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[11px] font-bold"
                            >
                              Record Payment
                            </button>
                          ) : (
                            <span className="text-[11px] text-[var(--status-ok)] font-bold flex items-center justify-end gap-1">
                              <CheckCircle2 size={13} /> Settled
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 4: CAMERA FLEET HEALTH OVERVIEW (Section 7.6) */}
      {/* ============================================================ */}
      {activeTab === "cameras" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex items-center gap-3">
              <select
                value={cameraStatusFilter}
                onChange={(e) => setCameraStatusFilter(e.target.value)}
                className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl px-3 py-2 text-xs text-[var(--text-primary)] outline-none font-mono"
              >
                <option value="ALL">All Camera Statuses</option>
                <option value="ONLINE">Online</option>
                <option value="OFFLINE">Offline</option>
                <option value="DEGRADED">Degraded</option>
                <option value="PENDING_SETUP">Pending Setup</option>
              </select>
            </div>

            <div className="text-xs font-mono text-[var(--text-muted)] bg-[var(--bg-panel)] px-3 py-1.5 rounded-xl border border-[var(--border-hairline)]">
              Privacy Enforcement: Private video streams locked (Diagnostic mode requires audit authorization)
            </div>
          </div>

          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl overflow-hidden shadow-xl">
            {filteredCameras.length === 0 ? (
              <div className="p-12 text-center text-xs font-mono text-[var(--text-muted)] space-y-2">
                <Camera size={32} className="mx-auto opacity-30 mb-2" />
                <div>No cameras registered across stores yet.</div>
                <div className="text-[11px] text-[var(--text-muted)]">
                  Store managers pair RTSP and USB cameras via their authorized store console.
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                    <tr>
                      <th className="p-4">HEALTH</th>
                      <th className="p-4">CAMERA LABEL</th>
                      <th className="p-4">STORE LOCATION</th>
                      <th className="p-4">STREAM SPEC</th>
                      <th className="p-4">FPS</th>
                      <th className="p-4">LAST HEARTBEAT</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {filteredCameras.map((c) => (
                      <tr key={c.cameraId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold ${
                              c.status === "ONLINE"
                                ? "bg-[var(--status-ok)]/15 text-[var(--status-ok)] border border-[var(--status-ok)]/30"
                                : c.status === "DEGRADED"
                                ? "bg-amber-500/15 text-amber-500 dark:text-amber-400 border border-amber-500/30"
                                : "bg-[var(--status-high)]/15 text-[var(--status-high)] border border-[var(--status-high)]/30"
                            }`}
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                            {c.status}
                          </span>
                        </td>
                        <td className="p-4 font-bold text-[var(--text-primary)]">{c.label}</td>
                        <td className="p-4 text-[var(--text-secondary)] font-sans">{c.storeName}</td>
                        <td className="p-4 text-[#38BDF8]">{c.resolution || "1080p (RTSP)"}</td>
                        <td className="p-4 text-[var(--text-primary)]">{c.fps || 30} FPS</td>
                        <td className="p-4 text-[var(--text-muted)]">
                          {c.lastHeartbeatAt ? new Date(c.lastHeartbeatAt).toLocaleTimeString() : "Never"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 5: AUDIT LOGS (Section 7.7) */}
      {/* ============================================================ */}
      {activeTab === "audit" && (
        <div className="bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] overflow-hidden shadow-xl">
          <div className="p-5 border-b border-[var(--border-hairline)] flex justify-between items-center bg-[var(--bg-canvas)]">
            <div>
              <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2">
                <Lock size={16} className="text-[#38BDF8]" /> PLATFORM IMMUTABLE AUDIT LEDGER
              </h3>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Full cryptographic audit trail of Software Owner governance and administrative events.
              </p>
            </div>
          </div>

          {auditLogs.length === 0 ? (
            <div className="p-12 text-center text-xs font-mono text-[var(--text-muted)]">
              No audit logs recorded yet.
            </div>
          ) : (
            <div className="divide-y divide-[var(--border-hairline)] text-xs font-mono">
              {auditLogs.map((log) => (
                <div
                  key={log.logId}
                  className="p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 hover:bg-[var(--bg-panel-raised)] transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[#38BDF8]">{log.action}</span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-black/5 dark:bg-white/5 border border-[var(--border-hairline)] text-[var(--text-muted)]">
                        Actor: {log.actor}
                      </span>
                    </div>
                    {log.tenantId && (
                      <div className="text-[var(--text-secondary)] text-[11px]">
                        Tenant Target: <span className="text-[var(--text-primary)] font-bold">{log.tenantId}</span>
                      </div>
                    )}
                  </div>
                  <div className="text-[var(--text-muted)] text-[11px]">
                    {new Date(log.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL 1: REGISTER NEW COMPANY / TENANT */}
      {/* ============================================================ */}
      {showCreateTenantModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Building size={18} className="text-[#38BDF8]" /> Register New Company / Tenant
              </h3>
              <button
                onClick={() => setShowCreateTenantModal(false)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTenant} className="space-y-3 text-xs font-mono">
              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Company Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Acme Retailers Pvt Ltd"
                  value={createTenantForm.name}
                  onChange={(e) => {
                    const val = e.target.value;
                    setCreateTenantForm((prev) => ({
                      ...prev,
                      name: val,
                      slug: prev.slug || val.toLowerCase().replace(/[^a-z0-9]/g, "-"),
                    }));
                  }}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Tenant Identifier Slug *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. acme-retailers"
                  value={createTenantForm.slug}
                  onChange={(e) =>
                    setCreateTenantForm((prev) => ({
                      ...prev,
                      slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""),
                    }))
                  }
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[#38BDF8] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Primary Contact Email</label>
                <input
                  type="email"
                  placeholder="finance@acme.com"
                  value={createTenantForm.contactEmail}
                  onChange={(e) =>
                    setCreateTenantForm((prev) => ({ ...prev, contactEmail: e.target.value }))
                  }
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Initial Subscription Tier</label>
                <select
                  value={createTenantForm.tierId}
                  onChange={(e) =>
                    setCreateTenantForm((prev) => ({ ...prev, tierId: e.target.value }))
                  }
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                >
                  {plans.map((p) => (
                    <option key={p.tierId} value={p.tierId}>
                      {p.name} ({formatCurrency(p.monthlyPriceCents)}/mo, max {p.maxCameras} cams)
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-2 border-t border-[var(--border-hairline)]">
                <span className="text-[11px] text-[var(--text-muted)] block mb-2">
                  Optional: Initial Store Owner Administrator Credentials
                </span>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <input
                      type="email"
                      placeholder="admin@acme.com"
                      value={createTenantForm.adminEmail}
                      onChange={(e) =>
                        setCreateTenantForm((prev) => ({ ...prev, adminEmail: e.target.value }))
                      }
                      className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2 text-[var(--text-primary)] outline-none"
                    />
                  </div>
                  <div>
                    <input
                      type="password"
                      placeholder="Password"
                      value={createTenantForm.adminPassword}
                      onChange={(e) =>
                        setCreateTenantForm((prev) => ({ ...prev, adminPassword: e.target.value }))
                      }
                      className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2 text-[var(--text-primary)] outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowCreateTenantModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl font-bold shadow-lg shadow-blue-900/30 disabled:opacity-50"
                >
                  {actionSubmitting ? "Registering..." : "Create Tenant"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL 2: SUSPEND / REACTIVATE REASON PROMPT (Section 7.3 & 7.4) */}
      {/* ============================================================ */}
      {showStatusReasonModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <AlertTriangle
                  size={18}
                  className={
                    showStatusReasonModal.targetStatus === "SUSPENDED" ? "text-rose-500 dark:text-rose-400" : "text-emerald-500 dark:text-emerald-400"
                  }
                />
                Confirm {showStatusReasonModal.targetStatus === "SUSPENDED" ? "Suspension" : "Reactivation"}
              </h3>
              <button
                onClick={() => setShowStatusReasonModal(null)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleApplyStatusChange} className="space-y-3 text-xs font-mono">
              <p className="text-[var(--text-secondary)]">
                You are about to change the status of{" "}
                <span className="text-[var(--text-primary)] font-bold">{showStatusReasonModal.name}</span> to{" "}
                <span
                  className={
                    showStatusReasonModal.targetStatus === "SUSPENDED" ? "text-rose-500 dark:text-rose-400 font-bold" : "text-emerald-500 dark:text-emerald-400 font-bold"
                  }
                >
                  {showStatusReasonModal.targetStatus}
                </span>
                .
              </p>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">
                  Mandatory Audit Reason Note *
                </label>
                <textarea
                  required={showStatusReasonModal.targetStatus === "SUSPENDED"}
                  rows={3}
                  placeholder="State the commercial or security reason for this action (e.g. Past due payment notice #1024, requested maintenance window)..."
                  value={statusReason}
                  onChange={(e) => setStatusReason(e.target.value)}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowStatusReasonModal(null)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className={`px-5 py-2 text-white rounded-xl font-bold shadow-lg disabled:opacity-50 ${
                    showStatusReasonModal.targetStatus === "SUSPENDED"
                      ? "bg-rose-600 hover:bg-rose-700 shadow-rose-900/30"
                      : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-900/30"
                  }`}
                >
                  {actionSubmitting ? "Applying..." : "Confirm Action"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL 3: PROVISION STORE OWNER ACCOUNT (Section 7.3) */}
      {/* ============================================================ */}
      {showProvisionOwnerModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <UserPlus size={18} className="text-[#38BDF8]" /> Provision Store Administrator
              </h3>
              <button
                onClick={() => setShowProvisionOwnerModal(null)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleProvisionStoreOwner} className="space-y-3 text-xs font-mono">
              <p className="text-[var(--text-secondary)]">
                Create a tenant-scoped administrator account for{" "}
                <span className="text-[var(--text-primary)] font-bold">{showProvisionOwnerModal.name}</span>. This account
                does NOT grant Software Owner privileges.
              </p>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Admin Email *</label>
                <input
                  type="email"
                  required
                  value={provisionOwnerForm.email}
                  onChange={(e) =>
                    setProvisionOwnerForm((prev) => ({ ...prev, email: e.target.value }))
                  }
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Username</label>
                <input
                  type="text"
                  value={provisionOwnerForm.username}
                  onChange={(e) =>
                    setProvisionOwnerForm((prev) => ({ ...prev, username: e.target.value }))
                  }
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Initial Password *</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  placeholder="••••••••••••"
                  value={provisionOwnerForm.password}
                  onChange={(e) =>
                    setProvisionOwnerForm((prev) => ({ ...prev, password: e.target.value }))
                  }
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowProvisionOwnerModal(null)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl font-bold shadow-lg shadow-blue-900/30 disabled:opacity-50"
                >
                  {actionSubmitting ? "Provisioning..." : "Provision Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL 4: RECORD INVOICE PAYMENT (Section 7.5) */}
      {/* ============================================================ */}
      {showRecordPaymentModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <DollarSign size={18} className="text-emerald-500 dark:text-emerald-400" /> Record Offline Payment
              </h3>
              <button
                onClick={() => setShowRecordPaymentModal(null)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRecordPayment} className="space-y-3 text-xs font-mono">
              <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] space-y-1">
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Invoice Number:</span>
                  <span className="text-[var(--text-primary)] font-bold">{showRecordPaymentModal.invoiceNumber}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Tenant:</span>
                  <span className="text-[var(--text-primary)] font-bold">{showRecordPaymentModal.tenantName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Amount Due:</span>
                  <span className="text-emerald-500 dark:text-emerald-400 font-bold">
                    {formatCurrency(showRecordPaymentModal.amountCents, showRecordPaymentModal.currency)}
                  </span>
                </div>
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Payment Reference ID *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. UTR-9021849102"
                  value={paymentForm.paymentRef}
                  onChange={(e) => setPaymentForm((prev) => ({ ...prev, paymentRef: e.target.value }))}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Payment Method</label>
                <select
                  value={paymentForm.paymentMethod}
                  onChange={(e) => setPaymentForm((prev) => ({ ...prev, paymentMethod: e.target.value }))}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                >
                  <option value="BANK_TRANSFER">Bank Transfer / NEFT / RTGS</option>
                  <option value="UPI">UPI / Digital Gateway</option>
                  <option value="CREDIT_CARD">Credit Card (Offline Swipe)</option>
                  <option value="CHEQUE">Cheque / Demand Draft</option>
                  <option value="CASH">Cash Settlement</option>
                </select>
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Notes / Remarks</label>
                <textarea
                  rows={2}
                  placeholder="Optional audit notes regarding offline verification..."
                  value={paymentForm.notes}
                  onChange={(e) => setPaymentForm((prev) => ({ ...prev, notes: e.target.value }))}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowRecordPaymentModal(null)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold shadow-lg shadow-emerald-900/30 disabled:opacity-50"
                >
                  {actionSubmitting ? "Recording..." : "Record Payment & Settle"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PlatformControlPanelPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs font-mono text-[var(--text-muted)]">
          Loading SaaS Control Deck...
        </div>
      }
    >
      <PlatformControlPanelInner />
    </Suspense>
  );
}
