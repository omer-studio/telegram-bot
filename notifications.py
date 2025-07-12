"""מרכז התראות, שגיאות ודיווחים לאדמין."""
import json
import os
import re
import traceback
from simple_logger import logger
from user_friendly_errors import safe_str
import asyncio
try:
    import telegram
    TELEGRAM_AVAILABLE = True
except ImportError:
    # סביבת CI או הרצה בלי הספרייה – יוצר dummy minimal כדי שהבדיקות הסטטיות ירוצו
    class telegram:
        class Bot:
            def __init__(self, token):
                self.token = token
            async def get_chat(self, chat_id):
                raise Exception("Telegram not available")
        class error:
            class BadRequest(Exception):
                pass
    TELEGRAM_AVAILABLE = False
from datetime import datetime, timedelta
import requests
import pytz
from config import (
    ADMIN_NOTIFICATION_CHAT_ID, 
    ADMIN_BOT_TELEGRAM_TOKEN, 
    BOT_TRACE_LOG_PATH, 
    BOT_ERRORS_PATH, 
    MAX_LOG_LINES_TO_KEEP,
    ADMIN_CHAT_ID,
    BOT_TOKEN
)
from simple_config import TimeoutConfig
from utils import get_israel_time
from chat_utils import log_error_stat
from recovery_manager import add_user_to_recovery_list, get_users_needing_recovery, send_recovery_messages_to_all_users
import time

# ייבוא פונקציות התראות אדמין שהועברו לadmin_notifications.py
from admin_notifications import (
    send_admin_notification,
    send_admin_notification_raw,
    send_admin_alert
)

# 🔄 מסד נתונים במקום קבצים - תיקון מערכתי
# משתנה לתאימות לאחור - לא יעבוד יותר אבל נדרש לקוד ישן
CRITICAL_ERROR_USERS_FILE = "data/critical_error_users.json"  # DEPRECATED - כבר לא בשימוש

# 🔄 DEPRECATED: הועבר למודול recovery_manager.py
# פונקציה זו מיושנת - השתמש במודול recovery_manager

def _save_critical_error_users(users_data):
    """שומר רשימת משתמשים שקיבלו הודעות שגיאה קריטיות - מחליף למסד נתונים"""
    try:
        # הפונקציה הזו כבר לא נחוצה - הכל נשמר ישירות במסד נתונים
        # משאיר רק לתאימות לאחור
        print(f"ℹ️ _save_critical_error_users מושבת - הכל נשמר ישירות במסד נתונים")
        return True
        
    except Exception as e:
        logger.error(f"Error in deprecated _save_critical_error_users: {e}", source="notifications")
        print(f"🚨 שגיאה בפונקציה מושבתת _save_critical_error_users: {e}")
        return False

def _add_user_to_critical_error_list(chat_id: str, error_message: str, original_user_message: str = None):
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.add_user_to_recovery_list() במקום
    """
    return add_user_to_recovery_list(chat_id, error_message, original_user_message)

def safe_add_user_to_recovery_list(chat_id: str, error_context: str = "Unknown error", original_message: str = ""):
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.add_user_to_recovery_list() במקום
    """
    return add_user_to_recovery_list(chat_id, error_context, original_message)

async def _send_user_friendly_error_message(update, chat_id: str, original_message: str = None):
    """שולח הודעת שגיאה ידידותית למשתמש - רק פעם אחת!"""
    
    # מוודא שהמשתמש נרשם לרשימת התאוששות (אם יש צורך) אך ללא קריאה רקורסיבית
    try:
        safe_add_user_to_recovery_list(safe_str(chat_id), "user_friendly_error", original_message)
    except Exception as e:
        logger.error(f"Failed to add user {safe_str(chat_id)} to recovery list: {e}", source="notifications")

    log_error_stat("user_friendly_error")
    
    try:
        user_friendly_message = (
            "🙏 מתנצל, יש בעיה - הבוט כרגע לא עובד.\n\n"
            "נסה שוב מאוחר יותר, הודעתי הרגע לעומר והוא יטפל בזה בהקדם. 🔧\n\n"
            "אני אודיע לך ברגע שהכל יחזור לעבוד! 💚"
        )
        
        if update and hasattr(update, 'message') and hasattr(update.message, 'reply_text'):
            from message_handler import send_system_message
            await send_system_message(update, chat_id, user_friendly_message)
        else:
            # אם אין update זמין, ננסה לשלוח ישירות דרך bot API
            bot = telegram.Bot(token=BOT_TOKEN)
            await bot.send_message(chat_id=safe_str(chat_id), text=user_friendly_message)
        
        logger.info(f"Sent user-friendly error message to user {safe_str(chat_id)}", source="notifications")
        print(f"✅ הודעת שגיאה נשלחה בהצלחה למשתמש {safe_str(chat_id)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send user-friendly error message to {safe_str(chat_id)}: {e}", source="notifications")
        print(f"⚠️ שליחת הודעה נכשלה למשתמש {safe_str(chat_id)}, אבל המשתמש כבר נרשם לרשימת התאוששות")
        # 🔧 תיקון: ניסיון נוסף לרישום המשתמש אם השליחה נכשלה
        try:
            _add_user_to_critical_error_list(safe_str(chat_id), f"Message sending failed: {str(e)[:100]}", original_message)
        except Exception:
            pass  # לא נעצור את התהליך בגלל זה
        return False

async def send_recovery_messages_to_affected_users():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.send_recovery_messages_to_all_users() במקום
    """
    logger.warning("Using deprecated send_recovery_messages_to_affected_users - switch to recovery_manager.py", source="notifications")
    return await send_recovery_messages_to_all_users()

async def process_lost_message(original_message: str, chat_id: str) -> str:
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    """
    logger.info(f"process_lost_message called but deprecated for user {chat_id}", source="notifications")
    return ""

def clear_old_critical_error_users(days_old: int = 7):
    """מנקה משתמשים ישנים מרשימת השגיאות הקריטיות"""
    try:
        users_list = get_users_needing_recovery()
        # המרה לפורמט הישן לתאימות
        users_data = {user.get('chat_id'): user for user in users_list}
        current_time = get_israel_time()
        cleaned_users = {}
        
        for chat_id, user_info in users_data.items():
            try:
                error_time = datetime.fromisoformat(user_info["timestamp"])
                if hasattr(error_time, 'tzinfo') and error_time.tzinfo is None:
                    # אם אין timezone, נניח שזה זמן ישראל
                    import pytz
                    israel_tz = pytz.timezone('Asia/Jerusalem')
                    error_time = israel_tz.localize(error_time)
                
                days_diff = (current_time - error_time).days
                
                # שומר רק אם זה פחות מהמספר ימים הנדרש או שעדיין לא התאושש
                if days_diff < days_old or not user_info.get("recovered", False):
                    cleaned_users[safe_str(chat_id)] = user_info
                    
            except Exception as e:
                logger.error(f"Error processing user {safe_str(chat_id)} in cleanup: {e}", source="notifications")
                # במקרה של שגיאה, שומר את המשתמש
                cleaned_users[safe_str(chat_id)] = user_info
        
        _save_critical_error_users(cleaned_users)
        removed_count = len(users_data) - len(cleaned_users)
        
        if removed_count > 0:
            logger.info(f"Cleaned {removed_count} old critical error users", source="notifications")
        
        return removed_count
        
    except Exception as e:
        logger.error(f"Error in clear_old_critical_error_users: {e}", source="notifications")
        return 0

def write_deploy_commit_to_log(commit):
    """שומר commit של דפלוי בקובץ לוג."""
    log_file = BOT_TRACE_LOG_PATH
    with open(log_file, "a", encoding="utf-8") as f:
        entry = {
            "type": "deploy_commit",
            "commit": commit,
            "timestamp": get_israel_time().isoformat()
        }
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_last_deploy_commit_from_log():
    """מחזיר את ה-commit האחרון מהלוג."""
    log_file = BOT_TRACE_LOG_PATH
    if not os.path.exists(log_file):
        return None
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # מחפש מהסוף להתחלה
    for line in reversed(lines):
        try:
            data = json.loads(line)
            if data.get("type") == "deploy_commit":
                return data.get("commit")
        except Exception:
            continue
    return None


def emoji_or_na(value):
    return value if value and value != "N/A" else "🤷🏼"

def get_commit_7first(commit):
    if not commit or commit == "N/A":
        return "🤷🏼"
    return commit[:7]

def send_deploy_notification(success=True, error_message=None, deploy_duration=None):
    """שולח הודעה לאדמין על סטטוס דפלוי."""
    timestamp = get_israel_time().strftime('%Y-%m-%d %H:%M:%S')
    project = emoji_or_na(os.getenv('RENDER_SERVICE_NAME', None))
    environment = emoji_or_na(os.getenv('RENDER_ENVIRONMENT', None))
    user = emoji_or_na(os.getenv('USER', None))
    deploy_id = emoji_or_na(os.getenv('RENDER_DEPLOY_ID', None))
    git_commit = get_commit_7first(os.getenv('RENDER_GIT_COMMIT', None))
    # Retrieve commit message (subject line) with multiple fallbacks
    raw_commit_msg = os.getenv('RENDER_GIT_COMMIT_MESSAGE')
    git_commit_msg = None

    if raw_commit_msg and raw_commit_msg.strip():
        git_commit_msg = raw_commit_msg.split('\n')[0][:100]
    else:
        # Fallback: retrieve message for the *current* commit only (accurate data)
        commit_hash_for_lookup = os.getenv('RENDER_GIT_COMMIT')
        if commit_hash_for_lookup:
            try:
                import subprocess
                commit_msg_out = subprocess.check_output(
                    ["git", "show", "-s", "--format=%s", commit_hash_for_lookup],
                    text=True,
                    timeout=TimeoutConfig.TELEGRAM_SEND_TIMEOUT
                ).strip()
                if commit_msg_out:
                    git_commit_msg = commit_msg_out.split('\n')[0][:100]
            except Exception:
                git_commit_msg = None
        # If still None, we leave it unknown – no fake data
        pass

    # Final sanitisation
    if git_commit_msg and git_commit_msg.strip():
        git_commit_msg = emoji_or_na(git_commit_msg)
    else:
        git_commit_msg = "🤷🏼"
    current_commit = os.getenv('RENDER_GIT_COMMIT', None)
    previous_commit = get_last_deploy_commit_from_log()
    write_deploy_commit_to_log(current_commit)

    # --- DEBUG: הצגת כל משתני הסביבה הרלוונטיים אם חסר מזהה קומיט ---
    debug_env = ""
    if not git_commit or git_commit == "🤷🏼":
        debug_env_vars = []
        for k, v in os.environ.items():
            if any(prefix in k for prefix in ["GIT", "RENDER", "COMMIT", "SHA", "DEPLOY", "BRANCH", "ENV"]):
                debug_env_vars.append(f"{k}={v}")
        if debug_env_vars:
            debug_env = "\n\n[DEBUG ENV]\n" + "\n".join(debug_env_vars)

    if deploy_duration is not None:
        duration_str = f"⏳ {int(deploy_duration)} שניות"
    else:
        duration_str = "🤷🏼"

    url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"

    if previous_commit and previous_commit == current_commit:
        # לא התבצע דפלוי חדש!
        text = (
            f"❗️יתכן שהפריסה נכשלה! (לא בוצעה פריסה חדשה)\n"
            f"⏰ טיימסטמפ: {timestamp}\n"
            f"🔢 מזהה קומיט: {git_commit}\n"
            f"\nבדוק את הלוגים או פנה ל-Render!"
        )
    else:
        # פריסה חדשה הושלמה!
        if deploy_duration is not None:
            duration_str = f"⏳ {int(deploy_duration)} שניות"
        else:
            duration_str = "🤷🏼"
        # Build the message only with fields that have real values
        fields = []
        fields.append(f"⏰ טיימסטמפ: {timestamp}")
        if environment not in ["🤷🏼", None, "None"]:
            fields.append(f"🖥️ סביבת הפעלה: {environment}")
        if user not in ["🤷🏼", None, "None"]:
            fields.append(f"👤 יוזר: {user}")
        if deploy_id not in ["🤷🏼", None, "None"]:
            fields.append(f"🦓 מזהה דפלוי: {deploy_id}")
        if git_commit not in ["🤷🏼", None, "None"]:
            fields.append(f"🔢 מזהה קומיט: {git_commit}")
        if git_commit_msg not in ["🤷🏼", None, "None"]:
            fields.append(f"📝 שם קומיט: {git_commit_msg}")
        fields.append("\nלפרטים נוספים בדוק את הלוגים ב-Render.")
        
        # הוספת מידע על מסד הנתונים
        db_info = get_database_table_counts()
        fields.append(f"\n{db_info}")
        
        text = "אדמין יקר - ✅פריסה הצליחה והבוט שלך רץ !! איזה כיף !! 🚀\n\n" + "\n".join(fields)
        if debug_env:
            text += debug_env

    data = {
        "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
        "text": text
    }
    try:
        requests.post(url, data=data, timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT)
    except Exception as e:
        print(f"שגיאה בשליחת הודעת פריסה: {e}")


def send_error_notification(error_message: str, chat_id: str = None, user_msg: str = None, error_type: str = "general_error") -> None:
    """שולח הודעת שגיאה לאדמין."""
    log_error_stat(error_type)
    # מסנן טוקנים/סודות
    def sanitize(msg):
        msg = re.sub(r'(token|key|api|secret)[^\s\n\r:]*[:=][^\s\n\r]+', '[SECURE]', msg, flags=re.IGNORECASE)
        return msg
    if not isinstance(error_message, str):
        error_message = str(error_message)
    text = f"🚨 שגיאה קריטית בבוט:\n<pre>{sanitize(error_message)}</pre>"
    if chat_id:
        text += f"\nchat_id: {safe_str(chat_id)}"
    if user_msg:
        text += f"\nuser_msg: {user_msg[:200]}"
    try:
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload, timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT)
    except Exception as e:
        print(f"[ERROR] לא הצלחתי לשלוח שגיאה לאדמין: {e}")

def send_admin_notification_raw(message):
    """שולח הודעה גולמית לאדמין ללא עיבוד"""
    try:
        # בדיקת סביבת בדיקה
        if (os.environ.get("CI") == "1" or 
            os.environ.get("TESTING") == "1" or 
            os.environ.get("PYTEST_CURRENT_TEST") is not None):
            logger.info(f"📨 [ADMIN_RAW] בסביבת בדיקה, לא שולח הודעה גולמית לאדמין: {message}")
            return
            
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload, timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT)
    except Exception as e:
        print(f"[ERROR] לא הצלחתי לשלוח הודעה גולמית לאדמין: {e}")

# 🗑️ פונקציה זו הוחלפה ב-unified_profile_notifications.send_profile_update_notification

def log_error_to_file(error_data, send_telegram=True):
    """
    רושם שגיאות לקובץ נפרד ב-data וגם שולח טלגרם לאדמין (אם send_telegram=True).
    קלט: error_data (dict), send_telegram (bool)
    פלט: אין (שומר לוג)
    """
    try:
        # DEBUG הודעות הוסרו לטובת ביצועים
        error_file = BOT_ERRORS_PATH
        error_data["timestamp"] = get_israel_time().isoformat()
        # יצירה אוטומטית של הקובץ אם לא קיים
        if not os.path.exists(error_file):
            with open(error_file, "w", encoding="utf-8") as f:
                pass
        with open(error_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(error_data, ensure_ascii=False) + "\n")
        # מגביל ל־MAX_LOG_LINES_TO_KEEP שורות
        if os.path.exists(error_file):
            with open(error_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > MAX_LOG_LINES_TO_KEEP:
                # שמירה על MAX_LOG_LINES_TO_KEEP שורות אחרונות בלבד
                f.writelines(lines[-MAX_LOG_LINES_TO_KEEP:])
        print(f"📝 שגיאה נרשמה בקובץ: {error_file}")
        # --- שולח גם טלגרם עם פירוט ---
        if send_telegram:
            msg = (
                "🛑 שגיאה חדשה נרשמה בקובץ:\n\n"
                f"⏰ {error_data.get('timestamp', '')}\n"
                f"סוג שגיאה: {error_data.get('error_type', 'לא ידוע')}\n"
                f"פרטי שגיאה: {str(error_data.get('error', ''))[:300]}\n"
                f"משתמש: {error_data.get('chat_id', '')}\n"
                f"הודעה: {str(error_data.get('user_msg', ''))[:80]}\n"
            )
            url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
            data = {
                "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
                "text": msg
            }
            requests.post(url, data=data, timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT)
    except Exception as e:
        print(f"💥 שגיאה ברישום שגיאה לקובץ: {e}")


def send_startup_notification():
    """
    שולח הודעה כשהבוט מתחיל לרוץ
    """
    send_deploy_notification()

from telegram import Update # type: ignore

async def handle_critical_error(error, chat_id, user_msg, update: Update):
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py  
    השתמש ב-recovery_manager.add_user_to_recovery_list() במקום
    """
    add_user_to_recovery_list(chat_id, f"Critical error: {str(error)[:100]}", user_msg)
    logger.error(f"Critical error handled via recovery_manager for user {safe_str(chat_id)}: {error}", source="notifications")

def handle_non_critical_error(error, chat_id, user_msg, error_type):
    """
    מטפל בשגיאות לא קריטיות - שגיאות שלא מונעות מהבוט לעבוד
    """
    print(f"⚠️ שגיאה לא קריטית: {error}")
    log_error_stat(error_type)
    send_error_notification(
        error_message=error,
        chat_id=safe_str(chat_id),
        user_msg=user_msg,
        error_type=error_type
    )
    log_error_to_file({
        "error_type": error_type.lower().replace(" ", "_"),
        "error": str(error),
        "chat_id": safe_str(chat_id),
        "user_msg": user_msg,
        "critical": False
    })

def send_concurrent_alert(alert_type: str, details: dict):
    """
    שליחת התראות ספציפיות למערכת Concurrent Handling
    """
    try:
        if alert_type == "max_users_reached":
            message = (
                f"🔴 **התראת עומס מקסימלי**\n"
                f"👥 הגענו למספר המקסימלי של משתמשים: {details.get('active_users', 0)}/{details.get('max_users', 10)}\n"
                f"⏱️ זמן: {get_israel_time().strftime('%H:%M:%S')}\n"
                f"📊 זמן תגובה ממוצע: {details.get('avg_response_time', 0):.2f}s\n"
                f"🚫 משתמשים נדחו: {details.get('rejected_users', 0)}\n"
                f"📈 יש לשקול הגדלת MAX_CONCURRENT_USERS"
            )
        elif alert_type == "high_response_time":
            message = (
                f"⚠️ **התראת זמן תגובה גבוה**\n"
                f"⏱️ זמן תגובה ממוצע: {details.get('avg_response_time', 0):.2f}s\n"
                f"🎯 יעד: מתחת ל-4 שניות\n"
                f"👥 משתמשים פעילים: {details.get('active_users', 0)}\n"
                f"📊 שיעור שגיאות: {details.get('error_rate', 0):.1%}"
            )
        # 🗑️ עברנו למסד נתונים - הסרת התראות Google Sheets
        # elif alert_type == "sheets_queue_overflow":
        #     message = (
        #         f"🗂️ **התראת עומס Google Sheets**\n"
        #         f"📥 גודל תור: {details.get('queue_size', 0)}\n"
        #         f"⚡ פעולות לדקה: {details.get('operations_per_minute', 0)}\n"
        #         f"🚨 יש לבדוק אם Google Sheets מגיב כראוי"
        #     )
        elif alert_type == "concurrent_error":
            # 🔧 תיקון: הוספת פרטים ספציפיים ל-session timeout
            if details.get('component') == 'session_timeout':
                message = (
                    f"🚨 **Session Timeout - שגיאה קריטית**\n"
                    f"🔧 רכיב: {details.get('component', 'לא ידוע')}\n"
                    f"📝 שגיאה: {details.get('error', 'לא ידוע')}\n"
                    f"👤 משתמש: {details.get('chat_id', 'לא ידוע')}\n"
                    f"⏱️ משך: {details.get('duration', 0):.2f} שניות\n"
                    f"📊 שלב: {details.get('stage', 'לא ידוע')}\n"
                    f"🆔 הודעה: {details.get('message_id', 'לא ידוע')}\n"
                    f"🎯 מיקום בתור: {details.get('queue_position', 'לא ידוע')}\n"
                    f"⏰ זמן מקסימלי: {details.get('max_allowed_time', 45)} שניות\n"
                    f"🕐 זמן: {details.get('timestamp', get_israel_time().strftime('%d/%m/%Y %H:%M:%S'))}"
                )
            else:
                message = (
                    f"❌ **שגיאה במערכת Concurrent**\n"
                    f"🔧 רכיב: {details.get('component', 'לא ידוע')}\n"
                    f"📝 שגיאה: {details.get('error', 'לא ידוע')}\n"
                    f"👤 משתמש: {details.get('chat_id', 'לא ידוע')}\n"
                    f"⏰ זמן: {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}"
                )
        # 🗑️ עברנו למסד נתונים - הסרת התראות Google Sheets
        # elif alert_type == "queue_failure":
        #     message = (
        #         f"🔥 **כשל בתור Google Sheets**\n"
        #         f"📊 פעולות שנדחו: {details.get('dropped_operations', 0)}\n"
        #         f"🔄 סוג פעולה: {details.get('operation_type', 'לא ידוע')}\n"
        #         f"⚠️ נתונים עלולים להיאבד!"
        #     )
        elif alert_type == "memory_warning":
            message = (
                f"🧠 **התראת זיכרון**\n"
                f"📊 שימוש זיכרון: {details.get('rss_mb', 0):.1f}MB ({details.get('percent', 0):.1f}%)\n"
                f"💾 זיכרון זמין: {details.get('available_mb', 0):.1f}MB\n"
                f"⚠️ {details.get('error', 'בעיית זיכרון')}\n"
                f"🔧 יש לבדוק memory leaks"
            )
        else:
            message = f"🔔 התראת Concurrent: {alert_type}\n{details}"
        
        send_error_notification(message)
        print(f"[CONCURRENT_ALERT] {alert_type}: {message}")
        
    except Exception as e:
        print(f"[ERROR] Failed to send concurrent alert: {e}")

def send_recovery_notification(recovery_type: str, details: dict):
    """
    הודעת התאוששות מבעיות concurrent
    """
    try:
        if recovery_type == "system_recovered":
            message = (
                f"✅ **מערכת התאוששה**\n"
                f"👥 משתמשים פעילים: {details.get('active_users', 0)}\n"
                f"⏱️ זמן תגובה: {details.get('avg_response_time', 0):.2f}s\n"
                f"📊 המערכת פועלת כרגיל"
            )
        # 🗑️ עברנו למסד נתונים - הסרת התראות Google Sheets
        # elif recovery_type == "queue_cleared":
        #     message = (
        #         f"🧹 **תור Google Sheets נוקה**\n"
        #         f"📥 גודל תור חדש: {details.get('queue_size', 0)}\n"
        #         f"✅ המערכת פועלת כרגיל"
        #     )
        else:
            message = f"🔄 התאוששות: {recovery_type}\n{details}"
        
        send_error_notification(message)
        print(f"[RECOVERY] {recovery_type}: {message}")
        
    except Exception as e:
        print(f"[ERROR] Failed to send recovery notification: {e}")

# 🚨 מערכת התראות אדמין - הועברה לadmin_notifications.py

def alert_billing_issue(cost_usd, model_name, tier, daily_usage, monthly_usage, daily_limit, monthly_limit):
    """
    💰 התראה על בעיית תקציב
    """
    daily_percent = (daily_usage / daily_limit) * 100
    monthly_percent = (monthly_usage / monthly_limit) * 100
    
    alert_level = "info"
    
    if daily_usage >= daily_limit or monthly_usage >= monthly_limit:
        alert_level = "critical"
        message = f"""🚨 **חריגה ממגבלת תקציב!**

💰 **העלות הנוכחית:**
• עלות השימוש: ${cost_usd:.3f}
• מודל: {model_name} ({tier})

📊 **סטטוס תקציב:**
• יומי: ${daily_usage:.2f} / ${daily_limit:.2f} ({daily_percent:.1f}%)
• חודשי: ${monthly_usage:.2f} / ${monthly_limit:.2f} ({monthly_percent:.1f}%)

⚠️ **המערכת ממשיכה לעבוד** - המשתמשים לא הושפעו!"""
        
    elif daily_percent >= 80 or monthly_percent >= 80:
        alert_level = "warning"
        message = f"""⚠️ **מתקרב למגבלת תקציב**

💰 **השימוש האחרון:**
• עלות: ${cost_usd:.3f}
• מודל: {model_name} ({tier})

📊 **סטטוס תקציב:**
• יומי: ${daily_usage:.2f} / ${daily_limit:.2f} ({daily_percent:.1f}%)
• חודשי: ${monthly_usage:.2f} / ${monthly_limit:.2f} ({monthly_percent:.1f}%)

✅ המערכת עובדת תקין"""
        
    elif tier == "paid" and daily_percent >= 50:
        alert_level = "info"
        message = f"""📊 **דוח שימוש בתשלום**

💰 **השימוש האחרון:**
• עלות: ${cost_usd:.3f}
• מודל: {model_name} (בתשלום)

📊 **סטטוס תקציב:**
• יומי: ${daily_usage:.2f} / ${daily_limit:.2f} ({daily_percent:.1f}%)
• חודשי: ${monthly_usage:.2f} / ${monthly_limit:.2f} ({monthly_percent:.1f}%)"""
    else:
        # שימוש רגיל - לא צריך התראה
        return
    
    send_admin_alert(message, alert_level)

def alert_system_status(message, level="info"):
    """התראה כללית על סטטוס המערכת"""
    send_admin_alert(f"🤖 **סטטוס מערכת:**\n\n{message}", level)

# מערכת תזכורות עדינות

from datetime import timedelta

GENTLE_REMINDER_MESSAGE = "היי, רק רציתי לבדוק מה שלומך, מקווה שאתה בטוב. אין לחץ – פשוט רציתי להזכיר לך שאני כאן ואם בא לך לשתף אז... מה שלומך וזה?"
REMINDER_INTERVAL_HOURS = 24
REMINDER_STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "reminder_state.json")
_reminder_state = {}

def _load_reminder_state():
    """טוען מצב תזכורות מקובץ JSON."""
    global _reminder_state
    try:
        if os.path.exists(REMINDER_STATE_FILE):
            with open(REMINDER_STATE_FILE, 'r', encoding='utf-8') as f:
                _reminder_state = json.load(f)
                logger.debug(f"[REMINDER] Loaded {len(_reminder_state)} reminder states")
        else:
            _reminder_state = {}
            logger.debug(f"[REMINDER] No reminder state file found, starting fresh")
    except Exception as e:
        logger.error(f"[REMINDER] Error loading reminder state: {e}")
        _reminder_state = {}

def _save_reminder_state():
    """שומר מצב תזכורות לקובץ JSON."""
    try:
        # יצירת תיקיית data אם לא קיימת
        os.makedirs(os.path.dirname(REMINDER_STATE_FILE), exist_ok=True)
        
        with open(REMINDER_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_reminder_state, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"[REMINDER] Saved reminder state with {len(_reminder_state)} entries")
    except Exception as e:
        logger.error(f"[REMINDER] Error saving reminder state: {e}")

# ==================== פונקציות ממשק ====================

def mark_user_active(chat_id: str):
    """
    מסמן שמשתמש פעיל (קיבל הודעה) - איפוס טיימר התזכורת
    """
    global _reminder_state
    try:
        current_time = get_israel_time()
        _reminder_state[safe_str(chat_id)] = {
            "last_activity": current_time.isoformat(),
            "reminder_sent": False,
            "reminder_delayed": False,
            "inactive_since": None,
            # רק לדיבאג - נוכחות המשתמש
            "status": "active"
        }
        
        # שמירה מידית של המצב החדש
        _save_reminder_state()
        
        logger.debug(f"[REMINDER] User {safe_str(chat_id)} marked as active", source="notifications")
        
    except Exception as e:
        logger.error(f"[REMINDER] Error marking user {safe_str(chat_id)} as active: {e}", source="notifications")

def _is_allowed_time() -> bool:
    """בודק אם זה זמן מתאים לשליחת תזכורות (לא מאוחר בלילה)"""
    current_time = get_israel_time()
    return 8 <= current_time.hour < 22  # בין 8:00 ל-22:00

def _mark_reminder_delayed(chat_id: str) -> None:
    """מסמן שתזכורת נדחתה (בגלל שעה לא מתאימה)"""
    global _reminder_state
    if safe_str(chat_id) in _reminder_state:
        _reminder_state[safe_str(chat_id)]["reminder_delayed"] = True
        _save_reminder_state()
        logger.debug(f"[REMINDER] Reminder for user {safe_str(chat_id)} delayed due to time", source="notifications")

def _mark_reminder_sent(chat_id: str) -> None:
    """מסמן שתזכורת נשלחה"""
    global _reminder_state
    if safe_str(chat_id) in _reminder_state:
        _reminder_state[safe_str(chat_id)]["reminder_sent"] = True
        _reminder_state[safe_str(chat_id)]["reminder_delayed"] = False
        _save_reminder_state()

def _log_to_chat_history(chat_id: str) -> None:
    """רושם הודעת תזכורת להיסטוריה"""
    try:
        from chat_utils import log_chat_message
        log_chat_message(safe_str(chat_id), "תזכורת עדינה", "system", "gentle_reminder")
        logger.debug(f"[REMINDER] Chat history logged for user {safe_str(chat_id)}", source="notifications")
    except Exception as e:
        logger.error(f"[REMINDER] Error logging chat history for user {safe_str(chat_id)}: {e}", source="notifications")

async def send_gentle_reminder(chat_id: str) -> bool:
    """
    שולח תזכורת עדינה למשתמש
    מחזיר True אם נשלחה בהצלחה, False אחרת
    """
    try:
        # בדיקת תקינות המשתמש לפני שליחה
        is_valid = await validate_user_before_reminder(safe_str(chat_id))
        if not is_valid:
            logger.debug(f"[REMINDER] User {safe_str(chat_id)} is not valid for reminder", source="notifications")
            return False
        
        # שליחת ההודעה
        bot = telegram.Bot(token=BOT_TOKEN)
        await bot.send_message(
            chat_id=safe_str(chat_id),
            text=GENTLE_REMINDER_MESSAGE,
            parse_mode=None  # ללא עיבוד מיוחד
        )
        
        # סימון שהתזכורת נשלחה
        _mark_reminder_sent(safe_str(chat_id))
        
        # רישום להיסטוריה
        _log_to_chat_history(safe_str(chat_id))
        
        logger.info(f"[REMINDER] Gentle reminder sent to user {safe_str(chat_id)}", source="notifications")
        print(f"✅ [REMINDER] נשלחה תזכורת עדינה למשתמש {safe_str(chat_id)}")
        
        # התראה מוקטנת לאדמין (לא להציף)
        send_admin_notification(
            f"💌 תזכורת עדינה נשלחה למשתמש {safe_str(chat_id)[:8]}...",
            urgent=False
        )
        
        return True
        
    except telegram.error.BadRequest as e:
        logger.warning(f"[REMINDER] BadRequest sending reminder to {safe_str(chat_id)}: {e}", source="notifications")
        # משתמש חסם את הבוט או מחק את החשבון
        _mark_user_inactive(safe_str(chat_id))
        return False
        
    except Exception as e:
        logger.error(f"[REMINDER] Error sending gentle reminder to {safe_str(chat_id)}: {e}", source="notifications")
        return False

def _mark_user_inactive(chat_id: str) -> None:
    """מסמן משתמש כלא פעיל (בעיקר אם חסם את הבוט)"""
    global _reminder_state
    try:
        current_time = get_israel_time()
        _reminder_state[safe_str(chat_id)] = {
            "last_activity": _reminder_state.get(safe_str(chat_id), {}).get("last_activity"),
            "reminder_sent": False,
            "reminder_delayed": False,
            "inactive_since": current_time.isoformat(),
            "status": "inactive"
        }
        _save_reminder_state()
        logger.info(f"[REMINDER] User {safe_str(chat_id)} marked as inactive", source="notifications")
    except Exception as e:
        logger.error(f"[REMINDER] Error marking user {safe_str(chat_id)} as inactive: {e}", source="notifications")

def cleanup_inactive_users():
    """
    פונקציה עזר לניקוי משתמשים לא פעילים מקובץ ההיסטוריה.
    לשימוש ידני או בתחזוקה תקופתית.
    """
    try:
        from config import CHAT_HISTORY_PATH
        global _reminder_state
        
        if not os.path.exists(CHAT_HISTORY_PATH):
            logger.warning("[CLEANUP] Chat history file not found")
            return
        
        # טעינת נתונים
        with open(CHAT_HISTORY_PATH, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        _load_reminder_state()
        
        # רשימת משתמשים לא פעילים
        inactive_users = [chat_id for chat_id, state in _reminder_state.items() 
                         if state.get("user_inactive")]
        
        if not inactive_users:
            logger.info("[CLEANUP] No inactive users found")
            return
        
        # הסרה מההיסטוריה
        removed_count = 0
        for chat_id in inactive_users:
            if chat_id in history_data:
                del history_data[chat_id]
                removed_count += 1
                logger.info(f"[CLEANUP] Removed inactive user {chat_id} from chat history")
        
        # שמירה חזרה
        if removed_count > 0:
            with open(CHAT_HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[CLEANUP] ✅ Removed {removed_count} inactive users from chat history")
        else:
            logger.info("[CLEANUP] No users needed to be removed from chat history")
            
    except Exception as e:
        logger.error(f"[CLEANUP] Error cleaning up inactive users: {e}")

def auto_cleanup_old_users():
    """ניקוי אוטומטי של משתמשים ישנים"""
    try:
        now = utils.get_israel_time()
        
        # וידוא timezone awareness
        if now.tzinfo is None:
            import pytz
            israel_tz = pytz.timezone('Asia/Jerusalem')
            now = israel_tz.localize(now)
        
        # סף של 60 יום לניקוי
        cutoff_date = now - timedelta(days=60)
        
        cleanup_candidates = []
        
        # עבור על כל המשתמשים
        for chat_id, user_state in _reminder_state.items():
            try:
                last_contact_str = user_state.get("last_contact")
                if last_contact_str:
                    try:
                        # 🔧 תיקון: שימוש בפונקציה בטוחה
                        last_contact_time = None
                        if isinstance(last_contact_str, str):
                            try:
                                last_contact_time = datetime.fromisoformat(last_contact_str.replace("Z", "+00:00"))
                            except ValueError:
                                try:
                                    last_contact_time = datetime.strptime(last_contact_str, "%Y-%m-%d %H:%M:%S")
                                except ValueError:
                                    pass
                        elif isinstance(last_contact_str, datetime):
                            last_contact_time = last_contact_str
                        
                        if last_contact_time:
                            # וידוא timezone awareness
                            if last_contact_time.tzinfo is None:
                                import pytz
                                israel_tz = pytz.timezone('Asia/Jerusalem')
                                last_contact_time = israel_tz.localize(last_contact_time)
                            
                            if last_contact_time < cutoff_date:
                                cleanup_candidates.append((chat_id, "old_user"))
                    except (ValueError, TypeError) as e:
                        logger.debug(f"[AUTO_CLEANUP] Error parsing last_contact for {chat_id}: {e}")
                        cleanup_candidates.append((chat_id, "invalid_contact_time"))
                
                # בדיקת תזכורות שנשלחו מזמן
                if user_state.get("reminder_sent"):
                    reminder_time_str = user_state.get("sent_at")
                    if reminder_time_str:
                        try:
                            # 🔧 תיקון: שימוש בפונקציה בטוחה
                            reminder_time = None
                            if isinstance(reminder_time_str, str):
                                try:
                                    reminder_time = datetime.fromisoformat(reminder_time_str.replace("Z", "+00:00"))
                                except ValueError:
                                    try:
                                        reminder_time = datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M:%S")
                                    except ValueError:
                                        pass
                            elif isinstance(reminder_time_str, datetime):
                                reminder_time = reminder_time_str
                            
                            if reminder_time:
                                # וידוא timezone awareness
                                if reminder_time.tzinfo is None:
                                    import pytz
                                    israel_tz = pytz.timezone('Asia/Jerusalem')
                                    reminder_time = israel_tz.localize(reminder_time)
                                
                                days_since_reminder = (now - reminder_time).days
                                if days_since_reminder > 30:
                                    cleanup_candidates.append((chat_id, f"no_response_to_reminder_{days_since_reminder}_days"))
                        except (ValueError, TypeError) as e:
                            logger.debug(f"[AUTO_CLEANUP] Error parsing reminder time for {chat_id}: {e}")
                            pass
                            
            except ValueError:
                # זמן לא תקין - מועמד לניקוי
                cleanup_candidates.append((chat_id, "invalid_timestamp"))
        
        # סימון המשתמשים כלא פעילים
        marked_count = 0
        for chat_id, reason in cleanup_candidates:
            _reminder_state[safe_str(chat_id)] = {
                "user_inactive": True,
                "marked_inactive_at": now.isoformat(),
                "reason": f"auto_cleanup_{reason}"
            }
            marked_count += 1
            logger.info(f"[AUTO_CLEANUP] Marked user {chat_id} as inactive: {reason}")
        
        # שמירת מצב
        _save_reminder_state()
        
        if marked_count > 0:
            logger.info(f"[AUTO_CLEANUP] Marked {marked_count} users as inactive")
        
        return marked_count
        
    except Exception as e:
        logger.error(f"[AUTO_CLEANUP] Error during cleanup: {e}")
        return 0

async def validate_user_before_reminder(chat_id: str) -> bool:
    """
    בודק תקפות משתמש לפני שליחת תזכורת.
    מנסה לשלוח הודעת בדיקה עדינה או בודק מצב השיחה.
    """
    try:
        # בדיקה פשוטה - ניסיון לקבל מידע על הצ'אט
        bot = telegram.Bot(token=BOT_TOKEN)
        chat_info = await bot.get_chat(safe_str(chat_id))
        
        # אם הצלחנו לקבל מידע, המשתמש תקף
        return True
        
    except telegram.error.BadRequest as e:
        if "chat not found" in str(e).lower():
            # המשתמש לא קיים - מסמנים כלא פעיל
            _mark_user_inactive(safe_str(chat_id))
            logger.warning(f"[VALIDATION] User {safe_str(chat_id)} validation failed - marked inactive", source="notifications")
            return False
        else:
            # שגיאה אחרת - עדיין נותנים הזדמנות
            logger.warning(f"[VALIDATION] Validation error for {safe_str(chat_id)}: {e}", source="notifications")
            return True
    except Exception as e:
        # שגיאה כללית - עדיין נותנים הזדמנות
        logger.warning(f"[VALIDATION] Unexpected validation error for {safe_str(chat_id)}: {e}", source="notifications")
        return True

async def check_and_send_gentle_reminders():
    """בדיקה ושליחת תזכורות עדינות"""
    try:
        now = utils.get_israel_time()
        
        # וידוא timezone awareness
        if now.tzinfo is None:
            import pytz
            israel_tz = pytz.timezone('Asia/Jerusalem')
            now = israel_tz.localize(now)
        
        # בדיקת שעות מותרות
        if not _is_allowed_time():
            logger.debug("[REMINDER] Outside allowed hours", source="notifications")
            return 0
        
        # ניקוי אוטומטי
        await auto_cleanup_old_users()
        
        # רענון מצב התזכורות
        await _refresh_reminder_state()
        
        # מציאת מועמדים לתזכורת
        reminder_candidates = []
        
        for chat_id, user_state in _reminder_state.items():
            try:
                # דילוג על משתמשים לא פעילים
                if user_state.get("user_inactive", False):
                    continue
                
                # דילוג על משתמשים שכבר נשלחה להם תזכורת והם לא ענו
                if user_state.get("reminder_sent_waiting_response", False):
                    continue
                
                # בדיקת זמן מגע אחרון
                last_contact_str = user_state.get("last_contact")
                if not last_contact_str:
                    continue
                
                try:
                    # 🔧 תיקון: שימוש בפונקציה בטוחה
                    last_contact_time = None
                    if isinstance(last_contact_str, str):
                        try:
                            last_contact_time = datetime.fromisoformat(last_contact_str.replace("Z", "+00:00"))
                        except ValueError:
                            try:
                                last_contact_time = datetime.strptime(last_contact_str, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                pass
                    elif isinstance(last_contact_str, datetime):
                        last_contact_time = last_contact_str
                    
                    if last_contact_time:
                        # וידוא timezone awareness לשני התאריכים
                        if last_contact_time.tzinfo is None:
                            import pytz
                            israel_tz = pytz.timezone('Asia/Jerusalem')
                            last_contact_time = israel_tz.localize(last_contact_time)
                        
                        time_since_last = now - last_contact_time
                        hours_since = time_since_last.total_seconds() / 3600
                        
                        # ✅ בדיקה: האם עברו מספיק שעות
                        if time_since_last >= timedelta(hours=REMINDER_INTERVAL_HOURS):
                            logger.debug(f"[REMINDER] User {safe_str(chat_id)} needs reminder ({hours_since:.1f}h since last contact)", source="notifications")
                            
                            # ✨ בדיקת תקפות המשתמש לפני שליחת תזכורת
                            is_valid = await validate_user_before_reminder(safe_str(chat_id))
                            if not is_valid:
                                logger.debug(f"[REMINDER] User {safe_str(chat_id)} validation failed - skipping", source="notifications")
                                continue
                            
                            success = await send_gentle_reminder(safe_str(chat_id))
                            if success:
                                reminders_sent += 1
                        else:
                            logger.debug(f"[REMINDER] User {safe_str(chat_id)} too recent ({hours_since:.1f}h < {REMINDER_INTERVAL_HOURS}h)", source="notifications")
                            
                except ValueError as e:
                    logger.warning(f"[REMINDER] Invalid timestamp for user {safe_str(chat_id)}: {last_contact_str}", source="notifications")
                    continue
                    
            except Exception as user_error:
                logger.warning(f"[REMINDER] Error checking user {safe_str(chat_id)}: {user_error}", source="notifications")
                continue
        
        logger.info(f"[REMINDER] Sent {reminders_sent} gentle reminders", source="notifications")
        return reminders_sent
        
    except Exception as e:
        logger.error(f"[REMINDER] Error in check_and_send_gentle_reminders: {e}", source="notifications")
        return 0

async def gentle_reminder_background_task():
    """משימת רקע לבדיקת תזכורות כל שעה + ניקוי אוטומטי שבועי."""
    logger.info("[REMINDER] 🚀 Starting gentle reminder background task", source="notifications")
    
    # 📂 טעינת מצב התזכורות בהתחלה
    _load_reminder_state()
    
    # מונה לניקוי שבועי (168 שעות = שבוע)
    hours_counter = 0
    
    # 🔄 לולאה אינסופית לבדיקה כל שעה
    while True:
        try:
            logger.debug("[REMINDER] Running hourly reminder check...", source="notifications")
            await check_and_send_gentle_reminders()
            
            # ניקוי אוטומטי פעם בשבוע (כל 168 שעות)
            hours_counter += 1
            if hours_counter >= 168:  # שבוע
                logger.info("[REMINDER] 🧹 Running weekly auto cleanup...", source="notifications")
                try:
                    auto_cleanup_old_users()
                    logger.info("[REMINDER] ✅ Weekly auto cleanup completed", source="notifications")
                except Exception as cleanup_error:
                    logger.error(f"[REMINDER] ❌ Weekly cleanup failed: {cleanup_error}", source="notifications")
                hours_counter = 0  # איפוס המונה
            
            # ⏰ המתנה של שעה עד הבדיקה הבאה
            logger.debug("[REMINDER] ⏱️ Waiting 1 hour until next check...", source="notifications")
            await asyncio.sleep(3600)  # 3600 שניות = שעה
            
        except Exception as e:
            error_msg = f"[REMINDER] ❌ Error in background task: {e}"
            logger.error(error_msg, source="notifications")
            
            # 🛡️ ממשיך לרוץ גם אחרי שגיאה
            logger.info("[REMINDER] 🔄 Continuing background task despite error...", source="notifications")
            await asyncio.sleep(3600)  # ממתין שעה גם במקרה של שגיאה

def diagnose_critical_users_system():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    """
    users = get_users_needing_recovery()
    print(f"📊 דוח מערכת התאוששות: {len(users)} משתמשים דורשים התאוששות")
    return {"total_users": len(users), "status": "OK"}

def manual_add_critical_user(chat_id: str, error_context: str = "Manual addition"):
    """הוספה ידנית של משתמש לרשימת משתמשים קריטיים - לשימוש חירום"""
    try:
        print(f"🔧 הוספה ידנית של משתמש {chat_id} לרשימת התאוששות...")
        _add_user_to_critical_error_list(safe_str(chat_id), f"Manual: {error_context}")
        print(f"✅ משתמש {safe_str(chat_id)} נוסף בהצלחה לרשימת התאוששות")
        
        # אימות שההוספה הצליחה
        try:
            from recovery_manager import get_users_needing_recovery
            users_list = get_users_needing_recovery()
            users_data = {user.get('chat_id'): user for user in users_list}
        except ImportError:
            users_data = {}
        
        if safe_str(chat_id) in users_data:
            print(f"✅ אומת: משתמש {safe_str(chat_id)} נמצא ברשימה")
            send_admin_notification(f"✅ הוספה ידנית הצליחה: משתמש {safe_str(chat_id)} נוסף לרשימת התאוששות")
            return True
        else:
            print(f"⚠️ משתמש {safe_str(chat_id)} לא נמצא ברשימה אחרי ההוספה!")
            send_admin_notification(f"⚠️ הוספה ידנית נכשלה: משתמש {safe_str(chat_id)} לא נמצא ברשימה", urgent=True)
            return False
            
    except Exception as e:
        error_msg = f"🚨 שגיאה בהוספה ידנית של משתמש {safe_str(chat_id)}: {e}"
        print(error_msg)
        send_admin_notification(error_msg, urgent=True)
        return False

def get_database_table_counts():
    """מקבל מידע על מספר השורות בכל טבלה במסד הנתונים עם השוואה לפריסה הקודמת"""
    try:
        import psycopg2
        import json
        import os
        from config import config
        
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        if not db_url:
            return "❌ לא נמצא חיבור למסד הנתונים"
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # קבלת רשימת כל הטבלאות
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        
        # קבלת מספר השורות בכל טבלה
        table_counts = {}
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                table_counts[table] = count
            except Exception as e:
                table_counts[table] = f"שגיאה: {str(e)[:50]}"
        
        cur.close()
        conn.close()
        
        # טעינת נתונים מהפריסה הקודמת
        previous_counts = {}
        try:
            db_stats_file = "data/last_db_stats.json"
            if os.path.exists(db_stats_file):
                with open(db_stats_file, 'r', encoding='utf-8') as f:
                    previous_counts = json.load(f)
        except Exception:
            pass
        
        # חישוב השינויים
        changes = {}
        for table, current_count in table_counts.items():
            if isinstance(current_count, int) and table in previous_counts:
                previous_count = previous_counts[table]
                change = current_count - previous_count
                if change != 0:  # רק שינויים
                    changes[table] = {
                        'current': current_count,
                        'previous': previous_count,
                        'change': change,
                        'change_percent': (change / previous_count * 100) if previous_count > 0 else 0
                    }
        
        # שמירת הנתונים הנוכחיים לפריסה הבאה
        try:
            os.makedirs(os.path.dirname(db_stats_file), exist_ok=True)
            with open(db_stats_file, 'w', encoding='utf-8') as f:
                json.dump(table_counts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        # יצירת הודעה מעוצבת
        if not table_counts:
            return "❌ לא נמצאו טבלאות במסד הנתונים"
        
        # 📊 כותרת ראשית
        message = "📊 **סטטוס מסד הנתונים:**\n\n"
        
        total_rows = 0
        
        # מיון לפי שינוי (הכי גדול קודם)
        sorted_tables = []
        for table, current_count in table_counts.items():
            if isinstance(current_count, int):
                total_rows += current_count
                change_info = ""
                if table in changes:
                    change = changes[table]
                    change_sign = "+" if change['change'] > 0 else ""
                    change_info = f"({change_sign}{change['change']:,})"
                else:
                    change_info = ""
                sorted_tables.append((table, current_count, change_info, abs(changes.get(table, {}).get('change', 0))))
            else:
                sorted_tables.append((table, current_count, "שגיאה", 0))
        
        # מיון לפי גודל השינוי (הכי גדול קודם)
        sorted_tables.sort(key=lambda x: x[3], reverse=True)
        
        # טבלה עם פונט קבוע
        message += "```\n"
        message += f"{'טבלה':<20} {'שורות':>8} {'שינוי':>10}\n"
        message += "=" * 40 + "\n"
        
        for table, count, change_info, _ in sorted_tables:
            # קיצור שם הטבלה
            short_name = table.replace('_', ' ')
            if len(short_name) > 19:
                short_name = short_name[:16] + "..."
            table_name = short_name.ljust(19)
            
            if isinstance(count, int):
                count_str = f"{count:,}".rjust(8)
                change_str = change_info.rjust(10) if change_info else "".rjust(10)
            else:
                count_str = "שגיאה".rjust(8)
                change_str = "N/A".rjust(10)
            
            message += f"{table_name} {count_str} {change_str}\n"
        
        # שורת סיכום
        message += "=" * 40 + "\n"
        
        # חישוב שינוי כללי
        total_change = 0
        if previous_counts:
            previous_total = sum(count for count in previous_counts.values() if isinstance(count, int))
            total_change = total_rows - previous_total
            if total_change != 0:
                change_sign = "+" if total_change > 0 else ""
                total_change_str = f"({change_sign}{total_change:,})".rjust(10)
            else:
                total_change_str = "(אין שינוי)".rjust(10)
        else:
            total_change_str = "(ראשונה)".rjust(10)
        
        total_str = f"{total_rows:,}".rjust(8)
        message += f"{'סה״כ'.ljust(19)} {total_str} {total_change_str}\n"
        message += "```"
        
        return message
        
    except Exception as e:
        return f"❌ שגיאה בקבלת מידע מסד הנתונים: {str(e)[:100]}"

def _load_critical_error_users():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.get_users_needing_recovery() במקום
    """
    users = get_users_needing_recovery()
    # המרה לפורמט הישן לתאימות
    return {user.get('chat_id'): user for user in users}

def merge_temporary_critical_files():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    פונקציה זו אינה נדרשת יותר - המודול החדש לא משתמש בקבצים זמניים
    """
    logger.info("merge_temporary_critical_files called but deprecated - no action needed", source="notifications")


