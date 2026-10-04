with open("src/ml/level1_detection/vision_service.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "from src.ml.level5_tracking.tracker_service import SimpleByteTrack",
    "from src.ml.level5_tracking.tracker import SimpleByteTrack"
)

with open("src/ml/level1_detection/vision_service.py", "w", encoding="utf-8") as f:
    f.write(content)
