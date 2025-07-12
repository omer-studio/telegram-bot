#!/usr/bin/env python3
"""
🔥 Interactions Logger - מערכת רישום מלא לכל אינטראקציה
כל שורה = אינטראקציה מלאה עם כל הפרטים
"""
import sys
sys.path.append('.')
from config import get_config
import psycopg2
import subprocess
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Union
from utils import safe_str

class InteractionsLogger:
    """מחלקה לרישום מלא של כל אינטראקציה"""
    
    def __init__(self):
        self.config = get_config()
        self.db_url = self.config.get("DATABASE_EXTERNAL_URL") or self.config.get("DATABASE_URL")
        
    def get_current_commit_hash(self) -> str:
        """קבלת ה-commit hash הנוכחי"""
        try:
            from simple_config import TimeoutConfig
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                    capture_output=True, text=True, timeout=TimeoutConfig.SUBPROCESS_TIMEOUT)
            return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"
    
    def calculate_total_cost(self, gpt_results: Dict[str, Any]) -> Decimal:
        """חישוב עלות כוללת בשקלים עבור כל ה-GPTs"""
        total_agorot = Decimal('0')
        
        for gpt_type in ['a', 'b', 'c', 'd', 'e']:
            if gpt_type in gpt_results and gpt_results[gpt_type]:
                usage = gpt_results[gpt_type].get('usage', {})
                cost_ils = usage.get('cost_total_ils', 0)
                if cost_ils:
                    # המרה לאגורות (1 שקל = 100 אגורות)
                    total_agorot += Decimal(str(cost_ils * 100))
        
        return total_agorot
    
    def format_system_prompts(self, messages_for_gpt: list) -> str:
        """פורמט כל הסיסטם פרומטס באופן מלא"""
        system_prompts = []
        
        for msg in messages_for_gpt:
            if msg.get('role') == 'system':
                system_prompts.append(msg.get('content', ''))
        
        return '\n\n--- SYSTEM PROMPT SEPARATOR ---\n\n'.join(system_prompts)
    
    def extract_gpt_data(self, gpt_type: str, gpt_result: Dict[str, Any]) -> Dict[str, Any]:
        """חילוץ נתונים מתוצאת GPT"""
        if not gpt_result:
            return {
                'activated': False,
                'reply': None,
                'model': None,
                'cost_agorot': None,
                'processing_time': None,
                'tokens_input': None,
                'tokens_output': None,
                'tokens_cached': None
            }
        
        usage = gpt_result.get('usage', {})
        cost_ils = usage.get('cost_total_ils', 0)
        cost_agorot = Decimal(str(cost_ils * 100)) if cost_ils else None
        
        # זמן עיבוד - נחפש בכמה מקומות אפשריים
        processing_time = None
        for time_key in ['gpt_pure_latency', 'processing_time', 'latency']:
            if time_key in gpt_result:
                processing_time = gpt_result[time_key]
                break
        
        return {
            'activated': True,
            'reply': gpt_result.get('response', gpt_result.get('summary', gpt_result.get('extracted_fields', str(gpt_result)))),
            'model': gpt_result.get('model', 'unknown'),
            'cost_agorot': cost_agorot,
            'processing_time': processing_time,
            'tokens_input': usage.get('prompt_tokens', usage.get('input_tokens')),
            'tokens_output': usage.get('completion_tokens', usage.get('output_tokens')),
            'tokens_cached': usage.get('prompt_tokens_cached', usage.get('cached_tokens', 0))
        }

    def count_history_messages(self, messages_for_gpt: list) -> tuple:
        """
        ספירת הודעות משתמש ובוט בהיסטוריה בלבד (לא סיסטם פרומטים)
        
        Args:
            messages_for_gpt: כל ההודעות שנשלחו ל-GPT
            
        Returns:
            tuple: (user_count, bot_count) - מספר הודעות משתמש ובוט מההיסטוריה
        """
        if not messages_for_gpt:
            return (0, 0)
        
        # ספירת הודעות משתמש ובוט בלבד (לא system)
        user_count = len([msg for msg in messages_for_gpt if msg.get("role") == "user"])
        bot_count = len([msg for msg in messages_for_gpt if msg.get("role") == "assistant"])
        
        # הודעת המשתמש הנוכחית היא חלק מ-messages_for_gpt אבל לא חלק מההיסטוריה
        # אז נפחית 1 מספירת המשתמשים (ההודעה האחרונה היא הנוכחית)
        if user_count > 0:
            user_count -= 1
        
        return (user_count, bot_count)
    
    def log_complete_interaction(self, 
                                chat_id: Union[str, int],
                                telegram_message_id: Optional[str],
                                user_msg: str,
                                bot_msg: str,
                                messages_for_gpt: list,
                                gpt_results: Dict[str, Any],
                                timing_data: Dict[str, float],
                                admin_notification: Optional[str] = None,
                                gpt_e_counter: Optional[str] = None) -> Optional[int]:
        """
        רישום אינטראקציה מלאה לטבלה
        
        Args:
            chat_id: מזהה משתמש
            telegram_message_id: מזהה הודעה בטלגרם
            user_msg: הודעת המשתמש
            bot_msg: תשובת הבוט
            messages_for_gpt: כל ההודעות שנשלחו ל-GPT (כולל system prompts)
            gpt_results: תוצאות מכל ה-GPTs {'a': result, 'b': result, etc}
            timing_data: נתוני זמנים {'user_to_bot': X, 'total': Y, etc}
            admin_notification: תוכן ההתראה לאדמין
            gpt_e_counter: מונה GPT-E ("5/10")
            
        Returns:
            int: מזהה הרשומה (serial_number) או None אם כשל
        """
        
        if not self.db_url:
            print("❌ [InteractionsLogger] לא נמצא URL למסד הנתונים")
            return None
        
        # וידוא שהטבלה קיימת עם השדות החדשים
        if not self.ensure_table_schema():
            print("❌ [InteractionsLogger] כשל בעדכון מבנה הטבלה")
            return None
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            # הכנת נתונים בסיסיים
            now = datetime.utcnow()
            commit_hash = self.get_current_commit_hash()
            full_system_prompts = self.format_system_prompts(messages_for_gpt)
            
            # חילוץ נתוני GPT לכל סוג
            gpt_data = {}
            for gpt_type in ['a', 'b', 'c', 'd', 'e']:
                gpt_data[gpt_type] = self.extract_gpt_data(gpt_type, gpt_results.get(gpt_type))
            
            # חישוב עלות כוללת
            total_cost_agorot = self.calculate_total_cost(gpt_results)
            
            # חישוב זמני עיבוד
            user_to_bot_time = timing_data.get('user_to_bot', 0)
            total_time = timing_data.get('total', user_to_bot_time)
            background_time = max(0, total_time - user_to_bot_time)
            
            # ספירת הודעות היסטוריה
            history_user_count, history_bot_count = self.count_history_messages(messages_for_gpt)
            
            # הכנת SQL
            insert_sql = """
            INSERT INTO interactions_log (
                telegram_message_id, chat_id, full_system_prompts, user_msg, bot_msg,
                
                gpt_a_model, gpt_a_cost_agorot, gpt_a_processing_time, gpt_a_tokens_input, gpt_a_tokens_output, gpt_a_tokens_cached,
                
                gpt_b_activated, gpt_b_reply, gpt_b_model, gpt_b_cost_agorot, gpt_b_processing_time, 
                gpt_b_tokens_input, gpt_b_tokens_output, gpt_b_tokens_cached,
                
                gpt_c_activated, gpt_c_reply, gpt_c_model, gpt_c_cost_agorot, gpt_c_processing_time,
                gpt_c_tokens_input, gpt_c_tokens_output, gpt_c_tokens_cached,
                
                gpt_d_activated, gpt_d_reply, gpt_d_model, gpt_d_cost_agorot, gpt_d_processing_time,
                gpt_d_tokens_input, gpt_d_tokens_output, gpt_d_tokens_cached,
                
                gpt_e_activated, gpt_e_reply, gpt_e_model, gpt_e_cost_agorot, gpt_e_processing_time,
                gpt_e_tokens_input, gpt_e_tokens_output, gpt_e_tokens_cached, gpt_e_counter,
                
                timestamp, date_only, time_only, user_to_bot_response_time, background_processing_time,
                history_user_messages_count, history_bot_messages_count,
                
                total_cost_agorot, source_commit_hash, admin_notification_text
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s
            ) RETURNING serial_number
            """
            
            # הכנת הערכים
            values = (
                telegram_message_id,
                int(safe_str(chat_id)),
                full_system_prompts,
                user_msg,
                bot_msg,
                
                # GPT-A
                gpt_data['a']['model'],
                gpt_data['a']['cost_agorot'],
                gpt_data['a']['processing_time'],
                gpt_data['a']['tokens_input'],
                gpt_data['a']['tokens_output'],
                gpt_data['a']['tokens_cached'],
                
                # GPT-B
                gpt_data['b']['activated'],
                gpt_data['b']['reply'],
                gpt_data['b']['model'],
                gpt_data['b']['cost_agorot'],
                gpt_data['b']['processing_time'],
                gpt_data['b']['tokens_input'],
                gpt_data['b']['tokens_output'],
                gpt_data['b']['tokens_cached'],
                
                # GPT-C
                gpt_data['c']['activated'],
                gpt_data['c']['reply'],
                gpt_data['c']['model'],
                gpt_data['c']['cost_agorot'],
                gpt_data['c']['processing_time'],
                gpt_data['c']['tokens_input'],
                gpt_data['c']['tokens_output'],
                gpt_data['c']['tokens_cached'],
                
                # GPT-D
                gpt_data['d']['activated'],
                gpt_data['d']['reply'],
                gpt_data['d']['model'],
                gpt_data['d']['cost_agorot'],
                gpt_data['d']['processing_time'],
                gpt_data['d']['tokens_input'],
                gpt_data['d']['tokens_output'],
                gpt_data['d']['tokens_cached'],
                
                # GPT-E
                gpt_data['e']['activated'],
                gpt_data['e']['reply'],
                gpt_data['e']['model'],
                gpt_data['e']['cost_agorot'],
                gpt_data['e']['processing_time'],
                gpt_data['e']['tokens_input'],
                gpt_data['e']['tokens_output'],
                gpt_data['e']['tokens_cached'],
                gpt_e_counter,
                
                # זמנים
                now,
                now.date(),
                now.time(),
                user_to_bot_time,
                background_time,
                
                # היסטוריה
                history_user_count,
                history_bot_count,
                
                # מטאדאטה
                total_cost_agorot,
                commit_hash,
                admin_notification
            )
            
            cur.execute(insert_sql, values)
            serial_number = cur.fetchone()[0]
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ [InteractionsLogger] אינטראקציה #{serial_number} נרשמה בהצלחה")
            print(f"   💰 עלות כוללת: {total_cost_agorot:.2f} אגורות")
            print(f"   ⏱️ זמן תגובה: {user_to_bot_time:.2f}s | רקע: {background_time:.2f}s")
            print(f"   📊 היסטוריה: {history_user_count} משתמש + {history_bot_count} בוט")
            
            return serial_number
            
        except Exception as e:
            print(f"❌ [InteractionsLogger] שגיאה ברישום אינטראקציה: {e}")
            return None

    def log_simple_interaction(self, chat_id: Union[str, int], user_msg: str, bot_msg: str, 
                              telegram_message_id: Optional[str] = None) -> Optional[int]:
        """
        🔥 רישום אינטראקציה פשוטה (למשתמשים חדשים/לא מאושרים)
        
        Args:
            chat_id: מזהה משתמש  
            user_msg: הודעת המשתמש
            bot_msg: תשובת הבוט
            telegram_message_id: מזהה הודעה בטלגרם
            
        Returns:
            int: מזהה הרשומה (serial_number) או None אם כשל
        """
        
        if not self.db_url:
            print("❌ [InteractionsLogger] לא נמצא URL למסד הנתונים")
            return None
        
        # וידוא שהטבלה קיימת
        if not self.ensure_table_schema():
            print("❌ [InteractionsLogger] כשל בעדכון מבנה הטבלה")
            return None
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            now = datetime.utcnow()
            commit_hash = self.get_current_commit_hash()
            
            # רישום פשוט - רק השדות הבסיסיים
            insert_sql = """
            INSERT INTO interactions_log (
                telegram_message_id, chat_id, user_msg, bot_msg,
                timestamp, date_only, time_only, source_commit_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
            RETURNING serial_number
            """
            
            values = (
                telegram_message_id,
                int(safe_str(chat_id)),
                user_msg,
                bot_msg,
                now,
                now.date(),
                now.time(),
                commit_hash
            )
            
            cur.execute(insert_sql, values)
            serial_number = cur.fetchone()[0]
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ [InteractionsLogger] אינטראקציה פשוטה #{serial_number} נרשמה")
            return serial_number
            
        except Exception as e:
            print(f"❌ [InteractionsLogger] שגיאה ברישום אינטראקציה פשוטה: {e}")
            return None

    def ensure_table_schema(self):
        """וידוא שהטבלה קיימת עם השדות החדשים"""
        if not self.db_url:
            return False
        
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            # בדיקה אם הטבלה קיימת
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'interactions_log'
                )
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                # יצירת הטבלה מאפס
                create_table_sql = """
                CREATE TABLE interactions_log (
                    serial_number SERIAL PRIMARY KEY,
                    telegram_message_id TEXT,
                    chat_id BIGINT NOT NULL,
                    full_system_prompts TEXT,
                    user_msg TEXT NOT NULL,
                    bot_msg TEXT,
                    
                    gpt_a_model TEXT,
                    gpt_a_cost_agorot INTEGER,
                    gpt_a_processing_time DECIMAL(10,3),
                    gpt_a_tokens_input INTEGER,
                    gpt_a_tokens_output INTEGER,
                    gpt_a_tokens_cached INTEGER DEFAULT 0,
                    
                    gpt_b_activated BOOLEAN DEFAULT FALSE,
                    gpt_b_reply TEXT,
                    gpt_b_model TEXT,
                    gpt_b_cost_agorot INTEGER,
                    gpt_b_processing_time DECIMAL(10,3),
                    gpt_b_tokens_input INTEGER,
                    gpt_b_tokens_output INTEGER,
                    gpt_b_tokens_cached INTEGER DEFAULT 0,
                    
                    gpt_c_activated BOOLEAN DEFAULT FALSE,
                    gpt_c_reply TEXT,
                    gpt_c_model TEXT,
                    gpt_c_cost_agorot INTEGER,
                    gpt_c_processing_time DECIMAL(10,3),
                    gpt_c_tokens_input INTEGER,
                    gpt_c_tokens_output INTEGER,
                    gpt_c_tokens_cached INTEGER DEFAULT 0,
                    
                    gpt_d_activated BOOLEAN DEFAULT FALSE,
                    gpt_d_reply TEXT,
                    gpt_d_model TEXT,
                    gpt_d_cost_agorot INTEGER,
                    gpt_d_processing_time DECIMAL(10,3),
                    gpt_d_tokens_input INTEGER,
                    gpt_d_tokens_output INTEGER,
                    gpt_d_tokens_cached INTEGER DEFAULT 0,
                    
                    gpt_e_activated BOOLEAN DEFAULT FALSE,
                    gpt_e_reply TEXT,
                    gpt_e_model TEXT,
                    gpt_e_cost_agorot INTEGER,
                    gpt_e_processing_time DECIMAL(10,3),
                    gpt_e_tokens_input INTEGER,
                    gpt_e_tokens_output INTEGER,
                    gpt_e_tokens_cached INTEGER DEFAULT 0,
                    gpt_e_counter TEXT,
                    
                    timestamp TIMESTAMP DEFAULT NOW(),
                    date_only DATE,
                    time_only TIME,
                    user_to_bot_response_time DECIMAL(10,3),
                    background_processing_time DECIMAL(10,3),
                    history_user_messages_count INTEGER DEFAULT 0,
                    history_bot_messages_count INTEGER DEFAULT 0,
                    
                    total_cost_agorot INTEGER DEFAULT 0,
                    source_commit_hash TEXT,
                    admin_notification_text TEXT
                )
                """
                cur.execute(create_table_sql)
                print("✅ [InteractionsLogger] יצירת טבלת interactions_log הושלמה")
            else:
                # בדיקה אם השדות החדשים קיימים
                cur.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'interactions_log' 
                    AND column_name IN ('gpt_a_tokens_cached', 'gpt_b_tokens_cached', 
                                      'gpt_c_tokens_cached', 'gpt_d_tokens_cached', 'gpt_e_tokens_cached',
                                      'history_user_messages_count', 'history_bot_messages_count')
                """)
                existing_columns = [row[0] for row in cur.fetchall()]
                
                # הוספת עמודות חסרות
                required_columns = {
                    'gpt_a_tokens_cached': 'INTEGER DEFAULT 0',
                    'gpt_b_tokens_cached': 'INTEGER DEFAULT 0',
                    'gpt_c_tokens_cached': 'INTEGER DEFAULT 0',
                    'gpt_d_tokens_cached': 'INTEGER DEFAULT 0',
                    'gpt_e_tokens_cached': 'INTEGER DEFAULT 0',
                    'history_user_messages_count': 'INTEGER DEFAULT 0',
                    'history_bot_messages_count': 'INTEGER DEFAULT 0'
                }
                
                for col_name, col_type in required_columns.items():
                    if col_name not in existing_columns:
                        cur.execute(f"ALTER TABLE interactions_log ADD COLUMN {col_name} {col_type}")
                        print(f"✅ [InteractionsLogger] הוספת עמודה: {col_name}")
                
            conn.commit()
            cur.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ [InteractionsLogger] שגיאה בעדכון מבנה הטבלה: {e}")
            return False

# פונקציה נוחה לשימוש
_logger_instance = None

def get_interactions_logger() -> InteractionsLogger:
    """קבלת instance יחיד של הלוגר"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = InteractionsLogger()
    return _logger_instance

def log_interaction(**kwargs) -> Optional[int]:
    """פונקציה קצרה לרישום אינטראקציה"""
    logger = get_interactions_logger()
    return logger.log_complete_interaction(**kwargs)

def log_simple(chat_id: Union[str, int], user_msg: str, bot_msg: str, 
               telegram_message_id: Optional[str] = None) -> Optional[int]:
    """
    🔥 פונקציה נוחה לרישום אינטראקציה פשוטה
    
    Args:
        chat_id: מזהה משתמש  
        user_msg: הודעת המשתמש
        bot_msg: תשובת הבוט
        telegram_message_id: מזהה הודעה בטלגרם
        
    Returns:
        int: מזהה הרשומה (serial_number) או None אם כשל
    """
    logger = get_interactions_logger()
    return logger.log_simple_interaction(chat_id, user_msg, bot_msg, telegram_message_id)

if __name__ == "__main__":
    # בדיקה פשוטה של הלוגר
    print("🧪 בדיקת InteractionsLogger...")
    
    logger = InteractionsLogger()
    print(f"📋 Commit hash נוכחי: {logger.get_current_commit_hash()}")
    print(f"💾 חיבור מסד נתונים: {'✅' if logger.db_url else '❌'}")
    
    print("✅ הלוגר מוכן לשימוש!") 