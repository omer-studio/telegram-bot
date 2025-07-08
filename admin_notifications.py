"""
admin_notifications.py
======================
מודול לניהול התראות אדמין ומערכת
הועבר מ-notifications.py כדי לשמור על קוד lean ומסודר
"""

import json
import os
import logging
import requests
from datetime import datetime
from config import (
    ADMIN_NOTIFICATION_CHAT_ID, 
    ADMIN_BOT_TELEGRAM_TOKEN, 
    ADMIN_CHAT_ID
)
from utils import get_israel_time

try:
    import telegram
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

def write_deploy_commit_to_log(commit):
    """רושם commit של פריסה ללוג"""
    try:
        deploy_log_file = "data/last_deploy_commit.json"
        os.makedirs(os.path.dirname(deploy_log_file), exist_ok=True)
        
        deploy_data = {
            "commit": commit,
            "timestamp": get_israel_time().isoformat(),
            "deploy_time": datetime.now().isoformat()
        }
        
        with open(deploy_log_file, 'w', encoding='utf-8') as f:
            json.dump(deploy_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logging.error(f"Error writing deploy commit to log: {e}")

def get_last_deploy_commit_from_log():
    """קורא את ה-commit האחרון מהלוג"""
    try:
        deploy_log_file = "data/last_deploy_commit.json"
        if os.path.exists(deploy_log_file):
            with open(deploy_log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("commit", "unknown")
        return "unknown"
    except Exception as e:
        logging.error(f"Error reading deploy commit from log: {e}")
        return "unknown"

def emoji_or_na(value):
    """מחזיר emoji או N/A"""
    return "✅" if value else "❌"

def get_commit_7first(commit):
    """מחזיר 7 תווים ראשונים של commit"""
    return commit[:7] if commit and len(commit) >= 7 else commit or "unknown"

def send_deploy_notification(success=True, error_message=None, deploy_duration=None):
    """שולח התראת פריסה לאדמין"""
    try:
        # קבלת מידע על הפריסה
        try:
            import subprocess
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
            current_commit = result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            current_commit = "unknown"
        
        # השוואה לפריסה הקודמת
        last_commit = get_last_deploy_commit_from_log()
        
        # יצירת הודעת פריסה
        if success:
            icon = "🚀"
            status = "הצליחה"
            color = "🟢"
        else:
            icon = "💥"
            status = "נכשלה"
            color = "🔴"
        
        message = f"{icon} **פריסה {status}** {color}\n\n"
        message += f"📅 **זמן:** {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}\n"
        message += f"🔗 **Commit:** `{get_commit_7first(current_commit)}`\n"
        
        if last_commit != "unknown" and current_commit != last_commit:
            message += f"🔄 **שינוי מ:** `{get_commit_7first(last_commit)}`\n"
        
        if deploy_duration:
            message += f"⏱️ **משך:** {deploy_duration:.1f}s\n"
        
        if not success and error_message:
            message += f"\n❌ **שגיאה:**\n```\n{error_message[:500]}\n```"
        
        # שמירת הcommit החדש רק אם הפריסה הצליחה
        if success:
            write_deploy_commit_to_log(current_commit)
        
        # שליחת ההתראה
        send_admin_notification(message)
        
        # לוג
        print(f"📨 נשלחה התראת פריסה: {status}")
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראת פריסה: {e}")
        logging.error(f"Error sending deploy notification: {e}")

def send_error_notification(error_message: str, chat_id: str = None, user_msg: str = None, error_type: str = "general_error") -> None:
    """שולח התראת שגיאה לאדמין (deprecated - השתמש בsend_admin_notification)"""
    def sanitize(msg):
        if not msg or not isinstance(msg, str):
            return "N/A"
        # הסרת תווים בעייתיים
        cleaned = ''.join(char for char in msg if ord(char) < 65536)
        return cleaned[:500] if len(cleaned) > 500 else cleaned

    try:
        clean_error = sanitize(error_message)
        clean_user_msg = sanitize(user_msg)
        
        notification_text = f"🚨 **שגיאה במערכת**\n\n"
        notification_text += f"🔍 **סוג:** {error_type}\n"
        if chat_id:
            notification_text += f"👤 **משתמש:** {chat_id}\n"
        if clean_user_msg != "N/A":
            notification_text += f"💬 **הודעה:** {clean_user_msg}\n"
        notification_text += f"❌ **שגיאה:** {clean_error}"
        
        send_admin_notification(notification_text, urgent=True)
        
    except Exception as e:
        print(f"🚨 Failed to send error notification: {e}")

def send_admin_notification(message, urgent=False):
    """שולח התראה לאדמין דרך הבוט הייעודי"""
    try:
        if not TELEGRAM_AVAILABLE:
            print(f"📨 [ADMIN] {message}")
            return
            
        # הוספת סימון דחיפות
        if urgent:
            message = f"🚨 **דחוף** 🚨\n\n{message}"
        
        # שליחה עם הבוט הייעודי
        _send_telegram_message_admin_sync(ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID, message)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראה לאדמין: {e}")
        logging.error(f"Error sending admin notification: {e}")

def send_admin_notification_raw(message):
    """שולח התראה גולמית לאדמין ללא עיבוד"""
    try:
        if not TELEGRAM_AVAILABLE:
            print(f"📨 [ADMIN_RAW] {message}")
            return
            
        _send_telegram_message_admin_sync(ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID, message)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראה גולמית: {e}")
        logging.error(f"Error sending raw admin notification: {e}")

def send_admin_secret_command_notification(message: str):
    """שולח התראה מיוחדת לאדמין על הפעלת פקודה סודית"""
    try:
        timestamp = get_israel_time().strftime("%d/%m/%Y %H:%M:%S")
        
        notification = f"🔐 **פקודה סודית הופעלה**\n\n"
        notification += f"🕐 **זמן:** {timestamp}\n"
        notification += f"🎯 **פעולה:** {message}\n"
        notification += f"🛡️ **רמת אבטחה:** גבוהה"
        
        send_admin_notification(notification, urgent=True)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראת פקודה סודית: {e}")

def log_error_to_file(error_data, send_telegram=True):
    """רושם שגיאה לקובץ ושולח התראה"""
    try:
        # רישום לקובץ
        error_log_file = "data/bot_errors.jsonl"
        os.makedirs(os.path.dirname(error_log_file), exist_ok=True)
        
        with open(error_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_data, ensure_ascii=False) + '\n')
        
        # שליחת התראה לטלגרם
        if send_telegram:
            error_summary = f"🚨 שגיאה: {error_data.get('error_type', 'לא ידוע')}\n"
            error_summary += f"👤 משתמש: {error_data.get('chat_id', 'לא ידוע')}\n"
            error_summary += f"🕐 זמן: {error_data.get('timestamp', 'לא ידוע')}"
            
            send_admin_notification(error_summary)
        
    except Exception as e:
        print(f"🚨 שגיאה ברישום שגיאה לקובץ: {e}")

def send_startup_notification():
    """שולח התראת הפעלה לאדמין"""
    try:
        startup_message = f"🤖 **הבוט הופעל בהצלחה**\n\n"
        startup_message += f"🕐 **זמן הפעלה:** {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}\n"
        startup_message += f"🌍 **סביבה:** {'Production (Render)' if os.getenv('RENDER') else 'Development'}\n"
        startup_message += f"✅ **סטטוס:** מוכן לקבלת הודעות"
        
        send_admin_notification(startup_message)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראת הפעלה: {e}")

def send_concurrent_alert(alert_type: str, details: dict):
    """שולח התראה על פעילות concurrent"""
    try:
        alert_icons = {
            "high_load": "⚠️",
            "error_burst": "🚨",
            "rate_limit": "🚦",
            "system_overload": "💥",
            "recovery": "✅"
        }
        
        icon = alert_icons.get(alert_type, "ℹ️")
        
        message = f"{icon} **התראת מערכת - {alert_type}**\n\n"
        
        for key, value in details.items():
            if key == "timestamp":
                continue
            message += f"📊 **{key}:** {value}\n"
        
        message += f"\n🕐 **זמן:** {get_israel_time().strftime('%H:%M:%S')}"
        
        # התראה דחופה לבעיות רציניות
        urgent = alert_type in ["error_burst", "system_overload"]
        
        send_admin_notification(message, urgent=urgent)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראת concurrent: {e}")

def send_recovery_notification(recovery_type: str, details: dict):
    """שולח התראת התאוששות"""
    try:
        recovery_icons = {
            "system_recovered": "✅",
            "error_resolved": "🔧",
            "service_restored": "🟢",
            "performance_improved": "📈"
        }
        
        icon = recovery_icons.get(recovery_type, "✅")
        
        message = f"{icon} **התאוששות מערכת - {recovery_type}**\n\n"
        
        for key, value in details.items():
            if key == "timestamp":
                continue
            message += f"📊 **{key}:** {value}\n"
        
        message += f"\n🕐 **זמן:** {get_israel_time().strftime('%H:%M:%S')}"
        
        send_admin_notification(message)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראת התאוששות: {e}")

def send_admin_alert(message, alert_level="info"):
    """שולח התראה כללית לאדמין"""
    try:
        level_icons = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "error": "🚨",
            "critical": "💥",
            "success": "✅"
        }
        
        icon = level_icons.get(alert_level, "ℹ️")
        formatted_message = f"{icon} **{alert_level.upper()}**\n\n{message}"
        
        urgent = alert_level in ["error", "critical"]
        send_admin_notification(formatted_message, urgent=urgent)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראה כללית: {e}")

async def _send_telegram_message_admin(bot_token, chat_id, text):
    """שולח הודעה אסינכרונית לאדמין"""
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחה אסינכרונית לאדמין: {e}")

def _send_telegram_message_admin_sync(bot_token, chat_id, text):
    """שולח הודעה סינכרונית לאדמין"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ התראה נשלחה לאדמין")
        else:
            print(f"⚠️ שגיאה בשליחת התראה: {response.status_code}")
            
    except Exception as e:
        print(f"🚨 שגיאה בשליחה סינכרונית לאדמין: {e}")

def alert_billing_issue(cost_usd, model_name, tier, daily_usage, monthly_usage, daily_limit, monthly_limit):
    """שולח התראה על בעיית חיוב"""
    try:
        alert_message = f"💳 **התראת חיוב**\n\n"
        alert_message += f"💰 **עלות נוכחית:** ${cost_usd:.4f}\n"
        alert_message += f"🤖 **מודל:** {model_name}\n"
        alert_message += f"🏷️ **רמה:** {tier}\n\n"
        alert_message += f"📊 **שימוש יומי:** ${daily_usage:.2f} / ${daily_limit:.2f}\n"
        alert_message += f"📅 **שימוש חודשי:** ${monthly_usage:.2f} / ${monthly_limit:.2f}\n"
        
        # בדיקת רמת דחיפות
        daily_percentage = (daily_usage / daily_limit) * 100 if daily_limit > 0 else 0
        monthly_percentage = (monthly_usage / monthly_limit) * 100 if monthly_limit > 0 else 0
        
        if daily_percentage > 90 or monthly_percentage > 90:
            alert_message += f"\n🚨 **אזהרה:** חריגה מ-90% מהמגבלה!"
            urgent = True
        elif daily_percentage > 75 or monthly_percentage > 75:
            alert_message += f"\n⚠️ **זהירות:** חריגה מ-75% מהמגבלה"
            urgent = False
        else:
            urgent = False
        
        send_admin_notification(alert_message, urgent=urgent)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראת חיוב: {e}")

def alert_system_status(message, level="info"):
    """שולח התראת סטטוס מערכת"""
    try:
        timestamp = get_israel_time().strftime("%H:%M:%S")
        
        status_message = f"🖥️ **סטטוס מערכת** ({timestamp})\n\n{message}"
        
        send_admin_alert(status_message, level)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת סטטוס מערכת: {e}") 

def send_anonymous_chat_notification(user_message: str, bot_response: str):
    """שולח התראה אנונימית לאדמין על התכתבות משתמש-בוט"""
    try:
        # יצירת הודעה מפורמטת ללא מזהה משתמש
        notification_text = f"💬 **התכתבות חדשה**\n\n"
        notification_text += f"👤 **משתמש כתב:**\n{user_message}\n\n"
        notification_text += f"➖➖➖➖➖➖➖➖➖➖\n\n"
        notification_text += f"🤖 **הבוט ענה:**\n{bot_response}"
        
        # הגבלת אורך ההודעה למניעת שגיאות טלגרם
        if len(notification_text) > 3900:
            notification_text = notification_text[:3900] + "\n\n... (הודעה קוצרה)"
        
        send_admin_notification_raw(notification_text)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת התראת התכתבות אנונימית: {e}")
        logging.error(f"Error sending anonymous chat notification: {e}") 