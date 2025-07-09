import psycopg2
from config import config
from datetime import datetime
import json
import threading
import queue

# 🎯 מרכז ניהול טיפוסי שדות - פתרון פשוט ויציב
def safe_str(value):
    """
    🎯 פונקציה מרכזית להמרה בטוחה לטקסט
    פותרת בעיות text=bigint ו-chat_id is None
    """
    if value is None:
        raise ValueError("ערך לא יכול להיות None")
    return str(value).strip()

def normalize_chat_id(chat_id):
    """
    🎯 מנרמל chat_id לטיפוס אחיד (TEXT)
    מונע בעיות text=bigint
    """
    return safe_str(chat_id)

def validate_chat_id(chat_id):
    """
    🎯 בודק תקינות chat_id
    """
    if chat_id is None:
        raise ValueError("chat_id לא יכול להיות None")
    return safe_str(chat_id)

def safe_operation(operation, *args, **kwargs):
    """
    🎯 הרצת פעולה בטוחה עם טיפול בשגיאות
    """
    try:
        return operation(*args, **kwargs)
    except Exception as e:
        print(f"❌ שגיאה בפעולה: {e}")
        return None

# ייבוא פונקציית debug logging
try:
    from config import should_log_debug_prints
except ImportError:
    # ברירת מחדל אם הפונקציה לא קיימת
    def should_log_debug_prints() -> bool:
        return False

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# 🚀 תור ברקע למטריקות - לא חוסם את הבוט!
_metrics_queue = queue.Queue()
_metrics_worker_running = False
_metrics_worker_thread = None

def _metrics_worker():
    """Worker thread שמעבד מטריקות ברקע"""
    global _metrics_worker_running
    _metrics_worker_running = True
    
    while _metrics_worker_running:
        try:
            # קבלת מטריקה מהתור (עם timeout)
            metrics_data = _metrics_queue.get(timeout=1)
            
            if metrics_data is None:  # אות ליציאה
                break
                
            # שמירה בפועל למסד הנתונים
            _save_system_metrics_sync(**metrics_data)
            
            _metrics_queue.task_done()
            
        except queue.Empty:
            continue
        except Exception as e:
            if should_log_debug_prints():
                print(f"❌ Worker thread error: {e}")

def _save_system_metrics_sync(metric_type, chat_id=None, **metrics):
    """
    שמירת מטריקות למסד הנתונים (גרסה סינכרונית - לworker thread בלבד)
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # יצירת טבלה אם לא קיימת
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id SERIAL PRIMARY KEY,
                metric_type VARCHAR(50) NOT NULL,
                chat_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- מטריקות זיכרון
                memory_mb DECIMAL(10,2),
                memory_stage VARCHAR(50),
                
                -- מטריקות זמן
                response_time_seconds DECIMAL(10,3),
                prep_time_seconds DECIMAL(10,3),
                processing_time_seconds DECIMAL(10,3),
                billing_time_seconds DECIMAL(10,3),
                gpt_latency_seconds DECIMAL(10,3),
                
                -- מטריקות concurrent
                active_sessions INTEGER,
                max_concurrent_users INTEGER,
                avg_response_time DECIMAL(10,3),
                max_response_time DECIMAL(10,3),
                
                -- מטריקות API
                api_calls_count INTEGER,
                api_calls_per_minute INTEGER,
                
                -- מטריקות שגיאות
                error_count INTEGER,
                error_type VARCHAR(100),
                timeout_count INTEGER,
                success_count INTEGER,
                
                -- מטריקות כלליות
                additional_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # הכנת הנתונים להכנסה
        insert_data = {
            'metric_type': metric_type,
            'chat_id': chat_id,
            'memory_mb': metrics.get('memory_mb'),
            'memory_stage': metrics.get('memory_stage'),
            'response_time_seconds': metrics.get('response_time_seconds'),
            'prep_time_seconds': metrics.get('prep_time_seconds'),
            'processing_time_seconds': metrics.get('processing_time_seconds'),
            'billing_time_seconds': metrics.get('billing_time_seconds'),
            'gpt_latency_seconds': metrics.get('gpt_latency_seconds'),
            'active_sessions': metrics.get('active_sessions'),
            'max_concurrent_users': metrics.get('max_concurrent_users'),
            'avg_response_time': metrics.get('avg_response_time'),
            'max_response_time': metrics.get('max_response_time'),
            'api_calls_count': metrics.get('api_calls_count'),
            'api_calls_per_minute': metrics.get('api_calls_per_minute'),
            'error_count': metrics.get('error_count'),
            'error_type': metrics.get('error_type'),
            'timeout_count': metrics.get('timeout_count'),
            'success_count': metrics.get('success_count'),
            'additional_data': json.dumps(metrics.get('additional_data', {})) if metrics.get('additional_data') else None
        }
        
        # הכנת SQL דינמי
        fields = [k for k, v in insert_data.items() if v is not None]
        placeholders = ', '.join(['%s'] * len(fields))
        values = [insert_data[k] for k in fields]
        
        insert_sql = f"""
        INSERT INTO system_metrics ({', '.join(fields)})
        VALUES ({placeholders})
        """
        
        cur.execute(insert_sql, values)
        conn.commit()
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה בשמירת מטריקות {metric_type}: {e}")
        return False

def start_metrics_worker():
    """התחלת worker thread למטריקות"""
    global _metrics_worker_thread, _metrics_worker_running
    
    if _metrics_worker_thread is not None and _metrics_worker_thread.is_alive():
        return  # כבר רץ
    
    _metrics_worker_running = True
    _metrics_worker_thread = threading.Thread(target=_metrics_worker, daemon=True)
    _metrics_worker_thread.start()
    
    if should_log_debug_prints():
        print("🚀 [METRICS] Background worker started")

def stop_metrics_worker():
    """עצירת worker thread למטריקות"""
    global _metrics_worker_running
    
    _metrics_worker_running = False
    _metrics_queue.put(None)  # אות ליציאה
    
    if _metrics_worker_thread and _metrics_worker_thread.is_alive():
        _metrics_worker_thread.join(timeout=5)

def save_system_metrics(metric_type, chat_id=None, **metrics):
    """
    שומר מטריקות מערכת ברקע - לא חוסם את הבוט!
    
    :param metric_type: סוג המטריקה (memory, response_time, concurrent, api_calls, errors)
    :param chat_id: מזהה משתמש (אם רלוונטי)
    :param metrics: מטריקות נוספות כ-kwargs
    """
    try:
        # הפעלת worker thread אם לא רץ
        if not _metrics_worker_running:
            start_metrics_worker()
        
        # הוספה לתור ברקע - לא חוסם!
        metrics_data = {
            'metric_type': metric_type,
            'chat_id': chat_id,
            **metrics
        }
        
        # ניסיון הוספה לתור (עם timeout קצר)
        _metrics_queue.put(metrics_data, timeout=0.001)  # 1ms timeout
        
        return True
        
    except queue.Full:
        # התור מלא - לא נחסום את הבוט!
        if should_log_debug_prints():
            print(f"⚠️ [METRICS] Queue full, skipping {metric_type} metric")
        return False
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה בהוספת מטריקה {metric_type}: {e}")
        return False

# === יצירת טבלאות (אם לא קיימות) ===
def create_tables():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # 🟢 טבלאות קריטיות - נשארות
    cur.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        chat_id TEXT,
        user_msg TEXT,
        bot_msg TEXT,
        timestamp TIMESTAMP
    );
    ''')
    
    # יצירת טבלת user_profiles עם עמודות נפרדות
    from fields_dict import get_user_profile_fields, FIELDS_DICT
    
    columns = []
    for field in get_user_profile_fields():
        field_info = FIELDS_DICT[field]
        field_type = field_info['type']
        
        # המרת טיפוסי Python לטיפוסי PostgreSQL
        if field_type == int:
            pg_type = 'INTEGER'
        elif field_type == float:
            pg_type = 'REAL'
        elif field_type == bool:
            pg_type = 'BOOLEAN'
        else:
            pg_type = 'TEXT'
        
        columns.append(f"{field} {pg_type}")
    
    create_user_profiles_sql = f'''
    CREATE TABLE IF NOT EXISTS user_profiles (
        id SERIAL PRIMARY KEY,
        chat_id TEXT UNIQUE NOT NULL,
        {', '.join(columns)},
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    '''
    
    cur.execute(create_user_profiles_sql)
    
    # 🟢 טבלת gpt_calls_log - קריטית (מכילה את כל נתוני הקריאות והעלויות)
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
    
    # 🚫 DISABLED: טבלאות מיותרות לא נוצרות יותר
    # gpt_usage_log - כפול ל-gpt_calls_log
    # system_logs - יש לוגים ספציפיים יותר
    # critical_users - VIP מנוהל בקונפיג
    # billing_usage - נתונים ב-gpt_calls_log
    # errors_stats - לא קריטי
    # free_model_limits - מנוהל בקונפיג
    
    if should_log_debug_prints():
        print("✅ [DB] Created only critical tables: chat_messages, user_profiles, gpt_calls_log")
        print("🚫 [DB] Skipped unused tables: gpt_usage_log, system_logs, critical_users, billing_usage, errors_stats, free_model_limits")
    
    conn.commit()
    cur.close()
    conn.close()

# === שמירת הודעת צ'אט ===
# === שמירת הודעת צ'אט מורחבת ===
def save_chat_message(chat_id, user_msg, bot_msg, timestamp=None, **kwargs):
    """
    שומר הודעת צ'אט עם נתונים מורחבים
    kwargs יכול להכיל:
    - message_type: סוג ההודעה (user/bot/pair/system)
    - telegram_message_id: מזהה ההודעה בטלגרם
    - source_file: קובץ המקור
    - gpt_type: סוג GPT (A/B/C/D)
    - gpt_model: שם המודל
    - gpt_cost_usd: עלות בדולרים
    - gpt_tokens_input/output: מספר טוקנים
    - gpt_request/response: בקשה ותגובה מלאה
    - metadata: מטה-דאטה כללי
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # הכנת הנתונים המורחבים
    insert_sql = """
    INSERT INTO chat_messages (
        chat_id, user_msg, bot_msg, timestamp,
        message_type, telegram_message_id, source_file, source_line_number,
        gpt_type, gpt_model, gpt_cost_usd, gpt_tokens_input, gpt_tokens_output,
        gpt_request, gpt_response, user_data, bot_data, metadata
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """
    
    # חילוץ נתונים מ-kwargs
    message_type = kwargs.get('message_type', 'pair' if user_msg and bot_msg else ('user' if user_msg else 'bot'))
    telegram_message_id = kwargs.get('telegram_message_id')
    source_file = kwargs.get('source_file', 'live_chat')
    source_line_number = kwargs.get('source_line_number')
    gpt_type = kwargs.get('gpt_type')
    gpt_model = kwargs.get('gpt_model')
    gpt_cost_usd = kwargs.get('gpt_cost_usd')
    gpt_tokens_input = kwargs.get('gpt_tokens_input')
    gpt_tokens_output = kwargs.get('gpt_tokens_output')
    gpt_request = kwargs.get('gpt_request')
    gpt_response = kwargs.get('gpt_response')
    user_data = kwargs.get('user_data')
    bot_data = kwargs.get('bot_data')
    metadata = kwargs.get('metadata')
    
    # המרת JSON objects לstrings
    import json
    gpt_request_json = json.dumps(gpt_request) if gpt_request else None
    gpt_response_json = json.dumps(gpt_response) if gpt_response else None
    user_data_json = json.dumps(user_data) if user_data else None
    bot_data_json = json.dumps(bot_data) if bot_data else None
    metadata_json = json.dumps(metadata) if metadata else None
    
    cur.execute(insert_sql, (
        chat_id, user_msg, bot_msg, timestamp or datetime.utcnow(),
        message_type, telegram_message_id, source_file, source_line_number,
        gpt_type, gpt_model, gpt_cost_usd, gpt_tokens_input, gpt_tokens_output,
        gpt_request_json, gpt_response_json, user_data_json, bot_data_json, metadata_json
    ))
    
    conn.commit()
    cur.close()
    conn.close()


def get_chat_history(chat_id, limit=100):
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
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
def save_user_profile(chat_id, profile_data):
    """
    שומר פרופיל משתמש במבנה החדש עם עמודות נפרדות
    profile_data יכול להיות dict או JSON string
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # המרת JSON string ל-dict אם צריך
    if isinstance(profile_data, str):
        try:
            profile_data = json.loads(profile_data)
        except:
            profile_data = {}
    
    # הכנת נתונים להכנסה
    from fields_dict import get_user_profile_fields
    
    # יצירת dict עם כל השדות
    insert_data = {'chat_id': chat_id}
    for field in get_user_profile_fields():
        if field in profile_data:
            insert_data[field] = profile_data[field]
        else:
            insert_data[field] = None
    
    # הוספת timestamp
    insert_data['updated_at'] = datetime.utcnow()
    
    # יצירת SQL דינמי
    fields = list(insert_data.keys())
    placeholders = ', '.join(['%s'] * len(fields))
    values = list(insert_data.values())
    
    insert_sql = f"""
    INSERT INTO user_profiles ({', '.join(fields)})
    VALUES ({placeholders})
    ON CONFLICT (chat_id) DO UPDATE SET
    {', '.join([f"{field} = EXCLUDED.{field}" for field in fields if field != 'chat_id'])}
    """
    
    cur.execute(insert_sql, values)
    conn.commit()
    cur.close()
    conn.close()

# === שליפת פרופיל משתמש ===
def get_user_profile(chat_id):
    """
    מחזיר פרופיל משתמשdict עם כל השדות
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    from fields_dict import get_user_profile_fields
    
    # יצירת SQL עם כל השדות
    fields = ['chat_id'] + get_user_profile_fields()
    select_sql = f"SELECT {', '.join(fields)} FROM user_profiles WHERE chat_id=%s"
    
    cur.execute(select_sql, (chat_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row:
        # המרת השורה ל-dict
        profile_dict = {}
        for i, field in enumerate(fields):
            profile_dict[field] = row[i]
        return profile_dict
    
    return None

# === שמירת לוג GPT ===
def save_gpt_call_log(chat_id, call_type, request_data, response_data, tokens_input, tokens_output, cost_usd, processing_time_seconds, timestamp=None):
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
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

# === שמירת לוג מערכת ===
def save_system_log(log_level, module, message, extra_data, timestamp=None):
    """
    🚫 DISABLED: טבלת system_logs הושבתה - לוגים נשמרים ב-bot_error_logs/bot_trace_logs
    יש לוגים ספציפיים יותר לכל סוג שגיאה/אירוע
    """
    try:
        # לוגים נשמרים בטבלאות ספציפיות - לא צריך טבלה כללית
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] system_logs table disabled - logs saved in specific tables")
        return  # לא שומר לטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # cur = conn.cursor()
        # ... system_logs table operations disabled
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"⚠️ שגיאה בשמירת לוג מערכת: {e}")

def save_critical_user_data(chat_id, user_info):
    """
    🚫 DISABLED: טבלת critical_users הושבתה - כל המידע הקריטי נשמר ב-user_profiles
    הפונקציה הזו לא פעילה יותר - המשתמש הקריטי היחיד (VIP) מוגדר בקונפיג
    """
    try:
        # שמירת המידע הקריטי ב-user_profiles במקום
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] critical_users table disabled - VIP user data managed via config for chat_id: {chat_id}")
        return  # לא שומר לטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # cur = conn.cursor()
        # ... critical_users table operations disabled
        
    except Exception as e:
        print(f"שגיאה בשמירת משתמש קריטי {chat_id}: {e}")
        raise

def save_reminder_state(chat_id, reminder_info):
    """שומר מצב תזכורת ל-SQL"""
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
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
            chat_id,
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
    """
    🚫 DISABLED: טבלת billing_usage הושבתה - כל נתוני החיוב נשמרים ב-gpt_calls_log
    כל עלות של קריאה נשמרת ב-gpt_calls_log עם cost_usd מלא
    """
    try:
        # כל נתוני החיוב כבר נשמרים ב-gpt_calls_log - לא צריך טבלה נפרדת
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] billing_usage table disabled - all billing data saved in gpt_calls_log")
        return  # לא שומר לטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # cur = conn.cursor()
        # ... billing_usage table operations disabled
        
    except Exception as e:
        print(f"שגיאה בשמירת נתוני חיוב: {e}")
        raise

def save_errors_stats_data(errors_data):
    """
    🚫 DISABLED: טבלת errors_stats הושבתה - כל השגיאות נשמרות ב-system_logs
    סטטיסטיקות שגיאות ניתן להפיק מ-system_logs לפי הצורך
    """
    try:
        # כל השגיאות כבר נשמרות ב-system_logs - לא צריך טבלה נפרדת
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] errors_stats table disabled - all errors saved in system_logs")
        return  # לא שומר לטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # cur = conn.cursor()
        # ... errors_stats table operations disabled
        
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
    """
    🚫 DISABLED: טבלת free_model_limits הושבתה - מגבלות מודלים מנוהלות בקונפיג
    אין צורך בטבלה נפרדת למגבלות - הכל מנוהל בקוד ובקונפיג
    """
    try:
        # מגבלות מודלים מנוהלות בקונפיג - לא צריך טבלה נפרדת
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] free_model_limits table disabled - limits managed via config")
        return  # לא שומר לטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # cur = conn.cursor()
        # ... free_model_limits table operations disabled
        
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

# === פונקציות עזר מורחבות ===
def save_gpt_chat_message(chat_id, user_msg, bot_msg, gpt_data=None, timestamp=None):
    """
    שומר הודעת צ'אט עם נתוני GPT מלאים
    gpt_data יכול להכיל:
    - type: A/B/C/D
    - model: שם המודל
    - cost_usd: עלות
    - tokens_input/output: טוקנים
    - request/response: בקשה ותגובה מלאה
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    kwargs = {'source_file': 'live_chat'}
    
    if gpt_data:
        gpt_kwargs = {
            'gpt_type': gpt_data.get('type'),
            'gpt_model': gpt_data.get('model'),
            'gpt_cost_usd': gpt_data.get('cost_usd'),
            'gpt_tokens_input': gpt_data.get('tokens_input'),
            'gpt_tokens_output': gpt_data.get('tokens_output'),
            'gpt_request': gpt_data.get('request'),
            'gpt_response': gpt_data.get('response'),
            'metadata': {
                'gpt_latency': gpt_data.get('latency'),
                'gpt_timestamp': gpt_data.get('timestamp'),
                'usage': gpt_data.get('usage', {})
            }
        }
        kwargs = {**kwargs, **gpt_kwargs}
    
    return save_chat_message(chat_id, user_msg, bot_msg, timestamp, **kwargs)

def get_chat_statistics():
    """מחזיר סטטיסטיקות מורחבות על השיחות"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    stats = {}
    
    # סטטיסטיקות בסיסיות
    cur.execute("SELECT COUNT(*) FROM chat_messages")
    stats['total_messages'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT chat_id) FROM chat_messages")
    stats['unique_chats'] = cur.fetchone()[0]
    
    # סטטיסטיקות GPT
    cur.execute("SELECT COUNT(*) FROM chat_messages WHERE gpt_type IS NOT NULL")
    stats['gpt_messages'] = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(gpt_cost_usd) FROM chat_messages WHERE gpt_cost_usd IS NOT NULL")
    result = cur.fetchone()[0]
    stats['total_cost_usd'] = float(result) if result else 0.0
    
    cur.execute("SELECT gpt_type, COUNT(*) FROM chat_messages WHERE gpt_type IS NOT NULL GROUP BY gpt_type")
    stats['gpt_by_type'] = dict(cur.fetchall())
    
    # סטטיסטיקות לפי סוג הודעה
    cur.execute("SELECT message_type, COUNT(*) FROM chat_messages WHERE message_type IS NOT NULL GROUP BY message_type")
    stats['by_message_type'] = dict(cur.fetchall())
    
    # צ'אטים פעילים (בשבוע האחרון)
    cur.execute("""
        SELECT COUNT(DISTINCT chat_id) 
        FROM chat_messages 
        WHERE created_at > NOW() - INTERVAL '7 days'
    """)
    stats['active_chats_week'] = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return stats

def get_chat_history_enhanced(chat_id, limit=50):
    """מחזיר היסטוריית צ'אט עם נתונים מורחבים"""
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            id, user_msg, bot_msg, timestamp, message_type,
            gpt_type, gpt_model, gpt_cost_usd, source_file, metadata
        FROM chat_messages 
        WHERE chat_id = %s 
        ORDER BY timestamp DESC 
        LIMIT %s
    """, (chat_id, limit))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    history = []
    for row in results:
        history.append({
            'id': row[0],
            'user_msg': row[1],
            'bot_msg': row[2],
            'timestamp': row[3],
            'message_type': row[4],
            'gpt_type': row[5],
            'gpt_model': row[6],
            'gpt_cost_usd': row[7],
            'source_file': row[8],
            'metadata': row[9]
        })
    
    return history

def get_billing_usage_data():
    """
    🚫 DISABLED: טבלת billing_usage הושבתה - נתוני חיוב נשלפים מ-gpt_calls_log
    """
    try:
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] billing_usage table disabled - billing data available in gpt_calls_log")
        return None  # לא קורא מהטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # ... billing_usage table operations disabled
        
    except Exception as e:
        print(f"שגיאה בקריאת נתוני חיוב: {e}")
        return None

def get_free_model_limits_data():
    """
    🚫 DISABLED: טבלת free_model_limits הושבתה - מגבלות מנוהלות בקונפיג
    """
    try:
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] free_model_limits table disabled - limits managed via config")
        return None  # לא קורא מהטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # ... free_model_limits table operations disabled
        
    except Exception as e:
        print(f"שגיאה בקריאת מגבלות מודל חינמי: {e}")
        return None

def get_errors_stats_data():
    """
    🚫 DISABLED: טבלת errors_stats הושבתה - סטטיסטיקות שגיאות מ-system_logs
    """
    try:
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] errors_stats table disabled - error stats available from system_logs")
        return {}  # לא קורא מהטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # ... errors_stats table operations disabled
        
    except Exception as e:
        print(f"שגיאה בקריאת סטטיסטיקות שגיאות: {e}")
        return {}

def get_critical_users_data():
    """
    🚫 DISABLED: טבלת critical_users הושבתה - משתמש VIP מוגדר בקונפיג
    """
    try:
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] critical_users table disabled - VIP user managed via config")
        return {}  # לא קורא מהטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # ... critical_users table operations disabled
        
    except Exception as e:
        print(f"שגיאה בקריאת משתמשים קריטיים: {e}")
        return {}

def get_reminder_states_data():
    """מחזיר מצבי תזכורות ממסד הנתונים"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT chat_id, last_activity, reminder_sent, reminder_count, state_data 
            FROM reminder_states 
            ORDER BY created_at DESC
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if results:
            return {
                str(chat_id): {
                    'last_activity': last_activity,
                    'reminder_sent': reminder_sent,
                    'reminder_count': reminder_count,
                    **state_data
                } for chat_id, last_activity, reminder_sent, reminder_count, state_data in results
            }
        return {}
        
    except Exception as e:
        print(f"שגיאה בקריאת מצבי תזכורות: {e}")
        return {}

# === שמירת לוג שימוש ===
def save_gpt_usage_log(chat_id, model, usage, cost_agorot, timestamp=None):
    """
    🚫 DISABLED: טבלת gpt_usage_log הושבתה - כל נתוני השימוש נשמרים ב-gpt_calls_log
    gpt_calls_log מכיל את כל המידע הנדרש: עלויות, טוקנים, מודלים, זמנים
    """
    try:
        # כל נתוני השימוש כבר נשמרים ב-gpt_calls_log - לא צריך טבלה נפרדת
        if should_log_debug_prints():
            print(f"🔄 [DISABLED] gpt_usage_log table disabled - all usage data saved in gpt_calls_log")
        return  # לא שומר לטבלה המיותרת
        
        # הקוד הישן הושבת:
        # conn = psycopg2.connect(DB_URL)
        # cur = conn.cursor()
        # ... gpt_usage_log table operations disabled
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"⚠️ שגיאה בשמירת נתוני שימוש: {e}")

def increment_user_message_count(chat_id):
    """
    מעדכן את מונה ההודעות הכולל של המשתמש ב-+1
    אם המשתמש לא קיים בטבלה, יוצר רשומה חדשה עם מונה 1
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקה אם המשתמש כבר קיים
        cur.execute("SELECT total_messages_count FROM user_profiles WHERE chat_id = %s", (chat_id,))
        result = cur.fetchone()
        
        if result:
            # משתמש קיים - מעדכן את המונה
            current_count = result[0] if result[0] is not None else 0
            new_count = current_count + 1
            cur.execute(
                "UPDATE user_profiles SET total_messages_count = %s, updated_at = %s WHERE chat_id = %s",
                (new_count, datetime.utcnow(), chat_id)
            )
            if should_log_debug_prints():
                print(f"📊 [DB] Updated message count for {chat_id}: {current_count} → {new_count}")
        else:
            # משתמש חדש - יוצר רשומה עם מונה 1
            from fields_dict import get_user_profile_fields
            
            # יצירת dict עם כל השדות (ברירת מחדל)
            insert_data = {'chat_id': chat_id, 'total_messages_count': 1}
            for field in get_user_profile_fields():
                if field != 'total_messages_count':  # כבר הוספנו אותו
                    insert_data[field] = None
            
            # הוספת timestamp
            insert_data['updated_at'] = datetime.utcnow()
            
            # יצירת SQL דינמי
            fields = list(insert_data.keys())
            placeholders = ', '.join(['%s'] * len(fields))
            values = list(insert_data.values())
            
            insert_sql = f"""
            INSERT INTO user_profiles ({', '.join(fields)})
            VALUES ({placeholders})
            """
            
            cur.execute(insert_sql, values)
            if should_log_debug_prints():
                print(f"📊 [DB] Created new user profile with message count 1 for {chat_id}")
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה בעדכון מונה הודעות עבור {chat_id}: {e}")
        return False

def get_user_message_count(chat_id):
    """
    מחזיר את מספר ההודעות הכולל של המשתמש
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT total_messages_count FROM user_profiles WHERE chat_id = %s", (chat_id,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return result[0] if result and result[0] is not None else 0
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה בקריאת מונה הודעות עבור {chat_id}: {e}")
        return 0

def clear_user_from_database(chat_id):
    """
    מוחק את כל הודעות הצ'אט של המשתמש מטבלת chat_messages,
    ומנקה את כל השדות של המשתמש ב-user_profiles (כולל chat_id),
    ומשאיר אך ורק את code_approve (כל השאר NULL/ריק).
    לא נוגע בכלל ב-gpt_calls_log!
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # מחיקת היסטוריית צ'אט
        cur.execute("DELETE FROM chat_messages WHERE chat_id = %s", (chat_id,))
        chat_deleted = cur.rowcount
        
        # איפוס כל השדות ב-user_profiles חוץ מ-code_approve
        cur.execute("""
            UPDATE user_profiles
            SET chat_id = NULL,
                name = NULL,
                age = NULL,
                pronoun_preference = NULL,
                occupation_or_role = NULL,
                attracted_to = NULL,
                relationship_type = NULL,
                parental_status = NULL,
                self_religious_affiliation = NULL,
                self_religiosity_level = NULL,
                family_religiosity = NULL,
                closet_status = NULL,
                who_knows = NULL,
                who_doesnt_know = NULL,
                attends_therapy = NULL,
                primary_conflict = NULL,
                trauma_history = NULL,
                goal_in_course = NULL,
                language_of_strength = NULL,
                date_first_seen = NULL,
                coping_strategies = NULL,
                fears_concerns = NULL,
                future_vision = NULL,
                other_insights = NULL,
                total_messages_count = NULL,
                summary = NULL,
                code_try = NULL,
                approved = NULL,
                updated_at = %s
            WHERE chat_id = %s
        """, (datetime.utcnow(), chat_id))
        profile_updated = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        if should_log_debug_prints():
            print(f"🗑️ [DB] נמחקו {chat_deleted} הודעות צ'אט, פרופיל אופס (רק code_approve נשאר) עבור {chat_id}")
        
        return chat_deleted > 0 or profile_updated > 0
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה במחיקת משתמש מהמסד נתונים: {e}")
        return False

# ================================
# 🔥 פונקציות חדשות למסד נתונים - מחליפות Google Sheets!
# ================================

# 🗑️ נמחקו הפונקציות הישנות של user_states - הכל עכשיו ב-user_profiles

# ================================
# 📋 פונקציות לוגיקת קודי אישור חדשה - לפי המדריך!
# ================================

def register_user_with_code_db(chat_id, code_input=None):
    """
    רישום משתמש עם קוד אישור לפי הלוגיקה של המדריך
    
    🔄 אם code_input הוא None: יוצר שורה זמנית למשתמש חדש
    🔄 אם code_input ניתן: מנסה לבצע מיזוג עם קוד קיים
    
    :param chat_id: מזהה צ'אט
    :param code_input: קוד אישור (או None למשתמש חדש)
    :return: {"success": bool, "message": str, "attempt_num": int}
    """
    # 🎯 נרמול chat_id לטיפוס אחיד
    chat_id = validate_chat_id(chat_id)
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        if should_log_debug_prints():
            print(f"🔍 [DB] register_user_with_code_db: chat_id={chat_id}, code_input={code_input}")
        
        if code_input is None:
            # שלב 1: משתמש חדש - יצירת שורה זמנית
            cur.execute("SELECT chat_id FROM user_profiles WHERE chat_id = %s", (chat_id,))
            existing = cur.fetchone()
            
            if existing:
                # משתמש כבר קיים
                if should_log_debug_prints():
                    print(f"🔍 [DB] משתמש {chat_id} כבר קיים")
                return {"success": True, "message": "משתמש כבר קיים", "attempt_num": 0}
            
            # יצירת שורה זמנית חדשה
            cur.execute("""
                INSERT INTO user_profiles (chat_id, code_try, approved, updated_at) 
                VALUES (%s, 0, FALSE, %s)
            """, (chat_id, datetime.utcnow()))
            
            conn.commit()
            cur.close()
            conn.close()
            
            if should_log_debug_prints():
                print(f"✅ [DB] נוצרה שורה זמנית עבור {chat_id}")
            
            return {"success": True, "message": "נוצרה שורה זמנית", "attempt_num": 0}
        
        else:
            # שלב 3: בדיקת קוד ומיזוג שורות
            code_input = str(code_input).strip()
            
            # BEGIN TRANSACTION לאטומיות
            cur.execute("BEGIN")
            
            # בדיקה אם הקוד קיים ופנוי (FOR UPDATE למניעת race conditions)
            cur.execute("""
                SELECT chat_id, code_try 
                FROM user_profiles 
                WHERE code_approve = %s 
                FOR UPDATE
            """, (code_input,))
            
            code_row = cur.fetchone()
            
            if not code_row:
                # קוד לא קיים
                # הגדלת code_try למשתמש
                cur.execute("""
                    UPDATE user_profiles 
                    SET code_try = code_try + 1, updated_at = %s 
                    WHERE chat_id = %s
                """, (datetime.utcnow(), str(chat_id)))
                
                # קבלת מספר הניסיון החדש
                cur.execute("SELECT code_try FROM user_profiles WHERE chat_id = %s", (str(chat_id),))
                attempt_result = cur.fetchone()
                attempt_num = attempt_result[0] if attempt_result else 1
                
                conn.commit()
                cur.close()
                conn.close()
                
                if should_log_debug_prints():
                    print(f"❌ [DB] קוד {code_input} לא קיים - attempt_num={attempt_num}")
                
                return {"success": False, "message": "קוד לא קיים", "attempt_num": attempt_num}
            
            existing_chat_id, existing_code_try = code_row
            
            if existing_chat_id and existing_chat_id != str(chat_id):
                # קוד כבר תפוס על ידי משתמש אחר
                # הגדלת code_try למשתמש הנוכחי
                cur.execute("""
                    UPDATE user_profiles 
                    SET code_try = code_try + 1, updated_at = %s 
                    WHERE chat_id = %s
                """, (datetime.utcnow(), str(chat_id)))
                
                # קבלת מספר הניסיון החדש
                cur.execute("SELECT code_try FROM user_profiles WHERE chat_id = %s", (str(chat_id),))
                attempt_result = cur.fetchone()
                attempt_num = attempt_result[0] if attempt_result else 1
                
                conn.commit()
                cur.close()
                conn.close()
                
                if should_log_debug_prints():
                    print(f"❌ [DB] קוד {code_input} תפוס על ידי {existing_chat_id} - attempt_num={attempt_num}")
                
                return {"success": False, "message": "קוד כבר בשימוש", "attempt_num": attempt_num}
            
            # קוד תקין ופנוי - מיזוג השורות!
            
            # 1. שמירת code_try מהשורה הזמנית
            cur.execute("SELECT code_try FROM user_profiles WHERE chat_id = %s", (str(chat_id),))
            temp_row = cur.fetchone()
            user_code_try = temp_row[0] if temp_row else 0
            
            # 2. מחיקת השורה הזמנית
            cur.execute("DELETE FROM user_profiles WHERE chat_id = %s", (str(chat_id),))
            
            # 3. עדכון השורה עם הקוד
            cur.execute("""
                UPDATE user_profiles 
                SET chat_id = %s, code_try = %s, approved = FALSE, updated_at = %s
                WHERE code_approve = %s AND chat_id IS NULL
            """, (str(chat_id), user_code_try, datetime.utcnow(), code_input))
            
            # בדיקה שהעדכון הצליח
            if cur.rowcount == 0:
                conn.rollback()
                cur.close()
                conn.close()
                
                if should_log_debug_prints():
                    print(f"❌ [DB] עדכון נכשל עבור קוד {code_input}")
                
                return {"success": False, "message": "עדכון נכשל", "attempt_num": user_code_try}
            
            conn.commit()
            cur.close()
            conn.close()
            
            if should_log_debug_prints():
                print(f"✅ [DB] מיזוג הצליח: {chat_id} <-> {code_input}, code_try={user_code_try}")
            
            return {"success": True, "message": "קוד אושר", "attempt_num": user_code_try}
            
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ [DB] שגיאה ב-register_user_with_code_db: {e}")
        
        try:
            conn.rollback()
            cur.close()
            conn.close()
        except:
            pass
            
        return {"success": False, "message": f"שגיאה: {e}", "attempt_num": 0}

def check_user_approved_status_db(chat_id):
    """
    בדיקת סטטוס אישור משתמש במסד נתונים
    
    :param chat_id: מזהה צ'אט
    :return: {"status": "approved"/"pending_approval"/"pending_code"/"not_found"}
    """
    try:
        # שימוש ישיר ב-chat_id כמספר (BIGINT)
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT code_approve, approved 
            FROM user_profiles 
            WHERE chat_id = %s
        """, (chat_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return {"status": "not_found"}
        
        code_approve, approved = row
        
        if not code_approve:
            # משתמש קיים אבל אין לו קוד (שורה זמנית) - צריך קוד
            return {"status": "pending_code"}
        
        if approved:
            return {"status": "approved"}
        else:
            # משתמש קיים עם קוד אבל לא אישר תנאים - צריך אישור
            return {"status": "pending_approval"}
            
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ [DB] שגיאה ב-check_user_approved_status_db: {e}")
        return {"status": "error"}

def increment_code_try_db_new(chat_id):
    """
    מגדיל מונה ניסיונות קוד במסד נתונים (לפי הלוגיקה החדשה)
    
    :param chat_id: מזהה צ'אט
    :return: int (מספר הניסיון החדש)
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE user_profiles 
            SET code_try = code_try + 1, updated_at = %s 
            WHERE chat_id = %s
        """, (datetime.utcnow(), str(chat_id)))
        
        if cur.rowcount == 0:
            # אין שורה כזאת - יוצר שורה זמנית עם code_try=1
            cur.execute("""
                INSERT INTO user_profiles (chat_id, code_try, approved, updated_at) 
                VALUES (%s, 1, FALSE, %s)
            """, (str(chat_id), datetime.utcnow()))
            new_attempt = 1
        else:
            # קבלת הערך החדש
            cur.execute("SELECT code_try FROM user_profiles WHERE chat_id = %s", (str(chat_id),))
            result = cur.fetchone()
            new_attempt = result[0] if result else 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        if should_log_debug_prints():
            print(f"🔢 [DB] increment_code_try_db_new: {chat_id} -> {new_attempt}")
        
        return new_attempt
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ [DB] שגיאה ב-increment_code_try_db_new: {e}")
        return 1

def approve_user_db_new(chat_id):
    """
    מאשר משתמש במסד נתונים (עדכון approved=TRUE) - הגרסה החדשה
    
    :param chat_id: מזהה צ'אט
    :return: {"success": bool}
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE user_profiles 
            SET approved = TRUE, updated_at = %s 
            WHERE chat_id = %s AND code_approve IS NOT NULL
        """, (datetime.utcnow(), str(chat_id)))
        
        success = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        
        if should_log_debug_prints():
            print(f"✅ [DB] approve_user_db_new: {chat_id} -> success={success}")
        
        return {"success": success}
        
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ [DB] שגיאה ב-approve_user_db_new: {e}")
        return {"success": False}

# === נקודת הכניסה לפונקציות המדריך ===
