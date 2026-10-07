# SEC-OPS 2.0 — System Architecture

## 1. Overview
SEC-OPS 2.0 is an enterprise-grade retail exit surveillance and inventory reconciliation platform. It combines edge computer vision, real-time sensor fusion, industrial hardware interlocks, and low-latency WebSocket streaming to verify retail exit transactions, eliminate inventory shrinkage, and ensure store security without impeding legitimate customer flow.

---

## 2. High-Level Architecture

```
+---------------------------------------------------------------------------------+
|                                Frontend (Next.js 16)                             |
|  - Real-Time CCTV Grids     - Incident Queue (/alerts)    - Audit Ledger        |
|  - Biometric Directory      - Anomaly Thresholds          - SKU Catalog         |
+---------------------------------------+-----------------------------------------+
                                        |  REST APIs / WebSockets (/ws/live)
                                        v
+---------------------------------------------------------------------------------+
|                             API Gateway / Reverse Proxy (Nginx)                 |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                           FastAPI Backend Application                            |
|                                                                                 |
|  [REST API Routers]                                                             |
|  - /cameras      - /alerts      - /events      - /invoices      - /products     |
|  - /auth         - /employees   - /kpis        - /reports       - /lanes        |
|                                                                                 |
|  [Real-Time & Middleware Engine]                                                |
|  - Correlation ID Tracing Middleware (X-Correlation-ID)                          |
|  - Sliding-Window Rate Limiter (Redis + In-Memory Fallback)                     |
|  - WebSocket Hub (Redis Pub/Sub Cluster Fan-Out, Keepalive Heartbeat)           |
|                                                                                 |
|  [Computer Vision & Inference Pipeline]                                         |
|  - Camera Ingestion Worker (Multi-Port Auto-Negotiation, RTSP / HTTP)           |
|  - Motion Detector (Gaussian blur, frame difference, debounce throttling)       |
|  - Inference Circuit Breaker (CLOSED / OPEN / HALF-OPEN with timeout watchdog)  |
|  - Object Detection (YOLOX ONNX runtime)                                        |
|  - Multi-Object Tracking (SimpleByteTrack with Hungarian association)           |
|  - Biometric Facial Recognition (SCRFD detector + ArcFace embeddings)          |
|  - Waybill & Document OCR (RapidOCR)                                            |
|                                                                                 |
|  [Industrial Automation & Consensus Engine]                                     |
|  - Tri-Sensor Fusion Engine (Vision + RFID + Weight scale Bayesian scoring)     |
|  - Verdict Engine (Configurable severity bands, unit discrepancy matching)      |
|  - Industrial Turnstile Interlock (Modbus-TCP relay driver)                     |
|  - Alarm Coordinator (Siren, Strobe, TTS, Mobile Push Dispatch)                 |
+-----------------------------------+---------------------------------------------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v                               v
    +-------------------------------+   +-------------------------------+
    |     PostgreSQL / SQLite       |   |       Redis Cache & Pub/Sub   |
    |  - Persistent Event Ledger    |   |  - Cluster Broadcast Fan-Out  |
    |  - Camera Registry & Tokens   |   |  - Sliding-Window Rate Limits |
    |  - Audit Log Trail            |   |  - Ephemeral Telemetry Cache  |
    +-------------------------------+   +-------------------------------+
```

---

## 3. Core Subsystems

### 3.1 Camera Fleet Ingestion & Network Probing
- **Camera Worker (`src/engine/camera_worker.py`):** Orchestrates frame capture, motion checks, and ML inference. Runs isolated database transactions per camera to prevent cross-stream contamination.
- **Motion Detector (`src/engine/motion_detector.py`):** Compares successive frame buffers using Gaussian blurring, absolute differencing, and dynamic debounce windows to trigger inference only on actual activity.
- **Camera Prober (`src/api/camera_prober.py`):** Scans camera endpoints, auto-negotiates ports (`554`, `8080`, `4747`, `80`, `8554`), tests RTSP/HTTP handshakes, and diagnoses connection states.
- **Standby Preview Utility (`src/api/camera_stream_utils.py`):** Renders tactical HUD standby frames when physical feeds are unassigned or offline.

### 3.2 Resilience & Fault Tolerance
- **Inference Circuit Breaker (`src/engine/circuit_breaker.py`):** A 3-state circuit breaker wrapping heavy vision inference calls. If consecutive inference timeouts or model failures occur, the breaker transitions to `OPEN` and prevents pipeline stalls, transitioning cameras to `DEGRADED` status while alerting the control room.
- **Timeout Watchdogs:** All computer vision and external socket requests run under strict asynchronous timeouts.

### 3.3 Multi-Sensor Fusion & Verdict Engine
- **Sensor Fusion Engine (`src/engine/sensor_fusion.py`):** Fuses optical detection with RFID tag readers and floor scale telemetry. If an optical channel is occluded, confidence degrades gracefully without fabricating data.
- **Verdict Engine (`src/engine/verdict.py`):** Compares physical unit counts against point-of-sale or waybill manifests. Flags discrepancies as `MISMATCH` with severity ratings (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).

### 3.4 Real-Time WebSockets & Distributed Cache
- **WebSocket Hub (`src/realtime/hub.py`):** Connects browser dashboards with the live edge pipeline. Features parallel client broadcast, dead connection pruning, ping/pong heartbeats, and Redis Pub/Sub cluster distribution.
- **Cache Service (`src/cache.py`):** High-performance caching layer supporting both Redis and in-memory storage. Uses non-blocking cursor scans (`SCAN` + `UNLINK`) to eliminate database stalls during key invalidation.

