import sys

with open("src/ml/vision_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add Tracker import
if "from src.ml.tracker import SimpleByteTrack" not in content:
    content = content.replace("from typing import List, Dict, Any, Tuple, Optional", "from typing import List, Dict, Any, Tuple, Optional\nfrom src.ml.tracker import SimpleByteTrack")

# Add trackers dict to class
if "_trackers: Dict[str, SimpleByteTrack]" not in content:
    content = content.replace("_loaded_version: Optional[str] = None", "_loaded_version: Optional[str] = None\n    _trackers: Dict[str, SimpleByteTrack] = {}")

# Update signature
if "camera_id: Optional[str] = None" not in content:
    content = content.replace("ignored_classes: Optional[list] = None,", "ignored_classes: Optional[list] = None,\n        camera_id: Optional[str] = None,")

# Replace Tracker logic
content = content.replace("track_id_seq += 1", "# track_id_seq increment removed in favor of ByteTrack")

# After detections are built, apply tracker
tracker_logic = """
        if camera_id:
            if camera_id not in cls._trackers:
                cls._trackers[camera_id] = SimpleByteTrack(track_buffer=30)
            detections = cls._trackers[camera_id].update(detections)
        else:
            # Fallback sequential IDs
            tid = 1
            for d in detections:
                d.track_id = tid
                tid += 1
"""

if "cls._trackers[camera_id]" not in content:
    content = content.replace("latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)", tracker_logic + "\n        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)")

with open("src/ml/vision_service.py", "w", encoding="utf-8") as f:
    f.write(content)
