# SEC-OPS Platform — Third-Party Notices & Model Cards

This document details all third-party software, libraries, and deep-learning models utilized within the SEC-OPS Smart Retail Exit Monitoring Platform, along with their respective licensing terms and operational usage constraints.

---

## 1. Project License vs. Third-Party Notices

The project's root `LICENSE` file governs the proprietary and source components of the SEC-OPS platform.
Third-party libraries, weights, and algorithms are subject to the distinct upstream licenses documented below.

---

## 2. Model Cards & Computer Vision Weights

### 2.1 Megvii YOLOX (Object Detection)
* **Model Family**: YOLOX-Tiny / YOLOX-S / YOLOX-M ONNX
* **Upstream Authors**: Megvii Technology (Zheng Ge, Songtao Liu, Feng Wang, Zeming Li, Jian Sun)
* **Repository**: https://github.com/Megvii-BaseDetection/YOLOX
* **License**: **Apache License 2.0**
* **Commercial Use**: Permitted under Apache 2.0 with copyright and license notice retention.
* **Input Resolution**: 416x416 / 640x640 letterboxed RGB
* **Runtime**: ONNX Runtime (CPU / OpenVINO / CUDA)
* **Purpose**: Real-time bounding box detection of person, bag, backpack, bottle, cart, phone, and retail SKUs.

---

### 2.2 DeepInsight / InsightFace (Face Recognition & Biometrics)
* **Model Family**: ArcFace 512-d (buffalo_s, buffalo_l), SCRFD Face Detector
* **Upstream Authors**: DeepInsight (Jiankang Deng, Jia Guo, Niannan Xue, Stefanos Zafeiriou)
* **Repository**: https://github.com/deepinsight/insightface
* **Code License**: MIT License
* **Pretrained Model Weights License**: **InsightFace Non-Commercial Research License**
* **CRITICAL LEGAL NOTICE**:
  > Pretrained weights distributed by the InsightFace project (including `buffalo_s`, `buffalo_l`, and `antelopev2`) are explicitly restricted to **academic research and non-commercial evaluation only**.
  > Commercial enterprise deployment in surveillance, loss prevention, or retail operations **requires an upstream commercial license** negotiated directly with DeepInsight. Contact: `contact@insightface.ai`.
* **Platform License Gate**:
  - `SECOPS_BIOMETRIC_ENABLED` is strictly **`false`** by default.
  - In `production` environments, initialization of the InsightFace runtime is gated by `SECOPS_BIOMETRIC_COMMERCIAL_LICENSE_ACKNOWLEDGED=true`.
  - Without an explicit commercial license acknowledgment, all biometric feature extraction, 1:N matching, and face photo enrollment paths are deactivated at startup.
* **Input Resolution**: 640x640 RGB (SCRFD detector) -> 112x112 aligned face crop (ArcFace feature extractor)
* **Output**: 512-dimensional L2-normalized float32 metric embedding vector.

---

### 2.3 ByteTrack (Multi-Object Tracking)
* **Upstream Authors**: Yifu Zhang, Peize Sun, Yi Jiang, Dongdong Yu, Fucheng Weng, Zehuan Yuan, Ping Luo, Wenyu Liu, Xinggang Wang
* **Repository**: https://github.com/ifzhang/ByteTrack
* **License**: **MIT License**
* **Commercial Use**: Permitted under MIT terms.
* **Purpose**: Association of high and low-confidence detection bounding boxes across consecutive video frames to maintain stable track identities and kinematic trajectories.

---

## 3. Core Open-Source Libraries

| Package | Upstream Project | License | Purpose |
|---|---|---|---|
| `fastapi` | Tiangolo / FastAPI | MIT | REST API and async application framework |
| `sqlalchemy` | SQLAlchemy Authors | MIT | SQL database ORM and relational query builder |
| `alembic` | Mike Bayer / SQLAlchemy | MIT | Relational schema migrations and versioning |
| `opencv-python-headless` | OpenCV Team | Apache 2.0 | Frame decode, color space transformation, annotation |
| `onnxruntime` | Microsoft | MIT | High-performance CPU/GPU cross-platform model execution |
| `pydantic` | Samuel Colvin / Pydantic | MIT | Data validation and type enforcement |
| `cryptography` | PyCA Cryptography | Apache 2.0 / BSD | MultiFernet symmetric payload and credential encryption |
| `redis` | Redis Python Developers | MIT | Distributed cache, rate limiter, and pub/sub bus |
| `asyncpg` | MagicStack Inc. | Apache 2.0 | High-performance asynchronous PostgreSQL client |
| `aiosqlite` | John Reese | MIT | Asynchronous SQLite driver for standalone fallback |
