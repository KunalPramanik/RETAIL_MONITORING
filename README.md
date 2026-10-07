# SEC-OPS 2.0: Retail Exit Monitoring Platform

An enterprise-grade, AI-powered video analytics and loss prevention platform designed for high-throughput retail exit lanes.

## Enterprise Architecture

The system has been built for 100% production readiness:
* **Frontend:** Secure, server-rendered Next.js (App Router) dashboard with real-time WebSocket telemetry.
* **Database:** Fully concurrent PostgreSQL database managed by Alembic migrations with connection pooling.
* **Security:** Strict JWT Authentication and Role-Based Access Control (RBAC) with bcrypt password hashing and sliding-window rate limiting.
* **Computer Vision & Tracking:** ByteTrack (Hungarian matching + IoU) with multi-sensor fusion, eliminating occlusion and double-counting defects.
* **Infrastructure:** 100% dynamic environment configuration (`.env` driven) ready for deployment via Docker Compose and Nginx reverse proxy.

---

## Getting Started

The platform is decoupled into a FastAPI backend and a Next.js frontend, orchestrated via Docker. Follow these steps to launch the stack.

### Prerequisites
* Docker & Docker Compose
* Node.js (v18+)
* Python (3.10+) with `uv` package manager (`pip install uv`)

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/KunalPramanik/RETAIL_MONITORING.git
cd RETAIL_MONITORING

# Copy the dynamic environment template
cp .env.example .env
```
*Note: In production, edit the `.env` file to set your own secure secrets (e.g. `JWT_SECRET_KEY`, database credentials).*

### Step 2: Launch Infrastructure (PostgreSQL & Redis)
The backend relies on PostgreSQL for persistent state and Redis for Celery queues and WebSocket pub/sub.
```bash
docker-compose up -d db redis
```
*Wait a few seconds for the databases to complete initialization.*

### Step 3: Run Database Migrations
Run Alembic migrations to build the schema:
```bash
cd retail-exit-backend
uv pip install -r pyproject.toml
uv run alembic upgrade head
```

### Step 4: Boot the FastAPI Backend
```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```
*The backend is live at http://localhost:8000. Interactive API documentation is available at http://localhost:8000/docs.*

### Step 5: Boot the Next.js Dashboard
In a new terminal window, launch the frontend:
```bash
cd retail-exit-nextjs
npm install
npm run dev
```
*The dashboard is live at http://localhost:3000.*

---

## Initial Administrative Account Setup
The API is secured by JWT authentication and Role-Based Access Control (RBAC). 
Before initial startup, configure your secure administrative password in `.env`:

```bash
ADMIN_INITIAL_PASSWORD="your-strong-random-password-here"
```

* **Default Admin Username:** `admin`
* **Initial Password:** Configured via `ADMIN_INITIAL_PASSWORD` in `.env`. On non-production initial bootstrap without this variable set, a secure one-time secret is generated upon first database initialization. Always rotate credentials regularly.

---

## Core Architecture Pipeline

```
Edge Layer (RTSP Streams)
       │
       ▼
Vision Inference (YOLOX-Tiny & Biometrics)
       │
       ▼
Multi-Object Tracking (ByteTrack Hungarian + IoU)
       │
       ▼
Tri-Sensor Fusion & Dispatch Engine
       │
       ▼
FastAPI Services (JWT, PostgreSQL, Redis)
       │
       ▼
Next.js Operations Dashboard (WebSockets & Telemetry)
```

For detailed architectural, deployment, and security specifications, see:
* [Architecture Guide](docs/ARCHITECTURE.md)
* [Deployment Guide](docs/DEPLOYMENT.md)
* [Security Specification](docs/SECURITY.md)