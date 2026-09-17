"""Real-Time Camera Stream Management Engine.

Provides persistent background video capture, high-throughput in-memory frame buffering,
and fluid MJPEG streaming for local USB/webcams (device indices 0, 1) and network RTSP/HTTP cameras.
Eliminates repetitive cv2.VideoCapture open/close latency and Windows device contention.
"""

import os
import cv2
import time
import socket
import logging
import threading
import asyncio
from typing import Optional, Dict, Tuple, AsyncGenerator
import numpy as np

logger = logging.getLogger("secops.stream_manager")


class CameraStreamSession:
    """Manages an active persistent OpenCV capture stream in a background thread."""

    def __init__(self, camera_key: str, source: str | int, auth_tuple: Optional[Tuple[str, str]] = None):
        self.camera_key = camera_key
        self.source = source
        self.auth_tuple = auth_tuple
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

        self.last_frame_bytes: Optional[bytes] = None
        self.last_frame_bgr: Optional[np.ndarray] = None
        self.last_frame_time: float = 0.0
        self.last_access_time: float = time.time()
        self.error_count: int = 0
        self.fps_observed: float = 0.0
        self.resolution: Tuple[int, int] = (0, 0)
        self.lock = threading.Lock()

    def start(self) -> None:
        """Starts the capture background thread."""
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True, name=f"Stream-{self.camera_key}")
            self.thread.start()

    def stop(self) -> None:
        """Stops the capture background thread and releases resources."""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        try:
            if isinstance(self.source, int) or (isinstance(self.source, str) and self.source.isdigit()):
                dev_idx = int(self.source)
                # Windows DirectShow backend for faster start and low latency
                cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(dev_idx)
            else:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"
                cap = cv2.VideoCapture(str(self.source), cv2.CAP_FFMPEG)

            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return cap
            else:
                cap.release()
                return None
        except Exception as e:
            logger.debug("Failed opening video capture for %s: %s", self.camera_key, e)
            return None

    def _capture_loop(self) -> None:
        """Continuous background frame acquisition loop."""
        cap = self._open_capture()
        consecutive_failures = 0

        while self.is_running:
            if cap is None or not cap.isOpened():
                consecutive_failures += 1
                sleep_time = min(5.0, 0.5 * (consecutive_failures ** 1.2))
                time.sleep(sleep_time)
                cap = self._open_capture()
                continue

            try:
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    consecutive_failures = 0
                    h, w = frame.shape[:2]
                    ret_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if ret_enc:
                        jpeg_bytes = buf.tobytes()
                        now = time.time()
                        with self.lock:
                            self.last_frame_bytes = jpeg_bytes
                            self.last_frame_bgr = frame
                            if self.last_frame_time > 0:
                                dt = now - self.last_frame_time
                                if dt > 0:
                                    self.fps_observed = round(0.9 * self.fps_observed + 0.1 * (1.0 / dt), 1)
                            self.last_frame_time = now
                            self.resolution = (w, h)
                    # Limit capture loop rate to ~30 FPS to prevent unnecessary CPU load
                    time.sleep(0.030)
                else:
                    consecutive_failures += 1
                    if consecutive_failures > 5:
                        cap.release()
                        cap = None
                    time.sleep(0.1)
            except Exception as ex:
                consecutive_failures += 1
                time.sleep(0.1)

        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


class CameraStreamManager:
    """Singleton stream coordinator managing live video streams across the fleet."""

    def __init__(self):
        self._streams: Dict[str, CameraStreamSession] = {}
        self._lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def _resolve_source(
        self, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None
    ) -> Tuple[str | int, str]:
        """Resolves source into an OpenCV-compatible target and unique cache key."""
        clean_ip = str(ip or "").strip().lower()
        clean_url = str(stream_url or "").strip()

        # Local webcam detection
        if clean_url in ("0", "1", "2"):
            dev_idx = int(clean_url)
            return dev_idx, f"local_cam_{dev_idx}"
        if clean_ip in ("0", "1", "2", "webcam"):
            dev_idx = int(clean_ip) if clean_ip.isdigit() else 0
            return dev_idx, f"local_cam_{dev_idx}"

        if clean_url.startswith(("http://", "https://", "rtsp://")):
            return clean_url, clean_url

        # Build RTSP URL
        path = rtsp_path.strip()
        if path and not path.startswith("/"):
            path = "/" + path
        target = f"rtsp://{ip}:554{path}"
        return target, target

    def get_session(
        self, camera_key: str, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None
    ) -> CameraStreamSession:
        """Retrieves or starts a persistent stream session."""
        with self._lock:
            if camera_key in self._streams:
                session = self._streams[camera_key]
                session.last_access_time = time.time()
                return session

            source, _ = self._resolve_source(ip, rtsp_path, stream_url)
            session = CameraStreamSession(camera_key, source)
            session.start()
            self._streams[camera_key] = session
            return session

    def get_latest_jpeg(
        self, camera_key: str, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None, max_wait_sec: float = 1.0
    ) -> Tuple[Optional[bytes], float]:
        """Returns the most recent JPEG frame directly from memory buffer with near-zero latency."""
        t0 = time.perf_counter()
        session = self.get_session(camera_key, ip, rtsp_path, stream_url)

        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            with session.lock:
                if session.last_frame_bytes is not None:
                    latency = round((time.perf_counter() - t0) * 1000.0, 1)
                    return session.last_frame_bytes, latency
            time.sleep(0.05)

        latency = round((time.perf_counter() - t0) * 1000.0, 1)
        return None, latency

    async def generate_mjpeg_stream(
        self, camera_key: str, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None, fps: int = 15
    ) -> AsyncGenerator[bytes, None]:
        """Yields continuous multipart MJPEG stream frames."""
        session = self.get_session(camera_key, ip, rtsp_path, stream_url)
        frame_interval = 1.0 / max(1, min(fps, 30))
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"

        while True:
            t_start = time.time()
            session.last_access_time = t_start
            frame_bytes = None
            with session.lock:
                if session.last_frame_bytes is not None:
                    frame_bytes = session.last_frame_bytes

            if frame_bytes is not None:
                yield boundary + frame_bytes + b"\r\n"
            else:
                # Small wait if no frame is ready yet
                await asyncio.sleep(0.1)
                continue

            elapsed = time.time() - t_start
            sleep_needed = max(0.01, frame_interval - elapsed)
            await asyncio.sleep(sleep_needed)

    def stop_session(self, camera_key: str) -> None:
        """Stops and removes a camera stream session."""
        with self._lock:
            session = self._streams.pop(camera_key, None)
            if session:
                session.stop()

    def stop_all(self) -> None:
        """Stops all active camera streams (call on server shutdown)."""
        with self._lock:
            for s in self._streams.values():
                s.stop()
            self._streams.clear()


# Global stream manager singleton
camera_stream_manager = CameraStreamManager()
