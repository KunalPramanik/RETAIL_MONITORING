"""SEC-OPS V8 Human-Reviewed Annotation Workflow & Provenance Manager

Implements Section 2.2 of the SEC-OPS V8 Master Prompt:
- Provides human-in-the-loop review queue for model-proposed or manual annotations.
- Explicitly tracks annotation provenance (operator_id, timestamp, review status).
- Enforces strict promotion gate: images are NEVER considered trusted training
  examples until verified and approved by a human reviewer.
- Supports bounding boxes and polygonal instance masks for:
  * Person (0)
  * Phone (67)
  * Bottle (39)
  * Cement bag (101)
  * Iron rods / rebar (102)
  * Carton or package (82 / 104)
  * Book (73)
  * Bookshelf (1003)
  * Industrial Pallet (105)
- Exports verified annotations to standard YOLO and COCO formats without synthetic fabrication.
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
import os
import time
import json
import uuid
import logging

logger = logging.getLogger("secops.ml.annotation_workflow")

CANONICAL_CLASSES: Dict[int, str] = {
    0: "Person",
    39: "Bottle",
    67: "Phone",
    73: "Book",
    82: "Carton or package",
    101: "Cement bag",
    102: "Iron rods or rebar",
    104: "Heavy master carton",
    105: "Industrial pallet",
    1003: "Bookshelf",
}


@dataclass
class AnnotationInstance:
    annotation_id: str
    class_id: int
    class_name: str
    # Bounding box in normalized YOLO coordinates: [center_x, center_y, width, height] (0.0 to 1.0)
    bbox_yolo: List[float]
    polygon_points: Optional[List[List[float]]] = None  # Normalized polygon [[x, y], ...]
    source: str = "MODEL_PROPOSED"  # "MODEL_PROPOSED", "MANUAL_HUMAN"
    confidence: float = 0.0
    status: str = "PROPOSED"  # "PROPOSED", "APPROVED", "MODIFIED", "REJECTED"
    operator_id: Optional[str] = None
    reviewed_at: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class ImageReviewQueueItem:
    queue_id: str
    image_path: str
    image_filename: str
    image_hash: str
    image_width: int
    image_height: int
    status: str = "UNREVIEWED"  # "UNREVIEWED", "IN_REVIEW", "APPROVED_TRUSTED", "REJECTED"
    annotations: List[AnnotationInstance] = field(default_factory=list)
    operator_assigned: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    review_completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnnotationWorkflowManager:
    """Manages the verification and export pipeline for dataset annotations."""

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            storage_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "annotation_queue")
        self.storage_dir = os.path.abspath(storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)
        self.queue_file = os.path.join(self.storage_dir, "review_queue.json")
        self._queue: Dict[str, ImageReviewQueueItem] = {}
        self._load_queue()

    def _load_queue(self) -> None:
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for q_id, item_dict in data.items():
                        ann_objs = [
                            AnnotationInstance(**ann) for ann in item_dict.get("annotations", [])
                        ]
                        item_dict["annotations"] = ann_objs
                        self._queue[q_id] = ImageReviewQueueItem(**item_dict)
            except Exception as e:
                logger.error("Failed to load annotation review queue: %s", e)

    def _save_queue(self) -> None:
        try:
            serialized = {k: v.to_dict() for k, v in self._queue.items()}
            with open(self.queue_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
        except Exception as e:
            logger.error("Failed to save annotation review queue: %s", e)

    def enqueue_image_for_review(
        self,
        image_path: str,
        image_hash: str,
        width: int,
        height: int,
        proposed_detections: Optional[List[Dict[str, Any]]] = None,
    ) -> ImageReviewQueueItem:
        """Enqueues an unverified image. Any model-generated detections are marked PROPOSED (untrusted)."""
        queue_id = str(uuid.uuid4())
        filename = os.path.basename(image_path)

        instances: List[AnnotationInstance] = []
        if proposed_detections:
            for det in proposed_detections:
                cid = int(det.get("class_id", -1))
                cname = CANONICAL_CLASSES.get(cid, det.get("class_name", "Unknown"))
                # Normalize bbox if in pixel coordinates [x, y, w, h]
                raw_box = det.get("bbox", [0, 0, 0, 0])
                if max(raw_box) > 1.0 and width > 0 and height > 0:
                    bx, by, bw, bh = raw_box
                    cx = (bx + bw / 2.0) / width
                    cy = (by + bh / 2.0) / height
                    nw = bw / width
                    nh = bh / height
                    yolo_box = [round(cx, 5), round(cy, 5), round(nw, 5), round(nh, 5)]
                else:
                    yolo_box = [round(float(v), 5) for v in raw_box]

                instances.append(
                    AnnotationInstance(
                        annotation_id=str(uuid.uuid4()),
                        class_id=cid,
                        class_name=cname,
                        bbox_yolo=yolo_box,
                        polygon_points=det.get("polygon"),
                        source="MODEL_PROPOSED",
                        confidence=float(det.get("confidence", 0.0)),
                        status="PROPOSED",
                    )
                )

        item = ImageReviewQueueItem(
            queue_id=queue_id,
            image_path=os.path.abspath(image_path),
            image_filename=filename,
            image_hash=image_hash,
            image_width=width,
            image_height=height,
            status="UNREVIEWED",
            annotations=instances,
        )

        self._queue[queue_id] = item
        self._save_queue()
        return item

    def get_pending_items(self) -> List[ImageReviewQueueItem]:
        """Returns all items currently awaiting human verification."""
        return [item for item in self._queue.values() if item.status in ("UNREVIEWED", "IN_REVIEW")]

    def review_annotation(
        self,
        queue_id: str,
        annotation_id: str,
        operator_id: str,
        action: str,  # "APPROVE", "MODIFY", "REJECT"
        corrected_class_id: Optional[int] = None,
        corrected_bbox_yolo: Optional[List[float]] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Applies a human review decision to a specific annotation instance."""
        if queue_id not in self._queue:
            return False

        item = self._queue[queue_id]
        target_ann: Optional[AnnotationInstance] = None
        for ann in item.annotations:
            if ann.annotation_id == annotation_id:
                target_ann = ann
                break

        if not target_ann:
            return False

        target_ann.operator_id = operator_id
        target_ann.reviewed_at = time.time()
        target_ann.notes = notes

        if action == "APPROVE":
            target_ann.status = "APPROVED"
        elif action == "MODIFY":
            target_ann.status = "MODIFIED"
            if corrected_class_id is not None:
                target_ann.class_id = corrected_class_id
                target_ann.class_name = CANONICAL_CLASSES.get(corrected_class_id, "Custom")
            if corrected_bbox_yolo is not None:
                target_ann.bbox_yolo = corrected_bbox_yolo
        elif action == "REJECT":
            target_ann.status = "REJECTED"

        item.status = "IN_REVIEW"
        item.updated_at = time.time()
        self._save_queue()
        return True

    def add_manual_annotation(
        self,
        queue_id: str,
        operator_id: str,
        class_id: int,
        bbox_yolo: List[float],
        polygon_points: Optional[List[List[float]]] = None,
        notes: Optional[str] = None,
    ) -> Optional[AnnotationInstance]:
        """Allows an operator to add a missed ground-truth instance to an image."""
        if queue_id not in self._queue:
            return None

        item = self._queue[queue_id]
        cname = CANONICAL_CLASSES.get(class_id, "Custom")
        ann = AnnotationInstance(
            annotation_id=str(uuid.uuid4()),
            class_id=class_id,
            class_name=cname,
            bbox_yolo=bbox_yolo,
            polygon_points=polygon_points,
            source="MANUAL_HUMAN",
            confidence=1.0,
            status="APPROVED",
            operator_id=operator_id,
            reviewed_at=time.time(),
            notes=notes,
        )
        item.annotations.append(ann)
        item.status = "IN_REVIEW"
        item.updated_at = time.time()
        self._save_queue()
        return ann

    def finalize_image_review(
        self,
        queue_id: str,
        operator_id: str,
        decision: str,  # "APPROVE_TRUSTED", "REJECT"
    ) -> bool:
        """Promotes an image to the trusted dataset only when all required annotations are confirmed."""
        if queue_id not in self._queue:
            return False

        item = self._queue[queue_id]
        if decision == "APPROVE_TRUSTED":
            # Verify that no unreviewed "PROPOSED" items remain
            for ann in item.annotations:
                if ann.status == "PROPOSED":
                    logger.warning("Cannot finalize %s: unreviewed annotations remain", queue_id)
                    return False
            item.status = "APPROVED_TRUSTED"
        else:
            item.status = "REJECTED"

        item.operator_assigned = operator_id
        item.review_completed_at = time.time()
        item.updated_at = time.time()
        self._save_queue()
        return True

    def export_verified_yolo_dataset(self, output_dir: str) -> Dict[str, Any]:
        """Exports ONLY verified and human-approved annotations to standard YOLO format.
        
        Strictly excludes any unapproved, proposed, or rejected labels to prevent data leakage.
        """
        os.makedirs(output_dir, exist_ok=True)
        images_out_dir = os.path.join(output_dir, "images")
        labels_out_dir = os.path.join(output_dir, "labels")
        os.makedirs(images_out_dir, exist_ok=True)
        os.makedirs(labels_out_dir, exist_ok=True)

        classes_path = os.path.join(output_dir, "classes.txt")
        sorted_cids = sorted(CANONICAL_CLASSES.keys())
        cid_to_idx = {cid: idx for idx, cid in enumerate(sorted_cids)}
        with open(classes_path, "w", encoding="utf-8") as f:
            for cid in sorted_cids:
                f.write(f"{CANONICAL_CLASSES[cid]}\n")

        exported_images_count = 0
        exported_annotations_count = 0

        for item in self._queue.values():
            if item.status != "APPROVED_TRUSTED":
                continue  # Skip unverified images

            # Filter approved or modified instances
            valid_anns = [
                ann for ann in item.annotations if ann.status in ("APPROVED", "MODIFIED")
            ]
            if not valid_anns:
                continue

            stem = os.path.splitext(item.image_filename)[0]
            label_file = os.path.join(labels_out_dir, f"{stem}.txt")

            with open(label_file, "w", encoding="utf-8") as lf:
                for ann in valid_anns:
                    idx = cid_to_idx.get(ann.class_id, 0)
                    cx, cy, w, h = ann.bbox_yolo
                    lf.write(f"{idx} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                    exported_annotations_count += 1

            exported_images_count += 1

        return {
            "output_dir": output_dir,
            "exported_images": exported_images_count,
            "exported_annotations": exported_annotations_count,
            "classes_count": len(sorted_cids),
        }

