import os
import ast
import subprocess
old_models = subprocess.check_output(["git", "show", "HEAD:retail-exit-backend/src/db/models.py"]).decode("utf-8")

tree = ast.parse(old_models)
classes = {node.name: ast.get_source_segment(old_models, node) for node in tree.body if isinstance(node, ast.ClassDef)}

handled = [
    "JSONType", "Store", "ThresholdConfig", "Product", "Shift", "Employee",
    "Lane", "Camera", "CameraPairingToken", "CameraHeartbeat",
    "ExitEvent", "ExitEventLineItem",
    "VisionDetection", "RfidRead", "WeightReading", "Invoice", "FaceMatchAttempt",
    "AppUser", "Alert", "AlarmDispatch", "AuditLog",
    "StaticImageDetection", "PersonAppearanceSummary", "MaterialMovementLedger", "MaterialInventoryBalance"
]

unhandled = [name for name in classes.keys() if name not in handled]
print("Unhandled:", unhandled)

if unhandled:
    code = "from .base import *\n"
    code += "from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON\n"
    code += "from sqlalchemy.orm import relationship\n\n"
    for cn in unhandled:
        code += classes[cn] + "\n\n"
    # fix foreign keys inside the new code
    import re
    code = re.sub(r'foreign_keys=\[([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\]', r'foreign_keys="[\1.\2]"', code)

    with open("src/db/models/misc.py", "w", encoding="utf-8") as f:
        f.write(code)
    
    with open("src/db/models/__init__.py", "a", encoding="utf-8") as f:
        f.write("from .misc import *\n")
