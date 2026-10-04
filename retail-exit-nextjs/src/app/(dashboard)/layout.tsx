"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
} from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [currentTime, setCurrentTime] = useState("");
  const [apiOnline, setApiOnline] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString());
    }, 1000);

    const checkApi = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/health");
        setApiOnline(res.ok);
      } catch {
        // backend might be starting
      }
    };
    checkApi();
    const apiInterval = setInterval(checkApi, 15000);

    return () => {
      clearInterval(timer);
      clearInterval(apiInterval);
    };
  }, []);

  const navItems = [
    { label: "Dashboard", href: "/", icon: Activity },
    { label: "Cameras & Fleet", href: "/settings/cameras", icon: Camera },
    { label: "Security Alerts", href: "/alerts", icon: AlertTriangle },
    { label: "Products & Pack Math", href: "/products", icon: Box },
    { label: "Employees & Face ID", href: "/employees", icon: Users },
    { label: "Invoices & OCR", href: "/invoices", icon: FileText },
    { label: "Exit Events", href: "/events", icon: Layers },
    { label: "Reports & PDF", href: "/reports", icon: FileSpreadsheet },
    { label: "Settings & Sensors", href: "/settings", icon: Settings },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-[#12151A] text-[#E7E9EC] select-none">
      {/* 1. Left Navigation Rail (Part A.1.4) */}
      <aside className="w-64 bg-[#1A1E26] border-r border-[#2C323D] flex flex-col z-20 shadow-2xl">
        {/* Brand / Logo */}
        <div className="p-5 border-b border-[#2C323D] flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-[#2563EB] text-white shadow-lg shadow-blue-900/40">
              <ShieldAlert size={20} />
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-[#E7E9EC] block leading-none">
                SEC-OPS <span className="text-[#38BDF8] text-xs">V8</span>
              </span>
              <span className="text-[10px] font-mono text-[#8B93A1] tracking-wider block mt-0.5">
                SURVEILLANCE AI
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
                    ? "bg-[#2563EB] text-white shadow-lg shadow-blue-900/30 font-bold border-l-2 border-[#38BDF8]"
                    : "text-[#8B93A1] hover:text-[#E7E9EC] hover:bg-[#20252F]"
                }`}
              >
                <item.icon size={16} className={isActive ? "text-white" : "text-[#8B93A1]"} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User / Station Footer */}
        <div className="p-4 border-t border-[#2C323D] bg-[#12151A]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#20252F] border border-[#2C323D] flex items-center justify-center font-bold text-xs text-[#38BDF8]">
              CSO
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-[#E7E9EC] truncate">Security Supervisor</div>
              <div className="text-[10px] font-mono text-[#8B93A1] truncate">Station #01 (Main Exit)</div>
            </div>
          </div>
        </div>
      </aside>

      {/* 2. Main Content View Area */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Top Control Room Header */}
        <header className="px-6 py-3.5 border-b border-[#2C323D] flex justify-between items-center bg-[#1A1E26] z-10 sticky top-0 shadow-md">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-[#8B93A1]">CONTROL CONSOLE //</span>
            <span className="text-sm font-bold tracking-tight text-[#E7E9EC]">
              {navItems.find((n) => (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href)))?.label ||
                "Console"}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-xs font-mono text-[#B8E3D6] bg-[#12151A] px-3 py-1 rounded-md border border-[#2C323D] flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#4FD1B3] animate-pulse"></span>
              <span>{currentTime || "12:00:00"}</span>
            </div>

            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border font-medium ${
                apiOnline
                  ? "bg-[#4FD1B3]/10 text-[#4FD1B3] border-[#4FD1B3]/30"
                  : "bg-[#E5484D]/10 text-[#E5484D] border-[#E5484D]/30"
              }`}
            >
              <CheckCircle size={13} /> {apiOnline ? "API: 8000 ONLINE" : "API: CONNECTING"}
            </div>
          </div>
        </header>

        {/* Page Children Container */}
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
      </main>
    </div>
  );
}
