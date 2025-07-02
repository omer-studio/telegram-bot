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
from utils import log_error_stat, get_israel_time
import time

# קובץ לעקוב אחרי משתמשים שקיבלו הודעת שגיאה
CRITICAL_ERROR_USERS_FILE = "data/critical_error_users.json"

def _load_critical_error_users():
    """טוען רשימת משתמשים שקיבלו הודעות שגיאה קריטיות"""
    try:
        if os.path.exists(CRITICAL_ERROR_USERS_FILE):
            with open(CRITICAL_ERROR_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ נטען קובץ משתמשים קריטיים עם {len(data)} משתמשים")
                return data
        
        # 🔧 תיקון: בדיקת קובץ backup אם הקובץ הראשי לא קיים
        backup_file = CRITICAL_ERROR_USERS_FILE + ".backup"
        if os.path.exists(backup_file):
            print("⚠️ קובץ ראשי לא קיים, מנסה לטעון מbackup...")
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # שחזור הקובץ הראשי מהbackup
                _save_critical_error_users(data)
                print(f"✅ שוחזר קובץ משתמשים קריטיים מbackup עם {len(data)} משתמשים")
                return data
        
        print("ℹ️ אין קובץ משתמשים קריטיים קיים - מתחיל ברשימה ריקה")
        return {}
    except Exception as e:
        logging.error(f"Error loading critical error users: {e}")
        print(f"🚨 שגיאה בטעינת קובץ משתמשים קריטיים: {e}")
        
        # 🔧 תיקון: ניסיון נוסף עם backup
        try:
            backup_file = CRITICAL_ERROR_USERS_FILE + ".backup"
            if os.path.exists(backup_file):
                print("🔄 מנסה לטעון מקובץ backup...")
                with open(backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"✅ נטען מbackup: {len(data)} משתמשים")
                    return data
        except Exception as backup_error:
            print(f"🚨 גם backup נכשל: {backup_error}")
        
        return {}

def _save_critical_error_users(users_data):
    """שומר רשימת משתמשים שקיבלו הודעות שגיאה קריטיות"""
    try:
        # יצירת תיקייה אם לא קיימת
        os.makedirs(os.path.dirname(CRITICAL_ERROR_USERS_FILE), exist_ok=True)
        
        # 🔧 תיקון: שמירת backup לפני כתיבת הקובץ החדש
        if os.path.exists(CRITICAL_ERROR_USERS_FILE):
            backup_file = CRITICAL_ERROR_USERS_FILE + ".backup"
            try:
                import shutil
                shutil.copy2(CRITICAL_ERROR_USERS_FILE, backup_file)
                print(f"✅ נוצר backup של קובץ המשתמשים הקריטיים")
            except Exception as backup_error:
                print(f"⚠️ נכשל ביצירת backup: {backup_error}")
        
        # כתיבת הקובץ החדש
        with open(CRITICAL_ERROR_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ נשמר קובץ משתמשים קריטיים עם {len(users_data)} משתמשים")
        
        # 🔧 תיקון: אימות שהקובץ נשמר נכון
        try:
            with open(CRITICAL_ERROR_USERS_FILE, 'r', encoding='utf-8') as f:
                verify_data = json.load(f)
                if len(verify_data) != len(users_data):
                    raise Exception(f"File verification failed: expected {len(users_data)} users, got {len(verify_data)}")
            print(f"✅ אומת: הקובץ נשמר נכון עם {len(users_data)} משתמשים")
        except Exception as verify_error:
            print(f"🚨 אימות הקובץ נכשל: {verify_error}")
            # ניסיון לשחזר מbackup
            backup_file = CRITICAL_ERROR_USERS_FILE + ".backup"
            if os.path.exists(backup_file):
                import shutil
                shutil.copy2(backup_file, CRITICAL_ERROR_USERS_FILE)
                print("🔄 שוחזר הקובץ מbackup")
                
    except Exception as e:
        logging.error(f"Error saving critical error users: {e}")
        print(f"🚨 שגיאה בשמירת קובץ משתמשים קריטיים: {e}")
        
        # 🔧 תיקון: ניסיון לשמור בקובץ חירום
        try:
            emergency_file = CRITICAL_ERROR_USERS_FILE + ".emergency"
            with open(emergency_file, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            print(f"⚠️ נשמר בקובץ חירום: {emergency_file}")
        except Exception as emergency_error:
            print(f"🚨 גם שמירת חירום נכשלה: {emergency_error}")

def _add_user_to_critical_error_list(chat_id: str, error_message: str, original_user_message: str = None):
    """מוסיף משתמש לרשימת מי שקיבל הודעת שגיאה קריטית"""
    try:
        users_data = _load_critical_error_users()
        user_data = {
            "timestamp": get_israel_time().isoformat(),
            "error_message": error_message,
            "recovered": False
        }
        
        # 🔧 הוספה: שמירת ההודעה המקורית של המשתמש אם קיימת
        if original_user_message and len(original_user_message.strip()) > 0:
            user_data["original_message"] = original_user_message.strip()
            user_data["message_processed"] = False  # וידוא שהמענה יישלח פעם אחת בלבד
            print(f"💾 נשמרה הודעה מקורית למשתמש {chat_id}: '{original_user_message[:50]}...'")
        
        users_data[str(chat_id)] = user_data
        _save_critical_error_users(users_data)
        logging.info(f"Added user {chat_id} to critical error list")
        print(f"✅ משתמש {chat_id} נוסף לרשימת המשתמשים הקריטיים")
    except Exception as e:
        logging.error(f"Error adding user to critical error list: {e}")
        print(f"🚨 שגיאה בהוספת משתמש {chat_id} לרשימת משתמשים קריטיים: {e}")
        
        # 🔧 תיקון: ניסיון לשמור לפחות ברשימה זמנית
        try:
            temp_data = {
                "timestamp": get_israel_time().isoformat(),
                "error_message": error_message,
                "recovered": False
            }
            if original_user_message:
                temp_data["original_message"] = original_user_message.strip()
                temp_data["message_processed"] = False
                
            temp_file = f"data/temp_critical_user_{chat_id}_{int(time.time())}.json"
            os.makedirs("data", exist_ok=True)
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump({str(chat_id): temp_data}, f, ensure_ascii=False, indent=2)
            print(f"⚠️ נשמר משתמש {chat_id} בקובץ זמני: {temp_file}")
        except Exception as temp_error:
            print(f"🚨 גם שמירה זמנית נכשלה: {temp_error}")
            # לפחות נשלח התראה לאדמין
            try:
                send_admin_notification(
                    f"🚨 CRITICAL: נכשל ברישום משתמש {chat_id} לרשימת התאוששות!\n"
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
    🔧 פונקציה בטוחה לרישום משתמש לרשימת התאוששות
    נקראת בכל מקום שעלולה להיות שגיאה שמונעת מהמשתמש לקבל מענה
    """
    try:
        if chat_id:
            # העברת ההודעה המקורית רק אם היא לא ריקה
            msg_to_save = original_message.strip() if original_message and original_message.strip() else None
            _add_user_to_critical_error_list(str(chat_id), f"Safe recovery: {error_context}", msg_to_save)
            print(f"🛡️ משתמש {chat_id} נוסף לרשימת התאוששות ({error_context})")
            if msg_to_save:
                print(f"💾 נשמרה הודעה מקורית: '{msg_to_save[:50]}...'")
    except Exception as e:
        # גם אם הפונקציה הזו נכשלת - לא נעצור את הקוד
        print(f"⚠️ נכשל ברישום משתמש {chat_id} לרשימת התאוששות: {e}")

async def _send_user_friendly_error_message(update, chat_id: str, original_message: str = None):
    """שולח הודעת שגיאה ידידותית למשתמש"""
    # 🔧 תיקון קריטי: רישום המשתמש לרשימה לפני ניסיון שליחת הודעה!
    try:
        _add_user_to_critical_error_list(chat_id, "User-friendly error message attempt", original_message)
        print(f"✅ משתמש {chat_id} נרשם בבטחה לרשימת התאוששות")
        if original_message:
            print(f"💾 נשמרה הודעה מקורית: '{original_message[:50]}...'")
    except Exception as registration_error:
        print(f"🚨 CRITICAL: נכשל ברישום משתמש {chat_id} לרשימת התאוששות: {registration_error}")
        # גם אם נכשל ברישום - ננסה לפחות לשלוח הודעה
    
    try:
        user_friendly_message = (
            "🙏 מתנצל, יש בעיה - הבוט כרגע לא עובד.\n\n"
            "נסה שוב מאוחר יותר, הודעתי הרגע לעומר והוא יטפל בזה בהקדם. 🔧\n\n"
            "אני אודיע לך ברגע שהכל יחזור לעבוד! 💚"
        )
        
        if update and hasattr(update, 'message') and hasattr(update.message, 'reply_text'):
            # 🐛 DEBUG: שליחה בלי פורמטינג!
            print("=" * 80)
            print("🚨 WARNING: SENDING MESSAGE WITHOUT FORMATTING!")
            print("=" * 80)
            print(f"📝 MESSAGE: {repr(user_friendly_message)}")
            print(f"📊 LENGTH: {len(user_friendly_message)} chars")
            print(f"📊 NEWLINES: {user_friendly_message.count(chr(10))}")
            print(f"📊 DOTS: {user_friendly_message.count('.')}")
            print(f"📊 QUESTIONS: {user_friendly_message.count('?')}")
            print(f"📊 EXCLAMATIONS: {user_friendly_message.count('!')}")
            print("=" * 80)
            from message_handler import send_system_message
            await send_system_message(update, chat_id, user_friendly_message)
        else:
            # אם אין update זמין, ננסה לשלוח ישירות דרך bot API (ללא פורמטינג - רק תשובות GPT-A צריכות פורמטינג)
            bot = telegram.Bot(token=BOT_TOKEN)
            await bot.send_message(chat_id=chat_id, text=user_friendly_message)
        
        logging.info(f"Sent user-friendly error message to user {chat_id}")
        print(f"✅ הודעת שגיאה נשלחה בהצלחה למשתמש {chat_id}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to send user-friendly error message to {chat_id}: {e}")
        print(f"⚠️ שליחת הודעה נכשלה למשתמש {chat_id}, אבל המשתמש כבר נרשם לרשימת התאוששות")
        # 🔧 תיקון: ניסיון נוסף לרישום המשתמש אם השליחה נכשלה
        try:
            _add_user_to_critical_error_list(chat_id, f"Message sending failed: {str(e)[:100]}", original_message)
        except Exception:
            pass  # לא נעצור את התהליך בגלל זה
        return False

async def send_recovery_messages_to_affected_users():
    """שולח הודעות התאוששות לכל המשתמשים שקיבלו הודעות שגיאה"""
    try:
        # 🔧 תיקון: איחוד קבצים זמניים לפני שליחת הודעות
        merge_temporary_critical_files()
        
        # 🚨 הוספה חירום: וידוא שמשתמש 179392777 ברשימה (המשתמש שלא קיבל הודעת התאוששות)
        try:
            emergency_user = "179392777"
            users_data_check = _load_critical_error_users()
            if emergency_user not in users_data_check:
                print(f"🚨 מוסיף משתמש חירום {emergency_user} לרשימת התאוששות...")
                _add_user_to_critical_error_list(emergency_user, "Emergency fix - user reported no recovery message received", "סיימתי את פרק 2")
                print(f"✅ משתמש חירום {emergency_user} נוסף לרשימה")
                send_admin_notification(f"🚨 הוספה חירום: משתמש {emergency_user} נוסף לרשימת התאוששות")
            else:
                print(f"ℹ️ משתמש חירום {emergency_user} כבר ברשימה")
                # בדיקה אם הוא לא התאושש
                if not users_data_check[emergency_user].get("recovered", False):
                    print(f"⚠️ משתמש {emergency_user} ברשימה אבל לא התאושש - יקבל הודעה")
                else:
                    print(f"ℹ️ משתמש {emergency_user} כבר התאושש")
        except Exception as emergency_error:
            print(f"🚨 שגיאה בהוספת משתמש חירום: {emergency_error}")
        
        users_data = _load_critical_error_users()
        
        recovery_message = "👋  היי, חזרתי! הבעיה נפתרה והכל עובד שוב כרגיל. 😊\n\nאפשר לשלוח לי הודעה ואענה כרגיל!"
        
        bot = telegram.Bot(token=BOT_TOKEN)
        recovered_users = []
        failed_users = []
        processed_lost_messages = []
        
        for chat_id, user_info in users_data.items():
            if not user_info.get("recovered", False):
                try:
                    # הודעת התאוששות - ללא פורמטינג (רק תשובות GPT-A צריכות פורמטינג)
                    await bot.send_message(chat_id=chat_id, text=recovery_message)
                    
                    # 💎 טיפול בהודעות אבודות - הקסם החדש!
                    original_message = user_info.get("original_message")
                    message_processed = user_info.get("message_processed", False)
                    
                    if original_message and not message_processed:
                        print(f"💬 נמצאה הודעה אבודה למשתמש {chat_id}: '{original_message[:50]}...'")
                        
                        # מעט השהיה בין הודעות
                        await asyncio.sleep(1)
                        
                        # 🧠 עיבוד ההודעה האבודה
                        try:
                            lost_message_response = await process_lost_message(original_message, chat_id)
                            if lost_message_response:
                                await bot.send_message(chat_id=chat_id, text=lost_message_response)
                                user_info["message_processed"] = True
                                processed_lost_messages.append({
                                    "chat_id": chat_id, 
                                    "message": original_message[:100],
                                    "response_sent": True
                                })
                                print(f"✅ נענה על הודעה אבודה למשתמש {chat_id}")
                            else:
                                print(f"⚠️ לא הצליח לעבד הודעה אבודה למשתמש {chat_id}")
                        except Exception as lost_msg_error:
                            print(f"❌ שגיאה בעיבוד הודעה אבודה למשתמש {chat_id}: {lost_msg_error}")
                            processed_lost_messages.append({
                                "chat_id": chat_id, 
                                "message": original_message[:100],
                                "error": str(lost_msg_error)
                            })
                    
                    user_info["recovered"] = True
                    user_info["recovery_timestamp"] = get_israel_time().isoformat()
                    recovered_users.append(chat_id)
                    logging.info(f"Sent recovery message to user {chat_id}")
                    print(f"✅ נשלחה הודעת התאוששות למשתמש {chat_id}")
                    
                    # מעט השהיה בין הודעות כדי לא לעמוס על טלגרם
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logging.error(f"Failed to send recovery message to {chat_id}: {e}")
                    print(f"⚠️ נכשל בשליחת הודעת התאוששות למשתמש {chat_id}: {e}")
                    failed_users.append({"chat_id": chat_id, "error": str(e)})
        
        # שמירת המצב המעודכן
        _save_critical_error_users(users_data)
        
        # התראה מפורטת לאדמין על מספר ההתאוששויות
        if recovered_users or failed_users or processed_lost_messages:
            admin_message = f"📊 דוח הודעות התאוששות:\n"
            admin_message += f"✅ נשלחו בהצלחה: {len(recovered_users)} משתמשים\n"
            admin_message += f"💬 הודעות אבודות שטופלו: {len(processed_lost_messages)}\n"
            
            if processed_lost_messages:
                admin_message += "\n🔍 פרטי הודעות אבודות:\n"
                for lost_msg in processed_lost_messages[:3]:  # מציג רק 3 ראשונות
                    status = "✅" if lost_msg.get("response_sent") else "❌"
                    admin_message += f"{status} {lost_msg['chat_id']}: {lost_msg['message'][:50]}...\n"
                if len(processed_lost_messages) > 3:
                    admin_message += f"... ועוד {len(processed_lost_messages) - 3} הודעות\n"
            
            if failed_users:
                admin_message += f"\n❌ נכשלו: {len(failed_users)} משתמשים\n"
                admin_message += "פרטי הכשלונות:\n"
                for failure in failed_users[:5]:  # מציג רק 5 ראשונים
                    admin_message += f"- {failure['chat_id']}: {failure['error'][:50]}\n"
                if len(failed_users) > 5:
                    admin_message += f"... ועוד {len(failed_users) - 5} כשלונות\n"
            
            send_admin_notification(admin_message)
        
        return len(recovered_users)
        
    except Exception as e:
        logging.error(f"Error sending recovery messages: {e}")
        print(f"🚨 שגיאה כללית בשליחת הודעות התאוששות: {e}")
        # התראה לאדמין על כשל כללי
        try:
            send_admin_notification(
                f"🚨 כשל כללי בשליחת הודעות התאוששות!\n"
                f"שגיאה: {str(e)[:200]}\n"
                f"⚠️ ייתכן שמשתמשים לא קיבלו הודעות התאוששות!",
                urgent=True
            )
        except Exception:
            pass
        return 0

async def process_lost_message(original_message: str, chat_id: str) -> str:
    """
    🧠 מעבד הודעה אבודה ומחזיר תשובה מתאימה
    בעיקר להודעות פשוטות כמו 'סיימתי את פרק X'
    """
    try:
        print(f"🧠 מעבד הודעה אבודה: '{original_message}' למשתמש {chat_id}")
        
        # זיהוי דפוסים נפוצים בהודעות
        message_lower = original_message.lower().strip()
        
        # זיהוי הודעות של סיום פרקים
        if any(word in message_lower for word in ["סיימתי", "גמרתי", "הושלם"]) and "פרק" in message_lower:
            # חילוץ מספר הפרק אם קיים
            import re
            chapter_match = re.search(r'פרק\s*(\d+)', message_lower)
            if chapter_match:
                chapter_num = chapter_match.group(1)
                response = f"🎉 איזה כיף שסיימת את פרק {chapter_num}! אני גאה בך! 💪\n\nמוכן לקחת הפסקה או לעבור לפרק הבא? אני כאן לעזור לך! ✨"
            else:
                response = "🎉 איזה כיף שסיימת את הפרק! אני גאה בך! 💪\n\nמוכן לקחת הפסקה או לעבור לפרק הבא? אני כאן לעזור לך! ✨"
            
            print(f"✅ זוהתה הודעת סיום פרק, נוצרה תשובה מתאימה")
            return response
        
        # זיהוי הודעות שאלה פשוטות
        elif any(word in message_lower for word in ["איך", "מה", "למה", "איפה", "מתי"]):
            response = "🤔 רואה שיש לך שאלה! מצטער שלא הספקתי לענות קודם בגלל הבעיה הטכנית.\n\nאם אתה רוצה, תוכל לשאול אותה שוב ואענה לך מיד! 😊"
            print(f"✅ זוהתה הודעת שאלה, נוצרה תשובה מתאימה")
            return response
        
        # זיהוי הודעות רגשיות/תמיכה
        elif any(word in message_lower for word in ["קשה", "עזרה", "בעיה", "תקוע", "לא מבין"]):
            response = "🤗 רואה שהיית צריך עזרה! מצטער שלא הייתי זמין בגלל הבעיה הטכנית.\n\nאם אתה עדיין צריך עזרה או תמיכה, אני כאן בשבילך! פשוט כתב לי מה קורה. 💙"
            print(f"✅ זוהתה הודעת תמיכה, נוצרה תשובה מתאימה")
            return response
        
        # תשובה כללית לכל הודעה אחרת
        else:
            response = f"💭 ראיתי שכתבת: '{original_message[:50]}...'\n\nמצטער שלא הספקתי לענות בגלל הבעיה הטכנית! אם זה עדיין רלוונטי, תוכל לכתב לי שוב ואענה מיד! 😊"
            print(f"✅ נוצרה תשובה כללית")
            return response
            
    except Exception as e:
        print(f"❌ שגיאה בעיבוד הודעה אבודה: {e}")
        return "💭 מצטער שלא הספקתי לענות על ההודעה שלך קודם בגלל הבעיה הטכנית! אם זה עדיין רלוונטי, תוכל לכתב לי שוב ואענה מיד! 😊"

def merge_temporary_critical_files():
    """מאחד קבצים זמניים של משתמשים קריטיים לקובץ הראשי"""
    try:
        data_dir = "data"
        if not os.path.exists(data_dir):
            return
        
        main_users_data = _load_critical_error_users()
        temp_files_found = []
        merged_users = 0
        
        # חיפוש קבצים זמניים
        for filename in os.listdir(data_dir):
            if filename.startswith("temp_critical_user_") and filename.endswith(".json"):
                temp_file_path = os.path.join(data_dir, filename)
                temp_files_found.append(temp_file_path)
                
                try:
                    with open(temp_file_path, 'r', encoding='utf-8') as f:
                        temp_data = json.load(f)
                    
                    # איחוד הנתונים
                    for chat_id, user_info in temp_data.items():
                        if chat_id not in main_users_data:
                            main_users_data[chat_id] = user_info
                            merged_users += 1
                            print(f"✅ מוזג משתמש {chat_id} מקובץ זמני")
                        else:
                            print(f"ℹ️ משתמש {chat_id} כבר קיים - מדלג")
                    
                    # מחיקת הקובץ הזמני אחרי איחוד מוצלח
                    os.remove(temp_file_path)
                    print(f"🗑️ נמחק קובץ זמני: {filename}")
                    
                except Exception as file_error:
                    print(f"⚠️ שגיאה בעיבוד קובץ זמני {filename}: {file_error}")
        
        # שמירת הנתונים המאוחדים אם היו שינויים
        if merged_users > 0:
            _save_critical_error_users(main_users_data)
            print(f"✅ אוחדו {merged_users} משתמשים מ-{len(temp_files_found)} קבצים זמניים")
            
            # התראה לאדמין על איחוד
            send_admin_notification(
                f"🔗 אוחדו קבצים זמניים של משתמשים קריטיים:\n"
                f"📁 {len(temp_files_found)} קבצים זמניים\n"
                f"👥 {merged_users} משתמשים נוספו\n"
                f"📊 סה\"כ משתמשים: {len(main_users_data)}"
            )
        elif temp_files_found:
            print(f"ℹ️ נמצאו {len(temp_files_found)} קבצים זמניים אבל לא נדרש איחוד")
        
    except Exception as e:
        print(f"🚨 שגיאה באיחוד קבצים זמניים: {e}")
        # לא נעצור את התהליך בגלל זה

def clear_old_critical_error_users(days_old: int = 7):
    """מנקה משתמשים ישנים מרשימת השגיאות הקריטיות"""
    try:
        users_data = _load_critical_error_users()
        current_time = get_israel_time()
        cleaned_users = {}
        
        for chat_id, user_info in users_data.items():
            try:
                error_time = datetime.fromisoformat(user_info["timestamp"])
                if hasattr(error_time, 'tzinfo') and error_time.tzinfo is None:
                    # אם אין timezone, נניח שזה זמן ישראל
                    import pytz
                    israel_tz = pytz.timezone('Asia/Jerusalem')
                    error_time = israel_tz.localize(error_time)
                
                days_diff = (current_time - error_time).days
                
                # שומר רק אם זה פחות מהמספר ימים הנדרש או שעדיין לא התאושש
                if days_diff < days_old or not user_info.get("recovered", False):
                    cleaned_users[chat_id] = user_info
                    
            except Exception as e:
                logging.error(f"Error processing user {chat_id} in cleanup: {e}")
                # במקרה של שגיאה, שומר את המשתמש
                cleaned_users[chat_id] = user_info
        
        _save_critical_error_users(cleaned_users)
        removed_count = len(users_data) - len(cleaned_users)
        
        if removed_count > 0:
            logging.info(f"Cleaned {removed_count} old critical error users")
        
        return removed_count
        
    except Exception as e:
        logging.error(f"Error in clear_old_critical_error_users: {e}")
        return 0

def write_deploy_commit_to_log(commit):
    """שומר commit של דפלוי בקובץ לוג."""
    log_file = BOT_TRACE_LOG_PATH
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
        requests.post(url, data=data, timeout=10)
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
        notification_text = f"{prefix}\n\n{message}\n\n⏰ {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}"

        url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
            "text": notification_text,
            "parse_mode": "HTML"
        }

        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"[DEBUG] admin_msg | chat={data.get('chat_id', 'N/A')} | status=sent")
        else:
            print(f"[DEBUG] admin_msg | chat={data.get('chat_id', 'N/A')} | status=fail | code={response.status_code}")

    except Exception as e:
        print(f"💥 שגיאה בשליחת הודעה: {e}")

def send_admin_notification_raw(message):
    """שולח הודעה לאדמין בלי הכותרת האוטומטית - רק עם זמן בסוף."""
    try:
        notification_text = f"{message}\n\n⏰ {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}"

        url = f"https://api.telegram.org/bot{ADMIN_BOT_TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": ADMIN_NOTIFICATION_CHAT_ID,
            "text": notification_text,
            "parse_mode": "HTML"
        }

        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"[DEBUG] admin_msg_raw | chat={data.get('chat_id', 'N/A')} | status=sent")
        else:
            print(f"[DEBUG] admin_msg_raw | chat={data.get('chat_id', 'N/A')} | status=fail | code={response.status_code}")

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
        # DEBUG הודעות הוסרו לטובת ביצועים
        error_file = BOT_ERRORS_PATH
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
            requests.post(url, data=data, timeout=10)
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
    # הוספת לוג להודעה נכנסת גם בשגיאות קריטיות
    if chat_id and user_msg and update and update.message:
        print(f"[IN_MSG] chat_id={chat_id} | message_id={update.message.message_id} | text={user_msg.replace(chr(10), ' ')[:120]} (CRITICAL ERROR)")
    
    print(f"🚨 שגיאה קריטית: {error}")
    # DEBUG הודעות הוסרו לטובת ביצועים
    
    # 🔧 הוספה: וידוא רישום המשתמש לרשימת התאוששות גם אם שליחת ההודעה נכשלת
    if chat_id:
        try:
            # רישום למשתמש לרשימת התאוששות לפני ניסיון שליחת הודעה - עם ההודעה המקורית!
            _add_user_to_critical_error_list(str(chat_id), f"Critical error: {str(error)[:100]}", user_msg)
            
            # ניסיון שליחת הודעה ידידותית למשתמש - עם ההודעה המקורית
            await _send_user_friendly_error_message(update, str(chat_id), user_msg)
        except Exception as e:
            # גם אם שליחת ההודעה נכשלת - המשתמש כבר ברשימת ההתאוששות
            logging.error(f"Failed to send user-friendly error message: {e}")
            print(f"⚠️ שליחת הודעה נכשלה, אבל המשתמש {chat_id} נרשם לרשימת התאוששות")
    
    log_error_stat("critical_error")
    
    # התראה מפורטת לאדמין
    admin_error_message = f"🚨 שגיאה קריטית בבוט:\n{str(error)}"
    if chat_id:
        admin_error_message += f"\nמשתמש: {chat_id}"
    if user_msg:
        admin_error_message += f"\nהודעה: {user_msg[:200]}"
    admin_error_message += f"\n⚠️ המשתמש נרשם לרשימת התאוששות ויקבל התראה כשהבוט יחזור לעבוד"
    if user_msg:
        admin_error_message += f"\n💾 ההודעה המקורית נשמרה ותטופל כשהמערכת תחזור לעבוד"
    
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

# 🚨 מערכת התראות אדמין

def send_admin_alert(message, alert_level="info"):
    """שולח התראה לאדמין בטלגרם"""
    try:
        # בחירת אייקון לפי רמת ההתראה
        icon_map = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "critical": "🚨",
            "success": "✅",
            "error": "❌"
        }
        icon = icon_map.get(alert_level, "ℹ️")
        
        timestamp = get_israel_time().strftime("%H:%M:%S")
        
        alert_text = f"{icon} **התראת מערכת** ({timestamp})\n\n{message}"
        
        # 🔧 תיקון: שימוש בפונקציה סינכרונית בטוחה
        _send_telegram_message_admin_sync(BOT_TOKEN, ADMIN_CHAT_ID, alert_text)
        
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

def _send_telegram_message_admin_sync(bot_token, chat_id, text):
    """שולח הודעה בטלגרם (סינכרונית) - תחליף בטוח ל-async"""
    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, data={
            "chat_id": chat_id, 
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=5)
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

from datetime import timedelta

GENTLE_REMINDER_MESSAGE = "היי, רק רציתי לבדוק מה שלומך, מקווה שאתה בטוב. אין לחץ – פשוט רציתי להזכיר לך שאני כאן ואם בא לך לשתף אז... מה שלומך וזה?"
REMINDER_INTERVAL_HOURS = 24
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
    return 7 <= get_israel_time().hour <= 22

def _mark_reminder_delayed(chat_id: str) -> None:
    """מסמן תזכורת כנדחית עד הבוקר."""
    global _reminder_state
    _reminder_state[str(chat_id)] = {
        "reminder_delayed": True,
        "delayed_at": get_israel_time().isoformat(),
        "scheduled_for_morning": True
    }
    _save_reminder_state()

def _mark_reminder_sent(chat_id: str) -> None:
    """מסמן תזכורת כנשלחה וניקוי מצב דחייה."""
    global _reminder_state
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
            current_hour = get_israel_time().hour
            logging.info(f"[REMINDER] ⏰ Delaying reminder for {chat_id} - current time {current_hour:02d}:00 outside 07:00-22:00")
            _mark_reminder_delayed(chat_id)
            return False
        
        # שליחת התזכורת (ללא פורמטינג - רק תשובות GPT-A צריכות פורמטינג)
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
                            except (ValueError, TypeError) as e:
                                logging.debug(f"[AUTO_CLEANUP] Error parsing reminder time for {chat_id}: {e}")
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

def diagnose_critical_users_system():
    """אבחון מלא של מערכת המשתמשים הקריטיים"""
    try:
        print("🔍 מתחיל אבחון מערכת המשתמשים הקריטיים...")
        
        # בדיקת הקובץ הראשי
        main_file_status = {
            "exists": os.path.exists(CRITICAL_ERROR_USERS_FILE),
            "size": 0,
            "users_count": 0,
            "readable": False,
            "last_modified": None
        }
        
        if main_file_status["exists"]:
            try:
                stat_info = os.stat(CRITICAL_ERROR_USERS_FILE)
                main_file_status["size"] = stat_info.st_size
                main_file_status["last_modified"] = time.ctime(stat_info.st_mtime)
                
                with open(CRITICAL_ERROR_USERS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    main_file_status["users_count"] = len(data)
                    main_file_status["readable"] = True
                    main_file_status["users"] = list(data.keys())
                    
                    # ספירת משתמשים שלא התאוששו
                    unrecovered = [uid for uid, info in data.items() if not info.get("recovered", False)]
                    main_file_status["unrecovered_count"] = len(unrecovered)
                    main_file_status["unrecovered_users"] = unrecovered
                    
            except Exception as e:
                main_file_status["error"] = str(e)
        
        # בדיקת קובץ backup
        backup_file = CRITICAL_ERROR_USERS_FILE + ".backup"
        backup_status = {
            "exists": os.path.exists(backup_file),
            "size": 0,
            "users_count": 0,
            "readable": False
        }
        
        if backup_status["exists"]:
            try:
                stat_info = os.stat(backup_file)
                backup_status["size"] = stat_info.st_size
                backup_status["last_modified"] = time.ctime(stat_info.st_mtime)
                
                with open(backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    backup_status["users_count"] = len(data)
                    backup_status["readable"] = True
                    
            except Exception as e:
                backup_status["error"] = str(e)
        
        # בדיקת קבצים זמניים
        temp_files = []
        data_dir = "data"
        if os.path.exists(data_dir):
            for filename in os.listdir(data_dir):
                if filename.startswith("temp_critical_user_") and filename.endswith(".json"):
                    temp_file_path = os.path.join(data_dir, filename)
                    temp_info = {
                        "filename": filename,
                        "path": temp_file_path,
                        "size": os.path.getsize(temp_file_path),
                        "readable": False,
                        "users_count": 0
                    }
                    
                    try:
                        with open(temp_file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            temp_info["users_count"] = len(data)
                            temp_info["readable"] = True
                            temp_info["users"] = list(data.keys())
                    except Exception as e:
                        temp_info["error"] = str(e)
                    
                    temp_files.append(temp_info)
        
        # בדיקת תיקיית data
        data_dir_status = {
            "exists": os.path.exists("data"),
            "writable": False,
            "permissions": None
        }
        
        if data_dir_status["exists"]:
            try:
                # בדיקת הרשאות כתיבה
                test_file = "data/test_write.tmp"
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                data_dir_status["writable"] = True
                data_dir_status["permissions"] = "OK"
            except Exception as e:
                data_dir_status["error"] = str(e)
        
        # דוח מלא
        report = f"""
🔍 דוח אבחון מערכת משתמשים קריטיים:

📁 תיקיית DATA:
   קיימת: {data_dir_status['exists']}
   ניתנת לכתיבה: {data_dir_status['writable']}
   {f"שגיאה: {data_dir_status.get('error', '')}" if 'error' in data_dir_status else ""}

📄 קובץ ראשי ({CRITICAL_ERROR_USERS_FILE}):
   קיים: {main_file_status['exists']}
   גודל: {main_file_status['size']} bytes
   ניתן לקריאה: {main_file_status['readable']}
   משתמשים: {main_file_status['users_count']}
   לא התאוששו: {main_file_status.get('unrecovered_count', 0)}
   {f"שינוי אחרון: {main_file_status.get('last_modified', 'לא ידוע')}" if main_file_status['exists'] else ""}
   {f"שגיאה: {main_file_status.get('error', '')}" if 'error' in main_file_status else ""}

🔄 קובץ Backup:
   קיים: {backup_status['exists']}
   גודל: {backup_status['size']} bytes
   ניתן לקריאה: {backup_status['readable']}
   משתמשים: {backup_status['users_count']}
   {f"שגיאה: {backup_status.get('error', '')}" if 'error' in backup_status else ""}

⏳ קבצים זמניים:
   נמצאו: {len(temp_files)}"""
        
        for temp_file in temp_files:
            report += f"""
   - {temp_file['filename']}: {temp_file['users_count']} משתמשים, {temp_file['size']} bytes"""
            if 'error' in temp_file:
                report += f" (שגיאה: {temp_file['error']})"
        
        if main_file_status.get('unrecovered_users'):
            report += f"""

👥 משתמשים שמחכים להתאוששות:
   {', '.join(main_file_status['unrecovered_users'])}"""
        
        print(report)
        
        # שליחת דוח לאדמין
        send_admin_notification(f"🔍 דוח אבחון מערכת משתמשים קריטיים:{report}")
        
        return {
            "main_file": main_file_status,
            "backup_file": backup_status,
            "temp_files": temp_files,
            "data_dir": data_dir_status
        }
        
    except Exception as e:
        error_msg = f"🚨 שגיאה באבחון מערכת משתמשים קריטיים: {e}"
        print(error_msg)
        send_admin_notification(error_msg, urgent=True)
        return {"error": str(e)}

def manual_add_critical_user(chat_id: str, error_context: str = "Manual addition"):
    """הוספה ידנית של משתמש לרשימת משתמשים קריטיים - לשימוש חירום"""
    try:
        print(f"🔧 הוספה ידנית של משתמש {chat_id} לרשימת התאוששות...")
        _add_user_to_critical_error_list(str(chat_id), f"Manual: {error_context}")
        print(f"✅ משתמש {chat_id} נוסף בהצלחה לרשימת התאוששות")
        
        # אימות שההוספה הצליחה
        users_data = _load_critical_error_users()
        if str(chat_id) in users_data:
            print(f"✅ אומת: משתמש {chat_id} נמצא ברשימה")
            send_admin_notification(f"✅ הוספה ידנית הצליחה: משתמש {chat_id} נוסף לרשימת התאוששות")
            return True
        else:
            print(f"⚠️ משתמש {chat_id} לא נמצא ברשימה אחרי ההוספה!")
            send_admin_notification(f"⚠️ הוספה ידנית נכשלה: משתמש {chat_id} לא נמצא ברשימה", urgent=True)
            return False
            
    except Exception as e:
        error_msg = f"🚨 שגיאה בהוספה ידנית של משתמש {chat_id}: {e}"
        print(error_msg)
        send_admin_notification(error_msg, urgent=True)
        return False


