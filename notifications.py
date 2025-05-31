"""
מחלקת התראות - כל פונקציות ההתראות והשגיאות
"""
import json
import os
from datetime import datetime
import requests
from config import ERROR_NOTIFICATION_CHAT_ID, ADMIN_TELEGRAM_TOKEN, TELEGRAM_BOT_TOKEN

def send_deploy_notification(success=True, error_message=None):
    """
    שולח הודעה לאדמין האם הפריסה החדשה הצליחה או לא, כולל פרטים וטיימסטמפ
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    project = os.getenv('RENDER_SERVICE_NAME', 'N/A')
    environment = os.getenv('RENDER_ENVIRONMENT', 'N/A')
    user = os.getenv('USER', 'N/A')
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    if success:
        text = (
            f"❕הודעה לאדמין❕\n"
            f"✅ פריסה חדשה הושלמה בהצלחה!\n"
            f"⏰ טיימסטמפ: {timestamp}\n"
            f"📁 פרויקט: {project}\n"
            f"🖥️ סביבת הפעלה: {environment}\n"
            f"👤 יוזר: {user}\n"
            f"\nלפרטים נוספים בדוק את הלוגים ב-Render."
        )
    else:
        text = (
            f"❕הודעה לאדמין❕\n"
            f"❌ פריסה חדשה נכשלה!\n"
            f"⏰ טיימסטמפ: {timestamp}\n"
            f"📁 פרויקט: {project}\n"
            f"🖥️ סביבת הפעלה: {environment}\n"
            f"👤 יוזר: {user}\n"
            f"⚠️ פירוט השגיאה:\n{error_message or 'אין פירוט'}\n"
            f"\nלפרטים נוספים בדוק את הלוגים ב-Render."
        )
    data = {
        "chat_id": ERROR_NOTIFICATION_CHAT_ID,
        "text": text
    }
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"שגיאה בשליחת הודעת פריסה: {e}")

def send_error_notification(error_msg, chat_id=None, user_msg=None, error_type="שגיאה כללית"):
    """
    שולח התראת שגיאה לאדמין בטלגרם
    """
    try:
        if not ERROR_NOTIFICATION_CHAT_ID:
            print("⚠️ לא הוגדר chat ID להתראות שגיאה")
            return

        notification_text = f"🚨 הודעה לאדמין: 🚨\n\n"
        notification_text += f"❌ {error_type}\n"
        notification_text += f"⏰ זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"

        if chat_id:
            notification_text += f"👤 משתמש: {chat_id}\n"
        if user_msg:
            display_msg = user_msg[:80] + "..." if len(user_msg) > 80 else user_msg
            notification_text += f"💬 הודעת משתמש: \"{display_msg}\"\n\n"

        notification_text += f"🔍 פרטי השגיאה:\n{str(error_msg)[:400]}"
        if len(str(error_msg)) > 400:
            notification_text += "...\n\n📄 השגיאה המלאה נשמרה בקובץ הלוגים"

        url = f"https://api.telegram.org/bot{ADMIN_TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": ERROR_NOTIFICATION_CHAT_ID,
            "text": notification_text,
            "parse_mode": "HTML"
        }

        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ התראת שגיאה נשלחה לאדמין")
        else:
            print(f"❌ שגיאה בשליחת התראה: {response.status_code}")

    except Exception as e:
        print(f"💥 שגיאה בשליחת התראת שגיאה: {e}")

def send_admin_notification(message, urgent=False):
    """
    שולח הודעה כללית לאדמין
    """
    try:
        prefix = "🚨 הודעה דחופה לאדמין: 🚨" if urgent else "ℹ️ הודעה לאדמין:"
        notification_text = f"{prefix}\n\n{message}\n\n⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"

        url = f"https://api.telegram.org/bot{ADMIN_TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": ERROR_NOTIFICATION_CHAT_ID,
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

def log_error_to_file(error_data):
    """
    רושם שגיאות לקובץ נפרד ב־/data וגם שולח טלגרם לאדמין
    """
    import requests
    from config import ERROR_NOTIFICATION_CHAT_ID, ADMIN_TELEGRAM_TOKEN

    try:
        error_file = "/data/bot_errors.jsonl"
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

        url = f"https://api.telegram.org/bot{ADMIN_TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": ERROR_NOTIFICATION_CHAT_ID,
            "text": msg
        }
        requests.post(url, data=data)

    except Exception as e:
        print(f"💥 שגיאה ברישום שגיאה לקובץ: {e}")


def send_startup_notification():
    """
    שולח הודעה כשהבוט מתחיל לרוץ
    """
    send_admin_notification("🚀 הבוט התחיל לרוץ בהצלחה! מוכן לקבל הודעות.")

from telegram import Update

async def handle_critical_error(error, chat_id, user_msg, update: Update):
    """
    מטפל בשגיאות קריטיות - שגיאות שמונעות מהבוט לענות למשתמש
    """
    print(f"🚨 שגיאה קריטית: {error}")

    send_error_notification(
        error_msg=error,
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

    try:
        await update.message.reply_text(
            "🙏  ..מתנצל, קרתה תקלה. דיווחתי לעומר ונטפל בזה בהקדם - תמשיך להנות מהקורס בינתיים "
        )
    except Exception as e:
        print(f"⚠️ שגיאה בשליחת ההודעה למשתמש: {e}")

def handle_non_critical_error(error, chat_id, user_msg, error_type):
    """
    מטפל בשגיאות לא קריטיות - שגיאות שלא מונעות מהבוט לעבוד
    """
    print(f"⚠️ שגיאה לא קריטית: {error}")
    
    send_error_notification(
        error_msg=error,
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
