import os
import re

with open("src/db/models.py", "r", encoding="utf-8") as f:
    content = f.read()

os.makedirs("src/db/models", exist_ok=True)

# We will just write a wrapper script to split by "# 1. Reference", "# 2. Lane & Camera", etc.
groups = re.split(r'# "?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?\n# \d\. (.*?)\n# .*?\n', content)
# Actually the divider has unicode characters that might get messed up. Let's use simple class regexes.

import ast
tree = ast.parse(content)

imports = []
classes = {}
functions = {}

for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        imports.append(ast.get_source_segment(content, node))
    elif isinstance(node, ast.ClassDef):
        classes[node.name] = ast.get_source_segment(content, node)
    elif isinstance(node, ast.FunctionDef):
        functions[node.name] = ast.get_source_segment(content, node)
    elif isinstance(node, ast.Assign):
        if len(node.targets) == 1 and getattr(node.targets[0], 'id', '') == 'Base':
            imports.append(ast.get_source_segment(content, node))

base_code = "\n".join(imports) + "\n\n" + "\n\n".join(functions.values()) + "\n\n"
if "JSONType" in classes:
    base_code += classes["JSONType"] + "\n\n"

with open("src/db/models/base.py", "w", encoding="utf-8") as f:
    f.write(base_code)

def write_group(filename, class_names):
    code = "from .base import *\n"
    code += "from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON\n"
    code += "from sqlalchemy.orm import relationship\n\n"
    for cn in class_names:
        if cn in classes:
            code += classes[cn] + "\n\n"
    with open(f"src/db/models/{filename}", "w", encoding="utf-8") as f:
        f.write(code)

write_group("store.py", ["Store", "ThresholdConfig"])
write_group("product.py", ["Product"])
write_group("employee.py", ["Shift", "Employee"])
write_group("camera.py", ["Lane", "Camera", "CameraPairingToken", "CameraHeartbeat"])
write_group("event.py", ["ExitEvent", "ExitEventLineItem"])
write_group("sensor.py", ["VisionDetection", "RfidRead", "WeightReading", "Invoice", "FaceMatchAttempt"])
write_group("alert.py", ["AppUser", "Alert", "AlarmDispatch"])
write_group("audit.py", ["AuditLog"])
write_group("analytics.py", ["StaticImageDetection", "PersonAppearanceSummary", "MaterialMovementLedger", "MaterialInventoryBalance"])

# Write __init__.py to export everything
with open("src/db/models/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .base import Base, get_utc_now\n")
    for group in ["store", "product", "employee", "camera", "event", "sensor", "alert", "audit", "analytics"]:
        f.write(f"from .{group} import *\n")
