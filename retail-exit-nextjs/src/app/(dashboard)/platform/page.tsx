"use client";

import React, { useState, useEffect, useMemo, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { safeFetch, formatErrorMessage } from "@/lib/api-client";
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
  EyeOff,
  Sliders,
  DollarSign,
  FileText,
  Filter,
  Check,
  X,
  Radio,
  Server,
  Layers,
  Users,
  UserCheck,
  Sparkles,
  Trash2,
  Edit,
  ShieldCheck,
} from "lucide-react";

interface AccountItem {
  userId: string;
  email: string;
  username: string;
  role: string;
  type: string;
  storeId?: string;
  storeName?: string;
  isActive: boolean;
  createdAt: string;
  lastLoginAt?: string | null;
  isPlatformOwner: boolean;
}

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
  tierId?: string;
  activeCamerasCount?: number;
  subscriptionTier?: string;
  billingStatus?: string;
  paymentStatus?: string;
}

interface PlanItem {
  tierId: string;
  name: string;
  monthlyPriceCents?: number;
  priceCents?: number;
  maxCameras: number;
  maxStores?: number;
  currency?: string;
  billingCycle?: string;
  features?: string[];
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
  const { user, isLoading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();

  const role = (user?.role || "ADMIN").toUpperCase();
  const isSoftwareOwner = role === "SUPER_ADMIN" || user?.isPlatformOwner === true;

  const tabParam = searchParams.get("tab") || "tenants";
  const [activeTab, setActiveTab] = useState<"tenants" | "stores" | "accounts" | "billing" | "cameras" | "audit">(
    (tabParam as any) || "tenants"
  );

  // Sync activeTab when query param changes
  useEffect(() => {
    if (tabParam && ["tenants", "stores", "accounts", "billing", "cameras", "audit"].includes(tabParam)) {
      setActiveTab(tabParam as any);
    }
  }, [tabParam]);

  const setTab = (newTab: "tenants" | "stores" | "accounts" | "billing" | "cameras" | "audit") => {
    setActiveTab(newTab);
    router.push(`/platform?tab=${newTab}`);
  };

  // Data states
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tenants, setTenants] = useState<TenantItem[]>([]);
  const [stores, setStores] = useState<StoreItem[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [cameras, setCameras] = useState<CameraFleetItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);

  // Search & Filters
  const [tenantSearch, setTenantSearch] = useState("");
  const [storeSearch, setStoreSearch] = useState("");
  const [accountSearch, setAccountSearch] = useState("");
  const [accountStatusFilter, setAccountStatusFilter] = useState<string>("ALL");
  const [storeStatusFilter, setStoreStatusFilter] = useState<string>("ALL");
  const [cameraStatusFilter, setCameraStatusFilter] = useState<string>("ALL");

  // Modals
  const [showCreateTenantModal, setShowCreateTenantModal] = useState(false);
  const [showProvisionOwnerModal, setShowProvisionOwnerModal] = useState<TenantItem | null>(null);
  const [showStatusReasonModal, setShowStatusReasonModal] = useState<{
    type: "tenant" | "store" | "account";
    id: string;
    name: string;
    currentStatus: string;
    targetStatus: string;
  } | null>(null);
  const [statusReason, setStatusReason] = useState("");
  const [showRecordPaymentModal, setShowRecordPaymentModal] = useState<InvoiceItem | null>(null);

  // Custom Plan Creator & Editor Modal
  const [showPlanModal, setShowPlanModal] = useState<{ mode: "create" | "edit"; plan?: PlanItem } | null>(null);
  const [planForm, setPlanForm] = useState({
    name: "",
    monthlyPriceRupees: 4999,
    maxCameras: 4,
    currency: "INR",
    billingCycle: "MONTHLY",
    features: [
      "AI Object & Person Detection",
      "Dense Bookshelf & Material Stack Counter",
      "ArcFace 360 Biometrics & Staff Verification",
      "Automatic Turnstile & Hardware Lock",
      "Multi-Lane Crossings & Analytics",
      "Invoice OCR Discrepancy Auditing",
      "30-Day HD Snapshot Storage",
    ],
  });

  // Override Store Subscription Modal
  const [showOverrideSubModal, setShowOverrideSubModal] = useState<StoreItem | null>(null);
  const [overrideSubForm, setOverrideSubForm] = useState({
    tierId: "tier_starter_01",
    status: "ACTIVE",
    extensionDays: 30,
    paymentVerified: true,
    notes: "Manual subscription adjustment by Software Owner",
  });

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

  // Password visibility & inline validation errors
  const [showCreateAdminPassword, setShowCreateAdminPassword] = useState(false);
  const [showProvisionPassword, setShowProvisionPassword] = useState(false);
  const [createTenantError, setCreateTenantError] = useState<string | null>(null);
  const [provisionOwnerError, setProvisionOwnerError] = useState<string | null>(null);

  const fetchAllData = async (isManual = false) => {
    try {
      if (isManual) setRefreshing(true);
      else setLoading(true);

      const [resTenants, resStores, resPlans, resSubs, resInvoices, resCameras, resAudit, resUsers] =
        await Promise.all([
          safeFetch("/api/platform/tenants"),
          safeFetch("/api/platform/stores"),
          safeFetch("/api/platform/billing/plans"),
          safeFetch("/api/platform/subscriptions"),
          safeFetch("/api/platform/billing/invoices"),
          safeFetch("/api/platform/cameras/fleet-health"),
          safeFetch("/api/platform/audit-logs"),
          safeFetch("/api/platform/users"),
        ]);

      if (resTenants.ok) setTenants(await resTenants.json());
      if (resStores.ok) setStores(await resStores.json());
      if (resPlans.ok) setPlans(await resPlans.json());
      if (resSubs.ok) setSubscriptions(await resSubs.json());
      if (resInvoices.ok) setInvoices(await resInvoices.json());
      if (resCameras.ok) setCameras(await resCameras.json());
      if (resAudit.ok) setAuditLogs(await resAudit.json());
      if (resUsers.ok) setAccounts(await resUsers.json());
    } catch (e) {
      console.warn("Failed to load platform data:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!isSoftwareOwner) {
      router.replace("/");
      return;
    }
    fetchAllData();
  }, [authLoading, isSoftwareOwner]);

  // Handlers
  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateTenantError(null);
    if (!createTenantForm.name.trim() || !createTenantForm.slug.trim()) {
      setCreateTenantError("Please provide Company Name and Slug.");
      return;
    }

    const emailTrim = createTenantForm.adminEmail.trim();
    const pwd = createTenantForm.adminPassword;

    if (emailTrim || pwd) {
      if (!emailTrim || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailTrim)) {
        setCreateTenantError("Incorrect email ID. Please provide a valid email format (e.g. admin@company.com).");
        return;
      }
      if (!pwd || pwd.length < 8) {
        setCreateTenantError("Incorrect password. Password must be at least 8 characters long.");
        return;
      }
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
          adminEmail: emailTrim || undefined,
          adminPassword: pwd || undefined,
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
        setCreateTenantError(null);
        fetchAllData(true);
      } else {
        const err = await res.json().catch(() => null);
        const parsed = formatErrorMessage(err?.detail || err?.message || err) || "Failed to create tenant. Please verify inputs.";
        setCreateTenantError(parsed);
      }
    } catch (e: any) {
      setCreateTenantError(e?.message || "Request failed.");
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
      let url = "";
      let payload: any = {};

      if (showStatusReasonModal.type === "tenant") {
        url = `/api/platform/tenants/${showStatusReasonModal.id}/status`;
        payload = {
          status: showStatusReasonModal.targetStatus,
          reason: statusReason.trim() || "Administrative action by Software Owner",
        };
      } else if (showStatusReasonModal.type === "store") {
        url = `/api/platform/stores/${showStatusReasonModal.id}/status`;
        payload = {
          status: showStatusReasonModal.targetStatus,
          reason: statusReason.trim() || "Administrative action by Software Owner",
        };
      } else {
        url = `/api/platform/users/${showStatusReasonModal.id}/status`;
        payload = {
          isActive: showStatusReasonModal.targetStatus === "ACTIVE",
          reason: statusReason.trim() || "Administrative action by Software Owner",
        };
      }

      const res = await safeFetch(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setShowStatusReasonModal(null);
        setStatusReason("");
        fetchAllData(true);
      } else {
        const err = await res.json().catch(() => null);
        alert(formatErrorMessage(err?.detail || err?.message || err) || "Failed to update status.");
      }
    } catch (e: any) {
      alert(e.message || "Failed to update status.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleProvisionStoreOwner = async (e: React.FormEvent) => {
    e.preventDefault();
    setProvisionOwnerError(null);
    if (!showProvisionOwnerModal) return;

    const emailTrim = provisionOwnerForm.email.trim();
    const pwd = provisionOwnerForm.password;

    if (!emailTrim || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailTrim)) {
      setProvisionOwnerError("Incorrect email ID. Please provide a valid email format (e.g. admin@company.com).");
      return;
    }
    if (!pwd || pwd.length < 8) {
      setProvisionOwnerError("Incorrect password. Password must be at least 8 characters long.");
      return;
    }

    setActionSubmitting(true);
    try {
      const res = await safeFetch(`/api/platform/tenants/${showProvisionOwnerModal.tenantId}/provision-owner`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailTrim,
          username: provisionOwnerForm.username.trim() || emailTrim.split("@")[0],
          password: pwd,
          role: "ADMIN",
        }),
      });

      if (res.ok) {
        setShowProvisionOwnerModal(null);
        setProvisionOwnerForm({ email: "", username: "", password: "" });
        setProvisionOwnerError(null);
        fetchAllData(true);
      } else {
        const err = await res.json().catch(() => null);
        const parsed = formatErrorMessage(err?.detail || err?.message || err) || "Incorrect email ID or password.";
        setProvisionOwnerError(parsed);
      }
    } catch (e: any) {
      setProvisionOwnerError(e?.message || "Failed to provision owner.");
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

  const handleToggleUserStatus = (acc: AccountItem) => {
    setShowStatusReasonModal({
      type: "account",
      id: acc.userId,
      name: `${acc.username || acc.email} (${acc.role})`,
      currentStatus: acc.isActive ? "ACTIVE" : "SUSPENDED",
      targetStatus: acc.isActive ? "SUSPENDED" : "ACTIVE",
    });
    setStatusReason("");
  };

  const toggleFeature = (feat: string) => {
    setPlanForm((prev) => {
      const exists = prev.features.includes(feat);
      return {
        ...prev,
        features: exists ? prev.features.filter((f) => f !== feat) : [...prev.features, feat],
      };
    });
  };

  const handleSavePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!planForm.name.trim()) {
      alert("Plan name is required.");
      return;
    }
    setActionSubmitting(true);
    try {
      const priceCents = Math.round(Number(planForm.monthlyPriceRupees || 0) * 100);
      const payload = {
        name: planForm.name.trim(),
        maxCameras: Number(planForm.maxCameras) || 4,
        priceCents: priceCents,
        currency: planForm.currency,
        billingCycle: planForm.billingCycle,
        features: planForm.features.filter(Boolean),
      };

      let res;
      if (showPlanModal?.mode === "edit" && showPlanModal.plan) {
        res = await safeFetch(`/api/platform/billing/plans/${showPlanModal.plan.tierId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        res = await safeFetch("/api/platform/billing/plans", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      if (res.ok) {
        setShowPlanModal(null);
        fetchAllData(true);
        alert(`Subscription plan '${planForm.name.trim()}' saved successfully.`);
      } else {
        const err = await res.json().catch(() => null);
        alert(formatErrorMessage(err?.detail || err?.message || "Failed to save plan."));
      }
    } catch (err: any) {
      alert(err?.message || "Network error saving plan.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleDeletePlan = async (tierId: string, planName: string) => {
    if (!confirm(`Are you sure you want to delete the plan '${planName}'? This action cannot be undone.`)) return;
    setActionSubmitting(true);
    try {
      const res = await safeFetch(`/api/platform/billing/plans/${tierId}`, { method: "DELETE" });
      if (res.ok) {
        fetchAllData(true);
        alert(`Plan '${planName}' deleted successfully.`);
      } else {
        const err = await res.json().catch(() => null);
        alert(formatErrorMessage(err?.detail || err?.message || "Failed to delete plan."));
      }
    } catch (err: any) {
      alert(err?.message || "Error deleting plan.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleApplyStoreSubscription = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showOverrideSubModal) return;
    setActionSubmitting(true);
    try {
      const res = await safeFetch(`/api/platform/stores/${showOverrideSubModal.storeId}/subscription`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tierId: overrideSubForm.tierId,
          status: overrideSubForm.status,
          extensionDays: Number(overrideSubForm.extensionDays) || 30,
          paymentVerified: overrideSubForm.paymentVerified,
          notes: overrideSubForm.notes,
        }),
      });
      if (res.ok) {
        setShowOverrideSubModal(null);
        fetchAllData(true);
        alert(`Store subscription successfully updated.`);
      } else {
        const err = await res.json().catch(() => null);
        alert(formatErrorMessage(err?.detail || err?.message || "Failed to override subscription."));
      }
    } catch (err: any) {
      alert(err?.message || "Network error overriding subscription.");
    } finally {
      setActionSubmitting(false);
    }
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

  const filteredAccounts = useMemo(() => {
    return (accounts || []).filter((acc) => {
      const q = (accountSearch || "").toLowerCase();
      const email = String(acc.email || "").toLowerCase();
      const username = String(acc.username || "").toLowerCase();
      const storeName = String(acc.storeName || "").toLowerCase();
      const role = String(acc.role || "").toLowerCase();
      const matchesSearch = email.includes(q) || username.includes(q) || storeName.includes(q) || role.includes(q);
      const matchesStatus =
        accountStatusFilter === "ALL" ||
        (accountStatusFilter === "ACTIVE" && acc.isActive) ||
        (accountStatusFilter === "SUSPENDED" && !acc.isActive);
      return matchesSearch && matchesStatus;
    });
  }, [accounts, accountSearch, accountStatusFilter]);

  const filteredCameras = useMemo(() => {
    return (cameras || []).filter((c) => {
      if (cameraStatusFilter === "ALL") return true;
      return c.status === cameraStatusFilter;
    });
  }, [cameras, cameraStatusFilter]);

  if (authLoading || !isSoftwareOwner) {
    return (
      <div className="flex h-64 items-center justify-center font-mono text-xs text-[var(--text-muted)] gap-2">
        <RefreshCw size={16} className="animate-spin text-[#38BDF8]" />
        Verifying software owner authorization...
      </div>
    );
  }

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
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]"
          }`}
        >
          <Building size={15} /> Companies & Tenants ({tenants.length})
        </button>

        <button
          onClick={() => setTab("stores")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "stores"
              ? "border-[#4FD1B3] text-[#4FD1B3] font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]"
          }`}
        >
          <Store size={15} /> Stores Fleet ({stores.length})
        </button>

        <button
          onClick={() => setTab("accounts")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "accounts"
              ? "border-violet-400 text-violet-400 font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]"
          }`}
        >
          <Users size={15} /> User Accounts & Security ({accounts.length})
        </button>

        <button
          onClick={() => setTab("billing")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "billing"
              ? "border-indigo-400 text-indigo-400 font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]"
          }`}
        >
          <CreditCard size={15} /> Subscriptions & Billing ({subscriptions.length})
        </button>

        <button
          onClick={() => setTab("cameras")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "cameras"
              ? "border-amber-400 text-amber-400 font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]"
          }`}
        >
          <Camera size={15} /> Camera Fleet Health ({cameras.length})
        </button>

        <button
          onClick={() => setTab("audit")}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-all shrink-0 ${
            activeTab === "audit"
              ? "border-rose-400 text-rose-400 font-bold"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-subtle)]"
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
              onClick={() => {
                setCreateTenantError(null);
                setShowCreateAdminPassword(false);
                setShowCreateTenantModal(true);
              }}
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
                                setProvisionOwnerError(null);
                                setShowProvisionPassword(false);
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
      {/* TAB: USER ACCOUNTS & SECURITY GOVERNANCE */}
      {/* ============================================================ */}
      {activeTab === "accounts" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
              <div className="relative w-full sm:w-80">
                <Search className="absolute left-3.5 top-3 text-[var(--text-muted)]" size={15} />
                <input
                  type="text"
                  placeholder="Search user, email, store, or role..."
                  value={accountSearch}
                  onChange={(e) => setAccountSearch(e.target.value)}
                  className="w-full bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl pl-10 pr-4 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8] shadow-inner font-mono"
                />
              </div>

              <select
                value={accountStatusFilter}
                onChange={(e) => setAccountStatusFilter(e.target.value)}
                className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl px-3 py-2 text-xs text-[var(--text-primary)] outline-none font-mono"
              >
                <option value="ALL">All Account Statuses</option>
                <option value="ACTIVE">Active Users Only</option>
                <option value="SUSPENDED">Suspended Users Only</option>
              </select>
            </div>

            <div className="text-xs font-mono text-cyan-400 bg-cyan-950/30 border border-cyan-800/40 px-3.5 py-1.5 rounded-xl flex items-center gap-2">
              <ShieldAlert size={14} className="text-cyan-400 shrink-0" />
              <span>Instant auto-session termination on suspension; password preserved on reactivation</span>
            </div>
          </div>

          <div className="card-3d bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl overflow-hidden shadow-2xl">
            {filteredAccounts.length === 0 ? (
              <div className="p-12 text-center text-xs font-mono text-[var(--text-muted)] space-y-2">
                <Users size={32} className="mx-auto opacity-30 mb-2" />
                <div>No user accounts found matching query.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                    <tr>
                      <th className="p-4">STATUS</th>
                      <th className="p-4">USER ACCOUNT</th>
                      <th className="p-4">ROLE & ACCESS</th>
                      <th className="p-4">STORE / ASSIGNMENT</th>
                      <th className="p-4">LAST LOGIN</th>
                      <th className="p-4 text-right">ADMIN ACTION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {filteredAccounts.map((acc) => (
                      <tr key={acc.userId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider ${
                              acc.isActive
                                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-[0_0_8px_rgba(16,185,129,0.2)]"
                                : "bg-rose-500/15 text-rose-400 border border-rose-500/30 shadow-[0_0_8px_rgba(244,63,94,0.2)]"
                            }`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${acc.isActive ? "bg-emerald-400 animate-pulse" : "bg-rose-400"}`} />
                            {acc.isActive ? "ACTIVE" : "SUSPENDED"}
                          </span>
                        </td>
                        <td className="p-4">
                          <div className="font-bold text-[var(--text-primary)] font-sans text-sm">{acc.username || acc.email.split("@")[0]}</div>
                          <div className="text-[11px] text-[var(--text-muted)] font-mono">{acc.email}</div>
                        </td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            acc.isPlatformOwner
                              ? "bg-violet-500/15 text-violet-400 border border-violet-500/30"
                              : acc.role === "ADMIN"
                              ? "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                              : "bg-slate-500/15 text-slate-300 border border-slate-500/30"
                          }`}>
                            {acc.isPlatformOwner ? "PLATFORM OWNER" : acc.role}
                          </span>
                        </td>
                        <td className="p-4 text-[var(--text-secondary)] font-sans">
                          {acc.storeName ? (
                            <span className="flex items-center gap-1.5 text-cyan-400 font-medium">
                              <Store size={13} /> {acc.storeName}
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)]">Global Management</span>
                          )}
                        </td>
                        <td className="p-4 text-[var(--text-muted)]">
                          {acc.lastLoginAt ? new Date(acc.lastLoginAt).toLocaleString() : "Never"}
                        </td>
                        <td className="p-4 text-right">
                          {acc.isPlatformOwner && (acc.userId === user?.user_id || acc.userId === user?.id) ? (
                            <span className="text-[11px] text-[var(--text-muted)] italic">Current Session</span>
                          ) : (
                            <button
                              onClick={() => handleToggleUserStatus(acc)}
                              className={`btn-3d px-3.5 py-1.5 rounded-xl text-[11px] font-bold transition-all shadow-md ${
                                acc.isActive
                                  ? "btn-3d-danger text-rose-300 border border-rose-500/40"
                                  : "btn-3d-success text-emerald-300 border border-emerald-500/40"
                              }`}
                            >
                              {acc.isActive ? "Suspend & Terminate Session" : "Reactivate (Keep Credentials)"}
                            </button>
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
      {/* TAB 3: SUBSCRIPTIONS & BILLING (Section 7.5) */}
      {/* ============================================================ */}
      {activeTab === "billing" && (
        <div className="space-y-6">
          {/* Subscription Tiers Catalog */}
          <div className="bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] p-6 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[var(--border-hairline)] pb-4">
              <div>
                <h2 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                  <CreditCard size={18} className="text-indigo-400" /> SaaS Subscription Tier Catalog
                </h2>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  Configure custom plans, set monthly pricing in INR, customize camera quotas, and assign access flags manually.
                </p>
              </div>

              <button
                onClick={() => {
                  setShowPlanModal({ mode: "create" });
                  setPlanForm({
                    name: "",
                    monthlyPriceRupees: 4999,
                    maxCameras: 4,
                    currency: "INR",
                    billingCycle: "MONTHLY",
                    features: [
                      "AI Object & Person Detection",
                      "Dense Bookshelf & Material Stack Counter",
                      "ArcFace 360 Biometrics & Staff Verification",
                      "Automatic Turnstile & Hardware Lock",
                      "30-Day HD Snapshot Storage",
                    ],
                  });
                }}
                className="btn-3d btn-3d-primary px-4 py-2 rounded-xl text-xs font-bold text-white flex items-center gap-2 shadow-lg"
              >
                <Plus size={14} /> Create Custom Plan
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {plans.map((p) => (
                <div
                  key={p.tierId}
                  className="card-3d box-3d bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-2xl p-5 space-y-4 relative flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider font-mono">
                          {p.name}
                        </span>
                        <div className="text-[11px] text-[var(--text-muted)] font-mono">ID: {p.tierId}</div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 font-bold uppercase">
                        {p.billingCycle || "MONTHLY"}
                      </span>
                    </div>

                    <div className="text-2xl font-bold font-mono text-[var(--text-primary)]">
                      {formatCurrency(p.priceCents ?? p.monthlyPriceCents ?? 0, p.currency)}
                      <span className="text-xs text-[var(--text-muted)] font-normal"> / month</span>
                    </div>

                    <div className="text-xs text-[var(--text-secondary)] font-mono space-y-2 pt-3 border-t border-[var(--border-hairline)]">
                      <div className="flex items-center gap-1.5 text-[var(--text-primary)] font-semibold">
                        <Camera size={14} className="text-[#38BDF8]" />
                        <span>Up to {p.maxCameras} cameras quota</span>
                      </div>
                      <div className="space-y-1.5 pt-1">
                        {(p.features && p.features.length > 0 ? p.features : [
                          "AI Object & Person Detection",
                          "Dense Material Counting",
                          "Automatic Turnstile Lock"
                        ]).map((f, i) => (
                          <div key={i} className="flex items-center gap-2 text-emerald-400 text-[11px]">
                            <Check size={12} className="shrink-0" />
                            <span>{f}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-[var(--border-hairline)] flex items-center justify-between gap-2">
                    <button
                      onClick={() => {
                        setShowPlanModal({ mode: "edit", plan: p });
                        setPlanForm({
                          name: p.name,
                          monthlyPriceRupees: Math.round(((p.priceCents ?? p.monthlyPriceCents ?? 0) / 100)),
                          maxCameras: p.maxCameras,
                          currency: p.currency || "INR",
                          billingCycle: p.billingCycle || "MONTHLY",
                          features: p.features && p.features.length > 0 ? p.features : [
                            "AI Object & Person Detection",
                            "Dense Bookshelf & Material Stack Counter",
                            "Automatic Turnstile & Hardware Lock",
                          ],
                        });
                      }}
                      className="btn-3d px-3 py-1.5 rounded-xl bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-cyan-300 border border-cyan-500/30 text-xs font-bold flex items-center gap-1.5 transition-colors"
                    >
                      <Edit size={13} /> Edit Pricing & Access
                    </button>
                    <button
                      onClick={() => handleDeletePlan(p.tierId, p.name)}
                      className="p-1.5 rounded-xl hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 transition-colors"
                      title="Delete Plan"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Store Subscriptions & Manual Plan Assignment */}
          <div className="card-3d bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] overflow-hidden shadow-2xl space-y-4">
            <div className="p-5 border-b border-[var(--border-hairline)] flex justify-between items-center bg-[var(--bg-canvas)]">
              <div>
                <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2">
                  <ShieldCheck size={16} className="text-emerald-400" /> ACTIVE STORE SUBSCRIPTIONS & MANUAL PLAN ASSIGNMENTS
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  Directly customize subscription plans, payment approvals, and active access rules per individual store location.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                  <tr>
                    <th className="p-4">STORE LOCATION</th>
                    <th className="p-4">COMPANY / TENANT</th>
                    <th className="p-4">CURRENT PLAN</th>
                    <th className="p-4">CAMERAS QUOTA</th>
                    <th className="p-4">SUBSCRIPTION STATUS</th>
                    <th className="p-4 text-right">MANUAL OVERRIDE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                  {stores.map((s) => {
                    const matchedPlan = plans.find((p) => p.tierId === s.tierId);
                    return (
                      <tr key={s.storeId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                        <td className="p-4">
                          <div className="font-bold text-[var(--text-primary)] font-sans text-sm flex items-center gap-2">
                            <Store size={14} className="text-cyan-400" /> {s.name}
                          </div>
                          <div className="text-[11px] text-[var(--text-muted)] font-mono">{s.storeId}</div>
                        </td>
                        <td className="p-4 text-[var(--text-secondary)] font-sans">{s.tenantName}</td>
                        <td className="p-4">
                          <span className="px-2.5 py-1 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 font-bold uppercase text-[11px]">
                            {matchedPlan?.name || s.tierId}
                          </span>
                        </td>
                        <td className="p-4 text-cyan-400 font-bold">
                          {s.activeCamerasCount} / {matchedPlan?.maxCameras ?? s.maxCameras} Allowed
                        </td>
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold ${
                              s.status === "ACTIVE"
                                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                            }`}
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-current" />
                            {s.status}
                          </span>
                        </td>
                        <td className="p-4 text-right">
                          <button
                            onClick={() => {
                              setShowOverrideSubModal(s);
                              setOverrideSubForm({
                                tierId: s.tierId || "tier_starter_01",
                                status: s.status || "ACTIVE",
                                extensionDays: 30,
                                paymentVerified: true,
                                notes: "Plan manually assigned by Software Owner",
                              });
                            }}
                            className="btn-3d px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-900/30"
                          >
                            Assign / Override Plan
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
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
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card-3d bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
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
              {createTenantError && (
                <div
                  role="alert"
                  className="p-3 rounded-xl border border-[var(--status-high)]/40 bg-[var(--status-high)]/10 text-[var(--status-high)] text-xs flex items-start gap-2 animate-in fade-in slide-in-from-top-1"
                >
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                  <span className="flex-1 font-medium">{createTenantError}</span>
                  <button
                    type="button"
                    onClick={() => setCreateTenantError(null)}
                    className="hover:opacity-75"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

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
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
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
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[#38BDF8] outline-none focus:border-[#38BDF8]"
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
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Initial Subscription Tier</label>
                <select
                  value={createTenantForm.tierId}
                  onChange={(e) =>
                    setCreateTenantForm((prev) => ({ ...prev, tierId: e.target.value }))
                  }
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                >
                  {plans.map((p) => (
                    <option key={p.tierId} value={p.tierId}>
                      {p.name} ({formatCurrency(p.priceCents ?? p.monthlyPriceCents ?? 0)}/mo, max {p.maxCameras} cams)
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
                      className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                    />
                  </div>
                  <div className="relative">
                    <input
                      type={showCreateAdminPassword ? "text" : "password"}
                      placeholder="Password (min 8 chars)"
                      value={createTenantForm.adminPassword}
                      onChange={(e) =>
                        setCreateTenantForm((prev) => ({ ...prev, adminPassword: e.target.value }))
                      }
                      className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2 pr-8 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowCreateAdminPassword(!showCreateAdminPassword)}
                      className="absolute right-2 top-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors focus:outline-none"
                      title={showCreateAdminPassword ? "Hide password" : "Show password"}
                      aria-label={showCreateAdminPassword ? "Hide password" : "Show password"}
                    >
                      {showCreateAdminPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowCreateTenantModal(false)}
                  className="btn-3d px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="btn-3d btn-3d-primary px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl font-bold shadow-lg shadow-blue-900/30 disabled:opacity-50"
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
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card-3d bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
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
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowStatusReasonModal(null)}
                  className="btn-3d px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className={`btn-3d px-5 py-2 text-white rounded-xl font-bold shadow-lg disabled:opacity-50 ${
                    showStatusReasonModal.targetStatus === "SUSPENDED"
                      ? "btn-3d-danger bg-rose-600 hover:bg-rose-700 shadow-rose-900/30"
                      : "btn-3d-success bg-emerald-600 hover:bg-emerald-700 shadow-emerald-900/30"
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
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card-3d bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
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
              {provisionOwnerError && (
                <div
                  role="alert"
                  className="p-3 rounded-xl border border-[var(--status-high)]/40 bg-[var(--status-high)]/10 text-[var(--status-high)] text-xs flex items-start gap-2 animate-in fade-in slide-in-from-top-1"
                >
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                  <span className="flex-1 font-medium">{provisionOwnerError}</span>
                  <button
                    type="button"
                    onClick={() => setProvisionOwnerError(null)}
                    className="hover:opacity-75"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

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
                  placeholder="admin@company.com"
                  value={provisionOwnerForm.email}
                  onChange={(e) =>
                    setProvisionOwnerForm((prev) => ({ ...prev, email: e.target.value }))
                  }
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Username</label>
                <input
                  type="text"
                  placeholder="e.g. store_admin"
                  value={provisionOwnerForm.username}
                  onChange={(e) =>
                    setProvisionOwnerForm((prev) => ({ ...prev, username: e.target.value }))
                  }
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Initial Password *</label>
                <div className="relative">
                  <input
                    type={showProvisionPassword ? "text" : "password"}
                    required
                    minLength={8}
                    placeholder="Min. 8 characters (e.g. Pass@1234)"
                    value={provisionOwnerForm.password}
                    onChange={(e) =>
                      setProvisionOwnerForm((prev) => ({ ...prev, password: e.target.value }))
                    }
                    className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 pr-10 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowProvisionPassword(!showProvisionPassword)}
                    className="absolute right-3 top-3 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors focus:outline-none"
                    title={showProvisionPassword ? "Hide password" : "Show password"}
                    aria-label={showProvisionPassword ? "Hide password" : "Show password"}
                  >
                    {showProvisionPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <div className="mt-1 text-[11px] text-[var(--text-muted)]">
                  Must be at least 8 characters long.
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowProvisionOwnerModal(null)}
                  className="btn-3d px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="btn-3d btn-3d-primary px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl font-bold shadow-lg shadow-blue-900/30 disabled:opacity-50"
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
        <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card-3d bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
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
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase">Payment Method</label>
                <select
                  value={paymentForm.paymentMethod}
                  onChange={(e) => setPaymentForm((prev) => ({ ...prev, paymentMethod: e.target.value }))}
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
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
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowRecordPaymentModal(null)}
                  className="btn-3d px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="btn-3d btn-3d-success px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold shadow-lg shadow-emerald-900/30 disabled:opacity-50"
                >
                  {actionSubmitting ? "Recording..." : "Record Payment & Settle"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL 5: CREATE / EDIT CUSTOM SUBSCRIPTION PLAN */}
      {/* ============================================================ */}
      {showPlanModal && (
        <div className="fixed inset-0 z-[9999] bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="card-3d bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                <CreditCard size={18} className="text-indigo-400" />
                {showPlanModal.mode === "create" ? "Create Custom SaaS Subscription Plan" : `Edit Plan: ${showPlanModal.plan?.name}`}
              </h3>
              <button
                onClick={() => setShowPlanModal(null)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSavePlan} className="space-y-4 text-xs font-mono">
              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Plan Display Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Enterprise Retail Ultra, Supermarket Pro"
                  value={planForm.name}
                  onChange={(e) => setPlanForm((prev) => ({ ...prev, name: e.target.value }))}
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Monthly Price (INR ₹) *</label>
                  <input
                    type="number"
                    required
                    min={0}
                    step={1}
                    value={planForm.monthlyPriceRupees}
                    onChange={(e) => setPlanForm((prev) => ({ ...prev, monthlyPriceRupees: Number(e.target.value) }))}
                    className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                  />
                  <div className="text-[10px] text-[var(--text-muted)] mt-1 font-sans">
                    Equivalent to ₹{Number(planForm.monthlyPriceRupees || 0).toLocaleString("en-IN")}/mo
                  </div>
                </div>

                <div>
                  <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Max Cameras Quota *</label>
                  <input
                    type="number"
                    required
                    min={1}
                    max={128}
                    value={planForm.maxCameras}
                    onChange={(e) => setPlanForm((prev) => ({ ...prev, maxCameras: Number(e.target.value) }))}
                    className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                  />
                  <div className="text-[10px] text-[var(--text-muted)] mt-1 font-sans">
                    Physical RTSP/CCTV channels allowed
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Billing Frequency</label>
                  <select
                    value={planForm.billingCycle}
                    onChange={(e) => setPlanForm((prev) => ({ ...prev, billingCycle: e.target.value }))}
                    className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                  >
                    <option value="MONTHLY">Monthly Renewal</option>
                    <option value="ANNUAL">Annual Contract</option>
                    <option value="QUARTERLY">Quarterly Renewal</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Currency</label>
                  <select
                    value={planForm.currency}
                    onChange={(e) => setPlanForm((prev) => ({ ...prev, currency: e.target.value }))}
                    className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                  >
                    <option value="INR">INR (₹)</option>
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-2 uppercase font-semibold">
                  Feature Flags & Access Permissions (Manual Software Owner Override)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] max-h-44 overflow-y-auto">
                  {[
                    "AI Object & Person Detection",
                    "Dense Bookshelf & Material Stack Counter",
                    "ArcFace 360 Biometrics & Staff Verification",
                    "Automatic Turnstile & Hardware Lock",
                    "Multi-Lane Crossings & Analytics",
                    "Invoice OCR Discrepancy Auditing",
                    "30-Day HD Snapshot Storage",
                    "90-Day HD Snapshot Storage",
                    "Dedicated API & Webhook Dispatch",
                  ].map((feat) => {
                    const isChecked = planForm.features.includes(feat);
                    return (
                      <label
                        key={feat}
                        onClick={() => toggleFeature(feat)}
                        className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer text-[11px] transition-colors border ${
                          isChecked
                            ? "bg-indigo-950/40 border-indigo-500/40 text-indigo-300 font-semibold"
                            : "bg-[var(--bg-panel)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                        }`}
                      >
                        <div className={`w-4 h-4 rounded flex items-center justify-center border transition-all ${
                          isChecked ? "bg-indigo-600 border-indigo-400 text-white" : "border-slate-600"
                        }`}>
                          {isChecked && <Check size={11} />}
                        </div>
                        <span className="truncate">{feat}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowPlanModal(null)}
                  className="btn-3d px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="btn-3d btn-3d-primary px-5 py-2 text-white rounded-xl font-bold shadow-lg shadow-indigo-900/30 text-xs disabled:opacity-50"
                >
                  {actionSubmitting ? "Saving..." : showPlanModal.mode === "create" ? "Create Plan" : "Update Plan"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL 6: MANUAL STORE SUBSCRIPTION OVERRIDE */}
      {/* ============================================================ */}
      {showOverrideSubModal && (
        <div className="fixed inset-0 z-[9999] bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="card-3d bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <div>
                <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                  <ShieldCheck size={18} className="text-emerald-400" /> Manual Store Plan Override
                </h3>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                  Store: <span className="text-[var(--text-primary)] font-bold">{showOverrideSubModal.name}</span>
                </p>
              </div>
              <button
                onClick={() => setShowOverrideSubModal(null)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleApplyStoreSubscription} className="space-y-4 text-xs font-mono">
              <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Parent Company:</span>
                  <span className="text-[var(--text-primary)] font-bold">{showOverrideSubModal.tenantName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Store ID:</span>
                  <span className="text-cyan-400 font-bold">{showOverrideSubModal.storeId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">Active Cameras:</span>
                  <span className="text-[var(--text-primary)] font-bold">
                    {showOverrideSubModal.activeCamerasCount ?? showOverrideSubModal.cameraCount ?? 0} cameras
                  </span>
                </div>
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Assign Subscription Tier</label>
                <select
                  value={overrideSubForm.tierId}
                  onChange={(e) => setOverrideSubForm((prev) => ({ ...prev, tierId: e.target.value }))}
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none font-sans"
                >
                  {plans.map((p) => (
                    <option key={p.tierId} value={p.tierId}>
                      {p.name} — {formatCurrency(p.priceCents ?? p.monthlyPriceCents ?? 0, p.currency)}/mo ({p.maxCameras} Cams)
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Subscription Status</label>
                  <select
                    value={overrideSubForm.status}
                    onChange={(e) => setOverrideSubForm((prev) => ({ ...prev, status: e.target.value }))}
                    className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="TRIAL">TRIAL</option>
                    <option value="SUSPENDED">SUSPENDED</option>
                    <option value="EXPIRED">EXPIRED</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Add Extension Days</label>
                  <input
                    type="number"
                    min={1}
                    max={730}
                    value={overrideSubForm.extensionDays}
                    onChange={(e) => setOverrideSubForm((prev) => ({ ...prev, extensionDays: Number(e.target.value) }))}
                    className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                  />
                </div>
              </div>

              <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)]">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={overrideSubForm.paymentVerified}
                    onChange={(e) => setOverrideSubForm((prev) => ({ ...prev, paymentVerified: e.target.checked }))}
                    className="w-4 h-4 rounded text-emerald-500 focus:ring-0 accent-emerald-500"
                  />
                  <span className="text-[11px] text-[var(--text-primary)] font-semibold font-sans">
                    Offline Commercial Settlement Confirmed
                  </span>
                </label>
                <p className="text-[10px] text-[var(--text-muted)] mt-1 font-sans pl-6">
                  Check this if the company owner paid offline or through direct bank contract.
                </p>
              </div>

              <div>
                <label className="block text-[var(--text-secondary)] mb-1 uppercase font-semibold">Audit Remarks / Notes</label>
                <textarea
                  rows={2}
                  placeholder="Reason for manual tier upgrade or subscription modification..."
                  value={overrideSubForm.notes}
                  onChange={(e) => setOverrideSubForm((prev) => ({ ...prev, notes: e.target.value }))}
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-2.5 text-[var(--text-primary)] outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowOverrideSubModal(null)}
                  className="btn-3d px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-xl text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="btn-3d btn-3d-primary px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold shadow-lg shadow-indigo-900/30 text-xs disabled:opacity-50"
                >
                  {actionSubmitting ? "Applying..." : "Confirm & Save Override"}
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
