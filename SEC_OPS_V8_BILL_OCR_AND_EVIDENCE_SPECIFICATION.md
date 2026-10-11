# SEC-OPS V8 — Bill OCR & Traversal Evidence Specification

**Document ID**: `SEC-OPS-V8-DOC-06`  
**Date**: October 11, 2026  
**Status**: **APPROVED SPECIFICATION**  

---

## 1. Overview & Dual-Mode OCR Architecture

SEC-OPS V8 provides an intelligent Bill of Lading (BOL), Receipt, and Manifest Verification engine via `src/ml/ocr/invoice_ocr_service.py` and `src/api/invoices.py`.

The service operates in two distinct modes:
1. **Direct Structured Upload**: Fast parsing when enterprise ERPs or scanners submit pre-extracted digital line items.
2. **Deep Learning Document Vision (PaddleOCR)**: Direct image text recognition and spatial layout analysis on photographed paper manifests, bills, or delivery challans.

---

## 2. Person-to-Goods Traversal Progress Tracking

When an exit event occurs at a store gate or loading dock:
1. The camera worker detects the carrier (person) and the carried items (goods).
2. The event is linked to the relevant bill of lading using `linkedEventId`.
3. The platform computes an automated consensus comparison:

$$\Delta\text{Units} = \text{Consensus Units (Vision)} - \text{Declared Units (Invoice)}$$

### Verdict Matrix:

| Condition | Verdict | Severity | System Action |
| :--- | :--- | :--- | :--- |
| $\Delta\text{Units} = 0$ | `PASS` | `INFO` | Gate turnstile opens; transaction cleared. |
| $\Delta\text{Units} > 0$ (Over-quantity) | `MISMATCH` | `HIGH` | Turnstile interlock engages; alert broadcasted to supervisor queue. |
| $\Delta\text{Units} < 0$ (Under-quantity) | `MISMATCH` | `MEDIUM` | Warning logged; operator prompt for physical count verification. |
| Uncataloged SKU Detected | `WRONG_ITEM` | `HIGH` | Security alert triggered; annotated snapshot forwarded for audit. |

---

## 3. Evidence Snapshot Chain of Custody

To guarantee evidentiary integrity for legal and insurance audits:
1. Every crossing event writes a high-resolution JPEG image to `/snapshots/{lane_id}_{event_id}.jpg`.
2. Image contains burned-in neural network bounding boxes:
   - Green: Verified catalog items.
   - Yellow: Unknown unmapped objects (`UNKNOWN (<Shape> <w>x<h>)`).
   - Red: Discrepancies or unauthorized crossing attempts.
   - Blue overlay: Calibrated gate tripwire crossing line.
3. Snapshots are tied to the immutable `ExitEvent` database record and referenced by URL.
4. Fallback handler (`GET /api/cameras/{id}/snapshot`) guarantees that even if a historical snapshot is archived, the current live camera frame is instantly accessible.

