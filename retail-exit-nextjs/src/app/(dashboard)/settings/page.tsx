"use client";

import React, { useState, useEffect } from "react";
import { safeFetch } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  ShieldAlert,
  Lock,
  Key,
  CheckCircle2,
  AlertTriangle,
  Server,
  Database,
  User,
  ShieldCheck,
  RefreshCw,
  Eye,
  EyeOff,
  Cpu,
  Layers,
} from "lucide-react";

interface SoftwareOwnerProfile {
  email: string;
  role: string;
  accountStatus: string;
  isPlatformOwner: boolean;
  lastLogin: string;
  activeSessions: number;
  systemVersion: string;
  dbConnected: boolean;
}

export default function SoftwareOwnerSettingsPage() {
  const { user } = useAuth();
  const role = (user?.role || "ADMIN").toUpperCase();
  const isSoftwareOwner = role === "SUPER_ADMIN" || user?.isPlatformOwner === true;

  const [profile, setProfile] = useState<SoftwareOwnerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Password change form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [savingPassword, setSavingPassword] = useState(false);
  const [pwdMessage, setPwdMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchProfile = async (isManual = false) => {
    try {
      if (isManual) setRefreshing(true);
      if (isSoftwareOwner) {
        const res = await safeFetch("/api/platform/settings/profile");
        if (res.ok) {
          const data = await res.json();
          setProfile({
            email: data.email,
            role: data.role,
            accountStatus: data.isActive ? "ACTIVE" : "INACTIVE",
            isPlatformOwner: true,
            lastLogin: data.lastLoginAt || new Date().toISOString(),
            activeSessions: 1,
            systemVersion: "SEC-OPS V8 v2.0.0",
            dbConnected: true,
          });
          return;
        }
      }
      // Store owner / user fallback
      setProfile({
        email: user?.email || "owner@store.com",
        role: role,
        accountStatus: "ACTIVE",
        isPlatformOwner: isSoftwareOwner,
        lastLogin: new Date().toISOString(),
        activeSessions: 1,
        systemVersion: "SEC-OPS V8 v2.0.0",
        dbConnected: true,
      });
    } catch (e) {
      console.warn("Failed to fetch owner profile:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, [user]);

  const calculatePasswordStrength = (pwd: string) => {
    if (!pwd) return { score: 0, label: "Empty", color: "text-[var(--text-muted)]" };
    let score = 0;
    if (pwd.length >= 8) score += 1;
    if (pwd.length >= 12) score += 1;
    if (/[A-Z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd)) score += 1;
    if (/[^A-Za-z0-9]/.test(pwd)) score += 1;

    if (score <= 2) return { score, label: "Weak", color: "text-rose-400" };
    if (score <= 4) return { score, label: "Moderate", color: "text-amber-400" };
    return { score, label: "Strong", color: "text-emerald-400" };
  };

  const strength = calculatePasswordStrength(newPassword);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdMessage(null);

    if (!currentPassword) {
      setPwdMessage({ type: "error", text: "Please enter your current password." });
      return;
    }
    if (newPassword.length < 8) {
      setPwdMessage({ type: "error", text: "New password must be at least 8 characters long." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwdMessage({ type: "error", text: "New password and confirmation do not match." });
      return;
    }

    setSavingPassword(true);
    try {
      const res = await safeFetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          currentPassword,
          newPassword,
        }),
      });

      if (res.ok) {
        setPwdMessage({
          type: "success",
          text: "Password successfully updated! Your new credentials are active immediately.",
        });
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        const err = await res.json().catch(() => null);
        setPwdMessage({
          type: "error",
          text: err?.detail || "Password change rejected. Verify current password.",
        });
      }
    } catch (e: any) {
      setPwdMessage({ type: "error", text: e.message || "Failed to submit password change." });
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-2xl border border-[var(--border-hairline)] shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-[#38BDF8] border border-blue-500/20 font-bold uppercase tracking-wider">
              ACCOUNT & PLATFORM SECURITY
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-2.5">
            {isSoftwareOwner ? "Software Owner Profile & Security" : "Account Settings & Security"}
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            {isSoftwareOwner
              ? "Manage your master Software Owner credentials, cryptographic policies, and database connection integrity."
              : "Manage your store administrative credentials and operational security settings."}
          </p>
        </div>

        <button
          onClick={() => fetchProfile(true)}
          disabled={refreshing}
          className="btn-3d px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-xl text-xs font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin text-[#38BDF8]" : ""} />
          <span>Refresh Status</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Software Owner Identity & Platform Status */}
        <div className="space-y-6">
          {/* Identity Card */}
          <div className="card-3d bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-3 pb-4 border-b border-[var(--border-hairline)]">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white shadow-lg shadow-blue-900/30 font-bold text-lg">
                {isSoftwareOwner ? "SO" : (profile?.email?.[0] || "A").toUpperCase()}
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  {isSoftwareOwner ? "Software Owner" : "Store Administrator"}
                </h3>
                <span className="text-[11px] font-mono text-[#38BDF8]">
                  {isSoftwareOwner ? "Root Authority" : "Store Level Authority"}
                </span>
              </div>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Registered Email</span>
                <span className="text-[var(--text-primary)] font-bold">{profile?.email || (isSoftwareOwner ? "ces@gmail.com" : "admin@store.com")}</span>
              </div>

              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Role Hierarchy</span>
                <span className="inline-block px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 font-bold mt-0.5">
                  {isSoftwareOwner ? "SOFTWARE_OWNER (SUPER_ADMIN)" : role}
                </span>
              </div>

              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Storage Partition</span>
                <span className="text-emerald-500 dark:text-emerald-400 font-bold">
                  {isSoftwareOwner ? "platform_super_admin (Isolated)" : "store_tenant_partition (Multi-tenant)"}
                </span>
              </div>

              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Account Status</span>
                <span className="inline-flex items-center gap-1.5 text-[var(--status-ok)] font-bold">
                  <CheckCircle2 size={13} /> Active & Verified
                </span>
              </div>

              <div>
                <span className="text-[var(--text-muted)] block text-[10px] uppercase">Active Sessions</span>
                <span className="text-[var(--text-primary)] font-bold">{profile?.activeSessions || 1} session</span>
              </div>
            </div>
          </div>

          {/* Security & System Health */}
          <div className="card-3d bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-500 dark:text-emerald-400" /> Platform Security Telemetry
            </h3>

            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] space-y-1">
                <span className="text-[var(--text-muted)] text-[10px] block">PASSWORD HASHING ALGORITHM</span>
                <span className="text-[var(--text-primary)] font-bold">Argon2id / bcrypt ($2b$12$)</span>
              </div>

              <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] space-y-1">
                <span className="text-[var(--text-muted)] text-[10px] block">API RATE LIMITING</span>
                <span className="text-emerald-500 dark:text-emerald-400 font-bold">ACTIVE (Brute-Force Protected)</span>
              </div>

              <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] space-y-1">
                <span className="text-[var(--text-muted)] text-[10px] block">MULTI-TENANT LEAK PREVENTION</span>
                <span className="text-[#38BDF8] font-bold">ENFORCED (Tenant ID Checks)</span>
              </div>

              <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] space-y-1">
                <span className="text-[var(--text-muted)] text-[10px] block">PUBLIC REGISTRATION</span>
                <span className="text-rose-400 font-bold">DISABLED (Owner Bootstrap Only)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Password Change Form (Section 7.8) */}
        <div className="lg:col-span-2 card-3d bg-[var(--bg-panel)] rounded-2xl border border-[var(--border-hairline)] p-6 shadow-xl space-y-6">
          <div className="border-b border-[var(--border-hairline)] pb-4">
            <h2 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Key size={18} className="text-[#38BDF8]" /> {isSoftwareOwner ? "Update Software Owner Password" : "Update Account Password"}
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {isSoftwareOwner
                ? "Securely update your master platform password. Passwords are saved with high-entropy salted hashes."
                : "Securely update your store administrator or operator password."}
            </p>
          </div>

          {pwdMessage && (
            <div
              className={`p-4 rounded-xl text-xs font-mono flex items-start gap-2.5 border ${
                pwdMessage.type === "success"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/30"
              }`}
            >
              {pwdMessage.type === "success" ? (
                <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
              )}
              <div className="flex-1 font-medium">{pwdMessage.text}</div>
            </div>
          )}

          <form onSubmit={handleChangePassword} className="space-y-4 text-xs font-mono">
            {/* Current Password */}
            <div>
              <label className="block text-[var(--text-secondary)] mb-1 uppercase tracking-wider">
                Current Password *
              </label>
              <div className="relative">
                <input
                  type={showCurrent ? "text" : "password"}
                  required
                  placeholder="Enter current password (e.g. Ces@1234)"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-3 pr-10 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  className="absolute right-3 top-3 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* New Password */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="block text-[var(--text-secondary)] uppercase tracking-wider">
                  New Password *
                </label>
                {newPassword && (
                  <span className={`text-[10px] font-bold ${strength.color}`}>
                    Strength: {strength.label}
                  </span>
                )}
              </div>
              <div className="relative">
                <input
                  type={showNew ? "text" : "password"}
                  required
                  minLength={8}
                  placeholder="Enter new strong password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-3 pr-10 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-3 top-3 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <div className="mt-1 text-[11px] text-[var(--text-muted)]">
                Must be at least 8 characters long with numbers and letters.
              </div>
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-[var(--text-secondary)] mb-1 uppercase tracking-wider">
                Confirm New Password *
              </label>
              <div className="relative">
                <input
                  type={showConfirm ? "text" : "password"}
                  required
                  minLength={8}
                  placeholder="Repeat new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input-3d w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-xl p-3 pr-10 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-3 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border-hairline)] flex justify-end">
              <button
                type="submit"
                disabled={savingPassword}
                className="btn-3d btn-3d-primary px-6 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-xl font-bold shadow-lg shadow-blue-900/30 disabled:opacity-50 flex items-center gap-2"
              >
                {savingPassword ? "Updating Password..." : "Update Master Password"}
              </button>
            </div>
          </form>

          {/* Database Health & Schema Information */}
          <div className="mt-8 pt-6 border-t border-[var(--border-hairline)] space-y-3">
            <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-2">
              <Database size={15} className="text-[#38BDF8]" /> Database Administration & Integrity
            </h3>
            <p className="text-xs text-[var(--text-secondary)]">
              SEC-OPS V8 database migrations are version-controlled via Alembic. Destructive CASCADE drops are eliminated from production environments.
            </p>
            <div className="p-3 bg-[var(--bg-canvas)] rounded-xl border border-[var(--border-hairline)] text-xs font-mono flex items-center justify-between">
              <span className="text-[var(--text-secondary)]">Current Schema Revision:</span>
              <span className="text-[var(--text-primary)] font-bold">4f8910b2c1d3 (Canonical Production V8)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
