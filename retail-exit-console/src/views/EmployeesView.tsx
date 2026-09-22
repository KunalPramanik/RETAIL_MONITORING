import React, { useState } from 'react';
import { useAppData } from '../context/AppDataContext';
import type { Employee, ExitEvent } from '../types';
import { Modal } from '../components/common/Modal';
import { Users, UserPlus, AlertTriangle, ShieldCheck, History, Search, Camera, Upload, Trash2, CheckCircle2 } from 'lucide-react';

export const EmployeesView: React.FC = () => {
  const { employees, events, addEmployee, uploadEmployeePhoto, deleteEmployeePhoto } = useAppData();
  const [searchQuery, setSearchQuery] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [inspectingEmployee, setInspectingEmployee] = useState<Employee | null>(null);

  // Biometric Photo Enrollment Modal State
  const [photoModalEmployee, setPhotoModalEmployee] = useState<Employee | null>(null);
  const [selectedPhotoFile, setSelectedPhotoFile] = useState<File | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [photoSuccess, setPhotoSuccess] = useState<string | null>(null);

  // Form State for Add/Edit
  const [formData, setFormData] = useState<Omit<Employee, 'employeeId'>>({
    name: '',
    role: 'Logistics Porter',
    rfidBadgeId: 'RFID-BADGE-1000',
    shiftId: 'SHIFT-MORNING-A',
    activeFlag: true,
    mismatchCount30d: 0,
  });

  const handleOpenAdd = () => {
    setFormData({
      name: '',
      role: 'Logistics Porter',
      rfidBadgeId: `RFID-BADGE-${Math.floor(1000 + Math.random() * 9000)}`,
      shiftId: 'SHIFT-MORNING-A',
      activeFlag: true,
      mismatchCount30d: 0,
    });
    setIsAddModalOpen(true);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    addEmployee(formData);
    setIsAddModalOpen(false);
  };

  const filteredEmployees = employees.filter((emp: Employee) => {
    const q = searchQuery.toLowerCase();
    return (
      emp.name.toLowerCase().includes(q) ||
      emp.role.toLowerCase().includes(q) ||
      emp.rfidBadgeId.toLowerCase().includes(q) ||
      emp.shiftId.toLowerCase().includes(q)
    );
  });

  // Calculate employee events for inspector
  const employeeEvents = inspectingEmployee
    ? events.filter((e: ExitEvent) => e.employeeId === inspectingEmployee.employeeId)
    : [];

  return (
    <div className="p-4 space-y-4">
      {/* Header and Add Action */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
              <Users className="w-5 h-5 text-amber" />
              Employee Badge Registry & Carrier Trust Scoring
            </h1>
            <p className="text-xs-tech text-text-sec mt-0.5">
              Tracks warehouse personnel, exit portal traversals, and surfaces repeat mismatch patterns for loss prevention escalation.
            </p>
          </div>

          <button
            onClick={handleOpenAdd}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 transition-colors self-start sm:self-auto"
          >
            <UserPlus className="w-3.5 h-3.5" />
            Register Personnel
          </button>
        </div>

        {/* Search */}
        <div className="relative pt-2 border-t border-hairline max-w-md">
          <Search className="w-3.5 h-3.5 text-text-sec absolute left-3 top-4.5" />
          <input
            type="text"
            placeholder="Search employee name, badge ID, role, shift..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri placeholder:text-text-sec/60 focus-visible:outline-2 focus-visible:outline-amber"
          />
        </div>
      </div>

      {/* Roster Table */}
      <div className="bg-panel border border-hairline rounded-sm overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-hairline bg-panel-raised text-xs-tech">
          <span className="font-semibold text-text-pri">
            Active Roster ({filteredEmployees.length} personnel)
          </span>
          <span className="font-mono text-text-sec text-[11px]">
            Biometric & RFID Verified
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-hairline bg-canvas/60 text-xs-tech text-text-sec font-normal">
                <th className="py-2 px-3 font-normal">Employee Name</th>
                <th className="py-2 px-3 font-normal">Biometric Face Profile</th>
                <th className="py-2 px-3 font-normal">Assigned Role</th>
                <th className="py-2 px-3 font-normal">RFID Badge Key</th>
                <th className="py-2 px-3 font-normal">Shift Schedule</th>
                <th className="py-2 px-3 font-normal">Status</th>
                <th className="py-2 px-3 font-normal text-right">Risk Standing</th>
                <th className="py-2 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredEmployees.length > 0 ? (
                filteredEmployees.map((emp: Employee) => {
                  const isRepeatOffender = emp.mismatchCount30d >= 3;
                  return (
                    <tr
                      key={emp.employeeId}
                      className="border-b border-hairline/60 hover:bg-panel-raised/50 transition-colors text-xs-tech"
                    >
                      {/* Name */}
                      <td className="py-2.5 px-3 font-semibold text-text-pri whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-canvas border border-hairline flex items-center justify-center text-[11px] font-mono text-amber">
                            {emp.name.slice(0, 2).toUpperCase()}
                          </div>
                          <span>{emp.name}</span>
                        </div>
                      </td>

                      {/* Biometric Face Profile */}
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        {emp.hasFaceEnrolled ? (
                          <div className="flex items-center gap-1.5">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-teal-950/40 text-status-ok border border-status-ok/40 font-mono text-[11px] font-semibold">
                              <ShieldCheck className="w-3 h-3" />
                              FACE ENROLLED
                            </span>
                            <button
                              onClick={() => {
                                setPhotoModalEmployee(emp);
                                setSelectedPhotoFile(null);
                                setPhotoPreviewUrl(null);
                                setPhotoError(null);
                                setPhotoSuccess(null);
                              }}
                              className="p-1 hover:bg-panel-raised rounded text-text-sec hover:text-amber transition-colors"
                              title="Update Biometric Photo"
                            >
                              <Camera className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-amber-950/20 text-amber border border-amber/30 font-mono text-[10px]">
                              <AlertTriangle className="w-3 h-3" />
                              NO PHOTO
                            </span>
                            <button
                              onClick={() => {
                                setPhotoModalEmployee(emp);
                                setSelectedPhotoFile(null);
                                setPhotoPreviewUrl(null);
                                setPhotoError(null);
                                setPhotoSuccess(null);
                              }}
                              className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-semibold rounded-sm bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 transition-colors"
                            >
                              <Upload className="w-3 h-3" />
                              Enroll Photo
                            </button>
                          </div>
                        )}
                      </td>

                      {/* Role */}
                      <td className="py-2.5 px-3 text-text-pri whitespace-nowrap">
                        {emp.role}
                      </td>

                      {/* Badge ID */}
                      <td className="py-2.5 px-3 font-mono text-text-sec whitespace-nowrap">
                        {emp.rfidBadgeId}
                      </td>

                      {/* Shift */}
                      <td className="py-2.5 px-3 text-text-sec whitespace-nowrap">
                        <span className="font-mono text-[11px]">
                          {emp.shiftId}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm font-mono text-[11px] ${
                            emp.activeFlag
                              ? 'bg-status-ok/10 text-status-ok border border-status-ok/30'
                              : 'bg-canvas text-text-sec border border-hairline'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              emp.activeFlag ? 'bg-status-ok' : 'bg-text-sec'
                            }`}
                          />
                          {emp.activeFlag ? 'ACTIVE' : 'INACTIVE'}
                        </span>
                      </td>

                      {/* 30d Mismatch History / Risk Tier */}
                      <td className="py-2.5 px-3 whitespace-nowrap text-right">
                        {isRepeatOffender ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-red-950/30 text-status-high border border-status-high/40 font-mono text-[10px] font-bold">
                            <AlertTriangle className="w-3 h-3" />
                            REPEAT OFFENDER ({emp.mismatchCount30d})
                          </span>
                        ) : emp.mismatchCount30d > 0 ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-yellow-950/20 text-status-low border border-status-low/30 font-mono text-[10px]">
                            WATCHLIST ({emp.mismatchCount30d})
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-teal-950/20 text-status-ok border border-status-ok/30 font-mono text-[10px]">
                            <ShieldCheck className="w-3 h-3" />
                            TRUSTED
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-2.5 px-3 text-right whitespace-nowrap space-x-1">
                        <button
                          onClick={() => {
                            setPhotoModalEmployee(emp);
                            setSelectedPhotoFile(null);
                            setPhotoPreviewUrl(null);
                            setPhotoError(null);
                            setPhotoSuccess(null);
                          }}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs-tech font-semibold rounded-sm bg-panel-raised hover:bg-hairline/40 text-amber border border-amber/30 transition-colors"
                          title="Enroll or Update Biometric Photo"
                        >
                          <Camera className="w-3 h-3" />
                          Photo
                        </button>
                        <button
                          onClick={() => setInspectingEmployee(emp)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs-tech font-semibold rounded-sm bg-panel-raised hover:bg-hairline/40 text-text-pri border border-hairline transition-colors"
                        >
                          <History className="w-3.5 h-3.5 text-amber" />
                          Audit
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : employees.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-xs-tech text-text-sec">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Users className="w-7 h-7 text-hairline" />
                      <span className="text-text-pri font-medium">No personnel enrolled in badge registry</span>
                      <span className="text-[11px] max-w-sm">
                        Enroll employees and exit gate operators to authenticate personnel during goods dispatch.
                      </span>
                      <button
                        onClick={handleOpenAdd}
                        className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 rounded-sm font-semibold transition-colors"
                      >
                        <UserPlus className="w-3.5 h-3.5" />
                        Enroll First Employee
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-xs-tech text-text-sec">
                    No personnel matched search query "{searchQuery}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Employee Event History Modal */}
      {inspectingEmployee && (
        <Modal
          isOpen={!!inspectingEmployee}
          onClose={() => setInspectingEmployee(null)}
          title={`Exit History: ${inspectingEmployee.name}`}
          subtitle={`Role: ${inspectingEmployee.role} · Badge: ${inspectingEmployee.rfidBadgeId} · 30d Mismatches: ${inspectingEmployee.mismatchCount30d}`}
          maxWidth="xl"
        >
          <div className="space-y-4">
            {inspectingEmployee.mismatchCount30d >= 3 && (
              <div className="p-3 bg-red-950/20 border border-status-high/40 rounded-sm flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-status-high flex-shrink-0 mt-0.5" />
                <div className="text-xs-tech">
                  <div className="font-bold text-status-high">
                    Escalation Notice: Carrier exceeds 30-day threshold (≥3 mismatches).
                  </div>
                  <div className="text-text-sec mt-0.5">
                    Any subsequent anomaly will immediately trigger an audible siren alarm and recommend locking the exit portal.
                  </div>
                </div>
              </div>
            )}

            <div className="border border-hairline rounded-sm overflow-hidden">
              <div className="px-3 py-2 bg-panel font-semibold text-xs-tech text-text-pri border-b border-hairline">
                Recent Outflow Traversals ({employeeEvents.length} records in active log)
              </div>
              <div className="divide-y divide-hairline/50 max-h-64 overflow-y-auto font-mono text-xs-tech">
                {employeeEvents.length > 0 ? (
                  employeeEvents.map((ev: ExitEvent) => (
                    <div
                      key={ev.eventId}
                      className="p-2.5 flex items-center justify-between hover:bg-panel-raised transition-colors"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-text-pri">{ev.eventId}</span>
                          <span className="text-text-sec">({ev.laneId})</span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] ${
                              ev.verdict === 'PASS'
                                ? 'bg-status-ok/20 text-status-ok'
                                : 'bg-status-high/20 text-status-high font-bold'
                            }`}
                          >
                            {ev.verdict}
                          </span>
                        </div>
                        <div className="text-text-sec text-[11px] font-sans">
                          {new Date(ev.timestamp).toLocaleString()} · {ev.casesDetected} cases ({ev.consensusUnits} units)
                        </div>
                      </div>

                      <div className="text-right">
                        {ev.deltaUnits !== undefined && ev.deltaUnits !== 0 ? (
                          <span className="text-status-high font-bold">Δ +{ev.deltaUnits} EA</span>
                        ) : (
                          <span className="text-status-ok">Δ 0 EA</span>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-6 text-center text-text-sec font-sans">
                    No individual traversals recorded for this employee in the current live buffer.
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setInspectingEmployee(null)}
                className="px-4 py-1.5 text-xs-tech rounded-sm bg-panel border border-hairline text-text-pri hover:bg-hairline/30"
              >
                Close Audit Trail
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Add Employee Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Register Warehouse Personnel"
        subtitle="Enables biometric and RFID authentication at turnstile lanes."
        maxWidth="md"
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs-tech font-medium text-text-sec mb-1">
              Full Employee Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Rachel Adams"
              className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs-tech font-medium text-text-sec mb-1">
                Warehouse Role
              </label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              >
                <option value="Logistics Supervisor">Logistics Supervisor</option>
                <option value="Forklift Operator">Forklift Operator</option>
                <option value="Receiving Porter">Receiving Porter</option>
                <option value="Night Fulfillment Lead">Night Fulfillment Lead</option>
                <option value="Exit Gate Attendant">Exit Gate Attendant</option>
                <option value="General Stock Clerk">General Stock Clerk</option>
              </select>
            </div>

            <div>
              <label className="block text-xs-tech font-medium text-text-sec mb-1">
                Shift Schedule
              </label>
              <select
                value={formData.shiftId}
                onChange={(e) => setFormData({ ...formData, shiftId: e.target.value })}
                className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              >
                <option value="SHIFT-MORNING-A">Morning Shift (06:00 - 14:30)</option>
                <option value="SHIFT-AFTERNOON-B">Afternoon Shift (14:00 - 22:30)</option>
                <option value="SHIFT-NIGHT-C">Night Fulfillment (22:00 - 06:30)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs-tech font-medium text-text-sec mb-1">
              Assigned RFID Badge ID Key
            </label>
            <input
              type="text"
              value={formData.rfidBadgeId}
              onChange={(e) => setFormData({ ...formData, rfidBadgeId: e.target.value })}
              className="w-full px-3 py-2 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-mono-val focus-visible:outline-2 focus-visible:outline-amber"
              required
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-hairline">
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              className="px-3 py-1.5 text-xs-tech rounded-sm border border-hairline hover:bg-hairline/30 text-text-sec transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors"
            >
              Save Personnel Record
            </button>
          </div>
        </form>
      </Modal>

      {/* Biometric Face Photo Enrollment Modal */}
      {photoModalEmployee && (
        <Modal
          isOpen={!!photoModalEmployee}
          onClose={() => {
            setPhotoModalEmployee(null);
            setSelectedPhotoFile(null);
            setPhotoPreviewUrl(null);
            setPhotoError(null);
            setPhotoSuccess(null);
          }}
          title={`Biometric Face Enrollment — ${photoModalEmployee.name}`}
          subtitle="Enrolls high-accuracy 512-d ArcFace facial embeddings for Known Person surveillance classification."
          maxWidth="md"
        >
          <div className="space-y-4">
            {/* Status overview */}
            <div className="p-3 bg-panel-raised border border-hairline rounded-sm flex items-center justify-between text-xs-tech">
              <div>
                <span className="text-text-sec block text-[11px]">PERSONNEL ID</span>
                <span className="font-mono text-mono-val">{photoModalEmployee.employeeId}</span>
              </div>
              <div className="text-right">
                <span className="text-text-sec block text-[11px]">BIOMETRIC STATUS</span>
                <span className={photoModalEmployee.hasFaceEnrolled ? 'text-status-ok font-semibold' : 'text-amber font-semibold'}>
                  {photoModalEmployee.hasFaceEnrolled ? '✓ Face Vector Active (512-d)' : '⚠ Unregistered (Treated as Unknown Person)'}
                </span>
              </div>
            </div>

            {/* Error or Success feedback banners */}
            {photoError && (
              <div className="p-3 rounded-sm bg-red-950/40 border border-status-high/50 text-status-high text-xs-tech flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{photoError}</span>
              </div>
            )}
            {photoSuccess && (
              <div className="p-3 rounded-sm bg-teal-950/40 border border-status-ok/50 text-status-ok text-xs-tech flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{photoSuccess}</span>
              </div>
            )}

            {/* Photo Selection / Dropzone */}
            <div className="border-2 border-dashed border-hairline hover:border-amber/60 rounded-sm p-4 text-center transition-colors bg-canvas/60">
              {photoPreviewUrl ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-36 h-36 rounded-sm overflow-hidden border-2 border-amber/60 relative group shadow-md bg-black mx-auto">
                    <img
                      src={photoPreviewUrl}
                      alt="Face Preview"
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <span className="text-xs-tech text-text-sec font-mono">
                    {selectedPhotoFile?.name} ({(selectedPhotoFile ? selectedPhotoFile.size / 1024 : 0).toFixed(1)} KB)
                  </span>
                  <label className="cursor-pointer px-2.5 py-1 text-xs-tech rounded-sm bg-panel border border-hairline hover:bg-hairline/30 text-text-pri inline-flex items-center gap-1.5 transition-colors mx-auto">
                    <Camera className="w-3.5 h-3.5 text-amber" />
                    Select Different Photo
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) {
                          setSelectedPhotoFile(f);
                          setPhotoPreviewUrl(URL.createObjectURL(f));
                          setPhotoError(null);
                          setPhotoSuccess(null);
                        }
                      }}
                    />
                  </label>
                </div>
              ) : (
                <label className="cursor-pointer flex flex-col items-center gap-2 py-4">
                  <Camera className="w-8 h-8 text-text-sec/80 group-hover:text-amber transition-colors" />
                  <span className="text-xs-tech text-text-pri font-semibold">
                    Click to select employee portrait photo
                  </span>
                  <span className="text-[11px] text-text-sec">
                    Supported: JPG, PNG, WebP. Ensure subject is directly facing camera.
                  </span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) {
                        setSelectedPhotoFile(f);
                        setPhotoPreviewUrl(URL.createObjectURL(f));
                        setPhotoError(null);
                        setPhotoSuccess(null);
                      }
                    }}
                  />
                </label>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-2 border-t border-hairline">
              <div>
                {photoModalEmployee.hasFaceEnrolled && (
                  <button
                    type="button"
                    onClick={async () => {
                      if (!confirm(`Are you sure you want to remove the biometric face profile for ${photoModalEmployee.name}?`)) return;
                      try {
                        await deleteEmployeePhoto(photoModalEmployee.employeeId);
                        setPhotoSuccess(`Biometric face profile removed for ${photoModalEmployee.name}.`);
                        setPhotoModalEmployee({ ...photoModalEmployee, hasFaceEnrolled: false });
                      } catch (err: any) {
                        setPhotoError(err.message || 'Failed to remove face profile.');
                      }
                    }}
                    className="px-3 py-1.5 text-xs-tech rounded-sm border border-red-900/40 text-status-high hover:bg-red-950/20 inline-flex items-center gap-1.5 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Remove Face Profile
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setPhotoModalEmployee(null);
                    setSelectedPhotoFile(null);
                    setPhotoPreviewUrl(null);
                    setPhotoError(null);
                    setPhotoSuccess(null);
                  }}
                  className="px-3 py-1.5 text-xs-tech rounded-sm border border-hairline hover:bg-hairline/30 text-text-sec transition-colors"
                >
                  Close
                </button>
                <button
                  type="button"
                  disabled={!selectedPhotoFile || isUploadingPhoto}
                  onClick={async () => {
                    if (!selectedPhotoFile) return;
                    setIsUploadingPhoto(true);
                    setPhotoError(null);
                    setPhotoSuccess(null);
                    try {
                      const res = await uploadEmployeePhoto(photoModalEmployee.employeeId, selectedPhotoFile);
                      setPhotoSuccess(res.message);
                      setPhotoModalEmployee({ ...photoModalEmployee, hasFaceEnrolled: true });
                      setSelectedPhotoFile(null);
                      setPhotoPreviewUrl(null);
                    } catch (err: any) {
                      setPhotoError(err.message || 'Failed to enroll biometric face.');
                    } finally {
                      setIsUploadingPhoto(false);
                    }
                  }}
                  className="px-4 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black inline-flex items-center gap-1.5 disabled:opacity-50 transition-colors"
                >
                  {isUploadingPhoto ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin" />
                      Extracting Biometric Vector...
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      Enroll Biometric Face
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

