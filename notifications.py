"""
notifications.py
----------------
קובץ זה מרכז את כל הפונקציות להתראות, שגיאות, ודיווחים לאדמין.
הרציונל: ריכוז כל ניהול ההתראות, שגיאות, ודיווחי מערכת במקום אחד, כולל שליחה לטלגרם ולוגים.
"""
import json
import os
from datetime import datetime
import requests
from config import ADMIN_NOTIFICATION_CHAT_ID, ADMIN_BOT_TELEGRAM_TOKEN, BOT_TRACE_LOG_PATH, BOT_ERRORS_PATH
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
    import traceback
    from config import ADMIN_NOTIFICATION_CHAT_ID, ADMIN_BOT_TELEGRAM_TOKEN
    import requests
    log_error_stat(error_type)
    # מסנן טוקנים/סודות
    def sanitize(msg):
        import re
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

def log_error_to_file(error_data):
    """
    רושם שגיאות לקובץ נפרד ב-data וגם שולח טלגרם לאדמין.
    קלט: error_data (dict)
    פלט: אין (שומר לוג)
    """
    import requests
    from config import ADMIN_NOTIFICATION_CHAT_ID, ADMIN_BOT_TELEGRAM_TOKEN

    try:
        error_file = BOT_ERRORS_PATH
        error_data["timestamp"] = datetime.now().isoformat()

        # יצירה אוטומטית של הקובץ אם לא קיים
        if not os.path.exists(error_file):
            with open(error_file, "w", encoding="utf-8") as f:
                pass

        with open(error_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(error_data, ensure_ascii=False) + "\n")

        # מגביל ל־500 שורות
        if os.path.exists(error_file):
            with open(error_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > 500:
                with open(error_file, "w", encoding="utf-8") as f:
                    f.writelines(lines[-500:])

        print(f"📝 שגיאה נרשמה בקובץ: {error_file}")

        # --- שולח גם טלגרם עם פירוט ---
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
    from utils import log_error_stat
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
    })



def handle_non_critical_error(error, chat_id, user_msg, error_type):
    """
    מטפל בשגיאות לא קריטיות - שגיאות שלא מונעות מהבוט לעבוד
    """
    print(f"⚠️ שגיאה לא קריטית: {error}")
    from utils import log_error_stat
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
