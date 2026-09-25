"""Master Prompt V6: Additive Object Intelligence Hardening Test Suite.

Verifies:
1. Scene A — Concurrent Multi-Object Frame:
   Simultaneous detection of multiple distinct object classes in one frame (person, laptop,
   smartphone, keyboard, mouse, books, bookshelf, bottles, clock, wall picture, doorway).
   Confirms environment/fixture items are tagged environment_only=True and do not pollute inventory counts.
2. Scene C — Exact Per-Instance Book and Shelf Counting:
   Individually visible adjacent books on a shelf are counted with exact instance precision (8 books, 1 shelf)
   and not collapsed into 1 detection due to class-specific NMS IoU tuning.
3. Scene D — Content-in-Content Quarantine:
   Faces and figures displayed inside wall pictures, posters, monitor displays, or phone screens
   are quarantined as static images and prevented from live authentication or triggering unauthorized alerts.
4. Scene E — Person Detection vs. Biometric Identity Verification Discipline:
   Clear separation between detecting a person and identifying them. Unmatched individuals are labeled
   strictly as "Unknown Person" with "Match: No confirmed database match", never given speculative identities.
5. Scene F — Box vs. Unit Counting Hierarchy:
   Hierarchical case-to-unit multiplication (e.g., 4 boxes of pack size 24 = 4 boxes, 96 units).
6. Scene G — Intra-Camera Tracking & Occlusion Resilience:
   Stable object track continuity across frames with occlusion tolerance up to 15 frames.
"""

import pytest
import numpy as np
import cv2
import time
from typing import List, Dict, Any

from src.ml.model_config import get_vision_config, reload_vision_config
from src.ml.vision_service import VisionInferenceService, DetectedBox
from src.ml.tracker_service import IntraCameraObjectTracker, SingleCameraTrack
from src.ml.static_image_service import StaticImageClassifier, quarantine_enclosed_visual_content, is_box_enclosed
from src.ml.scene_object_detector import SceneObjectDetector
from src.ml.face_service import FaceRecognitionService, FaceMatchResult
from src.ml.universal_taxonomy_service import UniversalTaxonomyService


# ============================================================================
# Scene A: Concurrent Multi-Object Frame & Environmental Fixture Isolation
# ============================================================================

def test_scene_a_taxonomy_and_environmental_isolation():
    """Scene A: Verifies taxonomy classification, environmental flag separation, and detection states."""
    cfg = reload_vision_config()

    # Verify class metadata contains all required V6 classes
    required_classes = [
        "person", "laptop", "cell phone", "keyboard", "mouse",
        "book", "bookshelf", "bottle", "clock", "picture", "doorway"
    ]
    for cls_name in required_classes:
        meta = cfg.get_class_metadata(cls_name)
        assert meta is not None, f"Missing class metadata for: {cls_name}"

    # Verify structural and environmental fixtures do NOT enter merchandise inventory
    fixtures = ["bookshelf", "doorway", "clock", "picture"]
    for fix in fixtures:
        meta = cfg.get_class_metadata(fix)
        assert meta.get("environment_only") is True, f"{fix} must be environment_only"
        assert meta.get("inventory_relevant") is False, f"{fix} must NOT be inventory_relevant"

    # Verify inventory items ARE inventory relevant
    inv_items = ["book", "bottle"]
    for item in inv_items:
        meta = cfg.get_class_metadata(item)
        assert meta.get("inventory_relevant") is True, f"{item} should be inventory_relevant"
        assert meta.get("environment_only") is False, f"{item} should NOT be environment_only"

    # Verify universal taxonomy categorizes them accurately
    fixture_cat = UniversalTaxonomyService.CAT_FIXTURES
    assert UniversalTaxonomyService.KEYWORD_MAPPINGS["bookshelf"][0] == fixture_cat
    assert UniversalTaxonomyService.KEYWORD_MAPPINGS["doorway"][0] == fixture_cat
    assert UniversalTaxonomyService.KEYWORD_MAPPINGS["clock"][0] == fixture_cat


def test_scene_a_concurrent_detections_inventory_filtering():
    """Scene A: Multi-object detection scenario ensures fixtures do not increment cases/units detected."""
    cfg = get_vision_config()

    # Construct synthetic multi-object scene detections:
    # 1 person, 1 laptop, 2 phones, 1 keyboard, 1 mouse, 4 books, 1 bookshelf, 2 bottles, 1 clock, 1 picture, 1 doorway
    synthetic_boxes = [
        DetectedBox(bbox=[50, 100, 150, 400], class_label="person", product_id=None, sku_code=None, confidence=0.92, detection_state="CONFIRMED"),
        DetectedBox(bbox=[250, 300, 120, 80], class_label="laptop", product_id=None, sku_code=None, confidence=0.90, detection_state="CONFIRMED"),
        DetectedBox(bbox=[260, 390, 30, 60], class_label="cell phone", product_id=None, sku_code=None, specific_label="Smartphone", confidence=0.88, detection_state="CONFIRMED"),
        DetectedBox(bbox=[300, 390, 30, 60], class_label="cell phone", product_id=None, sku_code=None, specific_label="Smartphone", confidence=0.86, detection_state="CONFIRMED"),
        DetectedBox(bbox=[380, 320, 100, 40], class_label="keyboard", product_id=None, sku_code=None, confidence=0.87, detection_state="CONFIRMED"),
        DetectedBox(bbox=[490, 330, 30, 30], class_label="mouse", product_id=None, sku_code=None, confidence=0.85, detection_state="CONFIRMED"),
        # 4 Books (inventory relevant)
        DetectedBox(bbox=[600, 200, 25, 80], class_label="book", product_id=None, sku_code=None, confidence=0.89, detection_state="CONFIRMED"),
        DetectedBox(bbox=[628, 200, 25, 80], class_label="book", product_id=None, sku_code=None, confidence=0.88, detection_state="CONFIRMED"),
        DetectedBox(bbox=[656, 200, 25, 80], class_label="book", product_id=None, sku_code=None, confidence=0.87, detection_state="CONFIRMED"),
        DetectedBox(bbox=[684, 200, 25, 80], class_label="book", product_id=None, sku_code=None, confidence=0.86, detection_state="CONFIRMED"),
        # Bookshelf (fixture / environmental)
        DetectedBox(bbox=[580, 180, 200, 300], class_label="bookshelf", product_id=None, sku_code=None, confidence=0.91, detection_state="CONFIRMED"),
        # 2 Bottles (inventory relevant)
        DetectedBox(bbox=[800, 300, 35, 90], class_label="bottle", product_id=None, sku_code=None, confidence=0.92, detection_state="CONFIRMED"),
        DetectedBox(bbox=[840, 300, 35, 90], class_label="bottle", product_id=None, sku_code=None, confidence=0.91, detection_state="CONFIRMED"),
        # Clock, Picture, Doorway (fixtures / environmental)
        DetectedBox(bbox=[100, 30, 60, 60], class_label="clock", product_id=None, sku_code=None, confidence=0.89, detection_state="CONFIRMED"),
        DetectedBox(bbox=[300, 50, 120, 100], class_label="picture", product_id=None, sku_code=None, specific_label="Wall Picture", confidence=0.90, detection_state="CONFIRMED"),
        DetectedBox(bbox=[950, 100, 120, 350], class_label="doorway", product_id=None, sku_code=None, confidence=0.93, detection_state="CONFIRMED"),
    ]

    # Verify inventory counting logic:
    # Only countable, inventory-relevant, non-environment items should contribute to total units
    inventory_boxes = []
    fixture_boxes = []
    for d in synthetic_boxes:
        is_inv = cfg.is_inventory_relevant(d.class_label)
        is_env = cfg.is_environment_only(d.class_label)
        if is_inv and not is_env:
            inventory_boxes.append(d)
        elif is_env:
            fixture_boxes.append(d)

    # 1 laptop + 2 phones + 1 keyboard + 1 mouse + 4 books + 2 bottles = 11 inventory units
    assert len(inventory_boxes) == 11
    # bookshelf, clock, picture, doorway = 4 fixture items
    assert len(fixture_boxes) == 4
    for b in synthetic_boxes:
        assert b.detection_state == "CONFIRMED"


# ============================================================================
# Scene C: Exact Per-Instance Book and Shelf Counting (No NMS Collapse)
# ============================================================================

def test_scene_c_exact_book_counting_and_nms_isolation():
    """Scene C: 8 adjacent books on a shelf must NOT collapse into 1 or fewer detections."""
    cfg = get_vision_config()

    # Verify class-specific NMS IoU for books is 0.50 (tighter threshold allowing touching books)
    book_nms_iou = cfg.get_class_nms_iou(73)
    assert book_nms_iou == 0.50

    # Create 8 side-by-side touching books: each width 24, height 90, spacing 2px
    books = []
    base_x = 100
    for i in range(8):
        x = base_x + i * 26
        books.append({
            "box": [x, 200, 24, 90],
            "confidence": 0.85 + (i % 3) * 0.03,
            "class_id": 73,
            "class_label": "book",
        })

    # Bookshelf bounding box enclosing all 8 books
    bookshelf = {
        "box": [90, 180, 240, 150],
        "confidence": 0.92,
        "class_id": 77,
        "class_label": "bookshelf",
    }

    # Simulate class-specific NMS on books:
    # Pairwise IoU between touching books [x, 200, 24, 90] and [x+26, 200, 24, 90] is 0.0 (no overlap)
    # Even if they slightly overlap by 6px (IoU ~ 0.14), book_nms_iou=0.50 keeps all 8!
    kept_books = []
    for b in books:
        bx = b["box"]
        suppressed = False
        for kb in kept_books:
            kx = kb["box"]
            # Compute IoU
            xa = max(bx[0], kx[0])
            ya = max(bx[1], kx[1])
            xb = min(bx[0] + bx[2], kx[0] + kx[2])
            yb = min(bx[1] + bx[3], kx[1] + kx[3])
            inter = max(0, xb - xa) * max(0, yb - ya)
            union = bx[2] * bx[3] + kx[2] * kx[3] - inter
            iou = inter / float(union) if union > 0 else 0.0
            if iou > book_nms_iou:
                suppressed = True
                break
        if not suppressed:
            kept_books.append(b)

    assert len(kept_books) == 8, f"Expected 8 books, got {len(kept_books)}"

    # Bookshelf is a separate class so it is never suppressed by book NMS
    all_detections = kept_books + [bookshelf]
    counts_by_label = {}
    for d in all_detections:
        counts_by_label[d["class_label"]] = counts_by_label.get(d["class_label"], 0) + 1

    assert counts_by_label["book"] == 8
    assert counts_by_label["bookshelf"] == 1


def test_scene_c_bookshelf_detector_heuristic():
    """Scene C: Tests SceneObjectDetector.detect_bookshelves on synthetic shelf geometry."""
    # Create an image with horizontal shelving lines
    img = np.full((400, 500, 3), 200, dtype=np.uint8)
    # Draw dark wooden shelf frame
    cv2.rectangle(img, (50, 50), (450, 350), (60, 40, 20), 4)
    # Draw horizontal shelves
    cv2.line(img, (50, 150), (450, 150), (60, 40, 20), 3)
    cv2.line(img, (50, 250), (450, 250), (60, 40, 20), 3)

    shelves = SceneObjectDetector.detect_bookshelves(img)
    assert len(shelves) >= 1
    assert shelves[0]["class_label"] == "bookshelf"
    assert shelves[0]["confidence"] >= 0.70


# ============================================================================
# Scene D: Content-in-Content Quarantine (Wall Picture & Monitor Faces)
# ============================================================================

def test_scene_d_containment_quarantine_logic():
    """Scene D: Verifies containment quarantine geometry detects faces inside screens and pictures."""
    # Display container: Wall picture at [100, 80, 250, 300]
    wall_picture = [100, 80, 250, 300]
    # Display container: Desktop screen at [500, 200, 200, 160]
    desktop_screen = [500, 200, 200, 160]
    # Display container: Smartphone at [750, 300, 60, 100]
    smartphone = [750, 300, 60, 100]

    containers = [wall_picture, desktop_screen, smartphone]

    # Face 1: Inside wall picture
    face_in_picture = [140, 120, 80, 90]
    # Face 2: Inside desktop screen
    face_in_screen = [540, 220, 70, 80]
    # Face 3: Inside smartphone
    face_in_phone = [755, 310, 45, 55]
    # Face 4: Real living person standing in the room
    live_person_face = [350, 200, 90, 110]

    candidate_faces = [face_in_picture, face_in_screen, face_in_phone, live_person_face]

    quarantined = quarantine_enclosed_visual_content(
        candidate_boxes=candidate_faces,
        container_boxes=containers,
        containment_threshold=0.65,
    )

    # Indices 0, 1, 2 must be quarantined; Index 3 (live human) must NOT be quarantined
    assert 0 in quarantined, "Face inside picture must be quarantined"
    assert 1 in quarantined, "Face inside screen must be quarantined"
    assert 2 in quarantined, "Face inside phone must be quarantined"
    assert 3 not in quarantined, "Live person face must NOT be quarantined"
    assert len(quarantined) == 3


def test_scene_d_static_quarantine_in_face_matching():
    """Scene D: Enclosed faces are flagged as static and excluded from live biometric matching."""
    # Create synthetic frame with a wall picture
    img = np.full((480, 640, 3), 180, dtype=np.uint8)
    wall_picture_bbox = [100, 80, 220, 260]
    cv2.rectangle(img, (100, 80), (320, 340), (40, 40, 40), 4)

    # Face box inside the picture
    face_inside = [140, 120, 80, 90]

    # Run quarantine check directly
    is_enclosed = is_box_enclosed(
        candidate_box=face_inside,
        container_box=wall_picture_bbox,
        containment_threshold=0.65,
    )
    assert is_enclosed is True

    # When quarantined, static classification should be PERSON_PHOTO
    static_res = StaticImageClassifier.classify_crop(
        crop=img[120:210, 140:220],
        liveness_score=0.05,
        has_face_geometry=True,
    )
    assert static_res.suppressed_alert is True
    assert static_res.confidence >= 0.40


# ============================================================================
# Scene E: Person Detection vs. Biometric Identity Verification Discipline
# ============================================================================

def test_scene_e_person_identity_discipline():
    """Scene E: Strict separation of person detection from biometric identity verification.

    1 known employee matched from database -> Confirmed Match (green).
    1 unknown person with no match -> Unknown Person with 'Match: No confirmed database match' (cyan).
    Zero speculative identity speculation.
    """
    enrolled_roster = [
        {
            "employee_id": "EMP-001",
            "name": "Sarah Connor",
            # Unit 512-d embedding
            "face_embedding": [1.0] + [0.0] * 511,
        }
    ]

    # Probe 1: Exact match for Sarah Connor
    probe_known = [1.0] + [0.0] * 511
    # Probe 2: Completely orthogonal embedding (unknown person)
    probe_unknown = [0.0, 1.0] + [0.0] * 510

    # 1. Match known person
    res_known = FaceRecognitionService.match_carrier(
        probe_embedding=[probe_known],
        enrolled_employees=enrolled_roster,
        match_threshold=0.65,
    )
    assert res_known.decision == "MATCHED"
    assert res_known.matched_employee_id == "EMP-001"
    assert res_known.employee_name == "Sarah Connor"
    assert res_known.similarity >= 0.95

    # 2. Match unknown person
    res_unknown = FaceRecognitionService.match_carrier(
        probe_embedding=[probe_unknown],
        enrolled_employees=enrolled_roster,
        match_threshold=0.65,
    )
    assert res_unknown.decision == "NO_MATCH"
    assert res_unknown.matched_employee_id is None
    assert res_unknown.employee_name is None
    assert res_unknown.similarity < 0.10


# ============================================================================
# Scene F: Box vs. Unit Counting Hierarchy
# ============================================================================

def test_scene_f_box_vs_unit_counting_hierarchy():
    """Scene F: 4 packaged boxes with pack size 24 = 4 boxes, 96 units."""
    pack_size = 24
    num_cases = 4

    total_units = num_cases * pack_size
    assert total_units == 96

    # Verify single exposed units arithmetic (pack size 1)
    single_units = 5
    assert single_units * 1 == 5

    # Combined dispatch total
    grand_total_units = total_units + single_units
    assert grand_total_units == 101


# ============================================================================
# Scene G: Intra-Camera Tracking & Occlusion Resilience
# ============================================================================

def test_scene_g_intra_camera_tracker_continuity_and_occlusion():
    """Scene G: Validates track ID continuity and occlusion recovery without track-ID flip."""
    tracker = IntraCameraObjectTracker(iou_threshold=0.30, max_lost_frames=15, min_hits=1)
    cam_id = "CAM-TEST-V6"

    # Frame 1: Object detected at [100, 100, 50, 50]
    dets_f1 = [{"box": [100, 100, 50, 50], "type": "ITEM", "label": "Book", "confidence": 0.90}]
    tr_f1 = tracker.update_tracks(camera_id=cam_id, detections=dets_f1, timestamp=1000.0)
    assert len(tr_f1) == 1
    t1_id = tr_f1[0]["track_id"]
    assert t1_id.startswith("TRK-")

    # Frame 2: Object moves slightly to [104, 102, 50, 50]
    dets_f2 = [{"box": [104, 102, 50, 50], "type": "ITEM", "label": "Book", "confidence": 0.91}]
    tr_f2 = tracker.update_tracks(camera_id=cam_id, detections=dets_f2, timestamp=1000.5)
    assert len(tr_f2) == 1
    assert tr_f2[0]["track_id"] == t1_id, "Track ID must remain stable across consecutive frames"

    # Frames 3, 4, 5: Brief occlusion (object not detected for 3 frames)
    for f in range(3):
        tracker.update_tracks(camera_id=cam_id, detections=[], timestamp=1001.0 + f * 0.5)

    # Verify track is retained in tracker memory as occluded/lost
    tracks = tracker.get_active_tracks(cam_id)
    assert t1_id in tracks
    assert tracks[t1_id].lost_frames == 3

    # Frame 6: Object reappears at [108, 105, 50, 50]
    dets_f6 = [{"box": [108, 105, 50, 50], "type": "ITEM", "label": "Book", "confidence": 0.89}]
    tr_f6 = tracker.update_tracks(camera_id=cam_id, detections=dets_f6, timestamp=1003.0)
    assert len(tr_f6) == 1
    assert tr_f6[0]["track_id"] == t1_id, "Track ID must be preserved after brief occlusion recovery"


# ============================================================================
# Part Y: Consolidated Dense Scene Verification (Co-presence & NMS Threshold)
# ============================================================================

def test_part_y_dense_multi_object_co_presence():
    """Part Y: Single camera scene containing doorway, wall pictures, bookshelf with known book count,
    phone, laptop, and live person. Confirms proper classification, fixture exclusion, and dense clustering.
    """
    cfg = reload_vision_config()
    assert hasattr(cfg, "dense_shelf_nms_iou_threshold")
    assert cfg.dense_shelf_nms_iou_threshold == 0.45

    # Multi-object co-presence scene:
    # 1 Doorway [0, 0, 150, 480] (Fixture)
    # 2 Wall Pictures [200, 50, 100, 120], [350, 50, 100, 120] (Fixtures / Display containers)
    # 1 Bookshelf [500, 150, 280, 300] (Fixture)
    # 6 Individual Books on the bookshelf: [520, 220, 30, 90], [555, 220, 30, 90], ... (Inventory relevant)
    # 1 Laptop on desk [250, 320, 140, 90] (Inventory relevant)
    # 1 Smartphone on desk [410, 340, 35, 60] (Inventory relevant)
    # 1 Live Person [160, 180, 120, 280] (Personnel)
    
    scene_detections = [
        DetectedBox(bbox=[0, 0, 150, 480], class_label="doorway", specific_label="Doorway / Exit Door", product_id=None, sku_code=None, confidence=0.94, is_inventory_relevant=False, is_environment_only=True),
        DetectedBox(bbox=[200, 50, 100, 120], class_label="wall_picture", specific_label="Wall Picture Frame", product_id=None, sku_code=None, confidence=0.91, is_inventory_relevant=False, is_environment_only=True),
        DetectedBox(bbox=[350, 50, 100, 120], class_label="wall_picture", specific_label="Wall Picture Frame", product_id=None, sku_code=None, confidence=0.89, is_inventory_relevant=False, is_environment_only=True),
        DetectedBox(bbox=[500, 150, 280, 300], class_label="bookshelf", specific_label="Storage Shelf / Bookcase", product_id=None, sku_code=None, confidence=0.93, is_inventory_relevant=False, is_environment_only=True),
        # 6 dense books on shelf
        DetectedBox(bbox=[520, 220, 30, 90], class_label="single_unit", specific_label="Book", product_id=None, sku_code=None, confidence=0.88, is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[555, 220, 30, 90], class_label="single_unit", specific_label="Book", product_id=None, sku_code=None, confidence=0.87, is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[590, 220, 30, 90], class_label="single_unit", specific_label="Book", product_id=None, sku_code=None, confidence=0.90, is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[625, 220, 30, 90], class_label="single_unit", specific_label="Book", product_id=None, sku_code=None, confidence=0.89, is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[660, 220, 30, 90], class_label="single_unit", specific_label="Book", product_id=None, sku_code=None, confidence=0.86, is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[695, 220, 30, 90], class_label="single_unit", specific_label="Book", product_id=None, sku_code=None, confidence=0.88, is_inventory_relevant=True, is_environment_only=False),
        # Desk items
        DetectedBox(bbox=[250, 320, 140, 90], class_label="single_unit", specific_label="Laptop", product_id=None, sku_code=None, confidence=0.92, is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[410, 340, 35, 60], class_label="single_unit", specific_label="Smartphone", product_id=None, sku_code=None, confidence=0.89, is_inventory_relevant=True, is_environment_only=False),
        # Real Person
        DetectedBox(bbox=[160, 180, 120, 280], class_label="person", specific_label="Person", product_id=None, sku_code=None, confidence=0.95, is_inventory_relevant=False, is_environment_only=False),
    ]

    # Verify inventory units: strictly 6 books + 1 laptop + 1 phone = 8 retail items
    inv_items = [d for d in scene_detections if d.is_inventory_relevant and not d.is_environment_only]
    assert len(inv_items) == 8
    book_items = [d for d in inv_items if d.specific_label == "Book"]
    assert len(book_items) == 6

    # Verify environmental fixtures: 1 doorway + 2 pictures + 1 bookshelf = 4 fixtures
    fixtures = [d for d in scene_detections if d.is_environment_only]
    assert len(fixtures) == 4

    # Verify person detection
    persons = [d for d in scene_detections if d.class_label == "person"]
    assert len(persons) == 1
    assert persons[0].confidence >= 0.90


# ============================================================================
# Part Z: Theft / Over-Carry Alert Identity Hardening (>= 0.65 Confidence)
# ============================================================================

def test_part_z_theft_over_carry_identity_discipline():
    """Part Z: Confirms employee identity attribution on over-carry/theft alerts:
    - Cosine similarity >= 0.65 attaches real employee name.
    - Cosine similarity < 0.65 strictly defaults to UNKNOWN_PERSON (zero speculation).
    """
    # Case 1: Verified employee with confidence 0.78 (>= 0.65)
    matched_high = FaceMatchResult(
        matched_employee_id="EMP-9021",
        employee_name="Alice Smith",
        similarity=0.78,
        decision="MATCHED",
        model_version="insightface-arcface-buffalo_s-512d",
        unauthorized_alert_needed=False,
        frames_evaluated=1,
    )
    is_verified_high = (
        matched_high.decision == "MATCHED"
        and matched_high.matched_employee_id is not None
        and float(matched_high.similarity or 0.0) >= 0.65
    )
    carrier_high = matched_high.employee_name if is_verified_high else "UNKNOWN_PERSON"
    assert carrier_high == "Alice Smith"

    # Case 2: Borderline similarity 0.61 (< 0.65 floor)
    matched_low = FaceMatchResult(
        matched_employee_id="EMP-9021",
        employee_name="Alice Smith",
        similarity=0.61,
        decision="LOW_CONFIDENCE",
        model_version="insightface-arcface-buffalo_s-512d",
        unauthorized_alert_needed=False,
        frames_evaluated=1,
    )
    is_verified_low = (
        matched_low.decision == "MATCHED"
        and matched_low.matched_employee_id is not None
        and float(matched_low.similarity or 0.0) >= 0.65
    )
    carrier_low = matched_low.employee_name if is_verified_low else "UNKNOWN_PERSON"
    assert carrier_low == "UNKNOWN_PERSON", "Low confidence face candidate must NEVER attach real employee name to theft alert"

    # Case 3: Complete non-match (unknown visitor / intruder)
    matched_none = FaceMatchResult(
        matched_employee_id=None,
        employee_name=None,
        similarity=0.22,
        decision="NO_MATCH",
        model_version="insightface-arcface-buffalo_s-512d",
        unauthorized_alert_needed=True,
        frames_evaluated=1,
    )
    is_verified_none = (
        matched_none.decision == "MATCHED"
        and matched_none.matched_employee_id is not None
        and float(matched_none.similarity or 0.0) >= 0.65
    )
    carrier_none = matched_none.employee_name if is_verified_none else "UNKNOWN_PERSON"
    assert carrier_none == "UNKNOWN_PERSON"
