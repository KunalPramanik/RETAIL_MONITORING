# SEC-OPS V8 — Inventory Ledger & Opening Stock Accounting

**Document ID**: `SEC-OPS-V8-DOC-05`  
**Date**: October 11, 2026  
**Status**: **APPROVED SPECIFICATION**  

---

## 1. Accounting Philosophy & Core Invariant

SEC-OPS V8 implements a rigorous double-entry inventory ledger model designed to eliminate ghost stock and maintain end-to-end auditability across the supply chain.

Every physical SKU record in the database is bound by the fundamental invariant:

$$\text{Current Stock} = \text{Opening Baseline} + \text{Incoming (Confirmed)} - \text{Outgoing (Confirmed)} + \text{Adjustments}$$

Where:
- $\text{Opening Baseline}$: Approved initial census count locked during system onboarding.
- $\text{Incoming (Confirmed)}$: Verified inventory entering via receiving dock gates (`ENTRY` direction).
- $\text{Outgoing (Confirmed)}$: Verified inventory leaving via customer exit lanes (`EXIT` direction).
- $\text{Adjustments}$: Manually audited operational corrections (spoilage, shrinkage, damaged goods) requiring mandatory supervisor justification.

---

## 2. Opening Stock Census Workflow

To ensure the system never starts with fabricated or hardcoded numbers, SEC-OPS V8 introduces the **AI-Assisted Opening Stock Census**:

```
+-----------------------------------------------------------+
|               PHYSICAL OPENING SCAN (INSPECTION)          |
| - Edge camera captures warehouse shelf / pallet racking  |
| - YOLOX Vision Engine performs object census             |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|          INITIAL STOCK VERIFICATION RECORD CREATED        |
| - Status: PENDING_VERIFICATION                            |
| - AI Proposed Count recorded                              |
| - Annotated snapshot preserved in /snapshots              |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|               OPERATOR / SUPERVISOR REVIEW                |
|                                                           |
|    [ YES — ACCEPT ]                 [ NO — EDIT ]         |
|  - Locks proposed count        - Operator inputs real qty |
|  - Baseline frozen             - Mandatory reason input   |
|  - Sets initial stock          - Discrepancy logged       |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|                  STOCK RECORD INITIALIZED                 |
| - Current Stock = Approved Count                          |
| - Opening Stock = Approved Count                          |
| - Status: APPROVED                                        |
| - Immutable Audit Log entry recorded                      |
+-----------------------------------------------------------+
```

---

## 3. Monetary Standards: Indian Rupee (`₹` / INR)

In strict accordance with the V8 Master Implementation guidelines, all monetary values, inventory valuations, unit costs, and shrinkage impact calculations across the entire stack are denominated in **Indian Rupees (`₹` / INR)**.

Example Ledger Presentation:

| SKU Code | Description | Opening | IN (+) | OUT (−) | ADJ (±) | Current Stock | Unit Cost | Total Valuation |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `SKU-BEV-001` | Mineral Water 1L | 0 | +50 | −10 | 0 | **40 U** | ₹ 20.00 | **₹ 800.00** |
| `SKU-DRY-002` | Basmati Rice 5kg | 0 | +20 | −4 | 0 | **16 U** | ₹ 450.00 | **₹ 7,200.00** |

---

## 4. Ledger Transaction Audit Immutability

1. `StockLedger` table maintains an append-only transaction history:
   - `transaction_id`: Unique UUID identifier.
   - `sku_code`: Target product identifier.
   - `delta_cases` / `delta_units`: Signed transaction delta.
   - `reason`: Machine event or supervisor adjustment rationale.
   - `created_at`: UTC timestamp.
2. The UI provides instant filtering by date preset (`Today`, `Yesterday`, `This Week`, `This Month`, `Custom Range`) with Indian Standard Time (`IST` / `en-IN`) timestamp presentation.

