with open("src/engine/camera_worker.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("ignored_classes=cam.ignored_classes", "ignored_classes=cam.ignored_classes,\n                camera_id=cam.camera_id")

with open("src/engine/camera_worker.py", "w", encoding="utf-8") as f:
    f.write(content)
