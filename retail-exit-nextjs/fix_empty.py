import glob
import os

for filepath in glob.glob("src/app/(dashboard)/**/page.tsx", recursive=True):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    if not content.strip():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("export default function Page() { return <div>Coming Soon</div>; }\n")
