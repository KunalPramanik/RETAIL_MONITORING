import sys

with open("src/ml/vision_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "from typing import" in line:
        new_lines.append("from src.ml.tracker import SimpleByteTrack\n")

with open("src/ml/vision_service.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
