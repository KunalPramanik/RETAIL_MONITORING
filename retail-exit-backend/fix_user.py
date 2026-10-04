import glob

for filepath in glob.glob("src/**/*.py", recursive=True):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    changed = False
    if "from src.db.models import " in content and "User" in content and "AppUser" not in content:
        content = content.replace("User", "AppUser as User")
        changed = True

    if changed:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
