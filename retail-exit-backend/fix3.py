with open("src/ml/level1_detection/vision_service.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'os.path.join(os.path.dirname(__file__), "weights", "yolox_x.onnx")',
    'os.path.join(os.path.dirname(__file__), "..", "weights", "yolox_x.onnx")'
)

with open("src/ml/level1_detection/vision_service.py", "w", encoding="utf-8") as f:
    f.write(content)
