with open("src/api/cameras.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip() == "cap = cv2.VideoCapture(dev_idx, cv2.CAP_MSMF)":
        # It's currently indented 8 spaces. Let's make it 12 spaces.
        lines[i] = "            cap = cv2.VideoCapture(dev_idx, cv2.CAP_MSMF)\n"

with open("src/api/cameras.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
