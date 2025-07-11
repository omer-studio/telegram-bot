"""
critical_users_manager.py
=========================
מודול לניהול משתמשים קריטיים שחוו שגיאות והתאוששות
הועבר מ-notifications.py כדי לשמור על קוד lean ומסודר
"""

import json
import os
import logging
import time
import asyncio
from datetime import datetime, timedelta
from telegram import Update # type: ignore
from config import BOT_TOKEN
from utils import get_israel_time, safe_str
from chat_utils import log_error_stat
from simple_logger import logger

# 🔄 מסד נתונים במקום קבצים - תיקון מערכתי
# משתנה לתאימות לאחור - לא יעבוד יותר אבל נדרש לקוד ישן
CRITICAL_ERROR_USERS_FILE = "data/critical_error_users.json"  # DEPRECATED - כבר לא בשימוש

# Mock classes for processing lost messages  
class MockChat:
    def __init__(self, chat_id):
        # שימוש בטוח בhמרת chat_id לint
        try:
            self.id = int(safe_str(chat_id))
        except (ValueError, TypeError):
            # גיבוי במקרה של chat_id לא תקין
            self.id = 0

class MockUpdate:
    class MockMessage:
        def __init__(self, text, chat_id):
            self.text = text
            self.chat = MockChat(chat_id)
    def __init__(self, text, chat_id):
        self.message = self.MockMessage(text, chat_id)
        self.effective_chat = MockChat(chat_id)

def _load_critical_error_users():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.get_users_needing_recovery() במקום
    """
    try:
        from recovery_manager import get_users_needing_recovery
        users = get_users_needing_recovery()
        # המרה לפורמט הישן לתאימות
        return {user.get('chat_id'): user for user in users}
    except ImportError:
        # fallback לקוד הישן
        return {}

def _save_critical_error_users(users_data):
    """שומר רשימת משתמשים שקיבלו הודעות שגיאה קריטיות - מחליף למסד נתונים"""
    try:
        # הפונקציה הזו כבר לא נחוצה - הכל נשמר ישירות במסד נתונים
        # משאיר רק לתאימות לאחור
        print(f"ℹ️ _save_critical_error_users מושבת - הכל נשמר ישירות במסד נתונים")
        return True
        
    except Exception as e:
        logging.error(f"Error in deprecated _save_critical_error_users: {e}")
        print(f"🚨 שגיאה בפונקציה מושבתת _save_critical_error_users: {e}")
        return False

def _add_user_to_critical_error_list(chat_id: str, error_message: str, original_user_message: str = None):
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.add_user_to_recovery_list() במקום
    """
    try:
        from recovery_manager import add_user_to_recovery_list
        return add_user_to_recovery_list(chat_id, error_message, original_user_message)
    except ImportError:
        # fallback לקוד הישן אם המודול החדש לא זמין
        from profile_utils import update_user_profile
        
        # עדכון הפרופיל במסד נתונים
        update_data = {
            "needs_recovery_message": True,
            "recovery_error_timestamp": get_israel_time().isoformat()
        }
        
        # 🔧 הוספה: שמירת ההודעה המקורית של המשתמש אם קיימת
        if original_user_message and len(original_user_message.strip()) > 0:
            update_data["recovery_original_message"] = original_user_message.strip()
            print(f"💾 נשמרה הודעה מקורית למשתמש {safe_str(chat_id)}: '{original_user_message[:50]}...'")
        
        # עדכון במסד נתונים
        success = update_user_profile(safe_str(chat_id), update_data)
        
        if success:
            logging.info(f"Added user {safe_str(chat_id)} to critical error list in database")
            print(f"✅ משתמש {safe_str(chat_id)} נוסף לרשימת המשתמשים הקריטיים במסד נתונים")
        else:
            raise Exception("Failed to update user profile in database")
            
    except Exception as e:
        logging.error(f"Error adding user to critical error list: {e}")
        print(f"🚨 שגיאה בהוספת משתמש {safe_str(chat_id)} לרשימת משתמשים קריטיים: {e}")
        
        # 🔧 תיקון: התראה לאדמין במקום שמירת קבצים זמניים
        try:
            from admin_notifications import send_admin_notification
            send_admin_notification(
                f"🚨 CRITICAL: נכשל ברישום משתמש {safe_str(chat_id)} לרשימת התאוששות!\n"
                f"שגיאה: {e}\n"
                f"הודעת שגיאה: {error_message[:100]}\n"
                f"הודעה מקורית: {(original_user_message or 'אין')[:100]}\n"
                f"⚠️ המשתמש עלול לא לקבל הודעת התאוששות!",
                urgent=True
            )
        except Exception:
            pass

def safe_add_user_to_recovery_list(chat_id: str, error_context: str = "Unknown error", original_message: str = ""):
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.add_user_to_recovery_list() במקום
    """
    try:
        from recovery_manager import add_user_to_recovery_list
        return add_user_to_recovery_list(chat_id, error_context, original_message)
    except ImportError:
        # fallback לקוד הישן
        try:
            if chat_id:
                # העברת ההודעה המקורית רק אם היא לא ריקה
                msg_to_save = original_message.strip() if original_message and original_message.strip() else None
                _add_user_to_critical_error_list(safe_str(chat_id), f"Safe recovery: {error_context}", msg_to_save)
                print(f"🛡️ משתמש {safe_str(chat_id)} נוסף לרשימת התאוששות ({error_context})")
                if msg_to_save:
                    print(f"💾 נשמרה הודעה מקורית: '{msg_to_save[:50]}...'")
        except Exception as e:
            logger.error(f"Failed to add user {safe_str(chat_id)} to recovery list: {e}", source="critical_users_manager")

async def _send_user_friendly_error_message(update, chat_id: str, original_message: str = None):
    """שולח הודעת שגיאה ידידותית למשתמש"""
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        
        error_message = (
            "🤖 אוי, משהו לא בסדר במערכת! \n\n"
            "🔧 אבל אל תדאג - הודעתך נשמרה בצורה בטוחה וכשהמערכת תחזור לפעול "
            "אני אעבד עליה ואשלח לך תשובה מלאה.\n\n"
            "⏰ בדרך כלל זה לוקח כמה דקות לתקן.\n\n"
            "💡 אם זה דחוף, נסה לשלוח שוב עוד כמה דקות."
        )
        
        await bot.send_message(chat_id=chat_id, text=error_message)
        print(f"✅ נשלחה הודעת שגיאה ידידותית למשתמש {chat_id}")
        
        # רישום המשתמש לרשימת ההתאוששות
        safe_add_user_to_recovery_list(chat_id, "Error message sent", original_message)
        
    except Exception as e:
        print(f"🚨 שגיאה בשליחת הודעת שגיאה למשתמש {chat_id}: {e}")
        # לפחות נשמור את המשתמש לרשימת ההתאוששות
        safe_add_user_to_recovery_list(chat_id, f"Failed to send error message: {e}", original_message)

async def send_recovery_messages_to_affected_users():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.send_recovery_messages_to_all_users() במקום
    """
    try:
        from recovery_manager import send_recovery_messages_to_all_users
        return await send_recovery_messages_to_all_users()
    except ImportError:
        # fallback לקוד הישן - רק לוג שהפונקציה הישנה נקראת
        logger.warning("Using deprecated send_recovery_messages_to_affected_users - switch to recovery_manager.py", source="critical_users_manager")
        return 0

async def process_lost_message(original_message: str, chat_id: str) -> str:
    """מעבד הודעה שאבדה בגלל שגיאה"""
    try:
        print(f"🔄 מעבד הודעה אבודה עבור {chat_id}: '{original_message[:50]}...'")
        
        # יבוא פונקציית העיבוד הראשית
        from gpt_a_handler import get_main_response
        
        # ייצירת update מדומה לעיבוד
        mock_update = MockUpdate(original_message, chat_id)
        
        # עיבוד ההודעה
        response = await get_main_response(mock_update, None)
        
        if response and len(response.strip()) > 0:
            print(f"✅ הודעה עובדה בהצלחה עבור {chat_id}")
            return response.strip()
        else:
            print(f"⚠️ לא התקבלה תשובה מהעיבוד עבור {chat_id}")
            return None
            
    except Exception as e:
        print(f"🚨 שגיאה בעיבוד הודעה אבודה עבור {chat_id}: {e}")
        return None

def merge_temporary_critical_files():
    """ממזג קבצים זמניים של משתמשים קריטיים לקובץ הראשי"""
    try:
        data_dir = "data"
        if not os.path.exists(data_dir):
            print("ℹ️ תיקיית data לא קיימת")
            return
        
        main_users = _load_critical_error_users()
        merged_count = 0
        
        for filename in os.listdir(data_dir):
            if filename.startswith("temp_critical_user_") and filename.endswith(".json"):
                temp_file_path = os.path.join(data_dir, filename)
                try:
                    with open(temp_file_path, 'r', encoding='utf-8') as f:
                        temp_data = json.load(f)
                    
                    for chat_id, user_data in temp_data.items():
                        if chat_id not in main_users:
                            main_users[chat_id] = user_data
                            merged_count += 1
                            print(f"✅ מוזג משתמש {chat_id} מקובץ זמני {filename}")
                        else:
                            print(f"ℹ️ משתמש {chat_id} כבר קיים - מדלג")
                    
                    # מחיקת הקובץ הזמני אחרי המיזוג
                    os.remove(temp_file_path)
                    print(f"🗑️ נמחק קובץ זמני {filename}")
                    
                except Exception as e:
                    print(f"⚠️ שגיאה במיזוג קובץ זמני {filename}: {e}")
                    continue
        
        if merged_count > 0:
            _save_critical_error_users(main_users)
            print(f"✅ מוזגו {merged_count} משתמשים מקבצים זמניים")
        else:
            print("ℹ️ לא נמצאו קבצים זמניים למיזוג")
            
    except Exception as e:
        print(f"🚨 שגיאה במיזוג קבצים זמניים: {e}")

def clear_old_critical_error_users(days_old: int = 7):
    """מנקה משתמשים ישנים מרשימת השגיאות הקריטיות"""
    try:
        users_data = _load_critical_error_users()
        if not users_data:
            print("ℹ️ אין משתמשים ברשימת השגיאות הקריטיות")
            return
        
        current_time = get_israel_time()
        cutoff_time = current_time - timedelta(days=days_old)
        
        filtered_users = {}
        removed_count = 0
        
        for chat_id, user_info in users_data.items():
            try:
                timestamp_str = user_info.get("timestamp", "")
                if timestamp_str:
                    user_time = datetime.fromisoformat(timestamp_str.replace("Z", ""))
                    if user_time > cutoff_time:
                        filtered_users[chat_id] = user_info
                    else:
                        removed_count += 1
                        print(f"🗑️ מסיר משתמש ישן {chat_id} ({timestamp_str})")
                else:
                    # אם אין timestamp, נשאיר את המשתמש
                    filtered_users[chat_id] = user_info
                    
            except Exception as e:
                print(f"⚠️ שגיאה בבדיקת זמן למשתמש {chat_id}: {e}")
                # במקרה של שגיאה, נשאיר את המשתמש
                filtered_users[chat_id] = user_info
        
        _save_critical_error_users(filtered_users)
        print(f"✅ נוקה רשימת משתמשים קריטיים - הוסרו {removed_count} משתמשים ישנים")
        
    except Exception as e:
        print(f"🚨 שגיאה בניקוי רשימת משתמשים קריטיים: {e}")

def diagnose_critical_users_system():
    """מאבחן את מערכת המשתמשים הקריטיים"""
    try:
        print("\n🔍 === אבחון מערכת משתמשים קריטיים ===")
        
        # בדיקת קיום הקובץ הראשי
        main_file_exists = os.path.exists(CRITICAL_ERROR_USERS_FILE)
        backup_file_exists = os.path.exists(CRITICAL_ERROR_USERS_FILE + ".backup")
        
        print(f"📁 קובץ ראשי: {'✅ קיים' if main_file_exists else '❌ לא קיים'}")
        print(f"📁 קובץ backup: {'✅ קיים' if backup_file_exists else '❌ לא קיים'}")
        
        # טעינת נתונים
        users_data = _load_critical_error_users()
        print(f"👥 משתמשים ברשימה: {len(users_data)}")
        
        if users_data:
            # סטטיסטיקות
            recovered_count = sum(1 for user in users_data.values() if user.get("recovered", False))
            with_original_message = sum(1 for user in users_data.values() if user.get("original_message"))
            processed_messages = sum(1 for user in users_data.values() if user.get("message_processed", False))
            
            print(f"✅ משתמשים שהתאוששו: {recovered_count}")
            print(f"💬 משתמשים עם הודעה מקורית: {with_original_message}")
            print(f"🔄 הודעות שעובדו: {processed_messages}")
            
            # הצגת 5 המשתמשים האחרונים
            print(f"\n📋 5 משתמשים אחרונים:")
            sorted_users = sorted(users_data.items(), key=lambda x: x[1].get("timestamp", ""), reverse=True)
            for i, (chat_id, user_info) in enumerate(sorted_users[:5], 1):
                timestamp = user_info.get("timestamp", "לא ידוע")
                recovered = "✅" if user_info.get("recovered", False) else "❌"
                has_message = "💬" if user_info.get("original_message") else "📝"
                print(f"  {i}. {chat_id} | {timestamp[:19]} | {recovered} | {has_message}")
        
        # בדיקת קבצים זמניים
        data_dir = "data"
        if os.path.exists(data_dir):
            temp_files = [f for f in os.listdir(data_dir) if f.startswith("temp_critical_user_")]
            print(f"📂 קבצים זמניים: {len(temp_files)}")
            if temp_files:
                print(f"   📝 דוגמאות: {', '.join(temp_files[:3])}{'...' if len(temp_files) > 3 else ''}")
        
        print("🔍 === סיום אבחון ===\n")
        
    except Exception as e:
        print(f"🚨 שגיאה באבחון מערכת משתמשים קריטיים: {e}")

def manual_add_critical_user(chat_id: str, error_context: str = "Manual addition"):
    """מוסיף משתמש באופן ידני לרשימת המשתמשים הקריטיים"""
    try:
        _add_user_to_critical_error_list(safe_str(chat_id), f"Manual: {error_context}")
        print(f"✅ משתמש {safe_str(chat_id)} נוסף ידנית לרשימת המשתמשים הקריטיים")
    except Exception as e:
        print(f"🚨 שגיאה בהוספה ידנית של משתמש {safe_str(chat_id)}: {e}") 

async def handle_critical_error(error, chat_id, user_msg, update: Update):
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py  
    השתמש ב-recovery_manager.add_user_to_recovery_list() במקום
    """
    try:
        from recovery_manager import add_user_to_recovery_list
        add_user_to_recovery_list(chat_id, f"Critical error: {str(error)[:100]}", user_msg)
        logger.error(f"Critical error handled via recovery_manager for user {safe_str(chat_id)}: {error}", source="critical_users_manager")
    except ImportError:
        # fallback לקוד הישן
        logger.error(f"Critical error for user {safe_str(chat_id)}: {error}", source="critical_users_manager")
        
        # שמירת המשתמש לרשימת התאוששות
        _add_user_to_critical_error_list(safe_str(chat_id), f"Critical error: {str(error)[:100]}", user_msg)
        
        # שליחת התראה לאדמין
        try:
            from notifications import send_admin_notification
            send_admin_notification(
                f"🚨 שגיאה קריטית!\n"
                f"👤 משתמש: {safe_str(chat_id)}\n"
                f"💬 הודעה: {user_msg[:100] if user_msg else 'אין'}\n"
                f"🔥 שגיאה: {str(error)[:200]}\n"
                f"⏰ זמן: {get_israel_time().strftime('%H:%M:%S')}\n\n"
                f"✅ המשתמש נוסף לרשימת התאוששות",
                urgent=True
            )
        except Exception as admin_error:
            logger.error(f"Failed to send admin notification: {admin_error}", source="critical_users_manager")

def _load_critical_error_users():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.get_users_needing_recovery() במקום
    """
    try:
        from recovery_manager import get_users_needing_recovery
        users = get_users_needing_recovery()
        # המרה לפורמט הישן לתאימות
        return {user.get('chat_id'): user for user in users}
    except ImportError:
        # fallback לקוד הישן
        return {}

async def send_recovery_messages_to_affected_users():
    """
    🗑️ DEPRECATED: פונקציה זו הוחלפה במודול recovery_manager.py
    השתמש ב-recovery_manager.send_recovery_messages_to_all_users() במקום
    """
    try:
        from recovery_manager import send_recovery_messages_to_all_users
        return await send_recovery_messages_to_all_users()
    except ImportError:
        # fallback לקוד הישן - רק לוג שהפונקציה הישנה נקראת
        logger.warning("Using deprecated send_recovery_messages_to_affected_users - switch to recovery_manager.py", source="critical_users_manager")
        return 0 