# SEC-OPS V8 — Inventory and Material Movement Workflow Specification

## 1. Architectural Separation: Detection vs. Movement vs. Inventory

A critical architectural tenet of the SEC-OPS V8 platform is the strict separation between three distinct operational phases:

```text
+-----------------------+     +-------------------------+     +-------------------------------+
|  1. LIVE DETECTION    |     |   2. ENTRY/EXIT EVENT   |     |    3. INVENTORY TRANSACTION   |
|  "What is visible?"   | --> |  "What crossed gate?"   | --> |  "What updates stock balance?"|
+-----------------------+     +-------------------------+     +-------------------------------+
| YOLOX Deep Learning   |     | ByteTrack Trajectory    |     | Consensus Verification        |
| Persistent Track IDs  |     | Ground Passage Boundary |     | Bill / Egress Authorization   |
| Non-mutating state    |     | Directional IN vs OUT   |     | Atomic Ledger Balance Update  |
+-----------------------+     +-------------------------+     +-------------------------------+
```

1. **Live Detection (`vision_detection`)**:
   - Represents the current optical observation of objects within the field of view.
   - An object remaining static on a pallet or shelf generates continuous frame tracking but **NEVER** mutates stock records.
2. **Movement Event (`exit_event` / `tripwire_crossing_event`)**:
   - Generated only when a tracked object centroid crosses the configured ground passage entry/exit threshold.
   - Implements anti-duplicate crossing locks with cooldown timers to prevent oscillation or standing near the threshold from generating spurious transactions.
3. **Inventory Transaction (`material_movement_ledger` / `material_inventory_balance`)**:
   - Commits an atomic balance change only when the movement is validated against authorizations or approved by dispatch reconciliation.

---

## 2. Initial Stock Baseline Verification Workflow (Phases 16 & 29)

To ensure the system never operates on unverified optical assumptions, initial inventory counting enforces human-in-the-loop verification before automated IN/OUT tracking begins:

```text
PHYSICAL INVENTORY SCANNED BY CAMERA
                ↓
AI PROPOSES BASELINE: e.g. Cement Bags = 1,000
                ↓
OPERATOR REVIEW CONSOLE (UI Notification)
                ↓
        +-------+-------+
        |               |
 [ YES — ACCEPT ]   [ NO — EDIT ]
        |               |
        |               +--> Operator Enters Actual Recount: 980
        |                    Records Reason: "8 units damaged in transit"
        ↓               ↓
VERIFIED OPENING STOCK SAVED TO DATABASE:
- AI Proposed Count: 1,000
- Verified Count: 1,000 (if YES) or 980 (if NO)
- Variance / Difference: 0 or -20
- Verified By: Operator Username
- Timestamp & Model Version Recorded
- Snapshot Evidence Persisted
```

### Database Persistence Model (`initial_stock_verification`)
* `verification_id`: Unique UUID/ULID
* `product_id` / `sku_code`: Target merchandise
* `ai_proposed_count`: Original model output
* `verified_count`: Confirmed count
* `difference`: Reconciled variance
* `status`: `PENDING_VERIFICATION` | `VERIFIED_ACCURATE` | `CORRECTED` | `REJECTED`
* `verified_by`: Operator attribution
* `correction_reason`: Audit rationale
* `snapshot_url`: Visual proof at time of scan

---

## 3. Automated Post-Verification Inventory Flow (Phases 17 & 19)

Once the baseline opening stock is established, inventory tracking becomes fully automated:

$$\text{Current Stock} = \text{Verified Opening Stock} + \text{Verified IN} - \text{Verified OUT} + \text{Adjustments}$$

### Egress & Ingress Rules:
1. **Item-by-Item Tracking**: Every physically transported item across the boundary decrements/increments the balance individually.
2. **Simultaneous Concurrency**: Multiple people and objects moving in opposite directions at the same timestamp are tracked as independent trajectories.
3. **Bill / Dispatch Authorization Matching (Phase 20)**:
   - Scanned Bills/Manifests (`invoice`) declare authorized items and quantities.
   - Live dispatch HUD shows:
     * `Authorized Quantity`: Scanned on manifest
     * `Actual Taken Quantity`: Incrementally verified by camera + sensors
     * `Remaining Quantity`: Real-time remaining quota
   - Verdict Categories:
     * `CORRECT`: Actual equals authorized
     * `WRONG_ITEM`: Detected SKU does not match manifest
     * `OVER_QUANTITY`: Taken exceeds authorized quota
     * `UNDER_QUANTITY`: Premature departure
     * `COUNT_UNCERTAIN`: High occlusion requiring manual audit

---

## 4. Exceptional Manual Adjustments (Phase 25)

Manual stock overrides are permitted for physical reconciliation, breakages, or supplier adjustments, but **never overwrite ledger history**:
* Every adjustment creates an immutable `MaterialMovementLedger` row with `transaction_type="MANUAL_ADJUSTMENT"`.
* Mandatory fields: `operator_id`, `reason`, `qty_change`, `previous_stock`, `new_stock`.
* Currency standard: Indian Rupee (₹ / INR).
