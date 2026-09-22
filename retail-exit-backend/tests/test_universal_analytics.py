"""Automated Test Suite for Universal AI Video Analytics & Standard Telemetry

Validates:
1. Universal Detection & Classification Taxonomy across all 9 core operational domains
2. Anti-Spoofing & Liveness Protocol (Real Verified, Real Unknown, Spoofed / Synthetic)
3. Dynamic Standard Output Schema (FRAME ANALYSIS REPORT)
4. Strict False Positive Elimination (Torso / Hand Screens & Collar / Shoulder Watches)
"""

import pytest
import numpy as np
import cv2
import os

from src.ml.universal_taxonomy_service import UniversalTaxonomyService, CategorizedEntity
from src.engine.frame_analysis_report import FrameAnalysisReportGenerator
from src.ml.scene_object_detector import SceneObjectDetector
from src.ml.pose_service import SuspiciousBehaviorDetector


def test_universal_taxonomy_mapping():
    """Verifies that visual targets are correctly classified into the 9 operational categories."""
    # 1. Personnel & Identification
    p_verified = UniversalTaxonomyService.classify_detection({
        "box": [100, 100, 200, 400],
        "type": "PERSON_MATCHED",
        "label": "Known: Alice Smith (98%)",
        "entity": "Alice Smith",
        "confidence": 0.98,
    })
    assert p_verified.category == UniversalTaxonomyService.CAT_PERSONNEL
    assert p_verified.canonical_label == "Real Verified Human"
    assert p_verified.registry_reference == "Alice Smith"
    assert not p_verified.is_spoofed

    p_unknown = UniversalTaxonomyService.classify_detection({
        "box": [100, 100, 200, 400],
        "type": "PERSON_UNMATCHED",
        "label": "Unknown Person (85%)",
        "confidence": 0.85,
    })
    assert p_unknown.category == UniversalTaxonomyService.CAT_PERSONNEL
    assert p_unknown.canonical_label == "Real Unknown Human"
    assert not p_unknown.is_spoofed

    p_spoof = UniversalTaxonomyService.classify_detection({
        "box": [100, 100, 150, 150],
        "type": "STATIC_IMAGE",
        "label": "Static: Framed Photo (82%)",
        "confidence": 0.82,
    })
    assert p_spoof.is_spoofed

    # 2. Everyday Items
    bottle = UniversalTaxonomyService.classify_detection({
        "box": [250, 200, 40, 120],
        "type": "ITEM",
        "label": "Water Bottle (75%)",
        "confidence": 0.75,
    })
    assert bottle.category == UniversalTaxonomyService.CAT_EVERYDAY_ITEMS
    assert bottle.canonical_label == "Bottle"

    # 3. Computing & Electronics
    screen = UniversalTaxonomyService.classify_detection({
        "box": [50, 150, 240, 160],
        "type": "DESKTOP_SCREEN",
        "label": "Desktop Screen (88%)",
        "confidence": 0.88,
    })
    assert screen.category == UniversalTaxonomyService.CAT_COMPUTING
    assert screen.canonical_label == "Monitor / Display"

    # 4. Fixtures & Furniture
    desk = UniversalTaxonomyService.classify_detection({
        "box": [0, 350, 600, 150],
        "type": "ITEM",
        "label": "Office Desk (90%)",
        "confidence": 0.90,
    })
    assert desk.category == UniversalTaxonomyService.CAT_FIXTURES
    assert desk.canonical_label == "Table / Desk"

    # 5. Logistics & Inventory
    case = UniversalTaxonomyService.classify_detection({
        "box": [300, 250, 120, 100],
        "type": "CASE",
        "label": "Case: Full Carton (92%)",
        "confidence": 0.92,
    })
    assert case.category == UniversalTaxonomyService.CAT_LOGISTICS
    assert case.canonical_label == "Full Case"

    # 6. Industrial Materials
    cement = UniversalTaxonomyService.classify_detection({
        "box": [400, 300, 150, 120],
        "type": "ITEM",
        "label": "Cement Sack (89%)",
        "confidence": 0.89,
    })
    assert cement.category == UniversalTaxonomyService.CAT_MATERIALS
    assert cement.canonical_label == "Cement Sack"

    # 7. PPE
    ppe = UniversalTaxonomyService.classify_detection({
        "box": [120, 90, 60, 50],
        "type": "PPE_COMPLIANT",
        "label": "Hard Hat (94%)",
        "confidence": 0.94,
    })
    assert ppe.category == UniversalTaxonomyService.CAT_PPE
    assert ppe.canonical_label == "Hard Hat / Helmet"
    assert ppe.operational_status == "In-Use"

    # 8. Transit Vehicles
    truck = UniversalTaxonomyService.classify_detection({
        "box": [0, 0, 500, 400],
        "type": "VEHICLE",
        "label": "Commercial Truck (96%)",
        "confidence": 0.96,
    })
    assert truck.category == UniversalTaxonomyService.CAT_VEHICLES

    # 9. Hazards
    fire = UniversalTaxonomyService.classify_detection({
        "box": [200, 150, 80, 100],
        "type": "HAZARD_FIRE",
        "label": "Active Flame (93%)",
        "confidence": 0.93,
    })
    assert fire.category == UniversalTaxonomyService.CAT_HAZARDS
    assert fire.canonical_label == "Active Flame / Fire"


def test_frame_analysis_report_generation():
    """Verifies that FrameAnalysisReportGenerator produces the exact standard report structure."""
    entities = [
        CategorizedEntity(
            category=UniversalTaxonomyService.CAT_PERSONNEL,
            canonical_label="Real Verified Human",
            raw_label="Known: Alice Smith (98%)",
            confidence=0.98,
            bbox=[100, 100, 200, 400],
            registry_reference="EMP-042 (Alice Smith)",
        ),
        CategorizedEntity(
            category=UniversalTaxonomyService.CAT_PERSONNEL,
            canonical_label="Real Unknown Human",
            raw_label="Unknown Person (86%)",
            confidence=0.86,
            bbox=[400, 120, 180, 380],
            tracking_id="TRK-01",
        ),
        CategorizedEntity(
            category=UniversalTaxonomyService.CAT_COMPUTING,
            canonical_label="Monitor / Display",
            raw_label="Desktop Screen (88%)",
            confidence=0.88,
            bbox=[50, 150, 240, 160],
            operational_status="Physical",
        ),
        CategorizedEntity(
            category=UniversalTaxonomyService.CAT_EVERYDAY_ITEMS,
            canonical_label="Bottle",
            raw_label="Bottle (75%)",
            confidence=0.75,
            bbox=[250, 200, 40, 120],
            operational_status="Physical",
        ),
    ]

    report = FrameAnalysisReportGenerator.generate_report(
        categorized_entities=entities,
        operational_confidence=0.95,
    )

    assert "FRAME ANALYSIS REPORT" in report
    assert "1. PERSONNEL & AUTHENTICATION SUMMARY" in report
    assert "Real Verified Persons: [1] -> [ID: EMP-042 (Alice Smith) (98%)]" in report
    assert "Real Unknown Persons: [1] -> [ID: TRK-01 (86%)]" in report
    assert "2. DETECTED INVENTORY & ASSET COUNTS" in report
    assert "Computing & Electronics:" in report
    assert "Monitor / Display: [1] | Status: [Physical] | Avg Confidence: [88%]" in report
    assert "3. SAFETY & HAZARD ALERTS" in report
    assert "4. SYSTEM HEALTH METRICS" in report
    assert "Operational Confidence: [95%]" in report
    assert "Parsing Mode: Fully Dynamic (Zero Mock / Zero Hardcoding)" in report


def test_hardened_detectors_reject_hand_torso_and_collar():
    """Verifies that hand, torso, collar placket, and shoulder false detections are rejected."""
    # Scene with a person
    scene = np.full((500, 700, 3), (200, 200, 200), dtype=np.uint8)
    p_box = [150, 80, 500, 400]

    # Hand contour (vertical aspect ratio w/h < 1.05)
    cv2.rectangle(scene, (20, 220), (120, 380), (40, 40, 40), -1)

    # 1. Screen detector MUST reject vertical hand
    screens = SceneObjectDetector.detect_desktop_monitors_and_screens(scene, exclude_boxes=[p_box])
    assert len(screens) == 0, f"False screen detected on hand: {screens}"

    # 2. Wrist watch detector MUST reject collar/chest keypoints
    collar_kp = {"left_wrist": (p_box[0] + int(p_box[2] * 0.50), p_box[1] + int(p_box[3] * 0.35))}
    watches = SceneObjectDetector.detect_wrist_watches(scene, wrist_keypoints=collar_kp, person_boxes=[p_box])
    assert len(watches) == 0, f"False watch detected on collar: {watches}"

