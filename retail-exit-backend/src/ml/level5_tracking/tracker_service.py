import numpy as np
from typing import List, Dict, Any, Tuple
from scipy.optimize import linear_sum_assignment
Any # type placeholder

class SimpleByteTrack:
    """Lightweight deterministic implementation of ByteTrack (IoU + Hungarian Matching).
    Maintains temporal ID persistence across frames to solve occlusion and double-counting.
    """
    def __init__(self, track_buffer: int = 30, match_thresh: float = 0.8, min_box_area: float = 100):
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.min_box_area = min_box_area
        self.tracked_objects: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1

    @staticmethod
    def bbox_iou(boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        if interArea == 0:
            return 0.0

        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]
        iou = interArea / float(boxAArea + boxBArea - interArea)
        return iou

    def update(self, detections: List[Any]) -> List[Any]:
        """Update tracker with new frame detections and assign persistent IDs."""
        current_frame_boxes = []
        for d in detections:
            area = d.bbox[2] * d.bbox[3]
            if area >= self.min_box_area:
                current_frame_boxes.append(d)

        if not current_frame_boxes:
            for tid in list(self.tracked_objects.keys()):
                self.tracked_objects[tid]["lost_frames"] += 1
                if self.tracked_objects[tid]["lost_frames"] > self.track_buffer:
                    del self.tracked_objects[tid]
            return []

        if not self.tracked_objects:
            for d in current_frame_boxes:
                d.track_id = self.next_id
                self.tracked_objects[self.next_id] = {"box": d, "lost_frames": 0}
                self.next_id += 1
            return current_frame_boxes

        track_ids = list(self.tracked_objects.keys())
        cost_matrix = np.zeros((len(track_ids), len(current_frame_boxes)))

        for i, tid in enumerate(track_ids):
            for j, det in enumerate(current_frame_boxes):
                iou = self.bbox_iou(self.tracked_objects[tid]["box"].bbox, det.bbox)
                cost_matrix[i, j] = 1.0 - iou

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        matched_indices = []
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] <= self.match_thresh:
                matched_indices.append((r, c))

        unmatched_dets = [j for j in range(len(current_frame_boxes)) if j not in [m[1] for m in matched_indices]]
        unmatched_tracks = [r for r in range(len(track_ids)) if r not in [m[0] for m in matched_indices]]

        updated_detections = []

        # Update matched tracks
        for r, c in matched_indices:
            tid = track_ids[r]
            det = current_frame_boxes[c]
            det.track_id = tid
            self.tracked_objects[tid]["box"] = det
            self.tracked_objects[tid]["lost_frames"] = 0
            updated_detections.append(det)

        # Register new tracks
        for j in unmatched_dets:
            det = current_frame_boxes[j]
            det.track_id = self.next_id
            self.tracked_objects[self.next_id] = {"box": det, "lost_frames": 0}
            updated_detections.append(det)
            self.next_id += 1

        # Age unmatched tracks
        for r in unmatched_tracks:
            tid = track_ids[r]
            self.tracked_objects[tid]["lost_frames"] += 1
            if self.tracked_objects[tid]["lost_frames"] > self.track_buffer:
                del self.tracked_objects[tid]

        return updated_detections
