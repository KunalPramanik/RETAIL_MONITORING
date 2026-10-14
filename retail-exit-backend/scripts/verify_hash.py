import bcrypt

def main():
    pwd = b"Ces@1234"
    salt = bcrypt.gensalt(rounds=12)
    h = bcrypt.hashpw(pwd, salt)
    hash_str = h.decode("utf-8")
    print(f"NEW_HASH={hash_str}")
    check = bcrypt.checkpw(pwd, hash_str.encode("utf-8"))
    print(f"VERIFICATION={check}")
    
    # Save to a file so we can read it directly
    with open("retail-exit-backend/scripts/current_hash.txt", "w") as f:
        f.write(hash_str)

if __name__ == "__main__":
    main()

