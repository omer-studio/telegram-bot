#!/usr/bin/env python3
"""
admin_notifications.py - התראות לאדמין
"""

import json
import os
import requests
from datetime import datetime
from simple_logger import logger
# מועבר ל-import מקומי במקומות הספציפיים
from config import (
    ADMIN_NOTIFICATION_CHAT_ID, 
    ADMIN_BOT_TELEGRAM_TOKEN, 
    ADMIN_CHAT_ID
)
from simple_config import TimeoutConfig
from utils import get_israel_time
from typing import Optional

try:
    import telegram
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

def is_test_environment():
    """בודק אם אנחנו בסביבת בדיקה - אם כן, לא שולחים הודעות אדמין"""
    return (
        os.environ.get("CI") == "1" or 
        os.environ.get("TESTING") == "1" or 
        os.environ.get("PYTEST_CURRENT_TEST") is not None
    )

def write_deploy_commit_to_log(commit):
    """רושם commit של פריסה ללוג"""
    try:
        deploy_log_file = "data/last_deploy_commit.json"
        os.makedirs(os.path.dirname(deploy_log_file), exist_ok=True)
        
        deploy_data = {
            "commit": commit,
            "timestamp": get_israel_time().isoformat(),
            "deploy_time": get_israel_time().isoformat()
        }
        
        with open(deploy_log_file, 'w', encoding='utf-8') as f:
            json.dump(deploy_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"Error writing deploy commit to log: {e}")

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
        logger.error(f"Error reading deploy commit from log: {e}")
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
        logger.info(f"📨 נשלחה התראת פריסה: {status}")
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בשליחת התראת פריסה: {e}")

def send_error_notification(error_message: str, chat_id: str = None, user_msg: str = None, error_type: str = "general_error") -> None:
    """שולח התראת שגיאה לאדמין (deprecated - השתמש בsend_admin_notification)"""
    def sanitize(msg):
        if not msg or not isinstance(msg, str):
            return "N/A"
        # הסרת תווים בעייתיים
        cleaned = ''.join(char for char in msg if ord(char) < 65536)
        return cleaned[:500] if len(cleaned) > 500 else cleaned

    try:
        if is_test_environment():
            logger.info(f"📨 [ERROR] בסביבת בדיקה, לא שולח התראת שגיאה: {error_message}")
            return
            
        clean_error = sanitize(error_message)
        clean_user_msg = sanitize(user_msg)
        
        notification_text = f"🚨 **שגיאה במערכת**\n\n"
        notification_text += f"🔍 **סוג:** {error_type}\n"
        if chat_id:
            from utils import safe_str
            notification_text += f"👤 **משתמש:** {safe_str(chat_id)}\n"
        if clean_user_msg != "N/A":
            notification_text += f"💬 **הודעה:** {clean_user_msg}\n"
        notification_text += f"❌ **שגיאה:** {clean_error}"
        
        send_admin_notification(notification_text, urgent=True)
        
    except Exception as e:
        logger.error(f"🚨 Failed to send error notification: {e}")

def send_admin_notification(message, urgent=False):
    """שולח התראה לאדמין דרך הבוט הייעודי"""
    try:
        if is_test_environment():
            logger.info(f"📨 [ADMIN] בסביבת בדיקה, לא שולח תראה לאדמין: {message}")
            return

        if not TELEGRAM_AVAILABLE:
            logger.info(f"📨 [ADMIN] {message}")
            return
            
        # הוספת סימון דחיפות
        if urgent:
            message = f"🚨 **דחוף** 🚨\n\n{message}"
        
        # שליחה עם הבוט הייעודי
        _send_telegram_message_admin_sync(ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID, message)
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בשליחת התראה לאדמין: {e}")

def send_admin_notification_raw(message):
    """שולח התראה גולמית לאדמין ללא עיבוד"""
    try:
        if is_test_environment():
            logger.info(f"📨 [ADMIN_RAW] בסביבת בדיקה, לא שולח תראה לאדמין: {message}")
            return

        if not TELEGRAM_AVAILABLE:
            logger.info(f"📨 [ADMIN_RAW] {message}")
            return
            
        _send_telegram_message_admin_sync(ADMIN_BOT_TELEGRAM_TOKEN, ADMIN_NOTIFICATION_CHAT_ID, message)
        
    except Exception as e:
        logger.error(f"�� שגיאה בשליחת התראה גולמית: {e}")

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
        logger.error(f"🚨 שגיאה בשליחת התראת פקודה סודית: {e}")

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
        logger.error(f"🚨 שגיאה ברישום שגיאה לקובץ: {e}")

def send_startup_notification():
    """שולח התראת הפעלה לאדמין"""
    try:
        startup_message = f"🤖 **הבוט הופעל בהצלחה**\n\n"
        startup_message += f"🕐 **זמן הפעלה:** {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}\n"
        startup_message += f"🌍 **סביבה:** {'Production (Render)' if os.getenv('RENDER') else 'Development'}\n"
        startup_message += f"✅ **סטטוס:** מוכן לקבלת הודעות"
        
        send_admin_notification(startup_message)
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בשליחת התראת הפעלה: {e}")

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
        logger.error(f"🚨 שגיאה בשליחת התראת concurrent: {e}")

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
        logger.error(f"🚨 שגיאה בשליחת התראת התאוששות: {e}")

def send_admin_alert(message, alert_level="info"):
    """שולח התראה כללית לאדמין"""
    try:
        if is_test_environment():
            logger.info(f"📨 [ALERT] בסביבת בדיקה, לא שולח התראה כללית: {message}")
            return
            
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
        logger.error(f"🚨 שגיאה בשליחת התראה כללית: {e}")

async def _send_telegram_message_admin(bot_token, chat_id, text):
    """שולח הודעה אסינכרונית לאדמין"""
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בשליחה אסינכרונית לאדמין: {e}")

def _send_telegram_message_admin_sync(bot_token, chat_id, text):
    """שולח הודעה סינכרונית לאדמין"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, data=data, timeout=TimeoutConfig.TELEGRAM_SEND_TIMEOUT)
        if response.status_code == 200:
            logger.info("✅ התראה נשלחה לאדמין")
        else:
            logger.warning(f"⚠️ שגיאה בשליחת התראה: {response.status_code}")
            
    except Exception as e:
        logger.error(f"🚨 שגיאה בשליחה סינכרונית לאדמין: {e}")

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
        logger.error(f" שגיאה בשליחת התראת חיוב: {e}")

def alert_system_status(message, level="info"):
    """שולח התראת סטטוס מערכת"""
    try:
        timestamp = get_israel_time().strftime("%H:%M:%S")
        
        status_message = f"🖥️ **סטטוס מערכת** ({timestamp})\n\n{message}"
        
        send_admin_alert(status_message, level)
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בשליחת סטטוס מערכת: {e}") 

# �️ הפונקציה הישנה הוסרה - עכשיו משתמשים ב-send_admin_notification_from_db
# שמורה כהערה היסטורית בלבד 

def send_admin_notification_from_db(interaction_id: int) -> bool:
    """
    🔥 שליחת התראה לאדמין מנתוני אמת מטבלת interactions_log
    
    Args:
        interaction_id: מזהה אינטראקציה בטבלת interactions_log
        
    Returns:
        bool: האם ההתראה נשלחה בהצלחה
    """
    try:
        if is_test_environment():
            logger.info(f"📨 [DB_NOTIFICATION] בסביבת בדיקה, לא שולח התראה לאדמין | interaction_id={interaction_id}")
            return True

        # חיבור למסד הנתונים
        from config import get_config
        import psycopg2
        config = get_config()
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        if not db_url:
            logger.error("[DB_NOTIFICATION] לא נמצא URL למסד הנתונים")
            return False
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # שליפת נתוני האינטראקציה המלאים כולל הסיסטם פרומפטים
        cur.execute("""
            SELECT 
                serial_number, chat_id, user_msg, bot_msg, full_system_prompts,
                gpt_a_model, gpt_a_processing_time, gpt_a_tokens_input, gpt_a_tokens_output, gpt_a_tokens_cached,
                gpt_b_activated, gpt_b_reply, gpt_b_model, gpt_b_processing_time, gpt_b_tokens_input, gpt_b_tokens_output, gpt_b_tokens_cached,
                gpt_c_activated, gpt_c_reply, gpt_c_model, gpt_c_processing_time, gpt_c_tokens_input, gpt_c_tokens_output, gpt_c_tokens_cached,
                gpt_d_activated, gpt_d_reply, gpt_d_model, gpt_d_processing_time, gpt_d_tokens_input, gpt_d_tokens_output, gpt_d_tokens_cached,
                gpt_e_activated, gpt_e_reply, gpt_e_model, gpt_e_processing_time, gpt_e_tokens_input, gpt_e_tokens_output, gpt_e_tokens_cached, gpt_e_counter,
                user_to_bot_response_time, background_processing_time, total_cost_agorot,
                history_user_messages_count, history_bot_messages_count, timestamp
            FROM interactions_log 
            WHERE serial_number = %s
        """, (interaction_id,))
        
        row = cur.fetchone()
        if not row:
            logger.error(f"[DB_NOTIFICATION] לא נמצאה אינטראקציה {interaction_id}")
            cur.close()
            conn.close()
            return False
        
        # פירוק הנתונים כולל הסיסטם פרומפטים
        (serial_num, chat_id, user_msg, bot_msg, full_system_prompts,
         gpt_a_model, gpt_a_time, gpt_a_input, gpt_a_output, gpt_a_cached,
         gpt_b_activated, gpt_b_reply, gpt_b_model, gpt_b_time, gpt_b_input, gpt_b_output, gpt_b_cached,
         gpt_c_activated, gpt_c_reply, gpt_c_model, gpt_c_time, gpt_c_input, gpt_c_output, gpt_c_cached,
         gpt_d_activated, gpt_d_reply, gpt_d_model, gpt_d_time, gpt_d_input, gpt_d_output, gpt_d_cached,
         gpt_e_activated, gpt_e_reply, gpt_e_model, gpt_e_time, gpt_e_input, gpt_e_output, gpt_e_cached, gpt_e_counter,
         user_to_bot_time, background_time, total_cost_agorot,
         history_user_count, history_bot_count, timestamp) = row
        
        cur.close()
        conn.close()
        
        # יצירת chat_id מוסווה עם 4 ספרות אחרונות
        chat_suffix = ""
        if chat_id:
            from utils import safe_str
            safe_chat_id = safe_str(chat_id)
            if len(safe_chat_id) > 4:
                # מיסוך כל הספרות חוץ מ-4 האחרונות
                masked_part = "X" * (len(safe_chat_id) - 4)
                last_4_digits = safe_chat_id[-4:]
                masked_chat_id = masked_part + last_4_digits
                chat_suffix = f" (`{masked_chat_id}`)"
            else:
                chat_suffix = f" (`{safe_chat_id}`)"

        # יצירת ID עם 7 ספרות
        formatted_id = f"{serial_num:07d}"
        
        # בניית תוכן ההתראה בפורמט הישן
        notification_text = f"💬 <b>התכתבות חדשה{chat_suffix}</b> 💬\n\n"
        notification_text += f"📚 <b>היסטוריה:</b> {history_user_count} משתמש + {history_bot_count} בוט\n"
        
        # הוספת מידע על סיסטם פרומפטים האמיתיים מהטבלה
        if full_system_prompts:
            # פיצול הסיסטם פרומפטים לפי המפריד
            system_prompts_list = full_system_prompts.split('\n\n--- SYSTEM PROMPT SEPARATOR ---\n\n')
            for i, prompt in enumerate(system_prompts_list, 1):
                if prompt.strip():
                    if len(prompt) > 30:
                        prompt_preview = prompt[:30] + "..."
                        remaining_chars = len(prompt) - 30
                        notification_text += f"<b>סיסטם פרומפט {i}:</b> {prompt_preview} (+{remaining_chars})\n"
                    else:
                        notification_text += f"<b>סיסטם פרומפט {i}:</b> {prompt}\n"
        else:
            notification_text += f"<b>סיסטם פרומפט:</b> לא נמצאו סיסטם פרומפטים בטבלה\n"
        
        notification_text += f"\n➖➖➖➖➖     <b>הודעת משתמש</b>     ➖➖➖➖➖\n\n"
        notification_text += f"{user_msg}\n\n"
        
        notification_text += f"➖➖➖➖➖       <b>תשובת הבוט</b>       ➖➖➖➖➖\n\n"
        notification_text += f"{bot_msg}\n\n"
        
        notification_text += f"➖➖➖➖➖➖    <b>עוד נתונים</b>   ➖➖➖➖➖➖\n\n"
        
        # GPT-B
        notification_text += f"<b><u>מודל gpt_b:</u></b>     (מודל {gpt_b_model or 'לא זמין'})\n"
        if gpt_b_activated and gpt_b_reply:
            # הצגת התשובה המלאה של GPT-B (לא קטועה)
            notification_text += f"{gpt_b_reply}\n\n"
        else:
            notification_text += f"לא הופעל\n\n"
        
        # GPT-C
        notification_text += f"<b><u>מודל gpt_c:</u></b>     (מודל {gpt_c_model or 'לא זמין'})\n"
        if gpt_c_activated and gpt_c_reply:
            # הצגת התשובה המלאה של GPT-C (לא קטועה)
            notification_text += f"{gpt_c_reply}\n\n"
        else:
            notification_text += f"לא הופעל\n\n"
        
        # GPT-D
        notification_text += f"<b><u>מודל gpt_d:</u></b>     (מודל {gpt_d_model or 'לא זמין'})\n"
        if gpt_d_activated and gpt_d_reply:
            # הצגת התשובה המלאה של GPT-D (לא קטועה)
            notification_text += f"{gpt_d_reply}\n\n"
        else:
            notification_text += f"לא הופעל\n\n"
        
        # GPT-E - תיקון המונה
        notification_text += f"<b><u>מודל gpt_e:</u></b>     (מודל {gpt_e_model or 'לא זמין'})\n"
        if gpt_e_activated and gpt_e_reply:
            # הצגת התשובה המלאה של GPT-E (לא קטועה)
            notification_text += f"{gpt_e_reply}"
        else:
            # חישוב מונה נכון - כל 10 הודעות מופעל GPT-E
            current_msg_count = history_user_count if history_user_count > 0 else 1
            from gpt_e_handler import GPT_E_RUN_EVERY_MESSAGES
            counter_display = current_msg_count % GPT_E_RUN_EVERY_MESSAGES
            notification_text += f"לא הופעל - מופעל לפי מונה הודעות כרגע המונה עומד על {counter_display} מתוך {GPT_E_RUN_EVERY_MESSAGES}"
        
        notification_text += f"\n\n"
        
        # הוספת סיכום פרופיל רגשי תמיד
        # שליפת פרופיל המשתמש
        try:
            profile_conn = psycopg2.connect(db_url)
            profile_cur = profile_conn.cursor()
            profile_cur.execute("SELECT summary FROM user_profiles WHERE chat_id = %s", (safe_str(chat_id),))
            user_profile = profile_cur.fetchone()
            
            notification_text += f"➖➖➖➖ <b>סיכום פרופיל רגשי</b> ➖➖➖➖➖➖\n"
            if user_profile and user_profile[0] and user_profile[0].strip():
                notification_text += f"{user_profile[0]}\n\n"
            else:
                notification_text += f"חסר (אין פרופיל למשתמש)\n\n"
            
            profile_cur.close()
            profile_conn.close()
        except Exception as profile_err:
            logger.warning(f"[DB_NOTIFICATION] שגיאה בשליפת פרופיל: {profile_err}")
            notification_text += f"➖➖➖➖ <b>סיכום פרופיל רגשי</b> ➖➖➖➖➖➖\n"
            notification_text += f"שגיאה בשליפת פרופיל\n\n"
        
        # הפרדה לפני נתוני אמת מהמסד
        notification_text += f"➖➖➖➖➖➖    <b>עוד נתונים</b>   ➖➖➖➖➖➖\n\n"
        
        # נתוני אמת מהמסד - למטה
        notification_text += f"📊 <b>נתוני אמת מהמסד:</b>\n"
        notification_text += f"💰 <b>עלות כוללת לכל האינטרקציה:</b> {total_cost_agorot:.1f} אגורות\n"
        
        # תיקון חישוב הזמנים - 3 שורות נפרדות
        notification_text += f"⏱️ <b>זמן שלקח לבינה:</b> {gpt_a_time or 0:.2f}s\n"
        notification_text += f"      <b>זמן שלקח למשתמש לקבל:</b> {user_to_bot_time:.2f}s\n"
        
        # חישוב פער קוד נכון
        if gpt_a_time and user_to_bot_time:
            code_gap = user_to_bot_time - gpt_a_time
            notification_text += f"      <b>פער קוד:</b> {code_gap:.2f}s\n"
        else:
            notification_text += f"      <b>פער קוד:</b> {background_time:.2f}s\n"
        
        notification_text += f"📊 <b>מספר הודעות משתמש כולל:</b> {history_user_count or 1}\n"
        
        # המרה לזמן ישראל עם pytz
        import pytz
        israel_tz = pytz.timezone('Asia/Jerusalem')
        
        # המרה נכונה מUTC לזמן ישראל
        if timestamp.tzinfo is None:
            # אם אין timezone, נניח שזה UTC
            utc_tz = pytz.timezone('UTC')
            timestamp_utc = utc_tz.localize(timestamp)
        else:
            timestamp_utc = timestamp
        
        israel_time = timestamp_utc.astimezone(israel_tz)
        notification_text += f"🕐 <b>ההודעה נשלחה ב:</b> {israel_time.strftime('%d/%m/%y %H:%M')} ישראל\n\n"
        
        # גישה מהירה לטבלה
        notification_text += f"🔗 <b>לגישה מהירה לטבלה:</b>\n"
        notification_text += f"```sql\n"
        notification_text += f"SELECT * FROM interactions_log WHERE serial_number = {formatted_id};\n"
        notification_text += f"```"

        # שליחת ההתראה לאדמין
        send_admin_notification_raw(notification_text)
        success = True  # נניח שהשליחה הצליחה אם לא הייתה exception
        
        if success:
            # עדכון הטבלה עם הנוסח שנשלח
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute("""
                    UPDATE interactions_log 
                    SET admin_notification_text = %s
                    WHERE serial_number = %s
                """, (notification_text, serial_num))
                conn.commit()
                cur.close()
                conn.close()
                
                logger.info(f"✅ [DB_NOTIFICATION] התראה נשלחה ועודכנה בטבלה | interaction_id={interaction_id} | formatted_id={formatted_id}")
                
            except Exception as update_err:
                logger.warning(f"[DB_NOTIFICATION] שגיאה בעדכון הטבלה: {update_err}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ [DB_NOTIFICATION] שגיאה בשליחת התראה מהטבלה: {e}")
        return False 