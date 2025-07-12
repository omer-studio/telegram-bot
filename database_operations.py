#!/usr/bin/env python3
"""
database_operations.py - מקום אחד לכל הכתיבה למסד נתונים
🎯 איחוד מערכתי: כל הפונקציות שכותבות למסד נתונים במקום אחד
🔧 פשוט ונקי: כל פונקציה עושה דבר אחד ועושה אותו טוב
📊 קל לתחזוקה: אם יש בעיה, אתה יודע איפה לחפש
"""

import psycopg2
import json
import time
import queue
import threading
import subprocess
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager

# ייבואים מרכזיים
from config import config
from user_friendly_errors import safe_str, safe_operation, safe_chat_id, handle_database_error
from simple_config import TimeoutConfig
from utils import safe_str, get_israel_time
from fields_dict import FIELDS_DICT, get_user_profile_fields

# הגדרות מרכזיות
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
from simple_logger import logger

# תור למטריקות ברקע
_metrics_queue = queue.Queue()
_metrics_worker_running = False

# =================================
# 🔒 חיבור בטוח למסד נתונים
# =================================

@contextmanager
def safe_db_connection():
    """Context Manager בטוח לחיבורי מסד נתונים"""
    conn = None
    try:
        if not DB_URL:
            raise Exception("No database URL found")
        
        conn = psycopg2.connect(DB_URL)
        yield conn
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def validate_chat_id(chat_id):
    """נרמול chat_id לטיפוס אחיד"""
    return safe_chat_id(chat_id, require_valid=True)

def should_log_debug_prints():
    """בדיקה אם להדפיס הדפסות debug"""
    return config.get("DEBUG_PRINTS", False)

# =================================
# 📝 פונקציות שמירת הודעות
# =================================

def save_chat_message(chat_id: str, user_msg: str, bot_msg: str, 
                     timestamp: Optional[datetime] = None, **kwargs) -> Optional[int]:
    """
    שמירת הודעת צ'אט - הפונקציה המרכזית
    
    Returns:
        int: message_id אם הצליח, None אם נכשל
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # 🔧 הגדרת timezone למסד הנתונים לזמן ישראל
            cur.execute("SET timezone TO 'Asia/Jerusalem'")
            
            # יצירת טבלה אם לא קיימת
            create_chat_messages_table_only(cur)
            
            # הכנסת ההודעה
            insert_chat_message_only(cur, chat_id, user_msg, bot_msg, timestamp)
            
            # קבלת ID של ההודעה
            cur.execute("SELECT lastval()")
            message_id = cur.fetchone()[0]
            
            conn.commit()
            cur.close()
            
            if should_log_debug_prints():
                print(f"📝 [DB] נשמרה הודעה #{message_id} עבור chat_id={chat_id}")
            
            return message_id
            
    except Exception as e:
        handle_database_error("save", chat_id, user_msg)
        return None

def create_chat_messages_table_only(cursor):
    """יצירת טבלת chat_messages - פונקציה מרכזית"""
    # 🔧 הגדרת timezone למסד הנתונים לזמן ישראל
    cursor.execute("SET timezone TO 'Asia/Jerusalem'")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            chat_id TEXT NOT NULL,
            user_msg TEXT,
            bot_msg TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

def insert_chat_message_only(cursor, chat_id, user_msg, bot_msg, timestamp=None):
    """הכנסת הודעה לטבלת chat_messages - פונקציה מרכזית"""
    if timestamp is None:
        # 🔧 תיקון קריטי: שמירה בזמן ישראל תמיד!
        from utils import get_israel_time
        timestamp = get_israel_time()
    
    cursor.execute("""
        INSERT INTO chat_messages (chat_id, user_msg, bot_msg, timestamp) 
        VALUES (%s, %s, %s, %s)
    """, (chat_id, user_msg, bot_msg, timestamp))
    
    # הדפסת מה שנרשם
    user_msg_display = (user_msg[:50] + "...") if user_msg and len(user_msg) > 50 else (user_msg or "")
    bot_msg_display = (bot_msg[:50] + "...") if bot_msg and len(bot_msg) > 50 else (bot_msg or "")
    print(f"💬 NEW MESSAGE [DB_INSERT] chat_messages: chat_id={chat_id} | user_msg={user_msg_display} | bot_msg={bot_msg_display} | timestamp={timestamp} (זמן ישראל)")

# =================================
# 👤 פונקציות שמירת פרופילים
# =================================

def save_user_profile(chat_id: str, profile_data: Dict[str, Any]) -> bool:
    """
    שמירת פרופיל משתמש - הפונקציה המרכזית
    
    Args:
        chat_id: מזהה צ'אט
        profile_data: נתוני הפרופיל
        
    Returns:
        bool: True אם הצליח, False אם נכשל
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # יצירת טבלה אם לא קיימת
            create_user_profiles_table(cur)
            
            # בדיקה אם פרופיל קיים
            cur.execute("SELECT id FROM user_profiles WHERE chat_id = %s", (chat_id,))
            existing = cur.fetchone()
            
            if existing:
                # עדכון פרופיל קיים
                cur.execute("""
                    UPDATE user_profiles 
                    SET profile_data = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE chat_id = %s
                """, (json.dumps(profile_data), chat_id))
            else:
                # יצירת פרופיל חדש
                cur.execute("""
                    INSERT INTO user_profiles (chat_id, profile_data, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                """, (chat_id, json.dumps(profile_data)))
            
            conn.commit()
            cur.close()
            
            if should_log_debug_prints():
                print(f"✅ [DB] פרופיל נשמר עבור chat_id={chat_id}")
                
            return True
            
    except Exception as e:
        handle_database_error("save", chat_id, "profile")
        return False

def update_user_profile_field(chat_id: str, field_name: str, new_value: Any, old_value: Any = None) -> bool:
    """
    עדכון שדה בפרופיל משתמש - הפונקציה המרכזית
    
    Args:
        chat_id: מזהה צ'אט
        field_name: שם השדה
        new_value: ערך חדש
        old_value: ערך ישן (לצרכי logging)
        
    Returns:
        bool: True אם הצליח, False אם נכשל
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # בדיקה אם פרופיל קיים
            cur.execute("SELECT id FROM user_profiles WHERE chat_id = %s", (chat_id,))
            profile_exists = cur.fetchone() is not None
            
            if profile_exists:
                # עדכון שדה קיים
                cur.execute(f"""
                    UPDATE user_profiles 
                    SET {field_name} = %s, updated_at = %s 
                    WHERE chat_id = %s
                """, (new_value, get_israel_time(), chat_id))
            else:
                # יצירת פרופיל חדש
                cur.execute(f"""
                    INSERT INTO user_profiles (chat_id, {field_name}, updated_at) 
                    VALUES (%s, %s, %s)
                """, (chat_id, new_value, get_israel_time()))
            
            conn.commit()
            cur.close()
            
            if should_log_debug_prints():
                print(f"✅ [DB] שדה {field_name} עודכן עבור chat_id={chat_id}")
                
            return True
            
    except Exception as e:
        handle_database_error("update", chat_id, f"field_{field_name}")
        return False

def create_user_profiles_table(cursor):
    """יצירת טבלת user_profiles עם כל השדות מfields_dict"""
    from fields_dict import get_user_profile_fields
    
    # בדיקת קיום הטבלה
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'user_profiles'
        )
    """)
    table_exists = cursor.fetchone()[0]
    
    if table_exists:
        # ✅ אם הטבלה קיימת, נוודא שיש לה את השדות החדשים
        missing_columns = []
        required_columns = {
            'needs_recovery_message': 'BOOLEAN DEFAULT FALSE',
            'recovery_original_message': 'TEXT',
            'recovery_error_timestamp': 'TIMESTAMP',
            'last_message_time': 'TIMESTAMP'
        }
        
        for column_name, column_type in required_columns.items():
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'user_profiles' 
                    AND column_name = %s
                )
            """, (column_name,))
            column_exists = cursor.fetchone()[0]
            
            if not column_exists:
                missing_columns.append((column_name, column_type))
        
        # הוספת עמודות חסרות
        for column_name, column_type in missing_columns:
            try:
                cursor.execute(f"ALTER TABLE user_profiles ADD COLUMN {column_name} {column_type}")
                print(f"✅ [DB_MIGRATION] הוספנו עמודה חדשה: {column_name}")
            except Exception as e:
                print(f"⚠️ [DB_MIGRATION] שגיאה בהוספת עמודה {column_name}: {e}")
        
        return
    
    # ✅ אם הטבלה לא קיימת - ניצור אותה מאפס
    fields = get_user_profile_fields()
    
    # מיפוי טיפוסי Python לטיפוסי PostgreSQL
    type_mapping = {
        int: "INTEGER",
        float: "DECIMAL(10,2)",
        str: "TEXT",
        bool: "BOOLEAN DEFAULT FALSE",
        datetime: "TIMESTAMP"
    }
    
    # בניית רשימת עמודות
    columns = []
    for field in fields:
        from fields_dict import FIELDS_DICT
        field_type = FIELDS_DICT.get(field, {}).get('type', str)
        pg_type = type_mapping.get(field_type, "TEXT")
        columns.append(f"{field} {pg_type}")
    
    create_sql = f'''
    CREATE TABLE IF NOT EXISTS user_profiles (
        id SERIAL PRIMARY KEY,
        chat_id TEXT UNIQUE NOT NULL,
        {', '.join(columns)},
        profile_data JSONB,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    '''
    
    cursor.execute(create_sql)

# =================================
# 🔧 פונקציה לריצת מיגרציה כפויה
# =================================

def force_database_migration():
    """
    מריץ מיגרציה כפויה לתיקון הבעיות במסד הנתונים
    פונקציה זו מטפלת בכל הבעיות שזוהו:
    1. עמודות חסרות בטבלת user_profiles
    2. וידוא שכל השדות החדשים קיימים
    3. תיקון מבנה הטבלה
    """
    try:
        print("🔧 מתחיל מיגרציה כפויה של מסד הנתונים...")
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # שלב 1: וידוא שהטבלה קיימת עם כל השדות
            print("📋 בודק מבנה טבלת user_profiles...")
            create_user_profiles_table(cur)
            
            # שלב 2: בדיקת עמודות נוספות שחסרות
            print("🔍 בודק עמודות נוספות...")
            additional_columns = {
                'code_try': 'INTEGER DEFAULT 0',
                'approved': 'BOOLEAN DEFAULT FALSE', 
                'code_approve': 'TEXT',
                'total_messages_count': 'INTEGER DEFAULT 0'
            }
            
            for column_name, column_type in additional_columns.items():
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'user_profiles' 
                        AND column_name = %s
                    )
                """, (column_name,))
                column_exists = cur.fetchone()[0]
                
                if not column_exists:
                    try:
                        cur.execute(f"ALTER TABLE user_profiles ADD COLUMN {column_name} {column_type}")
                        print(f"✅ [MIGRATION] הוספנו עמודה: {column_name}")
                    except Exception as e:
                        print(f"⚠️ [MIGRATION] שגיאה בהוספת עמודה {column_name}: {e}")
            
            # שלב 3: וידוא שהטבלאות האחרות קיימות
            print("📊 בודק טבלאות נוספות...")
            create_chat_messages_table_only(cur)
            create_interactions_log_table(cur)
            
            conn.commit()
            cur.close()
            
            print("✅ מיגרציה כפויה הושלמה בהצלחה!")
            return True
            
    except Exception as e:
        print(f"❌ שגיאה במיגרציה כפויה: {e}")
        return False

# =================================
# 🤖 פונקציות שמירת GPT
# =================================

def save_gpt_call(chat_id: str, call_type: str, request_data: Dict, 
                  response_data: Dict, tokens_input: int, tokens_output: int, 
                  cost_usd: float, processing_time: float) -> bool:
    """
    שמירת קריאת GPT - הפונקציה המרכזית
    
    Args:
        chat_id: מזהה צ'אט
        call_type: סוג הקריאה (gpt_a, gpt_b, etc.)
        request_data: נתוני הבקשה
        response_data: נתוני התגובה
        tokens_input: מספר טוקנים בקלט
        tokens_output: מספר טוקנים בפלט
        cost_usd: עלות בדולרים
        processing_time: זמן עיבוד
        
    Returns:
        bool: True אם הצליח, False אם נכשל
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # יצירת טבלה אם לא קיימת
            cur.execute("""
                -- 🗑️ REMOVED: gpt_calls table disabled - migrated to interactions_log
    -- CREATE TABLE IF NOT EXISTS gpt_calls (
                    id SERIAL PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    call_type VARCHAR(50),
                    request_data JSONB,
                    response_data JSONB,
                    tokens_input INTEGER,
                    tokens_output INTEGER,
                    cost_usd DECIMAL(10,6),
                    processing_time FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # הכנסת הנתונים
            cur.execute("""
                -- 🗑️ REMOVED: INSERT into gpt_calls disabled
    -- INSERT INTO gpt_calls (chat_id, call_type, request_data, response_data, 
                                     tokens_input, tokens_output, cost_usd, processing_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (chat_id, call_type, json.dumps(request_data), json.dumps(response_data),
                  tokens_input, tokens_output, cost_usd, processing_time))
            
            conn.commit()
            cur.close()
            
            if should_log_debug_prints():
                print(f"🤖 [DB] קריאת GPT-{call_type} נשמרה עבור chat_id={chat_id}")
                
            return True
            
    except Exception as e:
        handle_database_error("save", chat_id, f"gpt_call_{call_type}")
        return False

# 🚫 REMOVED: save_gpt_call_log - הועברה למערכת interactions_log החדשה
# השתמש ב-interactions_logger.log_interaction() במקום

# =================================
# 📊 פונקציות שמירת מטריקות
# =================================

# 🗑️ REMOVED: system_metrics functionality - not needed anymore
# כל המטריקות מטופלות עכשיו דרך הלוגינג הרגיל

def save_system_metrics(metric_type: str, chat_id: Optional[str] = None, **metrics) -> bool:
    """
    🗑️ DEPRECATED: system_metrics טבלה הוסרה - לא נדרשת יותר
    כל המטריקות מטופלות דרך הלוגינג הרגיל של הבוט
    """
    if should_log_debug_prints():
        print(f"🔄 [DISABLED] system_metrics removed - metric '{metric_type}' skipped")
    return True

# =================================
# 🔄 פונקציות אינטראקציות
# =================================

# 🔥 **הועבר למערכת מרכזית**: interactions_logger.py
# השתמש ב-interactions_logger.log_interaction() במקום
def save_complete_interaction(chat_id: Union[str, int], telegram_message_id: Optional[str],
                              user_msg: str, bot_msg: str, messages_for_gpt: list,
                              gpt_results: Dict[str, Any], timing_data: Dict[str, float],
                              admin_notification: Optional[str] = None, 
                              gpt_e_counter: Optional[str] = None) -> bool:
    """
    🔥 **הועבר למערכת מרכזית**: interactions_logger.py
    פונקציה זו מועברת לפונקציה המרכזית עם כל השדות החדשים
    
    ⚠️ DEPRECATED: השתמש ב-interactions_logger.log_interaction() במקום
    """
    try:
        from interactions_logger import log_interaction
        
        return log_interaction(
            chat_id=chat_id,
            telegram_message_id=telegram_message_id,
            user_msg=user_msg,
            bot_msg=bot_msg,
            messages_for_gpt=messages_for_gpt,
            gpt_results=gpt_results,
            timing_data=timing_data,
            admin_notification=admin_notification,
            gpt_e_counter=gpt_e_counter
        )
        
    except Exception as e:
        handle_database_error("save", chat_id, "interaction")
        return False

# 🔥 **הועבר למערכת מרכזית**: interactions_logger.py
# השתמש ב-interactions_logger.ensure_table_schema() במקום
def create_interactions_log_table(cursor):
    """
    🔥 **הועבר למערכת מרכזית**: interactions_logger.py
    ⚠️ DEPRECATED: השתמש ב-interactions_logger.ensure_table_schema() במקום
    """
    try:
        from interactions_logger import get_interactions_logger
        logger = get_interactions_logger()
        logger.ensure_table_schema()
        print("✅ [DB] יצירת טבלת interactions_log הושלמה (מועבר למערכת מרכזית)")
    except Exception as e:
        print(f"❌ [DB] שגיאה ביצירת טבלת interactions_log: {e}")
        # fallback - יצירה בסיסית
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions_log (
                serial_number SERIAL PRIMARY KEY,
                telegram_message_id TEXT,
                chat_id BIGINT,
                full_system_prompts TEXT,
                user_msg TEXT,
                bot_msg TEXT,
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        print("✅ [DB] יצירת טבלת interactions_log בסיסית הושלמה")

# =================================
# 🚨 פונקציות שמירת שגיאות
# =================================

def save_bot_error_log(error_type: str, error_message: str, chat_id: Optional[str] = None,
                       user_message: Optional[str] = None, error_data: Optional[Dict] = None) -> bool:
    """
    שמירת שגיאת בוט - הפונקציה המרכזית
    
    Args:
        error_type: סוג השגיאה
        error_message: הודעת השגיאה
        chat_id: מזהה צ'אט
        user_message: הודעת המשתמש
        error_data: נתוני השגיאה הנוספים
        
    Returns:
        bool: True אם הצליח, False אם נכשל
    """
    try:
        if chat_id:
            chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # יצירת טבלה אם לא קיימת
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_error_logs (
                    id SERIAL PRIMARY KEY,
                    error_type VARCHAR(100),
                    error_message TEXT,
                    chat_id TEXT,
                    user_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # הכנסת הנתונים
            cur.execute("""
                INSERT INTO bot_error_logs (error_type, error_message, chat_id, user_message, error_data)
                VALUES (%s, %s, %s, %s, %s)
            """, (error_type, error_message, chat_id, user_message, json.dumps(error_data) if error_data else None))
            
            conn.commit()
            cur.close()
            
            if should_log_debug_prints():
                print(f"🚨 [DB] שגיאת {error_type} נשמרה עבור chat_id={chat_id}")
            
            return True
            
    except Exception as e:
        print(f"❌ שגיאה בשמירת שגיאת בוט: {e}")
        return False

def save_bot_trace_log(chat_id: str, bot_message: str, trace_data: Dict) -> bool:
    """
    שמירת trace בוט - הפונקציה המרכזית
    
    Args:
        chat_id: מזהה צ'אט
        bot_message: הודעת הבוט
        trace_data: נתוני ה-trace
        
    Returns:
        bool: True אם הצליח, False אם נכשל
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # יצירת טבלה אם לא קיימת
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_trace_logs (
                    id SERIAL PRIMARY KEY,
                    chat_id TEXT,
                    bot_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    trace_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # הכנסת הנתונים
            cur.execute("""
                INSERT INTO bot_trace_logs (chat_id, bot_message, trace_data)
                VALUES (%s, %s, %s)
            """, (chat_id, bot_message, json.dumps(trace_data)))
            
            conn.commit()
            cur.close()
            
            if should_log_debug_prints():
                print(f"🔍 [DB] trace נשמר עבור chat_id={chat_id}")
            
            return True
            
    except Exception as e:
        print(f"❌ שגיאה בשמירת trace בוט: {e}")
        return False

# =================================
# 📊 פונקציות משתמשים
# =================================

def register_user_with_code(chat_id: str, code_input: Optional[str] = None) -> Dict[str, Any]:
    """
    רישום משתמש עם קוד - הפונקציה המרכזית
    
    Args:
        chat_id: מזהה צ'אט
        code_input: קוד אישור
        
    Returns:
        Dict: {"success": bool, "message": str, "attempt_num": int}
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            if code_input is None:
                # יצירת שורה זמנית למשתמש חדש
                cur.execute("SELECT chat_id FROM user_profiles WHERE chat_id = %s", (chat_id,))
                existing = cur.fetchone()
                
                if existing:
                    return {"success": True, "message": "משתמש כבר קיים", "attempt_num": 0}
                
                cur.execute("""
                    INSERT INTO user_profiles (chat_id, code_try, approved, updated_at) 
                    VALUES (%s, 0, FALSE, %s)
                """, (chat_id, get_israel_time()))
                
                conn.commit()
                cur.close()
                
                return {"success": True, "message": "נוצרה שורה זמנית", "attempt_num": 0}
            else:
                # בדיקת קוד ומיזוג
                code_input = str(code_input).strip()
                
                cur.execute("BEGIN")
                
                # בדיקת קוד
                cur.execute("SELECT chat_id, code_try FROM user_profiles WHERE code_approve = %s", (code_input,))
                code_row = cur.fetchone()
                
                if not code_row:
                    # הגדלת מונה ניסיונות
                    cur.execute("""
                        UPDATE user_profiles 
                        SET code_try = code_try + 1, updated_at = %s 
                        WHERE chat_id = %s
                    """, (datetime.utcnow(), chat_id))
                    
                    cur.execute("SELECT code_try FROM user_profiles WHERE chat_id = %s", (chat_id,))
                    attempt_result = cur.fetchone()
                    attempt_num = attempt_result[0] if attempt_result else 1
                    
                    conn.commit()
                    cur.close()
                    
                    return {"success": False, "message": "קוד לא קיים", "attempt_num": attempt_num}
                
                existing_chat_id, existing_code_try = code_row
                
                if existing_chat_id and existing_chat_id != chat_id:
                    # קוד תפוס
                    cur.execute("""
                        UPDATE user_profiles 
                        SET code_try = code_try + 1, updated_at = %s 
                        WHERE chat_id = %s
                    """, (datetime.utcnow(), chat_id))
                    
                    cur.execute("SELECT code_try FROM user_profiles WHERE chat_id = %s", (chat_id,))
                    attempt_result = cur.fetchone()
                    attempt_num = attempt_result[0] if attempt_result else 1
                    
                    conn.commit()
                    cur.close()
                    
                    return {"success": False, "message": "קוד תפוס", "attempt_num": attempt_num}
                
                # קוד תקין - מיזוג
                cur.execute("DELETE FROM user_profiles WHERE chat_id = %s", (chat_id,))
                cur.execute("""
                    UPDATE user_profiles 
                    SET chat_id = %s, updated_at = %s 
                    WHERE code_approve = %s
                """, (chat_id, get_israel_time(), code_input))
                
                conn.commit()
                cur.close()
                
                return {"success": True, "message": "קוד תקין", "attempt_num": 0}
                
    except Exception as e:
        print(f"❌ שגיאה ב-register_user_with_code: {e}")
        return {"success": False, "message": f"שגיאה: {e}", "attempt_num": 0}

def approve_user(chat_id: str) -> Dict[str, Any]:
    """
    אישור משתמש - הפונקציה המרכזית
    
    Args:
        chat_id: מזהה צ'אט
        
    Returns:
        Dict: {"success": bool, "message": str}
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE user_profiles 
                SET approved = TRUE, updated_at = %s 
                WHERE chat_id = %s
            """, (get_israel_time(), chat_id))
            
            success = cur.rowcount > 0
            
            conn.commit()
            cur.close()
            
            message = "אישור הצליח" if success else "אישור נכשל"
            
            if should_log_debug_prints():
                print(f"✅ [DB] אישור משתמש {chat_id}: {message}")
            
            return {"success": success, "message": message}
            
    except Exception as e:
        print(f"❌ שגיאה ב-approve_user: {e}")
        return {"success": False, "message": f"שגיאה: {e}"}

def increment_user_message_count(chat_id: str) -> bool:
    """
    הגדלת מונה הודעות משתמש - הפונקציה המרכזית
    
    Args:
        chat_id: מזהה צ'אט
        
    Returns:
        bool: True אם הצליח, False אם נכשל
    """
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # ספירת הודעות אמיתית
            cur.execute("SELECT COUNT(*) FROM chat_messages WHERE chat_id = %s", (chat_id,))
            actual_count = cur.fetchone()[0]
            
            # בדיקת פרופיל קיים
            cur.execute("SELECT total_messages_count FROM user_profiles WHERE chat_id = %s", (chat_id,))
            result = cur.fetchone()
            
            if result:
                # עדכון מונה למספר האמיתי
                cur.execute("""
                    UPDATE user_profiles 
                    SET total_messages_count = %s, updated_at = %s 
                    WHERE chat_id = %s
                """, (actual_count, get_israel_time(), chat_id))
                
                if should_log_debug_prints():
                    old_count = result[0] if result[0] is not None else 0
                    print(f"📊 [DB] מונה הודעות עודכן עבור {chat_id}: {old_count} → {actual_count}")
            else:
                # יצירת פרופיל חדש
                insert_data = {'chat_id': chat_id, 'total_messages_count': actual_count}
                for field in get_user_profile_fields():
                    if field != 'total_messages_count':
                        insert_data[field] = None
                
                insert_data['updated_at'] = get_israel_time()
                
                fields = list(insert_data.keys())
                placeholders = ', '.join(['%s'] * len(fields))
                values = list(insert_data.values())
                
                insert_sql = f"""
                INSERT INTO user_profiles ({', '.join(fields)})
                VALUES ({placeholders})
                """
                
                cur.execute(insert_sql, values)
                
                if should_log_debug_prints():
                    print(f"📊 [DB] פרופיל חדש נוצר עם מונה הודעות {actual_count} עבור {chat_id}")
            
            conn.commit()
            cur.close()
            
            return True
            
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה בעדכון מונה הודעות עבור {chat_id}: {e}")
        return False

# =================================
# 🗂️ פונקציות אחרות
# =================================

def save_reminder_state(chat_id: str, reminder_info: Dict) -> bool:
    """שמירת מצב תזכורת"""
    try:
        chat_id = validate_chat_id(chat_id)
        
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reminder_states (
                    id SERIAL PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    last_activity TIMESTAMP,
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    reminder_count INTEGER DEFAULT 0,
                    state_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                INSERT INTO reminder_states (chat_id, last_activity, reminder_sent, reminder_count, state_data)
                VALUES (%s, %s, %s, %s, %s)
            """, (chat_id, reminder_info.get('last_activity'), reminder_info.get('reminder_sent', False),
                  reminder_info.get('reminder_count', 0), json.dumps(reminder_info)))
            
            conn.commit()
            cur.close()
            
            return True
            
    except Exception as e:
        print(f"❌ שגיאה בשמירת תזכורת {chat_id}: {e}")
        return False

def save_sync_queue_data(sync_data: Dict) -> bool:
    """שמירת נתוני תור סנכרון"""
    try:
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id SERIAL PRIMARY KEY,
                    queue_data JSONB,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                INSERT INTO sync_queue (queue_data)
                VALUES (%s)
            """, (json.dumps(sync_data),))
            
            conn.commit()
            cur.close()
            
            return True
            
    except Exception as e:
        print(f"❌ שגיאה בשמירת תור סנכרון: {e}")
        return False

def save_rollback_data(filename: str, rollback_data: Dict) -> bool:
    """שמירת נתוני rollback"""
    try:
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rollback_data (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255),
                    rollback_info JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                INSERT INTO rollback_data (filename, rollback_info)
                VALUES (%s, %s)
            """, (filename, json.dumps(rollback_data)))
            
            conn.commit()
            cur.close()
            
            return True
            
    except Exception as e:
        print(f"❌ שגיאה בשמירת נתוני rollback {filename}: {e}")
        return False

def save_temp_critical_user_data(filename: str, temp_data: Dict) -> bool:
    """שמירת נתוני קובץ זמני משתמש קריטי"""
    try:
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temp_critical_files (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255),
                    temp_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                INSERT INTO temp_critical_files (filename, temp_data)
                VALUES (%s, %s)
            """, (filename, json.dumps(temp_data)))
            
            conn.commit()
            cur.close()
            
            return True
            
    except Exception as e:
        print(f"❌ שגיאה בשמירת קובץ זמני {filename}: {e}")
        return False

# =================================
# 🛠️ פונקציות עזר
# =================================

def get_current_commit_hash() -> str:
    """קבלת hash הקומיט הנוכחי"""
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                               capture_output=True, text=True, timeout=TimeoutConfig.SUBPROCESS_TIMEOUT)
        return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"

# 🔥 **הועבר למערכת מרכזית**: interactions_logger.py
# השתמש ב-interactions_logger.*() במקום

def format_system_prompts(messages_for_gpt: list) -> str:
    """⚠️ DEPRECATED: השתמש ב-interactions_logger.format_system_prompts() במקום"""
    try:
        from interactions_logger import get_interactions_logger
        logger = get_interactions_logger()
        return logger.format_system_prompts(messages_for_gpt)
    except:
        # fallback
        system_prompts = []
        for msg in messages_for_gpt:
            if msg.get('role') == 'system':
                system_prompts.append(msg.get('content', ''))
        return '\n\n--- SYSTEM PROMPT SEPARATOR ---\n\n'.join(system_prompts)

def extract_gpt_data(gpt_type: str, gpt_result: Dict[str, Any]) -> Dict[str, Any]:
    """⚠️ DEPRECATED: השתמש ב-interactions_logger.extract_gpt_data() במקום"""
    try:
        from interactions_logger import get_interactions_logger
        logger = get_interactions_logger()
        return logger.extract_gpt_data(gpt_type, gpt_result)
    except:
        # fallback
        return {
            'activated': False,
            'reply': None,
            'model': None,
            'cost_agorot': None,
            'processing_time': None,
            'tokens_input': None,
            'tokens_output': None,
            'tokens_cached': 0
        }

def calculate_total_cost(gpt_results: Dict[str, Any]) -> Decimal:
    """⚠️ DEPRECATED: השתמש ב-interactions_logger.calculate_total_cost() במקום"""
    try:
        from interactions_logger import get_interactions_logger
        logger = get_interactions_logger()
        return logger.calculate_total_cost(gpt_results)
    except:
        # fallback
        total_agorot = Decimal('0')
        for gpt_type in ['a', 'b', 'c', 'd', 'e']:
            if gpt_type in gpt_results and gpt_results[gpt_type]:
                usage = gpt_results[gpt_type].get('usage', {})
                cost_ils = usage.get('cost_total_ils', 0)
                if cost_ils:
                    total_agorot += Decimal(str(cost_ils * 100))
        return total_agorot

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> Any:
    """ביצוע שאילתת SQL גנרית"""
    try:
        with safe_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            
            if fetch_one:
                result = cur.fetchone()
                cur.close()
                return result
            elif fetch_all:
                results = cur.fetchall()
                cur.close()
                return results
            else:
                conn.commit()
                cur.close()
                return True
                
    except Exception as e:
        handle_database_error("query", "system", query)
        return None

# =================================
# 🚀 יצירת טבלאות (אם לא קיימות)
# =================================

def create_all_tables():
    """יצירת כל הטבלאות הנדרשות"""
    try:
        with safe_db_connection() as conn:
            cur = conn.cursor()
            
            # טבלאות קריטיות
            create_chat_messages_table_only(cur)
            create_user_profiles_table(cur)
            create_interactions_log_table(cur)
            
            # 🗑️ REMOVED: system_metrics table creation disabled
            # כל המטריקות מטופלות דרך הלוגינג הרגיל
            
            conn.commit()
            cur.close()
            
            if should_log_debug_prints():
                print("✅ [DB] כל הטבלאות נוצרו בהצלחה")
            
            return True
            
    except Exception as e:
        print(f"❌ שגיאה ביצירת טבלאות: {e}")
        return False

# =================================
# 🎯 נקודת כניסה עיקרית
# =================================

if __name__ == "__main__":
    print("🗄️ database_operations.py - מאחד כל הכתיבה למסד נתונים")
    print("=" * 60)
    
    # בדיקת חיבור
    try:
        with safe_db_connection() as conn:
            print("✅ חיבור למסד נתונים הצליח")
    except Exception as e:
        print(f"❌ שגיאה בחיבור למסד נתונים: {e}")
    
    # יצירת טבלאות
    if create_all_tables():
        print("✅ כל הטבלאות מוכנות")
    else:
        print("❌ בעיה ביצירת טבלאות")
    
    print("\n🚀 database_operations.py מוכן לשימוש!") 