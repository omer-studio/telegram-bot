"""utils.py – core generic helpers

Chat-history utilities are now located in `chat_utils.py` and profile-related
helpers in `profile_utils.py`.  This slimmer file retains only the low-level
primitives that are widely used across the codebase and re-exports the moved
helpers to preserve backwards-compatibility.
"""

from __future__ import annotations

import importlib
import json
import logging
import traceback
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytz
from config import BOT_TRACE_LOG_PATH, should_log_debug_prints, CHAT_HISTORY_PATH, config

# === Global control flags ===
# If True – automatic admin notifications from `update_user_profile_fast` are disabled.
_disable_auto_admin_profile_notification: bool = False

__all__ = [
    "get_israel_time",
    "get_effective_time",
    "log_event_to_file",
    "handle_secret_command",
]


# ---------------------------------------------------------------------------
# 🕑  Time helpers
# ---------------------------------------------------------------------------

def get_israel_time():
    """Return the current time in Israel (Asia/Jerusalem)."""
    israel_tz = pytz.timezone("Asia/Jerusalem")
    return datetime.now(israel_tz)


def get_effective_time(return_type: str = "datetime"):
    """Return an *effective* time where the day starts at 05:00.

    Parameters
    ----------
    return_type : "datetime" | "date" | "night_check"
        • "datetime"  → `datetime` object (default)
        • "date"      → `date` object (day starts at 05:00)
        • "night_check" → bool – True if time is in the range 23:00-05:00
    """
    now = get_israel_time()

    if return_type == "night_check":
        return now.hour >= 23 or now.hour < 5

    # Day starts at 05:00
    effective = now - timedelta(days=1) if now.hour < 5 else now

    if return_type == "date":
        return effective.date()
    return effective  # datetime


# ---------------------------------------------------------------------------
# 📝  Logging helper
# ---------------------------------------------------------------------------

def log_event_to_file(event_data: Dict[str, Any], filename: Optional[str] = None):
    """Append `event_data` (as JSON) to the given log file adding a timestamp."""
    try:
        if filename is None:
            filename = BOT_TRACE_LOG_PATH
        event_data["timestamp"] = get_israel_time().isoformat()
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data, ensure_ascii=False) + "\n")
        if should_log_debug_prints():
            logging.debug(f"Log saved → {filename}")
    except Exception as exc:
        logging.error(f"Error writing log: {exc}")
        if should_log_debug_prints():
            print(traceback.format_exc())


# ---------------------------------------------------------------------------
# 🔐  Secret Commands - Admin Functions
# ---------------------------------------------------------------------------

SECRET_CODES = {  # קודים סודיים
    "#487chaCha2025": "clear_history",    # מחק היסטוריית שיח
    # 🗑️ עברנו למסד נתונים - הסרת קוד Google Sheets
    # "#512SheetBooM": "clear_sheets",      # היה מוחק מידע מגיליונות
    "#734TotalZap": "clear_all",          # מחק הכל (היסטוריה + מסד נתונים)
    "#999PerformanceCheck": "performance_info",  # מידע על ביצועים ומסד נתונים
    # 🗑️ עברנו למסד נתונים - הסרת קוד reset cache
    # "#888ResetCache": "reset_cache",      # היה מאפס cache של Google Sheets
}

def handle_secret_command(chat_id, user_msg):
    """טיפול בקודים סודיים לאדמין וניקוי"""
    action = SECRET_CODES.get(user_msg.strip())
    if not action:
        return False, None
    
    if action == "clear_history":
        cleared = clear_chat_history(chat_id)
        msg = "🗑️ כל ההיסטוריה שלך נמחקה!" if cleared else "⚠️לא נמצאה היסטוריה למחיקה."
        log_event_to_file({"event": "secret_command", "timestamp": get_israel_time().isoformat(), "chat_id": chat_id, "action": "clear_history", "result": cleared})
        _send_admin_secret_notification(f"🔑 הופעל קוד סודי למחיקת היסטוריה מצ'אט {chat_id}.")
        return True, msg
    
    # 🗑️ עברנו למסד נתונים - הסרת טיפול בclear_sheets
    # if action == "clear_sheets":
    #     deleted_sheet, deleted_state = clear_from_sheets(chat_id)
    #     msg = "🗑️ כל הגיליונות שלך נמחקו מהגיליונות!" if (deleted_sheet or deleted_state) else "⚠️לא נמצא מידע למחיקה מהגיליונות."
    #     log_event_to_file({"event": "secret_command", "timestamp": get_israel_time().isoformat(), "chat_id": chat_id, "action": "clear_sheets", "deleted_sheet": deleted_sheet, "deleted_state": deleted_state})
    #     _send_admin_secret_notification(f"🔑 הופעל קוד סודי למחיקת גיליונות מצ'אט {chat_id}.")
    #     return True, msg
    
    if action == "clear_all":
        cleared = clear_chat_history(chat_id)
        # 🗑️ עברנו למסד נתונים - אין צורך למחוק מגיליונות
        # deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        
        # מחיקה מהמסד נתונים
        from db_manager import clear_user_from_database
        db_cleared = clear_user_from_database(chat_id)
        
        msg = "💥 עשה הכל נמחק! (היסטוריה + מסד נתונים)" if (cleared or db_cleared) else "⚠️לא נמצא שום מידע למחיקה."
        log_event_to_file({"event": "secret_command", "timestamp": get_israel_time().isoformat(), "chat_id": chat_id, "action": "clear_all", "cleared_history": cleared, "db_cleared": db_cleared})
        _send_admin_secret_notification(f"🔑 הופעל קוד סודי למחיקת **הכל** מצ'אט {chat_id}.")
        return True, msg
    
    if action == "performance_info":
        try:
            from gpt_a_handler import get_filter_analytics
            from db_manager import get_chat_statistics
            
            filter_analytics = get_filter_analytics()
            db_stats = get_chat_statistics()
            
            msg = f"📊 **דוח ביצועים:**\n\n"
            msg += f"🗄️ **מסד נתונים PostgreSQL:**\n"
            msg += f"• הודעות כולל: {db_stats.get('total_messages', 0)}\n"
            msg += f"• צ'אטים פעילים: {db_stats.get('unique_chats', 0)}\n"
            msg += f"• עלות כוללת: ${db_stats.get('total_cost_usd', 0):.4f}\n\n"
            msg += f"🤖 **GPT Model Filter:**\n"
            msg += f"• סה החלטות: {filter_analytics.get('total_decisions', 0)}\n"
            msg += f"• שימוש מודל מתקדם: {filter_analytics.get('premium_usage', 0)}%\n"
            msg += f"• פילוח: {filter_analytics.get('percentages', {})}\n\n"
            msg += f"💡 **טיפים לשיפור ביצועים:**\n"
            msg += f"• מסד נתונים מהיר פי 10 מ-Google Sheets\n"
            msg += f"• המודל המהיר חוסך ~40% בעלויות\n"
            msg += f"• גישות מקבילות למסד ביצועים מעולים"
            
            _send_admin_secret_notification(f"📊 הופעל קוד סודי לדוח ביצועים מצ'אט {chat_id}.")
            return True, msg
        except Exception as e:
            return True, f"❌ שגיאה בהכנת דוח ביצועים: {e}"
    
    # 🗑️ עברנו למסד נתונים - הסרת טיפול ברeset_cache
    # if action == "reset_cache":
    #     try:
    #         from config import reset_sheets_cache
    #         reset_sheets_cache()
    #         msg = "🔄 Cache של Google Sheets אופס בהצלחה!\nהגישה הבאה תיקח קצת קוד."
    #         _send_admin_secret_notification(f"🔄 הופעל קוד סודי לאיפוס cache מצ'אט {chat_id}.")
    #         return True, msg
    #     except Exception as e:
    #         return True, f"❌ שגיאה באיפוס cache: {e}"

    return False, None

def clear_chat_history(chat_id):
    """מחק היסטורית צ'אט ספציפי"""
    path = CHAT_HISTORY_PATH
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if str(chat_id) in data:
            data.pop(str(chat_id))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        return False
    except Exception as e:
        logging.error(f"[ERROR-clear_chat_history] {e} | chat_id={chat_id}")
        log_event_to_file({"event": "clear_history_error", "chat_id": chat_id, "error": str(e)})
        return False

def clear_from_sheets(chat_id):
    """🗑️ עברנו למסד נתונים - פונקציה deprecated"""
    # 🗑️ במסד נתונים אין צורך למחוק - המידע נשמר בטוח יותר
    # הפונקציה נשארת לתאימות אחורה בלבד
    logging.info(f"🗑️ clear_from_sheets deprecated - using database for {chat_id}")
    return False, False  # לא בוצעה מחיקה - עברנו למסד נתונים

def _send_admin_secret_notification(message: str):
    """שולח הודעה לאדמין על שימוש בקוד סודי"""
    try:
        from notifications import send_admin_secret_command_notification
        send_admin_secret_command_notification(message)
    except Exception as e:
        logging.error(f"🚨 שגיאה בשליחת התראת קוד סודי: {e}")


# ---------------------------------------------------------------------------
# 🔄  Re-export high-level helpers from the dedicated sub-modules
# ---------------------------------------------------------------------------
for _module_name in ("chat_utils", "profile_utils"):
    _mod = importlib.import_module(_module_name)
    for _name in getattr(_mod, "__all__", []):
        globals()[_name] = getattr(_mod, _name)
        __all__.append(_name)


# ---------------------------------------------------------------------------
# 🛠️  Utility functions for debugging and development
# ---------------------------------------------------------------------------

def show_log_status():
    """מציג את מצב הלוגים הקיים"""
    try:
        from config import (ENABLE_DEBUG_PRINTS, ENABLE_GPT_COST_DEBUG, 
                           ENABLE_PERFORMANCE_DEBUG, ENABLE_MESSAGE_DEBUG, 
                           ENABLE_DATA_EXTRACTION_DEBUG, DEFAULT_LOG_LEVEL)
        print(f"\n🔧 רמת לוגים: {DEFAULT_LOG_LEVEL}")
        print(f"🔍 דיבוג: {'כן' if ENABLE_DEBUG_PRINTS else 'לא'} | 💰 GPT: {'כן' if ENABLE_GPT_COST_DEBUG else 'לא'} | 📊 חילוץ נתונים: {'כן' if ENABLE_DATA_EXTRACTION_DEBUG else 'לא'}")
        print(f"⚡ ביצועים: {'כן' if ENABLE_PERFORMANCE_DEBUG else 'לא'} | 💬 הודעות: {'כן' if ENABLE_MESSAGE_DEBUG else 'לא'} | 🗄️ מסד נתונים: פעיל")
    except ImportError as e:
        print(f"❌ שגיאה בimport: {e}")
    except Exception as e:
        print(f"❌ שגיאה: {e}")

def show_gpt_input_examples():
    """דוגמאות למה ש-GPT מקבל בקלט"""
    print("📝 מבנה GPT: System + User Info + Context + 15 צורות הודעות + הודעה קודמת")

def show_personal_connection_examples():
    """דוגמאות לחיבור הקשר האישי"""
    print("🔗 חיבור קישור: נקודי 4+ שעות | משפחה (3+), לקח (2+), עבודה (3+) | צמיחה מיוחדת")


# ---------------------------------------------------------------------------
# 🚀  Command Line Interface
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "cleanup-test":
            from chat_utils import cleanup_test_users
            cleanup_test_users()
            print("✅ נמחקו משתמשי בדיקה")
        elif command == "log-status":
            show_log_status()
        elif command == "gpt-examples":
            show_gpt_input_examples()
        elif command == "connection-examples":
            show_personal_connection_examples()
        else:
            print(f"❌ לא מוכר את הפקודה: {command}")
            print("פקודות זמינות:")
            print("  cleanup-test - מחיקת משתמשי בדיקה")
            print("  log-status - מצב הלוגים")
            print("  gpt-examples - דוגמאות GPT")
            print("  connection-examples - דוגמאות חיבור")
    else:
        print("שימוש: python utils.py [cleanup-test|log-status|gpt-examples|connection-examples]")


