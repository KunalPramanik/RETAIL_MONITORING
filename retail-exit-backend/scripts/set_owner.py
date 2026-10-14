import sqlite3
import uuid

def set_owner():
    con = sqlite3.connect('retail-exit-backend/retail_secops.db')
    cur = con.cursor()
    
    # Deactivate all users
    cur.execute('UPDATE app_user SET is_active = 0')
    
    # Bcrypt hash for Ces@1234
    hash_val = '$2b$12$wkMTMLZQnzyPZMKTKl6EYe4fLo6mNMj6U38CVFcM3TP58KodO2FzC'
    
    cur.execute('SELECT user_id FROM app_user WHERE email = ?', ('ces@gmail.com',))
    row = cur.fetchone()
    if row:
        cur.execute(
            'UPDATE app_user SET password_hash = ?, is_active = 1, role = ?, username = ? WHERE email = ?',
            (hash_val, 'ADMIN', 'ces', 'ces@gmail.com')
        )
    else:
        # Check if admin user exists to update in-place, preserving foreign key relationships
        cur.execute('SELECT user_id FROM app_user WHERE email = "admin@secops.local"')
        admin_row = cur.fetchone()
        if admin_row:
            cur.execute(
                'UPDATE app_user SET email = ?, username = ?, password_hash = ?, role = "ADMIN", is_active = 1 WHERE user_id = ?',
                ('ces@gmail.com', 'ces', hash_val, admin_row[0])
            )
        else:
            new_id = str(uuid.uuid4())
            cur.execute(
                '''INSERT INTO app_user (user_id, email, username, password_hash, role, store_id, mfa_enabled, is_active, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                (new_id, 'ces@gmail.com', 'ces', hash_val, 'ADMIN', '0f8248a3-2947-4f6b-871d-5b6cb219e2c1', 0, 1)
            )
    
    con.commit()
    print("==================================================================")
    print(" Active users in retail_secops.db (ONLY ONE ID ACTIVATED):")
    print("==================================================================")
    for r in cur.execute("SELECT user_id, email, username, role, is_active FROM app_user WHERE is_active = 1").fetchall():
        print(f"  User ID: {r[0]} | Email: {r[1]} | Username: {r[2]} | Role: {r[3]} | Active: {r[4]}")
    con.close()

if __name__ == "__main__":
    set_owner()
