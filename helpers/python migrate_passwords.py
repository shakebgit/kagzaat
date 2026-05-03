import psycopg2
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get all users with plain text passwords
cur.execute("SELECT email, password FROM userdetails")
users = cur.fetchall()

for email, password in users:
    # Hash the password
    hashed = generate_password_hash(password, method='pbkdf2:sha256')
    
    # Update database
    cur.execute("UPDATE userdetails SET password=%s WHERE email=%s", (hashed, email))
    print(f"Updated: {email}")

conn.commit()
cur.close()
conn.close()

print("Migration complete!")