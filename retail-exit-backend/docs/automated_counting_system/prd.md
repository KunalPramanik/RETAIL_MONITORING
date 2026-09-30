# Product Requirements Document (PRD)

## Objective
Automated counting system for identifying and tallying all types of goods (boxes, cement sacks, iron rods).

## Core Requirements
1. **Dynamic Identification**: Capture Product IDs, item names, and categories using dynamic DB mapping (No hardcoding).
2. **Precise Counts**: Utilize YOLOX bounding boxes + Dense NMS for highly occluded or stacked goods.
3. **Manual Override**: Allow operators to flag discrepancies, trigger recounts, or input manual adjustments directly into the inventory ledger.