"use client";

import React, { useState, useEffect } from "react";
import { safeFetch } from "@/lib/api-client";
import Link from "next/link";
import {
  Sparkles,
  Building,
  Camera,
  Layers,
  Box,
  Sliders,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  RefreshCw,
  Clock,
  ShieldCheck,
  Server,
} from "lucide-react";

interface OnboardingProgress {
  storeConfigured: boolean;
  camerasConfigured: number;
  productsConfigured: number;
  baselineVerified: boolean;
  thresholdsConfigured: boolean;
  isComplete: boolean;
}

interface StoreProfile {
  name: string;
  address: string;
  timezone: string;
  currency: string;
}

export default function OnboardingWizardPage() {
  const [progress, setProgress] = useState<OnboardingProgress>({
    storeConfigured: false,
    camerasConfigured: 0,
    productsConfigured: 0,
    baselineVerified: false,
    thresholdsConfigured: false,
    isComplete: false,
  });

  const [profile, setProfile] = useState<StoreProfile>({
    name: "",
    address: "",
    timezone: "Asia/Kolkata",
    currency: "INR",
  });

  const [savingProfile, setSavingProfile] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [resProgress, resProfile] = await Promise.all([
        safeFetch("/api/settings/onboarding"),
        safeFetch("/api/settings/store"),
      ]);

      if (resProgress.ok) {
        setProgress(await resProgress.json());
      }
      if (resProfile.ok) {
        const p = await resProfile.json();
        setProfile({
          name: p.name || "",
          address: p.address || "",
          timezone: p.timezone || "Asia/Kolkata",
          currency: p.currency || "INR",
        });
      }
    } catch (e) {
      console.warn("Failed to fetch onboarding data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile.name.trim()) {
      alert("Store name is required.");
      return;
    }
    setSavingProfile(true);
    try {
      const res = await safeFetch("/api/settings/store", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      if (res.ok) {
        alert("Store profile and timezone saved successfully!");
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to update profile");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    } finally {
      setSavingProfile(false);
    }
  };

  const steps = [
    {
      title: "1. Store Profile & Timezone",
      desc: "Configure facility name, location address, and canonical timezone for operational event timestamps.",
      status: profile.name.trim().length > 0 ? "CONFIGURED" : "PENDING",
      action: null,
    },
    {
      title: "2. Product Catalogue & Pack Math",
      desc: "Register commercial SKUs, case-to-unit pack multipliers, and ₹ INR retail unit pricing.",
      status: progress.productsConfigured > 0 ? `${progress.productsConfigured} SKUs REGISTERED` : "NOT CONFIGURED",
      action: { label: "Manage Products", href: "/products" },
    },
    {
      title: "3. Camera Fleet Onboarding",
      desc: "Connect on-premise RTSP video streams or USB capture feeds and calibrate ground tripwire gates.",
      status: progress.camerasConfigured > 0 ? `${progress.camerasConfigured} CAMERAS ONLINE` : "NOT CONFIGURED",
      action: { label: "Configure Cameras", href: "/settings/cameras" },
    },
    {
      title: "4. Initial Stock Census Verification",
      desc: "Perform AI warehouse shelf scan and execute human YES / NO baseline approval in the ledger.",
      status: progress.baselineVerified ? "BASELINE LOCKED" : "PENDING REVIEW",
      action: { label: "Review Baseline", href: "/inventory" },
    },
    {
      title: "5. Operational Security Thresholds",
      desc: "Set severity discrepancies, turnstile auto-lock rules, and repeat offender triggers.",
      status: progress.thresholdsConfigured ? "THRESHOLDS ACTIVE" : "DEFAULT APPLIED",
      action: { label: "Review Thresholds", href: "/settings" },
    },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#38BDF8]/10 text-[#38BDF8] text-xs font-mono font-bold mb-2 border border-[#38BDF8]/30">
            <Sparkles size={14} /> STORE ONBOARDING WIZARD
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            Store Owner First-Time Guided Setup
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Complete the 5 deployment milestones below to transition this retail facility into production monitoring.
          </p>
        </div>
        <button
          onClick={fetchData}
          className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-xs font-mono font-medium flex items-center gap-2 transition-colors"
        >
          <RefreshCw size={13} /> Refresh Status
        </button>
      </div>

      {/* Progress Bar */}
      <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)] space-y-2">
        <div className="flex justify-between text-xs font-mono">
          <span className="text-[var(--text-secondary)]">ONBOARDING READINESS</span>
          <span className="text-[#38BDF8] font-bold">
            {progress.isComplete ? "100% COMPLETE // PRODUCTION READY" : "SETUP IN PROGRESS"}
          </span>
        </div>
        <div className="w-full h-2 bg-[var(--bg-canvas)] rounded-full overflow-hidden border border-[var(--border-hairline)]">
          <div
            className="h-full bg-gradient-to-r from-blue-600 to-[#38BDF8] transition-all duration-500"
            style={{
              width: `${
                ((Number(profile.name.trim().length > 0) +
                  Number(progress.productsConfigured > 0) +
                  Number(progress.camerasConfigured > 0) +
                  Number(progress.baselineVerified) +
                  Number(progress.thresholdsConfigured)) /
                  5) *
                100
              }%`,
            }}
          />
        </div>
      </div>

      {/* Step 1: Store Profile Form */}
      <div className="bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] space-y-4">
        <h3 className="text-sm font-bold font-mono text-[var(--text-primary)] flex items-center gap-2 border-b border-[var(--border-hairline)] pb-3">
          <Building size={16} className="text-[#38BDF8]" /> FACILITY IDENTITY & TIMEZONE CALIBRATION
        </h3>
        <form onSubmit={handleSaveProfile} className="space-y-4 text-xs font-mono">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[var(--text-secondary)] mb-1">STORE / FACILITY NAME *</label>
              <input
                type="text"
                required
                value={profile.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                placeholder="e.g. SEC-OPS Flagship Store #104"
                className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
              />
            </div>
            <div>
              <label className="block text-[var(--text-secondary)] mb-1">OPERATIONAL TIMEZONE *</label>
              <select
                value={profile.timezone}
                onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
              >
                <option value="Asia/Kolkata">Asia/Kolkata (IST, UTC+05:30)</option>
                <option value="UTC">UTC (Coordinated Universal Time)</option>
                <option value="America/New_York">America/New_York (EST, UTC-05:00)</option>
                <option value="Europe/London">Europe/London (GMT, UTC+00:00)</option>
                <option value="Asia/Dubai">Asia/Dubai (GST, UTC+04:00)</option>
                <option value="Asia/Singapore">Asia/Singapore (SGT, UTC+08:00)</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[var(--text-secondary)] mb-1">FACILITY PHYSICAL ADDRESS</label>
            <input
              type="text"
              value={profile.address}
              onChange={(e) => setProfile({ ...profile, address: e.target.value })}
              placeholder="e.g. Exit Terminal 2, Logistics Boulevard, Sector 12"
              className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
            />
          </div>
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={savingProfile}
              className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-bold transition-all shadow-md shadow-blue-900/30 disabled:opacity-50"
            >
              {savingProfile ? "Saving Profile..." : "Save Store Profile"}
            </button>
          </div>
        </form>
      </div>

      {/* Step Milestones List */}
      <div className="space-y-3">
        {steps.map((st, idx) => (
          <div
            key={idx}
            className="bg-[var(--bg-panel)] p-5 rounded-xl border border-[var(--border-hairline)] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 transition-colors"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-[var(--text-primary)] font-mono">{st.title}</span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
                    st.status.includes("CONFIGURED") || st.status.includes("ONLINE") || st.status.includes("LOCKED") || st.status.includes("ACTIVE")
                      ? "bg-[#4FD1B3]/15 text-[#4FD1B3] border-[#4FD1B3]/30"
                      : "bg-[#E8A33D]/15 text-[#E8A33D] border-[#E8A33D]/30"
                  }`}
                >
                  {st.status}
                </span>
              </div>
              <p className="text-xs text-[var(--text-secondary)] max-w-xl">{st.desc}</p>
            </div>
            {st.action && (
              <Link
                href={st.action.href}
                className="px-3.5 py-2 bg-[var(--bg-canvas)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] border border-[var(--border-hairline)] rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition-colors shrink-0"
              >
                {st.action.label} <ArrowRight size={13} />
              </Link>
            )}
          </div>
        ))}
      </div>

      {/* Finish Action */}
      <div className="bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] flex flex-col sm:flex-row justify-between items-center gap-4">
        <div>
          <h4 className="text-sm font-bold text-[var(--text-primary)] font-mono">COMPLETE ONBOARDING & ENTER MONITORING</h4>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Proceed to the live surveillance console and real-time detection stream.
          </p>
        </div>
        <Link
          href="/"
          className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-[#38BDF8] hover:opacity-90 text-white rounded-lg text-xs font-bold font-mono flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
        >
          Open Live Console <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  );
}

