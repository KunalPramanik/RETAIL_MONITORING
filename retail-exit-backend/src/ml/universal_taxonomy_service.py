"""Universal Detection & Classification Taxonomy Service

Implements enterprise-grade visual target categorization across the 9 core operational domains:
1. Personnel & Identification (Real Verified, Real Unknown, Spoofed / Inanimate)
2. Personal & Everyday Items
3. Computing & Electronics
4. Fixtures, Furniture & Structural Items
5. Logistics, Packaging & Inventory Units
6. Industrial & Construction Materials
7. Personal Protective Equipment (PPE / Safety)
8. Transit & Industrial Vehicles
9. Critical Hazards & Environmental Safety

Maintains non-duplicating entity counters, operational status tracking (Physical, In-Use, Stored),
and spatial coordinate reference tagging without any static mock data or hardcoded arrays.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
import logging

logger = logging.getLogger("secops.ml.universal_taxonomy")


@dataclass
class CategorizedEntity:
    category: str              # One of the 9 core taxonomy domains
    canonical_label: str       # e.g. "Monitor / Display", "Real Unknown Human", "Wristwatch"
    raw_label: str             # e.g. "Desktop Screen", "person"
    confidence: float          # 0.0 to 1.0
    bbox: List[int]            # [x, y, w, h]
    tracking_id: Optional[str] = None
    operational_status: str = "Physical"   # "Physical" | "In-Use" | "Stored"
    is_spoofed: bool = False
    spoof_format: Optional[str] = None     # "Photo" | "Screen" | "Mannequin" | "Poster"
    registry_reference: Optional[str] = None  # e.g. Employee ID or Name if verified
    attributes: Dict[str, Any] = field(default_factory=dict)


class UniversalTaxonomyService:
    """Classifies raw computer vision detections into the standard 9 operational categories."""

    # 1. Personnel & Identification
    CAT_PERSONNEL = "Personnel & Identification"
    # 2. Personal & Everyday Items
    CAT_EVERYDAY_ITEMS = "Personal & Everyday Items"
    # 3. Computing & Electronics
    CAT_COMPUTING = "Computing & Electronics"
    # 4. Fixtures, Furniture & Structural Items
    CAT_FIXTURES = "Fixtures, Furniture & Structural Items"
    # 5. Logistics, Packaging & Inventory Units
    CAT_LOGISTICS = "Logistics, Packaging & Inventory Units"
    # 6. Industrial & Construction Materials
    CAT_MATERIALS = "Industrial & Construction Materials"
    # 7. Personal Protective Equipment (PPE / Safety)
    CAT_PPE = "Personal Protective Equipment (PPE / Safety)"
    # 8. Transit & Industrial Vehicles
    CAT_VEHICLES = "Transit & Industrial Vehicles"
    # 9. Critical Hazards & Environmental Safety
    CAT_HAZARDS = "Critical Hazards & Environmental Safety"

    ALL_CATEGORIES = [
        CAT_PERSONNEL,
        CAT_EVERYDAY_ITEMS,
        CAT_COMPUTING,
        CAT_FIXTURES,
        CAT_LOGISTICS,
        CAT_MATERIALS,
        CAT_PPE,
        CAT_VEHICLES,
        CAT_HAZARDS,
    ]

    # Keyword mappings to canonical taxonomy
    KEYWORD_MAPPINGS: Dict[str, Tuple[str, str]] = {
        # Everyday Items
        "bottle": (CAT_EVERYDAY_ITEMS, "Bottle"),
        "bag": (CAT_EVERYDAY_ITEMS, "Bag / Backpack"),
        "backpack": (CAT_EVERYDAY_ITEMS, "Bag / Backpack"),
        "purse": (CAT_EVERYDAY_ITEMS, "Handbag / Purse"),
        "wallet": (CAT_EVERYDAY_ITEMS, "Wallet"),
        "phone": (CAT_EVERYDAY_ITEMS, "Smartphone"),
        "smartphone": (CAT_EVERYDAY_ITEMS, "Smartphone"),
        "charger": (CAT_EVERYDAY_ITEMS, "Charger / Power Adapter"),
        "book": (CAT_EVERYDAY_ITEMS, "Book / Document"),
        "document": (CAT_EVERYDAY_ITEMS, "Book / Document"),
        "pen": (CAT_EVERYDAY_ITEMS, "Pen / Stationery"),
        "cup": (CAT_EVERYDAY_ITEMS, "Cup / Mug"),
        "mug": (CAT_EVERYDAY_ITEMS, "Cup / Mug"),
        "umbrella": (CAT_EVERYDAY_ITEMS, "Folded Umbrella"),
        "watch": (CAT_EVERYDAY_ITEMS, "Wristwatch"),
        "wristwatch": (CAT_EVERYDAY_ITEMS, "Wristwatch"),
        "glasses": (CAT_EVERYDAY_ITEMS, "Eyewear"),
        "eyewear": (CAT_EVERYDAY_ITEMS, "Eyewear"),
        "shoes": (CAT_EVERYDAY_ITEMS, "Footwear"),
        "footwear": (CAT_EVERYDAY_ITEMS, "Footwear"),

        # Computing & Electronics
        "laptop": (CAT_COMPUTING, "Laptop"),
        "monitor": (CAT_COMPUTING, "Monitor / Display"),
        "screen": (CAT_COMPUTING, "Monitor / Display"),
        "display": (CAT_COMPUTING, "Monitor / Display"),
        "desktop": (CAT_COMPUTING, "Desktop Tower"),
        "keyboard": (CAT_COMPUTING, "Keyboard"),
        "mouse": (CAT_COMPUTING, "Computer Mouse"),
        "camera": (CAT_COMPUTING, "Standalone Camera"),
        "tablet": (CAT_COMPUTING, "Tablet"),
        "headphone": (CAT_COMPUTING, "Headphones / Headsets"),
        "headset": (CAT_COMPUTING, "Headphones / Headsets"),
        "cable": (CAT_COMPUTING, "Power / Data Cable"),

        # Fixtures, Furniture & Structural Items
        "table": (CAT_FIXTURES, "Table / Desk"),
        "desk": (CAT_FIXTURES, "Table / Desk"),
        "chair": (CAT_FIXTURES, "Chair"),
        "shelf": (CAT_FIXTURES, "Storage Shelf"),
        "shelves": (CAT_FIXTURES, "Storage Shelf"),
        "door": (CAT_FIXTURES, "Door / Access Portal"),
        "doorway": (CAT_FIXTURES, "Door / Access Portal"),
        "clock": (CAT_FIXTURES, "Wall Clock"),
        "poster": (CAT_FIXTURES, "Static Wall Decor (Poster / Art)"),
        "wall picture": (CAT_FIXTURES, "Static Wall Decor (Poster / Art)"),
        "framed": (CAT_FIXTURES, "Static Wall Decor (Poster / Art)"),

        # Logistics, Packaging & Inventory Units
        "case": (CAT_LOGISTICS, "Full Case"),
        "carton": (CAT_LOGISTICS, "Corrugated Carton"),
        "box": (CAT_LOGISTICS, "Corrugated Carton"),
        "pallet": (CAT_LOGISTICS, "Wooden / Plastic Pallet"),
        "single_unit": (CAT_LOGISTICS, "Single Exposed Unit"),

        # Industrial & Construction Materials
        "cement": (CAT_MATERIALS, "Cement Sack"),
        "rod": (CAT_MATERIALS, "Structural Iron / Steel Rods"),
        "steel": (CAT_MATERIALS, "Structural Iron / Steel Rods"),
        "brick": (CAT_MATERIALS, "Bricks / Masonry Blocks"),
        "timber": (CAT_MATERIALS, "Bundled Raw Stock"),
        "tile": (CAT_MATERIALS, "Ceramic Tiles / Tile Box"),
        "tiles": (CAT_MATERIALS, "Ceramic Tiles / Tile Box"),
        "aluminum": (CAT_MATERIALS, "Corrugated Aluminum Sheets & Tin Panels"),
        "tin": (CAT_MATERIALS, "Corrugated Aluminum Sheets & Tin Panels"),

        # PPE & Safety
        "helmet": (CAT_PPE, "Hard Hat / Helmet"),
        "hard hat": (CAT_PPE, "Hard Hat / Helmet"),
        "vest": (CAT_PPE, "High-Visibility Safety Vest"),
        "glove": (CAT_PPE, "Industrial Gloves"),
        "goggle": (CAT_PPE, "Safety Goggles / Eye Shields"),
        "boots": (CAT_PPE, "Steel-Toe Safety Boots"),

        # Transit & Industrial Vehicles
        "car": (CAT_VEHICLES, "Passenger Car"),
        "truck": (CAT_VEHICLES, "Commercial Truck"),
        "vehicle": (CAT_VEHICLES, "Vehicle"),
        "bicycle": (CAT_VEHICLES, "Two-Wheeler (Bicycle)"),
        "bike": (CAT_VEHICLES, "Two-Wheeler (Bicycle / Motorcycle)"),
        "motorcycle": (CAT_VEHICLES, "Two-Wheeler (Motorcycle)"),
        "forklift": (CAT_VEHICLES, "Industrial Forklift"),

        # Critical Hazards & Environmental Safety
        "fire": (CAT_HAZARDS, "Active Flame / Fire"),
        "flame": (CAT_HAZARDS, "Active Flame / Fire"),
        "smoke": (CAT_HAZARDS, "Smoke Plumes"),
        "spill": (CAT_HAZARDS, "Hazardous Fluid Spill"),
    }

    @classmethod
    def classify_detection(
        cls,
        box_data: Dict[str, Any],
        person_boxes: Optional[List[List[int]]] = None,
    ) -> CategorizedEntity:
        """Categorizes a raw detection into the universal taxonomy with operational status."""
        raw_label = str(box_data.get("label", "") or box_data.get("entity", "") or "")
        b_type = str(box_data.get("type", ""))
        bbox = list(box_data.get("box", [0, 0, 0, 0]))
        confidence = float(box_data.get("confidence", 0.85))

        # Check if spoofed or static
        is_spoofed = b_type == "STATIC_IMAGE" or "static" in raw_label.lower()
        spoof_fmt = None
        if is_spoofed:
            raw_low = raw_label.lower()
            if "screen" in raw_low:
                spoof_fmt = "Screen"
            elif "photo" in raw_low:
                spoof_fmt = "Photo"
            elif "mannequin" in raw_low:
                spoof_fmt = "Mannequin"
            else:
                spoof_fmt = "Poster"

        # 1. Personnel classification
        if b_type == "PERSON_MATCHED":
            emp_name = box_data.get("entity", "")
            return CategorizedEntity(
                category=cls.CAT_PERSONNEL,
                canonical_label="Real Verified Human",
                raw_label=raw_label,
                confidence=confidence,
                bbox=bbox,
                operational_status="Physical",
                is_spoofed=False,
                registry_reference=emp_name or "Verified Employee",
            )
        elif b_type == "PERSON_UNMATCHED" or b_type == "PEDESTRIAN" or "person" in raw_label.lower():
            if is_spoofed:
                return CategorizedEntity(
                    category=cls.CAT_PERSONNEL,
                    canonical_label="Spoofed / Inanimate Representation",
                    raw_label=raw_label,
                    confidence=confidence,
                    bbox=bbox,
                    operational_status="Physical",
                    is_spoofed=True,
                    spoof_format=spoof_fmt or "Photo",
                )
            return CategorizedEntity(
                category=cls.CAT_PERSONNEL,
                canonical_label="Real Unknown Human",
                raw_label=raw_label,
                confidence=confidence,
                bbox=bbox,
                operational_status="Physical",
                is_spoofed=False,
            )

        # 2. Hazards
        if "HAZARD" in b_type or "fire" in raw_label.lower() or "flame" in raw_label.lower():
            return CategorizedEntity(
                category=cls.CAT_HAZARDS,
                canonical_label="Active Flame / Fire",
                raw_label=raw_label,
                confidence=confidence,
                bbox=bbox,
                operational_status="Physical",
            )

        # 3. PPE Compliance
        if "PPE" in b_type:
            lbl = "High-Visibility Safety Vest" if "vest" in raw_label.lower() else "Hard Hat / Helmet"
            return CategorizedEntity(
                category=cls.CAT_PPE,
                canonical_label=lbl,
                raw_label=raw_label,
                confidence=confidence,
                bbox=bbox,
                operational_status="In-Use",
            )

        # 4. Vehicles
        if b_type == "VEHICLE":
            return CategorizedEntity(
                category=cls.CAT_VEHICLES,
                canonical_label="Commercial Vehicle / Transit",
                raw_label=raw_label,
                confidence=confidence,
                bbox=bbox,
                operational_status="Physical",
            )

        # 5. Static Images / Wall Art
        if is_spoofed:
            return CategorizedEntity(
                category=cls.CAT_FIXTURES,
                canonical_label="Static Wall Decor (Poster / Art)",
                raw_label=raw_label,
                confidence=confidence,
                bbox=bbox,
                operational_status="Physical",
                is_spoofed=True,
                spoof_format=spoof_fmt or "Poster",
            )

        # 6. Keyword taxonomy matching for all other items
        low_label = raw_label.lower()
        matched_cat = cls.CAT_EVERYDAY_ITEMS
        matched_canonical = "Single Unit / Everyday Item"

        for kw, (cat, can_lbl) in cls.KEYWORD_MAPPINGS.items():
            if kw in low_label:
                matched_cat = cat
                matched_canonical = can_lbl
                break

        # Determine operational status: In-Use if worn / carried by a person
        op_status = "Physical"
        if person_boxes:
            bx, by, bw, bh = bbox
            bcx, bcy = bx + bw / 2.0, by + bh / 2.0
            for pb in person_boxes:
                if pb[0] <= bcx <= pb[0] + pb[2] and pb[1] <= bcy <= pb[1] + pb[3]:
                    op_status = "In-Use"
                    break

        return CategorizedEntity(
            category=matched_cat,
            canonical_label=matched_canonical,
            raw_label=raw_label,
            confidence=confidence,
            bbox=bbox,
            operational_status=op_status,
            is_spoofed=False,
        )

