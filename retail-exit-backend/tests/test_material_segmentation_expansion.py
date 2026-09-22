"""Tests for Universal Material Instance Segmentation Expansion

Verifies polygonal segmentation and counting of dense store materials:
- Ceramic Tiles / Tile Boxes (class 106)
- Corrugated Aluminum Sheets & Tin Panels (class 107)
- Dynamic contour analysis, aspect ratio constraints, and physical masks
"""

import numpy as np
import cv2
import pytest
from src.ml.material_segmentation import MaterialSegmentationService, MaterialInstance


def test_material_config_includes_tiles_and_aluminum():
    """Verify that material config contains tile and aluminum tin classes."""
    cfg = MaterialSegmentationService.load_config()
    classes = cfg.get("material_classes", {})
    assert "106" in classes, "Class 106 (Ceramic Tiles) missing from material_classes_config.json"
    assert "107" in classes, "Class 107 (Corrugated Aluminum Tin) missing from material_classes_config.json"
    assert "Tile" in classes["106"]["name"]
    assert "Aluminum" in classes["107"]["name"] or "Tin" in classes["107"]["name"]


def test_segment_ceramic_tiles_synthetic():
    """Verify instance segmentation detects square-ish tile boxes with grid texture."""
    # Create synthetic frame with ceramic tile box: square aspect ratio ~ 1.05
    img = np.full((400, 600, 3), 40, dtype=np.uint8)
    # Draw tile box rectangle (x=100, y=100, w=150, h=140) => ar = 150/140 = 1.07
    cv2.rectangle(img, (100, 100), (250, 240), (190, 190, 195), -1)
    # Draw subtle grout/seam lines inside
    cv2.line(img, (175, 100), (175, 240), (70, 70, 75), 2)
    cv2.line(img, (100, 170), (250, 170), (70, 70, 75), 2)

    result = MaterialSegmentationService.segment_materials(img, min_confidence=0.40)
    assert result.total_instances > 0
    tile_instances = [i for i in result.instances if i.class_id == "106" or "Tile" in i.class_name]
    assert len(tile_instances) >= 1
    assert tile_instances[0].class_id == "106"
    assert "Ceramic Tiles" in tile_instances[0].class_name


def test_segment_corrugated_aluminum_tin():
    """Verify instance segmentation detects elongated corrugated aluminum / tin sheets."""
    img = np.full((500, 700, 3), 30, dtype=np.uint8)
    # Draw elongated sheet: w=260, h=95 => ar = 260/95 = 2.73 (within 2.2 <= ar <= 3.5)
    # Metallic bright intensity > 110
    cv2.rectangle(img, (150, 150), (410, 245), (180, 185, 190), -1)
    # Draw horizontal corrugated ribbing ridges
    for ry in range(165, 245, 15):
        cv2.line(img, (150, ry), (410, ry), (220, 225, 230), 2)
        cv2.line(img, (150, ry + 4), (410, ry + 4), (110, 115, 120), 1)

    result = MaterialSegmentationService.segment_materials(img, min_confidence=0.40)
    assert result.total_instances > 0
    tin_instances = [i for i in result.instances if i.class_id == "107" or "Aluminum" in i.class_name]
    assert len(tin_instances) >= 1
    assert tin_instances[0].class_id == "107"
    assert "Aluminum Sheets" in tin_instances[0].class_name or "Tin" in tin_instances[0].class_name


def test_annotate_frame_with_masks():
    """Verify that annotate_frame_with_masks produces annotated image without altering dimensions."""
    img = np.zeros((300, 400, 3), dtype=np.uint8)
    inst = MaterialInstance(
        class_id="106",
        class_name="Ceramic Tiles / Tile Box",
        confidence=0.88,
        bbox=[50, 50, 100, 100],
        polygon=[[50, 50], [150, 50], [150, 150], [50, 150]],
        area_pixels=10000,
        mask_color_bgr=(200, 150, 50),
    )
    annotated = MaterialSegmentationService.annotate_frame_with_masks(img, [inst])
    assert annotated.shape == img.shape
    # Check that mask overlay was applied
    assert not np.array_equal(annotated, img)

