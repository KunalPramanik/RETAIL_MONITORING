export type Severity = "NONE" | "LOW" | "MEDIUM" | "HIGH";
export type Verdict = "PASS" | "MISMATCH";
export type CameraStatus = "ONLINE" | "OFFLINE" | "DEGRADED" | "PENDING_SETUP";

export interface Product {
  productId: string;
  skuCode: string;
  name: string;
  category: string;
  packSize: number; // units per case
  unitPrice: number;
  casePrice: number;
  reorderThreshold: number;
}

export interface LineItemDetection {
  productId: string;
  casesQty: number;
  unitsQty: number;
}

export interface EmployeeVerificationDetail {
  employeeId: string;
  name: string;
  role: string;
  shift: string;
  rfidBadgeId: string;
  activeFlag: boolean;
  similarity: number;
  mismatchCount30d: number;
}

export interface AppearanceSummary {
  summaryId: string;
  clothingTopColor: string;
  clothingBottomColor: string;
  buildCategory: 'SHORTER' | 'AVERAGE' | 'TALLER' | 'UNKNOWN';
  buildConfidence: number;
  accessories: string[];
  accessoriesConfidence: Record<string, number>;
  modelVersion: string;
  recentSightingsCount: number;
  reidClusterId?: string;
  createdAt: string;
}

export interface ExitEvent {
  eventId: string;
  timestamp: string; // ISO 8601
  laneId: string;
  employeeId?: string;
  employeeName?: string;
  employeeRole?: string;
  employeeMatchConfidence?: number;
  faceMatchDecision?: string;
  casesDetected: number;
  unitsDetected: number;
  visionCount: number;
  rfidCount: number;
  weightKg: number;
  consensusUnits: number;
  invoiceId?: string;
  declaredUnits?: number;
  deltaUnits?: number;
  verdict: Verdict;
  severity: Severity;
  snapshotUrl?: string;
  lineItems: LineItemDetection[];
  notes?: string;
  verifiedEmployee?: EmployeeVerificationDetail;
  appearanceSummary?: AppearanceSummary;
}

export interface Alert {
  alertId: string;
  eventId?: string;
  cameraId?: string;
  alertType: "SENSOR_DISAGREEMENT" | "OVER_CARRY" | "UNDER_DECLARE" | "UNAUTHORIZED_ACCESS" | "INTRUSION" | "CAMERA_OFFLINE";
  severity: Severity;
  deltaUnits: number;
  createdAt: string;
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
  resolvedBy?: string;
  resolutionNote?: string;
}

export interface Employee {
  employeeId: string;
  name: string;
  role: string;
  rfidBadgeId: string;
  shiftId: string;
  activeFlag: boolean;
  mismatchCount30d: number;
  avatarSeed?: string;
  hasFaceEnrolled?: boolean;
  embeddingUpdatedAt?: string;
}

export interface InvoiceLineItem {
  skuCode: string;
  description: string;
  casesDeclared: number;
  unitsPerCase: number;
  totalUnits: number;
  status: "MATCHED" | "DISCREPANCY";
}

export interface Invoice {
  invoiceId: string;
  invoiceNumber: string;
  carrierName: string;
  storeDestination: string;
  ocrConfidence: number; // 0 to 100%
  scanTimestamp: string;
  declaredTotalUnits: number;
  linkedEventId?: string;
  lineItems: InvoiceLineItem[];
  rawOcrText?: string;
  rawFileUrl?: string;
}

export interface SensorLane {
  laneId: string;
  name: string;
  location: string;
  status: "ONLINE" | "DEGRADED" | "OFFLINE";
  cameraIp: string;
  cameraFps: number;
  rfidGatePowerDbm: number;
  scaleTareKg: number;
  lastPing: string;
}

export interface Camera {
  cameraId: string;
  label: string; // e.g. "Exit Lane 3 — North"
  laneId?: string; // unassigned until linked to a lane
  ipAddress: string;
  rtspPath: string;
  subStreamPath?: string; // e.g. "/Streaming/Channels/102"
  streamUrl?: string; // media-server-exposed WebRTC/HLS URL
  pairingMethod?: "MANUAL" | "QR_CAMERA_DISPLAYED" | "QR_APP_GENERATED";
  status: CameraStatus;
  resolution?: string; // e.g. "1920x1080"
  fps?: number;
  bitrateKbps?: number;
  fpsObserved?: number;
  droppedFrames?: number;
  hasAudio?: boolean;
  lastHeartbeatAt?: string;
  offlineSince?: string;
  addedAt: string;
  removedAt?: string;
  ptzCapable?: boolean;
  isIrMode?: boolean;
}

export interface QRDecodeResult {
  ipAddress?: string;
  model?: string;
  suggestedLabel?: string;
  rtspPath?: string;
  credentials?: string;
}

export interface PairingTokenResult {
  tokenId: string;
  tokenValue: string;
  qrPayload: string;
  expiresAt: string;
  status: "ACTIVE" | "EXPIRED" | "USED";
  laneId?: string;
  usedAt?: string;
  usedByCameraId?: string;
}

export interface SystemSettings {
  lowSeverityThreshold: number;
  medSeverityThreshold: number;
  highSeverityThreshold: number;
  repeatOffenderThreshold: number;
  repeatOffenderWindowDays: number;
  cameraOfflineAlertAfterSec: number;
  audioAlarmEnabled: boolean;
  alarmVolume: number;
  streamFrequencySeconds: number;
  autoSimulationEnabled: boolean;
  turnstileAutoLockOnHigh: boolean;
}

export type ViewType =
  | 'dashboard'
  | 'events'
  | 'alerts'
  | 'dispatch'
  | 'tripwire'
  | 'products'
  | 'employees'
  | 'invoices'
  | 'reports'
  | 'settings';


export type DetectionBoxType =
  | 'PERSON_MATCHED'
  | 'PERSON_UNMATCHED'
  | 'ITEM'
  | 'STATIC_IMAGE'
  | 'VEHICLE'
  | 'DOORWAY'
  | 'MATERIAL_INSTANCE'
  | 'HAZARD_FIRE'
  | 'SUSPICIOUS_BEHAVIOR'
  | 'PPE_COMPLIANT'
  | 'PPE_VIOLATION'
  | 'PEDESTRIAN'
  | 'ZONE_OCCUPANCY'
  | 'OPEN_VOCAB'
  | 'DESKTOP_SCREEN'
  | 'LAPTOP';

export interface DetectionBox {
  box: [number, number, number, number]; // [x, y, w, h]
  type: DetectionBoxType;
  label: string;
  confidence: number;
  color: 'green' | 'red' | 'amber' | 'static' | 'cyan' | 'fire' | 'suspicious' | 'ppe_ok' | 'ppe_violation';
  entity?: string;
  keypoints?: Record<string, [number, number]>;
  connections?: [string, string][];
}

export interface CameraDetectionUpdate {
  cameraId: string;
  laneId?: string;
  frameTs: string;
  frameWidth: number;
  frameHeight: number;
  boxes: DetectionBox[];
  entityCount: number;
  casesDetected?: number;
  unitsDetected?: number;
  carrierName?: string;
  faceDecision?: string;
  livenessDecision?: string;
  livenessScore?: number;
  confidence?: number;
  boxesCount?: number;
  occupancy?: number;
  totalFootfallIn?: number;
  totalFootfallOut?: number;
  crowdDensity?: string;
  uniqueVisitors?: number;
  trackingFidelity?: string;
  zoneMetrics?: Array<{
    zone_id: string;
    label: string;
    current_occupancy: number;
    avg_dwell_seconds: number;
    max_dwell_seconds: number;
  }>;
  tripwireTallies?: Array<{
    tripwire_id: string;
    label: string;
    in_count: number;
    out_count: number;
    net_flow: number;
  }>;
  activeTransaction?: {
    eventId: string;
    status: string; // 'CONSENSUS_PENDING' | 'RESOLVED'
    displayText: string;
    verdict?: string;
    severity?: string;
    deltaUnits?: number;
  };
  segmentedMaterials?: MaterialInstanceItem[];
  materialCounts?: Record<string, number>;
  totalMaterialCount?: number;
  activeCarriers?: Array<{
    personName: string;
    isKnown: boolean;
    employeeId?: string | null;
    direction: 'ENTRY' | 'EXIT' | 'TRAVERSAL';
    materials: Record<string, number>;
    summary: string;
    box: [number, number, number, number];
  }>;
  frameAnalysisReport?: string;
  categorizedEntities?: Array<{
    category: string;
    canonicalLabel: string;
    rawLabel: string;
    confidence: number;
    bbox: [number, number, number, number];
    status: string;
    isSpoofed: boolean;
    spoofFormat?: string;
    registryReference?: string;
  }>;
  recentLogs: Array<{
    id: string;
    timestamp: string;
    text: string;
    type: string;
  }>;
  timestamp?: string;
}

export interface StaticImageRecord {
  detectionId: string;
  cameraId: string;
  cameraLabel: string;
  frameTs: string;
  bbox: [number, number, number, number];
  livenessScore: number;
  classification: string;
  classificationConfidence: number;
  modelVersion: string;
  suppressedAlert: boolean;
  createdAt: string;
}

export interface DiscoveredDevice {
  discoveryId: string;
  ipAddress: string;
  deviceType: 'CAMERA' | 'RFID_GATE';
  manufacturer: string;
  model: string;
  macAddress?: string;
  rtspPath: string;
  subStreamPath?: string;
  credentials?: string;
  suggestedLaneId?: string;
  suggestedLaneName?: string;
  suggestionConfidence?: number;
  isReachable: boolean;
  latencyMs?: number;
  previewSnapshotUrl?: string;
  status: 'UNASSIGNED' | 'CONFIRMED' | 'TESTING';
  discoveredAt: string;
}

export interface UsbDeviceRecord {
  port: string;
  vid: string;
  pid: string;
  deviceType: 'WEIGHT_SCALE' | 'WEBCAM' | 'UNRECOGNIZED';
  manufacturer: string;
  model: string;
  laneId: string;
  isConnected: boolean;
  status: string;
  lastSeenAt?: string;
  rawDescription?: string;
}

export interface UsbStatusResponse {
  activeScalePort?: string | null;
  devices: UsbDeviceRecord[];
}

export interface MaterialClassDefinition {
  class_id: string;
  name: string;
  category: string;
  typical_dimensions_cm: number[];
  severity_tier: "LOW" | "MED" | "HIGH";
  density_notes: string;
  count_unit: string;
}

export interface MaterialInstanceItem {
  classId: string;
  className: string;
  confidence: number;
  bbox: [number, number, number, number];
  polygon: number[][];
  areaPixels: number;
}

export interface DispatchSessionRecord {
  sessionId: string;
  dockLaneId: string;
  manifestId?: string;
  carrierEmployeeId?: string;
  carrierName?: string;
  vehicleIdentifier?: string;
  status: "ACTIVE" | "COMPLETED" | "FLAGGED_DISCREPANCY" | "CANCELLED";
  startedAt: string;
  completedAt?: string;
  beforeCount: Record<string, number>;
  afterCount: Record<string, number>;
  removedDelta: Record<string, number>;
  manifestExpected: Record<string, number>;
  discrepancyType: "MATCH" | "OVER_AUTHORIZED" | "UNDER_COUNT";
  discrepancyMagnitude: number;
  trackingInterruptedSeconds: number;
  archivalSnapshotUrl?: string;
  notes?: string;
}

export interface VirtualTripwireRecord {
  tripwireId: string;
  cameraId: string;
  label: string;
  lineCoords: number[][];
  directionMode: "ENTRY" | "EXIT" | "BOTH";
  active: boolean;
  createdAt: string;
}

export interface TripwireCrossingRecord {
  crossingId: string;
  tripwireId: string;
  cameraId: string;
  trackId: string;
  timestamp: string;
  direction: "ENTRY" | "EXIT";
  entityType: "PERSON" | "VEHICLE";
  biometricStatus: "VERIFIED_KNOWN" | "UNKNOWN_INTRUDER" | "UNAVAILABLE";
  matchedEmployeeId?: string;
  isTailgating: boolean;
  tailgatingDetails?: Record<string, any>;
  snapshotUrl?: string;
}

export interface MaterialMovementItem {
  materialName: string;
  skuCode?: string;
  quantity: number;
  direction: 'ENTRY' | 'EXIT';
}

export interface EmployeeMovementRecord {
  eventId: string;
  timestamp: string;
  laneId: string;
  cameraName: string;
  direction: 'ENTRY' | 'EXIT' | 'TRAVERSAL';
  personIdentity: string;
  isKnown: boolean;
  materialsCarried: MaterialMovementItem[];
  casesDetected: number;
  unitsDetected: number;
  snapshotUrl?: string;
}

export interface EmployeeMovementSummaryResponse {
  employeeId: string;
  name: string;
  totalEntries: number;
  totalExits: number;
  totalTraversals: number;
  lastSeenCamera?: string;
  lastSeenTimestamp?: string;
  materialsHandledSummary: Record<string, { in: number; out: number; net: number }>;
  movements: EmployeeMovementRecord[];
}


