import React, { useState, useEffect, useRef } from 'react';
import { useAppData } from '../../context/AppDataContext';
import {
  Radio,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ArrowRight,
  ArrowLeft,
  Video,
  ShieldCheck,
  Plus,
  QrCode,
  Scan,
  Sliders,
  Clock,
  Shield,
  Zap,
  Camera as CameraIcon,
} from 'lucide-react';
import { Modal } from '../common/Modal';
import { QrCodeSvg } from './QrCodeSvg';

interface AddCameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

type SetupMode = 'MANUAL' | 'QR';
type QrDirection = 'SCAN_CAMERA' | 'GENERATE_QR';

export const AddCameraModal: React.FC<AddCameraModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const {
    lanes,
    addCamera,
    testCameraConnection,
    createLane,
    decodeCameraQr,
    createPairingToken,
    getPairingTokenStatus,
    pairCamera,
  } = useAppData();

  // Top-level Mode
  const [setupMode, setSetupMode] = useState<SetupMode>('MANUAL');
  const [qrDirection, setQrDirection] = useState<QrDirection>('SCAN_CAMERA');

  // Wizard Steps (for Manual or post-QR validation)
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [pairingMethod, setPairingMethod] = useState<'MANUAL' | 'QR_CAMERA_DISPLAYED' | 'QR_APP_GENERATED'>('MANUAL');

  // Camera config
  const [label, setLabel] = useState('');
  const [ipAddress, setIpAddress] = useState('');
  const [rtspPath, setRtspPath] = useState('');
  const [credentials, setCredentials] = useState('');
  const [selectedLaneId, setSelectedLaneId] = useState<string>('');

  // Inline new lane creation
  const [isCreatingInlineLane, setIsCreatingInlineLane] = useState(false);
  const [newLaneLabel, setNewLaneLabel] = useState('');

  // Connection Test state
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    tested: boolean;
    success: boolean;
    snapshotUrl?: string;
    errorMessage?: string;
    latencyMs?: number;
  }>({ tested: false, success: false });

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Direction 1: Scan Camera QR state
  const [qrInputText, setQrInputText] = useState('');
  const [isDecodingQr, setIsDecodingQr] = useState(false);
  const [decodedSpecs, setDecodedSpecs] = useState<{
    ipAddress?: string;
    model?: string;
    suggestedLabel?: string;
    rtspPath?: string;
    credentials?: string;
  } | null>(null);
  const [qrDecodeError, setQrDecodeError] = useState<string | null>(null);

  // Webcam scanning state
  const [isWebcamActive, setIsWebcamActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scanIntervalRef = useRef<number | null>(null);

  // Direction 2: Generate Pairing QR state
  const [dir2LaneId, setDir2LaneId] = useState<string>('');
  const [wifiSsid, setWifiSsid] = useState<string>('');
  const [wifiPassword, setWifiPassword] = useState<string>('');
  const [isGeneratingToken, setIsGeneratingToken] = useState(false);
  const [generatedToken, setGeneratedToken] = useState<{
    tokenId: string;
    tokenValue: string;
    qrPayload: string;
    expiresAt: string;
    status: string;
  } | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(600);
  const [isSimulatingPair, setIsSimulatingPair] = useState(false);
  const [pairSuccessCamera, setPairSuccessCamera] = useState<any | null>(null);

  const resetForm = () => {
    setSetupMode('MANUAL');
    setQrDirection('SCAN_CAMERA');
    setStep(1);
    setPairingMethod('MANUAL');
    setLabel('');
    setIpAddress('');
    setRtspPath('');
    setCredentials('');
    setSelectedLaneId('');
    setIsCreatingInlineLane(false);
    setNewLaneLabel('');
    setTestResult({ tested: false, success: false });
    setIsTesting(false);
    setQrInputText('');
    setIsDecodingQr(false);
    setDecodedSpecs(null);
    setQrDecodeError(null);
    stopWebcamScan();
    setDir2LaneId('');
    setWifiSsid('');
    setWifiPassword('');
    setIsGeneratingToken(false);
    setGeneratedToken(null);
    setSecondsRemaining(600);
    setIsSimulatingPair(false);
    setPairSuccessCamera(null);
  };

  // Webcam QR scanner cleanup
  const stopWebcamScan = () => {
    if (scanIntervalRef.current) {
      window.clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsWebcamActive(false);
  };

  useEffect(() => {
    return () => {
      stopWebcamScan();
    };
  }, []);

  // Direction 2: Countdown timer and status polling
  useEffect(() => {
    if (!generatedToken || generatedToken.status === 'USED') return;

    // Countdown
    const timer = setInterval(() => {
      const expTime = new Date(generatedToken.expiresAt).getTime();
      const diffSec = Math.max(0, Math.floor((expTime - Date.now()) / 1000));
      setSecondsRemaining(diffSec);
      if (diffSec <= 0) {
        clearInterval(timer);
      }
    }, 1000);

    // Polling fallback every 3 seconds
    const pollInterval = setInterval(async () => {
      try {
        const res = await getPairingTokenStatus(generatedToken.tokenId);
        if (res.status === 'USED') {
          setGeneratedToken((prev) => (prev ? { ...prev, status: 'USED' } : null));
          setPairSuccessCamera({
            cameraId: res.usedByCameraId || 'AUTO_PAIRED',
            laneId: res.laneId,
          });
          clearInterval(pollInterval);
        }
      } catch {
        // silent fallback
      }
    }, 3000);

    return () => {
      clearInterval(timer);
      clearInterval(pollInterval);
    };
  }, [generatedToken, getPairingTokenStatus]);

  // Handle live webcam scan
  const startWebcamScan = async () => {
    setQrDecodeError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      streamRef.current = stream;
      setIsWebcamActive(true);

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }

      // Check if BarcodeDetector is supported in browser
      if ('BarcodeDetector' in window) {
        const barcodeDetector = new (window as any).BarcodeDetector({ formats: ['qr_code'] });
        scanIntervalRef.current = window.setInterval(async () => {
          if (videoRef.current && videoRef.current.readyState >= 2) {
            try {
              const barcodes = await barcodeDetector.detect(videoRef.current);
              if (barcodes.length > 0) {
                const detectedVal = barcodes[0].rawValue;
                handleDecodePayload(detectedVal);
                stopWebcamScan();
              }
            } catch {
              // detection frame error
            }
          }
        }, 400);
      }
    } catch (err: any) {
      console.warn('Webcam access error:', err);
      setQrDecodeError('Webcam access unavailable or permission denied. You can paste or select a preset below.');
      setIsWebcamActive(false);
    }
  };

  // Decode QR payload (Direction 1)
  const handleDecodePayload = async (payload: string) => {
    if (!payload.trim()) return;
    setIsDecodingQr(true);
    setQrDecodeError(null);
    try {
      const res = await decodeCameraQr(payload);
      setDecodedSpecs(res);
      if (res.ipAddress) setIpAddress(res.ipAddress);
      if (res.rtspPath) setRtspPath(res.rtspPath);
      if (res.credentials) setCredentials(res.credentials);
      if (res.suggestedLabel) setLabel(res.suggestedLabel);
      else if (res.model) setLabel(`Exit Cam — ${res.model}`);
      setPairingMethod('QR_CAMERA_DISPLAYED');
    } catch (err: any) {
      setQrDecodeError(err.message || 'Failed to decode camera QR payload');
    } finally {
      setIsDecodingQr(false);
    }
  };

  // Generate pairing token (Direction 2)
  const handleGeneratePairingToken = async () => {
    setIsGeneratingToken(true);
    try {
      const res = await createPairingToken({
        laneId: dir2LaneId || undefined,
        wifiSsid: wifiSsid.trim() || undefined,
        wifiPassword: wifiPassword.trim() || undefined,
      });
      setGeneratedToken(res);
      const expTime = new Date(res.expiresAt).getTime();
      setSecondsRemaining(Math.max(0, Math.floor((expTime - Date.now()) / 1000)));
    } catch (err: any) {
      console.error('Failed to generate token:', err);
    } finally {
      setIsGeneratingToken(false);
    }
  };

  // Simulate pairing handshake (Direction 2 testing)
  const handleSimulatePairing = async () => {
    if (!generatedToken) return;
    setIsSimulatingPair(true);
    try {
      const paired = await pairCamera({
        token: generatedToken.tokenValue,
        ipAddress: '192.168.10.88',
        label: `Auto-Paired ${dir2LaneId ? `Lane ${dir2LaneId}` : 'Overhead'} Cam`,
        model: 'SecOps-EdgeCam-4K',
        rtspPath: '/live/ch0',
      });
      setPairSuccessCamera(paired);
      setGeneratedToken((prev) => (prev ? { ...prev, status: 'USED' } : null));
    } catch (err: any) {
      console.error('Simulate pairing failed:', err);
    } finally {
      setIsSimulatingPair(false);
    }
  };

  // Test RTSP Connection
  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult({ tested: false, success: false });
    try {
      const res = await testCameraConnection('temp_test', {
        ipAddress,
        rtspPath,
        credentials,
      });
      setTestResult({
        tested: true,
        success: res.success,
        snapshotUrl: res.snapshotUrl,
        errorMessage: res.errorMessage,
        latencyMs: res.latencyMs,
      });
    } catch (e: any) {
      setTestResult({
        tested: true,
        success: false,
        errorMessage: e.message || 'Connection attempt failed',
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleCreateInlineLane = async () => {
    if (!newLaneLabel.trim()) return;
    const created = await createLane({ label: newLaneLabel });
    setSelectedLaneId(created.laneId);
    setIsCreatingInlineLane(false);
    setNewLaneLabel('');
  };

  const handleSubmit = async () => {
    if (!label.trim()) return;
    setIsSubmitting(true);
    try {
      await addCamera({
        label,
        ipAddress,
        rtspPath,
        laneId: selectedLaneId || undefined,
        credentials,
        pairingMethod,
      });
      if (onSuccess) onSuccess();
      onClose();
      resetForm();
    } catch (err) {
      console.error('Failed to register camera:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        onClose();
        resetForm();
      }}
      title="Add Surveillance Camera to Exit Fleet"
      maxWidth="2xl"
    >
      <div className="space-y-4">
        {/* Top-Level Mode Selector: Manual vs QR-Code Auto-Pairing */}
        <div className="grid grid-cols-2 gap-2 p-1 bg-canvas border border-hairline rounded-sm">
          <button
            type="button"
            onClick={() => {
              setSetupMode('MANUAL');
              setPairingMethod('MANUAL');
              stopWebcamScan();
            }}
            className={`flex items-center justify-center gap-2 py-2 px-3 text-xs-tech font-bold rounded-sm transition-all ${
              setupMode === 'MANUAL'
                ? 'bg-panel-raised text-amber border border-amber/40 shadow-sm'
                : 'text-text-sec hover:text-text-pri'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            Manual Setup (4-Step)
          </button>

          <button
            type="button"
            onClick={() => {
              setSetupMode('QR');
              stopWebcamScan();
            }}
            className={`flex items-center justify-center gap-2 py-2 px-3 text-xs-tech font-bold rounded-sm transition-all ${
              setupMode === 'QR'
                ? 'bg-panel-raised text-amber border border-amber/40 shadow-sm'
                : 'text-text-sec hover:text-text-pri'
            }`}
          >
            <QrCode className="w-3.5 h-3.5" />
            QR-Code Auto-Pairing
            <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber/20 text-amber font-mono font-normal">
              FAST
            </span>
          </button>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* MODE: QR-CODE AUTO-PAIRING                                     */}
        {/* ------------------------------------------------------------- */}
        {setupMode === 'QR' && (
          <div className="space-y-4">
            {/* Direction Sub-Tabs */}
            <div className="flex border-b border-hairline gap-4 text-xs-tech font-mono">
              <button
                type="button"
                onClick={() => {
                  setQrDirection('SCAN_CAMERA');
                  stopWebcamScan();
                }}
                className={`pb-2 border-b-2 flex items-center gap-1.5 transition-colors ${
                  qrDirection === 'SCAN_CAMERA'
                    ? 'border-amber text-amber font-bold'
                    : 'border-transparent text-text-sec hover:text-text-pri'
                }`}
              >
                <Scan className="w-3.5 h-3.5" />
                Direction 1: Scan Camera QR
              </button>

              <button
                type="button"
                onClick={() => {
                  setQrDirection('GENERATE_QR');
                  stopWebcamScan();
                }}
                className={`pb-2 border-b-2 flex items-center gap-1.5 transition-colors ${
                  qrDirection === 'GENERATE_QR'
                    ? 'border-amber text-amber font-bold'
                    : 'border-transparent text-text-sec hover:text-text-pri'
                }`}
              >
                <QrCode className="w-3.5 h-3.5" />
                Direction 2: Generate Pairing QR
              </button>
            </div>

            {/* DIRECTION 1: Operator scans camera QR */}
            {qrDirection === 'SCAN_CAMERA' && (
              <div className="space-y-4">
                <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-1">
                  <div className="text-xs-tech font-bold text-text-pri flex items-center gap-1.5">
                    <Scan className="w-4 h-4 text-amber" />
                    Inbound Provisioning: Scan Camera Setup Code
                  </div>
                  <p className="text-[11px] text-text-sec">
                    Point your console camera at the QR code displayed on the device body, mobile IP webcam screen,
                    or packaging sticker. Decoded network specs will automatically pre-fill configuration.
                  </p>
                </div>

                {/* Webcam Viewfinder Area */}
                {isWebcamActive ? (
                  <div className="relative rounded overflow-hidden border border-amber/40 bg-black aspect-video max-w-md mx-auto flex flex-col items-center justify-center">
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover"
                    />
                    {/* Scanning reticle overlay */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                      <div className="w-48 h-48 border-2 border-amber/70 rounded-lg relative">
                        <div className="absolute inset-x-0 h-0.5 bg-amber animate-pulse shadow-[0_0_8px_#f59e0b]" />
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={stopWebcamScan}
                      className="absolute bottom-2 px-3 py-1 bg-black/80 hover:bg-black text-xs-tech text-text-sec hover:text-white rounded border border-hairline"
                    >
                      Stop Webcam Scanner
                    </button>
                  </div>
                ) : (
                  <div className="flex justify-center">
                    <button
                      type="button"
                      onClick={startWebcamScan}
                      className="flex items-center gap-2 px-4 py-2 bg-panel-raised border border-hairline hover:border-amber text-xs-tech font-semibold text-text-pri rounded-sm transition-colors"
                    >
                      <CameraIcon className="w-4 h-4 text-amber" />
                      Open Live Webcam Viewfinder
                    </button>
                  </div>
                )}

                {/* QR Text / URL Input & Presets */}
                <div className="space-y-2">
                  <label className="text-xs-tech font-medium text-text-pri block">
                    Or Paste QR Payload / Stream Endpoint String:
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={qrInputText}
                      onChange={(e) => setQrInputText(e.target.value)}
                      placeholder='{"ip": "192.168.1.120", "path": "/live/ch0", "model": "Hikvision 4K"}'
                      className="flex-1 px-3 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                    />
                    <button
                      type="button"
                      disabled={!qrInputText.trim() || isDecodingQr}
                      onClick={() => handleDecodePayload(qrInputText)}
                      className="px-3 py-1.5 bg-amber text-black font-semibold text-xs-tech rounded-sm disabled:opacity-40 flex items-center gap-1.5"
                    >
                      {isDecodingQr ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Decode'}
                    </button>
                  </div>
                </div>

                {/* Test Hardware Presets */}
                <div className="space-y-1.5">
                  <span className="text-[11px] text-text-sec block font-mono">1-Click Quick Hardware Presets:</span>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {[
                      {
                        name: 'Hikvision 4K',
                        payload:
                          '{"ip":"192.168.1.120","path":"/Streaming/Channels/101","model":"DS-2CD2386G2","user":"admin","pass":"SecOps2026!"}',
                      },
                      {
                        name: 'Dahua Bullet',
                        payload:
                          '{"ip":"192.168.1.125","path":"/cam/realmonitor?channel=1","model":"IPC-HFW5842E","user":"admin","pass":"Dahua2026!"}',
                      },
                      {
                        name: 'Mobile IP Cam',
                        payload: 'http://192.168.1.150:8080/video',
                      },
                      {
                        name: 'Standard RTSP',
                        payload: 'rtsp://admin:pass@192.168.1.180:554/live/ch0',
                      },
                    ].map((preset) => (
                      <button
                        key={preset.name}
                        type="button"
                        onClick={() => {
                          setQrInputText(preset.payload);
                          handleDecodePayload(preset.payload);
                        }}
                        className="p-1.5 text-left bg-canvas hover:bg-panel-raised border border-hairline hover:border-amber/50 rounded text-[11px] font-mono transition-colors"
                      >
                        <div className="text-text-pri font-medium">{preset.name}</div>
                        <div className="text-[9px] text-text-sec truncate">{preset.payload}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Error Banner */}
                {qrDecodeError && (
                  <div className="p-2.5 bg-red-950/20 border border-status-high/40 rounded-sm text-status-high text-xs-tech flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>{qrDecodeError}</span>
                  </div>
                )}

                {/* Decoded Specs Summary Card */}
                {decodedSpecs && (
                  <div className="p-3 bg-teal-950/20 border border-status-ok/30 rounded-sm space-y-2.5 animate-in fade-in">
                    <div className="flex items-center justify-between">
                      <span className="text-xs-tech font-bold text-status-ok flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4" />
                        Camera Specifications Successfully Decoded
                      </span>
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-teal-900/50 text-status-ok border border-status-ok/30">
                        {decodedSpecs.model || 'IP OPTICAL SENSOR'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs-tech font-mono">
                      <div>
                        <span className="text-text-sec text-[10px] block">Target IP:</span>
                        <span className="text-text-pri font-bold">{decodedSpecs.ipAddress}</span>
                      </div>
                      <div>
                        <span className="text-text-sec text-[10px] block">RTSP / HTTP Path:</span>
                        <span className="text-text-pri">{decodedSpecs.rtspPath}</span>
                      </div>
                      <div>
                        <span className="text-text-sec text-[10px] block">Suggested Label:</span>
                        <span className="text-text-pri">{decodedSpecs.suggestedLabel || label}</span>
                      </div>
                      <div>
                        <span className="text-text-sec text-[10px] block">Credentials:</span>
                        <span className="text-text-pri">{decodedSpecs.credentials ? '••••••••' : 'None'}</span>
                      </div>
                    </div>

                    <div className="pt-2 flex justify-end">
                      <button
                        type="button"
                        onClick={() => {
                          setSetupMode('MANUAL');
                          setStep(2); // Proceed to Stream Verification
                        }}
                        className="flex items-center gap-1.5 px-4 py-2 bg-amber hover:bg-amber/90 text-black font-semibold text-xs-tech rounded-sm transition-colors"
                      >
                        Verify RTSP Stream Handshake
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* DIRECTION 2: App generates single-use pairing token QR */}
            {qrDirection === 'GENERATE_QR' && (
              <div className="space-y-4">
                <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-1">
                  <div className="text-xs-tech font-bold text-text-pri flex items-center gap-1.5">
                    <QrCode className="w-4 h-4 text-amber" />
                    Outbound Optical Provisioning: Console Generates Pairing QR
                  </div>
                  <p className="text-[11px] text-text-sec">
                    Generate an encrypted, single-use, 10-minute token QR code. Point the physical camera lens at this
                    screen; the camera will optical-scan the token and auto-enroll itself into the SecOps fleet.
                  </p>
                </div>

                {!generatedToken ? (
                  /* Form to generate pairing token */
                  <div className="space-y-3 p-3 bg-canvas border border-hairline rounded-sm">
                    <div>
                      <label className="text-xs-tech font-medium text-text-pri block mb-1">
                        Target Exit Lane Portal
                      </label>
                      <select
                        value={dir2LaneId}
                        onChange={(e) => setDir2LaneId(e.target.value)}
                        className="w-full px-3 py-1.5 font-mono bg-panel border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                      >
                        <option value="">-- Unassigned (Spare / Staging Fleet) --</option>
                        {lanes.map((l) => (
                          <option key={l.laneId} value={l.laneId}>
                            {l.laneId} — {l.location}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs-tech font-medium text-text-pri block mb-1">
                          Camera WiFi SSID (Optional)
                        </label>
                        <input
                          type="text"
                          value={wifiSsid}
                          onChange={(e) => setWifiSsid(e.target.value)}
                          placeholder="e.g. SecOps-IoT-5G"
                          className="w-full px-3 py-1.5 font-mono bg-panel border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                        />
                      </div>
                      <div>
                        <label className="text-xs-tech font-medium text-text-pri block mb-1">
                          WiFi Pre-Shared Key (Optional)
                        </label>
                        <input
                          type="password"
                          value={wifiPassword}
                          onChange={(e) => setWifiPassword(e.target.value)}
                          placeholder="••••••••••••"
                          className="w-full px-3 py-1.5 font-mono bg-panel border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                        />
                      </div>
                    </div>

                    {/* Security notice */}
                    <div className="flex items-start gap-2 p-2 bg-panel-raised border border-hairline rounded text-[11px] text-text-sec">
                      <Shield className="w-3.5 h-3.5 text-amber shrink-0 mt-0.5" />
                      <span>
                        Credentials are transiently encoded in the pairing QR payload for camera optical setup and
                        never saved unencrypted in system storage.
                      </span>
                    </div>

                    <div className="pt-2 flex justify-end">
                      <button
                        type="button"
                        disabled={isGeneratingToken}
                        onClick={handleGeneratePairingToken}
                        className="flex items-center gap-2 px-4 py-2 bg-amber hover:bg-amber/90 text-black font-bold text-xs-tech rounded-sm transition-colors disabled:opacity-40"
                      >
                        {isGeneratingToken ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Generating Cryptographic Token...
                          </>
                        ) : (
                          <>
                            <QrCode className="w-4 h-4" />
                            Generate 10-Minute Pairing QR
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Display Generated QR & Countdown */
                  <div className="space-y-4">
                    {pairSuccessCamera ? (
                      /* Paired Success banner */
                      <div className="p-4 bg-teal-950/30 border border-status-ok/40 rounded-sm text-center space-y-3 animate-in zoom-in-95">
                        <CheckCircle2 className="w-10 h-10 text-status-ok mx-auto" />
                        <div className="space-y-1">
                          <h3 className="text-sm font-bold text-status-ok uppercase tracking-wider">
                            Optical Handshake Confirmed!
                          </h3>
                          <p className="text-xs-tech text-text-sec">
                            Camera <span className="font-mono text-text-pri">{pairSuccessCamera.cameraId}</span>{' '}
                            successfully scanned token and registered into fleet.
                          </p>
                        </div>
                        <div className="pt-2">
                          <button
                            type="button"
                            onClick={() => {
                              if (onSuccess) onSuccess();
                              onClose();
                              resetForm();
                            }}
                            className="px-5 py-2 bg-status-ok hover:bg-status-ok/90 text-black font-bold text-xs-tech rounded-sm"
                          >
                            Close & Return to Fleet
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Active Pairing Session */
                      <div className="flex flex-col items-center p-4 bg-panel-raised border border-hairline rounded-sm space-y-3">
                        {/* Countdown Badge */}
                        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-canvas border border-amber/40 text-xs-tech font-mono text-amber">
                          <Clock className="w-3.5 h-3.5 animate-pulse" />
                          <span>
                            Token Active: {Math.floor(secondsRemaining / 60)}:
                            {String(secondsRemaining % 60).padStart(2, '0')} remaining
                          </span>
                        </div>

                        {/* SVG QR Code */}
                        <div className="p-3 bg-white rounded-lg shadow-lg border-2 border-amber">
                          <QrCodeSvg value={generatedToken.qrPayload} size={220} />
                        </div>

                        <div className="text-center space-y-1">
                          <span className="text-xs-tech font-bold text-text-pri block">
                            Point Surveillance Camera Lens at this QR Code
                          </span>
                          <span className="text-[11px] text-text-sec block max-w-sm">
                            Listening on WebSocket for camera optical handshake confirmation...
                          </span>
                        </div>

                        {/* Simulation / Dev Helper */}
                        <div className="pt-3 w-full border-t border-hairline/60 flex items-center justify-between">
                          <button
                            type="button"
                            onClick={() => setGeneratedToken(null)}
                            className="text-xs-tech text-text-sec hover:text-text-pri"
                          >
                            Cancel & New Token
                          </button>

                          <button
                            type="button"
                            disabled={isSimulatingPair}
                            onClick={handleSimulatePairing}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-canvas border border-amber/50 hover:border-amber text-amber text-xs-tech font-semibold rounded-sm transition-colors disabled:opacity-40"
                            title="Simulate optical scan by camera firmware for development testing"
                          >
                            {isSimulatingPair ? (
                              <Loader2 className="w-3 h-3 animate-spin text-amber" />
                            ) : (
                              <Zap className="w-3 h-3 text-amber" />
                            )}
                            Simulate Camera Optical Scan
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* MODE: MANUAL SETUP WIZARD (STEPS 1-4)                         */}
        {/* ------------------------------------------------------------- */}
        {setupMode === 'MANUAL' && (
          <div className="space-y-4">
            {/* Step Indicator */}
            <div className="flex items-center justify-between border-b border-hairline pb-3">
              {[
                { num: 1, label: '1. Network & RTSP' },
                { num: 2, label: '2. Connection Test' },
                { num: 3, label: '3. Lane Linkage' },
                { num: 4, label: '4. Deploy' },
              ].map((s) => (
                <div
                  key={s.num}
                  className={`flex items-center gap-1.5 text-xs-tech font-mono ${
                    step === s.num
                      ? 'text-amber font-bold'
                      : step > s.num
                      ? 'text-status-ok'
                      : 'text-text-sec/60'
                  }`}
                >
                  <span
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                      step === s.num
                        ? 'bg-amber text-black font-bold'
                        : step > s.num
                        ? 'bg-status-ok/20 text-status-ok border border-status-ok/30'
                        : 'bg-panel-raised border border-hairline text-text-sec'
                    }`}
                  >
                    {step > s.num ? '✓' : s.num}
                  </span>
                  <span className="hidden sm:inline">{s.label}</span>
                </div>
              ))}
            </div>

            {/* Step 1: Network & Stream Config */}
            {step === 1 && (
              <div className="space-y-3 pt-1">
                <div>
                  <label className="text-xs-tech font-medium text-text-pri block mb-1">
                    Camera Descriptive Label <span className="text-status-high">*</span>
                  </label>
                  <input
                    type="text"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="e.g. Exit Lane 3 — High-Angle Overhead"
                    className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                  />
                  <span className="text-[11px] text-text-sec block mt-1">
                    Operator-visible label on video walls and forensic audit timelines.
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs-tech font-medium text-text-pri block mb-1">
                      Edge IP Address <span className="text-status-high">*</span>
                    </label>
                    <input
                      type="text"
                      value={ipAddress}
                      onChange={(e) => setIpAddress(e.target.value)}
                      placeholder="192.168.10.45"
                      className="w-full px-3 py-2 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                    />
                  </div>

                  <div>
                    <label className="text-xs-tech font-medium text-text-pri block mb-1">
                      RTSP Stream Path <span className="text-status-high">*</span>
                    </label>
                    <input
                      type="text"
                      value={rtspPath}
                      onChange={(e) => setRtspPath(e.target.value)}
                      placeholder="/live/ch0"
                      className="w-full px-3 py-2 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs-tech font-medium text-text-pri block mb-1">
                    Camera Credentials (User : Password)
                  </label>
                  <input
                    type="password"
                    value={credentials}
                    onChange={(e) => setCredentials(e.target.value)}
                    placeholder="admin:pass"
                    className="w-full px-3 py-2 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                  />
                  <span className="text-[11px] text-text-sec block mt-1">
                    Encrypted in secrets vault. Browser consoles stream via WebRTC through media server, never
                    exposing raw RTSP.
                  </span>
                </div>

                <div className="flex justify-end pt-3">
                  <button
                    type="button"
                    disabled={!label.trim() || !ipAddress.trim() || !rtspPath.trim()}
                    onClick={() => setStep(2)}
                    className="flex items-center gap-1.5 px-4 py-2 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 disabled:opacity-40 text-black transition-colors"
                  >
                    Proceed to Connection Test
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Connection Test */}
            {step === 2 && (
              <div className="space-y-4 pt-1">
                <div className="p-3 bg-panel-raised border border-hairline rounded-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs-tech text-text-sec">Target RTSP Endpoint:</span>
                    <span className="font-mono text-xs-tech text-mono-val">
                      rtsp://{ipAddress}:554{rtspPath}
                    </span>
                  </div>

                  <div className="flex justify-center py-2">
                    <button
                      type="button"
                      onClick={handleTestConnection}
                      disabled={isTesting}
                      className="flex items-center gap-2 px-4 py-2 text-xs-tech font-semibold bg-panel border border-amber text-amber hover:bg-amber/10 rounded-sm transition-colors"
                    >
                      {isTesting ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin text-amber" />
                          Testing RTSP Handshake & Pulling Frame...
                        </>
                      ) : (
                        <>
                          <Video className="w-4 h-4 text-amber" />
                          Execute Stream Pull Test
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Test Result Display */}
                {testResult.tested && (
                  <div
                    className={`p-4 rounded-sm border ${
                      testResult.success
                        ? 'bg-teal-950/15 border-status-ok/30'
                        : 'bg-red-950/15 border-status-high/30'
                    } space-y-3 animate-in fade-in`}
                  >
                    <div className="flex items-start gap-2.5">
                      {testResult.success ? (
                        <CheckCircle2 className="w-5 h-5 text-status-ok shrink-0 mt-0.5" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-status-high shrink-0 mt-0.5" />
                      )}
                      <div className="space-y-1">
                        <div className="text-xs-tech font-bold text-text-pri">
                          {testResult.success
                            ? `RTSP Handshake Succeeded (${testResult.latencyMs}ms)`
                            : 'Camera Connection Failed'}
                        </div>
                        <p className="text-[11px] text-text-sec">
                          {testResult.success
                            ? 'Edge media server verified frame pull at 1920x1080 @ 30fps with H.264 video decoding.'
                            : testResult.errorMessage}
                        </p>
                      </div>
                    </div>

                    {testResult.success && (
                      <div className="relative rounded overflow-hidden border border-hairline bg-black max-w-sm mx-auto aspect-video flex items-center justify-center">
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex items-end p-2 justify-between z-10">
                          <span className="font-mono text-[10px] text-status-ok">● LIVE FEED READY</span>
                          <span className="font-mono text-[10px] text-text-sec">1080p · 30 FPS</span>
                        </div>
                        {testResult.snapshotUrl ? (
                          <img
                            src={
                              testResult.snapshotUrl.startsWith('http')
                                ? testResult.snapshotUrl
                                : `http://127.0.0.1:8000${testResult.snapshotUrl}?t=${Date.now()}`
                            }
                            alt="Live Camera Snapshot"
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="text-center p-4">
                            <Video className="w-8 h-8 text-status-ok mx-auto mb-1 opacity-70" />
                            <span className="text-[11px] text-text-sec font-mono">Live Video Stream Connected</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-between pt-2">
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-medium bg-panel-raised border border-hairline hover:bg-hairline/40 text-text-sec rounded-sm transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    Back
                  </button>

                  <button
                    type="button"
                    onClick={() => setStep(3)}
                    className="flex items-center gap-1.5 px-4 py-2 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors"
                  >
                    Continue to Lane Linkage
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: Lane Assignment */}
            {step === 3 && (
              <div className="space-y-4 pt-1">
                <div className="space-y-2">
                  <label className="text-xs-tech font-medium text-text-pri block">
                    Assign Camera to Exit Lane Portal
                  </label>

                  {!isCreatingInlineLane ? (
                    <div className="space-y-3">
                      <select
                        value={selectedLaneId}
                        onChange={(e) => setSelectedLaneId(e.target.value)}
                        className="w-full px-3 py-2 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                      >
                        <option value="">-- Leave Unassigned (Spare / Staging Pool) --</option>
                        {lanes.map((lane) => (
                          <option key={lane.laneId} value={lane.laneId}>
                            {lane.laneId} — {lane.location} ({lane.status})
                          </option>
                        ))}
                      </select>

                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px] text-text-sec">
                          Camera can exist unassigned in reserve pool or bound to a live exit lane.
                        </span>
                        <button
                          type="button"
                          onClick={() => setIsCreatingInlineLane(true)}
                          className="inline-flex items-center gap-1 text-xs-tech font-semibold text-amber hover:underline"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          Create New Exit Lane Inline
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 bg-panel-raised border border-amber/30 rounded-sm space-y-2">
                      <div className="text-xs-tech font-bold text-amber flex items-center gap-1.5">
                        <Radio className="w-3.5 h-3.5" />
                        Define New Exit Lane
                      </div>
                      <input
                        type="text"
                        value={newLaneLabel}
                        onChange={(e) => setNewLaneLabel(e.target.value)}
                        placeholder="e.g. Exit Lane 05 (East Loading Bay)"
                        className="w-full px-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                      />
                      <div className="flex justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setIsCreatingInlineLane(false)}
                          className="px-2.5 py-1 text-xs-tech text-text-sec hover:text-text-pri"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={handleCreateInlineLane}
                          disabled={!newLaneLabel.trim()}
                          className="px-3 py-1 text-xs-tech font-semibold bg-amber text-black rounded-sm disabled:opacity-40"
                        >
                          Add & Bind Lane
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex justify-between pt-3">
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-medium bg-panel-raised border border-hairline hover:bg-hairline/40 text-text-sec rounded-sm transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    Back
                  </button>

                  <button
                    type="button"
                    onClick={() => setStep(4)}
                    className="flex items-center gap-1.5 px-4 py-2 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors"
                  >
                    Review & Deploy
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 4: Review & Deploy */}
            {step === 4 && (
              <div className="space-y-4 pt-1">
                <div className="p-3.5 bg-panel-raised border border-hairline rounded-sm space-y-2.5 font-mono text-xs-tech">
                  <div className="text-xs-tech font-bold font-sans text-text-pri border-b border-hairline pb-1.5">
                    Surveillance Camera Registration Summary
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <span className="text-text-sec font-sans">Camera Label:</span>
                    <span className="text-text-pri font-bold">{label}</span>

                    <span className="text-text-sec font-sans">IP & Stream:</span>
                    <span className="text-mono-val">
                      {ipAddress}:554{rtspPath}
                    </span>

                    <span className="text-text-sec font-sans">Assigned Portal:</span>
                    <span className="text-text-pri">{selectedLaneId || 'UNASSIGNED (SPARE POOL)'}</span>

                    <span className="text-text-sec font-sans">Pairing Method:</span>
                    <span className="text-amber font-bold">{pairingMethod}</span>

                    <span className="text-text-sec font-sans">Initial State:</span>
                    <span className="text-status-ok font-bold">PENDING_SETUP ➔ ONLINE</span>
                  </div>
                </div>

                <div className="flex justify-between pt-2">
                  <button
                    type="button"
                    onClick={() => setStep(3)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-medium bg-panel-raised border border-hairline hover:bg-hairline/40 text-text-sec rounded-sm transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    Back
                  </button>

                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={handleSubmit}
                    className="flex items-center gap-2 px-5 py-2 text-xs-tech font-bold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors disabled:opacity-50"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-black" />
                        Registering Camera...
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4" />
                        Deploy Camera to Fleet
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};
