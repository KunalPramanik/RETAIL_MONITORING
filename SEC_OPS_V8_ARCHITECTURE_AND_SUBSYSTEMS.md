# SEC-OPS V8 — Architecture & Subsystems Specification

**Document ID**: `SEC-OPS-V8-DOC-02`  
**Date**: October 11, 2026  
**Status**: **APPROVED SPECIFICATION**  

---

## 1. System Topology Overview

SEC-OPS V8 follows a high-throughput, edge-capable micro-modular service architecture designed to operate both on-premise at retail facilities and as a centralized cloud multi-tenant platform.

```
                    +------------------------------------+
                    |        EDGE DEVICES / CAMERAS      |
                    |  (RTSP / USB DirectShow / ONVIF)  |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |       CAMERA WORKER INGESTION      |
                    |  - Async Frame Polling (30 FPS)    |
                    |  - Motion Pre-filter & Debouncing  |
                    |  - Tripwire Gate Raycasting        |
                    +-----------------+------------------+
                                      |
                                      v
          +---------------------------+---------------------------+
          |                                                       |
          v                                                       v
+-------------------+                                   +-------------------+
|  YOLOX CV ENGINE  |                                   |  BIOMETRIC ENGINE |
| - Deep Tensor Inf |                                   | - InsightFace     |
| - Anti-Confusion  |                                   | - ArcFace 512-d   |
| - Unknown BBoxes  |                                   | - Master Killsw.  |
+---------+---------+                                   +---------+---------+
          |                                                       |
          +---------------------------+---------------------------+
                                      |
                                      v
                    +------------------------------------+
                    |     MULTI-SENSOR FUSION ENGINE     |
                    |  - Vision / RFID / Scale Weight    |
                    |  - Occlusion Capping (0.75 max)    |
                    |  - Deterministic Verdict Engine    |
                    +-----------------+------------------+
                                      |
                                      v
          +---------------------------+---------------------------+
          |                                                       |
          v                                                       v
+-------------------+                                   +-------------------+
|  POSTGRES / SQL   |                                   |  WEBSOCKET GATEWAY|
| - Audit Logs      |                                   | - Sub-50ms push   |
| - Exit Events     |                                   | - Ping/Pong Heartb|
| - Inventory Ledger|                                   | - Live Traversal  |
+-------------------+                                   +-------------------+
```

---

## 2. Core Subsystems

### 2.1 Edge Ingestion & Camera Worker (`src/engine/camera_worker.py`)
- **DirectShow / MSMF Concurrency**: Re-entrant memory-mapped frame sharing (`_last_raw_frames` and `_last_annotated_frames`) prevents OS device contention on Windows DirectShow drivers.
- **Hardware Circuit Breakers**: Automatic exponential backoff prevents infinite thread locking if network cameras drop offline.
- **Tripwire Gate Raycasting**: Deterministic directional vector crossing tests detect entry vs. exit traversals with zero ambiguity.

### 2.2 Deep Learning AI Vision Pipeline (`src/ml/vision_service.py`)
- **Model Standard**: Pure deep learning tensor evaluation using YOLOX ONNX/PyTorch models.
- **Anti-Confusion Filtering**:
  - Wall picture frames and rectangular interior decorations are distinguished from handheld books via height/area ratios and static background suppression.
  - Bare human skin and limbs are filtered to prevent false identification as commercial packaging.
- **Dynamic Unknown Classification**: Unmapped items are dynamically identified as `UNKNOWN (<Shape> <w>x<h>)` with full bounding box coordinates, preventing synthetic hallucinations.

### 2.3 Multi-Sensor Consensus Fusion Engine (`src/engine/fusion_engine.py`)
- **Tri-Sensor Weighting**:
  - Vision Consensus: 50%
  - RFID Tunnel Reader: 30%
  - Floor Strain-Gauge Scale: 20%
- **Graceful Sensor Degradation**: When RFID or Scales are unavailable, the engine gracefully degrades to vision-only counts while enforcing strict confidence flooring (capped at 0.75 under visual occlusion).

### 2.4 Double-Entry Inventory Ledger & Stock Service (`src/services/stock_service.py`)
- **Fundamental Accounting Formula**:
  $$\text{Current Stock} = \text{Opening Baseline} + \text{Incoming (Confirmed)} - \text{Outgoing (Confirmed)} + \text{Adjustments}$$
- **Audit Invariant**: No stock record may be updated without an associated `StockLedger` entry and an immutable `AuditLog` entry detailing the actor, timestamp, and justification.

### 2.5 Realtime WebSocket Hub (`src/realtime/hub.py`)
- Centralized asynchronous pub-sub broadcast system providing sub-50ms live updates to frontend operators.
- Automatic slow-consumer eviction, queue throttling (128 items max), and 20-second ping/pong keep-alive heartbeats.

