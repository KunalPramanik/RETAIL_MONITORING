/**
 * SEC-OPS 2.0 API Client
 *
 * Provides type-safe HTTP communication with the FastAPI backend server.
 * Adheres strictly to the REST contracts defined in Part D and schema in Part C.
 */

import type {
  ExitEvent,
  Alert,
  Product,
  Employee,
  Invoice,
  SensorLane,
  Camera,
  SystemSettings,
  StaticImageRecord,
  CameraDetectionUpdate,
  DiscoveredDevice,
  UsbDeviceRecord,
  UsbStatusResponse,
} from '../types';

function getEffectiveApiBase(): string {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl;
  if (typeof window !== 'undefined') {
    const host =
      window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? '127.0.0.1'
        : window.location.hostname;
    return `http://${host}:8000/api`;
  }
  return 'http://127.0.0.1:8000/api';
}

const API_BASE = getEffectiveApiBase();
export const BACKEND_URL = API_BASE.replace(/\/api\/?$/, '');

/** Resolves any relative media/snapshot URL against the active dynamic backend URL. */
export function resolveMediaUrl(pathOrUrl?: string | null): string {
  if (!pathOrUrl) return '';
  if (
    pathOrUrl.startsWith('http://') ||
    pathOrUrl.startsWith('https://') ||
    pathOrUrl.startsWith('blob:') ||
    pathOrUrl.startsWith('data:')
  ) {
    return pathOrUrl;
  }
  const cleanPath = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`;
  return `${BACKEND_URL}${cleanPath}`;
}

/** Dynamically builds the live CCTV snapshot stream URL for a given camera ID. */
export function getCameraSnapshotUrl(
  cameraId: string,
  key?: number | string,
  quality?: 'main' | 'sub',
  raw: boolean = true
): string {
  const t = key || Date.now();
  const streamParam = quality === 'sub' ? '&stream=sub' : '';
  const rawParam = raw ? '&raw=true' : '';
  return `${BACKEND_URL}/api/cameras/${cameraId}/snapshot?t=${t}${streamParam}${rawParam}`;
}

export interface LiveKPIs {
  todayThroughputUnits: number;
  openAlertsCount: number;
  openAlertsBySeverity: { high: number; medium: number; low: number };
  consensusAccuracyRate: number;
  activeLanesCount: number;
  totalLanesCount: number;
  camerasOnlineCount: number;
  camerasTotalCount: number;
}

export interface TestConnectionResult {
  success: boolean;
  status: string;
  errorMessage?: string;
  streamUrl?: string;
  snapshotUrl?: string;
  resolution?: string;
  fps?: number;
  latencyMs?: number;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  let res: Response;
  try {
    res = await fetch(url, { ...options, headers });
  } catch (err: any) {
    if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) {
      throw new Error(
        `Unable to reach SEC-OPS backend service at ${API_BASE}. Please verify edge server is running on port 8000.`
      );
    }
    throw new Error(`Network transport failure calling ${endpoint}: ${err.message || err}`);
  }

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errJson = await res.json();
      if (Array.isArray(errJson.detail)) {
        // FastAPI 422 validation error unpacking
        errorDetail = errJson.detail
          .map((d: any) => `${d.loc ? d.loc.slice(1).join('.') : 'field'}: ${d.msg}`)
          .join('; ');
      } else {
        errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
      }
    } catch {
      // ignore
    }

    if (res.status === 403) {
      throw new Error(`Insufficient Permissions (403): ${errorDetail || 'Action requires ADMIN or SUPERVISOR role.'}`);
    }
    if (res.status === 404) {
      throw new Error(`Resource Not Found (404): ${errorDetail || endpoint}`);
    }
    throw new Error(errorDetail || `HTTP error ${res.status}`);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

export const api = {
  // ── KPIs ──────────────────────────────────────────────────────────
  async getLiveKPIs(): Promise<LiveKPIs> {
    return request<LiveKPIs>('/kpis/live');
  },

  // ── Events ────────────────────────────────────────────────────────
  async getEvents(params?: {
    laneId?: string;
    sku?: string;
    verdict?: string;
    page?: number;
  }): Promise<ExitEvent[]> {
    const searchParams = new URLSearchParams();
    if (params?.laneId) searchParams.set('laneId', params.laneId);
    if (params?.sku) searchParams.set('sku', params.sku);
    if (params?.verdict) searchParams.set('verdict', params.verdict);
    if (params?.page) searchParams.set('page', params.page.toString());
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return request<ExitEvent[]>(`/events${qs}`);
  },

  async getEventDetail(eventId: string): Promise<ExitEvent> {
    return request<ExitEvent>(`/events/${eventId}`);
  },

  // ── Alerts ────────────────────────────────────────────────────────
  async getAlerts(params?: { status?: string; severity?: string; page?: number }): Promise<Alert[]> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.severity) searchParams.set('severity', params.severity);
    if (params?.page) searchParams.set('page', params.page.toString());
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return request<Alert[]>(`/alerts${qs}`);
  },

  async acknowledgeAlert(alertId: string, acknowledgedBy = 'SUPERVISOR'): Promise<Alert> {
    return request<Alert>(`/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ acknowledgedBy }),
    });
  },

  async resolveAlert(alertId: string, resolutionNote: string, resolvedBy = 'SUPERVISOR'): Promise<Alert> {
    return request<Alert>(`/alerts/${alertId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolutionNote, resolvedBy }),
    });
  },

  // ── Products ──────────────────────────────────────────────────────
  async getProducts(query?: string): Promise<Product[]> {
    const qs = query ? `?query=${encodeURIComponent(query)}` : '';
    return request<Product[]>(`/products${qs}`);
  },

  async createProduct(data: Omit<Product, 'productId'>): Promise<Product> {
    return request<Product>('/products', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateProduct(productId: string, data: Partial<Product>): Promise<Product> {
    return request<Product>(`/products/${productId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async deleteProduct(productId: string): Promise<void> {
    return request<void>(`/products/${productId}`, {
      method: 'DELETE',
    });
  },

  // ── Employees ─────────────────────────────────────────────────────
  async getEmployees(query?: string): Promise<Employee[]> {
    const qs = query ? `?query=${encodeURIComponent(query)}` : '';
    return request<Employee[]>(`/employees${qs}`);
  },

  async createEmployee(data: {
    name: string;
    role: string;
    rfidBadgeId: string;
    shiftId?: string;
  }): Promise<Employee> {
    return request<Employee>('/employees', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getEmployeeHistory(employeeId: string): Promise<ExitEvent[]> {
    return request<ExitEvent[]>(`/employees/${employeeId}/history`);
  },

  // ── Invoices ──────────────────────────────────────────────────────
  async getInvoices(query?: string): Promise<Invoice[]> {
    const qs = query ? `?query=${encodeURIComponent(query)}` : '';
    return request<Invoice[]>(`/invoices${qs}`);
  },

  async uploadInvoice(formData: FormData): Promise<Invoice> {
    const url = `${API_BASE}/invoices/upload`;
    const res = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      let errorDetail = res.statusText;
      try {
        const errJson = await res.json();
        errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
      } catch {}
      throw new Error(errorDetail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },

  async createInvoice(data: any): Promise<Invoice> {
    return request<Invoice>('/invoices', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // ── Cameras ───────────────────────────────────────────────────────
  async getCameras(params?: { laneId?: string; status?: string }): Promise<Camera[]> {
    const searchParams = new URLSearchParams();
    if (params?.laneId) searchParams.set('laneId', params.laneId);
    if (params?.status) searchParams.set('status', params.status);
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return request<Camera[]>(`/cameras${qs}`);
  },

  async createCamera(data: {
    label: string;
    ipAddress: string;
    rtspPath: string;
    subStreamPath?: string;
    laneId?: string;
    credentials?: string;
  }): Promise<Camera> {
    return request<Camera>('/cameras', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async testCameraConnection(
    cameraId: string,
    overrides?: { ipAddress?: string; rtspPath?: string; subStreamPath?: string; streamUrl?: string; credentials?: string }
  ): Promise<TestConnectionResult> {
    return request<TestConnectionResult>(`/cameras/${cameraId}/test-connection`, {
      method: 'POST',
      body: JSON.stringify(overrides || {}),
    });
  },

  async scanCameraNow(cameraId: string): Promise<{
    success: boolean;
    eventId: string;
    laneId: string;
    casesDetected: number;
    unitsDetected: number;
    verdict: string;
    severity: string;
    snapshotUrl?: string;
    detail?: string;
  }> {
    return request(`/cameras/${cameraId}/scan-now`, { method: 'POST' });
  },

  async getCameraTelemetry(cameraId: string): Promise<{
    cameraId: string;
    status: string;
    fpsObserved: number;
    bitrateKbps: number;
    droppedFrames: number;
    lastHeartbeatAt?: string;
  }> {
    return request(`/cameras/${cameraId}/telemetry`);
  },

  async getCameraLiveDetection(cameraId: string): Promise<CameraDetectionUpdate> {
    return request<CameraDetectionUpdate>(`/cameras/${cameraId}/detection`);
  },

  async getStaticImages(params?: { cameraId?: string; limit?: number }): Promise<StaticImageRecord[]> {
    const searchParams = new URLSearchParams();
    if (params?.cameraId) searchParams.set('camera_id', params.cameraId);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return request<StaticImageRecord[]>(`/cameras/static-images${qs}`);
  },

  async updateCamera(cameraId: string, data: Partial<Camera>): Promise<Camera> {
    return request<Camera>(`/cameras/${cameraId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async deleteCamera(cameraId: string): Promise<void> {
    return request<void>(`/cameras/${cameraId}`, {
      method: 'DELETE',
    });
  },

  // ── QR Camera Auto-Pairing (Both Directions) ──────────────────────
  async decodeCameraQr(qrPayload: string): Promise<{
    ipAddress?: string;
    model?: string;
    suggestedLabel?: string;
    rtspPath?: string;
    credentials?: string;
  }> {
    return request('/cameras/qr-decode', {
      method: 'POST',
      body: JSON.stringify({ qrPayload }),
    });
  },

  async createPairingToken(data: {
    storeId?: string;
    laneId?: string;
    wifiSsid?: string;
    wifiPassword?: string;
  }): Promise<{
    tokenId: string;
    tokenValue: string;
    qrPayload: string;
    expiresAt: string;
    status: 'ACTIVE' | 'EXPIRED' | 'USED';
    laneId?: string;
  }> {
    return request('/cameras/pairing-tokens', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getPairingTokenStatus(tokenId: string): Promise<{
    tokenId: string;
    tokenValue: string;
    qrPayload: string;
    expiresAt: string;
    status: 'ACTIVE' | 'EXPIRED' | 'USED';
    laneId?: string;
    usedAt?: string;
    usedByCameraId?: string;
  }> {
    return request(`/cameras/pairing-tokens/${tokenId}`);
  },

  async pairCamera(data: {
    token: string;
    ipAddress?: string;
    label?: string;
    model?: string;
    rtspPath?: string;
  }): Promise<Camera> {
    return request('/cameras/pair', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // ── Lanes ─────────────────────────────────────────────────────────
  async getLanes(): Promise<SensorLane[]> {
    return request<SensorLane[]>('/lanes');
  },

  async createLane(data: { label: string; storeId?: string }): Promise<SensorLane> {
    return request<SensorLane>('/lanes', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async toggleTurnstile(laneId: string): Promise<{ laneId: string; isLocked: boolean }> {
    return request<{ laneId: string; isLocked: boolean }>(`/lanes/${laneId}/turnstile/toggle`, {
      method: 'POST',
    });
  },

  // ── Settings & Thresholds ─────────────────────────────────────────
  async getSettings(): Promise<SystemSettings> {
    return request<SystemSettings>('/settings/thresholds');
  },

  async updateSettings(data: Partial<SystemSettings>): Promise<SystemSettings> {
    return request<SystemSettings>('/settings/thresholds', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  // ── Ingest & Scenario Simulation ──────────────────────────────────
  async injectScenario(scenarioType: string): Promise<ExitEvent> {
    return request<ExitEvent>(`/ingest/scenario?scenario_type=${encodeURIComponent(scenarioType)}`, {
      method: 'POST',
    });
  },

  // ── Part I Compliance: Zero-State Purge ───────────────────────────
  async resetDatabase(): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>('/settings/reset-database', {
      method: 'POST',
    });
  },

  // ── Reports & Compliance Exports ──────────────────────────────────
  async downloadAuditXlsx(params?: { laneId?: string; severity?: string; startDate?: string; endDate?: string }): Promise<void> {
    const query = new URLSearchParams();
    if (params?.laneId && params.laneId !== 'ALL') query.append('lane_id', params.laneId);
    if (params?.severity && params.severity !== 'ALL') query.append('severity', params.severity);
    if (params?.startDate) query.append('start_date', params.startDate);
    if (params?.endDate) query.append('end_date', params.endDate);

    const token = localStorage.getItem('secops_token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const url = `${API_BASE}/reports/export/xlsx?${query.toString()}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`Failed to download Excel report: ${res.statusText}`);
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `audit_export_${new Date().toISOString().slice(0, 10)}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  },

  async downloadCsv(dataset: string, params?: { laneId?: string; severity?: string }): Promise<void> {
    const query = new URLSearchParams({ dataset });
    if (params?.laneId && params.laneId !== 'ALL') query.append('lane_id', params.laneId);
    if (params?.severity && params.severity !== 'ALL') query.append('severity', params.severity);

    const token = localStorage.getItem('secops_token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const url = `${API_BASE}/reports/export/csv?${query.toString()}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`Failed to download CSV: ${res.statusText}`);
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `${dataset}_export_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  },

  // ── PTZ Camera Control ────────────────────────────────────────────
  async movePtz(cameraId: string, pan: number, tilt: number, zoom: number = 0, velocity: number = 1.0): Promise<any> {
    return request(`/cameras/${cameraId}/ptz/move`, {
      method: 'POST',
      body: JSON.stringify({ pan, tilt, zoom, velocity }),
    });
  },

  async stopPtz(cameraId: string): Promise<any> {
    return request(`/cameras/${cameraId}/ptz/stop`, {
      method: 'POST',
    });
  },

  async gotoPtzPreset(cameraId: string, presetId: number): Promise<any> {
    return request(`/cameras/${cameraId}/ptz/preset/${presetId}`, {
      method: 'POST',
    });
  },

  async getPtzStatus(cameraId: string): Promise<{ isPtzCapable: boolean; pan: number; tilt: number; zoom: number; moving: boolean }> {
    return request(`/cameras/${cameraId}/ptz/status`);
  },

  // ── Hardware Auto-Discovery & Auto-Connect ────────────────────────
  async getDiscoveredDevices(): Promise<DiscoveredDevice[]> {
    return request<DiscoveredDevice[]>('/discovery/devices');
  },

  async confirmDiscoveredDevice(data: { discoveryId: string; laneId: string; label?: string }): Promise<any> {
    return request('/discovery/confirm-lane', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getUsbDevices(): Promise<UsbStatusResponse> {
    return request<UsbStatusResponse>('/discovery/usb');
  },

  async configureUsbDevice(data: { port: string; deviceType: string; laneId?: string; customModel?: string }): Promise<any> {
    return request('/discovery/usb/configure', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async scanDiscoveryNow(): Promise<{ lanDevicesDiscovered: number; usbDevicesConnected: number; lanDevices: DiscoveredDevice[]; usbDevices: UsbDeviceRecord[] }> {
    return request('/discovery/scan-now', {
      method: 'POST',
    });
  },

  async simulateDiscovery(data: { deviceType: string; ipAddress?: string; port?: string; vid?: string; pid?: string; manufacturer?: string; model?: string; suggestedLaneId?: string }): Promise<any> {
    return request('/discovery/simulate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
};

