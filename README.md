# SEC-OPS 2.0: Retail Exit Monitoring Platform

An enterprise-grade, AI-powered video analytics and loss prevention platform designed for high-throughput retail exit lanes.

## Enterprise Architecture Upgrades (V8)
The system has been completely overhauled for 100% production readiness:
*   Frontend: Migrated from React/Vite to a secure, server-rendered Next.js (App Router) framework.
*   Database: Replaced single-file SQLite with a fully concurrent PostgreSQL database managed by Alembic migrations.
*   Security: APIs are no longer open. Implemented strict JWT Authentication and Role-Based Access Control (RBAC) via bcrypt.
*   Infrastructure: Fully dynamic configuration (.env driven) with zero hardcoding. Ready for deployment via docker-compose.

## System Architecture

*   Edge Layer: IP Camera RTSP -> H.264 IngestWorker
*   Core AI Engine: Decoded Frames -> VisionService -> ObjectDetection (YOLOX-Tiny) & BiometricEngine (InsightFace)
*   Tracking: Bounding Boxes -> ByteTrack / DeepSORT Tracker -> DispatchEngine
*   Backend Services: DispatchEngine -> FastAPI (JWT Secured) -> PostgreSQL & Redis Queue
*   Presentation: FastAPI -> WebSockets / HTTP -> Next.js Dashboard

## Quick Start (Docker Compose)

1. Clone & Configure
   cd retail-exit-backend
   cp .env.example .env

2. Launch Infrastructure
   docker-compose up -d db redis

3. Run Migrations & Boot Backend
   uv run alembic upgrade head
   uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

4. Boot Next.js Dashboard
   cd ../retail-exit-nextjs
   npm install
   npm run dev

## Security & Authentication
The system requires a valid JWT Bearer token to access the API. On first boot, the system dynamically provisions a SUPER_ADMIN account if the database is empty. 
*   Username: admin
*   Password: admin123 (Must be changed on first login)

## Automated Testing
The backend utilizes a comprehensive Pytest suite located in retail-exit-backend/tests/.
   cd retail-exit-backend
   uv run python -m pytest
