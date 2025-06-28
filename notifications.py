"""מרכז התראות, שגיאות ודיווחים לאדמין."""
import json
import os
import re
import traceback
import logging
import asyncio
import telegram
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
from utils import log_error_stat

def write_deploy_commit_to_log(commit):
    """שומר commit של דפלוי בקובץ לוג."""
    log_file = BOT_TRACE_LOG_PATH
    from utils import get_israel_time
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
    from utils import get_israel_time
    timestamp = get_israel_time().strftime('%Y-%m-%d %H:%M:%S')
    project = emoji_or_na(os.getenv('RENDER_SERVICE_NAME', None))
    environment = emoji_or_na(os.getenv('RENDER_ENVIRONMENT', None))
    user = emoji_or_na(os.getenv('USER', None))
    deploy_id = emoji_or_na(os.getenv('RENDER_DEPLOY_ID', None))
    git_commit = get_commit_7first(os.getenv('RENDER_GIT_COMMIT', None))
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
        fields.append("\nלפרטים נוספים בדוק את הלוגים ב-Render.")
        text = "אדמין יקר - ✅פריסה הצליחה והבוט שלך רץ !! איזה כיף !! 🚀\n\n" + "\n".join(fields)
        if debug_env:
            text += debug_env

    data = {
        "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
        "text": text
    }
    try:
        requests.post(url, data=data)
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
        text += f"\nchat_id: {chat_id}"
    if user_msg:
        text += f"\nuser_msg: {user_msg[:200]}"
    try:
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"[ERROR] לא הצלחתי לשלוח שגיאה לאדמין: {e}")

def send_admin_notification(message, urgent=False):
    """שולח הודעה כללית לאדמין."""
    try:
        prefix = "🚨 הודעה דחופה לאדמין: 🚨" if urgent else "ℹ️ הודעה לאדמין:"
        from utils import get_israel_time
        notification_text = f"{prefix}\n\n{message}\n\n⏰ {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}"

        url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
            "text": notification_text,
            "parse_mode": "HTML"
        }

        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ הודעה נשלחה לאדמין")
        else:
            print(f"❌ שגיאה בשליחת הודעה: {response.status_code}")

    except Exception as e:
        print(f"💥 שגיאה בשליחת הודעה: {e}")

# === הוספה: שליחת התראת קוד סודי לאדמין ===
def send_admin_secret_command_notification(message: str):
    """
    שולח הודעה מיוחדת לאדמין על שימוש בקוד סודי.
    קלט: message (str)
    פלט: אין (שולח הודעה)
    """
    try:
        from utils import get_israel_time
        notification_text = (
            f"🔑 *הפעלה של קוד סודי בבוט!* 🔑\n\n"
            f"{message}\n\n"
            f"⏰ {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
            "text": notification_text,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ התראת קוד סודי נשלחה לאדמין")
        else:
            print(f"❌ שגיאה בשליחת התראת קוד סודי: {response.status_code}")
    except Exception as e:
        print(f"💥 שגיאה בשליחת התראת קוד סודי: {e}")

def log_error_to_file(error_data, send_telegram=True):
    """
    רושם שגיאות לקובץ נפרד ב-data וגם שולח טלגרם לאדמין (אם send_telegram=True).
    קלט: error_data (dict), send_telegram (bool)
    פלט: אין (שומר לוג)
    """
    try:
        print("[DEBUG][log_error_to_file] --- START ---")
        for k, v in error_data.items():
            print(f"[DEBUG][log_error_to_file] {k} = {v} (type: {type(v)})")
            if isinstance(v, (dict, list)):
                print(f"[DEBUG][log_error_to_file][ALERT] {k} הוא {type(v)}! ערך: {v}")
        error_file = BOT_ERRORS_PATH
        from utils import get_israel_time
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
            requests.post(url, data=data)
    except Exception as e:
        print(f"💥 שגיאה ברישום שגיאה לקובץ: {e}")
        print("[DEBUG][log_error_to_file][EXCEPTION] error_data:")
        for k, v in error_data.items():
            print(f"[DEBUG][log_error_to_file][EXCEPTION] {k} = {v} (type: {type(v)})")
        print(traceback.format_exc())


def send_startup_notification():
    """
    שולח הודעה כשהבוט מתחיל לרוץ
    """
    send_deploy_notification()

from telegram import Update # type: ignore

async def handle_critical_error(error, chat_id, user_msg, update: Update):
    """
    מטפל בשגיאות קריטיות - שגיאות שמונעות מהבוט לענות למשתמש
    """
    print(f"🚨 שגיאה קריטית: {error}")
    print("[DEBUG][handle_critical_error][locals]:")
    for k, v in locals().items():
        print(f"[DEBUG][handle_critical_error][locals] {k} = {v} (type: {type(v)})")
    log_error_stat("critical_error")
    send_error_notification(
        error_message=error,
        chat_id=chat_id,
        user_msg=user_msg,
        error_type="שגיאה קריטית - הבוט לא הצליח לענות למשתמש"
    )
    log_error_to_file({
        "error_type": "critical_error",
        "error": str(error),
        "chat_id": chat_id,
        "user_msg": user_msg,
        "critical": True
    }, send_telegram=False)



def handle_non_critical_error(error, chat_id, user_msg, error_type):
    """
    מטפל בשגיאות לא קריטיות - שגיאות שלא מונעות מהבוט לעבוד
    """
    print(f"⚠️ שגיאה לא קריטית: {error}")
    log_error_stat(error_type)
    send_error_notification(
        error_message=error,
        chat_id=chat_id,
        user_msg=user_msg,
        error_type=error_type
    )
    log_error_to_file({
        "error_type": error_type.lower().replace(" ", "_"),
        "error": str(error),
        "chat_id": chat_id,
        "user_msg": user_msg,
        "critical": False
    })

def send_concurrent_alert(alert_type: str, details: dict):
    """
    שליחת התראות ספציפיות למערכת Concurrent Handling
    """
    try:
        if alert_type == "max_users_reached":
            from utils import get_israel_time
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
        elif alert_type == "sheets_queue_overflow":
            message = (
                f"🗂️ **התראת עומס Google Sheets**\n"
                f"📥 גודל תור: {details.get('queue_size', 0)}\n"
                f"⚡ פעולות לדקה: {details.get('operations_per_minute', 0)}\n"
                f"🚨 יש לבדוק אם Google Sheets מגיב כראוי"
            )
        elif alert_type == "concurrent_error":
            from utils import get_israel_time  
            message = (
                f"❌ **שגיאה במערכת Concurrent**\n"
                f"🔧 רכיב: {details.get('component', 'לא ידוע')}\n"
                f"📝 שגיאה: {details.get('error', 'לא ידוע')}\n"
                f"👤 משתמש: {details.get('chat_id', 'לא ידוע')}\n"
                f"⏰ זמן: {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}"
            )
        elif alert_type == "queue_failure":
            message = (
                f"🔥 **כשל בתור Google Sheets**\n"
                f"📊 פעולות שנדחו: {details.get('dropped_operations', 0)}\n"
                f"🔄 סוג פעולה: {details.get('operation_type', 'לא ידוע')}\n"
                f"⚠️ נתונים עלולים להיאבד!"
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
        elif recovery_type == "queue_cleared":
            message = (
                f"🧹 **תור Google Sheets נוקה**\n"
                f"📥 גודל תור חדש: {details.get('queue_size', 0)}\n"
                f"✅ המערכת פועלת כרגיל"
            )
        else:
            message = f"🔄 התאוששות: {recovery_type}\n{details}"
        
        send_error_notification(message)
        print(f"[RECOVERY] {recovery_type}: {message}")
        
    except Exception as e:
        print(f"[ERROR] Failed to send recovery notification: {e}")

# ========================================
# 🚨 מערכת התראות אדמין (מקור: admin_alerts.py)
# ========================================

def send_admin_alert(message, alert_level="info"):
    """
    🚨 שולח התראה לאדמין בטלגרם
    
    Args:
        message: הודעת ההתראה
        alert_level: "info", "warning", "critical"
    """
    try:
        # אייקונים לפי רמת חומרה
        icons = {
            "info": "📊",
            "warning": "⚠️", 
            "critical": "🚨"
        }
        
        icon = icons.get(alert_level, "📊")
        from utils import get_israel_time
        timestamp = get_israel_time().strftime("%H:%M:%S")
        
        alert_text = f"{icon} **התראת מערכת** ({timestamp})\n\n{message}"
        
        # שליחה אסינכרונית (לא חוסמת)
        asyncio.create_task(_send_telegram_message_admin(BOT_TOKEN, ADMIN_CHAT_ID, alert_text))
        
        # גם ללוג
        logging.warning(f"[🚨 אדמין] {message}")
        
    except Exception as e:
        # אם נכשל לשלוח - לפחות ללוג
        logging.error(f"[🚨] נכשל לשלוח התראה לאדמין: {e}")
        logging.warning(f"[🚨 לוג] {message}")

async def _send_telegram_message_admin(bot_token, chat_id, text):
    """שולח הודעה בטלגרם (אסינכרונית)"""
    try:
        bot = telegram.Bot(token=bot_token)
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"[טלגרם] שגיאה בשליחה: {e}")

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

import asyncio
from datetime import timedelta

GENTLE_REMINDER_MESSAGE = "היי, רק רציתי לבדוק מה שלומך, מקווה שאתה בטוב. אין לחץ – פשוט רציתי להזכיר לך מה שלומך?"
REMINDER_INTERVAL_HOURS = 3
REMINDER_STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "reminder_state.json")
_reminder_state = {}

def _load_reminder_state():
    """טוען מצב תזכורות מקובץ JSON."""
    global _reminder_state
    try:
        if os.path.exists(REMINDER_STATE_FILE):
            with open(REMINDER_STATE_FILE, 'r', encoding='utf-8') as f:
                _reminder_state = json.load(f)
                logging.debug(f"[REMINDER] Loaded {len(_reminder_state)} reminder states")
        else:
            _reminder_state = {}
            logging.debug(f"[REMINDER] No reminder state file found, starting fresh")
    except Exception as e:
        logging.error(f"[REMINDER] Error loading reminder state: {e}")
        _reminder_state = {}

def _save_reminder_state():
    """שומר מצב תזכורות לקובץ JSON."""
    try:
        # יצירת תיקיית data אם לא קיימת
        os.makedirs(os.path.dirname(REMINDER_STATE_FILE), exist_ok=True)
        
        with open(REMINDER_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_reminder_state, f, ensure_ascii=False, indent=2)
        
        logging.debug(f"[REMINDER] Saved reminder state with {len(_reminder_state)} entries")
    except Exception as e:
        logging.error(f"[REMINDER] Error saving reminder state: {e}")

# ==================== פונקציות ממשק ====================

def mark_user_active(chat_id: str):
    """
    🟢 מסמן משתמש כפעיל ומאפס את מצב התזכורת שלו
    
    מטרה: כשמשתמש שולח הודעה, לאפס את מצב התזכורת שלו
           כך שיוכל לקבל תזכורת חדשה בעתיד
    
    📥 קלט: 
       - chat_id (str): מזהה הצ'אט של המשתמש
    📤 פלט: אין
    
    🔄 תהליך:
       1. בודק אם למשתמש יש מצב תזכורת שמור
       2. אם כן - מוחק אותו מהמילון הגלובלי
       3. שומר את המצב החדש לקובץ
    
    💡 נקרא מ-message_handler.py בכל הודעה מהמשתמש
    """
    global _reminder_state
    chat_id = str(chat_id)
    
    if chat_id in _reminder_state:
        del _reminder_state[chat_id]
        _save_reminder_state()
        logging.info(f"[REMINDER] ✅ User {chat_id} became active, reminder state reset")
    else:
        logging.debug(f"[REMINDER] User {chat_id} was already active (no reminder state)")

def _is_allowed_time() -> bool:
    """בודק אם השעה הנוכחית מותרת לשליחת הודעות (7:00-22:00)."""
    from utils import get_israel_time
    return 7 <= get_israel_time().hour <= 22

def _mark_reminder_delayed(chat_id: str) -> None:
    """מסמן תזכורת כנדחית עד הבוקר."""
    global _reminder_state
    from utils import get_israel_time
    _reminder_state[str(chat_id)] = {
        "reminder_delayed": True,
        "delayed_at": get_israel_time().isoformat(),
        "scheduled_for_morning": True
    }
    _save_reminder_state()

def _mark_reminder_sent(chat_id: str) -> None:
    """מסמן תזכורת כנשלחה וניקוי מצב דחייה."""
    global _reminder_state
    from utils import get_israel_time
    _reminder_state[str(chat_id)] = {"reminder_sent": True, "sent_at": get_israel_time().isoformat()}
    _save_reminder_state()

def _log_to_chat_history(chat_id: str) -> None:
    """מתעד הודעת תזכורת בהיסטוריית הצ'אט."""
    try:
        from utils import update_chat_history
        update_chat_history(chat_id, "[הודעה אוטומטית מהבוט]", GENTLE_REMINDER_MESSAGE)
    except Exception as e:
        logging.error(f"[REMINDER] Failed to log reminder to chat history: {e}")

async def send_gentle_reminder(chat_id: str) -> bool:
    """שולח תזכורת עדינה למשתמש רק בשעות מותרות (7:00-22:00)."""
    try:
        if not _is_allowed_time():
            from utils import get_israel_time
            current_hour = get_israel_time().hour
            logging.info(f"[REMINDER] ⏰ Delaying reminder for {chat_id} - current time {current_hour:02d}:00 outside 07:00-22:00")
            _mark_reminder_delayed(chat_id)
            return False
        
        # שליחת התזכורת
        bot = telegram.Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text=GENTLE_REMINDER_MESSAGE)
        
        # תיעוד ועדכון מצב
        _log_to_chat_history(chat_id)
        _mark_reminder_sent(chat_id)
        
        # התראה לאדמין
        admin_message = f"🫶 נשלחה תזכורת עדינה למשתמש {chat_id}"
        try:
            url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": ADMIN_NOTIFICATION_CHAT_ID, "text": admin_message}, timeout=5)
        except Exception:
            pass  # לא קריטי אם התראת האדמין נכשלת
        
        logging.info(f"[REMINDER] 🫶 Gentle reminder sent to user {chat_id}")
        return True
        
    except telegram.error.BadRequest as e:
        if "chat not found" in str(e).lower():
            # משתמש לא זמין - מסמנים כלא פעיל כדי לא לנסות שוב
            _mark_user_inactive(chat_id)
            logging.warning(f"[REMINDER] 🚫 User {chat_id} marked as inactive (chat not found)")
            return False
        else:
            logging.error(f"[REMINDER] ❌ BadRequest error for {chat_id}: {e}")
            return False
    except Exception as e:
        if "chat not found" in str(e).lower():
            # משתמש לא זמין - מסמנים כלא פעיל כדי לא לנסות שוב
            _mark_user_inactive(chat_id)
            logging.warning(f"[REMINDER] 🚫 User {chat_id} marked as inactive (chat not found)")
            return False
        else:
            logging.error(f"[REMINDER] ❌ Failed to send reminder to {chat_id}: {e}")
            return False

def _mark_user_inactive(chat_id: str) -> None:
    """מסמן משתמש כלא פעיל כדי שלא ינסה לשלוח לו תזכורות."""
    global _reminder_state
    from utils import get_israel_time
    _reminder_state[str(chat_id)] = {
        "user_inactive": True, 
        "marked_inactive_at": get_israel_time().isoformat(),
        "reason": "chat_not_found"
    }
    _save_reminder_state()
    logging.info(f"[REMINDER] 🚫 User {chat_id} marked as inactive permanently")

def cleanup_inactive_users():
    """
    פונקציה עזר לניקוי משתמשים לא פעילים מקובץ ההיסטוריה.
    לשימוש ידני או בתחזוקה תקופתית.
    """
    try:
        from config import CHAT_HISTORY_PATH
        global _reminder_state
        
        if not os.path.exists(CHAT_HISTORY_PATH):
            logging.warning("[CLEANUP] Chat history file not found")
            return
        
        # טעינת נתונים
        with open(CHAT_HISTORY_PATH, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        _load_reminder_state()
        
        # רשימת משתמשים לא פעילים
        inactive_users = [chat_id for chat_id, state in _reminder_state.items() 
                         if state.get("user_inactive")]
        
        if not inactive_users:
            logging.info("[CLEANUP] No inactive users found")
            return
        
        # הסרה מההיסטוריה
        removed_count = 0
        for chat_id in inactive_users:
            if chat_id in history_data:
                del history_data[chat_id]
                removed_count += 1
                logging.info(f"[CLEANUP] Removed inactive user {chat_id} from chat history")
        
        # שמירה חזרה
        if removed_count > 0:
            with open(CHAT_HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"[CLEANUP] ✅ Removed {removed_count} inactive users from chat history")
        else:
            logging.info("[CLEANUP] No users needed to be removed from chat history")
            
    except Exception as e:
        logging.error(f"[CLEANUP] Error cleaning up inactive users: {e}")

def auto_cleanup_old_users():
    """
    ניקוי אוטומטי של משתמשים ישנים (יותר מ-90 יום ללא פעילות)
    ומשתמשים שלא הגיבו לתזכורות במשך זמן רב.
    """
    try:
        from config import CHAT_HISTORY_PATH
        global _reminder_state
        
        if not os.path.exists(CHAT_HISTORY_PATH):
            logging.debug("[AUTO_CLEANUP] Chat history file not found")
            return
        
        # טעינת נתונים
        with open(CHAT_HISTORY_PATH, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        _load_reminder_state()
        from utils import get_israel_time
        now = get_israel_time()
        cleanup_candidates = []
        
        for chat_id, user_data in history_data.items():
            if not user_data.get("history"):
                continue
                
            # בדיקת זמן האינטראקציה האחרונה
            last_entry = user_data["history"][-1]
            last_contact_str = last_entry.get("timestamp")
            
            if last_contact_str:
                try:
                    last_contact_time = datetime.fromisoformat(last_contact_str)
                    # וידוא שיש timezone לשני התאריכים
                    if last_contact_time.tzinfo is None:
                        import pytz
                        israel_tz = pytz.timezone('Asia/Jerusalem')
                        last_contact_time = israel_tz.localize(last_contact_time)
                    days_since = (now - last_contact_time).days
                    
                    # משתמשים שלא פעילים יותר מ-90 יום
                    if days_since > 90:
                        cleanup_candidates.append((chat_id, f"inactive_{days_since}_days"))
                        continue
                    
                    # משתמשים שקיבלו תזכורת אבל לא הגיבו יותר מ-30 יום
                    user_state = _reminder_state.get(str(chat_id), {})
                    if user_state.get("reminder_sent"):
                        reminder_time_str = user_state.get("sent_at")
                        if reminder_time_str:
                            try:
                                reminder_time = datetime.fromisoformat(reminder_time_str)
                                # וידוא שיש timezone לשני התאריכים
                                if reminder_time.tzinfo is None:
                                    import pytz
                                    israel_tz = pytz.timezone('Asia/Jerusalem')
                                    reminder_time = israel_tz.localize(reminder_time)
                                days_since_reminder = (now - reminder_time).days
                                if days_since_reminder > 30:
                                    cleanup_candidates.append((chat_id, f"no_response_to_reminder_{days_since_reminder}_days"))
                            except:
                                pass
                                
                except ValueError:
                    # זמן לא תקין - מועמד לניקוי
                    cleanup_candidates.append((chat_id, "invalid_timestamp"))
        
        # סימון המשתמשים כלא פעילים
        marked_count = 0
        for chat_id, reason in cleanup_candidates:
            _reminder_state[str(chat_id)] = {
                "user_inactive": True,
                "marked_inactive_at": now.isoformat(),
                "reason": f"auto_cleanup_{reason}"
            }
            marked_count += 1
            logging.info(f"[AUTO_CLEANUP] Marked user {chat_id} as inactive: {reason}")
        
        if marked_count > 0:
            _save_reminder_state()
            logging.info(f"[AUTO_CLEANUP] ✅ Marked {marked_count} users as inactive")
            
            # הפעלת ניקוי מלא
            cleanup_inactive_users()
        else:
            logging.debug("[AUTO_CLEANUP] No users need cleanup")
            
    except Exception as e:
        logging.error(f"[AUTO_CLEANUP] Error in auto cleanup: {e}")

async def validate_user_before_reminder(chat_id: str) -> bool:
    """
    בודק תקפות משתמש לפני שליחת תזכורת.
    מנסה לשלוח הודעת בדיקה עדינה או בודק מצב השיחה.
    """
    try:
        # בדיקה פשוטה - ניסיון לקבל מידע על הצ'אט
        bot = telegram.Bot(token=BOT_TOKEN)
        chat_info = await bot.get_chat(chat_id)
        
        # אם הצלחנו לקבל מידע, המשתמש תקף
        return True
        
    except telegram.error.BadRequest as e:
        if "chat not found" in str(e).lower():
            # המשתמש לא קיים - מסמנים כלא פעיל
            _mark_user_inactive(chat_id)
            logging.warning(f"[VALIDATION] User {chat_id} validation failed - marked inactive")
            return False
        else:
            # שגיאה אחרת - עדיין נותנים הזדמנות
            logging.warning(f"[VALIDATION] Validation error for {chat_id}: {e}")
            return True
    except Exception as e:
        # שגיאה כללית - עדיין נותנים הזדמנות
        logging.warning(f"[VALIDATION] Unexpected validation error for {chat_id}: {e}")
        return True

async def check_and_send_gentle_reminders():
    """בודק משתמשים ושולח תזכורות לפי הצורך."""
    global _reminder_state
    try:
        from config import CHAT_HISTORY_PATH
        
        # 📂 בדיקת קיום קובץ ההיסטוריה
        if not os.path.exists(CHAT_HISTORY_PATH):
            logging.debug(f"[REMINDER] Chat history file not found: {CHAT_HISTORY_PATH}")
            return
        
        # 📖 קריאת היסטוריית כל המשתמשים
        with open(CHAT_HISTORY_PATH, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        reminders_sent = 0
        from utils import get_israel_time
        now = get_israel_time()
        total_users = len(history_data)
        
        logging.debug(f"[REMINDER] Checking {total_users} users for gentle reminders")
        
        # 🔄 לולאה על כל המשתמשים
        for chat_id, user_data in history_data.items():
            # ⏭️ דילוג על משתמשים ללא היסטוריה
            if not user_data.get("history"):
                continue
            
            chat_id_str = str(chat_id)
            user_reminder_state = _reminder_state.get(chat_id_str, {})
            
            # ⏭️ דילוג על משתמשים שסומנו כלא פעילים
            if user_reminder_state.get("user_inactive"):
                logging.debug(f"[REMINDER] Skipping inactive user {chat_id}")
                continue
            
            # בדיקה אם יש תזכורת נדחית שצריך לשלוח ב-7 בבוקר
            if user_reminder_state.get("scheduled_for_morning") and 7 <= now.hour <= 22:
                logging.info(f"[REMINDER] 🌅 Sending delayed reminder to {chat_id} (scheduled for morning)")
                success = await send_gentle_reminder(chat_id)
                if success:
                    reminders_sent += 1
                continue
            
            # ⏭️ דילוג על משתמשים שכבר קיבלו תזכורת
            if user_reminder_state.get("reminder_sent"):
                continue
            
            # 🕐 חישוב זמן מהאינטראקציה האחרונה
            last_entry = user_data["history"][-1]
            last_contact_str = last_entry.get("timestamp")
            
            if not last_contact_str:
                continue
            
            try:
                last_contact_time = datetime.fromisoformat(last_contact_str)
                # וידוא שיש timezone לשני התאריכים
                if last_contact_time.tzinfo is None:
                    # אם אין timezone, נניח שזה בזמן ישראל
                    import pytz
                    israel_tz = pytz.timezone('Asia/Jerusalem')
                    last_contact_time = israel_tz.localize(last_contact_time)
                time_since_last = now - last_contact_time
                hours_since = time_since_last.total_seconds() / 3600
                
                # ✅ בדיקה: האם עברו מספיק שעות
                if time_since_last >= timedelta(hours=REMINDER_INTERVAL_HOURS):
                    logging.debug(f"[REMINDER] User {chat_id} needs reminder ({hours_since:.1f}h since last contact)")
                    
                    # ✨ בדיקת תקפות המשתמש לפני שליחת תזכורת
                    is_valid = await validate_user_before_reminder(chat_id)
                    if not is_valid:
                        logging.debug(f"[REMINDER] User {chat_id} validation failed - skipping")
                        continue
                    
                    success = await send_gentle_reminder(chat_id)
                    if success:
                        reminders_sent += 1
                else:
                    logging.debug(f"[REMINDER] User {chat_id} too recent ({hours_since:.1f}h < {REMINDER_INTERVAL_HOURS}h)")
                        
            except ValueError as e:
                logging.warning(f"[REMINDER] Invalid timestamp for user {chat_id}: {last_contact_str}")
                continue
        
        # 📊 דיווח סיכום
        if reminders_sent > 0:
            logging.info(f"[REMINDER] ✅ Sent {reminders_sent} gentle reminders out of {total_users} users")
        else:
            logging.debug(f"[REMINDER] No reminders needed for {total_users} users")
            
    except Exception as e:
        error_msg = f"[REMINDER] Critical error in check_and_send_gentle_reminders: {e}"
        logging.error(error_msg)
        send_error_notification(error_msg)

async def gentle_reminder_background_task():
    """משימת רקע לבדיקת תזכורות כל שעה + ניקוי אוטומטי שבועי."""
    logging.info("[REMINDER] 🚀 Starting gentle reminder background task")
    
    # 📂 טעינת מצב התזכורות בהתחלה
    _load_reminder_state()
    
    # מונה לניקוי שבועי (168 שעות = שבוע)
    hours_counter = 0
    
    # 🔄 לולאה אינסופית לבדיקה כל שעה
    while True:
        try:
            logging.debug("[REMINDER] Running hourly reminder check...")
            await check_and_send_gentle_reminders()
            
            # ניקוי אוטומטי פעם בשבוע (כל 168 שעות)
            hours_counter += 1
            if hours_counter >= 168:  # שבוע
                logging.info("[REMINDER] 🧹 Running weekly auto cleanup...")
                try:
                    auto_cleanup_old_users()
                    logging.info("[REMINDER] ✅ Weekly auto cleanup completed")
                except Exception as cleanup_error:
                    logging.error(f"[REMINDER] ❌ Weekly cleanup failed: {cleanup_error}")
                hours_counter = 0  # איפוס המונה
            
            # ⏰ המתנה של שעה עד הבדיקה הבאה
            logging.debug("[REMINDER] ⏱️ Waiting 1 hour until next check...")
            await asyncio.sleep(3600)  # 3600 שניות = שעה
            
        except Exception as e:
            error_msg = f"[REMINDER] ❌ Error in background task: {e}"
            logging.error(error_msg)
            
            # 🛡️ ממשיך לרוץ גם אחרי שגיאה
            logging.info("[REMINDER] 🔄 Continuing background task despite error...")
            await asyncio.sleep(3600)  # ממתין שעה גם במקרה של שגיאה


