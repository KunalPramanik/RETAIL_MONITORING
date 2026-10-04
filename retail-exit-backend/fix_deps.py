with open("src/api/deps.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("from src.db.models import User", "from src.db.models import AppUser as User")
content = content.replace("User.id", "User.user_id")

with open("src/api/deps.py", "w", encoding="utf-8") as f:
    f.write(content)
