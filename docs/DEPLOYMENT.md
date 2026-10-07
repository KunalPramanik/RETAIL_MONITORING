# SEC-OPS 2.0 — Production Deployment Guide

## 1. Prerequisites
- **Docker & Docker Compose:** Docker Engine 24.0+ and Docker Compose v2.20+
- **Hardware Recommendations:**
  - **CPU:** 8+ Physical Cores (x86_64 or ARM64)
  - **RAM:** Minimum 16 GB (32 GB recommended for multi-camera streams)
  - **GPU (Optional):** NVIDIA GPU with CUDA 12+ for accelerated ONNX Runtime inference
  - **Network:** Gigabit Ethernet (dedicated VLAN for IP camera RTSP streams recommended)

---

## 2. Environment Configuration

Copy `.env.example` to `.env` in `retail-exit-backend/`:
```bash
cp retail-exit-backend/.env.example retail-exit-backend/.env
```

Ensure the following mandatory production variables are configured:
```ini
ENVIRONMENT=production
SECRET_KEY=<generate-secure-random-64-character-string>
JWT_SECRET=<generate-secure-random-64-character-string>
MOBILE_HMAC_SECRET=<generate-secure-random-32-character-string>

DATABASE_URL=postgresql+asyncpg://secops_user:secops_password@postgres:5432/retail_secops
REDIS_URL=redis://redis:6379/0

CORS_ORIGINS=["https://dashboard.yourstore.com"]
```

---

## 3. Quick Deployment with Docker Compose

Deploy the complete multi-service stack with a single command:
```bash
docker compose up -d --build
```

### Services Started:
| Service | Container Name | Port | Description |
| :--- | :--- | :--- | :--- |
| **Backend** | `secops-backend` | `8000` | FastAPI core application, CV inference & WebSocket hub |
| **Frontend** | `secops-frontend` | `3000` | Next.js 16 management dashboard |
| **Database** | `secops-postgres` | `5432` | PostgreSQL persistent ledger |
| **Cache** | `secops-redis` | `6379` | Redis distributed cache & Pub/Sub broker |
| **Proxy** | `secops-nginx` | `80, 443`| SSL termination and reverse proxy |

---

## 4. Database Migrations

Apply Alembic migrations to initialize schema and tables:
```bash
docker compose exec backend alembic upgrade head
```

---

## 5. Health Checks & Observability

Verify system readiness using built-in telemetry endpoints:
- **Service Health:** `GET http://localhost:8000/health`
- **Prometheus Metrics:** `GET http://localhost:8000/metrics`
- **WebSocket Gateway:** `ws://localhost:8000/ws/live`

