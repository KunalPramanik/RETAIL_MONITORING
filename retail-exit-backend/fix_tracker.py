with open("src/ml/tracker.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("from src.schemas.cv import DetectedBox", "Any # type placeholder")
content = content.replace("List[DetectedBox]", "List[Any]")

with open("src/ml/tracker.py", "w", encoding="utf-8") as f:
    f.write(content)
