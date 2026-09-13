"""Cross-Camera & Multi-Lane Hand-Off Tracking Service

Tracks subjects (people and carts) across overlapping or adjacent camera fields of view.
Performs appearance/Re-ID matching to preserve tracking identity across camera boundaries
and suppresses double-counting across shared egress zones.
Zero database schema changes required.
"""

from typing import Dict, List, Optional, Tuple, Any
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
                # If no features, temporal-spatial continuity across adjacent cameras
                if tr.current_camera_id != camera_id and time_delta <= 5.0:
                    score = 0.72  # strong temporal hand-off prior

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

