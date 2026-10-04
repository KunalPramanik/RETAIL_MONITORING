with open('src/api/cameras.py', 'r', encoding='utf-8') as f:
    c = f.read()

idx1 = c.find('def capture_camera_frame_sync(')
idx2 = c.find('cap = cv2.VideoCapture(dev_idx, cv2.CAP_MSMF)', idx1)

replacement = """def capture_camera_frame_sync(
    ip: str,
    rtsp_path: str,
    credentials: Optional[str] = None,
    sub_stream_path: Optional[str] = None,
    timeout_sec: float = 2.5,
    stream_url: Optional[str] = None,
    return_diag: bool = False,
) -> tuple:
    '''Attempts to capture a real frame from RTSP stream (main/sub), HTTP endpoints, or local devices.'''
    from src.core.config import settings
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
        
        """

new_content = c[:idx1] + replacement + c[idx2:]

with open('src/api/cameras.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
