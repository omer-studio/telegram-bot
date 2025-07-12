#!/usr/bin/env python3
"""
simple_data_manager.py - המקום היחיד שמתחבר למסד נתונים
פשוט, עקבי, ותחזוקה קלה
"""

import psycopg2
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from simple_logger import logger
from user_friendly_errors import safe_str, safe_operation  
from user_friendly_errors import safe_int, handle_database_error
from simple_config import TimeoutConfig

# ייבוא הפונקציות המרכזיות מ-db_manager
from db_manager import create_chat_messages_table_only, insert_chat_message_only

# טעינת קונפיגורציה
try:
    from config import config
    DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
except ImportError:
    DB_URL = None


@contextmanager
def safe_db_connection():
    """
    🔒 Context Manager בטוח לחיבורי מסד נתונים
    מונע דליפות זיכרון ומוודא סגירה תמיד
    """
    conn = None
    try:
        if not DB_URL:
            raise Exception("No database URL found")
        
        conn = psycopg2.connect(DB_URL)
        yield conn
        
    except Exception as e:
        # במקרה של שגיאה - rollback אם יש transaction פעיל
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    finally:
        # תמיד סוגר את החיבור, גם במקרה של שגיאה
        if conn:
            try:
                conn.close()
            except:
                pass


class SimpleDataManager:
    """המקום היחיד שמתחבר למסד נתונים - פשוט ועקבי"""
    
    def __init__(self):
        self._connection = None
        self._last_used = None
        self._connection_timeout = TimeoutConfig.DATABASE_CONNECTION_TIMEOUT  # 🔧 תיקון מערכתי
    
    # ✅ הוסרה פונקציה deprecated _get_connection - כולם משתמשים בsafe_db_connection()
    
    def save_chat_message(self, chat_id: str, user_msg: str, bot_msg: str, 
                         timestamp: Optional[datetime] = None, **kwargs) -> bool:
        """שמירת הודעת צ'אט - משתמש בפונקציה המרכזית מ-db_manager"""
        try:
            with safe_db_connection() as conn:
                cur = conn.cursor()
                
                # יצירת טבלה אם לא קיימת - משתמש בפונקציה המרכזית
                create_chat_messages_table_only(cur)
                
                # הכנסת ההודעה - משתמש בפונקציה המרכזית
                insert_chat_message_only(cur, chat_id, user_msg, bot_msg, timestamp)
                
                conn.commit()
                cur.close()
                
                return True
                
        except Exception as e:
            handle_database_error("save", chat_id, user_msg)
            return False
    
    def get_chat_history(self, chat_id: str, limit: int = 100) -> List[Dict]:
        """קבלת היסטוריית צ'אט - פונקציה אחת פשוטה עם Context Manager בטוח"""
        try:
            with safe_db_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT user_msg, bot_msg, timestamp
                    FROM chat_messages 
                    WHERE chat_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT %s
                """, (chat_id, limit))
                
                results = cur.fetchall()
                cur.close()
                
                history = []
                for row in results:
                    history.append({
                        'user_msg': row[0],
                        'bot_msg': row[1],
                        'timestamp': row[2]
                    })
                
                return history
                
        except Exception as e:
            handle_database_error("load", chat_id, "")
            return []
    
    def save_user_profile(self, chat_id: str, profile_data: Dict[str, Any]) -> bool:
        """שמירת פרופיל משתמש - פונקציה אחת פשוטה עם Context Manager בטוח"""
        try:
            with safe_db_connection() as conn:
                cur = conn.cursor()
                
                # יצירת טבלה אם לא קיימת
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        id SERIAL PRIMARY KEY,
                        chat_id TEXT UNIQUE NOT NULL,
                        profile_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
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
                        INSERT INTO user_profiles (chat_id, profile_data)
                        VALUES (%s, %s)
                    """, (chat_id, json.dumps(profile_data)))
                
                conn.commit()
                cur.close()
                
                return True
                
        except Exception as e:
            handle_database_error("save", chat_id, "profile")
            return False
    
    def get_user_profile(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """קבלת פרופיל משתמש - פונקציה אחת פשוטה עם Context Manager בטוח"""
        try:
            with safe_db_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("SELECT profile_data FROM user_profiles WHERE chat_id = %s", (chat_id,))
                result = cur.fetchone()
                cur.close()
                
                if result and result[0]:
                    return json.loads(result[0])
                
                return None
                
        except Exception as e:
            handle_database_error("load", chat_id, "profile")
            return None
    
    def save_gpt_call(self, chat_id: str, call_type: str, request_data: Dict, 
                      response_data: Dict, tokens_input: int, tokens_output: int, 
                      cost_usd: float, processing_time: float) -> bool:
        """שמירת קריאת GPT - פונקציה אחת פשוטה עם Context Manager בטוח"""
        try:
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
                
                cur.execute("""
                    -- 🗑️ REMOVED: INSERT into gpt_calls disabled
    -- INSERT INTO gpt_calls (chat_id, call_type, request_data, response_data, 
                                         tokens_input, tokens_output, cost_usd, processing_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (chat_id, call_type, json.dumps(request_data), json.dumps(response_data),
                      tokens_input, tokens_output, cost_usd, processing_time))
                
                conn.commit()
                cur.close()
                
                return True
                
        except Exception as e:
            handle_database_error("save", chat_id, f"gpt_call_{call_type}")
            return False
    
    def execute_query(self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> Any:
        """ביצוע שאילתת SQL גנרית - לבדיקות ומקרים מיוחדים עם Context Manager בטוח"""
        try:
            with safe_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, params)
                
                if fetch_one:
                    result = cur.fetchone()
                    cur.close()
                    if result:
                        # Convert to dict if possible
                        columns = [desc[0] for desc in cur.description] if hasattr(cur, 'description') and cur.description else None
                        if columns and len(result) == len(columns):
                            return dict(zip(columns, result))
                        return {"result": result[0]} if len(result) == 1 else {"values": result}
                    return None
                elif fetch_all:
                    results = cur.fetchall()
                    cur.close()
                    return [{"table_name": row[0]} for row in results] if results else []
                else:
                    # For INSERT/UPDATE/DELETE - commit changes
                    conn.commit()
                    cur.close()
                    return True
                    
        except Exception as e:
            handle_database_error("query", "system", query)
            return None

    def update_user_profile_fast(self, chat_id: str, updates: Dict[str, Any]) -> bool:
        """עדכון מהיר של פרופיל משתמש - מיזוג עם הנתונים הקיימים"""
        try:
            # קבלת הפרופיל הקיים
            existing_profile = self.get_user_profile(chat_id) or {}
            
            # מיזוג העדכונים
            existing_profile.update(updates)
            
            # שמירה חזרה
            return self.save_user_profile(chat_id, existing_profile)
            
        except Exception as e:
            handle_database_error("update", chat_id, f"profile_updates_{list(updates.keys())}")
            return False

    def close(self):
        """סגירת חיבור למסד נתונים - לא נחוץ יותר עם Context Manager"""
        if self._connection:
            try:
                self._connection.close()
                logger.info("✅ חיבור למסד נתונים נסגר", source="data_manager")
            except Exception as e:
                logger.error(f"❌ שגיאה בסגירת חיבור: {e}", source="data_manager")

# יצירת מופע גלובלי
data_manager = SimpleDataManager() 