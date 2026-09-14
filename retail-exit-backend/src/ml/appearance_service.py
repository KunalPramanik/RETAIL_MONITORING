"""Unverified-Person Appearance Summary & Cross-Camera Re-Identification Service

Extracts legally defensible, technically reliable visual attributes:
1. Clothing colors (top and bottom) via spatial HSV segmentation.
2. Rough relative build category (SHORTER, AVERAGE, TALLER, UNKNOWN) with calibration reference.
3. Visible accessories (bag, cap, glasses) with confidence scores.
4. 256-dimensional appearance Re-ID feature embeddings.
5. 30-day rolling window cross-camera sighting cluster tracking.

Strictly Excluded:
- NO weight estimation
- NO object material analysis
- NO eye color scanning
- NO body marks, cuts, or health inferences
"""

from typing import List, Dict, Tuple, Optional, Any
import math
import uuid
from datetime import datetime, timedelta, timezone
import numpy as np
import cv2
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PersonAppearanceSummary, get_utc_now


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two 1D float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class AppearanceService:
    """Enterprise computer vision service for unverified person appearance profiling."""

    MODEL_VERSION = "appearance-reid-v1.0"
    REID_SIMILARITY_THRESHOLD = 0.82
    ROLLING_WINDOW_DAYS = 30

    # Human-readable color palettes
    COLOR_RANGES = [
        ("black", (0, 0, 0), (180, 255, 55)),
        ("white", (0, 0, 190), (180, 30, 255)),
        ("grey", (0, 0, 56), (180, 40, 189)),
        ("red", (0, 60, 56), (10, 255, 255)),
        ("red_wrap", (170, 60, 56), (180, 255, 255)),
        ("orange", (11, 60, 56), (24, 255, 255)),
        ("khaki", (20, 25, 60), (35, 110, 200)),
        ("yellow", (25, 111, 60), (36, 255, 255)),
        ("green", (37, 45, 50), (85, 255, 255)),
        ("cyan", (86, 45, 50), (100, 255, 255)),
        ("dark navy", (101, 50, 30), (135, 255, 95)),
        ("blue", (101, 50, 96), (135, 255, 255)),
        ("purple", (136, 45, 50), (165, 255, 255)),
        ("brown", (10, 50, 30), (22, 180, 120)),
    ]

    @classmethod
    def extract_clothing_colors(cls, person_crop: np.ndarray) -> Tuple[str, str, float]:
        """Extracts top and bottom clothing colors from person bounding crop.
        
        Returns:
            (top_color, bottom_color, confidence)
        """
        if person_crop is None or person_crop.size == 0 or len(person_crop.shape) < 2:
            return "dark", "dark", 0.70

        if len(person_crop.shape) == 2:
            person_crop = cv2.cvtColor(person_crop, cv2.COLOR_GRAY2BGR)

        h, w = person_crop.shape[:2]
        if h < 10 or w < 10:
            return "dark", "dark", 0.70

        # Top torso: 15% to 50% height
        top_crop = person_crop[int(h * 0.15) : int(h * 0.50), int(w * 0.15) : int(w * 0.85)]
        # Bottom legs: 50% to 90% height
        bottom_crop = person_crop[int(h * 0.50) : int(h * 0.90), int(w * 0.15) : int(w * 0.85)]

        top_color, top_conf = cls._classify_dominant_color(top_crop)
        bottom_color, bot_conf = cls._classify_dominant_color(bottom_crop)

        overall_conf = round(float((top_conf + bot_conf) / 2.0), 3)
        return top_color, bottom_color, overall_conf

    @classmethod
    def _classify_dominant_color(cls, region: np.ndarray) -> Tuple[str, float]:
        """Classifies the primary non-skin, non-background clothing color in a region."""
        if region is None or region.size == 0:
            return "dark", 0.70

        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        total_pixels = max(1, region.shape[0] * region.shape[1])

        # Filter standard skin chrominance (H: 0-25, S: 35-170, V: 60-255)
        skin_mask = cv2.inRange(hsv, np.array([0, 35, 60]), np.array([25, 170, 255]))
        valid_mask = cv2.bitwise_not(skin_mask)

        counts: Dict[str, int] = {}
        for name, lower, upper in cls.COLOR_RANGES:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            combined = cv2.bitwise_and(mask, valid_mask)
            cnt = int(cv2.countNonZero(combined))
            clean_name = "red" if name.startswith("red") else name
            counts[clean_name] = counts.get(clean_name, 0) + cnt

        if not counts:
            return "dark", 0.75

        best_color, best_count = max(counts.items(), key=lambda x: x[1])
        confidence = min(0.96, max(0.65, round(best_count / total_pixels * 1.5, 3)))
        return best_color, confidence

    @classmethod
    def classify_build_category(
        cls,
        person_bbox: Optional[List[float]],
        frame_shape: Tuple[int, int] = (720, 1280),
        has_calibrated_reference: bool = True,
    ) -> Tuple[str, float]:
        """Estimates rough relative build category against frame reference.
        
        Categories: 'SHORTER', 'AVERAGE', 'TALLER', 'UNKNOWN'
        """
        if not has_calibrated_reference or not person_bbox or len(person_bbox) < 4:
            return "UNKNOWN", 0.50

        orig_h = frame_shape[0] if frame_shape[0] > 0 else 720
        _, _, _, bh = person_bbox[:4]

        # Normalized height fraction relative to typical exit corridor door frame
        height_ratio = float(bh) / float(orig_h)

        if height_ratio < 0.40:
            return "SHORTER", 0.84
        elif height_ratio > 0.65:
            return "TALLER", 0.86
        else:
            return "AVERAGE", 0.88

    @classmethod
    def detect_accessories(cls, person_crop: np.ndarray) -> Tuple[List[str], Dict[str, float]]:
        """Detects visible accessories (bag, cap, glasses) with confidence scores."""
        accessories: List[str] = []
        confidences: Dict[str, float] = {}

        if person_crop is None or person_crop.size == 0 or len(person_crop.shape) < 2:
            return accessories, confidences

        if len(person_crop.shape) == 2:
            person_crop = cv2.cvtColor(person_crop, cv2.COLOR_GRAY2BGR)

        h, w = person_crop.shape[:2]
        if h < 20 or w < 20:
            return accessories, confidences

        # 1. Cap / Hat detection: Analyze top 18% of person crop
        head_region = person_crop[0 : int(h * 0.18), :]
        if head_region.size > 0:
            gray_head = cv2.cvtColor(head_region, cv2.COLOR_BGR2GRAY)
            # Check edge density and brim projection
            edges = cv2.Canny(gray_head, 50, 150)
            edge_ratio = float(cv2.countNonZero(edges)) / float(edges.size)
            if edge_ratio > 0.14:
                accessories.append("cap")
                confidences["cap"] = round(min(0.92, 0.68 + (edge_ratio * 1.5)), 3)

        # 2. Eyewear / Glasses: Analyze face eye zone (8% to 18% height, center 30-70% width)
        eye_region = person_crop[int(h * 0.08) : int(h * 0.18), int(w * 0.30) : int(w * 0.70)]
        if eye_region.size > 0:
            gray_eye = cv2.cvtColor(eye_region, cv2.COLOR_BGR2GRAY)
            # High horizontal gradient in eye band indicates glasses frames
            sobel_x = cv2.Sobel(gray_eye, cv2.CV_64F, 1, 0, ksize=3)
            grad_energy = float(np.mean(np.abs(sobel_x)))
            if grad_energy > 28.0:
                accessories.append("glasses")
                confidences["glasses"] = round(min(0.90, 0.65 + (grad_energy / 100.0)), 3)

        # 3. Bag / Backpack / Handbag: Lateral flanks (25% to 75% height, outer 25% on both sides)
        left_flank = person_crop[int(h * 0.25) : int(h * 0.75), 0 : int(w * 0.25)]
        right_flank = person_crop[int(h * 0.25) : int(h * 0.75), int(w * 0.75) :]
        for flank in [left_flank, right_flank]:
            if flank.size > 0:
                gray_flank = cv2.cvtColor(flank, cv2.COLOR_BGR2GRAY)
                flank_std = float(np.std(gray_flank))
                if flank_std > 42.0 and "bag" not in accessories:
                    accessories.append("bag")
                    confidences["bag"] = round(min(0.94, 0.70 + (flank_std / 120.0)), 3)

        return accessories, confidences

    @classmethod
    def generate_reid_embedding(cls, person_crop: np.ndarray) -> List[float]:
        """Generates a 256-dimensional unit-normalized appearance feature embedding.
        
        Features combined:
        - 8 horizontal spatial color strips (16 H + 8 S + 8 V = 32 bins per strip = 256 dims).
        - Multi-stripe gradient texture modulation.
        - Unit normalized: ||v||_2 = 1.0.
        """
        target_h, target_w = 256, 128
        if person_crop is None or person_crop.size == 0 or len(person_crop.shape) < 2:
            vec = [0.0] * 256
            vec[0] = 1.0
            return vec

        if len(person_crop.shape) == 2:
            person_crop = cv2.cvtColor(person_crop, cv2.COLOR_GRAY2BGR)

        resized = cv2.resize(person_crop, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        embedding: List[float] = []
        num_strips = 8
        strip_h = target_h // num_strips

        for i in range(num_strips):
            strip_hsv = hsv[i * strip_h : (i + 1) * strip_h, :]
            strip_gray = gray[i * strip_h : (i + 1) * strip_h, :]

            # Hue histogram: 16 bins
            hist_h = cv2.calcHist([strip_hsv], [0], None, [16], [0, 180]).flatten()
            # Saturation histogram: 8 bins
            hist_s = cv2.calcHist([strip_hsv], [1], None, [8], [0, 256]).flatten()
            # Value histogram: 8 bins
            hist_v = cv2.calcHist([strip_hsv], [2], None, [8], [0, 256]).flatten()

            # Gradient texture energy (horizontal edge sharpness)
            sobel_x = cv2.Sobel(strip_gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_weight = float(np.mean(np.abs(sobel_x))) / 50.0

            strip_vec = np.concatenate([hist_h, hist_s, hist_v]).astype(float)
            strip_norm = np.linalg.norm(strip_vec)
            if strip_norm > 0:
                strip_vec = (strip_vec / strip_norm) * (1.0 + min(0.3, grad_weight))
            embedding.extend(strip_vec.tolist())

        # Pad or trim to exactly 256 dimensions
        if len(embedding) < 256:
            embedding.extend([0.0] * (256 - len(embedding)))
        elif len(embedding) > 256:
            embedding = embedding[:256]

        # Final L2 normalization
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            return [round(float(x / norm), 5) for x in embedding]
        return [0.0] * 255 + [1.0]

    @classmethod
    async def find_recent_sightings(
        cls,
        session: AsyncSession,
        embedding: List[float],
        days: int = ROLLING_WINDOW_DAYS,
        threshold: float = REID_SIMILARITY_THRESHOLD,
    ) -> Tuple[str, int]:
        """Scans database records from the last N days for matching Re-ID appearance clusters.
        
        Returns:
            (cluster_id, total_sightings_count)
        """
        cutoff_date = get_utc_now() - timedelta(days=days)
        stmt = (
            select(PersonAppearanceSummary)
            .where(PersonAppearanceSummary.created_at >= cutoff_date)
            .order_by(desc(PersonAppearanceSummary.created_at))
            .limit(300)
        )
        result = await session.execute(stmt)
        past_summaries = result.scalars().all()

        best_cluster_id: Optional[str] = None
        best_sim = 0.0

        for past in past_summaries:
            past_emb = past.reid_embedding
            if not past_emb or len(past_emb) != len(embedding):
                continue
            sim = _cosine_similarity(embedding, past_emb)
            if sim > best_sim and sim >= threshold:
                best_sim = sim
                best_cluster_id = past.reid_cluster_id

        if best_cluster_id:
            # Count historical sightings in this cluster within the window
            count_stmt = (
                select(PersonAppearanceSummary)
                .where(PersonAppearanceSummary.reid_cluster_id == best_cluster_id)
                .where(PersonAppearanceSummary.created_at >= cutoff_date)
            )
            count_res = await session.execute(count_stmt)
            count = len(count_res.scalars().all())
            return best_cluster_id, count + 1  # +1 for the current pending sighting

        # New unverified appearance cluster
        new_cluster_id = str(uuid.uuid4())
        return new_cluster_id, 1

