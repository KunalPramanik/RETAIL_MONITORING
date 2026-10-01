# Retail Exit Monitoring System (V8 Enterprise Edition)

## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [System Architecture Diagram](#system-architecture-diagram)
4. [Data Flow Diagram](#data-flow-diagram)
5. [Database Schema (ERD)](#database-schema-erd)
6. [End-to-End Project Details](#end-to-end-project-details)
7. [User Manual](#user-manual)
8. [Project Rules & Information](#project-rules--information)
9. [Milestones Achieved](#milestones-achieved)

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

## 3. System Architecture Diagram

`mermaid
graph TD
    subgraph Frontend [React / Vite SPA]
        UI[Smart Wall UI]
        CamGrid[Camera Grid / MJPEG]
        Alerts[Live Alerts / Timeline]
    end

    subgraph Backend [FastAPI / Python]
        API[REST API Endpoints]
        WS[WebSocket Manager]
        SM[MJPEG Stream Manager]
        Worker[Camera Feed Worker]
        Renderer[FrameRenderer]
        
        subgraph ML_Services [Machine Learning]
            YOLO[VisionInferenceService (YOLOX)]
            Face[FaceRecognitionService (InsightFace)]
            Static[Static Image / Reflection Filter]
        end
    end

    subgraph DataLayer [Storage Layer]
        SQL[(SQLite Database)]
        Disk[Local Disk / Snapshots]
    end

    %% Interactions
    UI -->|HTTP GET/POST| API
    UI <-->|WebSocket| WS
    CamGrid <-->|HTTP MJPEG| SM

    Worker -->|1. Capture Frame| Camera((IP Camera))
    Worker -->|2. Detect Objects| YOLO
    Worker -->|3. Authenticate| Face
    YOLO -->|4. Quarantine Check| Static
    Worker -->|5. Draw Boxes| Renderer
    
    Renderer -->|6. Annotated Frame| SM
    Worker -->|7. Push Events| WS
    Worker -->|8. Save Event & Metrics| SQL
    Worker -->|9. Save Evidence| Disk
`

---

## 4. Data Flow Diagram

`mermaid
sequenceDiagram
    participant Cam as IP Camera
    participant Worker as CameraFeedWorker
    participant ML as Vision & Face Services
    participant DB as SQLite DB
    participant SM as Stream Manager
    participant UI as React Frontend

    loop Every 0.5 seconds
        Worker->>Cam: Fetch latest frame bytes
        Cam-->>Worker: raw_frame_bytes
        
        Worker->>ML: Analyze objects & detect faces
        ML-->>Worker: Bounding boxes, labels, face match IDs
        
        Worker->>Worker: Apply ROI & Ignore Lists
        Worker->>Worker: FrameRenderer draws boxes on frame
        
        Worker->>SM: Push annotated_bytes to Stream
        SM-->>UI: Live MJPEG stream updates automatically
        
        alt Suspicious exit or motion detected
            Worker->>DB: Save ExitEvent & DetectedObjects
            Worker->>DB: Save Snapshot to disk
            Worker->>UI: Emit WebSocket detection_update
            UI->>UI: Flash Smart Wall red & add to timeline
        end
    end
`

---

## 5. Database Schema (ERD)

`mermaid
erDiagram
    CAMERA ||--o{ EXIT_EVENT : tracks
    CAMERA {
        string camera_id PK
        string lane_id
        string ip_address
        string status
        json roi_polygon
        json ignored_classes
    }

    EXIT_EVENT ||--o{ DETECTED_OBJECT : contains
    EXIT_EVENT {
        string event_id PK
        string camera_id FK
        datetime timestamp
        int cases_detected
        int singles_detected
        string carrier_name
        string snapshot_path
    }

    DETECTED_OBJECT {
        string object_id PK
        string event_id FK
        string class_label
        string specific_label
        float confidence
        json bbox
        boolean is_inventory_relevant
    }

    ROSTER {
        string employee_id PK
        string full_name
        string role
        boolean is_active
        bytes face_embedding
    }

    CATALOG {
        string product_id PK
        string sku_code
        string product_name
        int pack_size
    }

    DAILY_METRICS {
        string metric_id PK
        date target_date
        int total_events
        int total_units_lost
    }
`

---

## 6. End-to-End Project Details

### Overview
This system is an enterprise-scale application built to monitor exit points (like retail doors, warehouse loading docks, and distribution centers) autonomously. 

### Step-by-Step Execution Flow
1. **Ingestion**: The system continuously connects to registered RTSP streams or local webcams via background asynchronous workers.
2. **Inference**: Every fetched frame is converted to a NumPy array and passed through an in-memory YOLO-based vision detector. Simultaneously, InsightFace checks for the presence of human faces.
3. **Filtering**: 
   - A reflection/quarantine module checks if the detected objects are actually reflections inside a TV or mirror.
   - Dynamic Region of Interest (ROI) polygons strip out detections occurring outside the designated operational zones.
   - Ignored class lists drop structural entities like "bookshelf" or "doorway" if the user has requested they be excluded from alerts.
4. **Authentication**: If a face is found, it is evaluated for "liveness" (rejecting static photos held up to the camera) and matched against the SQLite ROSTER table embeddings.
5. **Rendering**: The FrameRenderer acts as the single source of truth. It physically paints the bounding boxes and telemetry data (like latency and FPS) onto the image bytes.
6. **Streaming & Alerting**: The newly painted frame is handed off to the Stream Manager which serves it as a frictionless MJPEG stream to the React UI. If items cross the threshold, a database entry is stored and the WebSocket fires an alert to update the frontend timeline instantly.

---

## 7. User Manual
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

## 8. Project Rules & Information
- **Zero Mock Data**: No hardcoding or mock data is allowed anywhere in the system. The platform operates completely dynamically using true live data.
- **Professionalism**: The codebase is strictly human-written in appearance, clean, and production-ready without lingering AI-generated test files.
- **Consistency**: Live Video Stream must exactly match the saved snapshots.
- **Visual Design**: The system is designed to look like a modern surveillance UI. Green represents standard detections, yellow is used for vehicles/environment elements, and faces have specialized highlighting.

---

## 9. Milestones Achieved
1. **Zero-Mock Data Enforcement**: Transitioned the entire application from using static/hardcoded mock files to dynamic ML inference driven entirely by live data.
2. **True Event and Video Synchronization**: Implemented a unified FrameRenderer that completely overrides client-side SVG drawing, pushing server-rendered JPG frames into the live MJPEG stream. This guarantees that what the operator sees live is pixel-for-pixel what is stored as evidence.
3. **Advanced Detection Tuning**: Implemented Reflection Discrimination and customizable ROI configurations to drastically drop the false-positive rate from monitors, windows, and shelving units.
4. **Codebase Hardening**: Cleaned all unused endpoints, test data, testing scripts, and obsolete frontend UI elements.
5. **Database Synchronization**: Successfully auto-migrated schema structures to support advanced dynamic capabilities (oi_polygon, ignored_classes) without losing chain-of-custody data.
