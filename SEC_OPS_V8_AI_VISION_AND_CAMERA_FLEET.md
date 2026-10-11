# SEC-OPS V8 — AI Vision Pipeline & Camera Fleet Architecture

**Document ID**: `SEC-OPS-V8-DOC-04`  
**Date**: October 11, 2026  
**Status**: **APPROVED SPECIFICATION**  

---

## 1. Computer Vision Pipeline Integrity

The SEC-OPS V8 platform enforces a strict **Zero-Fake / Zero-Synthetic Detections Policy**. All detection records displayed in the UI or committed to the operational database originate exclusively from real neural network tensor inference.

```
+-------------------------------------------------------------+
|                     CAMERA FRAME INGESTION                  |
| - High-throughput RTSP / DirectShow ingestion (30 FPS)       |
| - Timestamp & Frame Sequence validation                     |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                PREPROCESSING & MOTION FILTER                |
| - Gaussian blur diffing & debounce (6.0s default)           |
| - Suppresses static background video frames                 |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     YOLOX-M INFERENCE                       |
| - Tensor evaluation (Confidence floor: 0.50)                |
| - NMS IoU threshold: 0.35                                   |
| - Anti-confusion suppression (Wall frames, Bare limbs)      |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                 DYNAMIC UNKNOWN SHAPE CLASSIFIER            |
| - Unmapped objects labeled as UNKNOWN (<Shape> <w>x<h>)     |
| - Real bounding box coordinates preserved                   |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                  BYTETRACK OBJECT TRACKER                   |
| - Kalman filter motion estimation                           |
| - Track association & Tripwire Gate Raycasting              |
+-------------------------------------------------------------+
```

---

## 2. Re-entrant DirectShow Webcam Preview Architecture

In Windows environments, OS hardware locks prevent multiple processes or threads from opening `cv2.VideoCapture(0)` simultaneously. Legacy implementations produced black screens and device busy errors when testing connections or requesting snapshots while the background camera worker was active.

### Solution Implemented:
1. `CameraWorker` maintains a thread-safe frame buffer:
   - `_last_raw_frames[camera_id]`: Unaltered BGR camera frames.
   - `_last_annotated_frames[camera_id]`: Frames annotated with active bounding boxes and gate lines.
2. The preview endpoints:
   - `POST /api/cameras/test-connection`
   - `GET /api/cameras/{id}/snapshot`
   - `POST /api/cameras/{id}/suggest-gate-line`
   tap directly into the in-memory frame cache.
3. If the worker is running, frames are returned in **sub-10ms** with zero device contention. If offline, the hardware capture is queried with clean resource release.

---

## 3. Interactive Gate Line & Tripwire Suggestion Tool

To eliminate manual configuration errors, V8 introduces an automated Gate Line Suggestion engine in `settings/cameras/page.tsx`:
1. **Automated Calculation**: Evaluates camera frame dimensions (e.g. 1920x1080) and calculates an optimal horizontal crossing threshold at 65% frame height ($y = 0.65 \times H$), spanning 10% to 90% width.
2. **Interactive UI Controls**:
   - `ACCEPT SUGGESTION`: Instantly commits coordinates to the camera configuration.
   - `NUDGE UP / NUDGE DOWN`: Shifts the gate threshold by $\pm 20\text{px}$ for precise fine-tuning.
   - `RESET`: Restores default center coordinates.
3. **Tripwire Polygon Persistence**: Stored directly in the `cameras.roi_polygon` column and evaluated in real-time by the tracking worker.

