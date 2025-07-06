from config import config
import psycopg2

url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
print("Trying:", url)
try:
    conn = psycopg2.connect(url)
    print("✅ Connected!")
    conn.close()
except Exception as e:
    print("❌ Connection failed:", e) 