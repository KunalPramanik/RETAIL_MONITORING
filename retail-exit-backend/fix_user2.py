files = ["src/api/auth.py", "src/api/deps.py", "src/db/init_config.py"]
for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # replace import
    content = content.replace("from src.db.models import User", "from src.db.models import AppUser as User")
    content = content.replace("from src.db.models import ThresholdConfig, User", "from src.db.models import ThresholdConfig, AppUser as User")
    
    # replace User.id with User.user_id if needed
    content = content.replace("User.id", "User.user_id")
    
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
