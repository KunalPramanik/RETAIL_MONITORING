# SEC-OPS 2.0: Retail Exit Monitoring Platform

An enterprise-grade, AI-powered video analytics and loss prevention platform designed for high-throughput retail exit lanes.

## Enterprise Architecture (V8)
The system has been completely overhauled for 100% production readiness:
*   Frontend: Migrated from React/Vite to a secure, server-rendered Next.js (App Router) framework.
*   Database: Replaced single-file SQLite with a fully concurrent PostgreSQL database managed by Alembic migrations.
*   Security: APIs are no longer open. Implemented strict JWT Authentication and Role-Based Access Control (RBAC) via bcrypt.
*   Tracking: Integrated ByteTrack (Hungarian matching + IoU) to solve occlusion and double-counting defects.
*   Infrastructure: Fully dynamic configuration (.env driven) with zero hardcoding. Ready for deployment via docker-compose.

---

## How to Run the Full System (100% Production Ready)

This system is decoupled into an API backend and a Next.js frontend, orchestrated via Docker. Follow these exact steps to launch the stack on a fresh machine.

### Prerequisites
*   Docker & Docker Compose
*   Node.js (v18+)
*   Python (3.10+) with uv package manager installed (pip install uv)

### Step 1: Clone and Configure Environment
`ash
git clone https://github.com/KunalPramanik/RETAIL_MONITORING.git
cd RETAIL_MONITORING/retail-exit-backend

# Copy the dynamic environment template
cp .env.example .env
`
*Note: In production, edit the .env file to set your own secure JWT_SECRET_KEY.*

### Step 2: Launch Infrastructure (PostgreSQL & Redis)
The backend relies on PostgreSQL for persistent state and Redis for Celery queues/WebSockets.
`ash
cd ..
docker-compose up -d db redis
`
*Wait 10 seconds for the databases to initialize.*

### Step 3: Run Database Migrations
We use Alembic to ensure the PostgreSQL schema is properly built.
`ash
cd retail-exit-backend
uv pip install -r pyproject.toml
uv run alembic upgrade head
`
*On the first run, this will dynamically provision a SUPER_ADMIN account.*

### Step 4: Boot the FastAPI Backend
`ash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
`
*The backend is now live at http://localhost:8000. API Docs are at http://localhost:8000/docs.*

### Step 5: Boot the Next.js Dashboard
In a new terminal window, launch the frontend:
`ash
cd retail-exit-nextjs
npm install
npm run dev
`
*The dashboard is now live at http://localhost:3000.*

---

## Initial Login Credentials
Because the API is secured by JWT, you must log in to the Dashboard to view camera feeds and analytics.

*   **Username:** admin
*   **Password:** admin123

*(You will be prompted to change this password in a production environment).*

## System Architecture

*   Edge Layer: IP Camera RTSP -> H.264 IngestWorker
*   Core AI Engine: Decoded Frames -> VisionService -> ObjectDetection (YOLOX-Tiny) & BiometricEngine (InsightFace)
*   Tracking: Bounding Boxes -> ByteTrack (IoU + Hungarian) -> DispatchEngine
*   Backend Services: DispatchEngine -> FastAPI (JWT Secured) -> PostgreSQL & Redis Queue
*   Presentation: FastAPI -> WebSockets / HTTP -> Next.js Dashboard
