# Retail Exit Monitoring System (V8 Enterprise Edition)

## Overview
The Retail Exit Monitoring System is an AI-powered surveillance and inventory reconciliation platform. It seamlessly ingests live camera feeds, detects retail items (cases and singles), identifies vehicles and structural elements, and utilizes advanced facial recognition to track carriers—all in real-time.

## Key Features
- **Real-Time Edge CV**: Deep-learning object detection (YOLOX) for retail goods, packages, and environment structures.
- **Biometric Security**: Integration with InsightFace for robust carrier identification, liveness detection, and smart tracking.
- **Single-Source-of-Truth Rendering**: Server-side bounding box drawing, telemetry overlays, and status banners ensure that live streams and saved snapshot evidence match pixel-for-pixel.
- **Active Learning & Smart Wall**: Interactive dashboard to review exit events, flag false positives, set physical Regions of Interest (ROI), and refine models dynamically.
- **Enterprise-Grade Database**: Robust SQLite/SQLAlchemy schema dynamically managing physical cameras, object definitions, and deep metrics.

## Documentation
Please refer to the docs/ folder for comprehensive documentation on the system's architecture, product requirements, and operations.
- docs/user_manual.md: Setup and operational instructions.
- docs/full_summary.md: Complete overview of the system architecture and completed milestones.
- docs/architecture.md: Backend/Frontend technology stack details.
- docs/prd.md: Product Requirements Document.
