import psycopg2
import json
from datetime import datetime

# Load DB config
with open('etc/secrets/config.json', encoding='utf-8') as f:
    config = json.load(f)
DB_URL = config.get('DATABASE_EXTERNAL_URL') or config.get('DATABASE_URL')

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute('SELECT user_msg, bot_msg, timestamp FROM chat_messages WHERE chat_id=%s ORDER BY timestamp', ('5676571979',))
rows = cur.fetchall()

with open('chat_history_5676571979.txt', 'w', encoding='utf-8') as f:
    for row in rows:
        ts = row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else ''
        f.write(f'[{ts}]\nUSER: {row[0]}\nBOT: {row[1]}\n\n')

cur.close()
conn.close()

print('✅ chat_history_5676571979.txt נוצר בהצלחה!') 