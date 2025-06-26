"""
notifications.py
----------------
קובץ זה מרכז את כל הפונקציות להתראות, שגיאות, ודיווחים לאדמין.
הרציונל: ריכוז כל ניהול ההתראות, שגיאות, ודיווחי מערכת במקום אחד, כולל שליחה לטלגרם ולוגים.
"""
import json
import os
import re
import traceback
import logging
import asyncio
import telegram
from datetime import datetime
import requests
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
    """
    שומר commit של דפלוי בקובץ לוג ייעודי.
    קלט: commit (str)
    פלט: אין (שומר לקובץ)
    """
    log_file = BOT_TRACE_LOG_PATH
    with open(log_file, "a", encoding="utf-8") as f:
        entry = {
            "type": "deploy_commit",
            "commit": commit,
            "timestamp": datetime.now().isoformat()
        }
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_last_deploy_commit_from_log():
    """
    מחפש את ה-commit האחרון מהלוג.
    פלט: commit (str) או None
    """
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
    """
    שולח הודעה לאדמין על הצלחת/כישלון דפלוי, כולל פרטים.
    קלט: success (bool), error_message (str), deploy_duration (int/None)
    פלט: אין (שולח הודעה)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
    """
    שולח הודעת שגיאה לאדמין עם פירוט מלא (ללא טוקנים/סודות).
    קלט: error_message (str), chat_id (str), user_msg (str), error_type (str)
    פלט: אין (שולח הודעה)
    """
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
    """
    שולח הודעה כללית לאדמין (רגילה או דחופה).
    קלט: message (str), urgent (bool)
    פלט: אין (שולח הודעה)
    """
    try:
        prefix = "🚨 הודעה דחופה לאדמין: 🚨" if urgent else "ℹ️ הודעה לאדמין:"
        notification_text = f"{prefix}\n\n{message}\n\n⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"

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
        notification_text = (
            f"🔑 *הפעלה של קוד סודי בבוט!* 🔑\n\n"
            f"{message}\n\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
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
        error_data["timestamp"] = datetime.now().isoformat()
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
            message = (
                f"🔴 **התראת עומס מקסימלי**\n"
                f"👥 הגענו למספר המקסימלי של משתמשים: {details.get('active_users', 0)}/{details.get('max_users', 10)}\n"
                f"⏱️ זמן: {datetime.now().strftime('%H:%M:%S')}\n"
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
            message = (
                f"❌ **שגיאה במערכת Concurrent**\n"
                f"🔧 רכיב: {details.get('component', 'לא ידוע')}\n"
                f"📝 שגיאה: {details.get('error', 'לא ידוע')}\n"
                f"👤 משתמש: {details.get('chat_id', 'לא ידוע')}\n"
                f"⏰ זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
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
        timestamp = datetime.now().strftime("%H:%M:%S")
        
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
