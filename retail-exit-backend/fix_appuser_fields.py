files = ["src/api/auth.py", "src/api/deps.py", "src/db/init_config.py", "tests/api/test_auth.py"]
for fpath in files:
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # We need to map OAuth2 username field to AppUser email field
        # In test_auth.py, we might need to send "admin@secops.local" instead of "fake"
        
        content = content.replace("User.username", "User.email")
        content = content.replace("user.hashed_password", "user.password_hash")
        content = content.replace("User.hashed_password", "User.password_hash")
        
        if fpath == "src/db/init_config.py":
            content = content.replace('"admin"', '"admin@secops.local"')
            content = content.replace('username="admin"', 'email="admin@secops.local"')
            content = content.replace('hashed_password=', 'password_hash=')
        
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
    except FileNotFoundError:
        pass
