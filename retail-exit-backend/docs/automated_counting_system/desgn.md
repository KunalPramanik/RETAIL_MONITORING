# Design Document

## Database Schema Utilization
* Product: Defines item names, categories, and ML class_id bindings.
* MaterialInventoryBalance: Holds the current running total.
* MaterialMovementLedger: Tracks every change (Inference Count vs Manual Adjustment).

## API Endpoints
* POST /inventory/count/trigger: Triggers a synchronous CV recount.
* POST /inventory/adjust: Appends a manual operator correction.