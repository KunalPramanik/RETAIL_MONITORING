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
  RotateCw,
} from "lucide-react";

interface EmployeeItem {
  employeeId: string;
  employeeCode?: string;
  name: string;
  role: string;
  rfidBadgeId: string;
  activeFlag: boolean;
  mismatchCount30d: number;
  hasPhoto?: boolean;
  hasFaceEnrolled?: boolean;
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<EmployeeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [enrollEmployee, setEnrollEmployee] = useState<EmployeeItem | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // 360 Multi-Angle Face Enrollment State (Modal)
  const [enroll360Employee, setEnroll360Employee] = useState<EmployeeItem | null>(null);
  const [files360, setFiles360] = useState<{ [angle: string]: File | null }>({
    front: null,
    left: null,
    right: null,
    up: null,
    down: null,
  });
  const [uploading360, setUploading360] = useState(false);

  // Add Employee Form State
  const [formData, setFormData] = useState({
    name: "",
    role: "STORE_ASSOCIATE",
    rfidBadgeId: "",
  });

  // Biometric Photo Enrollment within "Register New Employee" modal
  const [addEnrollMode, setAddEnrollMode] = useState<"360" | "single" | "none">("360");
  const [addSingleFile, setAddSingleFile] = useState<File | null>(null);
  const [addFiles360, setAddFiles360] = useState<{ [angle: string]: File | null }>({
    front: null,
    left: null,
    right: null,
    up: null,
    down: null,
  });
  const [isSubmittingAdd, setIsSubmittingAdd] = useState(false);

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
    if (!formData.name.trim()) {
      alert("Please enter employee full name.");
      return;
    }

    setIsSubmittingAdd(true);
    try {
      // Step 1: Create employee record
      const payload: any = {
        name: formData.name.trim(),
        role: formData.role,
      };
      if (formData.rfidBadgeId.trim()) {
        payload.rfidBadgeId = formData.rfidBadgeId.trim();
      }

      const res = await safeFetch("/api/employees", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Registration failed");
        setIsSubmittingAdd(false);
        return;
      }

      const createdEmp = await res.json();
      const empId = createdEmp.employeeId;
      const empCode = createdEmp.employeeCode || createdEmp.employee_code || "EMP-ASSIGNED";

      let photoEnrolled = false;
      let photoMsg = "";

      // Step 2: Upload Biometric Face Photos based on chosen mode
      if (addEnrollMode === "single" && addSingleFile) {
        try {
          const photoData = new FormData();
          photoData.append("file", addSingleFile);
          const pRes = await safeFetch(`/api/employees/${empId}/photo`, {
            method: "POST",
            body: photoData,
          });
          if (pRes.ok) {
            photoEnrolled = true;
            photoMsg = "Single portrait face enrolled. Live store cameras will authenticate as KNOWN STAFF.";
          } else {
            const pErr = await pRes.json();
            photoMsg = `Warning: ${pErr.detail || "Face not detected in photo"}. Employee marked UNKNOWN until verified photo is added.`;
          }
        } catch (pe: any) {
          photoMsg = `Photo upload error: ${pe.message}`;
        }
      } else if (addEnrollMode === "360") {
        const active360 = Object.values(addFiles360).filter((f): f is File => f !== null);
        if (active360.length > 0) {
          try {
            const data360 = new FormData();
            active360.forEach((f) => data360.append("files", f));
            const pRes = await safeFetch(`/api/employees/${empId}/face-360`, {
              method: "POST",
              body: data360,
            });
            if (pRes.ok) {
              photoEnrolled = true;
              photoMsg = `360° Multi-Angle Biometric Profile enrolled (${active360.length} angles). Live store cameras will authenticate as KNOWN STAFF from any angle.`;
            } else {
              const pErr = await pRes.json();
              photoMsg = `Warning: ${pErr.detail || "Face detection failed"}. Employee marked UNKNOWN until photos are added.`;
            }
          } catch (pe: any) {
            photoMsg = `360 upload error: ${pe.message}`;
          }
        }
      }

      // Close modal and reset form
      setShowAddModal(false);
      setFormData({ name: "", role: "STORE_ASSOCIATE", rfidBadgeId: "" });
      setAddSingleFile(null);
      setAddFiles360({ front: null, left: null, right: null, up: null, down: null });
      fetchEmployees();

      if (photoEnrolled) {
        alert(`Success! Employee registered with Code: ${empCode}.\n\n${photoMsg}`);
      } else if (photoMsg) {
        alert(`Employee registered (${empCode}).\n${photoMsg}`);
      } else {
        alert(`Employee registered successfully! Assigned Code: ${empCode}.\nNote: No face enrolled yet (store cameras will recognize as Unknown until photo is uploaded).`);
      }
    } catch (e: any) {
      alert(e.message || "Request failed");
    } finally {
      setIsSubmittingAdd(false);
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

  const handleUpload360 = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enroll360Employee) return;
    const activeFiles = Object.values(files360).filter((f): f is File => f !== null);
    if (activeFiles.length === 0) {
      alert("Please select at least 1 face angle image for 360 enrollment.");
      return;
    }
    setUploading360(true);
    try {
      const data = new FormData();
      activeFiles.forEach((file) => {
        data.append("files", file);
      });

      const res = await safeFetch(`/api/employees/${enroll360Employee.employeeId}/face-360`, {
        method: "POST",
        body: data,
      });

      if (res.ok) {
        const respData = await res.json();
        alert(respData.message || "360° Multi-Angle Biometric Profile successfully saved!");
        setEnroll360Employee(null);
        setFiles360({ front: null, left: null, right: null, up: null, down: null });
        fetchEmployees();
      } else {
        const err = await res.json();
        alert(err.detail || "360° Face enrollment failed");
      }
    } catch (err: any) {
      alert(err.message || "Upload error");
    } finally {
      setUploading360(false);
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
        {loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <RefreshCw size={28} className="mx-auto mb-3 text-[#38BDF8] animate-spin" />
            <h4 className="text-sm font-bold text-[var(--text-primary)]">Loading Warehouse Personnel...</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1">Retrieving employee roster and RFID credentials from store database.</p>
          </div>
        ) : employees.length === 0 ? (
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
                  <th className="p-4">EMP CODE</th>
                  <th className="p-4">NAME</th>
                  <th className="p-4">ROLE</th>
                  <th className="p-4">RFID BADGE ID</th>
                  <th className="p-4">CAMERA STATUS</th>
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
                    <td className="p-4 font-mono text-xs font-bold text-[#38BDF8]">
                      {emp.employeeCode || `EMP-${emp.employeeId.slice(0, 6).toUpperCase()}`}
                    </td>
                    <td className="p-4 font-bold text-[var(--text-primary)]">{emp.name}</td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[var(--bg-canvas)] text-[#38BDF8] border border-[var(--border-hairline)]">
                        {emp.role}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-xs text-[#E8A33D]">{emp.rfidBadgeId}</td>
                    <td className="p-4">
                      {emp.hasFaceEnrolled || emp.hasPhoto ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold bg-[#4FD1B3]/10 text-[#4FD1B3] border border-[#4FD1B3]/30">
                          <ShieldCheck size={13} /> KNOWN STAFF
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold bg-[#E5484D]/10 text-[#E5484D] border border-[#E5484D]/30">
                          <AlertTriangle size={13} /> UNKNOWN (NO FACE)
                        </span>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => {
                            setEnroll360Employee(emp);
                            setFiles360({ front: null, left: null, right: null, up: null, down: null });
                          }}
                          className="px-2.5 py-1 bg-gradient-to-r from-blue-600/20 to-teal-600/20 hover:from-blue-600/30 hover:to-teal-600/30 text-[#38BDF8] border border-[#38BDF8]/40 hover:border-[#38BDF8] rounded text-xs font-mono font-bold flex items-center gap-1.5 transition-all shadow-sm"
                          title="Multi-Angle 360 Biometric Enrollment"
                        >
                          <RotateCw size={13} className="text-[#38BDF8]" /> 360° Face Add
                        </button>
                        <button
                          onClick={() => setEnrollEmployee(emp)}
                          className="px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--bg-panel-raised)] text-[#4FD1B3] border border-[var(--border-hairline)] hover:border-[#4FD1B3] rounded text-xs font-mono flex items-center gap-1.5 transition-colors"
                          title="Single Portrait Photo Enrollment"
                        >
                          <Camera size={13} /> {emp.hasFaceEnrolled || emp.hasPhoto ? "Photo Update" : "Add Photo"}
                        </button>
                      </div>
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

      {/* Add Employee Modal with Integrated Photo & 360 Face Enrollment */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Users size={18} className="text-[#4FD1B3]" /> Register New Employee & Face Biometrics
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateEmployee} className="space-y-4 text-sm">
              <div className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-3 text-xs font-mono space-y-1">
                <div className="text-[var(--text-secondary)] flex justify-between items-center">
                  <span>EMPLOYEE CODE (SYSTEM SEQUENCED):</span>
                  <span className="text-[#38BDF8] font-bold px-2 py-0.5 bg-[#38BDF8]/10 rounded border border-[#38BDF8]/30">EMP-AUTO</span>
                </div>
                <p className="text-[11px] text-[var(--text-muted)]">
                  Collision-safe sequence (e.g. EMP-000001) will be atomically assigned by the server.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                    <option value="SECURITY">Store Security Guard</option>
                    <option value="SUPERVISOR">Security Supervisor</option>
                    <option value="ADMIN">Store Administrator</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                  RFID BADGE ID <span className="text-[var(--text-muted)]">(OPTIONAL - Auto-generated if blank)</span>
                </label>
                <input
                  type="text"
                  value={formData.rfidBadgeId}
                  onChange={(e) => setFormData({ ...formData, rfidBadgeId: e.target.value })}
                  placeholder="Auto-generated if empty (e.g. RFID-8A3F)"
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[#E8A33D] font-mono outline-none focus:border-[#38BDF8]"
                />
              </div>

              {/* Integrated Biometric Face Enrollment Section */}
              <div className="border border-[var(--border-hairline)] rounded-xl p-4 bg-[var(--bg-canvas)] space-y-3">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                  <div>
                    <h4 className="text-xs font-bold font-mono text-[#38BDF8] flex items-center gap-1.5">
                      <Camera size={14} /> BIOMETRIC FACE ENROLLMENT (STORE & EXIT CAMERAS)
                    </h4>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                      Enrolling photos allows AI surveillance cameras to authenticate this staff member as <b>Known Staff</b>. Un-enrolled staff are flagged as <b>Unknown Person</b>.
                    </p>
                  </div>
                </div>

                {/* Mode Selector */}
                <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                  <button
                    type="button"
                    onClick={() => setAddEnrollMode("360")}
                    className={`py-2 px-3 rounded-lg border flex items-center justify-center gap-1.5 transition-all text-center ${
                      addEnrollMode === "360"
                        ? "bg-gradient-to-r from-blue-600/30 to-teal-600/30 border-[#38BDF8] text-[#38BDF8] font-bold"
                        : "bg-[var(--bg-panel)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <RotateCw size={13} /> 360° Multi-Angle
                  </button>
                  <button
                    type="button"
                    onClick={() => setAddEnrollMode("single")}
                    className={`py-2 px-3 rounded-lg border flex items-center justify-center gap-1.5 transition-all text-center ${
                      addEnrollMode === "single"
                        ? "bg-[#2563EB]/20 border-[#2563EB] text-[#38BDF8] font-bold"
                        : "bg-[var(--bg-panel)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <Camera size={13} /> Single Portrait
                  </button>
                  <button
                    type="button"
                    onClick={() => setAddEnrollMode("none")}
                    className={`py-2 px-3 rounded-lg border flex items-center justify-center gap-1.5 transition-all text-center ${
                      addEnrollMode === "none"
                        ? "bg-[var(--bg-panel-hover)] border-[var(--text-secondary)] text-[var(--text-primary)] font-bold"
                        : "bg-[var(--bg-panel)] border-[var(--border-hairline)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    Skip Photo
                  </button>
                </div>

                {/* 360 Mode Slots */}
                {addEnrollMode === "360" && (
                  <div className="space-y-2 pt-2">
                    <p className="text-[11px] text-[var(--text-muted)] font-mono">
                      Select 1 to 5 face angle photos to compute ArcFace 360° omni-directional centroid:
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                      {[
                        { key: "front", label: "0° Front (Main)" },
                        { key: "left", label: "45° Left Profile" },
                        { key: "right", label: "45° Right Profile" },
                        { key: "up", label: "15° Tilted Up" },
                        { key: "down", label: "15° Tilted Down" },
                      ].map((slot) => (
                        <div
                          key={slot.key}
                          className="border border-[var(--border-hairline)] hover:border-[#38BDF8] rounded-lg p-2.5 text-center bg-[var(--bg-panel)] transition-all flex flex-col justify-between"
                        >
                          <span className="text-[10px] font-mono text-[var(--text-secondary)] font-bold block mb-1.5">
                            {slot.label}
                          </span>
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            id={`add-slot-${slot.key}`}
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0] || null;
                              setAddFiles360((prev) => ({ ...prev, [slot.key]: f }));
                            }}
                          />
                          <label
                            htmlFor={`add-slot-${slot.key}`}
                            className="cursor-pointer block py-2 border border-dashed border-[var(--border-hairline)] hover:border-[#38BDF8] rounded bg-[var(--bg-canvas)]"
                          >
                            <Camera size={16} className="mx-auto text-[#38BDF8] mb-1" />
                            <span className="text-[10px] text-[var(--text-muted)] block truncate px-1">
                              {addFiles360[slot.key]?.name || "Select"}
                            </span>
                          </label>
                          {addFiles360[slot.key] && (
                            <span className="text-[10px] text-[#4FD1B3] font-mono font-bold mt-1 flex items-center justify-center gap-0.5">
                              <CheckCircle size={10} /> Ready
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Single Portrait Mode */}
                {addEnrollMode === "single" && (
                  <div className="pt-2">
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      id="add-single-photo"
                      className="hidden"
                      onChange={(e) => setAddSingleFile(e.target.files?.[0] || null)}
                    />
                    <label
                      htmlFor="add-single-photo"
                      className="border-2 border-dashed border-[var(--border-hairline)] hover:border-[#38BDF8] rounded-xl p-4 text-center cursor-pointer transition-colors bg-[var(--bg-panel)] block"
                    >
                      <UploadCloud size={24} className="mx-auto text-[#38BDF8] mb-1" />
                      {addSingleFile ? (
                        <span className="font-mono text-xs text-[#4FD1B3] font-bold block">{addSingleFile.name}</span>
                      ) : (
                        <>
                          <span className="text-xs font-semibold text-[var(--text-primary)] block">Click to select portrait image</span>
                          <span className="text-[11px] text-[var(--text-secondary)] block mt-0.5">JPEG, PNG or WebP</span>
                        </>
                      )}
                    </label>
                  </div>
                )}

                {/* Skip Mode Notice */}
                {addEnrollMode === "none" && (
                  <p className="text-xs text-[#E8A33D] font-mono bg-[#E8A33D]/10 border border-[#E8A33D]/20 p-2.5 rounded-lg">
                    Notice: This employee will be created without face biometrics. Live cameras will identify them as "Unknown Person" until a face photo is enrolled later.
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  disabled={isSubmittingAdd}
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingAdd}
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold shadow-lg shadow-blue-900/30 flex items-center gap-2 disabled:opacity-50"
                >
                  {isSubmittingAdd ? (
                    <>
                      <RefreshCw size={15} className="animate-spin" /> Processing Biometrics...
                    </>
                  ) : (
                    "Register & Enroll Staff"
                  )}
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
              <button onClick={() => setEnrollEmployee(null)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
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

      {/* 360 Multi-Angle Face Biometric Enrollment Modal */}
      {enroll360Employee && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <RotateCw size={18} className="text-[#38BDF8]" /> 360° Multi-Angle Face Enrollment: {enroll360Employee.name}
              </h3>
              <button
                onClick={() => setEnroll360Employee(null)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-[var(--text-secondary)]">
              Upload multi-angle portraits (Front, Left Profile, Right Profile, Up, Down) to construct a 360-degree
              512-d ArcFace centroid. This enables omni-directional recognition at retail exit gates under any camera angle.
            </p>

            <form onSubmit={handleUpload360} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { key: "front", label: "0° Frontal Face *" },
                  { key: "left", label: "45° Left Profile" },
                  { key: "right", label: "45° Right Profile" },
                  { key: "up", label: "15° Tilted Up" },
                  { key: "down", label: "15° Tilted Down" },
                ].map((slot) => (
                  <div
                    key={slot.key}
                    className="border border-[var(--border-hairline)] hover:border-[#38BDF8] rounded-lg p-3 text-center bg-[var(--bg-canvas)] transition-all flex flex-col justify-between"
                  >
                    <div>
                      <span className="text-[11px] font-mono text-[var(--text-secondary)] font-bold block mb-2">
                        {slot.label}
                      </span>
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        id={`slot-${slot.key}`}
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0] || null;
                          setFiles360((prev) => ({ ...prev, [slot.key]: f }));
                        }}
                      />
                      <label
                        htmlFor={`slot-${slot.key}`}
                        className="cursor-pointer block py-2 border border-dashed border-[var(--border-hairline)] hover:border-[#38BDF8] rounded bg-[var(--bg-panel-raised)]"
                      >
                        <Camera size={18} className="mx-auto text-[#38BDF8] mb-1" />
                        <span className="text-[10px] text-[var(--text-muted)] block truncate px-1">
                          {files360[slot.key]?.name || "Select Image"}
                        </span>
                      </label>
                    </div>
                    {files360[slot.key] && (
                      <span className="text-[10px] text-[#4FD1B3] font-mono font-bold mt-1.5 flex items-center justify-center gap-1">
                        <CheckCircle size={10} /> Loaded
                      </span>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex justify-between items-center text-xs font-mono text-[var(--text-secondary)] pt-2 border-t border-[var(--border-hairline)]">
                <span>
                  Angles Ready:{" "}
                  <b className="text-[#38BDF8]">
                    {Object.values(files360).filter((f) => f !== null).length} / 5
                  </b>
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setEnroll360Employee(null)}
                    className="px-3.5 py-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={uploading360 || Object.values(files360).filter((f) => f !== null).length === 0}
                    className="px-4 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-semibold shadow-lg shadow-blue-900/30 disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {uploading360 ? "Synthesizing 360 Embeddings..." : "Save 360° Profile"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
