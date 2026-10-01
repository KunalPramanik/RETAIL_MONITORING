# Architecture
## Backend
- **FastAPI / Uvicorn**: Serves the REST API and WebSocket events.
- **SQLAlchemy (SQLite)**: Stores cameras, events, and metrics.
- **Vision Inference**: YOLO-based ML bounding box detection.
- **Face Recognition**: InsightFace liveness & embedding extraction.
- **Stream Manager**: Distributes MJPEG streams to frontend safely.
- **Workers**: Asynchronous background workers for polling cameras.

## Frontend
- **React / Vite**: Modern SPA interface.
- **WebSockets**: Real-time event and snapshot updates.
- **TailwindCSS**: UI styling.
