# Retail Exit Monitoring System (V8 Enterprise Edition)

## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [User Manual](#user-manual)
5. [Project Rules & Information](#project-rules--information)
6. [Milestones Achieved](#milestones-achieved)

---

## 1. Overview
The Retail Exit Monitoring System is an AI-powered surveillance and inventory reconciliation platform. It seamlessly ingests live camera feeds, detects retail items (cases and singles), identifies vehicles and structural elements, and utilizes advanced facial recognition to track carriers—all in real-time.

---

## 2. Key Features
- **Real-Time Edge CV**: Deep-learning object detection (YOLOX) for retail goods, packages, and environment structures.
- **Biometric Security**: Integration with InsightFace for robust carrier identification, liveness detection, and smart tracking.
- **Single-Source-of-Truth Rendering**: Server-side bounding box drawing, telemetry overlays, and status banners ensure that live streams and saved snapshot evidence match pixel-for-pixel.
- **Active Learning & Smart Wall**: Interactive dashboard to review exit events, flag false positives, set physical Regions of Interest (ROI), and refine models dynamically.
- **Enterprise-Grade Database**: Robust SQLite/SQLAlchemy schema dynamically managing physical cameras, object definitions, and deep metrics.

---

## 3. Architecture
### Backend
- **FastAPI / Uvicorn**: Serves the REST API and WebSocket events.
- **SQLAlchemy (SQLite)**: Stores cameras, events, and metrics.
- **Vision Inference**: YOLO-based ML bounding box detection.
- **Face Recognition**: InsightFace liveness & embedding extraction.
- **Stream Manager**: Distributes MJPEG streams to frontend safely.
- **Workers**: Asynchronous background workers for polling cameras.

### Frontend
- **React / Vite**: Modern SPA interface.
- **WebSockets**: Real-time event and snapshot updates.
- **TailwindCSS**: UI styling.

---

## 4. User Manual
### System Requirements
- Python 3.9+
- Node.js 18+
- Modern Web Browser (Chrome/Firefox/Edge)

### Running the Backend
1. Navigate to etail-exit-backend/.
2. Activate your virtual environment.
3. Start the server using Uvicorn:
   `\ash
   python -m uvicorn src.main:app --port 8000 --host 127.0.0.1 --reload
   `\
4. The API and background worker processes will automatically initialize. WebSockets and MJPEG stream managers will listen for active camera connections.

### Running the Frontend Console
1. Navigate to etail-exit-console/.
2. Install dependencies: 
pm install
3. Start the development server:
   `\ash
   npm run dev
   `\
4. Open the provided localhost URL in your browser to access the Smart Wall.

### Operational Workflows
- **Adding a Camera**: Navigate to the "Cameras" tab and input the RTSP URL or physical camera ID. Configure regions of interest (ROI) via the visual interface to ignore static elements like shelves or wall pictures.
- **Reviewing Alerts**: Alerts are dynamically generated when motion triggers object detection. Use the timeline to investigate items flagged as missing or unverified carriers.

---

## 5. Project Rules & Information
- **Zero Mock Data**: No hardcoding or mock data is allowed anywhere in the system. The platform operates completely dynamically using true live data.
- **Professionalism**: The codebase is strictly human-written in appearance, clean, and production-ready without lingering AI-generated test files.
- **Consistency**: Live Video Stream must exactly match the saved snapshots.
- **Visual Design**: The system is designed to look like a modern surveillance UI. Green represents standard detections, yellow is used for vehicles/environment elements, and faces have specialized highlighting.

---

## 6. Milestones Achieved
1. **Zero-Mock Data Enforcement**: Transitioned the entire application from using static/hardcoded mock files to dynamic ML inference driven entirely by live data.
2. **True Event and Video Synchronization**: Implemented a unified FrameRenderer that completely overrides client-side SVG drawing, pushing server-rendered JPG frames into the live MJPEG stream. This guarantees that what the operator sees live is pixel-for-pixel what is stored as evidence.
3. **Advanced Detection Tuning**: Implemented Reflection Discrimination and customizable ROI configurations to drastically drop the false-positive rate from monitors, windows, and shelving units.
4. **Codebase Hardening**: Cleaned all unused endpoints, test data, testing scripts, and obsolete frontend UI elements.
5. **Database Synchronization**: Successfully auto-migrated schema structures to support advanced dynamic capabilities (oi_polygon, ignored_classes) without losing chain-of-custody data.
