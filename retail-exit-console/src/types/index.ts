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

export interface ExitEvent {
  eventId: string;
  timestamp: string; // ISO 8601
  laneId: string;
  employeeId?: string;
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
  | 'products'
  | 'employees'
  | 'invoices'
  | 'reports'
  | 'settings';

export type DetectionBoxType = 'PERSON_MATCHED' | 'PERSON_UNMATCHED' | 'ITEM' | 'STATIC_IMAGE';

export interface DetectionBox {
  box: [number, number, number, number]; // [x, y, w, h]
  type: DetectionBoxType;
  label: string;
  confidence: number;
  color: 'green' | 'red' | 'amber' | 'static';
  entity?: string;
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
  activeTransaction?: {
    eventId: string;
    status: string; // 'CONSENSUS_PENDING' | 'RESOLVED'
    displayText: string;
    verdict?: string;
    severity?: string;
    deltaUnits?: number;
  };
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
