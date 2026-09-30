# V8 DATABASE AUDIT

*Status: ACTIVE - Phase 1 (Audit)*

## 1. Schema Baseline (V7)
The current database contains 28 physical tables including:
* **Master Data:** `Store`, `Employee`, `Product`, `Material`, `PackageDefinition`.
* **Devices:** `Camera`, `CameraHeartbeat`, `Lane`, `VirtualTripwireConfig`.
* **Operations:** `ExitEvent`, `DispatchSession`, `MaterialMovementLedger`, `MaterialInventoryBalance`.
* **Inference / Sensors:** `VisionDetection`, `FaceMatchAttempt`, `RfidRead`, `WeightReading`, `StaticImageDetection`, `PersonAppearanceSummary`.
* **Incidents & UI:** `Alert`, `AlarmDispatch`, `AuditLog`, `AppUser`, `ThresholdConfig`.

## 2. V8 Gap Analysis & Extension Strategy
The V8 Enterprise mandate requires new data domains (Smart Wall, Evidence Chain, ANPR, Access Control). Per Section 23, we will reuse existing structures wherever possible.

| New Capability | Proposed Storage Strategy | Justification / Schema Impact |
| :--- | :--- | :--- |
| **Evidence Management (Hashes/Chain-of-Custody)** | **NEW TABLE:** `EvidenceArtifact` | V7's `ExitEvent` stores raw S3 URLs, but lacks cryptographic hashes, retention limits, export tracking, and cross-incident correlation required by Section 12. |
| **Unified Incident Graph** | REUSE: `ExitEvent` + `Alert` | We will elevate `ExitEvent` and `DispatchSession` to abstract "Incidents" and link them via the existing relational graph. No new incident table required. |
| **Smart Wall Layouts** | **NEW TABLE:** `SmartWallLayout` | V7 has no persistence for user-configured 1/4/9 camera grids or automatic rotation schedules. |
| **Access Control (Door/Badge)** | **NEW TABLE:** `AccessControlEvent` | RFID exists (`RfidRead`), but it is tuned for material logistics. Physical doors require anti-passback, interlock status, and MFA tracking. |
| **Vehicle / ANPR** | **NEW TABLE:** `VehicleDetection` | Cannot reuse `VisionDetection` as ANPR requires specific metadata (Plate Text, Watchlist Hit, Direction, State/Region) not present in generic bboxes. |
| **Forensic Search** | REUSE: `PersonAppearanceSummary` + pgvector | We will heavily index the existing pgvector column in `PersonAppearanceSummary` to support semantic search. |

## 3. Empty Database Verification (Section 35.10)
A clean boot script `scripts/clean_db.py` exists and successfully provisions a 0-row operational state. During Phase 14 (Real Acceptance), the system will be evaluated starting from this 0-row state to prove no hidden seed data bypasses the logic.
