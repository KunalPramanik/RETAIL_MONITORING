# Smart Retail Exit Monitoring & Inventory Intelligence — Backend & ML Platform (SEC-OPS 2.0)

Production-grade backend system of record, multi-modal sensor fusion pipeline, camera fleet management, and real-time inference platform for retail loss prevention and exit-lane intelligence.

---

## 1. System Overview

```
 Edge Sensors (per lane)              Ingestion & Fusion Services           Serving & Storage
 ┌──────────────────────┐             ┌────────────────────────┐            ┌────────────────────────┐
 │ Camera Frame Stream  │───batch───▶ │ Vision Inference Svc   │──┐         │ Database (Postgres)    │
 │ (RTSP Media Server)  │             │ (YOLOX Apache 2.0)     │  │         │ 18 Relational Tables   │
 │ RFID Antenna Reads   │───tags────▶ │ RFID Analytics Svc     │  ├─fuse──▶ │ Append-Only Audit Log  │
 │ Floor Scale (kg)     │───delta───▶ │ Weight Fusion Svc      │  │         │ Camera Fleet Registry  │
 │ Turnstile Interlock  │◀──lock────  │                        │──┘         └───────────┬────────────┘
 └──────────────────────┘             └────────────────────────┘                        │
                                                                                        ▼
 ┌──────────────────────┐             ┌────────────────────────┐            ┌────────────────────────┐
 │ OCR Waybill Manifest │───scan────▶ │ OCR Ingestion Svc      │───────────▶│ Verdict Engine         │
 │ (TrOCR / PaddleOCR)  │             │ (Structured parsing)   │            │ (Rules & Thresholds)   │
 └──────────────────────┘             └────────────────────────┘            └───────────┬────────────┘
                                                                                        │
 ┌──────────────────────┐             ┌────────────────────────┐                        ▼
 │ Face Recognition     │───1:N─────▶ │ InsightFace / ArcFace  │───────────▶┌────────────────────────┐
 │ (512-d embeddings)   │             │ (Active roster match)  │            │ Alarm Coordinator      │
 └──────────────────────┘             └────────────────────────┘            │ (Siren, Lock, PUSH)    │
                                                                            └───────────┬────────────┘
                                                                                        │
                                                                                        ▼
                                                                            ┌────────────────────────┐
                                                                            │ WebSocket Gateway      │──▶ Control Console
                                                                            │ (/ws/live)             │    (Frontend)
                                                                            └────────────────────────┘
```

---

## 2. Machine Learning & Deep Learning Pipeline

### E.0 Open-Source Model Selection & Licensing Matrix

All 5 models in this pipeline are free to use, fine-tune, and deploy commercially with zero per-inference cost and no closed-source licensing conflicts.

> [!IMPORTANT]
> **Commercial Licensing Directive**: Explicitly avoid **YOLOv8 / YOLOv11 (Ultralytics)** — they are licensed under **AGPL-3.0**, which requires open-sourcing the entire proprietary codebase if deployed without purchasing an expensive commercial license. **YOLOX (Megvii)** is used instead, providing equivalent detection accuracy under the permissive **Apache 2.0** license.

| Pipeline Job | Selected Model | Source Repository | License Note |
|---|---|---|---|
| **Vision: Case / Unit Detection** | **YOLOX** (`yolox-x-retail-pack`) | `github.com/Megvii-BaseDetection/YOLOX` | **Apache 2.0** — Fully open, unrestricted commercial deployment |
| **Multi-Frame Object Tracking** | **ByteTrack** | Native YOLOX tracker pairing | **MIT** — Permissive |
| **OCR: Invoice & Bill Parsing** | **PaddleOCR** / **TrOCR** | `microsoft/trocr-base-printed` | **Apache 2.0 / MIT** |
| **Invoice Layout Understanding** | **LayoutLMv3** (Optional) | `microsoft/layoutlmv3-base` | **MIT** |
| **Face Biometrics: Carrier Match** | **InsightFace / ArcFace** | `github.com/deepinsight/insightface` | **MIT / Apache 2.0** |

All models are used **pretrained first, then fine-tuned** on store-specific footage and employee enrollment photos.

---

### E.1 Vision Detection & Case-to-Unit Counting (`src/ml/vision_service.py`)
- **Model**: **YOLOX** (Megvii Apache 2.0) paired with **ByteTrack** (MIT).
- **Target Classes**: `case_full`, `case_open`, `single_unit`, `person`.
- **Pack Size Resolution**: Multiplies detected cases by `product.pack_size` (e.g. 3 boxes of soda $\times$ 24 = 72 units) plus single items.
- **Confidence Gating**: Detections below floor threshold (0.70) are logged for model-quality review without falsely inflating the count.

### E.2 Multi-Sensor Consensus Fusion (`src/engine/fusion.py`)
Consensus formula combining measurements across **Vision AI** ($w=0.50$), **RFID Gate** ($w=0.30$), and **Floor Scale** ($w=0.20$):
$$\text{Consensus Units} = \text{round}\left(\frac{\sum v_i \cdot w_i \cdot \text{conf}_i}{\sum w_i \cdot \text{conf}_i}\right)$$
- **Majority Override**: When 2 out of 3 channels (e.g. Vision and Scale) agree exactly with high confidence, the consensus adopts the 2-channel majority and flags the dissenting channel (e.g. RFID RF shielding / attenuation).

### E.3 OCR Invoice Extraction (`src/ml/ocr_service.py`)
- **Model**: **PaddleOCR** / **TrOCR** for tabular manifest layouts.
- **Pipeline**: Scanned image/PDF $\rightarrow$ bounding box text recognition $\rightarrow$ structured JSON line items $\rightarrow$ fuzzy SKU match $\rightarrow$ `declared_units`.

### E.4 Face Recognition & Employee Authentication (`src/ml/face_service.py`)
- **Model**: **InsightFace / ArcFace** 512-dimensional metric embeddings.
- **Cosine Similarity Match**: 1:N matching against active employee vectors stored in `pgvector`.
- **Biometric Security**: Probe vectors below 0.65 similarity trigger `UNAUTHORIZED_ACCESS` flags.

### E.5 Deterministic Verdict Engine (`src/engine/verdict.py`)
- **Pure Rule Evaluation**: Consumes `(consensusUnits, declaredUnits, thresholdConfig, employeeHistory)`. Models never emit verdicts directly.
- **Tolerance Math**: `PASS` when $|\Delta| \le \max(\text{unitTolerance}, \text{pctTolerance} \times \text{declaredUnits})$.
- **Severity Bands**: `NONE`, `LOW`, `MEDIUM`, `HIGH`.
- **Repeat Offender Escalation**: Automatically bumps severity by $+1$ band if carrier has $\ge 3$ mismatches in a rolling 30-day window.

---

## 3. Camera Fleet Management Pipeline

- **Decoupled Architecture**: Cameras exist in a spare/staging pool or bind to exit lanes without restarting inference services.
- **Continuous Heartbeat Monitoring**: Background task scans cameras every 10s. If heartbeat ceases for $> 60$s (`camera_offline_alert_after_sec`), status flips to `OFFLINE` and a `HIGH`-severity `CAMERA_OFFLINE` alert is broadcast via WebSocket.
- **Soft-Deletion**: `DELETE /api/cameras/{id}` sets `removed_at` and unbinds the lane, preserving historical detection records for forensic audits.

---

## 4. API Surface

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/kpis/live` | Live telemetry KPI strip (throughput, open alerts, consensus rate, active lanes, cameras online/total) |
| `GET` | `/api/events` | Historical exit events with multi-facet filters & pagination |
| `GET` | `/api/events/{id}` | Full forensic detail with raw sensor artifacts and face match |
| `GET` | `/api/alerts` | Active incident queue prioritized by severity |
| `POST` | `/api/alerts/{id}/acknowledge` | Acknowledges alert and writes audit log |
| `POST` | `/api/alerts/{id}/resolve` | Resolves alert with mandatory loss-prevention notes |
| `GET/POST` | `/api/products` | CRUD catalog with case pack sizes |
| `GET/POST` | `/api/employees` | Badge registry with 30-day mismatch count |
| `GET` | `/api/employees/{id}/history` | Individual personnel exit traversal audit trail |
| `GET` | `/api/invoices` | Scanned carrier manifests and waybills |
| `GET` | `/api/reports/daily` | Daily loss prevention operations digest |
| `GET` | `/api/reports/daily/{id}/pdf` | Official downloadable PDF audit report |
| `GET/PUT`| `/api/settings/thresholds` | Threshold configuration management |
| `GET` | `/api/cameras` | List camera fleet with status and lane filters |
| `POST`| `/api/cameras` | Register camera in `PENDING_SETUP` state |
| `POST`| `/api/cameras/{id}/test-connection` | RTSP stream pull test with actionable diagnostics |
| `PUT` | `/api/cameras/{id}` | Rebind lane or update resolution/FPS |
| `DELETE`| `/api/cameras/{id}` | Soft-delete camera and unbind lane |
| `POST`| `/api/cameras/{id}/heartbeat` | Ingest edge media server telemetry |
| `GET/POST`| `/api/lanes` | Lane hardware registry and inline lane creation |
| `POST`| `/api/lanes/{id}/turnstile/toggle` | Electromagnetic turnstile lock command |
| `POST`| `/api/ingest/event` | Edge sensor pipeline ingestion endpoint |
| `POST`| `/api/ingest/scenario` | Interactive edge scenario simulator |
| `WS`  | `/ws/live` | Real-time typed WebSocket event stream |
| `GET` | `/metrics` | Prometheus-compatible telemetry metrics |
| `GET` | `/health` | Application health and database status |

---

## 5. Running the Platform & Automated Tests

```bash
# 1. Navigate to backend directory
cd C:\Users\DELL\.gemini\antigravity\scratch\retail-exit-backend

# 2. Run automated test suite (33 tests)
uv run pytest -v

# 3. Start the FastAPI application
uv run uvicorn src.main:app --port 8000 --host 127.0.0.1
```

- **Interactive API Docs**: `http://127.0.0.1:8000/docs`
- **Prometheus Metrics**: `http://127.0.0.1:8000/metrics`
- **Live WebSocket Stream**: `ws://127.0.0.1:8000/ws/live`

