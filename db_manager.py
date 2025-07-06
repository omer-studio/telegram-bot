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

def save_critical_user_data(chat_id, user_info):
    """שומר נתוני משתמש קריטי ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS critical_users (
                id SERIAL PRIMARY KEY,
                chat_id VARCHAR(50) NOT NULL,
                error_context TEXT,
                original_message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recovered BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO critical_users (chat_id, error_context, original_message, recovered)
            VALUES (%s, %s, %s, %s)
        """, (
            str(chat_id),
            user_info.get('error_context', ''),
            user_info.get('original_message', ''),
            user_info.get('recovered', False)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת משתמש קריטי {chat_id}: {e}")
        raise

def save_reminder_state(chat_id, reminder_info):
    """שומר מצב תזכורת ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reminder_states (
                id SERIAL PRIMARY KEY,
                chat_id VARCHAR(50) NOT NULL,
                last_activity TIMESTAMP,
                reminder_sent BOOLEAN DEFAULT FALSE,
                reminder_count INTEGER DEFAULT 0,
                state_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO reminder_states (chat_id, last_activity, reminder_sent, reminder_count, state_data)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            str(chat_id),
            reminder_info.get('last_activity'),
            reminder_info.get('reminder_sent', False),
            reminder_info.get('reminder_count', 0),
            json.dumps(reminder_info)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת תזכורת {chat_id}: {e}")
        raise

def save_billing_usage_data(billing_data):
    """שומר נתוני חיוב ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS billing_usage (
                id SERIAL PRIMARY KEY,
                daily_data JSONB,
                monthly_data JSONB,
                alerts_sent JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO billing_usage (daily_data, monthly_data, alerts_sent)
            VALUES (%s, %s, %s)
        """, (
            json.dumps(billing_data.get('daily', {})),
            json.dumps(billing_data.get('monthly', {})),
            json.dumps(billing_data.get('alerts_sent', {}))
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת נתוני חיוב: {e}")
        raise

def save_errors_stats_data(errors_data):
    """שומר סטטיסטיקות שגיאות ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS errors_stats (
                id SERIAL PRIMARY KEY,
                error_type VARCHAR(100),
                count INTEGER DEFAULT 0,
                last_occurrence TIMESTAMP,
                stats_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        for error_type, count in errors_data.items():
            cur.execute("""
                INSERT INTO errors_stats (error_type, count, stats_data)
                VALUES (%s, %s, %s)
            """, (
                str(error_type),
                int(count) if isinstance(count, (int, float)) else 0,
                json.dumps({error_type: count})
            ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת סטטיסטיקות שגיאות: {e}")
        raise

def save_bot_error_log(entry):
    """שומר לוג שגיאות בוט ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_error_logs (
                id SERIAL PRIMARY KEY,
                error_type VARCHAR(100),
                error_message TEXT,
                chat_id VARCHAR(50),
                user_message TEXT,
                timestamp TIMESTAMP,
                error_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO bot_error_logs (error_type, error_message, chat_id, user_message, timestamp, error_data)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            entry.get('error_type', ''),
            entry.get('error', ''),
            entry.get('chat_id', ''),
            entry.get('user_msg', ''),
            entry.get('timestamp'),
            json.dumps(entry)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת לוג שגיאות בוט: {e}")
        raise

def save_bot_trace_log(entry):
    """שומר לוג trace בוט ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_trace_logs (
                id SERIAL PRIMARY KEY,
                chat_id VARCHAR(50),
                bot_message TEXT,
                timestamp TIMESTAMP,
                trace_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO bot_trace_logs (chat_id, bot_message, timestamp, trace_data)
            VALUES (%s, %s, %s, %s)
        """, (
            entry.get('chat_id', ''),
            entry.get('bot_message', ''),
            entry.get('timestamp'),
            json.dumps(entry)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת לוג trace בוט: {e}")
        raise

def save_sync_queue_data(sync_data):
    """שומר נתוני תור סנכרון ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id SERIAL PRIMARY KEY,
                queue_data JSONB,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO sync_queue (queue_data)
            VALUES (%s)
        """, (json.dumps(sync_data),))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת תור סנכרון: {e}")
        raise

def save_rollback_data(filename, rollback_data):
    """שומר נתוני rollback ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rollback_data (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255),
                rollback_info JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO rollback_data (filename, rollback_info)
            VALUES (%s, %s)
        """, (filename, json.dumps(rollback_data)))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת נתוני rollback {filename}: {e}")
        raise

def save_free_model_limits_data(limits_data):
    """שומר מגבלות מודל חינמי ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS free_model_limits (
                id SERIAL PRIMARY KEY,
                limits_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO free_model_limits (limits_data)
            VALUES (%s)
        """, (json.dumps(limits_data),))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת מגבלות מודל חינמי: {e}")
        raise

def save_temp_critical_user_data(filename, temp_data):
    """שומר נתוני קובץ זמני משתמש קריטי ל-SQL"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS temp_critical_files (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255),
                temp_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנסת נתונים
        cur.execute("""
            INSERT INTO temp_critical_files (filename, temp_data)
            VALUES (%s, %s)
        """, (filename, json.dumps(temp_data)))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"שגיאה בשמירת קובץ זמני {filename}: {e}")
        raise 