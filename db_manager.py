import psycopg2
from config import config
from datetime import datetime
import json

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# === יצירת טבלאות (אם לא קיימות) ===
def create_tables():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        chat_id TEXT,
        user_msg TEXT,
        bot_msg TEXT,
        timestamp TIMESTAMP
    );
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_profiles (
        id SERIAL PRIMARY KEY,
        chat_id TEXT UNIQUE,
        profile_json JSONB,
        updated_at TIMESTAMP
    );
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS gpt_calls_log (
        id SERIAL PRIMARY KEY,
        chat_id TEXT,
        call_type TEXT,
        request_data JSONB,
        response_data JSONB,
        tokens_input INTEGER,
        tokens_output INTEGER,
        cost_usd DECIMAL(10,6),
        processing_time_seconds DECIMAL(8,3),
        timestamp TIMESTAMP
    );
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS gpt_usage_log (
        id SERIAL PRIMARY KEY,
        chat_id TEXT,
        model TEXT,
        usage JSONB,
        cost_agorot INTEGER,
        timestamp TIMESTAMP
    );
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS system_logs (
        id SERIAL PRIMARY KEY,
        log_level TEXT,
        module TEXT,
        message TEXT,
        extra_data JSONB,
        timestamp TIMESTAMP
    );
    ''')
    conn.commit()
    cur.close()
    conn.close()

# === שמירת הודעת צ'אט ===
def save_chat_message(chat_id, user_msg, bot_msg, timestamp=None):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_messages (chat_id, user_msg, bot_msg, timestamp) VALUES (%s, %s, %s, %s)",
        (chat_id, user_msg, bot_msg, timestamp or datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()

# === שליפת היסטוריית צ'אט ===
def get_chat_history(chat_id, limit=100):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(
        "SELECT user_msg, bot_msg, timestamp FROM chat_messages WHERE chat_id=%s ORDER BY timestamp DESC LIMIT %s",
        (chat_id, limit)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows[::-1]  # מהישן לחדש

# === שמירת פרופיל משתמש ===
def save_user_profile(chat_id, profile_json):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_profiles (chat_id, profile_json, updated_at) VALUES (%s, %s, %s) ON CONFLICT (chat_id) DO UPDATE SET profile_json=EXCLUDED.profile_json, updated_at=EXCLUDED.updated_at",
        (chat_id, profile_json, datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()

# === שליפת פרופיל משתמש ===
def get_user_profile(chat_id):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT profile_json FROM user_profiles WHERE chat_id=%s", (chat_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

# === שמירת לוג GPT ===
def save_gpt_call_log(chat_id, call_type, request_data, response_data, tokens_input, tokens_output, cost_usd, processing_time_seconds, timestamp=None):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # המרת dict ל-JSON string
    request_json = json.dumps(request_data) if isinstance(request_data, dict) else str(request_data)
    response_json = json.dumps(response_data) if isinstance(response_data, dict) else str(response_data)
    
    cur.execute(
        "INSERT INTO gpt_calls_log (chat_id, call_type, request_data, response_data, tokens_input, tokens_output, cost_usd, processing_time_seconds, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (chat_id, call_type, request_json, response_json, tokens_input, tokens_output, cost_usd, processing_time_seconds, timestamp or datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()

# === שמירת לוג שימוש ===
def save_gpt_usage_log(chat_id, model, usage, cost_agorot, timestamp=None):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # המרת dict ל-JSON string
    usage_json = json.dumps(usage) if isinstance(usage, dict) else str(usage)
    
    cur.execute(
        "INSERT INTO gpt_usage_log (chat_id, model, usage, cost_agorot, timestamp) VALUES (%s, %s, %s, %s, %s)",
        (chat_id, model, usage_json, cost_agorot, timestamp or datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()

# === שמירת לוג מערכת ===
def save_system_log(log_level, module, message, extra_data, timestamp=None):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # המרת dict ל-JSON string
    extra_json = json.dumps(extra_data) if isinstance(extra_data, dict) else str(extra_data)
    
    cur.execute(
        "INSERT INTO system_logs (log_level, module, message, extra_data, timestamp) VALUES (%s, %s, %s, %s, %s)",
        (log_level, module, message, extra_json, timestamp or datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close() 