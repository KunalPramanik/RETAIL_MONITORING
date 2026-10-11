# SEC-OPS V8 — Deployment & Operator Runbook

**Document ID**: `SEC-OPS-V8-DOC-10`  
**Date**: October 11, 2026  
**Status**: **APPROVED RUNBOOK**  

---

## 1. System Requirements & Prerequisites

### 1.1 Edge Server Node (Per Retail Facility)
- **CPU**: Intel Xeon / Core i7 (8+ cores, 3.2 GHz+) or AMD Ryzen 7
- **GPU**: NVIDIA RTX 3060 (8GB VRAM) or higher (CUDA 12.x / TensorRT enabled)
- **RAM**: 32 GB DDR4/DDR5
- **Storage**: 500 GB NVMe SSD (for fast local frame and snapshot caching)
- **OS**: Windows 11 Enterprise / Ubuntu 22.04 LTS

### 1.2 Central Cloud Control Plane (Multi-Tenant Hub)
- **Runtime**: Docker Engine 24+ & Docker Compose v2
- **Database**: PostgreSQL 15+ with pg_stat_statements enabled
- **Cache**: Redis 7.x cluster

---

## 2. Cold-Start Installation & Service Initialization

### Step 1: Clone Repository & Configure Environment
```bash
git clone <repo-url> secops-v8
cd secops-v8
cp .env.example .env
```
Ensure mandatory environment variables are set:
```ini
ENVIRONMENT=production
JWT_SECRET_KEY=<generate-strong-64-char-secret>
DATABASE_URL=sqlite+aiosqlite:///retail_secops.db
SECOPS_BIOMETRIC_ENABLED=false
```

### Step 2: Database Migration & Schema Bootstrap
```bash
cd retail-exit-backend
.\.venv\Scripts\activate
alembic upgrade head
```

### Step 3: Launch Services
1. **Backend API & Ingestion Service**:
   ```bash
   python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
   ```
2. **Next.js Frontend Dashboard**:
   ```bash
   cd retail-exit-nextjs
   npm run start -- -p 3000
   ```

---

## 3. Onboarding Runbook: First-Time Store Deployment

```
[ Step 1: Super Admin Login ]
Access http://<server-ip>:3000/platform
Login with Platform Super Admin credentials and provision new Tenant Company.

[ Step 2: Tenant Company Admin Login ]
Access http://<server-ip>:3000/login
Login as Tenant Admin.

[ Step 3: Camera Fleet Onboarding ]
Navigate to /settings/cameras
Add physical RTSP stream (e.g. rtsp://admin:pass@192.168.1.100:554/ch0) or USB webcam (device 0).
Click "Test Connection" -> Verify live preview stream.
Click "Suggest Gate Line" -> Adjust with NUDGE UP/DOWN -> Click "ACCEPT".

[ Step 4: Catalog & Opening Census ]
Navigate to /products -> Import or register store SKUs.
Navigate to /inventory -> Conduct Opening Stock Scan.
Review AI census proposals -> Click "YES — ACCEPT" to freeze baseline stock.

[ Step 5: Live Operation ]
Monitor / (Main Dashboard) for real-time detections, exit traversals, and ledger balances.
```

