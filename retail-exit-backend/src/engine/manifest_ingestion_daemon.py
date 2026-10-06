"""Physical Paper Manifest & Barcode Edge Ingestion Daemon

Provides automated edge capture for warehouse dispatch docks:
1. BarcodeScannerListener: Asynchronous serial/USB HID event listener for Code-128,
   GS1-128, and DataMatrix barcode scanners with 750ms deduplication debouncing.
2. DeskManifestScanner: Overhead/Desk camera capture loop with real-time document
   quadrilateral contour detection, perspective deskew rectification, and OCR parsing.
3. Automated dispatch session binding for instant baseline manifest registration.
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
import asyncio
import time
import re
import logging
import cv2
import numpy as np

logger = logging.getLogger("secops.engine.manifest_ingestion")


@dataclass
class ScannedBarcodeRecord:
    raw_code: str
    symbology: str                       # "CODE128", "GS1_128", "DATAMATRIX", "QR"
    timestamp: float
    parsed_sku: Optional[str] = None
    serial_number: Optional[str] = None
    lot_number: Optional[str] = None


@dataclass
class ExtractedManifestDocument:
    bol_number: str
    carrier_name: Optional[str]
    line_items: Dict[str, int]           # {"cement_50kg": 40, "tin_sheet_8ft": 25}
    raw_text: str
    confidence: float
    is_deskewed: bool
    rectified_image: Optional[np.ndarray] = None


class BarcodeScannerListener:
    """Asynchronous serial/USB HID barcode scanner event listener with deduplication."""

    def __init__(self, debounce_window_ms: float = 750.0):
        self.debounce_window_s = debounce_window_ms / 1000.0
        self._last_seen: Dict[str, float] = {}
        self._queue: asyncio.Queue[ScannedBarcodeRecord] = asyncio.Queue()
        self._subscribers: List[Callable[[ScannedBarcodeRecord], None]] = []
        self._running: bool = False

    def subscribe(self, callback: Callable[[ScannedBarcodeRecord], None]) -> None:
        self._subscribers.append(callback)

    def process_raw_scan(self, raw_input: str) -> Optional[ScannedBarcodeRecord]:
        """Ingests a raw barcode string, debounces, parses symbology, and queues."""
        cleaned = raw_input.strip()
        if not cleaned:
            return None

        now = time.time()
        last_t = self._last_seen.get(cleaned, 0.0)
        if (now - last_t) < self.debounce_window_s:
            logger.debug("Debounced duplicate barcode scan: %s", cleaned)
            return None

        self._last_seen[cleaned] = now

        # Parse symbology and identifiers
        symbology = "CODE128"
        sku = None
        serial = None
        lot = None

        if cleaned.startswith("]C1") or cleaned.startswith("(01)"):
            symbology = "GS1_128"
            # Extract GS1 Application Identifiers e.g. (01)GTIN(21)SERIAL
            gtin_match = re.search(r"\(01\)(\d{14})", cleaned)
            ser_match = re.search(r"\(21\)([A-Za-z0-9_-]+)", cleaned)
            if gtin_match:
                sku = gtin_match.group(1)
            if ser_match:
                serial = ser_match.group(1)
        elif cleaned.startswith("]d") or " " in cleaned:
            symbology = "DATAMATRIX"
            parts = cleaned.split()
            if len(parts) >= 2:
                sku = parts[0]
                serial = parts[1]
        else:
            sku = cleaned
            serial = f"SER-{cleaned[-6:]}" if len(cleaned) >= 6 else cleaned

        record = ScannedBarcodeRecord(
            raw_code=cleaned,
            symbology=symbology,
            timestamp=now,
            parsed_sku=sku,
            serial_number=serial,
            lot_number=lot,
        )

        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            pass

        for cb in self._subscribers:
            try:
                cb(record)
            except Exception as e:
                logger.error("Error in barcode scanner callback: %s", e)

        return record

    async def get_next_scan(self, timeout: Optional[float] = None) -> Optional[ScannedBarcodeRecord]:
        """Awaits the next scanned barcode record."""
        try:
            if timeout:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None


class DeskManifestScanner:
    """Desk camera OCR pipeline with document boundary detection and perspective rectification."""

    @classmethod
    def detect_document_quad(cls, frame_bgr: np.ndarray) -> Optional[np.ndarray]:
        """Detects a 4-point quadrilateral paper document boundary in the camera view.

        Requires: Contour Area >= 0.20 * Frame Area and Vertices == 4.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        h, w = frame_bgr.shape[:2]
        frame_area = h * w
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Morphological gradient + Canny edge detection
        edges = cv2.Canny(blurred, 40, 140)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for cnt in contours[:5]:
            area = cv2.contourArea(cnt)
            if area < (0.20 * frame_area):
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            if len(approx) == 4 and cv2.isContourConvex(approx):
                # Order corner points: top-left, top-right, bottom-right, bottom-left
                pts = approx.reshape(4, 2)
                ordered = cls._order_points(pts)
                return ordered

        return None

    @classmethod
    def _order_points(cls, pts: np.ndarray) -> np.ndarray:
        """Orders coordinates: [top-left, top-right, bottom-right, bottom-left]."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    @classmethod
    def warp_perspective_deskew(
        cls,
        frame_bgr: np.ndarray,
        corners: np.ndarray,
        target_width: int = 1200,
        target_height: int = 1600,
    ) -> np.ndarray:
        """Applies 4-point perspective warp transformation to produce an upright deskewed document."""
        dst = np.array(
            [
                [0, 0],
                [target_width - 1, 0],
                [target_width - 1, target_height - 1],
                [0, target_height - 1],
            ],
            dtype=np.float32,
        )

        matrix = cv2.getPerspectiveTransform(corners, dst)
        warped = cv2.warpPerspective(frame_bgr, matrix, (target_width, target_height))
        return warped

    @classmethod
    def parse_manifest_text(cls, raw_text: str) -> ExtractedManifestDocument:
        """Parses Bill of Lading / Invoice text into structured line items and quantities."""
        # Clean text
        text = raw_text.replace("\r", " ")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1. Extract BOL / Invoice number
        bol_match = re.search(r"(?:BOL|INVOICE|MANIFEST|BILL\s*OF\s*LADING)[\s:#*-]*([A-Z0-9_-]{5,20})", text, re.IGNORECASE)
        bol_num = bol_match.group(1).upper() if bol_match else f"BOL-{int(time.time())}"

        # 2. Extract Carrier (match within single line only)
        carrier_match = re.search(r"(?:CARRIER|DRIVER|TRANSPORT)[\s:#*-]*([A-Za-z0-9_ -]{3,35})", text, re.IGNORECASE)
        carrier = carrier_match.group(1).strip() if carrier_match else None

        # 3. Extract Material Line Items
        # Target classes: cement, rebar, tin sheet, carton box, bricks
        line_items: Dict[str, int] = {}

        sku_patterns = [
            (r"(?:CEMENT|PORTLAND)[^\d\n]*?(\d+)\s*(?:BAG|BAGS|PCS|UNITS)?", "cement_bag"),
            (r"(?:REBAR|IRON\s*ROD|STEEL\s*ROD)[^\d\n]*?(\d+)\s*(?:PCS|BUNDLES|UNITS)?", "iron_rod_bundle"),
            (r"(?:TIN\s*SHEET|CGI\s*SHEET|CORRUGATED)[^\d\n]*?(\d+)\s*(?:SHEETS|PCS|UNITS)?", "corrugated_tin_sheet"),
            (r"(?:CARTON|BOX|CASE)[^\d\n]*?(\d+)\s*(?:BOXES|CASES|UNITS)?", "carton_box"),
        ]

        for pat, mat_id in sku_patterns:
            matches = re.finditer(pat, text, re.IGNORECASE)
            for m in matches:
                try:
                    qty = int(m.group(1))
                    if 0 < qty < 10000:
                        line_items[mat_id] = line_items.get(mat_id, 0) + qty
                except ValueError:
                    pass

        # If no specific materials found, search generic line item patterns: "SKU-XXX : 40"
        if not line_items:
            generic_matches = re.finditer(r"([A-Z0-9_-]{3,15})[\s:,-]+(\d{1,5})\s*(?:UNITS|PCS)?", text)
            for m in generic_matches:
                k = m.group(1).lower()
                v = int(m.group(2))
                if v > 0:
                    line_items[k] = v

        conf = 0.92 if line_items and bol_match else (0.75 if line_items else 0.0)

        return ExtractedManifestDocument(
            bol_number=bol_num if bol_match else "UNKNOWN",
            carrier_name=carrier,
            line_items=line_items,
            raw_text=raw_text,
            confidence=conf,
            is_deskewed=True,
        )

    @classmethod
    def process_desk_frame(cls, frame_bgr: np.ndarray, ocr_text_override: Optional[str] = None) -> ExtractedManifestDocument:
        """Processes raw camera frame: detects boundary, deskews, and extracts manifest."""
        corners = cls.detect_document_quad(frame_bgr)
        if corners is not None:
            warped = cls.warp_perspective_deskew(frame_bgr, corners)
        else:
            warped = frame_bgr

        # Use OCR text override if testing or external OCR engine output provided
        if ocr_text_override:
            manifest = cls.parse_manifest_text(ocr_text_override)
            manifest.rectified_image = warped
            manifest.is_deskewed = (corners is not None)
            return manifest

        # Execute real OCR extraction on the deskewed/warped document frame
        extracted_text = ""
        try:
            from src.ml.ocr.invoice_ocr_service import OcrService
            success, enc_bytes = cv2.imencode(".jpg", warped)
            if success:
                ocr_result = OcrService.extract_from_image(enc_bytes.tobytes())
                if ocr_result.line_items and len(ocr_result.raw_ocr_text) > 0:
                    extracted_text = ocr_result.raw_ocr_text
        except Exception as ocr_err:
            logger.debug("Live manifest OCR extraction unavailable or failed: %s", ocr_err)
            extracted_text = ""

        if extracted_text.strip():
            manifest = cls.parse_manifest_text(extracted_text)
        else:
            manifest = ExtractedManifestDocument(
                bol_number="UNKNOWN",
                carrier_name=None,
                line_items={},
                raw_text="",
                confidence=0.0,
                is_deskewed=(corners is not None),
                rectified_image=warped,
            )

        manifest.rectified_image = warped
        manifest.is_deskewed = (corners is not None)
        return manifest
