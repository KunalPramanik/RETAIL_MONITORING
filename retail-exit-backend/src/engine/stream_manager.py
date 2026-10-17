"""Real-Time Camera Stream Management Engine.

Provides persistent background video capture, high-throughput in-memory frame buffering,
and fluid MJPEG streaming for local USB/webcams (device indices 0, 1) and network RTSP/HTTP cameras.
Strictly adheres to Zero-Fake-Data / Dynamic Operations Policy:
- Disconnected or pending streams render authentic CCTV Technical Standby Cards.
- Never substitutes missing streams with pre-recorded images or candidate files.
- Tracks real hardware frames explicitly with `has_real_frame`.
"""

import os
import cv2
import time
import socket
import logging
import threading
import asyncio
import queue
from datetime import datetime, timezone
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
        self.is_connected = False
        self.has_real_frame = False
        self.thread: Optional[threading.Thread] = None

        self.last_frame_bytes: Optional[bytes] = None
        self.last_annotated_frame_bytes: Optional[bytes] = None
        self.last_frame_bgr: Optional[np.ndarray] = None
        self.last_real_frame_bytes: Optional[bytes] = None
        self.last_frame_time: float = 0.0
        self.last_access_time: float = time.time()
        self.error_count: int = 0
        self.fps_observed: float = 0.0
        self.resolution: Tuple[int, int] = (1280, 720)
        self.lock = threading.Lock()
        self._newest_frame_queue: queue.Queue = queue.Queue(maxsize=1)
        
        # V8 Health Metrics
        self.reconnect_count: int = 0
        self.decode_failure_count: int = 0
        self.codec: str = "UNKNOWN"
        self.latency_ms: float = 0.0

    def push_newest_frame(self, frame_bytes: bytes, frame_bgr: np.ndarray, timestamp: float) -> None:
        """Pushes frame into size-1 newest-frame queue, dropping oldest if full (F4)."""
        try:
            if self._newest_frame_queue.full():
                try:
                    self._newest_frame_queue.get_nowait()
                except Exception:
                    pass
            self._newest_frame_queue.put_nowait((frame_bytes, frame_bgr, timestamp))
        except Exception:
            pass

    def pop_newest_frame(self) -> Optional[Tuple[bytes, np.ndarray, float]]:
        """Consumes freshest available frame from size-1 queue without latency accumulation."""
        try:
            return self._newest_frame_queue.get_nowait()
        except Exception:
            return None



    def compute_health_status(self) -> str:
        """V8 Health Status Computation. Returns granular enum."""
        if not self.is_connected:
            if self.error_count > 10:
                return "AUTH_FAILED" if "401" in str(self.source) else "OFFLINE"
            return "PENDING_SETUP"
        if self.codec in ["HEVC", "H265"]:
            return "CODEC_MISMATCH" # Needs transcoding
        if self.fps_observed > 0 and self.fps_observed < 10.0:
            return "LOW_FPS"
        if self.decode_failure_count > 50:
            return "STREAM_UNDECODABLE"
        if self.reconnect_count > 5 and not self.has_real_frame:
            return "DEGRADED"
        return "ONLINE"

    def start(self) -> None:
        """Starts the capture background thread with immediate technical standby frame."""
        if not self.is_running:
            self.is_running = True
            init_frame = self._generate_standby_frame(0)
            ret_enc, buf = cv2.imencode(".jpg", init_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret_enc:
                with self.lock:
                    self.last_frame_bytes = buf.tobytes()
                    self.last_frame_bgr = init_frame
                    self.last_frame_time = time.time()
                    self.fps_observed = 25.0
                    self.resolution = (1280, 720)
                    self.has_real_frame = False
                    self.is_connected = False

            target_func = self._capture_http_snapshot_loop if self._is_http_snapshot_source() else self._capture_loop
            self.thread = threading.Thread(target=target_func, daemon=True, name=f"Stream-{self.camera_key}")
            self.thread.start()

    def stop(self) -> None:
        """Stops the capture background thread and releases resources."""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        try:
            if isinstance(self.source, int) or (isinstance(self.source, str) and str(self.source).strip().isdigit()):
                dev_idx = int(self.source)
                # On Windows: DirectShow (CAP_DSHOW) opens in < 50ms and avoids MSMF 1.1s driver hangs
                if os.name == "nt":
                    cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        cap = cv2.VideoCapture(dev_idx, cv2.CAP_MSMF)
                    if not cap.isOpened():
                        cap = cv2.VideoCapture(dev_idx)
                else:
                    cap = cv2.VideoCapture(dev_idx)
            else:
                src_str = str(self.source).strip()
                if src_str.startswith("rtsp://"):
                    import urllib.parse
                    try:
                        parsed = urllib.parse.urlparse(src_str)
                        h, p = parsed.hostname, parsed.port or 554
                        if h:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                s.settimeout(0.7)
                                if s.connect_ex((h, p)) != 0:
                                    return None
                    except Exception:
                        return None

                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;2000000|stimeout;2000000|rw_timeout;2000000"
                    try:
                        cap = cv2.VideoCapture(src_str, cv2.CAP_FFMPEG, [
                            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 2000,
                            cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000,
                        ])
                    except Exception:
                        cap = cv2.VideoCapture(src_str, cv2.CAP_FFMPEG)
                else:
                    cap = cv2.VideoCapture(src_str)

            # If RTSP connection on given path failed but host port 554 is reachable, auto-probe candidate NVR paths
            if (cap is None or not cap.isOpened()) and isinstance(self.source, str) and str(self.source).strip().startswith("rtsp://"):
                try:
                    parsed = urllib.parse.urlparse(str(self.source).strip())
                    host = parsed.hostname
                    port = parsed.port or 554
                    user = parsed.username or "admin"
                    pwd = parsed.password or ""

                    auth_candidates = [(user, pwd)]
                    for def_a in [("admin", "123456"), ("admin", ""), ("admin", "admin"), ("admin", "12345")]:
                        if def_a not in auth_candidates:
                            auth_candidates.append(def_a)

                    nvr_candidate_paths = [
                        parsed.path,
                        "/unicast/c1/s0/live",
                        "/unicast/c1/s1/live",
                        "/media/video1",
                        "/media/video2",
                        "/Live/Ch0/101",
                        "/Live/Ch0/102",
                        "/Streaming/Channels/101",
                        "/Streaming/Channels/102",
                        "/cam/realmonitor?channel=1&subtype=0",
                        "/cam/realmonitor?channel=1&subtype=1",
                        "/live/ch0",
                        "/live/ch1",
                        "/h264Preview_01_main",
                        "/h264Preview_01_sub",
                    ]
                    seen_p = set()
                    unique_paths = []
                    for p_item in nvr_candidate_paths:
                        if p_item and p_item not in seen_p:
                            seen_p.add(p_item)
                            unique_paths.append(p_item)

                    for a_u, a_p in auth_candidates:
                        a_pfx = f"{a_u}:{a_p}@" if a_u else ""
                        for p_cand in unique_paths:
                            candidate_url = f"rtsp://{a_pfx}{host}:{port}{p_cand}"
                            if candidate_url == str(self.source).strip():
                                continue
                            try:
                                c_test = cv2.VideoCapture(candidate_url, cv2.CAP_FFMPEG, [
                                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1500,
                                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1500,
                                ])
                            except Exception:
                                c_test = cv2.VideoCapture(candidate_url, cv2.CAP_FFMPEG)

                            if c_test and c_test.isOpened():
                                ret_t, _ = c_test.read()
                                if ret_t:
                                    logger.info("Auto-discovered working NVR RTSP stream: %s (replaced %s)", candidate_url, self.source)
                                    self.source = candidate_url
                                    cap = c_test
                                    break
                                else:
                                    c_test.release()
                            elif c_test:
                                c_test.release()
                        if cap and cap.isOpened():
                            break
                except Exception as ap_err:
                    logger.debug("Auto-probe NVR candidate paths failed: %s", ap_err)

            if cap and cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                try:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 2000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000)
                except Exception:
                    pass
                # AA.4 Codec checkpoint: detect H.265/HEVC streams that break MediaMTX WebRTC.
                # MediaMTX WebRTC output only supports H.264/VP8/VP9/AV1 — not H.265.
                # Cameras whose native main-stream is H.265 will produce a broken or black
                # WebRTC browser preview without an explicit transcoding rule.
                try:
                    raw_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                    if raw_fourcc:
                        fourcc_str = "".join(
                            chr((raw_fourcc >> (8 * i)) & 0xFF) for i in range(4)
                        ).strip("\x00").upper()
                        hevc_fourccs = {"HEVC", "H265", "HVC1", "HEV1", "X265"}
                        if any(h in fourcc_str for h in hevc_fourccs):
                            logger.warning(
                                "[AA.4] H.265/HEVC stream detected on camera '%s' (fourcc=%s). "
                                "MediaMTX WebRTC only supports H.264/VP8/VP9/AV1. "
                                "Browser preview will be broken or black without a transcoding rule. "
                                "Fix: add a MediaMTX path rule with 'runOnReady: ffmpeg -i <source> -c:v libx264 ...' "
                                "or switch the camera to H.264 sub-stream encoding.",
                                self.camera_key, fourcc_str,
                            )
                except Exception:
                    pass
                return cap
            else:
                if cap:
                    cap.release()
                return None
        except Exception as e:
            logger.debug("Failed opening video capture for %s: %s", self.camera_key, e)
            return None

    def _generate_standby_frame(self, tick: int) -> np.ndarray:
        """Generates an authentic, professional CCTV Technical Standby Card with live UTC time."""
        w, h = 1280, 720
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (18, 22, 28)  # Deep tactical dark grey-blue

        # Technical CCTV grid
        grid_color = (28, 36, 46)
        for x in range(0, w, 60):
            cv2.line(frame, (x, 0), (x, h), grid_color, 1)
        for y in range(0, h, 60):
            cv2.line(frame, (0, y), (w, y), grid_color, 1)

        # Subtle dynamic scanning line (confirms backend video pipeline is active)
        scan_y = int((tick * 8) % h)
        cv2.line(frame, (0, scan_y), (w, scan_y), (45, 65, 85), 2)
        if 0 < scan_y < h - 2:
            cv2.line(frame, (0, scan_y + 1), (w, scan_y + 1), (30, 45, 60), 1)

        # Center reticle & corner framing
        center_x, center_y = w // 2, h // 2
        bracket_len = 35
        bracket_color = (60, 75, 95)
        # Top-left corner
        cv2.line(frame, (40, 40), (40 + bracket_len, 40), bracket_color, 2)
        cv2.line(frame, (40, 40), (40, 40 + bracket_len), bracket_color, 2)
        # Top-right corner
        cv2.line(frame, (w - 40, 40), (w - 40 - bracket_len, 40), bracket_color, 2)
        cv2.line(frame, (w - 40, 40), (w - 40, 40 + bracket_len), bracket_color, 2)
        # Bottom-left corner
        cv2.line(frame, (40, h - 40), (40 + bracket_len, h - 40), bracket_color, 2)
        cv2.line(frame, (40, h - 40), (40, h - 40 - bracket_len), bracket_color, 2)
        # Bottom-right corner
        cv2.line(frame, (w - 40, h - 40), (w - 40 - bracket_len, h - 40), bracket_color, 2)
        cv2.line(frame, (w - 40, h - 40), (w - 40, h - 40 - bracket_len), bracket_color, 2)

        # Central Standby Box
        box_w, box_h = 560, 160
        box_x1 = center_x - box_w // 2
        box_y1 = center_y - box_h // 2
        cv2.rectangle(frame, (box_x1, box_y1), (box_x1 + box_w, box_y1 + box_h), (25, 32, 42), -1)
        cv2.rectangle(frame, (box_x1, box_y1), (box_x1 + box_w, box_y1 + box_h), (70, 85, 105), 1)

        # Technical status text inside box
        cv2.putText(frame, "[ NO LIVE SIGNAL // AWAITING STREAM INPUT ]", (box_x1 + 30, box_y1 + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (235, 165, 45), 2)
        cv2.putText(frame, f"ENDPOINT: {str(self.source)}", (box_x1 + 30, box_y1 + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (190, 205, 220), 1)
        cv2.putText(frame, "STATUS: STANDBY CARD // POLLING PHYSICAL DEVICE", (box_x1 + 30, box_y1 + 115), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (130, 145, 160), 1)
        pulse_dots = "." * ((tick // 6) % 4)
        cv2.putText(frame, f"RECONNECTING{pulse_dots}", (box_x1 + 30, box_y1 + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (235, 165, 45), 1)

        # Top HUD overlay banner
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 85), (12, 15, 20), -1)
        cv2.rectangle(overlay, (0, h - 55), (w, h), (12, 15, 20), -1)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

        cv2.putText(frame, "SEC-OPS SURVEILLANCE FLEET // REAL-TIME CV NODE", (30, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (217, 119, 6), 2)
        disp_title = f"{self.camera_key.upper()}"
        cv2.putText(frame, f"CHANNEL: {disp_title} | TARGET: {self.source}", (30, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # Live UTC timestamp updated continuously every frame
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-4] + " UTC"
        cv2.putText(frame, f"REC [STANDBY]  {now_str}", (30, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 195, 210), 1)
        cv2.putText(frame, "STATUS: AWAITING STREAM FEED // 25.0 FPS", (w - 490, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 165, 45), 2)

        return frame

    def _is_http_snapshot_source(self) -> bool:
        if not isinstance(self.source, str):
            return False
        src = self.source.lower().strip()
        if not (src.startswith("http://") or src.startswith("https://")):
            return False
        snapshot_indicators = ("/snapshot", ".jpg", ".jpeg", "/shot.jpg", "/picture", "/image.cgi", "/snap.cgi", "/image")
        return any(ind in src for ind in snapshot_indicators)

    def _capture_http_snapshot_loop(self) -> None:
        """High-throughput HTTP/HTTPS snapshot frame acquisition loop for web/IP cameras."""
        import httpx
        import urllib.parse

        src_str = str(self.source).strip()
        parsed = urllib.parse.urlparse(src_str)
        auth = self.auth_tuple
        if not auth and parsed.username is not None:
            auth = (parsed.username, parsed.password or "")
        elif not auth:
            auth = ("admin", "")

        port_str = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
        netloc = f"{parsed.hostname}{port_str}"
        clean_url = urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

        consecutive_failures = 0
        tick = 0
        headers = {"Connection": "close", "User-Agent": "Mozilla/5.0"}

        while self.is_running:
            tick += 1
            try:
                with httpx.Client(timeout=1.5, headers=headers, follow_redirects=True) as client:
                    resp = client.get(clean_url, auth=auth)

                if resp.status_code == 200 and len(resp.content) > 500 and (
                    resp.content.startswith(b"\xff\xd8\xff")
                    or "image" in resp.headers.get("content-type", "")
                    or resp.headers.get("content-type") == "application/octet-stream"
                ):
                    consecutive_failures = 0
                    jpeg_bytes = resp.content
                    nparr = np.frombuffer(jpeg_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if frame is not None and frame.size > 0:
                        h, w = frame.shape[:2]
                        now = time.time()
                        self.push_newest_frame(jpeg_bytes, frame, now)
                        with self.lock:
                            self.last_frame_bytes = jpeg_bytes
                            self.last_real_frame_bytes = jpeg_bytes
                            self.last_frame_bgr = frame
                            if self.last_frame_time > 0:
                                dt = now - self.last_frame_time
                                if dt > 0:
                                    self.fps_observed = round(0.9 * self.fps_observed + 0.1 * (1.0 / dt), 1)
                            self.last_frame_time = now
                            self.resolution = (w, h)
                            self.has_real_frame = True
                            self.is_connected = True
                    time.sleep(0.040)
                    continue
                else:
                    consecutive_failures += 1
            except Exception:
                consecutive_failures += 1

            if consecutive_failures > 3:
                now = time.time()
                frame_anim = self._generate_standby_frame(tick)
                ret_enc, buf = cv2.imencode(".jpg", frame_anim, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ret_enc:
                    with self.lock:
                        self.last_frame_bytes = buf.tobytes()
                        self.last_frame_bgr = frame_anim
                        self.last_frame_time = now
                        self.fps_observed = 25.0
                        self.resolution = (1280, 720)
                        self.has_real_frame = False
                        self.is_connected = False
                time.sleep(0.4)
            else:
                time.sleep(0.08)

    def _capture_loop(self) -> None:
        """Continuous background frame acquisition loop."""
        cap = self._open_capture()
        consecutive_failures = 0
        tick = 0

        while self.is_running:
            tick += 1
            if cap is None or not cap.isOpened():
                consecutive_failures += 1
                now = time.time()
                frame_anim = self._generate_standby_frame(tick)
                ret_enc, buf = cv2.imencode(".jpg", frame_anim, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ret_enc:
                    with self.lock:
                        self.last_frame_bytes = buf.tobytes()
                        self.last_frame_bgr = frame_anim
                        self.last_frame_time = now
                        self.fps_observed = 25.0
                        self.resolution = (1280, 720)
                        self.has_real_frame = False
                        self.is_connected = False

                # Attempt capture re-open periodically (every ~3 seconds / 75 frames)
                if consecutive_failures % 75 == 0:
                    cap = self._open_capture()

                time.sleep(0.040)  # ~25 FPS
                continue

            try:
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    consecutive_failures = 0
                    self.reconnect_count = 0
                    self.error_count = 0
                    h, w = frame.shape[:2]
                    ret_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if ret_enc:
                        jpeg_bytes = buf.tobytes()
                        now = time.time()
                        self.push_newest_frame(jpeg_bytes, frame, now)
                        with self.lock:
                            self.last_frame_bytes = jpeg_bytes
                            self.last_real_frame_bytes = jpeg_bytes
                            self.last_frame_bgr = frame
                            if self.last_frame_time > 0:
                                dt = now - self.last_frame_time
                                if dt > 0:
                                    self.fps_observed = round(0.9 * self.fps_observed + 0.1 * (1.0 / dt), 1)
                            self.last_frame_time = now
                            self.resolution = (w, h)
                            self.has_real_frame = True
                            self.is_connected = True
                    # Limit capture loop rate to ~30 FPS to prevent unnecessary CPU load
                    time.sleep(0.030)
                else:
                    consecutive_failures += 1
                    with self.lock:
                        self.has_real_frame = False
                        self.is_connected = False
                    if consecutive_failures > 5:
                        cap.release()
                        cap = None
                    time.sleep(0.040)
            except Exception as ex:
                consecutive_failures += 1
                with self.lock:
                    self.has_real_frame = False
                    self.is_connected = False
                time.sleep(0.040)

        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


class CameraStreamManager:
    """Singleton stream coordinator managing live video streams across the fleet."""

    _instance: Optional["CameraStreamManager"] = None

    def __init__(self):
        self._streams: Dict[str, CameraStreamSession] = {}
        self._lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        CameraStreamManager._instance = self

    @classmethod
    def get_instance(cls) -> "CameraStreamManager":
        if cls._instance is None:
            cls._instance = CameraStreamManager()
        return cls._instance

    @property
    def sessions(self) -> Dict[str, CameraStreamSession]:
        return self._streams

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    @property
    def sessions(self) -> Dict[str, CameraStreamSession]:
        return self._streams

    def _resolve_source(
        self, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None, credentials: Optional[str] = None
    ) -> Tuple[str | int, str]:
        """Resolves source into an OpenCV-compatible target and unique cache key."""
        clean_ip = str(ip or "").strip().lower()
        clean_url = str(stream_url or "").strip()
        clean_creds = str(credentials or "").strip()
        auth_prefix = ""
        if clean_creds and ":" in clean_creds and not clean_creds.startswith("secops/"):
            auth_prefix = f"{clean_creds}@"

        # Local webcam detection
        if clean_url in ("0", "1", "2"):
            dev_idx = int(clean_url)
            return dev_idx, f"local_cam_{dev_idx}"
        if clean_ip in ("0", "1", "2", "webcam"):
            dev_idx = int(clean_ip) if clean_ip.isdigit() else 0
            return dev_idx, f"local_cam_{dev_idx}"

        if clean_url.startswith(("http://", "https://", "rtsp://")):
            if clean_url.startswith("rtsp://") and "@" not in clean_url and auth_prefix:
                clean_url = clean_url.replace("rtsp://", f"rtsp://{auth_prefix}")
            return clean_url, clean_url

        # Check if rtsp_path is a full URL or snapshot path
        path = rtsp_path.strip()
        if path.startswith(("http://", "https://", "rtsp://")):
            if path.startswith("rtsp://") and "@" not in path and auth_prefix:
                path = path.replace("rtsp://", f"rtsp://{auth_prefix}")
            return path, path

        if path and not path.startswith("/"):
            path = "/" + path

        clean_host = clean_ip
        port_part = ":554"
        if ":" in clean_host:
            parts = clean_host.split(":", 1)
            clean_host = parts[0]
            port_part = f":{parts[1]}"

        if path.lower().startswith(("/snapshot", "/shot.jpg", "/picture", "/cgi-bin/snapshot.cgi")) or port_part in (":80", ":8080"):
            target = f"http://{clean_host}{port_part if port_part != ':80' else ''}{path or '/snapshot'}"
            return target, target

        # Build RTSP URL with authentication credentials
        target = f"rtsp://{auth_prefix}{clean_host}{port_part}{path}"
        return target, target

    def get_session(
        self, camera_key: str, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None, credentials: Optional[str] = None
    ) -> CameraStreamSession:
        """Retrieves or starts a persistent stream session with canonical device sharing."""
        with self._lock:
            if camera_key in self._streams:
                session = self._streams[camera_key]
                session.last_access_time = time.time()
                return session

            source, canonical_key = self._resolve_source(ip, rtsp_path, stream_url, credentials)
            if canonical_key in self._streams:
                session = self._streams[canonical_key]
                self._streams[camera_key] = session
                session.last_access_time = time.time()
                return session

            session = CameraStreamSession(camera_key, source)
            session.start()
            self._streams[camera_key] = session
            self._streams[canonical_key] = session
            return session

    def get_latest_jpeg(
        self, camera_key: str, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None, credentials: Optional[str] = None, max_wait_sec: float = 1.0
    ) -> Tuple[Optional[bytes], float]:
        """Returns the most recent JPEG frame (live video or technical standby) with near-zero latency."""
        t0 = time.perf_counter()
        session = self.get_session(camera_key, ip, rtsp_path, stream_url, credentials)

        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            with session.lock:
                if session.last_frame_bytes is not None:
                    latency = round((time.perf_counter() - t0) * 1000.0, 1)
                    return session.last_frame_bytes, latency
            time.sleep(0.05)

        latency = round((time.perf_counter() - t0) * 1000.0, 1)
        return None, latency

    def get_latest_real_jpeg(
        self, camera_key: str, ip: str, rtsp_path: str = "", stream_url: Optional[str] = None, credentials: Optional[str] = None, max_wait_sec: float = 1.0
    ) -> Tuple[Optional[bytes], float]:
        """Returns the most recent JPEG frame ONLY if captured from authentic live hardware/RTSP stream."""
        t0 = time.perf_counter()
        session = self.get_session(camera_key, ip, rtsp_path, stream_url, credentials)

        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            q_item = session.pop_newest_frame()
            if q_item is not None:
                latency = round((time.perf_counter() - t0) * 1000.0, 1)
                return q_item[0], latency
            with session.lock:
                if session.has_real_frame and session.last_real_frame_bytes is not None:
                    latency = round((time.perf_counter() - t0) * 1000.0, 1)
                    return session.last_real_frame_bytes, latency
            time.sleep(0.01)

        latency = round((time.perf_counter() - t0) * 1000.0, 1)
        return None, latency

    async def generate_mjpeg_stream(
        self,
        camera_key: str,
        ip: str,
        rtsp_path: str = "",
        stream_url: Optional[str] = None,
        credentials: Optional[str] = None,
        fps: int = 15,
        raw: bool = False,
    ) -> AsyncGenerator[bytes, None]:
        """Yields continuous multipart MJPEG stream frames."""
        session = self.get_session(camera_key, ip, rtsp_path, stream_url, credentials)
        frame_interval = 1.0 / max(1, min(fps, 30))
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"

        while True:
            t_start = time.time()
            session.last_access_time = t_start
            frame_bytes = None
            with session.lock:
                if not raw and session.last_annotated_frame_bytes is not None:
                    frame_bytes = session.last_annotated_frame_bytes
                elif session.last_frame_bytes is not None:
                    frame_bytes = session.last_frame_bytes
                elif session.last_annotated_frame_bytes is not None:
                    frame_bytes = session.last_annotated_frame_bytes

            if frame_bytes is not None:
                yield boundary + frame_bytes + b"\r\n"
            else:
                await asyncio.sleep(0.1)
                continue

            elapsed = time.time() - t_start
            sleep_needed = max(0.01, frame_interval - elapsed)
            await asyncio.sleep(sleep_needed)

    def get_latest_frame_bytes(self, camera_key: str) -> Optional[bytes]:
        """Convenience method to retrieve the latest frame bytes for an existing active stream."""
        with self._lock:
            session = self._streams.get(camera_key)
            if session:
                with session.lock:
                    return session.last_real_frame_bytes or session.last_frame_bytes
        return None

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
stream_manager = camera_stream_manager


def get_latest_frame_bytes(camera_key: str) -> Optional[bytes]:
    """Retrieves the latest frame bytes for an active camera from the global manager."""
    return camera_stream_manager.get_latest_frame_bytes(camera_key)

