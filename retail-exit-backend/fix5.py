with open("src/ml/model_config.py", "r", encoding="utf-8") as f:
    content = f.read()

# I will define model_config at the end of the file as an alias for get_vision_config()
if "model_config =" not in content:
    content += "\nmodel_config = get_vision_config()\n"

with open("src/ml/model_config.py", "w", encoding="utf-8") as f:
    f.write(content)
