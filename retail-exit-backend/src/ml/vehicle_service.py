"""Vehicle Entry Intelligence & Automatic License Plate Recognition (ALPR) Service

Performs real-time vehicle intelligence for parking/exit portals:
1. Identifies vehicle category (Car, Motorcycle / Bike, Truck, Bus, Bicycle).
2. Extracts vehicle exterior dominant color via calibrated HSV spatial clustering.
3. Optical Character Recognition (ALPR / ANPR) on front/rear license plates via RapidOCR.
4. Auto-captures and persists vehicle snapshot dossiers.
"""

import os
import re
import cv2
import numpy as np
import logging
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger("secops.ml.vehicle")

# Common license plate regex patterns (Indian RTO standard & international alphanumeric plates)
PLATE_PATTERNS = [
    re.compile(r'^[A-Z]{2}\s?[0-9]{1,2}\s?[A-Z]{1,3}\s?[0-9]{4}$'),  # Standard (e.g. MH 12 AB 1234)
    re.compile(r'^[0-9]{2}\s?BH\s?[0-9]{4}\s?[A-Z]{1,2}$'),          # Bharat series (e.g. 22 BH 1234 AA)
    re.compile(r'^[A-Z]{2,3}\s?[0-9]{1,4}\s?[A-Z]{0,2}$'),          # Short / custom plate
    re.compile(r'^[A-Z0-9]{5,11}$'),                                  # General alphanumeric plate
]


class VehicleIntelligenceService:
    """Provides vehicle exterior color recognition and license plate OCR."""

    _ocr_engine = None

    @classmethod
    def get_ocr_engine(cls):
        """Lazy-loads ONNX OCR engine from ocr_service."""
        if cls._ocr_engine is None:
            try:
                from src.ml.ocr.invoice_ocr_service import OcrService
                cls._ocr_engine = OcrService.get_ocr_engine()
            except Exception as e:
                logger.warning("Could not load OCR engine for vehicle plates: %s", e)
        return cls._ocr_engine

    @staticmethod
    def detect_vehicle_color(vehicle_crop: np.ndarray) -> str:
        """Determines the dominant exterior paint color of a vehicle from an image crop."""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return "UNKNOWN"

        vh, vw = vehicle_crop.shape[:2]
        if vh < 20 or vw < 20:
            return "UNKNOWN"

        # Crop out wheels, windshield, and ground reflection by focusing on vehicle core body
        # Upper 15% is often sky/windshield, bottom 20% is tires/asphalt
        top_cut = int(vh * 0.15)
        bottom_cut = int(vh * 0.80)
        left_cut = int(vw * 0.12)
        right_cut = int(vw * 0.88)

        body_crop = vehicle_crop[top_cut:bottom_cut, left_cut:right_cut]
        if body_crop.size == 0:
            body_crop = vehicle_crop

        # Convert to HSV color space
        hsv = cv2.cvtColor(body_crop, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        total_pixels = max(1, body_crop.shape[0] * body_crop.shape[1])

        # Color masks
        # 1. White: very low saturation, high brightness
        white_mask = (s < 35) & (v > 170)

        # 2. Black / Dark: very low brightness
        black_mask = (v < 55)

        # 3. Silver / Grey: low saturation, moderate brightness
        grey_mask = (s < 45) & (v >= 55) & (v <= 170)

        # Chromatic colors (require noticeable saturation)
        chroma = (s >= 45) & (v >= 55)

        # 4. Red: wraps around 0 and 180 in OpenCV (0-10 or 170-180)
        red_mask = chroma & ((h < 10) | (h >= 170))

        # 5. Orange: 10-25
        orange_mask = chroma & (h >= 10) & (h < 25)

        # 6. Yellow: 25-35
        yellow_mask = chroma & (h >= 25) & (h < 35)

        # 7. Green: 35-85
        green_mask = chroma & (h >= 35) & (h < 85)

        # 8. Blue: 85-135
        blue_mask = chroma & (h >= 85) & (h < 135)

        # 9. Violet / Purple: 135-170
        purple_mask = chroma & (h >= 135) & (h < 170)

        # 10. Brown: low-saturation warm hues
        brown_mask = (s >= 35) & (s < 120) & (v >= 40) & (v <= 120) & (h >= 10) & (h < 28)

        color_counts = {
            "White": int(np.count_nonzero(white_mask)),
            "Black": int(np.count_nonzero(black_mask)),
            "Silver / Grey": int(np.count_nonzero(grey_mask)),
            "Red": int(np.count_nonzero(red_mask)),
            "Blue": int(np.count_nonzero(blue_mask)),
            "Green": int(np.count_nonzero(green_mask)),
            "Yellow": int(np.count_nonzero(yellow_mask)),
            "Orange": int(np.count_nonzero(orange_mask)),
            "Purple": int(np.count_nonzero(purple_mask)),
            "Brown": int(np.count_nonzero(brown_mask)),
        }

        dominant_color = max(color_counts, key=lambda k: color_counts[k])
        dominant_pct = color_counts[dominant_color] / total_pixels

        # If highest color is negligible or inconclusive, classify as Silver / Grey
        if dominant_pct < 0.12:
            return "Silver / Grey"

        return dominant_color

    @classmethod
    def detect_license_plate(cls, vehicle_crop: np.ndarray) -> Tuple[Optional[str], Optional[List[int]]]:
        """Runs OCR on the vehicle bumper / plate area to extract alphanumeric license number."""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return None, None

        vh, vw = vehicle_crop.shape[:2]
        if vh < 30 or vw < 30:
            return None, None

        ocr = cls.get_ocr_engine()
        if ocr is None:
            return None, None

        # License plates typically reside in the lower 45% of the vehicle (front or rear bumper)
        plate_y_start = max(0, int(vh * 0.45))
        bumper_region = vehicle_crop[plate_y_start:vh, :]

        regions_to_test = [
            (bumper_region, 0, plate_y_start),
            (vehicle_crop, 0, 0),  # fallback to entire vehicle if bumper crop misses
        ]

        best_plate: Optional[str] = None
        best_plate_box: Optional[List[int]] = None
        highest_conf: float = 0.0

        for candidate_img, offset_x, offset_y in regions_to_test:
            if candidate_img.size == 0:
                continue

            # Preprocessing: upscale if small, apply CLAHE contrast boost
            ch, cw = candidate_img.shape[:2]
            scale = 1.0
            if cw < 300:
                scale = 300.0 / max(1, cw)
                candidate_img = cv2.resize(candidate_img, (int(cw * scale), int(ch * scale)), interpolation=cv2.INTER_CUBIC)

            # Convert to gray and apply CLAHE
            gray = cv2.cvtColor(candidate_img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            contrasted = clahe.apply(gray)
            prep_bgr = cv2.cvtColor(contrasted, cv2.COLOR_GRAY2BGR)

            try:
                ocr_results, _ = ocr(prep_bgr)
                if not ocr_results:
                    continue

                for res in ocr_results:
                    # res format: [box_points, text, confidence]
                    poly, text, conf = res[0], str(res[1]).strip().upper(), float(res[2])
                    clean_text = re.sub(r'[^A-Z0-9]', '', text)

                    if len(clean_text) < 4 or len(clean_text) > 13:
                        continue

                    # Must have at least 1 letter and 1 digit to be a valid license plate
                    has_letter = any(c.isalpha() for c in clean_text)
                    has_digit = any(c.isdigit() for c in clean_text)
                    if not (has_letter and has_digit):
                        continue

                    # Match against license plate patterns
                    is_valid = any(pat.match(clean_text) for pat in PLATE_PATTERNS)
                    if is_valid or (5 <= len(clean_text) <= 11 and has_letter and has_digit):
                        if conf > highest_conf:
                            highest_conf = conf
                            best_plate = clean_text

                            # Calculate bounding box relative to vehicle crop
                            if len(poly) >= 4:
                                pts = np.asarray(poly, dtype=np.float32) / scale
                                min_x = int(np.min(pts[:, 0])) + offset_x
                                min_y = int(np.min(pts[:, 1])) + offset_y
                                max_x = int(np.max(pts[:, 0])) + offset_x
                                max_y = int(np.max(pts[:, 1])) + offset_y
                                best_plate_box = [min_x, min_y, max_x - min_x, max_y - min_y]

                if best_plate:
                    break
            except Exception as e:
                logger.debug("License plate OCR evaluation exception: %s", e)

        return best_plate, best_plate_box

    @classmethod
    def analyze_vehicle(
        cls,
        full_frame: np.ndarray,
        vehicle_bbox: List[int],
        vehicle_type: str = "Car",
    ) -> Dict[str, Any]:
        """Extracts complete vehicle metadata: type, dominant color, and license plate."""
        fh, fw = full_frame.shape[:2]
        vx, vy, vw, vh = vehicle_bbox

        # Safe clipping
        x1 = max(0, min(vx, fw - 1))
        y1 = max(0, min(vy, fh - 1))
        x2 = max(x1 + 1, min(vx + vw, fw))
        y2 = max(y1 + 1, min(vy + vh, fh))

        vehicle_crop = full_frame[y1:y2, x1:x2]

        color = cls.detect_vehicle_color(vehicle_crop)
        plate_text, plate_rel_box = cls.detect_license_plate(vehicle_crop)

        plate_abs_box = None
        if plate_rel_box:
            plate_abs_box = [
                x1 + plate_rel_box[0],
                y1 + plate_rel_box[1],
                plate_rel_box[2],
                plate_rel_box[3],
            ]

        plate_display = plate_text if plate_text else "NOT_LEGIBLE"

        return {
            "vehicle_type": vehicle_type,
            "color": color,
            "license_plate": plate_text,
            "plate_display": plate_display,
            "plate_bbox": plate_abs_box,
            "badge_text": f"{vehicle_type.upper()} ({color.upper()}) | PLATE: {plate_display}",
        }


# Global instance
vehicle_service = VehicleIntelligenceService()

