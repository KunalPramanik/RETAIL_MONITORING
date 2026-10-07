"""Camera Network Prober & Frame Capture

Provides robust RTSP/HTTP network diagnostics, socket connectivity testing,
device index fallback, multi-port auto-negotiation, and live frame acquisition.
"""

import os
import time
import socket
import urllib.parse
import logging
from typing import Optional, Dict, Any, List, Tuple
import cv2
import httpx

from src.core.config import settings
from src.engine.stream_manager import camera_stream_manager

logger = logging.getLogger("secops.api.camera_prober")


def capture_camera_frame_sync(
    ip: str,
    rtsp_path: str,
    credentials: Optional[str] = None,
    sub_stream_path: Optional[str] = None,
    timeout_sec: Optional[float] = None,
    stream_url: Optional[str] = None,
    return_diag: bool = False,
) -> tuple:
    """Attempts to capture a real frame from RTSP stream (main/sub), HTTP endpoints, or local devices."""
    if timeout_sec is None:
        timeout_sec = settings.camera.capture_timeout_sec
    t0 = time.perf_counter()
    diag_info: Dict[str, Any] = {
        "stage": "UNKNOWN",
        "error_message": "",
        "host": str(ip or ""),
        "port": 554,
        "is_reachable": False,
        "is_port_open": False,
        "is_handshake_ok": False,
    }

    dev_idx = None
    if settings.ENVIRONMENT.lower() in ("development", "dev", "test"):
        if stream_url and str(stream_url).strip() in ("0", "1", "2"):
            dev_idx = int(stream_url.strip())
        elif ip and str(ip).strip() in ("0", "1", "2", "webcam"):
            dev_idx = int(ip.strip()) if ip.strip().isdigit() else 0

    if dev_idx is not None:
        diag_info["host"] = f"dev_{dev_idx}"
        diag_info["is_reachable"] = True
        try:
            buf, lat = camera_stream_manager.get_latest_real_jpeg(f"dev_{dev_idx}", str(dev_idx), "", None, max_wait_sec=0.8)
            if buf is not None:
                diag_info["stage"] = "SUCCESS"
                return (buf, f"Local Camera Device ({dev_idx})", lat, diag_info) if return_diag else (buf, f"Local Camera Device ({dev_idx})", lat)
        except Exception:
            pass

        try:
            cap = cv2.VideoCapture(dev_idx, cv2.CAP_MSMF)
            if not cap.isOpened():
                cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(dev_idx)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    ret_enc, buf_enc = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if ret_enc:
                        latency = round((time.perf_counter() - t0) * 1000.0, 1)
                        diag_info["stage"] = "SUCCESS"
                        diag_info["is_port_open"] = True
                        diag_info["is_handshake_ok"] = True
                        return (buf_enc.tobytes(), f"Local Camera Device ({dev_idx})", latency, diag_info) if return_diag else (buf_enc.tobytes(), f"Local Camera Device ({dev_idx})", latency)
                else:
                    diag_info["stage"] = "LOCAL_DEVICE_PREEMPTED"
                    diag_info["error_message"] = (
                        f"Local camera (index {dev_idx}) opened but read() failed — "
                        "the device may be in use by another application (e.g. browser, Teams) "
                        "or blocked by Windows Camera Privacy Settings."
                    )
            else:
                diag_info["stage"] = "LOCAL_DEVICE_UNAVAILABLE"
                diag_info["error_message"] = f"Local camera (index {dev_idx}) could not be opened on any capture backend (MSMF/DShow)."
        except Exception as exc:
            diag_info["stage"] = "LOCAL_DEVICE_ERROR"
            diag_info["error_message"] = f"Local camera capture error for index {dev_idx}: {exc}"

        latency = round((time.perf_counter() - t0) * 1000.0, 1)
        return (None, "Local Camera Unavailable", latency, diag_info) if return_diag else (None, "Local Camera Unavailable", latency)

    # Parse credentials cleanly
    auth_tuples = []
    if stream_url and ("@" in str(stream_url)):
        try:
            parsed_s = urllib.parse.urlparse(str(stream_url))
            if parsed_s.username is not None:
                auth_tuples.append((parsed_s.username, parsed_s.password or ""))
        except Exception:
            pass

    if credentials:
        clean_c = str(credentials).strip()
        if ":" in clean_c:
            u, p = clean_c.split(":", 1)
            auth_tuples.append((u, p))
        elif not clean_c.startswith("secops/"):
            auth_tuples.append((clean_c, ""))
        auth_tuples.append(None)
        auth_tuples.extend([("admin", ""), ("admin", "admin"), ("admin", "12345")])
    else:
        # Default to unauthenticated stream pull first, then standard IP camera defaults
        auth_tuples.append(None)
        # Common IP camera defaults as fallbacks (Juan/Jooan/Hiseeu default is admin with blank pass)
        auth_tuples.extend([("admin", ""), ("admin", "admin"), ("admin", "12345")])

    # Distinct auth tuples while preserving order
    seen = set()
    distinct_auth = []
    for a in auth_tuples:
        key = a if a is not None else ("__NONE__", "")
        if key not in seen:
            seen.add(key)
            distinct_auth.append(a)

    auth_part = (
        f"{distinct_auth[0][0]}:{distinct_auth[0][1]}@"
        if (distinct_auth and distinct_auth[0] is not None and distinct_auth[0] != ("__NONE__", ""))
        else ""
    )

    # 2. Check direct stream_url if provided
    if stream_url and str(stream_url).startswith(("http://", "https://", "rtsp://")):
        is_stream_open = False
        try:
            parsed_u = urllib.parse.urlparse(stream_url)
            u_host = parsed_u.hostname
            u_port = parsed_u.port or (443 if parsed_u.scheme == "https" else (554 if parsed_u.scheme == "rtsp" else 80))
            if u_host:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.25)
                    is_stream_open = (s.connect_ex((u_host, u_port)) == 0)
        except Exception:
            is_stream_open = False

        if is_stream_open:
            # Direct HTTP/HTTPS snapshot or stream
            if stream_url.startswith(("http://", "https://")):
                try:
                    headers = {"Connection": "close", "AppUser as User-Agent": "Mozilla/5.0"}
                    with httpx.Client(timeout=min(timeout_sec, 1.5), follow_redirects=True, headers=headers) as client:
                        for auth in distinct_auth:
                            try:
                                resp = client.get(stream_url, auth=auth)
                                if resp.status_code == 200 and len(resp.content) > 500:
                                    if (
                                        resp.content.startswith(b"\xff\xd8\xff")
                                        or "image" in resp.headers.get("content-type", "")
                                        or resp.headers.get("content-type") == "application/octet-stream"
                                    ):
                                        latency = round((time.perf_counter() - t0) * 1000.0, 1)
                                        diag_info["stage"] = "SUCCESS"
                                        diag_info["is_port_open"] = True
                                        diag_info["is_handshake_ok"] = True
                                        diag_info["suggested_stream_url"] = stream_url
                                        diag_info["error_message"] = ""
                                        return (resp.content, f"Direct Stream URL ({stream_url})", latency, diag_info) if return_diag else (resp.content, f"Direct Stream URL ({stream_url})", latency)
                            except Exception:
                                pass
                except Exception:
                    pass

            # Try OpenCV on stream_url (RTSP, MJPEG, or HTTP video)
            try:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"
                cap = cv2.VideoCapture(stream_url)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1500)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1500)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None and frame.size > 0:
                        ret_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        if ret_enc:
                            latency = round((time.perf_counter() - t0) * 1000.0, 1)
                            diag_info["stage"] = "SUCCESS"
                            diag_info["is_port_open"] = True
                            diag_info["is_handshake_ok"] = True
                            diag_info["suggested_stream_url"] = stream_url
                            diag_info["error_message"] = ""
                            return (buf.tobytes(), f"Direct Stream Video ({stream_url})", latency, diag_info) if return_diag else (buf.tobytes(), f"Direct Stream Video ({stream_url})", latency)
                else:
                    cap.release()
            except Exception:
                pass

    # Derive sub-stream path if not provided
    if not sub_stream_path:
        if "101" in rtsp_path:
            sub_stream_path = rtsp_path.replace("101", "102")
        elif "ch0" in rtsp_path:
            sub_stream_path = rtsp_path.replace("ch0", "ch1")

    # Parse target host and port cleanly
    clean_ip = str(ip or "").strip()
    target_host = clean_ip
    target_port = 554
    if ":" in clean_ip and not clean_ip.startswith(("http://", "https://", "rtsp://")):
        parts = clean_ip.split(":", 1)
        target_host = parts[0]
        try:
            target_port = int(parts[1])
        except ValueError:
            target_port = 554

    # 3. Candidate RTSP URLs (try main, then sub-stream) if port is reachable
    is_rtsp_reachable = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.35)
            is_rtsp_reachable = (s.connect_ex((target_host, target_port)) == 0)
    except Exception:
        is_rtsp_reachable = False

    diag_info["is_port_open"] = is_rtsp_reachable

    open_ports: List[int] = []
    host_responds: bool = False

    if not is_rtsp_reachable:
        # Probe configured fallback ports to distinguish host unreachable vs port closed
        # and support smart multi-port camera auto-negotiation
        for test_p in settings.camera.discovery_ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.15)
                    if s.connect_ex((target_host, test_p)) == 0:
                        open_ports.append(test_p)
            except Exception:
                pass

        host_responds = len(open_ports) > 0
        diag_info["is_reachable"] = host_responds
        if not host_responds:
            diag_info["stage"] = "HOST_UNREACHABLE"
            diag_info["error_message"] = (
                f"Host Unreachable: Camera at '{target_host}' did not respond to network probes. "
                "Confirm camera is powered on and connected to the store network."
            )
        else:
            diag_info["stage"] = "PORT_CLOSED"
            diag_info["error_message"] = (
                f"Port Closed: Host '{target_host}' is reachable, but TCP port {target_port} is closed. "
                f"Probed open camera ports: {open_ports}. Attempting stream auto-negotiation..."
            )
    else:
        diag_info["is_reachable"] = True
        diag_info["stage"] = "RTSP_HANDSHAKE_FAILED"
        diag_info["error_message"] = (
            f"RTSP Handshake Failed: Port {target_port} is open on {target_host}, but RTSP handshake failed "
            f"on path '{rtsp_path}'. Verify the stream path for this camera model (e.g. /live/ch0, /Streaming/Channels/101, /cam/realmonitor)."
        )

    if is_rtsp_reachable:
        candidate_rtsp_urls = []
        if rtsp_path:
            candidate_rtsp_urls.append((f"rtsp://{auth_part}{target_host}:{target_port}{rtsp_path}", "RTSP Main Stream"))
        if sub_stream_path and sub_stream_path != rtsp_path:
            candidate_rtsp_urls.append((f"rtsp://{auth_part}{target_host}:{target_port}{sub_stream_path}", "RTSP Sub Stream"))

        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;2000000"

        for url, desc in candidate_rtsp_urls:
            try:
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1500)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1500)
                if cap.isOpened():
                    diag_info["is_handshake_ok"] = True
                    # AA.4: inspect codec before read — H.265 produces decode failures on MediaMTX WebRTC
                    codec_warning = ""
                    try:
                        raw_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                        if raw_fourcc:
                            fourcc_str = "".join(
                                chr((raw_fourcc >> (8 * i)) & 0xFF) for i in range(4)
                            ).strip("\x00").upper()
                            hevc_fourccs = {"HEVC", "H265", "HVC1", "HEV1", "X265"}
                            if any(h in fourcc_str for h in hevc_fourccs):
                                codec_warning = (
                                    f" [CODEC ALERT] H.265/HEVC stream detected (fourcc={fourcc_str}). "
                                    "MediaMTX WebRTC only supports H.264/VP8/VP9/AV1 — browser preview will be "
                                    "broken or black. Fix: switch the camera to H.264 sub-stream encoding, or add a "
                                    "MediaMTX transcoding rule: paths: ~^.*$: runOnReady: ffmpeg -i {source} -c:v libx264 ..."
                                )
                    except Exception:
                        pass
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None and frame.size > 0:
                        ret_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        if ret_enc:
                            latency = round((time.perf_counter() - t0) * 1000.0, 1)
                            diag_info["stage"] = "SUCCESS"
                            diag_info["error_message"] = ""
                            diag_info["suggested_stream_url"] = url
                            return (buf.tobytes(), desc, latency, diag_info) if return_diag else (buf.tobytes(), desc, latency)
                    else:
                        diag_info["stage"] = "DECODE_FAILED"
                        diag_info["error_message"] = (
                            f"Video Decode Failed: Connection opened on {target_host}:{target_port}, "
                            "but no valid video frames could be decoded. "
                            "Check camera encoding codec (H.264 required for WebRTC)."
                            + codec_warning
                        )
                else:
                    cap.release()
            except Exception as exc:
                logger.debug("OpenCV RTSP pull exception on %s: %s", url, exc)

    # 4. Smart Multi-Port Camera Auto-Negotiation (HTTP/MJPEG/Alternate RTSP)
    discovered_video_urls = []
    if not is_rtsp_reachable and host_responds:
        for p in open_ports:
            if p == 8080:
                discovered_video_urls.extend([
                    (f"http://{target_host}:8080/video", "IP Webcam Stream (Port 8080)"),
                    (f"http://{target_host}:8080/shot.jpg", "IP Webcam Snapshot (Port 8080)"),
                ])
            elif p == 4747:
                discovered_video_urls.extend([
                    (f"http://{target_host}:4747/video", "DroidCam Stream (Port 4747)"),
                    (f"http://{target_host}:4747/mjpegfeed", "DroidCam Feed (Port 4747)"),
                ])
            elif p == 8554:
                discovered_video_urls.append(
                    (f"rtsp://{auth_part}{target_host}:8554{rtsp_path or '/live'}", "Alternate RTSP (Port 8554)")
                )
            elif p == 80:
                discovered_video_urls.extend([
                    (f"http://{target_host}/snapshot", "HTTP Snapshot (Port 80)"),
                    (f"http://{target_host}:80/snapshot", "HTTP Snapshot (Port 80)"),
                    (f"http://{target_host}/video", "HTTP Video (Port 80)"),
                    (f"http://{target_host}/mjpeg", "MJPEG Stream (Port 80)"),
                    (f"http://{target_host}/live.mjpg", "Live MJPG (Port 80)"),
                    (f"http://{target_host}/live", "HTTP Live (Port 80)"),
                    (f"http://{target_host}/ch0", "HTTP Channel 0 (Port 80)"),
                    (f"http://{target_host}/cgi-bin/snapshot.cgi", "CGI Snapshot (Port 80)"),
                ])
            elif p == 8000:
                discovered_video_urls.append(
                    (f"http://{target_host}:8000/video", "DVR/ONVIF Stream (Port 8000)")
                )

    # Add default candidate HTTP snapshot URLs if host is localhost/127.0.0.1
    if target_host in ("localhost", "127.0.0.1"):
        discovered_video_urls.extend([
            (f"http://{target_host}:8000/snapshot", "Local Snapshot (8000)"),
            (f"http://{target_host}:8080/video", "Local Video (8080)"),
        ])

    # Test discovered video endpoints
    for v_url, v_desc in discovered_video_urls:
        if v_url.startswith(("http://", "https://")):
            for auth_item in distinct_auth:
                try:
                    headers = {"Connection": "close", "AppUser as User-Agent": "Mozilla/5.0"}
                    with httpx.Client(timeout=1.0, follow_redirects=True, headers=headers) as client:
                        resp = client.get(v_url, auth=auth_item)
                        if resp.status_code == 200 and len(resp.content) > 500:
                            if (
                                resp.content.startswith(b"\xff\xd8\xff")
                                or "image" in resp.headers.get("content-type", "")
                                or resp.headers.get("content-type") == "application/octet-stream"
                            ):
                                latency = round((time.perf_counter() - t0) * 1000.0, 1)
                                diag_info["stage"] = "SUCCESS"
                                diag_info["is_port_open"] = True
                                diag_info["is_handshake_ok"] = True
                                resolved_url = v_url
                                if auth_item and auth_item != ("__NONE__", ""):
                                    u, p = auth_item
                                    parsed = urllib.parse.urlparse(v_url)
                                    port_str = f":{parsed.port}" if parsed.port and parsed.port != 80 else ""
                                    netloc = f"{u}:{p}@{parsed.hostname}{port_str}"
                                    resolved_url = urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
                                diag_info["suggested_stream_url"] = resolved_url
                                diag_info["error_message"] = ""
                                return (resp.content, f"{v_desc} ({resolved_url})", latency, diag_info) if return_diag else (resp.content, f"{v_desc} ({resolved_url})", latency)
                except Exception:
                    pass

        try:
            cap = cv2.VideoCapture(v_url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1200)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1200)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    ret_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if ret_enc:
                        latency = round((time.perf_counter() - t0) * 1000.0, 1)
                        diag_info["stage"] = "SUCCESS"
                        diag_info["is_port_open"] = True
                        diag_info["is_handshake_ok"] = True
                        diag_info["suggested_stream_url"] = v_url
                        diag_info["error_message"] = ""
                        return (buf.tobytes(), f"{v_desc} ({v_url})", latency, diag_info) if return_diag else (buf.tobytes(), f"{v_desc} ({v_url})", latency)
            else:
                cap.release()
        except Exception:
            pass

    if not is_rtsp_reachable and host_responds:
        if open_ports:
            diag_info["error_message"] = (
                f"RTSP port {target_port} is closed on '{target_host}'. Open TCP port(s) detected: {open_ports}, "
                f"but no video stream could be decoded (web server or authentication required). "
                f"If using a phone camera or IP camera, verify the streaming app is started and specify the stream path."
            )

    latency = round((time.perf_counter() - t0) * 1000.0, 1)
    if is_rtsp_reachable or (open_ports and len(open_ports) > 0):
        return (None, "SOCKET_CONNECTED_DECODE_PENDING", latency, diag_info) if return_diag else (None, "SOCKET_CONNECTED_DECODE_PENDING", latency)
    return (None, "NETWORK_UNREACHABLE", latency, diag_info) if return_diag else (None, "NETWORK_UNREACHABLE", latency)

