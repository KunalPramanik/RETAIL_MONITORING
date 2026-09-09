import io
import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.ml.vision_service import VisionInferenceService
from src.ml.face_service import FaceRecognitionService
from src.ml.ocr_service import OcrService


def test_yolox_deep_learning_model_metadata_and_inference():
    assert VisionInferenceService.MODEL_VERSION == 'yolox-tiny-coco-v0.1.0'
    session = VisionInferenceService.get_session()
    assert session is not None

    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(img, (120, 100), (320, 300), (255, 255, 255), -1)
    _, encoded = cv2.imencode('.jpg', img)

    result, annotated_bytes = VisionInferenceService.analyze_frame_bytes(encoded.tobytes())
    assert result.model_version == 'yolox-tiny-coco-v0.1.0'
    assert result.cases_detected >= 1
    assert result.vision_count >= 1
    assert result.latency_ms > 0
    assert len(annotated_bytes) > 500
    assert len(result.detections) >= 1
    assert result.detections[0].class_label in ['case_full', 'case_open', 'single_unit', 'person']


def test_insightface_arcface_biometric_model_metadata_and_embedding():
    assert FaceRecognitionService.MODEL_VERSION == 'insightface-arcface-buffalo_s-512d'
    assert FaceRecognitionService.EMBEDDING_DIM == 512
    assert FaceRecognitionService.THRESHOLD_MATCHED == 0.65
    assert FaceRecognitionService.THRESHOLD_LOW_CONF == 0.45

    v1 = np.random.randn(512).astype(np.float32)
    v1 = v1 / np.linalg.norm(v1)
    v2 = v1.copy()
    sim_exact = FaceRecognitionService.cosine_similarity(v1, v2)
    assert pytest.approx(sim_exact, 0.001) == 1.0

    v3 = np.random.randn(512).astype(np.float32)
    v3 = v3 - np.dot(v3, v1) * v1
    v3 = v3 / np.linalg.norm(v3)
    sim_ortho = FaceRecognitionService.cosine_similarity(v1, v3)
    assert abs(sim_ortho) < 0.10

    empty_img = np.zeros((480, 640, 3), dtype=np.uint8)
    _, enc = cv2.imencode('.jpg', empty_img)
    match_res, _, boxes = FaceRecognitionService.detect_and_match_faces(
        frame_bytes=enc.tobytes(),
        enrolled_employees=[],
    )
    assert match_res.decision == 'NO_MATCH'
    assert len(boxes) == 0


def test_paddleocr_text_and_sku_extraction():
    assert OcrService.MODEL_VERSION == 'paddleocr-rapidocr-v3.2'

    img = Image.new('RGB', (700, 350), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((25, 25), 'INVOICE: BOL-DEEP-2026', fill=(0, 0, 0))
    draw.text((25, 70), 'CARRIER: DELHI VERY FREIGHT', fill=(0, 0, 0))
    draw.text((25, 120), 'SKU-SOD-330-24 5 CASES PACK 24', fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    raw_bytes = buf.getvalue()

    catalog_products = [
        {'sku_code': 'SKU-SOD-330-24', 'name': 'Classic Spark Cola 330ml Cans', 'pack_size': 24}
    ]

    result = OcrService.extract_from_image(
        image_bytes=raw_bytes,
        catalog_products=catalog_products,
    )

    assert result.model_version == 'paddleocr-rapidocr-v3.2'
    assert result.extraction_confidence > 0.70
    assert len(result.line_items) >= 1

    item = result.line_items[0]
    assert item.sku_code == 'SKU-SOD-330-24'
    assert item.cases_declared == 5
    assert item.units_per_case == 24
    assert item.total_units == 120
    assert result.declared_total_units == 120
    assert 'BOL-DEEP-2026' in result.raw_ocr_text
