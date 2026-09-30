# System Rules

1. **Zero Hardcoding**: All class-to-product mappings must query the Postgres database.
2. **Zero Mock Data**: If the camera is offline, count is 0. No fallback images.
3. **Immutable Ledger**: Manual adjustments do not overwrite ML counts; they append a correction row to the ledger for auditability.