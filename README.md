# SEC-OPS 2.0: Smart Retail Exit Monitoring & Inventory Intelligence Platform

An industrial-grade physical-security and loss-prevention control room platform for high-throughput retail environments. Combines real-time computer vision inference, multi-modal sensor fusion (OpenCV, RFID simulation, load cells, biometric face matching), deterministic verdict arbitration, camera fleet management with **bidirectional QR-code auto-pairing**, and live WebSocket telemetry.

---

## 🏛️ System Architecture

```
                                  +---------------------------------------+
                                  |     Edge Cameras / IP Webcams         |
                                  |  (RTSP / HTTP MJPEG / ONVIF Streams)  |
                                  +-------------------+-------------------+
                                                      |
                                                      v
+------------------------+        +---------------------------------------+
|  Hard-Copy Bills /     |  OCR   |   Deep-Learning Ingestion Pipeline    |
|  Manifest Ingestion    +------->|   - Megvii YOLOX (Apache 2.0)         |
+------------------------+        |   - InsightFace ArcFace (512-d)       |
                                  |   - PaddleOCR (DBNet + CRNN)          |
                                  |   - Multi-Modal Sensor Fusion         |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |       Verdict & Arbitration Engine    |
                                  |   - Unit & % Tolerance Thresholds     |
                                  |   - Repeat Offender Escalation        |
                                  |   - Auto-Turnstile Locking & Dispatch |
                                  +-------------------+-------------------+
                                                      |
                                                      v
+------------------------+        +---------------------------------------+
|  SQLite / PostgreSQL   |<-------+    FastAPI Async Backend (:8000)      |
|  SQLAlchemy 2.0 Engine |        |    - REST API + WebSocket Hub         |
+------------------------+        +-------------------+-------------------+
                                                      |
                                                      | WebSocket / REST
                                                      v
                                  +---------------------------------------+
                                  |    React 18 + Vite Frontend (:5173)   |
                                  |    - Live CCTV Surveillance Feeds     |
                                  |    - Audit Trails & Alert Resolution  |
                                  |    - Two-Way QR Camera Auto-Pairing   |
                                  +---------------------------------------+
```

---

## 🚀 Key Features

1. **Two-Directional QR-Code Camera Auto-Pairing**:
   - **Direction 1 (Camera $\to$ Console)**: Operator scans camera's QR code using device webcam or pastes stream URL. Backend executes live network verification and provisions camera.
   - **Direction 2 (Console $\to$ Camera)**: Console generates a high-contrast SVG pairing QR code tied to a single-use cryptographic token (10-min TTL). Camera scans screen and self-provisions over `POST /api/cameras/pair`.
2. **Multi-Modal Sensor Fusion Engine**:
   - Synthesizes computer vision box counts, RFID tag counts, floor scale weight readings, and face recognition into a unified consensus.
   - Robust to sensor failure, RFID blind spots, and single-channel attenuation.
3. **Deterministic Verdict Rules & Repeat-Offender Escalation**:
   - Clear classification: `PASS`, `MISMATCH_LOW`, `MISMATCH_MED`, `MISMATCH_HIGH`, `CRITICAL`.
   - Dynamic threshold configuration (unit tolerance, percentage tolerance, temporal repeat offender lookback windows).
4. **Zero-Mock, Pure Dynamic Data**:
   - Zero hardcoded fallback lists or mock records. Empty states provide clear operator calls to action.
5. **Industrial Control Room UI**:
   - Dark theme default, teal `--status-ok` palette, IBM Plex Mono technical typography, responsive grid, real-time alert triage drawer, and printable PDF audit manifests.

---

## 📂 Project Structure

```
.
├── retail-exit-backend/        # FastAPI async backend service
│   ├── src/
│   │   ├── api/                # REST endpoints (cameras, events, alerts, invoices, etc.)
│   │   ├── db/                 # Models, sessions, migrations & baseline init
│   │   ├── engine/             # Camera worker, fusion engine & verdict logic
│   │   ├── ml/                 # Megvii YOLOX, InsightFace ArcFace & PaddleOCR
│   │   ├── schemas/            # Pydantic schemas
│   │   └── main.py             # FastAPI entrypoint, lifespan & static mounts
│   ├── tests/                  # 49 unit, integration, and deep-learning ML tests
│   ├── snapshots/              # Evidence snapshots and camera previews
│   └── uploads/                # Hard-copy invoice uploads
│
├── retail-exit-console/        # React + TypeScript + Vite frontend
│   ├── src/
│   │   ├── api/                # Typed REST client & WebSocket hooks
│   │   ├── components/         # Modular UI components (cameras, events, alerts, etc.)
│   │   ├── context/            # Global real-time app data provider
│   │   ├── views/              # Views (Dashboard, Cameras, Events, Invoices, Settings)
│   │   └── types/              # TypeScript interfaces
│   ├── package.json
│   └── vite.config.ts
│
├── .gitignore
├── pyrightconfig.json
└── README.md
```

---

## ⚡ Quick Start Guide

### Prerequisites
- **Python**: 3.10+ (Python 3.11 recommended)
- **Node.js**: 18+ (Node 20+ recommended)
- **Git**

---

### 1. Backend Setup (`retail-exit-backend`)

```powershell
cd retail-exit-backend

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
# or: source .venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Start backend service
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be available at:
- **API**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### 2. Frontend Console Setup (`retail-exit-console`)

```powershell
cd retail-exit-console

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Open your browser at [http://localhost:5173](http://localhost:5173).

---

### 3. Running Automated Tests

```powershell
cd retail-exit-backend
python -m pytest -v
```

All 49 unit and integration tests run in isolated in-memory SQLite and verify all fusion, verdict, OCR, and computer vision pipelines.

---

## 🔒 Security & Privacy

- Edge camera streams and tokens are scoped strictly to specific retail lanes.
- Cryptographic pairing tokens expire in 10 minutes and are single-use.
- Biometric face embeddings are evaluated dynamically in-memory without persistent external tracking.

