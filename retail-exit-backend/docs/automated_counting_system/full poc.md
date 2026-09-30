# Full Proof of Concept (POC) Flow

1. Operator points camera at a pallet of Cement Sacks.
2. System infers 42 items.
3. DB maps Class ID 1005 to "Portland Cement 50kg".
4. System registers 42 units in Ledger.
5. Operator counts 43 manually.
6. Operator submits POST /inventory/adjust with +1.
7. Ledger shows: ML(+42), Manual(+1). Total = 43.