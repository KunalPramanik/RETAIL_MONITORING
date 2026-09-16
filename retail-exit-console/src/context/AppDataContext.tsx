import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import type {
  ExitEvent,
  Alert,
  Product,
  Employee,
  Invoice,
  SensorLane,
  SystemSettings,
  Camera,
  ViewType,
  CameraDetectionUpdate,
  StaticImageRecord,
} from '../types';
import { api, BACKEND_URL, type TestConnectionResult } from '../api/client';
import { playAlarmSound } from '../utils/audioAlarm';

export const DEFAULT_SETTINGS: SystemSettings = {
  lowSeverityThreshold: 1,
  medSeverityThreshold: 3,
  highSeverityThreshold: 6,
  repeatOffenderThreshold: 3,
  repeatOffenderWindowDays: 30,
  cameraOfflineAlertAfterSec: 60,
  audioAlarmEnabled: true,
  alarmVolume: 0.75,
  streamFrequencySeconds: 8,
  autoSimulationEnabled: false,
  turnstileAutoLockOnHigh: true,
};

interface AppDataContextType {
  events: ExitEvent[];
  alerts: Alert[];
  products: Product[];
  employees: Employee[];
  invoices: Invoice[];
  lanes: SensorLane[];
  cameras: Camera[];
  settings: SystemSettings;
  selectedEventId: string | null;
  selectedEvent: ExitEvent | undefined;
  turnstileLocked: Record<string, boolean>;
  latestHighAlertId: string | null;
  isStreaming: boolean;
  activeLanesCount: number;
  openAlertsCount: number;
  openAlertsBySeverity: { high: number; medium: number; low: number };
  todayThroughputUnits: number;
  consensusAccuracyRate: number;
  camerasOnlineCount: number;
  camerasTotalCount: number;
  wsConnected: boolean;
  wsStatus: 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';
  reconnectAttempt: number;
  isLoading: boolean;
  apiError: string | null;
  activeView: ViewType;
  latestDetections: Record<string, CameraDetectionUpdate>;
  staticImages: StaticImageRecord[];

  // Actions
  setActiveView: (view: ViewType) => void;
  refreshStaticImages: () => Promise<void>;
  setSelectedEventId: (id: string | null) => void;
  resolveAlert: (alertId: string, note: string, resolvedBy?: string) => Promise<void>;
  acknowledgeAlert: (alertId: string, acknowledgedBy?: string) => Promise<void>;
  addProduct: (product: Omit<Product, 'productId'>) => Promise<Product>;
  updateProduct: (product: Product) => Promise<Product>;
  deleteProduct: (productId: string) => Promise<void>;
  addEmployee: (employee: { name: string; role: string; rfidBadgeId: string; shiftId?: string }) => Promise<Employee>;
  updateEmployee: (employee: Employee) => void;
  updateSettings: (newSettings: Partial<SystemSettings>) => Promise<void>;
  toggleLaneTurnstile: (laneId: string) => Promise<void>;
  injectSimulatedScenario: (scenarioType: 'CLEAN_PASS' | 'CASE_PACK_OVER' | 'RFID_BLINDSPOT' | 'REPEAT_OFFENDER_HIGH' | 'UNDER_DECLARE_OCR') => Promise<void>;
  setIsStreaming: (streaming: boolean) => void;
  testAlarmSound: () => void;
  refreshAllData: () => Promise<void>;
  resetDatabase: () => Promise<void>;

  // Invoice Actions
  uploadInvoice: (formData: FormData) => Promise<Invoice>;
  createInvoice: (data: any) => Promise<Invoice>;

  addCamera: (camera: { label: string; ipAddress: string; rtspPath: string; laneId?: string; credentials?: string; pairingMethod?: "MANUAL" | "QR_CAMERA_DISPLAYED" | "QR_APP_GENERATED" }) => Promise<Camera>;
  updateCamera: (camera: Partial<Camera> & { cameraId: string }) => Promise<void>;
  removeCamera: (cameraId: string) => Promise<void>;
  testCameraConnection: (cameraId: string, overrides?: { ipAddress?: string; rtspPath?: string; credentials?: string }) => Promise<TestConnectionResult>;
  createLane: (lane: { label: string; storeId?: string }) => Promise<SensorLane>;
  decodeCameraQr: (qrPayload: string) => Promise<{ ipAddress?: string; model?: string; suggestedLabel?: string; rtspPath?: string; credentials?: string }>;
  createPairingToken: (data: { storeId?: string; laneId?: string; wifiSsid?: string; wifiPassword?: string }) => Promise<{ tokenId: string; tokenValue: string; qrPayload: string; expiresAt: string; status: string; laneId?: string }>;
  getPairingTokenStatus: (tokenId: string) => Promise<{ tokenId: string; tokenValue: string; qrPayload: string; expiresAt: string; status: string; laneId?: string; usedAt?: string; usedByCameraId?: string }>;
  pairCamera: (data: { token: string; ipAddress?: string; label?: string; model?: string; rtspPath?: string }) => Promise<Camera>;
}

const AppDataContext = createContext<AppDataContextType | undefined>(undefined);

export const AppDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Pure zero-data initial state adhering to Part I Zero-Hardcode policy
  const [events, setEvents] = useState<ExitEvent[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [lanes, setLanes] = useState<SensorLane[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [settings, setSettings] = useState<SystemSettings>(DEFAULT_SETTINGS);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [turnstileLocked, setTurnstileLocked] = useState<Record<string, boolean>>({});
  const [latestHighAlertId, setLatestHighAlertId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [wsStatus, setWsStatus] = useState<'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'>('DISCONNECTED');
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ViewType>('dashboard');
  const [latestDetections, setLatestDetections] = useState<Record<string, CameraDetectionUpdate>>({});
  const [staticImages, setStaticImages] = useState<StaticImageRecord[]>([]);

  const refreshStaticImages = useCallback(async () => {
    try {
      const records = await api.getStaticImages();
      setStaticImages(records);
    } catch (err: any) {
      const isConnRefused =
        err?.message?.includes('Unable to reach') ||
        err?.message?.includes('Failed to fetch') ||
        err?.message?.includes('NetworkError');
      if (!isConnRefused) {
        console.warn('Could not fetch static images:', err);
      }
    }
  }, []);

  // Selected event lookup
  const selectedEvent = useMemo(() => {
    if (!selectedEventId) return events[0];
    return events.find((e) => e.eventId === selectedEventId) || events[0];
  }, [events, selectedEventId]);

  // Derived metrics
  const activeLanesCount = useMemo(() => {
    return lanes.filter((l) => l.status === 'ONLINE').length;
  }, [lanes]);

  const camerasTotalCount = useMemo(() => {
    return cameras.filter((c) => !c.removedAt).length;
  }, [cameras]);

  const camerasOnlineCount = useMemo(() => {
    return cameras.filter((c) => !c.removedAt && c.status === 'ONLINE').length;
  }, [cameras]);

  const openAlerts = useMemo(() => {
    return alerts.filter((a) => a.status === 'OPEN' || a.status === 'ACKNOWLEDGED');
  }, [alerts]);

  const openAlertsCount = openAlerts.length;

  const openAlertsBySeverity = useMemo(() => {
    return {
      high: openAlerts.filter((a) => a.severity === 'HIGH').length,
      medium: openAlerts.filter((a) => a.severity === 'MEDIUM').length,
      low: openAlerts.filter((a) => a.severity === 'LOW').length,
    };
  }, [openAlerts]);

  const todayThroughputUnits = useMemo(() => {
    return events.reduce((acc, ev) => acc + (ev.consensusUnits || 0), 0);
  }, [events]);

  const consensusAccuracyRate = useMemo(() => {
    if (events.length === 0) return 100;
    const passCount = events.filter((e) => e.verdict === 'PASS').length;
    return Math.round((passCount / events.length) * 1000) / 10;
  }, [events]);

  // ── Initial Fetch from Live Backend ──────────────────────────────────────
  const refreshAllData = useCallback(async () => {
    setIsLoading(true);
    setApiError(null);
    try {
      let hadNetworkFailure = false;
      const handleFetchError = (resource: string, err: any) => {
        const isConnRefused =
          err?.message?.includes('Unable to reach') ||
          err?.message?.includes('Failed to fetch') ||
          err?.message?.includes('NetworkError');
        if (isConnRefused) {
          hadNetworkFailure = true;
        } else {
          console.warn(`Could not fetch ${resource}:`, err);
        }
        return [];
      };

      const [prodRes, empRes, laneRes, camRes, evtRes, altRes, invRes, setRes] = await Promise.all([
        api.getProducts().catch((err) => handleFetchError('products', err)),
        api.getEmployees().catch((err) => handleFetchError('employees', err)),
        api.getLanes().catch((err) => handleFetchError('lanes', err)),
        api.getCameras().catch((err) => handleFetchError('cameras', err)),
        api.getEvents().catch((err) => handleFetchError('events', err)),
        api.getAlerts().catch((err) => handleFetchError('alerts', err)),
        api.getInvoices().catch((err) => handleFetchError('invoices', err)),
        api.getSettings().catch((err) => {
          handleFetchError('settings', err);
          return null;
        }),
      ]);

      setProducts(prodRes);
      setEmployees(empRes);
      setLanes(laneRes);
      // Deduplicate camera entries by unique cameraId
      const camDedupeMap = new Map<string, Camera>();
      for (const c of camRes) {
        if (c.cameraId && !camDedupeMap.has(c.cameraId)) {
          camDedupeMap.set(c.cameraId, c);
        }
      }
      setCameras(Array.from(camDedupeMap.values()));
      setEvents(evtRes);
      setAlerts(altRes);
      setInvoices(invRes);
      if (setRes) {
        setSettings((prev) => ({ ...prev, ...setRes }));
      }
      if (evtRes.length > 0) {
        setSelectedEventId(evtRes[0].eventId);
      }
      refreshStaticImages().catch(() => {});

      if (hadNetworkFailure) {
        setApiError('Unable to reach SEC-OPS backend service on port 8000. Waiting for edge server...');
      } else {
        setApiError(null);
      }
    } catch (err: any) {
      const isConnRefused =
        err?.message?.includes('Unable to reach') ||
        err?.message?.includes('Failed to fetch') ||
        err?.message?.includes('NetworkError');
      if (!isConnRefused) {
        console.error('Initialization error:', err);
      }
      setApiError(err.message || 'Failed to connect to SEC-OPS backend');
    } finally {
      setIsLoading(false);
    }
  }, [refreshStaticImages]);

  useEffect(() => {
    refreshAllData();
  }, [refreshAllData]);

  // Handle Tab Title Alert Flashing
  useEffect(() => {
    if (openAlertsBySeverity.high > 0) {
      let toggle = false;
      const interval = setInterval(() => {
        document.title = toggle
          ? `⚠️ [ALARM: ${openAlertsBySeverity.high} HIGH] Exit Lane Alert`
          : `SEC-OPS // Exit Monitor & Inventory Intelligence`;
        toggle = !toggle;
      }, 1200);
      return () => {
        clearInterval(interval);
        document.title = 'SEC-OPS // Exit Monitor & Inventory Intelligence';
      };
    } else {
      document.title = 'SEC-OPS // Exit Monitor & Inventory Intelligence';
    }
  }, [openAlertsBySeverity.high]);

  // ── WebSocket Live Connection Layer with Exponential Backoff ──────────────
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let isMounted = true;

    const connectWebSocket = () => {
      if (!isMounted) return;
      try {
        let wsHost = '127.0.0.1:8000';
        let isSecure = false;
        try {
          if (BACKEND_URL) {
            const parsed = new URL(BACKEND_URL);
            const hostName =
              parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1'
                ? '127.0.0.1'
                : parsed.hostname;
            wsHost = `${hostName}${parsed.port ? `:${parsed.port}` : ''}`;
            isSecure = parsed.protocol === 'https:';
          } else if (typeof window !== 'undefined') {
            const hostName =
              window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
                ? '127.0.0.1'
                : window.location.hostname;
            wsHost = `${hostName}:8000`;
            isSecure = window.location.protocol === 'https:';
          }
        } catch {
          wsHost = '127.0.0.1:8000';
        }

        const defaultProto = isSecure ? 'wss:' : 'ws:';
        const wsUrl = import.meta.env.VITE_WS_URL || `${defaultProto}//${wsHost}/ws/live`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (!isMounted) {
            try { ws?.close(); } catch {}
            return;
          }
          attempt = 0;
          setReconnectAttempt(0);
          setWsConnected(true);
          setWsStatus('CONNECTED');
          setApiError(null);
          refreshAllData().catch(() => {});
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'new_event') {
              const payload = data.payload;
              setEvents((prev) => {
                if (prev.some((e) => e.eventId === payload.eventId)) return prev;
                return [payload, ...prev.slice(0, 49)];
              });
              setSelectedEventId(payload.eventId);
            } else if (data.type === 'new_alert') {
              const payload = data.payload;
              setAlerts((prev) => {
                if (prev.some((a) => a.alertId === payload.alertId)) return prev;
                return [payload, ...prev];
              });
              if (payload.severity === 'HIGH') {
                setLatestHighAlertId(payload.alertId);
                if (settings.audioAlarmEnabled) {
                  playAlarmSound(settings.alarmVolume, 'HIGH');
                }
              }
            } else if (data.type === 'alert_status_changed') {
              const payload = data.payload;
              setAlerts((prev) =>
                prev.map((a) => (a.alertId === payload.alertId ? { ...a, ...payload } : a))
              );
            } else if (data.type === 'camera_status_changed') {
              const payload = data.payload;
              setCameras((prev) => {
                const exists = prev.some((c) => c.cameraId === payload.cameraId);
                if (exists) {
                  return prev.map((c) => (c.cameraId === payload.cameraId ? { ...c, ...payload } : c));
                }
                return [payload, ...prev];
              });
            } else if (data.type === 'pairing_token_used') {
              api.getCameras().then((cList) => {
                const map = new Map<string, Camera>();
                for (const c of cList) {
                  if (c.cameraId && !map.has(c.cameraId)) map.set(c.cameraId, c);
                }
                setCameras(Array.from(map.values()));
              }).catch(() => {});
            } else if (data.type === 'turnstile_lock_changed') {
              const { laneId, isLocked } = data.payload;
              setTurnstileLocked((prev) => ({ ...prev, [laneId]: isLocked }));
            } else if (data.type === 'lane_status_changed') {
              const payload = data.payload;
              setLanes((prev) =>
                prev.map((l) => (l.laneId === payload.laneId ? { ...l, ...payload } : l))
              );
            } else if (data.type === 'invoice_uploaded') {
              api.getInvoices().then(setInvoices).catch(() => {});
              api.getEvents().then(setEvents).catch(() => {});
            } else if (data.type === 'detection_update') {
              const payload = data.payload;
              if (payload?.cameraId) {
                setLatestDetections((prev) => ({
                  ...prev,
                  [payload.cameraId]: payload,
                }));
                if (payload.boxes?.some((b: any) => b.type === 'STATIC_IMAGE')) {
                  refreshStaticImages().catch(() => {});
                }
              }
            }
          } catch (e) {
            console.error('Error parsing WebSocket message:', e);
          }
        };

        const scheduleReconnect = () => {
          if (!isMounted) return;
          setWsConnected(false);
          setWsStatus('RECONNECTING');
          attempt += 1;
          setReconnectAttempt(attempt);
          const delay = Math.min(2000 * Math.pow(1.5, attempt), 20000) * (0.8 + Math.random() * 0.4);
          reconnectTimeout = setTimeout(connectWebSocket, Math.round(delay));
        };

        ws.onclose = () => {
          scheduleReconnect();
        };

        ws.onerror = () => {
          if (!isMounted) return;
          setWsConnected(false);
          setWsStatus('RECONNECTING');
        };
      } catch {
        if (!isMounted) return;
        setWsConnected(false);
        setWsStatus('RECONNECTING');
        attempt += 1;
        setReconnectAttempt(attempt);
        const delay = Math.min(2000 * Math.pow(1.5, attempt), 20000);
        reconnectTimeout = setTimeout(connectWebSocket, Math.round(delay));
      }
    };

    connectWebSocket();

    return () => {
      isMounted = false;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        } else if (ws.readyState === WebSocket.CONNECTING) {
          ws.onopen = () => {
            try { ws?.close(); } catch {}
          };
          ws.onerror = () => {};
        }
      }
    };
  }, [settings.audioAlarmEnabled, settings.alarmVolume, refreshAllData, refreshStaticImages]);

  // ── Actions Wired to Real Backend ───────────────────────────────────────

  const addProduct = async (productData: Omit<Product, 'productId'>): Promise<Product> => {
    const created = await api.createProduct(productData);
    setProducts((prev) => [...prev, created]);
    return created;
  };

  const updateProduct = async (product: Product): Promise<Product> => {
    const updated = await api.updateProduct(product.productId, product);
    setProducts((prev) => prev.map((p) => (p.productId === updated.productId ? updated : p)));
    return updated;
  };

  const deleteProduct = async (productId: string): Promise<void> => {
    await api.deleteProduct(productId);
    setProducts((prev) => prev.filter((p) => p.productId !== productId));
  };

  const addEmployee = async (employeeData: { name: string; role: string; rfidBadgeId: string; shiftId?: string }): Promise<Employee> => {
    const created = await api.createEmployee(employeeData);
    setEmployees((prev) => [...prev, created]);
    return created;
  };

  const updateEmployee = (employee: Employee) => {
    setEmployees((prev) => prev.map((e) => (e.employeeId === employee.employeeId ? employee : e)));
  };

  const addCamera = async (data: { label: string; ipAddress: string; rtspPath: string; laneId?: string; credentials?: string }): Promise<Camera> => {
    const created = await api.createCamera(data);
    setCameras((prev) => [created, ...prev.filter((c) => c.cameraId !== created.cameraId)]);
    return created;
  };

  const updateCamera = async (camera: Partial<Camera> & { cameraId: string }): Promise<void> => {
    const updated = await api.updateCamera(camera.cameraId, camera);
    setCameras((prev) => prev.map((c) => (c.cameraId === updated.cameraId ? { ...c, ...updated } : c)));
  };

  const removeCamera = async (cameraId: string): Promise<void> => {
    await api.deleteCamera(cameraId);
    setCameras((prev) => prev.filter((c) => c.cameraId !== cameraId));
  };

  const testCameraConnection = async (
    cameraId: string,
    overrides?: { ipAddress?: string; rtspPath?: string; credentials?: string }
  ): Promise<TestConnectionResult> => {
    const res = await api.testCameraConnection(cameraId, overrides);
    if (res.success) {
      setCameras((prev) =>
        prev.map((c) =>
          c.cameraId === cameraId
            ? { ...c, status: 'ONLINE', lastHeartbeatAt: new Date().toISOString() }
            : c
        )
      );
    }
    return res;
  };

  const decodeCameraQr = async (qrPayload: string) => {
    return api.decodeCameraQr(qrPayload);
  };

  const createPairingToken = async (data: { storeId?: string; laneId?: string; wifiSsid?: string; wifiPassword?: string }) => {
    return api.createPairingToken(data);
  };

  const getPairingTokenStatus = async (tokenId: string) => {
    return api.getPairingTokenStatus(tokenId);
  };

  const pairCamera = async (data: { token: string; ipAddress?: string; label?: string; model?: string; rtspPath?: string }) => {
    const created = await api.pairCamera(data);
    setCameras((prev) => [created, ...prev.filter((c) => c.cameraId !== created.cameraId)]);
    return created;
  };

  const createLane = async (data: { label: string; storeId?: string }): Promise<SensorLane> => {
    const created = await api.createLane(data);
    setLanes((prev) => [...prev, created]);
    return created;
  };

  const toggleLaneTurnstile = async (laneId: string): Promise<void> => {
    const res = await api.toggleTurnstile(laneId);
    setTurnstileLocked((prev) => ({ ...prev, [laneId]: res.isLocked }));
  };

  const acknowledgeAlert = async (alertId: string, acknowledgedBy = 'SUPERVISOR'): Promise<void> => {
    const updated = await api.acknowledgeAlert(alertId, acknowledgedBy);
    setAlerts((prev) => prev.map((a) => (a.alertId === alertId ? { ...a, ...updated } : a)));
  };

  const resolveAlert = async (alertId: string, note: string, resolvedBy = 'SUPERVISOR'): Promise<void> => {
    const updated = await api.resolveAlert(alertId, note, resolvedBy);
    setAlerts((prev) => prev.map((a) => (a.alertId === alertId ? { ...a, ...updated } : a)));
  };

  const updateSettings = async (newSettings: Partial<SystemSettings>): Promise<void> => {
    const updated = await api.updateSettings(newSettings);
    setSettings((prev) => ({ ...prev, ...updated }));
  };

  const injectSimulatedScenario = async (
    scenarioType: 'CLEAN_PASS' | 'CASE_PACK_OVER' | 'RFID_BLINDSPOT' | 'REPEAT_OFFENDER_HIGH' | 'UNDER_DECLARE_OCR'
  ): Promise<void> => {
    const event = await api.injectScenario(scenarioType);
    setEvents((prev) => {
      if (prev.some((e) => e.eventId === event.eventId)) return prev;
      return [event, ...prev.slice(0, 49)];
    });
    setSelectedEventId(event.eventId);
  };

  const testAlarmSound = () => {
    playAlarmSound(settings.alarmVolume, 'HIGH');
  };

  const uploadInvoice = async (formData: FormData): Promise<Invoice> => {
    const created = await api.uploadInvoice(formData);
    setInvoices((prev) => [created, ...prev.filter((i) => i.invoiceId !== created.invoiceId)]);
    api.getEvents().then(setEvents).catch(console.warn);
    return created;
  };

  const createInvoice = async (data: any): Promise<Invoice> => {
    const created = await api.createInvoice(data);
    setInvoices((prev) => [created, ...prev.filter((i) => i.invoiceId !== created.invoiceId)]);
    api.getEvents().then(setEvents).catch(console.warn);
    return created;
  };

  const resetDatabase = async (): Promise<void> => {
    await api.resetDatabase();
    await refreshAllData();
  };

  return (
    <AppDataContext.Provider
      value={{
        events,
        alerts,
        products,
        employees,
        invoices,
        lanes,
        cameras,
        settings,
        selectedEventId,
        selectedEvent,
        turnstileLocked,
        latestHighAlertId,
        isStreaming,
        activeLanesCount,
        openAlertsCount,
        openAlertsBySeverity,
        todayThroughputUnits,
        consensusAccuracyRate,
        camerasOnlineCount,
        camerasTotalCount,
        wsConnected,
        wsStatus,
        reconnectAttempt,
        isLoading,
        apiError,
        activeView,
        latestDetections,
        staticImages,
        refreshStaticImages,
        setActiveView,
        setSelectedEventId,
        resolveAlert,
        acknowledgeAlert,
        addProduct,
        updateProduct,
        deleteProduct,
        addEmployee,
        updateEmployee,
        updateSettings,
        toggleLaneTurnstile,
        injectSimulatedScenario,
        setIsStreaming,
        testAlarmSound,
        refreshAllData,
        resetDatabase,
        uploadInvoice,
        createInvoice,
        addCamera,
        updateCamera,
        removeCamera,
        testCameraConnection,
        createLane,
        decodeCameraQr,
        createPairingToken,
        getPairingTokenStatus,
        pairCamera,
      }}
    >
      {children}
    </AppDataContext.Provider>
  );
};

export const useAppData = (): AppDataContextType => {
  const context = useContext(AppDataContext);
  if (!context) {
    throw new Error('useAppData must be used within an AppDataProvider');
  }
  return context;
};
