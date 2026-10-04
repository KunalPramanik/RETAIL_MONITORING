with open("src/ml/model_config.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add get_vision_config if it's missing
if "def get_vision_config" not in content:
    content += """

def get_vision_config():
    return model_config
"""

with open("src/ml/model_config.py", "w", encoding="utf-8") as f:
    f.write(content)
