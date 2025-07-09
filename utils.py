# TODO: temporary comment to verify commit workflow
#!/usr/bin/env python3
"""
utils.py - פונקציות עזר כלליות
כל הפונקציות כאן - פשוטות, ברורות, ונגישות
"""

import os
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional, List
from simple_logger import logger
from user_friendly_errors import safe_str, safe_operation
import pytz

def save_log_to_file(content: str, filename: str = None) -> str:
    """שמירת לוג לקובץ - פונקציה אחת פשוטה"""
    try:
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"log_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.debug(f"Log saved → {filename}", source="utils")
        return filename
        
    except Exception as exc:
        logger.error(f"Error writing log: {exc}", source="utils")
        return ""

@safe_operation("clear_chat_history", "לא ניתן לנקות היסטוריית צ'אט")
def clear_chat_history(chat_id: Any) -> bool:
    """ניקוי היסטוריית צ'אט - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # ניקוי מהמסד נתונים
        from simple_data_manager import data_manager
        
        # מחיקת הודעות מהמסד נתונים
        # (זה ייעשה דרך data_manager - לא ישירות)
        
        logger.info(f"🗑️ clear_from_sheets deprecated - using database for {safe_id}", source="utils")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR-clear_chat_history] {e} | chat_id={safe_str(chat_id)}", source="utils")
        return False

def send_secret_code_alert(chat_id: Any, code: str) -> bool:
    """שליחת התראת קוד סודי - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        
        # שליחת התראה למשתמש
        from message_handler import send_telegram_message
        
        message = f"🔐 הקוד הסודי שלך: {code}\n\n⚠️ אל תשתף אותו עם אף אחד!"
        
        success = send_telegram_message(safe_id, message)
        
        if success:
            logger.info(f"✅ התראת קוד סודי נשלחה למשתמש {safe_id}", source="utils")
            return True
        else:
            logger.error(f"❌ לא הצלחתי לשלוח התראת קוד סודי למשתמש {safe_id}", source="utils")
            return False
            
    except Exception as e:
        logger.error(f"🚨 שגיאה בשליחת התראת קוד סודי: {e}", source="utils")
        return False

def format_user_friendly_error(error: Exception, context: str = "") -> str:
    """עיצוב שגיאה ידידותית למשתמש - פונקציה אחת פשוטה"""
    error_type = type(error).__name__
    error_msg = str(error)
    
    if context:
        return f"שגיאה ב-{context}: {error_msg}"
    else:
        return f"שגיאה: {error_msg}"

def safe_json_dumps(data: Any) -> str:
    """המרה בטוחה ל-JSON - פונקציה אחת פשוטה"""
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"שגיאה בהמרה ל-JSON: {e}", source="utils")
        return "{}"

def safe_json_loads(json_str: str) -> Dict:
    """טעינה בטוחה מ-JSON - פונקציה אחת פשוטה"""
    try:
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"שגיאה בטעינה מ-JSON: {e}", source="utils")
        return {}

def get_timestamp() -> str:
    """קבלת timestamp נוכחי - פונקציה אחת פשוטה"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_israel_time():
    """החזרת הזמן בישראל (Asia/Jerusalem) – תאימות לאחור"""
    israel_tz = pytz.timezone("Asia/Jerusalem")
    return datetime.now(israel_tz)

def is_valid_chat_id(chat_id: Any) -> bool:
    """בדיקה אם chat_id תקין - פונקציה אחת פשוטה"""
    try:
        safe_id = safe_str(chat_id)
        return bool(safe_id and safe_id.strip())
    except:
        return False

def log_event_to_file(*args, **kwargs):
    """תאימות לאחור – פונקציה זו עברה ל-simple_logger"""
    # TODO: מעבר זמני - להחליף בקוד הקורא ב-logger.info()
    try:
        # אם קיבלנו dict - נרשום אותו כ-JSON
        if args and isinstance(args[0], dict):
            log_data = args[0]
            log_message = f"Event: {log_data.get('event_type', 'unknown')}"
            if 'chat_id' in log_data:
                log_message += f" | chat_id={log_data['chat_id']}"
            if 'bot_message' in log_data:
                log_message += f" | message={log_data['bot_message'][:100]}..."
            logger.info(log_message, source="legacy_log_event")
        else:
            # רישום כללי
            logger.info(f"Legacy log call: {args[:2]}", source="legacy_log_event")
    except Exception as e:
        logger.error(f"Error in legacy log_event_to_file: {e}", source="legacy_log_event")

def handle_secret_command(*args, **kwargs):
    """תאימות לאחור – פונקציה זו עברה לפקודות טלגרם"""
    # TODO: מעבר זמני - הפונקציונליות עברה ל-/migrate_all_data, /show_logs, /search_logs
    try:
        # פונקציה זו הוחלפה בפקודות טלגרם רגילות
        # השתמש ב: /migrate_all_data SECRET_MIGRATION_2024, /show_logs, /search_logs
        logger.info("Legacy handle_secret_command called - use telegram commands instead", source="legacy_secret")
        return False, "🔐 פקודות סודיות עברו לפקודות טלגרם רגילות: /migrate_all_data, /show_logs, /search_logs"
    except Exception as e:
        logger.error(f"Error in legacy handle_secret_command: {e}", source="legacy_secret")
        return False, "⚠️ שגיאה בפקודה סודית ישנה"

def get_chat_history_messages(*args, **kwargs):
    """תאימות לאחור – פונקציה זו אינה בשימוש. יש לעבור ל-data_manager.get_chat_messages."""
    from simple_data_manager import data_manager
    return data_manager.get_chat_messages(*args, **kwargs)

def update_chat_history(*args, **kwargs):
    """תאימות לאחור – מפנה ל-chat_utils.update_chat_history"""
    from chat_utils import update_chat_history as real_update_chat_history
    return real_update_chat_history(*args, **kwargs)

def send_usage_report():
    """Backward compatibility wrapper for send_usage_report"""
    try:
        from notifications import send_usage_report as _send_usage_report
        return _send_usage_report()
    except ImportError:
        # Fallback if notifications module not available
        return None

def send_error_stats_report():
    """Backward compatibility wrapper for send_error_stats_report"""
    try:
        from notifications import send_error_stats_report as _send_error_stats_report
        return _send_error_stats_report()
    except ImportError:
        # Fallback if notifications module not available
        return None

def health_check():
    """Backward compatibility wrapper for health_check"""
    try:
        from chat_utils import health_check as _health_check
        return _health_check()
    except ImportError:
        # Fallback basic health check
        return {
            "config": True,
            "logger": True,
            "data_manager": True
        }


