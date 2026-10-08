"use client";

import { safeFetch } from "@/lib/api-client";
import React, { useState, useEffect } from "react";
import {
  Users,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  Camera,
  ShieldCheck,
  AlertTriangle,
  UploadCloud,
  CheckCircle,
  Clock,
  Key,
} from "lucide-react";

interface EmployeeItem {
  employeeId: string;
  name: string;
  role: string;
  rfidBadgeId: string;
  activeFlag: boolean;
  mismatchCount30d: number;
  hasPhoto?: boolean;
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<EmployeeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [enrollEmployee, setEnrollEmployee] = useState<EmployeeItem | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    role: "STORE_ASSOCIATE",
    rfidBadgeId: "",
  });

  const fetchEmployees = async () => {
    try {
      setLoading(true);
      const url = search
        ? `/api/employees?query=${encodeURIComponent(search)}`
        : "/api/employees";
      const res = await safeFetch(url);
      if (res.ok) {
        const data = await res.json();
        setEmployees(data);
      }
    } catch (e) {
      console.warn("Fetch employees error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployees();
  }, [search]);

  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await safeFetch("/api/employees", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        setShowAddModal(false);
        setFormData({ name: "", role: "STORE_ASSOCIATE", rfidBadgeId: "" });
        fetchEmployees();
      } else {
        const err = await res.json();
        alert(err.detail || "Registration failed");
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    }
  };

  const handleUploadPhoto = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollEmployee || !selectedFile) return;
    setUploading(true);
    try {
      const data = new FormData();
      data.append("file", selectedFile);

      const res = await safeFetch(`/api/employees/${enrollEmployee.employeeId}/photo`, {
        method: "POST",
        body: data,
      });

      if (res.ok) {
        alert("ArcFace biometric 512-d embedding successfully calculated and saved to database!");
        setEnrollEmployee(null);
        setSelectedFile(null);
        fetchEmployees();
      } else {
        const err = await res.json();
        alert(err.detail || "Photo enrollment failed");
      }
    } catch (err: any) {
      alert(err.message || "Upload error");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <Users className="text-[#4FD1B3]" /> Personnel & Biometric Face Rostering
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Enrolled employee biometric profiles (InsightFace/ArcFace 512-d embeddings), RFID badges, and 30-day
            compliance audit records.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchEmployees}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
          >
            <Plus size={16} /> Add Employee
          </button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)] flex justify-between items-center">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by employee name or RFID badge ID..."
            className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
          />
        </div>
        <div className="text-xs font-mono text-[var(--text-secondary)]">
          Total Enrolled: <b className="text-[#4FD1B3]">{employees.length}</b>
        </div>
      </div>

      {/* Employees Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        {employees.length === 0 && !loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <ShieldCheck size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">No employees registered</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Add warehouse associates and upload their portrait photo to enable automated identity verification at exit
              gates.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs font-mono border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-4">STATUS</th>
                  <th className="p-4">NAME</th>
                  <th className="p-4">ROLE</th>
                  <th className="p-4">RFID BADGE ID</th>
                  <th className="p-4">BIOMETRICS</th>
                  <th className="p-4">30-DAY MISMATCHES</th>
                  <th className="p-4 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {employees.map((emp) => (
                  <tr key={emp.employeeId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono ${
                          emp.activeFlag
                            ? "bg-[#4FD1B3]/10 text-[#4FD1B3] border border-[#4FD1B3]/30"
                            : "bg-[#8B93A1]/10 text-[var(--text-secondary)]"
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                        {emp.activeFlag ? "ACTIVE" : "INACTIVE"}
                      </span>
                    </td>
                    <td className="p-4 font-bold text-[var(--text-primary)]">{emp.name}</td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[var(--bg-canvas)] text-[#38BDF8] border border-[var(--border-hairline)]">
                        {emp.role}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-xs text-[#E8A33D]">{emp.rfidBadgeId}</td>
                    <td className="p-4">
                      <button
                        onClick={() => setEnrollEmployee(emp)}
                        className="px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--bg-panel-raised)] text-[#4FD1B3] border border-[var(--border-hairline)] hover:border-[#4FD1B3] rounded text-xs font-mono flex items-center gap-1.5 transition-colors"
                      >
                        <Camera size={13} /> {emp.hasPhoto ? "Re-Enroll Face" : "Enroll Face"}
                      </button>
                    </td>
                    <td className="p-4 font-mono text-xs">
                      {emp.mismatchCount30d > 0 ? (
                        <span className="text-[#E5484D] font-bold flex items-center gap-1">
                          <AlertTriangle size={13} /> {emp.mismatchCount30d} incidents
                        </span>
                      ) : (
                        <span className="text-[#4FD1B3]">0 clean</span>
                      )}
                    </td>
                    <td className="p-4 text-right">
                      <a
                        href={`/employees/${emp.employeeId}`}
                        className="text-xs font-mono text-[#38BDF8] hover:underline"
                      >
                        View Dossier →
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Employee Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Users size={18} className="text-[#4FD1B3]" /> Register New Employee
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateEmployee} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">FULL NAME *</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Alice Chen"
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">AUTHORIZATION ROLE</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                >
                  <option value="STORE_ASSOCIATE">Store Associate</option>
                  <option value="OPERATOR">Loading Dock Operator</option>
                  <option value="SUPERVISOR">Security Supervisor</option>
                  <option value="ADMIN">Facility Administrator</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">RFID BADGE ID *</label>
                <input
                  type="text"
                  required
                  value={formData.rfidBadgeId}
                  onChange={(e) => setFormData({ ...formData, rfidBadgeId: e.target.value })}
                  placeholder="e.g. BADGE-0091"
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[#E8A33D] font-mono outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold shadow-lg shadow-blue-900/30"
                >
                  Register Employee
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Face Biometric Photo Enrollment Modal */}
      {enrollEmployee && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Camera size={18} className="text-[#38BDF8]" /> Biometric Enrollment: {enrollEmployee.name}
              </h3>
              <button onClick={() => setEnrollEmployee(null)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadPhoto} className="space-y-4 text-sm">
              <p className="text-xs text-[var(--text-secondary)]">
                Upload an official front-facing portrait to compute ArcFace 512-dimensional facial embedding vectors.
              </p>

              <div className="border-2 border-dashed border-[var(--border-hairline)] hover:border-[#38BDF8] rounded-xl p-6 text-center cursor-pointer transition-colors bg-[var(--bg-canvas)]">
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  required
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="face-upload"
                />
                <label htmlFor="face-upload" className="cursor-pointer">
                  <UploadCloud size={32} className="mx-auto text-[#38BDF8] mb-2" />
                  {selectedFile ? (
                    <span className="font-mono text-xs text-[#4FD1B3] font-bold">{selectedFile.name}</span>
                  ) : (
                    <>
                      <span className="text-xs font-semibold text-[var(--text-primary)] block">Click to select photo</span>
                      <span className="text-[11px] text-[var(--text-secondary)] block mt-0.5">JPEG or PNG under 5MB</span>
                    </>
                  )}
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEnrollEmployee(null)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !selectedFile}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold shadow-lg shadow-blue-900/30 disabled:opacity-50"
                >
                  {uploading ? "Extracting Embeddings..." : "Save Biometric Face"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
