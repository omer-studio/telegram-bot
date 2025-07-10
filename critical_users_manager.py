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
    """טוען רשימת משתמשים שקיבלו הודעות שגיאה קריטיות מהמסד נתונים"""
    try:
        from profile_utils import get_all_users_with_condition
        
        # קבלת כל המשתמשים שצריכים הודעת התאוששות
        users = get_all_users_with_condition("needs_recovery_message = TRUE")
        
        if not users:
            print("ℹ️ אין משתמשים שצריכים הודעת התאוששות - מתחיל ברשימה ריקה")
            return {}
        
        # המרה לפורמט הישן לתאימות לאחור
        users_data = {}
        for user in users:
            chat_id = user.get('chat_id')
            if chat_id:
                users_data[safe_str(chat_id)] = {
                    "timestamp": user.get('recovery_error_timestamp', ''),
                    "error_message": "Database stored recovery",
                    "recovered": False,
                    "original_message": user.get('recovery_original_message', ''),
                    "message_processed": False
                }
        
        print(f"✅ נטענו {len(users_data)} משתמשים מהמסד נתונים שצריכים הודעת התאוששות")
        return users_data
        
    except Exception as e:
        logging.error(f"Error loading critical error users from database: {e}")
        print(f"🚨 שגיאה בטעינת משתמשים קריטיים ממסד נתונים: {e}")
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
    """מוסיף משתמש לרשימת מי שקיבל הודעת שגיאה קריטית - מסד נתונים"""
    try:
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
    """פונקציה בטוחה לרישום משתמש לרשימת התאוששות"""
    try:
        if chat_id:
            # העברת ההודעה המקורית רק אם היא לא ריקה
            msg_to_save = original_message.strip() if original_message and original_message.strip() else None
            _add_user_to_critical_error_list(safe_str(chat_id), f"Safe recovery: {error_context}", msg_to_save)
            print(f"🛡️ משתמש {safe_str(chat_id)} נוסף לרשימת התאוששות ({error_context})")
            if msg_to_save:
                print(f"💾 נשמרה הודעה מקורית: '{msg_to_save[:50]}...'")
    except Exception as e:
        print(f"🚨 שגיאה ברישום להתאוששות: {e}")

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
    """שולח הודעות התאוששות למשתמשים שחוו שגיאות"""
    try:
        users_data = _load_critical_error_users()
        if not users_data:
            print("ℹ️ אין משתמשים ברשימת ההתאוששות")
            return
            
        print(f"🔄 מתחיל שליחת הודעות התאוששות ל-{len(users_data)} משתמשים...")
        
        from telegram import Bot
        from telegram.error import BadRequest
        bot = Bot(token=BOT_TOKEN)
        
        updated_users = {}
        recovery_count = 0
        
        for chat_id, user_info in users_data.items():
            try:
                if user_info.get("recovered", False):
                    print(f"ℹ️ משתמש {chat_id} כבר התאושש - מדלג")
                    updated_users[chat_id] = user_info
                    continue
                
                # בדיקה אם יש הודעה מקורית לעיבוד
                original_message = user_info.get("original_message", "").strip()
                message_processed = user_info.get("message_processed", False)
                
                if original_message and not message_processed:
                    # עיבוד ההודעה המקורית
                    print(f"🔄 מעבד הודעה מקורית למשתמש {chat_id}: '{original_message[:50]}...'")
                    
                    try:
                        # קריאה לפונקציה שמעבדת הודעות אבודות
                        processed_response = await process_lost_message(original_message, chat_id)
                        
                        if processed_response:
                            # שליחת התשובה המעובדת
                            recovery_message = (
                                "✅ המערכת חזרה לפעול!\n\n"
                                "🔄 עיבדתי את הודעתך שנשלחה קודם:\n"
                                f"💬 \"{original_message[:100]}{'...' if len(original_message) > 100 else ''}\"\n\n"
                                f"{processed_response}\n\n"
                                "🎯 תודה על הסבלנות!"
                            )
                            
                            await bot.send_message(chat_id=chat_id, text=recovery_message)
                            print(f"✅ נשלחה תשובה מעובדת למשתמש {chat_id}")
                            
                            # עדכון שההודעה עובדה
                            user_info["message_processed"] = True
                            user_info["recovery_response_sent"] = True
                            user_info["recovery_timestamp"] = get_israel_time().isoformat()
                            recovery_count += 1
                        else:
                            print(f"⚠️ לא הצלחתי לעבד הודעה למשתמש {chat_id}")
                            # שליחת הודעת התאוששות רגילה
                            recovery_message = (
                                "✅ המערכת חזרה לפעול!\n\n"
                                "🔄 ראיתי שניסית לשלוח הודעה קודם כשהייתה תקלה.\n"
                                "💬 אשמח אם תשלח שוב את מה שרצית לשאול - עכשיו הכל עובד תקין!\n\n"
                                "🎯 תודה על הסבלנות!"
                            )
                            
                            await bot.send_message(chat_id=chat_id, text=recovery_message)
                            print(f"✅ נשלחה הודעת התאוששות רגילה למשתמש {chat_id}")
                            
                            user_info["recovery_response_sent"] = True
                            user_info["recovery_timestamp"] = get_israel_time().isoformat()
                            recovery_count += 1
                            
                    except Exception as processing_error:
                        print(f"⚠️ שגיאה בעיבוד הודעה למשתמש {chat_id}: {processing_error}")
                        # שליחת הודעה רגילה במקום
                        recovery_message = (
                            "✅ המערכת חזרה לפעול!\n\n"
                            "💬 אשמח אם תשלח שוב את מה שרצית לשאול - עכשיו הכל עובד תקין!\n\n"
                            "🎯 תודה על הסבלנות!"
                        )
                        
                        await bot.send_message(chat_id=chat_id, text=recovery_message)
                        print(f"✅ נשלחה הודעת התאוששות חלופית למשתמש {chat_id}")
                        
                        user_info["recovery_response_sent"] = True
                        user_info["recovery_timestamp"] = get_israel_time().isoformat()
                        recovery_count += 1
                else:
                    # אין הודעה מקורית או שכבר עובדה - שליחת הודעה רגילה
                    recovery_message = (
                        "✅ המערכת חזרה לפעול!\n\n"
                        "💬 אשמח אם תשלח שוב את מה שרצית לשאול - עכשיו הכל עובד תקין!\n\n"
                        "🎯 תודה על הסבלנות!"
                    )
                    
                    await bot.send_message(chat_id=chat_id, text=recovery_message)
                    print(f"✅ נשלחה הודעת התאוששות למשתמש {chat_id}")
                    
                    user_info["recovery_response_sent"] = True
                    user_info["recovery_timestamp"] = get_israel_time().isoformat()
                    recovery_count += 1
                
                # עדכון שהמשתמש התאושש
                user_info["recovered"] = True
                updated_users[chat_id] = user_info
                
                # מניעת spam - המתנה בין הודעות
                await asyncio.sleep(2)
                
            except BadRequest as e:
                if "chat not found" in str(e).lower() or "user is deactivated" in str(e).lower():
                    print(f"⚠️ משתמש {chat_id} חסום/לא קיים - מסיר מהרשימה")
                    # לא נוסיף אותו לרשימה המעודכנת
                    continue
                else:
                    print(f"⚠️ שגיאת Telegram למשתמש {chat_id}: {e}")
                    # נשאיר ברשימה לניסיון מאוחר יותר
                    updated_users[chat_id] = user_info
                    
            except Exception as e:
                print(f"⚠️ שגיאה בשליחת הודעת התאוששות למשתמש {chat_id}: {e}")
                # נשאיר ברשימה לניסיון מאוחר יותר
                updated_users[chat_id] = user_info
        
        # שמירת הרשימה המעודכנת
        _save_critical_error_users(updated_users)
        
        print(f"✅ הושלמה שליחת הודעות התאוששות - {recovery_count} משתמשים התאוששו")
        
        # שליחת דיווח לאדמין
        from admin_notifications import send_admin_notification
        send_admin_notification(
            f"✅ התאוששות הושלמה!\n"
            f"📊 {recovery_count} משתמשים קיבלו הודעת התאוששות\n"
            f"📋 {len(updated_users)} משתמשים נשארו ברשימה"
        )
        
    except Exception as e:
        print(f"🚨 שגיאה כללית בשליחת הודעות התאוששות: {e}")
        try:
            from admin_notifications import send_admin_notification
            send_admin_notification(f"🚨 שגיאה בהתאוששות: {e}", urgent=True)
        except:
            pass

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
    מטפל בשגיאות קריטיות - שגיאות שמונעות מהבוט לענות למשתמש
    """
    # הוספת לוג להודעה נכנסת גם בשגיאות קריטיות
    if chat_id and user_msg and update and update.message:
        print(f"[IN_MSG] chat_id={safe_str(chat_id)} | message_id={update.message.message_id} | text={user_msg.replace(chr(10), ' ')[:120]} (CRITICAL ERROR)")
    
    print(f"🚨 שגיאה קריטית: {error}")
    # DEBUG הודעות הוסרו לטובת ביצועים
    
    # 🔧 הוספה: וידוא רישום המשתמש לרשימת התאוששות גם אם שליחת ההודעה נכשלת
    if chat_id:
        try:
            # רישום למשתמש לרשימת התאוששות לפני ניסיון שליחת הודעה - עם ההודעה המקורית!
            _add_user_to_critical_error_list(safe_str(chat_id), f"Critical error: {str(error)[:100]}", user_msg)
            
            # ניסיון שליחת הודעה ידידותית למשתמש - עם ההודעה המקורית
            await _send_user_friendly_error_message(update, safe_str(chat_id), user_msg)
        except Exception as e:
            # גם אם שליחת ההודעה נכשלת - המשתמש כבר ברשימת ההתאוששות
            logging.error(f"Failed to send user-friendly error message: {e}")
            print(f"⚠️ שליחת הודעה נכשלה, אבל המשתמש {safe_str(chat_id)} נרשם לרשימת התאוששות")
    
    log_error_stat("critical_error")
    
    # התראה מפורטת לאדמין
    admin_error_message = f"🚨 שגיאה קריטית בבוט:\n{str(error)}"
    if chat_id:
        admin_error_message += f"\nמשתמש: {safe_str(chat_id)}"
    if user_msg:
        admin_error_message += f"\nהודעה: {user_msg[:200]}"
    admin_error_message += f"\n⚠️ המשתמש נרשם לרשימת התאוששות ויקבל התראה כשהבוט יחזור לעבוד"
    if user_msg:
        admin_error_message += f"\n💾 ההודעה המקורית נשמרה ותטופל כשהמערכת תחזור לעבוד"
    
    # ייבוא delayed כדי למנוע circular imports
    from notifications import send_error_notification, log_error_to_file
    
    send_error_notification(
        error_message=admin_error_message,
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