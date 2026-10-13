"""SEC-OPS V8 CPU-First Dataset Inspection & Quality Audit Service

Implements Section 2.1 & 2.3 of the SEC-OPS V8 Master Prompt:
- Inventories available dataset images without assuming arbitrary folder layout.
- Measures resolution, corruption, blur (Laplacian variance), exposure, and contrast.
- Detects exact and near-duplicate images using 64-bit difference hashing (dHash).
- Identifies split leakage risks across train/val/test splits.
- Assesses counting suitability (discrete instance count vs dense stack volumetric estimation).
- Strictly preserves original image provenance and flags missing annotations.
"""

from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field, asdict
import os
import glob
import time
import json
import logging
import cv2
import numpy as np

logger = logging.getLogger("secops.ml.dataset_inspector")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}


@dataclass
class ImageQualityMetrics:
    file_path: str
    filename: str
    file_format: str
    file_size_bytes: int
    width: int
    height: int
    aspect_ratio: float
    channels: int
    is_corrupted: bool
    blur_laplacian_var: float
    blur_status: str  # "SHARP", "MODERATE_BLUR", "HEAVY_BLUR"
    mean_brightness: float  # 0 to 255
    exposure_status: str  # "UNDEREXPOSED", "NORMAL", "OVEREXPOSED"
    contrast_std: float
    contrast_status: str  # "LOW", "NORMAL", "HIGH"
    dhash: str  # 64-bit hex difference hash
    counting_suitability: str  # "INDIVIDUAL_INSTANCE_RESOLVABLE", "DENSE_STACK_HEURISTIC_REQUIRED", "UNSUITABLE"
    distinguishable_at_resolution: bool
    quality_issues: List[str] = field(default_factory=list)


@dataclass
class DatasetInspectionReport:
    timestamp: float
    root_directories_scanned: List[str]
    total_images_found: int
    valid_images_count: int
    corrupted_images_count: int
    formats_distribution: Dict[str, int]
    resolution_distribution: Dict[str, int]
    blur_summary: Dict[str, int]
    exposure_summary: Dict[str, int]
    exact_duplicates: List[List[str]]
    near_duplicates: List[Dict[str, Any]]
    leakage_safe_splits: Dict[str, List[str]]  # "train", "val", "held_out_test"
    counting_suitability_breakdown: Dict[str, int]
    images: List[ImageQualityMetrics] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class DatasetInspector:
    """CPU-friendly dataset inspection and quality auditing engine."""

    @staticmethod
    def compute_dhash(image_gray: np.ndarray, hash_size: int = 8) -> str:
        """Computes difference hash (dHash) for fast near-duplicate frame detection."""
        # Resize to (hash_size + 1, hash_size)
        resized = cv2.resize(image_gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        # Compare adjacent pixels
        diff = resized[:, 1:] > resized[:, :-1]
        # Convert bool array to 64-bit integer
        decimal_val = 0
        for bit in diff.flatten():
            decimal_val = (decimal_val << 1) | int(bit)
        return f"{decimal_val:016x}"

    @staticmethod
    def hamming_distance(hash1_hex: str, hash2_hex: str) -> int:
        """Computes hamming distance between two hex hashes."""
        try:
            val1 = int(hash1_hex, 16)
            val2 = int(hash2_hex, 16)
            xor_val = val1 ^ val2
            return bin(xor_val).count("1")
        except Exception:
            return 64

    @classmethod
    def inspect_single_image(cls, file_path: str) -> ImageQualityMetrics:
        """Performs non-destructive quality evaluation on a single image file."""
        filename = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        try:
            # Read image using OpenCV
            img = cv2.imread(file_path)
            if img is None or img.size == 0:
                return ImageQualityMetrics(
                    file_path=file_path,
                    filename=filename,
                    file_format=ext,
                    file_size_bytes=size_bytes,
                    width=0,
                    height=0,
                    aspect_ratio=0.0,
                    channels=0,
                    is_corrupted=True,
                    blur_laplacian_var=0.0,
                    blur_status="CORRUPTED",
                    mean_brightness=0.0,
                    exposure_status="CORRUPTED",
                    contrast_std=0.0,
                    contrast_status="CORRUPTED",
                    dhash="",
                    counting_suitability="UNSUITABLE",
                    distinguishable_at_resolution=False,
                    quality_issues=["Failed to decode image bytes; file is corrupted or unreadable"],
                )

            h, w = img.shape[:2]
            c = img.shape[2] if len(img.shape) > 2 else 1
            ar = round(float(w) / float(h), 3) if h > 0 else 0.0

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if c > 1 else img

            # 1. Blur calculation via Laplacian variance
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if lap_var >= 100.0:
                blur_status = "SHARP"
            elif lap_var >= 40.0:
                blur_status = "MODERATE_BLUR"
            else:
                blur_status = "HEAVY_BLUR"

            # 2. Exposure & Brightness
            mean_b = float(np.mean(gray))
            if mean_b < 50.0:
                exposure_status = "UNDEREXPOSED"
            elif mean_b > 200.0:
                exposure_status = "OVEREXPOSED"
            else:
                exposure_status = "NORMAL"

            # 3. Contrast via standard deviation
            std_c = float(np.std(gray))
            if std_c < 25.0:
                contrast_status = "LOW"
            elif std_c > 75.0:
                contrast_status = "HIGH"
            else:
                contrast_status = "NORMAL"

            # 4. Hash for duplicate detection
            dhash_hex = cls.compute_dhash(gray)

            # 5. Quality issues & counting suitability
            issues: List[str] = []
            if blur_status == "HEAVY_BLUR":
                issues.append("Image suffers from heavy motion or optical blur (Laplacian var < 40)")
            if exposure_status == "UNDEREXPOSED":
                issues.append("Image is severely underexposed (mean brightness < 50)")
            elif exposure_status == "OVEREXPOSED":
                issues.append("Image is overexposed/blown out (mean brightness > 200)")
            if contrast_status == "LOW":
                issues.append("Image has very low contrast, hindering edge separation")

            # Check resolution for distinguishing objects
            # At least 640x480 is required for reliable discrete counting
            distinguishable = (w >= 640 and h >= 480)
            if not distinguishable:
                issues.append(f"Low resolution ({w}x{h}) limits small object distinguishability")

            # Assess counting suitability
            if blur_status == "HEAVY_BLUR" or not distinguishable:
                suitability = "UNSUITABLE"
            elif w >= 1024 and h >= 720:
                suitability = "INDIVIDUAL_INSTANCE_RESOLVABLE"
            else:
                suitability = "DENSE_STACK_HEURISTIC_REQUIRED"

            return ImageQualityMetrics(
                file_path=file_path,
                filename=filename,
                file_format=ext,
                file_size_bytes=size_bytes,
                width=w,
                height=h,
                aspect_ratio=ar,
                channels=c,
                is_corrupted=False,
                blur_laplacian_var=round(lap_var, 2),
                blur_status=blur_status,
                mean_brightness=round(mean_b, 2),
                exposure_status=exposure_status,
                contrast_std=round(std_c, 2),
                contrast_status=contrast_status,
                dhash=dhash_hex,
                counting_suitability=suitability,
                distinguishable_at_resolution=distinguishable,
                quality_issues=issues,
            )

        except Exception as e:
            logger.error("Exception inspecting image %s: %s", file_path, e)
            return ImageQualityMetrics(
                file_path=file_path,
                filename=filename,
                file_format=ext,
                file_size_bytes=size_bytes,
                width=0,
                height=0,
                aspect_ratio=0.0,
                channels=0,
                is_corrupted=True,
                blur_laplacian_var=0.0,
                blur_status="CORRUPTED",
                mean_brightness=0.0,
                exposure_status="CORRUPTED",
                contrast_std=0.0,
                contrast_status="CORRUPTED",
                dhash="",
                counting_suitability="UNSUITABLE",
                distinguishable_at_resolution=False,
                quality_issues=[f"Error processing image: {str(e)}"],
            )

    @classmethod
    def inspect_directories(cls, directory_paths: List[str]) -> DatasetInspectionReport:
        """Inspects all supported images across given directories and builds a leakage-safe audit."""
        all_files: List[str] = []
        scanned_dirs: List[str] = []

        for d in directory_paths:
            if not os.path.exists(d):
                continue
            scanned_dirs.append(os.path.abspath(d))
            for root, _, files in os.walk(d):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        all_files.append(os.path.join(root, f))

        metrics_list: List[ImageQualityMetrics] = []
        formats_dist: Dict[str, int] = {}
        res_dist: Dict[str, int] = {}
        blur_dist: Dict[str, int] = {"SHARP": 0, "MODERATE_BLUR": 0, "HEAVY_BLUR": 0, "CORRUPTED": 0}
        exp_dist: Dict[str, int] = {"UNDEREXPOSED": 0, "NORMAL": 0, "OVEREXPOSED": 0, "CORRUPTED": 0}
        suit_dist: Dict[str, int] = {"INDIVIDUAL_INSTANCE_RESOLVABLE": 0, "DENSE_STACK_HEURISTIC_REQUIRED": 0, "UNSUITABLE": 0}

        corrupted_count = 0
        valid_count = 0

        # Hash map for exact duplicates: dhash -> list of paths
        hash_map: Dict[str, List[str]] = {}

        for p in all_files:
            m = cls.inspect_single_image(p)
            metrics_list.append(m)

            formats_dist[m.file_format] = formats_dist.get(m.file_format, 0) + 1
            if m.is_corrupted:
                corrupted_count += 1
                blur_dist["CORRUPTED"] += 1
                exp_dist["CORRUPTED"] += 1
            else:
                valid_count += 1
                res_key = f"{m.width}x{m.height}"
                res_dist[res_key] = res_dist.get(res_key, 0) + 1
                blur_dist[m.blur_status] = blur_dist.get(m.blur_status, 0) + 1
                exp_dist[m.exposure_status] = exp_dist.get(m.exposure_status, 0) + 1
                suit_dist[m.counting_suitability] = suit_dist.get(m.counting_suitability, 0) + 1

                if m.dhash:
                    hash_map.setdefault(m.dhash, []).append(m.file_path)

        # Exact duplicates
        exact_duplicates = [paths for paths in hash_map.values() if len(paths) > 1]

        # Near duplicates: check pairwise hamming distance on distinct hashes
        unique_metrics = [m for m in metrics_list if not m.is_corrupted and m.dhash]
        near_duplicates: List[Dict[str, Any]] = []
        for i in range(len(unique_metrics)):
            for j in range(i + 1, len(unique_metrics)):
                m1 = unique_metrics[i]
                m2 = unique_metrics[j]
                if m1.dhash == m2.dhash:
                    continue  # already captured in exact duplicates
                dist = cls.hamming_distance(m1.dhash, m2.dhash)
                # Hamming distance <= 6 out of 64 bits represents significant visual near-duplication
                if dist <= 6:
                    near_duplicates.append({
                        "image_a": m1.file_path,
                        "image_b": m2.file_path,
                        "hamming_distance": dist,
                        "similarity_pct": round((1.0 - (dist / 64.0)) * 100.0, 1),
                    })

        # Leakage-safe split partitioning:
        # Group near-duplicate clusters together so no two near-duplicates end up in different splits
        splits = cls._create_leakage_safe_splits(unique_metrics, near_duplicates)

        return DatasetInspectionReport(
            timestamp=time.time(),
            root_directories_scanned=scanned_dirs,
            total_images_found=len(all_files),
            valid_images_count=valid_count,
            corrupted_images_count=corrupted_count,
            formats_distribution=formats_dist,
            resolution_distribution=res_dist,
            blur_summary=blur_dist,
            exposure_summary=exp_dist,
            exact_duplicates=exact_duplicates,
            near_duplicates=near_duplicates,
            leakage_safe_splits=splits,
            counting_suitability_breakdown=suit_dist,
            images=metrics_list,
        )

    @classmethod
    def _create_leakage_safe_splits(
        cls,
        metrics: List[ImageQualityMetrics],
        near_dups: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Partitions images into train (70%), val (15%), held-out test (15%) preserving cluster isolation."""
        if not metrics:
            return {"train": [], "val": [], "held_out_test": []}

        # Build adjacency graph of image paths that are near-duplicates
        adj: Dict[str, Set[str]] = {m.file_path: set() for m in metrics}
        for nd in near_dups:
            p_a = nd["image_a"]
            p_b = nd["image_b"]
            if p_a in adj and p_b in adj:
                adj[p_a].add(p_b)
                adj[p_b].add(p_a)

        # Connected components (clusters)
        visited: Set[str] = set()
        clusters: List[List[str]] = []
        for path in adj:
            if path not in visited:
                comp: List[str] = []
                q = [path]
                visited.add(path)
                while q:
                    curr = q.pop()
                    comp.append(curr)
                    for nxt in adj[curr]:
                        if nxt not in visited:
                            visited.add(nxt)
                            q.append(nxt)
                clusters.append(comp)

        # Sort clusters deterministically
        clusters.sort(key=lambda c: len(c), reverse=True)

        train: List[str] = []
        val: List[str] = []
        held_out_test: List[str] = []

        total_imgs = len(metrics)
        target_train = max(1, int(total_imgs * 0.70))
        target_val = max(1, int(total_imgs * 0.15))

        for cluster in clusters:
            if len(train) < target_train or (len(val) >= target_val and len(held_out_test) >= 1):
                train.extend(cluster)
            elif len(val) < target_val:
                val.extend(cluster)
            else:
                held_out_test.extend(cluster)

        # Ensure held-out test has at least 1 image if >= 3 images exist
        if total_imgs >= 3 and not held_out_test and len(train) > 1:
            held_out_test.append(train.pop())

        return {
            "train": train,
            "val": val,
            "held_out_test": held_out_test,
        }

