"""
מחלקת התראות - כל פונקציות ההתראות והשגיאות
"""
import json
import os
from datetime import datetime
from config import ERROR_NOTIFICATION_CHAT_ID, ADMIN_TELEGRAM_TOKEN


def send_error_notification(error_msg, chat_id=None, user_msg=None, error_type="שגיאה כללית"):
    """
    שולח התראת שגיאה לאדמין בטלגרם
    """
    try:
        if not ERROR_NOTIFICATION_CHAT_ID:
            print("⚠️ לא הוגדר chat ID להתראות שגיאה")
            return

        import requests

        # יוצר הודעת שגיאה מפורטת עם סירנה
        notification_text = f"🚨 הודעה לאדמין: 🚨\n\n"
        notification_text += f"❌ {error_type}\n"
        notification_text += f"⏰ זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"

        if chat_id:
            notification_text += f"👤 משתמש: {chat_id}\n"
        if user_msg:
            # מקצר הודעה אם היא ארוכה
            display_msg = user_msg[:80] + "..." if len(user_msg) > 80 else user_msg
            notification_text += f"💬 הודעת משתמש: \"{display_msg}\"\n\n"

        notification_text += f"🔍 פרטי השגיאה:\n{str(error_msg)[:400]}"

        if len(str(error_msg)) > 400:
            notification_text += "...\n\n📄 השגיאה המלאה נשמרה בקובץ הלוגים"

        # שולח הודעה דרך Telegram API
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
        import requests

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
    רושם שגיאות לקובץ נפרד
    """
    try:
        error_file = "bot_errors.jsonl"
        error_data["timestamp"] = datetime.now().isoformat()

        with open(error_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(error_data, ensure_ascii=False) + "\n")

        # מגביל את קובץ השגיאות ל-500 שורות
        if os.path.exists(error_file):
            with open(error_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > 500:
                with open(error_file, "w", encoding="utf-8") as f:
                    f.writelines(lines[-500:])

        print(f"📝 שגיאה נרשמה בקובץ: {error_file}")

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

    # שליחת התראה לאדמין
    send_error_notification(
        error_msg=error,
        chat_id=chat_id,
        user_msg=user_msg,
        error_type="שגיאה קריטית - הבוט לא הצליח לענות למשתמש"
    )

    # רישום לקובץ לוג
    log_error_to_file({
        "error_type": "critical_error",
        "error": str(error),
        "chat_id": chat_id,
        "user_msg": user_msg,
        "critical": True
    })

    # שליחת הודעה למשתמש
    try:
        await update.message.reply_text(
            "🙏 מתנצל, קרתה תקלה. דיווחתי לעומר וננסה לטפל בזה בהקדם."
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