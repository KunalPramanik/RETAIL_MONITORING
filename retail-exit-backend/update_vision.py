with open("src/ml/level1_detection/vision_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Update import and model version
content = content.replace("MODEL_VERSION = \"yolox-tiny-coco-v0.1.0\"", "MODEL_VERSION = \"yolox-x-v1\"")
content = content.replace("yolox_tiny.onnx", "yolox_x.onnx")
content = content.replace("INPUT_SIZE = (416, 416)", "INPUT_SIZE = (640, 640)")

# Add model_config import if not exists
if "from src.ml.model_config import model_config" not in content:
    content = content.replace("from dataclasses", "from src.ml.model_config import model_config\nfrom dataclasses")

# Replace hardcoded confidences
content = content.replace("if conf < 0.50:", "if conf < model_config.confidence_floor:")
content = content.replace("if bh < 0.20 * orig_h and conf < 0.50:", "if bh < 0.20 * orig_h and conf < model_config.confidence_floor:")

with open("src/ml/level1_detection/vision_service.py", "w", encoding="utf-8") as f:
    f.write(content)
