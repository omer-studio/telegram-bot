"""
gentle_reminders.py
==================
מודול לניהול תזכורות עדינות למשתמשים
הועבר מ-notifications.py כדי לשמור על קוד lean ומסודר
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from config import BOT_TOKEN
from utils import get_israel_time
from user_friendly_errors import safe_str
import pytz

# 🚀 יבוא המערכת החדשה - פשוטה ועקבית
from simple_logger import logger

# קובץ לניהול מצבי תזכורות
REMINDER_STATE_FILE = "data/reminder_state.json"

def _load_reminder_state():
    """טוען את מצב התזכורות מהקובץ"""
    try:
        if os.path.exists(REMINDER_STATE_FILE):
            with open(REMINDER_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading reminder state: {e}", source="gentle_reminders")
        return {}

def _save_reminder_state(state):
    """שומר את מצב התזכורות לקובץ"""
    try:
        os.makedirs(os.path.dirname(REMINDER_STATE_FILE), exist_ok=True)
        with open(REMINDER_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving reminder state: {e}", source="gentle_reminders")

def mark_user_active(chat_id: str):
    """מסמן משתמש כפעיל (קיבל הודעה או שלח הודעה) ומאפס דגל תזכורת"""
    try:
        state = _load_reminder_state()
        user_id = safe_str(chat_id)
        
        current_time = get_israel_time()
        
        if user_id not in state:
            state[user_id] = {}
        
        state[user_id].update({
            "last_activity": current_time.isoformat(),
            "reminders_sent": state[user_id].get("reminders_sent", 0),  # שומר את הספירה
            "reminder_due": False,
            "last_reminder": state[user_id].get("last_reminder"),  # שומר את הזמן האחרון
            "inactive_count": 0,
            "reminder_sent_waiting_response": False  # מאפס - המשתמש ענה!
        })
        
        _save_reminder_state(state)
        
    except Exception as e:
        logger.error(f"Error marking user {safe_str(chat_id)} as active: {e}", source="gentle_reminders")

def _is_allowed_time() -> bool:
    """בדיקה אם זה זמן מתאים לשליחת תזכורות (9:00-21:00)"""
    israel_tz = pytz.timezone('Asia/Jerusalem')
    current_time = datetime.now(israel_tz)
    return 9 <= current_time.hour < 21

def _mark_reminder_delayed(chat_id: str) -> None:
    """מסמן תזכורת כדחויה בגלל זמן לא מתאים"""
    try:
        state = _load_reminder_state()
        user_id = safe_str(chat_id)
        
        if user_id in state:
            state[user_id]["reminder_delayed"] = True
            state[user_id]["delay_reason"] = "inappropriate_time"
            _save_reminder_state(state)
    except Exception as e:
        logger.error(f"Error marking reminder delayed for {safe_str(chat_id)}: {e}", source="gentle_reminders")

def _mark_reminder_sent(chat_id: str) -> None:
    """מסמן שתזכורת נשלחה למשתמש ואנחנו מחכים לתשובה"""
    try:
        state = _load_reminder_state()
        user_id = safe_str(chat_id)
        
        if user_id in state:
            current_time = get_israel_time()
            state[user_id]["last_reminder"] = current_time.isoformat()
            state[user_id]["reminders_sent"] = state[user_id].get("reminders_sent", 0) + 1
            state[user_id]["reminder_sent_waiting_response"] = True  # מחכים לתשובה
            state[user_id]["reminder_due"] = False
            state[user_id]["reminder_delayed"] = False
            _save_reminder_state(state)
    except Exception as e:
        logger.error(f"Error marking reminder sent for {safe_str(chat_id)}: {e}", source="gentle_reminders")

def _log_to_chat_history(chat_id: str) -> None:
    """רושם את התזכורת להיסטוריית הצ'אט"""
    try:
        from chat_utils import update_chat_history
        
        reminder_message = {
            "role": "assistant",
            "content": "🌟 תזכורת עדינה נשלחה למשתמש",
            "timestamp": get_israel_time().isoformat(),
            "message_type": "gentle_reminder"
        }
        
        update_chat_history(chat_id, reminder_message)
        
    except Exception as e:
        logger.error(f"Error logging reminder to chat history for {safe_str(chat_id)}: {e}", source="gentle_reminders")

async def send_gentle_reminder(chat_id: str) -> bool:
    """שולח תזכורת עדינה למשתמש"""
    try:
        if not _is_allowed_time():
            _mark_reminder_delayed(chat_id)
            return False
        
        from telegram import Bot
        from telegram.error import BadRequest
        bot = Bot(token=BOT_TOKEN)
        
        reminder_messages = [
            "היי! 😊 לא רוצה ללחוץ אבל רק רוצה להזכיר שאני כאן :) מה שלומך?"
        ]
        
        import random
        reminder_text = random.choice(reminder_messages)
        
        await bot.send_message(chat_id=chat_id, text=reminder_text)
        
        _mark_reminder_sent(chat_id)
        _log_to_chat_history(chat_id)
        
        print(f"✅ נשלחה תזכורת עדינה למשתמש {chat_id}")
        return True
        
    except BadRequest as e:
        if "chat not found" in str(e).lower() or "user is deactivated" in str(e).lower():
            print(f"⚠️ משתמש {chat_id} חסום/לא קיים - מסיר מרשימת התזכורות")
            _mark_user_inactive(chat_id)
            return False
        else:
            print(f"⚠️ שגיאת Telegram בתזכורת למשתמש {chat_id}: {e}")
            return False
            
    except Exception as e:
        print(f"🚨 שגיאה בשליחת תזכורת למשתמש {chat_id}: {e}")
        return False

def _mark_user_inactive(chat_id: str) -> None:
    """מסמן משתמש כלא פעיל"""
    try:
        state = _load_reminder_state()
        user_id = safe_str(chat_id)
        
        if user_id in state:
            state[user_id]["inactive"] = True
            state[user_id]["inactive_since"] = get_israel_time().isoformat()
            state[user_id]["inactive_count"] = state[user_id].get("inactive_count", 0) + 1
            _save_reminder_state(state)
            
    except Exception as e:
        logger.error(f"Error marking user {safe_str(chat_id)} as inactive: {e}", source="gentle_reminders")

def cleanup_inactive_users():
    """מנקה משתמשים לא פעילים מרשימת התזכורות"""
    try:
        state = _load_reminder_state()
        current_time = get_israel_time()
        cutoff_time = current_time - timedelta(days=30)  # 30 יום
        
        active_users = {}
        removed_count = 0
        
        for user_id, user_state in state.items():
            last_activity_str = user_state.get("last_activity")
            
            if last_activity_str:
                try:
                    last_activity = datetime.fromisoformat(last_activity_str.replace("Z", ""))
                    if last_activity > cutoff_time and not user_state.get("inactive", False):
                        active_users[user_id] = user_state
                    else:
                        removed_count += 1
                        print(f"🗑️ מסיר משתמש לא פעיל {user_id}")
                except:
                    # אם יש בעיה עם הזמן, נשאיר את המשתמש
                    active_users[user_id] = user_state
            else:
                # אם אין זמן פעילות, נשאיר את המשתמש
                active_users[user_id] = user_state
        
        _save_reminder_state(active_users)
        print(f"✅ נוקה רשימת תזכורות - הוסרו {removed_count} משתמשים לא פעילים")
        
    except Exception as e:
        print(f"🚨 שגיאה בניקוי משתמשים לא פעילים: {e}")

def auto_cleanup_old_users():
    """ניקוי אוטומטי של משתמשים ישנים"""
    try:
        state = _load_reminder_state()
        current_time = get_israel_time()
        cutoff_time = current_time - timedelta(days=90)  # 90 יום
        
        updated_state = {}
        removed_count = 0
        
        for user_id, user_data in state.items():
            try:
                last_activity_str = user_data.get("last_activity", "")
                if not last_activity_str:
                    # אם אין זמן פעילות, נשאיר את המשתמש
                    updated_state[user_id] = user_data
                    continue
                
                last_activity = datetime.fromisoformat(last_activity_str.replace("Z", ""))
                
                # הסרת משתמשים שלא פעילים יותר מ-90 יום
                if last_activity > cutoff_time:
                    updated_state[user_id] = user_data
                else:
                    removed_count += 1
                    print(f"🗑️ ניקוי אוטומטי: הוסר משתמש {user_id} (לא פעיל מ-{last_activity_str[:10]})")
                    
            except Exception as parse_error:
                print(f"⚠️ שגיאה בפרסור זמן למשתמש {user_id}: {parse_error}")
                # במקרה של שגיאה, נשאיר את המשתמש
                updated_state[user_id] = user_data
        
        _save_reminder_state(updated_state)
        
        if removed_count > 0:
            print(f"✅ ניקוי אוטומטי הושלם - הוסרו {removed_count} משתמשים ישנים")
            
            # שליחת דיווח לאדמין
            try:
                from admin_notifications import send_admin_notification
                send_admin_notification(
                    f"🧹 ניקוי אוטומטי של תזכורות הושלם\n"
                    f"📊 הוסרו {removed_count} משתמשים לא פעילים (90+ יום)\n"
                    f"👥 נשארו {len(updated_state)} משתמשים פעילים"
                )
            except Exception as notification_error:
                print(f"⚠️ שגיאה בשליחת דיווח ניקוי: {notification_error}")
        else:
            print("ℹ️ ניקוי אוטומטי - לא נמצאו משתמשים להסרה")
            
    except Exception as e:
        print(f"🚨 שגיאה בניקוי אוטומטי: {e}")
        try:
            from admin_notifications import send_admin_notification
            send_admin_notification(f"🚨 שגיאה בניקוי אוטומטי של תזכורות: {e}", urgent=True)
        except:
            pass

async def validate_user_before_reminder(chat_id: str) -> bool:
    """מאמת שמשתמש זכאי לקבל תזכורת - 🗑️ עברנו למסד נתונים"""
    try:
        # 🗑️ עברנו למסד נתונים - אין צורך ב-Google Sheets!
        from db_manager import check_user_approved_status_db
        
        # בדיקה במסד נתונים במקום Google Sheets
        try:
            user_status = check_user_approved_status_db(chat_id)
            
            if isinstance(user_status, dict):
                if user_status.get("status") == "not_found":
                    print(f"ℹ️ משתמש {chat_id} לא נמצא במסד - לא ישלח תזכורת")
                    return False
                    
                if not user_status.get("approved", False):
                    print(f"ℹ️ משתמש {chat_id} לא מאושר - לא ישלח תזכורת")
                    return False
            else:
                print(f"⚠️ תגובה לא צפויה מהמסד למשתמש {chat_id}")
                return False
                
        except Exception as db_error:
            print(f"⚠️ שגיאה בבדיקת מסד נתונים למשתמש {chat_id}: {db_error}")
            # במקרה של שגיאה, נניח שהמשתמש מאושר (נותנים הטבה של הספק)
            return True
        
        return True
        
    except Exception as e:
        print(f"🚨 שגיאה באימות משתמש {chat_id}: {e}")
        # במקרה של שגיאה כללית, נותנים הטבה של הספק
        return True

async def check_and_send_gentle_reminders():
    """בודק ושולח תזכורות עדינות למשתמשים שזקוקים להן"""
    try:
        if not _is_allowed_time():
            print("⏰ לא זמן מתאים לתזכורות (מחוץ ל-9:00-21:00)")
            return
        
        print("🔄 מתחיל בדיקת תזכורות עדינות...")
        
        state = _load_reminder_state()
        if not state:
            print("ℹ️ אין משתמשים ברשימת התזכורות")
            return
        
        current_time = get_israel_time()
        reminder_threshold = current_time - timedelta(hours=24)  # 24 שעות מהפעילות האחרונה
        max_reminders_per_run = 5  # מקסימום 5 תזכורות בכל הרצה
        
        reminders_sent = 0
        candidates = []
        
        # מציאת מועמדים לתזכורת
        for user_id, user_state in state.items():
            try:
                # בדיקה אם המשתמש מסומן כלא פעיל
                if user_state.get("inactive", False):
                    continue
                
                # בדיקה אם כבר נשלחה תזכורת ועדיין לא ענה
                if user_state.get("reminder_sent_waiting_response", False):
                    continue  # לא שולח שוב עד שיענה
                
                # בדיקת פעילות אחרונה
                last_activity_str = user_state.get("last_activity")
                if last_activity_str:
                    last_activity = datetime.fromisoformat(last_activity_str.replace("Z", ""))
                    
                    # אם המשתמש לא פעיל יותר מ-24 שעות ופחות מ-30 יום
                    if last_activity < reminder_threshold and (current_time - last_activity).days < 30:
                        candidates.append(user_id)
                
            except Exception as user_error:
                print(f"⚠️ שגיאה בבדיקת משתמש {user_id}: {user_error}")
                continue
        
        print(f"📋 נמצאו {len(candidates)} מועמדים לתזכורות")
        
        # שליחת תזכורות (מוגבל למספר מסוים)
        for user_id in candidates[:max_reminders_per_run]:
            try:
                # אימות נוסף לפני שליחה
                if await validate_user_before_reminder(user_id):
                    success = await send_gentle_reminder(user_id)
                    if success:
                        reminders_sent += 1
                        print(f"✅ תזכורת נשלחה למשתמש {user_id}")
                        
                        # המתנה בין תזכורות
                        await asyncio.sleep(10)
                    else:
                        print(f"⚠️ תזכורת נכשלה למשתמש {user_id}")
                else:
                    print(f"⚠️ משתמש {user_id} לא עבר אימות")
                    
            except Exception as send_error:
                print(f"🚨 שגיאה בשליחת תזכורת למשתמש {user_id}: {send_error}")
                continue
        
        print(f"✅ הושלמה בדיקת תזכורות - נשלחו {reminders_sent} תזכורות")
        
        # שליחת דיווח לאדמין אם נשלחו תזכורות
        if reminders_sent > 0:
            try:
                from admin_notifications import send_admin_notification
                send_admin_notification(
                    f"🌟 דיווח תזכורות עדינות\n"
                    f"📊 נשלחו {reminders_sent} תזכורות\n"
                    f"👥 מתוך {len(candidates)} מועמדים\n"
                    f"🕐 {current_time.strftime('%H:%M')}"
                )
            except Exception as notification_error:
                print(f"⚠️ שגיאה בשליחת דיווח תזכורות: {notification_error}")
        
    except Exception as e:
        print(f"🚨 שגיאה כללית בבדיקת תזכורות: {e}")
        try:
            from admin_notifications import send_admin_notification
            send_admin_notification(f"🚨 שגיאה במערכת תזכורות: {e}", urgent=True)
        except:
            pass

async def gentle_reminder_background_task():
    """משימת רקע לתזכורות עדינות - רצה מדי שעה"""
    try:
        print("🌟 התחלת משימת רקע לתזכורות עדינות...")
        
        # בדיקה וניקוי אוטומטי (פעם ביום)
        current_hour = get_israel_time().hour
        if current_hour == 2:  # 2:00 בלילה
            auto_cleanup_old_users()
        
        # בדיקה ושליחת תזכורות
        await check_and_send_gentle_reminders()
        
        print("✅ משימת רקע לתזכורות הושלמה")
        
    except Exception as e:
        print(f"🚨 שגיאה במשימת רקע לתזכורות: {e}")
        logger.error(f"Error in gentle reminder background task: {e}", source="gentle_reminders")
        
        try:
            from admin_notifications import send_admin_notification
            send_admin_notification(f"🚨 שגיאה במשימת רקע לתזכורות: {e}", urgent=True)
        except Exception as notification_error:
            print(f"⚠️ גם שליחת התראה נכשלה: {notification_error}") 