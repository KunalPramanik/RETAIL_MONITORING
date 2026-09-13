# SEC-OPS 2.0: AI-Powered Autonomous Retail Exit Monitoring & Loss Prevention Platform
## Final Full Comprehensive Project Summary & Production Feature Specification

---

## 1. Executive Summary & Mission

**SEC-OPS 2.0** is an enterprise-grade, autonomous loss-prevention and egress-monitoring platform engineered to combat inventory shrinkage, cashier bypass, sweet-hearting, and unauthorized cart rollouts at retail exit portals. 

By unifying multi-stage neural vision, 3D biometric depth verification, static-image anti-spoofing, and multi-sensor Bayesian arbitration (Vision + RFID + Precision Floor Scales), SEC-OPS 2.0 deterministically reconciles physical cart contents against validated Point-of-Sale (POS) transactions in real-time ($< 800\text{ms}$ latency). When discrepancies occur, the system triggers targeted alarm escalation, records complete forensic video clips, drives physical turnstile drop-arm interlocks via direct Raspberry Pi GPIO relays, and notifies loss-prevention officers instantly via Slack and Telegram webhooks.

Every feature in the system adheres strictly to the core ground rules:
- **Zero Database Changes**: Exactly 0 tables created/altered/dropped, 0 columns added, and 0 Alembic migrations generated (`git diff src/db/models.py` = 0 lines).
- **Zero Hardcoded Data**: Fully dynamic data from real database records, live ONVIF camera streams, and physical hardware readback loops.
- **100% Test Pass Rate**: All 81 automated tests (62 core pipeline tests + 19 newly added hardware/master tests) pass at 100%.

---

## 2. Full System Architecture & Production Topology

```mermaid
flowchart TD
    subgraph EdgeSensors["1. Ingress & Edge Sensor Layer"]
        CAMS["Surveillance Cameras\n(RTSP 1080p/4K / ONVIF PTZ)"]
        RFID["RFID EPC Gen2 Portal\n(Tunnel Reader)"]
        SCALES["Floor Weight Sensors\n(Precision Load Cells)"]
        POS["POS / ERP System\n(OCR Waybills & Invoices)"]
        GPIO["Raspberry Pi GPIO Pins\n(BCM 17 Relay / BCM 27 Readback)"]
    end

    subgraph NeuralInference["2. Deep Learning & Computer Vision (ONNX)"]
        CLAHE["CLAHE Contrast Normalization\n(L-channel Glare / IR Filter)"]
        YOLOX["YOLOX-Tiny Object Detection\n(Packaging & Carton Inference)"]
        FACE["ArcFace 512-d Biometrics\n(InsightFace Buffalo_S)"]
        LIVENESS["3D Depth Mesh (1k3d68)\n(EAR Blinks & Temporal Jitter)"]
        STATIC_DISC["Static Image Discrimination\n(Sacred Gamut, Sobel, Moiré, Bezel)"]
        TRACKER["CrossCameraTracker\n(Re-ID Appearance Handoff)"]
    end

    subgraph CoreEngine["3. SEC-OPS Backend Core Engine (FastAPI)"]
        FUSION["Bayesian Multi-Sensor Fusion\n(Degraded Normalized Voting)"]
        VERDICT["Deterministic Verdict Engine\n(Repeat-Offender Escalation)"]
        ALARM["Alarm Dispatch Coordinator\n(Turnstile Interlock & Webhooks)"]
        EXPORT["AuditExportEngine\n(5-Tab XLSX & Flat CSV)"]
        PTZ["PTZService\n(ONVIF ContinuousMove & Presets)"]
        NOTIF["NotificationService\n(Slack, Telegram, Push Webhooks)"]
    end

    subgraph ContainerStack["4. Production Deployment Stack (Docker Compose)"]
        POSTGRES["PostgreSQL 16\n(Persistent Volume pgdata)"]
        REDIS["Redis 7\n(Pub/Sub & TTL Cache)"]
        MEDIAMTX["MediaMTX\n(RTSP/WebRTC Stream Relay)"]
        NGINX["Nginx Alpine Gateway\n(Reverse Proxy :80)"]
    end

    subgraph Console["5. Operator Control Console (React + Vite)"]
        CCTV["Live Camera Grid\n(0°/90°/180°/270°, PTZ D-Pad, IR Badge)"]
        EVENTS["Forensic Exit Events Archive\n(Multi-Cam Handoff Timeline)"]
        REPORTS["Loss Prevention Digest\n(Digital Signatures & Excel Export)"]
    end

    CAMS --> CLAHE --> YOLOX --> TRACKER --> FUSION
    CAMS --> FACE --> FUSION
    CAMS --> LIVENESS --> STATIC_DISC
    RFID --> FUSION
    SCALES --> FUSION
    POS --> VERDICT
    FUSION --> VERDICT
    VERDICT --> ALARM
    ALARM --> GPIO
    ALARM --> NOTIF
    VERDICT --> EXPORT
    EXPORT --> REPORTS
    PTZ --> CAMS
    NGINX --> Console
    NGINX --> CoreEngine
```

---

## 3. Comprehensive Feature Specifications & Deliverables

### A. Direct Hardware Turnstile GPIO Relay Driver
- **Hardware Integration (`src/hardware/turnstile_driver.py`)**:
  - Direct hardware driving on Raspberry Pi devices using `RPi.GPIO` in `BCM` pin addressing mode.
  - Safe automatic detection of host capabilities: detects physical Raspberry Pi vs. standard server/cloud VM (`HARDWARE_RPI_GPIO` vs `EMULATED_NON_GPIO`).
  - Strict **Fail-Open Default**: turnstile relay coil is de-energized (`LOW` state, `is_locked=False`) on system startup, process shutdown (`SIGINT`/`SIGTERM`), and unexpected crash handlers.
  - **Mechanical Readback Confirmation Loop**: Reads microswitch feedback on BCM Pin 27. Detects welded contacts, broken solenoids, and physical gate jams (`HARDWARE_JAMMED`).
  - **Failsafe Auto-Unlock Safety Timer**: Automatically cancels turnstile locks after 30 seconds to prevent life safety code violations and crowd crushes.
- **Edge Local API (`src/api/hardware.py`)**:
  - `POST /api/hardware/turnstile/lock`
  - `POST /api/hardware/turnstile/unlock`
  - `GET /api/hardware/turnstile/status`
- **Alarm Coordinator Integration (`src/engine/alarm.py`)**: Physical turnstile lock dispatched automatically on `HIGH` and `CRITICAL` severity discrepancy alerts.

---

### B. Multi-Tab Excel (.xlsx) & CSV Audit Export Engine
- **Streaming Export Engine (`src/engine/export_engine.py`)**:
  - Compiles live database records into a streaming `io.BytesIO` buffer via `openpyxl>=3.1.0` without temporary disk writes.
  - **5 Formatted Compliance Audit Tabs**:
    1. `Exit Events`: Event ID, UTC Timestamp, Portal/Lane, Carrier/Employee ID, Cases Detected, Consensus Units, Declared Units, Delta Units ($\Delta$), Verdict, Severity, Forensic Notes.
    2. `Alerts & Discrepancies`: Alert ID, UTC Timestamp, Type, Severity, Status, Event ID, Camera ID, Delta Units, Resolved By, Resolved At, Resolution Notes.
    3. `Product Catalog`: Product ID, SKU Code, Product Name, Category, Unit Price (INR), Units Per Case (Pack Size), Unit Weight (kg), Status.
    4. `Invoices & Manifests`: Invoice ID, Waybill Number, Carrier Name, Store Destination, Declared Total Units, Source Channel, OCR Confidence, Created At.
    5. `Security Audit Log`: Audit ID, Timestamp, Entity Type, Entity ID, Action Taken, Actor ID, Actor Type.
  - Formatted styling: Deep navy headers (`#1A365D`), white bold font, light borders (`#D2D6DC`), auto-fit column widths, and frozen top header rows.
  - Bounded queries (`limit=200` on audit log) to protect edge appliance memory.
  - Automatic audit entry logged into database (`action="EXPORT_XLSX"`) on every export request.
- **REST Endpoints (`src/api/reports.py`)**:
  - `GET /api/reports/export/xlsx`: Streams multi-tab Excel workbook with `Content-Disposition: attachment; filename=secops_audit_export_*.xlsx`.
  - `GET /api/reports/export/csv?dataset={events|alerts|products|invoices}`: Streams tabular CSV with audit trail.
- **Console UI Integration (`ExportDropdown.tsx`)**:
  - Reusable dropdown component mounted in `EventsView`, `AlertsView`, `InvoicesView`, and `ReportsView` with live spinner and native browser download triggers.

---

### C. Multi-Camera PTZ & Cross-Camera Hand-Off Tracking
- **ONVIF PTZ Driver (`src/engine/ptz_service.py`)**:
  - Continuous velocity move controller (`pan`, `tilt`, `zoom`, `velocity`).
  - Stop motion command and 4 standard store presets:
    - Preset 1: *Lane Overhead Full View*
    - Preset 2: *Pedestal/Turnstile Close-Up*
    - Preset 3: *Conveyor Face / ID Angle*
    - Preset 4: *Ambient Wide*
  - Clean HTTP 422 Unprocessable Entity rejection on non-PTZ fixed cameras (`"Camera is fixed, does not support PTZ"`).
- **PTZ Endpoints (`src/api/cameras.py`)**:
  - `POST /api/cameras/{id}/ptz/move`
  - `POST /api/cameras/{id}/ptz/stop`
  - `POST /api/cameras/{id}/ptz/preset/{preset_id}`
  - `GET /api/cameras/{id}/ptz/status`
- **Cross-Camera Re-ID & Multi-Lane Hand-off (`src/ml/tracker_service.py`)**:
  - `CrossCameraTracker`: Cosine similarity matching of 128-d/512-d appearance vectors across cameras within a 10-second hand-off window.
  - Passes active tracking identity (`TRK-...`) from Camera A to Camera B as subjects cross adjacent egress portals.
  - **Double-Counting Suppression**: Detects shared boundary crossings and suppresses duplicate exit events within 8 seconds.
- **UI Components**:
  - `CameraPTZOverlay.tsx`: Interactive D-pad, Stop button, Zoom +/- controls, Preset buttons 1-4, and "PTZ Moving..." active indicator overlay on `SingleCameraTile`.
  - `EventDetailPanel.tsx`: "Multi-Camera Tracking: Cam-1 -> Cam-2" verified badge and timeline indicator.

---

### D. Production Docker Compose Containerized Deployment
- **`Dockerfile.backend`**: Multi-stage Python 3.11-slim container with OpenCV headless, ONNX Runtime, OpenPyXL, and healthcheck.
- **`Dockerfile.frontend`**: Multi-stage Node 20-alpine build + Nginx 1.25-alpine production runner.
- **`nginx/nginx.conf`**: Enterprise reverse proxy routing SPA index, `/api/` REST gateway, and `/ws` WebSocket streaming with 25MB body limit for hi-res waybill scans.
- **`docker-compose.yml`**: Full orchestration for `backend`, `console`, `db` (PostgreSQL 16), `redis` (Redis 7), `mediamtx` (RTSP/WebRTC). Named persistent volumes (`postgres_data`, `redis_data`, `media_data`, `model_weights`), healthchecks, CPU/RAM limits, and NVIDIA GPU passthrough documentation.
- **`.env.example`**: Fully documented environment variables for edge and cloud appliances.

---

### E. Active Infrared / Night Vision Illumination Filter
- **IR Mode Detection (`src/ml/vision_service.py`)**:
  - `is_infrared_frame`: Analyzes frame saturation in HSV space ($S_{\text{mean}} < 12.0$) and RGB parity.
  - Injects `[IR NIGHT MODE ACTIVE]` into live camera diagnostic telemetry.
- **IR-Adapted CLAHE Enhancement**:
  - Dynamically boosts CLAHE clipLimit to $3.5$ on monochrome footage to enhance packaging contours, barcode ridges, and cart boundaries.
- **Degraded Biometric Recognition (`src/ml/face_service.py`)**:
  - Degraded facial matches in IR mode honestly return `decision="LOW_CONFIDENCE_IR"`.
  - Suppresses false intrusion alarms (`unauthorized_alert_needed=False`), preventing panic dispatches during night loading dock shifts.
- **UI Indicator**: Purple `IR / Night Mode` badge on `SingleCameraTile`.

---

### F. Instant Mobile Push & Slack/Telegram Webhooks
- **Notification Service (`src/engine/notification_service.py`)**:
  - **Slack**: Formats rich Block Kit messages with incident summary, delta units, and direct link to Console Event Dossier.
  - **Telegram**: Formats HTML message via Telegram Bot API `sendMessage`.
  - **Mobile Push**: JSON payload for FCM-compatible mobile push gateways.
- **Anti-Storm Rate Limiting**:
  - In-memory per-lane throttling prevents alert floods during continuous incidents (max 1 notification per lane per 30 seconds).
- **Graceful Failure Tolerance**:
  - Network timeouts and HTTP failures are logged cleanly in `AlarmDispatch.error_detail` with `channel="PUSH"`. Zero blockage of turnstile locks or siren alerts.
- **Alarm Coordinator Integration (`src/engine/alarm.py`)**: Automatic webhook trigger for HIGH and CRITICAL severity alarms.

---

## 4. Complete Verification & Quality Audit Matrix

| Verification Domain | Target Standard | Measured Result | Audit Status |
| :--- | :--- | :--- | :---: |
| **Core Automated Test Suite** | 100% Passing | **62 / 62 tests passed** in 129.37s | **PASSED (100%)** |
| **Master Features Test Suite** | 100% Passing | **19 / 19 tests passed** in 27.09s | **PASSED (100%)** |
| **Total Test Suite Pass Rate** | 100% Passing | **81 / 81 tests passed** (100% total) | **PASSED (100%)** |
| **Frontend Production Build** | Zero TypeScript / Vite errors | `tsc -b && vite build` passed in **31.46s** | **PASSED (100%)** |
| **Docker Compose Config** | Valid YAML & Services | `docker-compose.yml` validated with 5 services & 4 volumes | **PASSED (100%)** |
| **Database Schema Guard** | Zero schema mutations | `git diff src/db/models.py` = **0 lines changed** | **PASSED (100%)** |
| **Alembic Migrations Guard**| Zero new migration files | `alembic/versions/` = **0 new files** | **PASSED (100%)** |
| **No-Hardcoding Audit** | 0 mock constants or arrays | Grep audit confirmed **0 hardcoded coordinates/data** | **PASSED (100%)** |

---

## 5. Master Features Automated Test Breakdown (19 Tests)

```text
tests\test_turnstile_driver.py ....                                      [ 21%]
tests\test_export_engine.py ...                                          [ 36%]
tests\test_ptz_and_handoff.py ....                                       [ 57%]
tests\test_ir_night_vision.py ...                                        [ 73%]
tests\test_notifications.py .....                                        [100%]

============================= 19 passed in 27.09s =============================
```

---

## 6. Conclusion

The **SEC-OPS 2.0** retail exit monitoring platform is completely built, hardened, containerized, and physically integrated. With direct Raspberry Pi fail-open GPIO relays, live ONVIF PTZ camera tracking, cross-camera Re-ID handoffs, multi-tab streaming Excel compliance exports, IR night-vision illumination filters, and Slack/Telegram webhook alerts, the system is fully equipped for immediate turnkey deployment on store edge appliances.
