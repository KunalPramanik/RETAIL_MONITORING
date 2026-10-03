# DEFECT & BUG REGISTER

## BUG-0001: Missing Automated Test Suite
*   **Module:** Core System
*   **Severity:** BLOCKER
*   **Priority:** P0 - Immediate
*   **Expected Result:** A complete suite of unit and integration tests (pytest) should exist for a production-grade enterprise system.
*   **Actual Result:** The 	ests/ directory was deleted. Code coverage is 0%.
*   **Impact:** Any code change risks silent regressions in mission-critical hardware (turnstiles) and biometric authentication.
*   **Status:** OPEN

## BUG-0002: Missing API Authentication Middleware
*   **Module:** Backend API (src/api)
*   **Severity:** CRITICAL
*   **Priority:** P0 - Immediate
*   **Expected Result:** Routes serving biometric data, exit events, and system settings must be protected by JWT or session-based authentication.
*   **Actual Result:** Endpoints do not implement Depends(get_current_user) or equivalent OAuth2 mechanisms.
*   **Impact:** An attacker on the local network can fetch biometric embeddings or trigger false turnstile drops.
*   **Status:** OPEN

## BUG-0003: SQLite Concurrency Lock Risk
*   **Module:** Database (src/db)
*   **Severity:** CRITICAL
*   **Priority:** P1 - Very High
*   **Expected Result:** The database should handle concurrent writes from 10+ camera workers simultaneously.
*   **Actual Result:** The system utilizes sqlite+aiosqlite. While asynchronous, SQLite uses a file-level lock for writes, guaranteeing database is locked exceptions under concurrent camera loads.
*   **Impact:** Event data will be lost during peak hours.
*   **Status:** OPEN

## BUG-0004: Occlusion Failure (Bagging Problem)
*   **Module:** ML Pipeline (src/ml/vision_service.py)
*   **Severity:** HIGH
*   **Priority:** P2 - High
*   **Expected Result:** The system should track items even if obscured during exit.
*   **Actual Result:** YOLO vision model strictly requires line-of-sight. Items placed in bags bypass the scanner.
*   **Impact:** False positive "Discrepancy" alerts.
*   **Status:** OPEN

## BUG-0005: Orphaned Active Learning Code
*   **Module:** Data Pipeline
*   **Severity:** MEDIUM
*   **Priority:** P3 - Normal
*   **Expected Result:** The active learning pipeline should process flagged images and queue them for retraining.
*   **Actual Result:** Over 6,000 candidate JSON files were manually deleted from data/active_learning/candidates, but the pipeline logic still attempts to read/write to non-existent or unmanaged directory structures.
*   **Status:** OPEN
