"""SecOps Motion Detection Engine

Handles frame difference analysis, Gaussian blurring, contour/threshold calculation,
and dynamic debounce throttling across camera feeds.
"""

import time
import logging
from typing import Dict, Optional
import cv2
import numpy as np

from src.core.config import settings

logger = logging.getLogger("secops.motion_detector")


class MotionDetector:
    """Evaluates inter-frame motion for camera streams with configurable thresholds."""

    def __init__(self):
        self._last_frames: Dict[str, np.ndarray] = {}
        self._last_event_time: Dict[str, float] = {}

    def check_motion(
        self,
        camera_id: str,
        frame_bytes: bytes,
        resize_width: Optional[int] = None,
        resize_height: Optional[int] = None,
        blur_kernel_size: Optional[int] = None,
        diff_threshold: Optional[int] = None,
        pixel_threshold: Optional[int] = None,
        debounce_seconds: Optional[float] = None,
    ) -> bool:
        """Determines if significant motion / traversal occurred between consecutive frames."""
        try:
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return False

            rw = resize_width or settings.motion.resize_width
            rh = resize_height or settings.motion.resize_height
            bk = blur_kernel_size or settings.motion.blur_kernel_size
            if bk % 2 == 0:
                bk += 1
            dt = diff_threshold if diff_threshold is not None else settings.motion.diff_threshold
            pt = pixel_threshold if pixel_threshold is not None else settings.motion.pixel_threshold
            db = debounce_seconds if debounce_seconds is not None else settings.motion.debounce_seconds

            small = cv2.resize(img, (rw, rh))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (bk, bk), 0)

            prev = self._last_frames.get(camera_id)
            self._last_frames[camera_id] = gray

            if prev is None:
                return False

            delta = cv2.absdiff(prev, gray)
            thresh = cv2.threshold(delta, dt, 255, cv2.THRESH_BINARY)[1]
            motion_pixels = cv2.countNonZero(thresh)

            # Throttle events using configurable debounce per camera
            now_ts = time.time()
            last_event = self._last_event_time.get(camera_id, 0.0)
            if motion_pixels > pt and (now_ts - last_event) > db:
                self._last_event_time[camera_id] = now_ts
                logger.info(
                    "Significant motion detected on %s (%d px > %d threshold). Triggering exit event.",
                    camera_id,
                    motion_pixels,
                    pt,
                )
                return True
        except Exception as e:
            logger.warning("Motion check error on %s: %s", camera_id, e)

        return False

    def reset_camera(self, camera_id: str) -> None:
        """Resets cached frame and event state for a camera."""
        self._last_frames.pop(camera_id, None)
        self._last_event_time.pop(camera_id, None)


motion_detector = MotionDetector()

