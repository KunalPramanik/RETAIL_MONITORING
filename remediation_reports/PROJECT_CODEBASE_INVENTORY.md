# PROJECT CODEBASE INVENTORY

## A. Full Directory Tree
### Backend (etail-exit-backend/)
- src/api: FastAPI Routers (settings, cameras, events, dispatch)
- src/core: Configuration (config.py)
- src/db: SQLAlchemy setup (session.py, models.py)
- src/engine: Core workers (camera_worker.py, dispatch_engine.py)
- src/ml: Computer Vision (ision_service.py, YOLO/InsightFace wrappers)
- src/services: Business logic (event_service.py)
- data/: SQLite DB and AI candidate storage
- *(Missing)*: 	ests/ directory (deleted prior to audit)

### Frontend (etail-exit-console/)
- src/api: Axios client
- src/components: React UI components (Dashboard, Camera streams, Data grids)
- src/views: Route pages

## B. File-by-File Classification
| File | Purpose | Runtime Role | Production Relevant | Safe to Remove |
| :--- | :--- | :--- | :--- | :--- |
| src/db/session.py | SQLite Engine setup | DB Layer | Yes | No |
| src/engine/camera_worker.py | Stream ingestion | Worker | Yes | No |
| src/ml/vision_service.py | YOLO inference | CV logic | Yes | No |
| src/api/routes/*.py | REST Endpoints | HTTP API | Yes | No |

## C. Architecture Map
\\\	ext
IP Camera (RTSP)
   ↓
camera_worker.py (OpenCV VideoCapture)
   ↓
vision_service.py (YOLOX-Tiny ONNX -> InsightFace ArcFace)
   ↓
dispatch_engine.py (Severity Assessment / Confidence filters)
   ↓
session.py (SQLite Commit)
   ↓
FastAPI Routes
   ↓
React Vite Console
\\\

## D. Dependency Map
- **Python:** fastapi, uvicorn, sqlalchemy, aiosqlite, opencv-python, onnxruntime, numpy.
- **Node:** react, react-dom, tailwindcss, vite, axios.
- **Missing Enterprise Deps:** asyncpg (PostgreSQL), PyJWT (Auth), passlib (Hashing), pika/redis (Queues), pytest (Testing).

## E. Database Inventory
- **Engine:** SQLite (via aiosqlite)
- **Tables:** events (Exit events), cameras (Configurations), settings (System thresholds)
- **Weakness:** SQLite lock potential, no migration framework (Alembic is missing), raw auto-creation on startup.
