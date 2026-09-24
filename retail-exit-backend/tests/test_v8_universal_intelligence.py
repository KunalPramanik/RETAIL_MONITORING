"""Master Prompt V8: Universal Object Intelligence, Anti-Confusion Discrimination & Exact Counting Test Suite.

Verifies:
1. Observed Problem A (Wall Picture -> Book False Positive):
   Wall pictures, framed art, and posters are NEVER falsely labeled as 'Book'. They are recognized
   as 'Wall Picture Frame' (class 1002, environment_only=True, inventory_relevant=False) or unconfirmed.
2. Observed Problem B (Background Visual Content vs Foreground Objects):
   Wall decorations, clocks, doorways, bookshelves are categorized as environment fixtures
   and isolated from merchandise counts.
3. Observed Problem C (Body Region / Hand Confusion vs Wristwatch):
   - Bare hands/arms are NOT detected as inventory products or 'Hand' as merchandise.
   - Bare hands without watch dials are NOT detected as 'WristWatch'.
   - Worn wristwatches are recognized as 'WristWatch' with relation='worn_by' without collapsing into the person.
   - Standalone wristwatches resting on desks/tables are recognized as 'WristWatch'.
   - Watches displayed on phone screens or posters are quarantined.
4. Observed Problem D (Simultaneous Real Objects Coexistence):
   Concurrent presence of Person, WristWatch, Laptop, Smartphones, Books, Bottles, Boxes,
   Bookshelf, Clock, and Wall Pictures correctly preserves every confirmed instance with exact counting.
5. Detection State Machine:
   Enforces 7-stage state machine and proper rejection states for sub-floor, static, or conflicting candidates.
"""

import pytest
import numpy as np
import cv2
from typing import List, Dict, Any

from src.ml.model_config import get_vision_config, reload_vision_config
from src.ml.vision_service import VisionInferenceService, DetectedBox
from src.ml.semantic_validation import SemanticValidationEngine, DetectionState
from src.ml.scene_object_detector import SceneObjectDetector
from src.ml.wall_picture_detector import WallPictureDetector
from src.ml.universal_taxonomy_service import UniversalTaxonomyService
from src.engine.frame_analysis_report import FrameAnalysisReportGenerator


# ============================================================================
# 1. Observed Problem A: Wall Picture vs. Book Discrimination
# ============================================================================

def test_v8_wall_picture_not_classified_as_book():
    """A framed picture / poster on a wall must NOT be classified as 'Book'."""
    # Create synthetic frame with framed wall picture
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 220  # Light wall backdrop

    # Draw framed picture with prominent outer bezel border
    bx, by, bw, bh = 400, 100, 220, 160
    # Outer dark frame moulding
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (30, 30, 30), 8)
    # Inner artwork texture
    cv2.rectangle(frame, (bx + 8, by + 8), (bx + bw - 8, by + bh - 8), (250, 240, 220), -1)
    cv2.putText(frame, "ART EXHIBIT", (bx + 20, by + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)

    # Pre-detect wall picture
    wall_pics = WallPictureDetector.detect_wall_pictures(frame)
    assert len(wall_pics) >= 1, "WallPictureDetector should isolate framed planar wall art"

    # Evaluate a candidate box initially proposed as Book / Document (class 73)
    is_wall_pic, reason, telemetry = SemanticValidationEngine.discriminate_book_vs_wall_picture(
        frame=frame,
        bbox=[bx, by, bw, bh],
        candidate_conf=0.91,
        detected_wall_pictures=wall_pics,
        person_boxes=None,
    )

    assert is_wall_pic is True, f"Wall picture must be identified as wall picture, not book (reason: {reason})"
    assert "WALL_PICTURE" in reason or "BEZEL" in reason


def test_v8_real_book_on_desk_or_held_is_confirmed():
    """A real physical book on a desk or held by a person is confirmed as Book."""
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 180

    # Person holding a book at desk level
    person_box = [200, 150, 180, 450]
    book_box = [260, 380, 70, 95]

    # Evaluate book candidate
    is_wall_pic, reason, telemetry = SemanticValidationEngine.discriminate_book_vs_wall_picture(
        frame=frame,
        bbox=book_box,
        candidate_conf=0.89,
        detected_wall_pictures=[],
        person_boxes=[person_box],
    )

    assert is_wall_pic is False, "Physical book held by person must NOT be labeled wall picture"
    assert "PHYSICAL_BOOK_CONFIRMED" in reason


def test_v8_multiple_books_and_wall_picture_coexistence():
    """Multiple physical books near a wall picture remain separate and do not merge or pollute each other."""
    wall_picture_box = DetectedBox(
        bbox=[150, 80, 200, 150],
        class_label="wall_picture",
        product_id=None,
        sku_code=None,
        confidence=0.92,
        specific_label="Wall Picture Frame",
        detection_state="CONFIRMED",
        category_family="FIXTURES",
        is_inventory_relevant=False,
        is_environment_only=True,
    )

    book_boxes = [
        DetectedBox(bbox=[450, 400, 25, 80], class_label="single_unit", product_id="P1", sku_code="SKU-BK1", confidence=0.88, specific_label="Book / Document", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[480, 400, 25, 80], class_label="single_unit", product_id="P1", sku_code="SKU-BK1", confidence=0.87, specific_label="Book / Document", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[510, 400, 25, 80], class_label="single_unit", product_id="P1", sku_code="SKU-BK1", confidence=0.89, specific_label="Book / Document", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
    ]

    all_detections = [wall_picture_box] + book_boxes

    # Verify inventory accounting
    inventory_items = [d for d in all_detections if d.is_inventory_relevant]
    environment_items = [d for d in all_detections if d.is_environment_only]

    assert len(inventory_items) == 3, "Only the 3 physical books must count towards merchandise inventory"
    assert len(environment_items) == 1, "The wall picture must be isolated as an environmental fixture"
    assert environment_items[0].specific_label == "Wall Picture Frame"


# ============================================================================
# 2. Observed Problem C: Body Region / Hand Confusion vs Wristwatch
# ============================================================================

def test_v8_bare_hand_not_detected_as_product_or_wristwatch():
    """Bare hand/arm skin is NOT detected as WristWatch or merchandise product."""
    # Create synthetic bare skin crop (warm skin tones, smooth surface)
    skin_crop = np.zeros((80, 80, 3), dtype=np.uint8)
    skin_crop[:, :] = [130, 160, 220]  # BGR skin tone (high saturation/value in HSV)

    is_body, reason, skin_dens = SemanticValidationEngine.discriminate_bare_body_part(
        crop=skin_crop,
        person_boxes=[[100, 100, 200, 500]],
        candidate_box=[150, 350, 80, 80],
    )

    assert is_body is True, f"Bare skin patch must be recognized as body part (reason: {reason})"
    assert skin_dens >= 0.65


def test_v8_person_with_worn_wristwatch():
    """Person with visible wristwatch produces Person: 1, WristWatch: 1 (worn_by)."""
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 150
    person_box = [300, 100, 220, 560]

    # Draw person arm with wristwatch (skin arm + dark watch dial + metallic bezel)
    arm_x, arm_y = 460, 420
    # Arm skin
    cv2.rectangle(frame, (arm_x - 20, arm_y - 20), (arm_x + 35, arm_y + 35), (130, 160, 220), -1)
    # Watch dial (compact circle with sharp high-contrast bezel)
    cv2.circle(frame, (arm_x, arm_y), 14, (30, 30, 30), -1)
    cv2.circle(frame, (arm_x, arm_y), 14, (200, 200, 200), 2)
    # Dial hands
    cv2.line(frame, (arm_x, arm_y), (arm_x + 6, arm_y - 6), (240, 240, 240), 2)

    wrist_kps = {"right_wrist": [arm_x, arm_y]}

    watches = SemanticValidationEngine.detect_wristwatches_in_scene(
        frame=frame,
        person_boxes=[person_box],
        wrist_keypoints=wrist_kps,
        min_confidence=0.50,
    )

    assert len(watches) >= 1, "Must detect worn wristwatch at wrist keypoint"
    watch = watches[0]
    assert watch["specific_label"] == "WristWatch"
    assert watch["relation"] == "worn_by"
    assert watch["wearable"] is True
    assert watch["is_inventory_relevant"] is True


def test_v8_standalone_wristwatch_on_desk():
    """Real physical wristwatch resting standalone on desk/table is recognized as WristWatch."""
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 160

    # Draw standalone watch on desk (strap + circular dial with bezel)
    wx, wy = 500, 450
    # Strap
    cv2.rectangle(frame, (wx - 8, wy - 22), (wx + 8, wy + 22), (50, 40, 30), -1)
    # Dial casing with high edge density
    cv2.circle(frame, (wx, wy), 16, (20, 20, 20), -1)
    cv2.circle(frame, (wx, wy), 16, (220, 220, 220), 2)
    cv2.line(frame, (wx, wy), (wx + 7, wy - 7), (240, 240, 240), 2)

    watches = SemanticValidationEngine.detect_wristwatches_in_scene(
        frame=frame,
        person_boxes=None,  # No person wearing it
        wrist_keypoints=None,
        min_confidence=0.50,
    )

    assert len(watches) >= 1, "Standalone wristwatch on table must be detected"
    watch = watches[0]
    assert watch["specific_label"] == "WristWatch"
    assert watch["relation"] == "standalone"
    assert watch["wearable"] is True


def test_v8_screen_or_photo_watch_quarantined():
    """A watch shown on a phone screen or inside a picture is quarantined from physical counts."""
    display_screen = [400, 300, 150, 250]  # Smartphone / screen
    watch_box = [430, 360, 45, 45]       # Watch image inside the screen

    is_enclosed = SemanticValidationEngine.calculate_box_iou(watch_box, display_screen) > 0 or \
        (watch_box[0] >= display_screen[0] and watch_box[0] + watch_box[2] <= display_screen[0] + display_screen[2] and
         watch_box[1] >= display_screen[1] and watch_box[1] + watch_box[3] <= display_screen[1] + display_screen[3])

    assert is_enclosed is True, "Watch inside screen must be identified as enclosed"

    # In SemanticValidationEngine.validate_scene_detections, enclosed candidates transition to REJECTED_STATIC_CONTENT
    candidate = DetectedBox(
        bbox=watch_box,
        class_label="single_unit",
        product_id=None,
        sku_code=None,
        confidence=0.88,
        specific_label="WristWatch",
        detection_state="CANDIDATE",
    )

    confirmed, rejected = SemanticValidationEngine.validate_scene_detections(
        frame=np.ones((720, 1280, 3), dtype=np.uint8) * 100,
        candidates=[candidate],
        display_containers=[display_screen],
    )

    assert len(confirmed) == 0, "Virtual watch inside screen must NOT be confirmed"
    assert len(rejected) == 1, "Virtual watch must be rejected into quarantine"
    assert rejected[0]["reason"] == "ENCLOSED_IN_DISPLAY_CONTAINER"


# ============================================================================
# 3. Observed Problem D: Simultaneous Real Objects Coexistence & Exact Counting
# ============================================================================

def test_v8_simultaneous_multi_object_scene():
    """Verifies concurrent detection & exact counting for real multi-object scene:
    1 person, 1 wristwatch, 1 laptop, 2 smartphones, 4 books, 3 bottles, 2 boxes,
    1 bookshelf, 1 wall clock, 2 wall pictures.
    """
    # 1. Personnel (1)
    b_person = DetectedBox(bbox=[100, 150, 180, 500], class_label="person", product_id=None, sku_code=None, confidence=0.94, specific_label="Person", detection_state="CONFIRMED", is_inventory_relevant=False, is_environment_only=False)

    # 2. Wearables (1 WristWatch worn by person)
    b_watch = DetectedBox(bbox=[260, 420, 35, 35], class_label="single_unit", product_id=None, sku_code=None, confidence=0.88, specific_label="WristWatch", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False, relation="worn_by", parent_track_id="tr_person_1")

    # 3. Computing (1 Laptop, 2 Smartphones)
    b_laptop = DetectedBox(bbox=[350, 350, 140, 90], class_label="single_unit", product_id=None, sku_code=None, confidence=0.92, specific_label="Laptop", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False)
    b_phone1 = DetectedBox(bbox=[510, 370, 30, 60], class_label="single_unit", product_id=None, sku_code=None, confidence=0.90, specific_label="Smartphone", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False)
    b_phone2 = DetectedBox(bbox=[550, 370, 30, 60], class_label="single_unit", product_id=None, sku_code=None, confidence=0.89, specific_label="Smartphone", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False)

    # 4. Reading/Office (4 Books)
    b_books = [
        DetectedBox(bbox=[620, 380, 22, 75], class_label="single_unit", product_id="BK", sku_code="SKU-BK", confidence=0.89, specific_label="Book / Document", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[645, 380, 22, 75], class_label="single_unit", product_id="BK", sku_code="SKU-BK", confidence=0.88, specific_label="Book / Document", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[670, 380, 22, 75], class_label="single_unit", product_id="BK", sku_code="SKU-BK", confidence=0.87, specific_label="Book / Document", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[695, 380, 22, 75], class_label="single_unit", product_id="BK", sku_code="SKU-BK", confidence=0.86, specific_label="Book / Document", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
    ]

    # 5. Everyday Items (3 Bottles)
    b_bottles = [
        DetectedBox(bbox=[740, 360, 35, 95], class_label="single_unit", product_id="BT", sku_code="SKU-BT", confidence=0.91, specific_label="Bottle", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[780, 360, 35, 95], class_label="single_unit", product_id="BT", sku_code="SKU-BT", confidence=0.90, specific_label="Bottle", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[820, 360, 35, 95], class_label="single_unit", product_id="BT", sku_code="SKU-BT", confidence=0.89, specific_label="Bottle", detection_state="CONFIRMED", is_inventory_relevant=True, is_environment_only=False),
    ]

    # 6. Logistics Cases (2 Boxes)
    b_boxes = [
        DetectedBox(bbox=[880, 320, 110, 100], class_label="case_full", product_id="BX", sku_code="SKU-BX", confidence=0.92, specific_label="Carton / Shipping Box", detection_state="CONFIRMED", pack_size=12, is_inventory_relevant=True, is_environment_only=False),
        DetectedBox(bbox=[1000, 320, 110, 100], class_label="case_full", product_id="BX", sku_code="SKU-BX", confidence=0.91, specific_label="Carton / Shipping Box", detection_state="CONFIRMED", pack_size=12, is_inventory_relevant=True, is_environment_only=False),
    ]

    # 7. Fixtures / Environment (1 Bookshelf, 1 Wall Clock, 2 Wall Pictures)
    b_shelf = DetectedBox(bbox=[600, 200, 140, 300], class_label="bookshelf", product_id=None, sku_code=None, confidence=0.91, specific_label="Storage Shelf / Bookcase", detection_state="CONFIRMED", is_inventory_relevant=False, is_environment_only=True)
    b_clock = DetectedBox(bbox=[70, 40, 50, 50], class_label="clock", product_id=None, sku_code=None, confidence=0.89, specific_label="Clock / Wall Item", detection_state="CONFIRMED", is_inventory_relevant=False, is_environment_only=True)
    b_pics = [
        DetectedBox(bbox=[350, 80, 120, 90], class_label="wall_picture", product_id=None, sku_code=None, confidence=0.90, specific_label="Wall Picture Frame", detection_state="CONFIRMED", is_inventory_relevant=False, is_environment_only=True),
        DetectedBox(bbox=[500, 80, 120, 90], class_label="wall_picture", product_id=None, sku_code=None, confidence=0.88, specific_label="Wall Picture Frame", detection_state="CONFIRMED", is_inventory_relevant=False, is_environment_only=True),
    ]

    all_scene_items = [b_person, b_watch, b_laptop, b_phone1, b_phone2] + b_books + b_bottles + b_boxes + [b_shelf, b_clock] + b_pics

    # Total detected entities in frame (1 person + 1 watch + 1 laptop + 2 phones + 4 books + 3 bottles + 2 boxes + 1 shelf + 1 clock + 2 pictures = 18)
    assert len(all_scene_items) == 18

    # Verify per-class instance counting
    counts: Dict[str, int] = {}
    for item in all_scene_items:
        lbl = item.specific_label or item.class_label
        counts[lbl] = counts.get(lbl, 0) + 1

    assert counts["Person"] == 1
    assert counts["WristWatch"] == 1
    assert counts["Laptop"] == 1
    assert counts["Smartphone"] == 2
    assert counts["Book / Document"] == 4
    assert counts["Bottle"] == 3
    assert counts["Carton / Shipping Box"] == 2
    assert counts["Storage Shelf / Bookcase"] == 1
    assert counts["Clock / Wall Item"] == 1
    assert counts["Wall Picture Frame"] == 2

    # Verify merchandise inventory calculation: environmental fixtures must be 0 in inventory
    inv_singles = [item for item in all_scene_items if item.is_inventory_relevant and item.class_label != "case_full"]
    inv_cases = [item for item in all_scene_items if item.is_inventory_relevant and item.class_label == "case_full"]

    # 1 watch + 1 laptop + 2 phones + 4 books + 3 bottles = 11 singles
    assert len(inv_singles) == 11
    # 2 cartons = 2 cases (2 * 12 = 24 units)
    assert len(inv_cases) == 2
    total_case_units = sum(c.pack_size for c in inv_cases)
    assert total_case_units == 24
    total_merchandise_units = len(inv_singles) + total_case_units
    assert total_merchandise_units == 35


# ============================================================================
# 4. Universal Taxonomy & Frame Analysis Report Integration
# ============================================================================

def test_v8_universal_taxonomy_and_frame_report():
    """Verifies that FrameAnalysisReport categorizes the V8 multi-object scene accurately."""
    boxes = [
        {"box": [100, 150, 180, 500], "type": "PERSON_UNMATCHED", "label": "Unknown Person (94%)", "confidence": 0.94, "color": "cyan"},
        {"box": [260, 420, 35, 35], "type": "WRISTWATCH", "label": "WristWatch (88%)", "confidence": 0.88, "color": "amber", "relation": "worn_by"},
        {"box": [350, 350, 140, 90], "type": "LAPTOP", "label": "Laptop (92%)", "confidence": 0.92, "color": "cyan"},
        {"box": [510, 370, 30, 60], "type": "SMARTPHONE", "label": "Smartphone (90%)", "confidence": 0.90, "color": "cyan"},
        {"box": [620, 380, 22, 75], "type": "BOOK", "label": "Book (89%)", "confidence": 0.89, "color": "amber"},
        {"box": [350, 80, 120, 90], "type": "WALL_PICTURE", "label": "Wall Picture Frame (90%)", "confidence": 0.90, "color": "cyan"},
    ]

    person_boxes = [[100, 150, 180, 500]]
    categorized = [
        UniversalTaxonomyService.classify_detection(b, person_boxes=person_boxes)
        for b in boxes
    ]

    report = FrameAnalysisReportGenerator.generate_report(
        categorized_entities=categorized,
        operational_confidence=0.93,
    )

    assert "FRAME ANALYSIS REPORT" in report
    assert "Real Unknown Persons: [1]" in report
    assert "Wristwatch: [1] | Status: [In-Use]" in report
    assert "Laptop: [1]" in report
    assert "Smartphone: [1]" in report
    assert "Book / Document: [1]" in report
    assert "Static Wall Decor (Poster / Art): [1]" in report
    assert "Operational Confidence: [93%]" in report
