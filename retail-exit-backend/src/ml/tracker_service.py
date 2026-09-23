"""Cross-Camera & Multi-Lane Hand-Off Tracking Service

Tracks subjects (people and carts) across overlapping or adjacent camera fields of view.
Performs appearance/Re-ID matching to preserve tracking identity across camera boundaries
and suppresses double-counting across shared egress zones.
Zero database schema changes required.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import time
import math
import uuid
import logging

logger = logging.getLogger("secops.tracker")


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


class SubjectTrack:
    """Represents an active entity moving through single or multiple camera views."""

    def __init__(
        self,
        track_id: str,
        camera_id: str,
        lane_id: str,
        embedding: Optional[List[float]] = None,
        color_hist: Optional[List[float]] = None,
        bbox: Optional[List[float]] = None,
        timestamp: Optional[float] = None,
    ):
        self.track_id = track_id
        self.origin_camera_id = camera_id
        self.current_camera_id = camera_id
        self.lane_id = lane_id
        self.embedding = embedding
        self.color_hist = color_hist
        self.last_bbox = bbox or [0.0, 0.0, 1.0, 1.0]
        now = timestamp if timestamp is not None else time.time()
        self.first_seen_ts: float = now
        self.last_seen_ts: float = now
        self.camera_history: List[str] = [camera_id]
        self.is_handed_off: bool = False
        self.emitted_event_id: Optional[str] = None
        self.emitted_event_ts: Optional[float] = None

    @property
    def tracking_label(self) -> str:
        if len(self.camera_history) > 1:
            return f"Multi-Camera Tracking: {' -> '.join(self.camera_history)}"
        return f"Camera {self.origin_camera_id}"


class CrossCameraTracker:
    """Multi-camera re-identification and tracking engine."""

    def __init__(
        self,
        handoff_window_sec: float = 10.0,
        similarity_threshold: float = 0.70,
        double_count_suppression_window_sec: float = 8.0,
    ):
        self.handoff_window_sec = handoff_window_sec
        self.similarity_threshold = similarity_threshold
        self.double_count_suppression_window_sec = double_count_suppression_window_sec
        self._tracks: Dict[str, SubjectTrack] = {}

    def process_detection(
        self,
        camera_id: str,
        lane_id: str,
        bbox: Optional[List[float]] = None,
        embedding: Optional[List[float]] = None,
        color_hist: Optional[List[float]] = None,
        timestamp: Optional[float] = None,
    ) -> Tuple[SubjectTrack, bool]:
        """Processes a detection and associates it with an existing cross-camera track or creates a new one.
        
        Returns:
            (track, is_new_handoff)
        """
        now = timestamp if timestamp is not None else time.time()
        best_match_id: Optional[str] = None
        highest_score = 0.0

        # Scan active tracks in the hand-off window
        for tid, tr in list(self._tracks.items()):
            time_delta = now - tr.last_seen_ts
            if time_delta > self.handoff_window_sec:
                continue

            # Calculate match score
            score = 0.0
            if embedding and tr.embedding:
                score = _cosine_similarity(embedding, tr.embedding)
            elif color_hist and tr.color_hist:
                score = _cosine_similarity(color_hist, tr.color_hist)
            else:
                # Temporal-spatial continuity: maintains track identity across brief occlusion
                if tr.current_camera_id == camera_id and time_delta <= 5.0:
                    score = 0.85  # Same camera occlusion persistence (~15 frames / 5s)
                elif tr.current_camera_id != camera_id and time_delta <= 5.0:
                    score = 0.72  # Cross-camera hand-off prior

            if score > highest_score and score >= self.similarity_threshold:
                highest_score = score
                best_match_id = tid

        # Case 1: Match found -> Associate and check handoff
        if best_match_id is not None:
            track = self._tracks[best_match_id]
            is_new_handoff = False

            if track.current_camera_id != camera_id:
                track.is_handed_off = True
                if camera_id not in track.camera_history:
                    track.camera_history.append(camera_id)
                track.current_camera_id = camera_id
                track.lane_id = lane_id
                is_new_handoff = True
                logger.info(
                    f"HAND-OFF DETECTED: Track {track.track_id} moved to Camera {camera_id}. "
                    f"Trajectory: {' -> '.join(track.camera_history)}"
                )

            track.last_seen_ts = now
            if bbox:
                track.last_bbox = bbox
            if embedding:
                track.embedding = embedding
            return track, is_new_handoff

        # Case 2: New subject
        new_id = f"TRK-{uuid.uuid4().hex[:8].upper()}"
        new_track = SubjectTrack(
            track_id=new_id,
            camera_id=camera_id,
            lane_id=lane_id,
            embedding=embedding,
            color_hist=color_hist,
            bbox=bbox,
            timestamp=now,
        )
        self._tracks[new_id] = new_track
        return new_track, False

    def should_suppress_exit_event(
        self,
        track_id: str,
        current_ts: Optional[float] = None,
    ) -> bool:
        """Determines whether a new exit event should be suppressed to prevent double-counting.
        
        If an event was already created for this track within the suppression window, returns True.
        """
        now = current_ts if current_ts is not None else time.time()
        track = self._tracks.get(track_id)
        if not track:
            return False

        if track.emitted_event_ts is not None:
            elapsed = now - track.emitted_event_ts
            if elapsed < self.double_count_suppression_window_sec:
                logger.info(
                    f"DOUBLE-COUNT SUPPRESSED for Track {track_id} on Camera {track.current_camera_id}. "
                    f"Previous event {track.emitted_event_id} was {elapsed:.1f}s ago."
                )
                return True

        return False

    def mark_event_emitted(self, track_id: str, event_id: str, timestamp: Optional[float] = None):
        """Records that an exit event has been officially emitted for this track."""
        track = self._tracks.get(track_id)
        if track:
            now = timestamp if timestamp is not None else time.time()
            track.emitted_event_id = event_id
            track.emitted_event_ts = now

    def cleanup_old_tracks(self, max_age_sec: float = 60.0):
        """Removes expired tracks to prevent memory leak."""
        now = time.time()
        expired = [tid for tid, tr in self._tracks.items() if now - tr.last_seen_ts > max_age_sec]
        for tid in expired:
            del self._tracks[tid]


# Global singleton
cross_camera_tracker = CrossCameraTracker()


@dataclass
class SingleCameraTrack:
    track_id: str
    class_label: str
    specific_label: str
    bbox: List[int]
    confidence: float
    first_seen_ts: float
    last_seen_ts: float
    hits: int = 1
    lost_frames: int = 0
    is_confirmed: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)


class IntraCameraObjectTracker:
    """Stable multi-object tracking per camera field of view across consecutive frames.

    Provides:
    - Stable track IDs for all detected instances (Person, Book, Laptop, Phone, Bottle, etc.)
    - Occlusion resilience (tolerates missing detections up to max_lost_frames before expiring)
    - Anti-flicker / duplicate count suppression
    """

    def __init__(self, iou_threshold: float = 0.25, max_lost_frames: int = 15, min_hits: int = 1):
        self.iou_threshold = iou_threshold
        self.max_lost_frames = max_lost_frames
        self.min_hits = min_hits
        self._camera_tracks: Dict[str, Dict[str, SingleCameraTrack]] = {}
        self._next_id: int = 1

    @staticmethod
    def _calculate_iou(boxA: List[int], boxB: List[int]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])
        inter = max(0, xB - xA) * max(0, yB - yA)
        denom = boxA[2] * boxA[3] + boxB[2] * boxB[3] - inter
        return inter / float(denom) if denom > 0 else 0.0

    def update_tracks(
        self,
        camera_id: str,
        detections: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Updates and associates detected bounding boxes with stable track IDs."""
        now = timestamp if timestamp is not None else time.time()
        tracks = self._camera_tracks.setdefault(camera_id, {})

        unmatched_dets = list(range(len(detections)))
        matched_track_ids = set()

        for det_idx in list(unmatched_dets):
            det = detections[det_idx]
            det_box = det.get("box", det.get("bbox", [0, 0, 0, 0]))
            det_cls = det.get("type", det.get("class_label", ""))
            det_spec = det.get("label", det.get("specific_label", det_cls))

            best_tid = None
            best_iou = self.iou_threshold

            for tid, tr in tracks.items():
                if tid in matched_track_ids:
                    continue
                # Match if class compatible or specific label compatible
                if tr.class_label != det_cls and tr.specific_label != det_spec:
                    continue

                iou = self._calculate_iou(det_box, tr.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_tid = tid

            if best_tid is not None:
                tr = tracks[best_tid]
                tr.bbox = det_box
                tr.confidence = float(det.get("confidence", tr.confidence))
                tr.last_seen_ts = now
                tr.hits += 1
                tr.lost_frames = 0
                tr.is_confirmed = tr.hits >= self.min_hits
                matched_track_ids.add(best_tid)
                unmatched_dets.remove(det_idx)
                det["track_id"] = tr.track_id

        # Spawn new tracks for remaining unmatched detections
        for det_idx in unmatched_dets:
            det = detections[det_idx]
            new_tid = f"TRK-{self._next_id:04d}"
            self._next_id += 1
            det_box = det.get("box", det.get("bbox", [0, 0, 0, 0]))
            det_cls = det.get("type", det.get("class_label", ""))
            det_spec = det.get("label", det.get("specific_label", det_cls))
            conf = float(det.get("confidence", 0.85))

            new_tr = SingleCameraTrack(
                track_id=new_tid,
                class_label=det_cls,
                specific_label=det_spec,
                bbox=det_box,
                confidence=conf,
                first_seen_ts=now,
                last_seen_ts=now,
                hits=1,
                lost_frames=0,
                is_confirmed=True,
            )
            tracks[new_tid] = new_tr
            matched_track_ids.add(new_tid)
            det["track_id"] = new_tid

        # Age unmatched tracks (occlusion resilience: retain until max_lost_frames)
        expired_tids = []
        for tid, tr in tracks.items():
            if tid not in matched_track_ids:
                tr.lost_frames += 1
                if tr.lost_frames > self.max_lost_frames:
                    expired_tids.append(tid)

        for tid in expired_tids:
            del tracks[tid]

        return detections

    def get_active_tracks(self, camera_id: str) -> Dict[str, SingleCameraTrack]:
        """Returns the dictionary of active (including briefly lost) tracks for the camera."""
        return self._camera_tracks.get(camera_id, {})



# Global single-camera multi-object tracker singleton
intra_camera_tracker = IntraCameraObjectTracker()

