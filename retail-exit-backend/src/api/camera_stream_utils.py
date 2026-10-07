"""Camera Stream Utilities

Provides diagnostic standby cards, frame rendering utilities, and HUD overlay generation
for cameras in standby, error, or unconfigured states.
"""

from datetime import datetime, timezone
from typing import Optional
import cv2
import numpy as np


def generate_diagnostic_preview_frame(
    label: str,
    ip: str,
    rtsp_path: str,
    status: str = "PENDING_SETUP",
    camera_id: Optional[str] = None,
    lane_id: Optional[str] = None,
) -> bytes:
    """Generates an authentic CCTV Technical Standby Card with live UTC timestamp.

    Never uses pre-recorded candidate images. Always renders a proper signal-loss
    standby card so the operator clearly sees the camera is offline/pending.
    """
    w, h = 1280, 720
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = (18, 22, 28)  # Tactical dark background

    # Technical grid
    grid_color = (28, 36, 46)
    for x in range(0, w, 60):
        cv2.line(img, (x, 0), (x, h), grid_color, 1)
    for y in range(0, h, 60):
        cv2.line(img, (0, y), (w, y), grid_color, 1)

    # Corner brackets
    blen = 35
    bcol = (60, 75, 95)
    cv2.line(img, (40, 40), (40 + blen, 40), bcol, 2)
    cv2.line(img, (40, 40), (40, 40 + blen), bcol, 2)
    cv2.line(img, (w - 40, 40), (w - 40 - blen, 40), bcol, 2)
    cv2.line(img, (w - 40, 40), (w - 40, 40 + blen), bcol, 2)
    cv2.line(img, (40, h - 40), (40 + blen, h - 40), bcol, 2)
    cv2.line(img, (40, h - 40), (40, h - 40 - blen), bcol, 2)
    cv2.line(img, (w - 40, h - 40), (w - 40 - blen, h - 40), bcol, 2)
    cv2.line(img, (w - 40, h - 40), (w - 40, h - 40 - blen), bcol, 2)

    # Central standby box
    box_w, box_h = 620, 175
    bx = w // 2 - box_w // 2
    by = h // 2 - box_h // 2
    cv2.rectangle(img, (bx, by), (bx + box_w, by + box_h), (25, 32, 42), -1)
    cv2.rectangle(img, (bx, by), (bx + box_w, by + box_h), (70, 85, 105), 1)

    # Status text — reflect actual status so operator knows the true state
    status_upper = status.upper().replace("_", " ")
    is_offline = status_upper in ("OFFLINE", "CONNECTION_FAILED", "NETWORK_UNREACHABLE", "PENDING SETUP")
    badge_color = (235, 165, 45) if is_offline else (34, 197, 94)

    cv2.putText(img, f"[ NO LIVE SIGNAL // {status_upper} ]", (bx + 30, by + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, badge_color, 2)
    disp_cam = f"{label.upper()} [{camera_id or 'UNREGISTERED'}]"
    cv2.putText(img, f"CAMERA: {disp_cam}", (bx + 30, by + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (190, 205, 220), 1)
    lane_desc = f"LANE: {lane_id}" if lane_id else "LANE: NOT ASSIGNED"
    cv2.putText(img, f"ENDPOINT: {ip}{rtsp_path}  |  {lane_desc}", (bx + 30, by + 110), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (130, 145, 160), 1)
    cv2.putText(img, "AWAITING PHYSICAL STREAM CONNECTION", (bx + 30, by + 148), cv2.FONT_HERSHEY_SIMPLEX, 0.47, (235, 165, 45), 1)

    # Top & bottom HUD overlay
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 85), (12, 15, 20), -1)
    cv2.rectangle(overlay, (0, h - 55), (w, h), (12, 15, 20), -1)
    cv2.addWeighted(overlay, 0.70, img, 0.30, 0, img)

    cv2.putText(img, "SEC-OPS RETAIL MONITORING // LIVE CCTV NODE", (30, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (217, 119, 6), 2)
    cv2.putText(img, f"STREAM: {label.upper()} [{camera_id or 'PENDING'}]", (30, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    cv2.putText(img, f"REC [STANDBY]  {now_str}", (30, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 195, 210), 1)
    cv2.putText(img, "STATUS: STANDBY // AWAITING STREAM FEED", (w - 490, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 165, 45), 2)

    _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return buf.tobytes()

