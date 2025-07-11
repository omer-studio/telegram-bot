#!/usr/bin/env python3
import psycopg2
from config import config

conn = psycopg2.connect(config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL"))
cur = conn.cursor()

print("=== סטטוס נוכחי ===")
cur.execute("SELECT COUNT(*) FROM chat_messages")
count = cur.fetchone()[0]
print(f"הודעות במסד: {count:,}")

cur.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_messages")
users = cur.fetchone()[0]
print(f"משתמשים: {users:,}")

print(f"נוספו מההתחלה: {count - 625:,}")

cur.execute("SELECT chat_id, COUNT(*) FROM chat_messages GROUP BY chat_id ORDER BY COUNT(*) DESC LIMIT 3")
top_users = cur.fetchall()
print("\nמשתמשים מובילים:")
for chat_id, msg_count in top_users:
    print(f"  {chat_id}: {msg_count:,} הודעות")

conn.close() 