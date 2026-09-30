# System Architecture

## Flow
1. **Edge Node**: Camera frames captured via CameraStreamSession.
2. **Inference**: YOLOX predicts bounding boxes.
3. **Counter Engine**: AutomatedCountingEngine groups boxes by Class ID, queries the DB for matching Product variants, and tallies the count.
4. **Ledger**: Tally is committed to MaterialMovementLedger.
5. **API Override**: inventory_routes.py provides REST endpoints for manual adjustment.