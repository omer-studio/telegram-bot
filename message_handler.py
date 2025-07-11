"""
message_handler.py
------------------
קובץ זה מרכז את כל הטיפול בהודעות ושליחה של הודעות.
הרציונל: ריכוז כל ניהול ההודעות, שגיאות, וחוויית משתמש במקום אחד.
"""

import asyncio
import re
import json
import time
import psycopg2

# 🚀 יבוא המערכת החדשה - פשוטה ועקבית
from simple_config import config, TimeoutConfig
from simple_logger import logger
from simple_data_manager import data_manager
from db_manager import safe_str, safe_operation

from utils import get_israel_time
from chat_utils import log_error_stat, update_chat_history, get_chat_history_messages, get_chat_history_for_users, get_chat_history_for_gpt, update_last_bot_message
# Telegram types (ignored if telegram package absent in testing env)
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove  # type: ignore
from telegram.ext import ContextTypes  # type: ignore
from datetime import datetime
# 🗑️ handle_secret_command הוסרה - עברנו לפקודות טלגרם רגילות
from config import should_log_message_debug, should_log_debug_prints
from messages import get_welcome_messages, get_retry_message_by_attempt, approval_text, approval_keyboard, APPROVE_BUTTON_TEXT, DECLINE_BUTTON_TEXT, code_approved_message, code_not_received_message, not_approved_message, nice_keyboard, nice_keyboard_message, remove_keyboard_message, full_access_message, error_human_funny_message, get_unsupported_message_response, get_code_request_message
# 🗑️ הסרת כל הייבואים מ-sheets_handler - עברנו למסד נתונים!
# ✅ החלפה לפונקציות מסד נתונים ו-profile_utils  
import profile_utils as _pu
from gpt_a_handler import get_main_response
from gpt_b_handler import get_summary
from gpt_c_handler import extract_user_info, should_run_gpt_c
from gpt_d_handler import smart_update_profile_with_gpt_d_async
from gpt_utils import normalize_usage_dict
try:
    from fields_dict import FIELDS_DICT
except ImportError:
    FIELDS_DICT = {"dummy": "dummy"}
from gpt_e_handler import execute_gpt_e_if_needed
from concurrent_monitor import start_monitoring_user, update_user_processing_stage, end_monitoring_user
from notifications import mark_user_active
from recovery_manager import add_user_to_recovery_list, update_last_message_time
from chat_utils import should_send_time_greeting, get_time_greeting_instruction
from prompts import SYSTEM_PROMPT
import traceback
# 🆕 פונקציות חדשות למסד נתונים - לפי המדריך!
import db_manager
from db_manager import register_user_with_code_db, check_user_approved_status_db, approve_user_db_new, increment_code_try_db_new, save_gpt_chat_message

from chat_utils import get_weekday_context_instruction, get_holiday_system_message



def _extract_message_data(update):
    """
    חילוץ נתונים בסיסיים מההודעה - ללא לוגיקה מורכבת
    """
    if not update or not hasattr(update, 'message') or not update.message:
        return None, None, None, None, None, None, False
    
    message = update.message
    return (
        message.chat_id,
        message.message_id, 
        message.text or "",
        getattr(message, 'voice', None),
        getattr(message, 'document', None),
        getattr(message, 'photo', None),
        True
    )

def _determine_message_type(voice, document, photo, text):
    """
    קביעת סוג הודעה - לוגיקה פשוטה וברורה
    """
    if voice:
        return "voice"
    elif document:
        return "document"
    elif photo:
        return "photo"
    elif text and text.strip():
        return "text"
    else:
        return "unknown"

def safe_extract_message_info(update):
    """
    🔧 פונקציה מרכזית לחילוץ בטוח של chat_id, message_id ותוכן הודעה
    מחזירה: (chat_id, message_id, message_text, message_type, success)
    """
    try:
        # חילוץ נתונים
        chat_id, message_id, text, voice, document, photo, success = _extract_message_data(update)
        
        if not success:
            return None, None, None, "unknown", False
        
        # קביעת סוג הודעה
        message_type = _determine_message_type(voice, document, photo, text)
        
        # 🔧 DEBUG: לוגים לבדיקת הודעה (רק בדיבאג)
        if should_log_debug_prints():
            logger.info(f"[DEBUG_MESSAGE_TYPE] chat_id={safe_str(chat_id)}, message_id={message_id}", source="message_handler")
            logger.info(f"[DEBUG_MESSAGE_TYPE] message_text={repr(text)}", source="message_handler")
            logger.info(f"[DEBUG_MESSAGE_TYPE] voice: {voice is not None}, document: {document is not None}, photo: {photo is not None}", source="message_handler")
            logger.info(f"[DEBUG_MESSAGE_TYPE] FINAL message_type: {message_type}", source="message_handler")
        
        return chat_id, message_id, text, message_type, True
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בחילוץ מידע הודעה: {e}", source="message_handler")
        return None, None, None, "error", False

async def send_approval_message(update, chat_id):
    """
    שולחת הודעת אישור למשתמש חדש
    """
    try:
        approval_msg = approval_text() + "\n\nאנא לחץ על 'מאשר' או 'לא מאשר' במקלדת למטה."
        await asyncio.wait_for(
            update.message.reply_text(
                approval_msg,
                reply_markup=ReplyKeyboardMarkup(approval_keyboard(), one_time_keyboard=True, resize_keyboard=True)
            ),
            timeout=TimeoutConfig.TELEGRAM_SEND_TIMEOUT
        )
        # 🚀 הודעת אישור נשלחה! עדכון היסטוריה יתבצע ברקע להאצת זמן תגובה
        logger.info("הודעת אישור נשלחה", source="message_handler", chat_id=chat_id)
        
    except Exception as e:
        logger.error(f"❌ שליחת הודעת אישור נכשלה: {e}", source="message_handler")
        await send_system_message(update, chat_id, approval_msg)



async def _handle_holiday_check(update, chat_id, bot_reply):
    """
    🔧 בדיקה ושליחת הודעות חגים מיוחדים אם רלוונטי
    """
    try:
        from chat_utils import get_holiday_system_message
        
        holiday_message = get_holiday_system_message(safe_str(chat_id), bot_reply)
        if holiday_message:
            await send_system_message(update, chat_id, holiday_message)
            
    except Exception as holiday_err:
        logger.warning(f"⚠️ שגיאה בבדיקת חגים: {holiday_err}", source="message_handler")

async def send_message(update, chat_id, text, is_bot_message=True, is_gpt_a_response=False):
    """
    שולחת הודעה למשתמש בטלגרם, כולל לוגים ועדכון היסטוריה.
    קלט: update (אובייקט טלגרם), chat_id (int), text (str), is_bot_message (bool), is_gpt_a_response (bool)
    פלט: מחזיר את הזמן הדיוק שההודעה נשלחה בפועל לטלגרם
    # מהלך מעניין: עדכון היסטוריה ולוגים רק אם ההודעה נשלחה בהצלחה.
    """
    
    # 🚨 CRITICAL SECURITY CHECK: מנע שליחת הודעות פנימיות למשתמש!
    if text and ("[עדכון פרופיל]" in text or "[PROFILE_CHANGE]" in text or 
                 (text.startswith("[") and "]" in text and any(keyword in text for keyword in ["עדכון", "debug", "admin", "system"]))):
        logger.critical(f"🚨 BLOCKED INTERNAL MESSAGE TO USER! chat_id={safe_str(chat_id)} | text={text[:100]}", source="message_handler")
        print(f"🚨🚨🚨 CRITICAL: חסימת הודעה פנימית למשתמש! chat_id={safe_str(chat_id)}")
        return
    
    # שליחת טקסט כמו שהוא, ללא עיבוד מיוחד
    formatted_text = text
    
    # 🔧 תיקון קריטי: Progressive timeout מהיר יותר
    telegram_send_time = None  # זמן השליחה בפועל לטלגרם
    
    try:
        max_retries = 3  # פחות ניסיונות
        timeout_seconds = [TimeoutConfig.TELEGRAM_SEND_TIMEOUT, TimeoutConfig.TELEGRAM_SEND_TIMEOUT * 1.5, TimeoutConfig.TELEGRAM_SEND_TIMEOUT * 2]  # timeouts מהירים יותר!
        
        for attempt in range(max_retries + 1):
            current_timeout = timeout_seconds[min(attempt, len(timeout_seconds) - 1)]
            try:
                # שליחה עם timeout מהיר
                sent_message = await asyncio.wait_for(
                    update.message.reply_text(formatted_text, parse_mode="HTML"),
                    timeout=current_timeout
                )
                
                # 🔧 מדידת זמן דיוק של שליחה בפועל לטלגרם
                telegram_send_time = time.time()
                
                logger.info(f"✅ [TELEGRAM_REPLY] הצלחה בניסיון {attempt + 1} | chat_id={safe_str(chat_id)}", source="message_handler")
                break  # הצלחה - יוצאים מהלולאה
                
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    logger.warning(f"⏰ [TIMEOUT] ניסיון {attempt + 1} נכשל אחרי {current_timeout}s", source="message_handler")
                    continue
                else:
                    raise Exception(f"Telegram timeout after {max_retries + 1} attempts")
                    
            except Exception as e:
                if attempt < max_retries and ("network" in str(e).lower() or "timeout" in str(e).lower()):
                    continue
                else:
                    raise e
        else:
            raise Exception(f"Failed to send message after {max_retries + 1} attempts")
                     
    except Exception as e:
        logger.error(f"❌ [SEND_ERROR] שליחת הודעה נכשלה: {e}", source="message_handler")
        try:
            from notifications import send_error_notification
            send_error_notification(error_message=f"[send_message] שליחת הודעה נכשלה: {e}", chat_id=safe_str(chat_id), user_msg=formatted_text)
            # גם נוסיף את המשתמש לרשימת התאוששות
            add_user_to_recovery_list(safe_str(chat_id), f"Failed to send message: {e}", formatted_text)
        except Exception as notify_err:
            logger.error(f"❌ [NOTIFY_ERROR] התראה לאדמין נכשלה: {notify_err}", source="message_handler")
        return None  # החזרת None במקרה של כשלון
    
    # 🚀 הודעה נשלחה בהצלחה! עדכון היסטוריה מועבר לרקע להאצת זמן תגובה
    # עדכון ההיסטוריה יתבצע ברקע ב-handle_background_tasks
    
    logger.info(f"📤 [SENT] הודעה נשלחה | chat_id={safe_str(chat_id)}", source="message_handler")
    
    # החזרת זמן השליחה הדיוק לטלגרם
    return telegram_send_time



async def handle_background_tasks(update, context, chat_id, user_msg, bot_reply, message_id, user_request_start_time, gpt_result, history_messages, messages_for_gpt, user_response_actual_time):
    """
    🔧 פונקציה חדשה: מטפלת בכל המשימות ברקע אחרי שהמשתמש קיבל תשובה
    זה מבטיח שהמשתמש מקבל תשובה מהר, וכל השאר קורה ברקע
    """
    try:
        # 🚀 שלב 0: עיבוד GPT-A ברקע (עלויות, מטריקות, לוגים)
        try:
            if isinstance(gpt_result, dict) and gpt_result.get("background_data"):
                from gpt_a_handler import process_gpt_a_background_tasks
                process_gpt_a_background_tasks(gpt_result, chat_id, message_id)
        except Exception as gpt_a_bg_err:
            logger.warning(f"[BACKGROUND] שגיאה בעיבוד GPT-A ברקע: {gpt_a_bg_err}", source="message_handler")
        
        # הקריאה לsend_anonymous_chat_notification הועברה למקום הנכון אחרי עיבוד כל הGPT

        # 🔧 תיקון: שימוש בזמן התגובה האמיתי
        response_time = user_response_actual_time
        
        # 💾 שמירת זמן תגובה כולל למסד הנתונים
        try:
            from db_manager import save_system_metrics
            save_system_metrics(
                metric_type="response_time",
                chat_id=safe_str(chat_id),
                response_time_seconds=response_time,
                additional_data={
                    "message_id": message_id,
                    "user_msg_length": len(user_msg),
                    "bot_msg_length": len(bot_reply) if bot_reply else 0,
                    "background_processing": True
                }
            )
        except Exception as save_err:
            logger.warning(f"Could not save response time metrics: {save_err}", source="message_handler")
        
        background_data = {
            "chat_id": safe_str(chat_id),
            "message_id": message_id,
            "user_msg": user_msg,
            "bot_reply": bot_reply,
            "response_time": response_time,
            "timestamp": datetime.utcnow().isoformat(),
            "processing_stage": "background"
        }
        
        logger.info(f"✅ [BACKGROUND] כל משימות הרקע הושלמו | chat_id={safe_str(chat_id)} | זמן תגובה סופי: {response_time:.2f}s", source="message_handler")
        
        # שלב 1: עדכון היסטוריה (הועבר לכאן לצמצום פער הקוד)
        # 🔧 תיקון קריטי: הסרת כפילות שמירה - רק save_gpt_chat_message ישמור הכל
        # try:
        #     # עדכון ההיסטוריה המלא - כל ההודעות
        #     update_chat_history(safe_str(chat_id), user_msg, bot_reply)
        #     logger.info(f"[BACKGROUND] היסטוריה עודכנה | chat_id={safe_str(chat_id)}", source="message_handler")
        # except Exception as hist_err:
        #     logger.warning(f"[BACKGROUND] שגיאה בעדכון היסטוריה: {hist_err}", source="message_handler")
        
        # 🔧 ההסבר: הסרתי את update_chat_history כדי למנוע כפילויות עם save_gpt_chat_message
        
        # 🔧 תיקון: טעינת היסטוריה מחדש אחרי השמירה כדי שהמונה יעלה
        # ❌ BAG FIX: אל לדרוס את history_messages המקורי שנשלח ל-GPT!
        # זה גורם ל"אין היסטוריה" בהתראה לאדמין
        try:
            from chat_utils import get_chat_history_for_users
            updated_history_messages = get_chat_history_for_users(safe_str(chat_id), limit=32)
            # ✅ שמירת ההיסטוריה המקורית שנשלחה ל-GPT במשתנה נפרד
            original_history_messages = history_messages  # ההיסטוריה שבאמת נשלחה ל-GPT
            original_messages_for_gpt = messages_for_gpt  # ההודעות שבאמת נשלחו ל-GPT
            
            # רק לצורך הלוגינג נשתמש בהיסטוריה המעודכנת
            updated_history_for_logging = updated_history_messages if updated_history_messages else []
            print(f"🔄 [BACKGROUND] היסטוריה מקורית ל-GPT: {len(original_history_messages)} | היסטוריה מעודכנת ללוגים: {len(updated_history_for_logging)}")
        except Exception as hist_reload_err:
            logger.warning(f"[BACKGROUND] שגיאה בטעינת היסטוריה מחדש: {hist_reload_err}", source="message_handler")
            # במקרה של שגיאה, נשמור את המקוריים
            original_history_messages = history_messages
            original_messages_for_gpt = messages_for_gpt
            updated_history_for_logging = history_messages  # ✅ נשתמש במקורי גם ללוגים

        # שלב 2: הפעלת GPT-B ליצירת סיכום (אם התשובה ארוכה מספיק)
        summary_result = None
        summary_usage = {}
        if len(bot_reply) > 100:
            try:
                summary_result = get_summary(user_msg, bot_reply, safe_str(chat_id), message_id)
                if summary_result and isinstance(summary_result, dict):
                    summary_usage = summary_result.get("usage", {})
                    print(f"📝 [BACKGROUND] נוצר סיכום: {summary_result.get('summary', '')[:50]}...")
            except Exception as summary_err:
                logger.warning(f"[BACKGROUND] שגיאה ביצירת סיכום: {summary_err}", source="message_handler")
        
        # שלב 3: הפעלה במקביל של כל התהליכים
        all_tasks = []
        gpt_c_result = None
        
        if should_run_gpt_c(user_msg):
            gpt_c_result = await asyncio.to_thread(extract_user_info, user_msg, safe_str(chat_id))
        
        all_tasks.append(smart_update_profile_with_gpt_d_async(safe_str(chat_id), user_msg, bot_reply, gpt_c_result))
        all_tasks.append(execute_gpt_e_if_needed(safe_str(chat_id)))
        
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        # שחזור תוצאות GPT-D ו-GPT-E
        gpt_d_result = results[0] if len(results) > 0 else None
        gpt_e_result = results[1] if len(results) > 1 else None
        
        # 🔧 **הועבר לסוף**: ההתראה לאדמין תישלח רק אחרי שכל הדברים הסתיימו
        
        # שלב 4: רישום למסד נתונים
        try:
            # איסוף נתונים מלאים לרישום  
            # ✅ השתמש בפונקציה מהמסד נתונים
            from profile_utils import get_user_summary_fast
            current_summary = get_user_summary_fast(safe_str(chat_id)) or ""
            from chat_utils import get_chat_history_for_users
            history_messages = get_chat_history_for_users(safe_str(chat_id), limit=32)
            
            # בניית הודעות מלאות לרישום
            messages_for_log = [{"role": "system", "content": SYSTEM_PROMPT}]
            if current_summary:
                messages_for_log.append({"role": "system", "content": f"🎯 מידע על המשתמש: {current_summary}"})
            # ✅ השתמש בהיסטוריה המעודכנת רק ללוגים במסד נתונים
            if updated_history_for_logging:
                messages_for_log.extend(updated_history_for_logging)
            messages_for_log.append({"role": "user", "content": user_msg})
            
            # ✅ רישום למסד נתונים עם מספר סידורי (שמירה קיימת)
            save_result = save_gpt_chat_message(
                chat_id=safe_str(chat_id),
                user_msg=user_msg,
                bot_msg=bot_reply,
                gpt_data={
                    "message_id": message_id,
                    "reply_summary": summary_result.get("summary", "") if summary_result else "",
                    "main_usage": gpt_result.get("usage", {}) if isinstance(gpt_result, dict) else {},
                    "summary_usage": summary_usage,
                    "extract_usage": gpt_c_result.get("usage", {}) if gpt_c_result and isinstance(gpt_c_result, dict) else {},
                    "total_tokens": gpt_result.get("usage", {}).get("total_tokens", 0) if isinstance(gpt_result, dict) else 0,
                    "cost_usd": gpt_result.get("usage", {}).get("cost_total", 0) if isinstance(gpt_result, dict) else 0,
                    "cost_ils": gpt_result.get("usage", {}).get("cost_total_ils", 0) if isinstance(gpt_result, dict) else 0
                }
            )
            
            # שמירת המספר הסידורי לשימוש בהתראות
            interaction_message_number = save_result.get('interaction_message_number') if isinstance(save_result, dict) else None
            
            logger.info(f"💾 [BACKGROUND] נשמר למסד נתונים | chat_id={safe_str(chat_id)} | הודעה #{interaction_message_number}", source="message_handler")
            
            # 🔥 רישום למסד החדש interactions_log - הטבלה המרכזית החדשה!
            try:
                from interactions_logger import log_interaction
                
                # חישוב זמנים
                total_background_time = time.time() - user_request_start_time
                timing_data = {
                    'user_to_bot': response_time,
                    'total': total_background_time
                }
                
                # איסוף תוצאות GPT
                gpt_results = {
                    'a': gpt_result,
                    'b': summary_result,
                    'c': gpt_c_result,
                    'd': results[0] if len(results) > 0 else None,
                    'e': results[1] if len(results) > 1 else None
                }
                
                # חישוב מונה GPT-E
                gpt_e_counter = None
                if gpt_results['e'] and isinstance(gpt_results['e'], dict) and gpt_results['e'].get("success"):
                    try:
                        from chat_utils import get_total_user_messages_count
                        from gpt_e_handler import GPT_E_RUN_EVERY_MESSAGES
                        total_messages = get_total_user_messages_count(safe_str(chat_id))
                        current_count = total_messages % GPT_E_RUN_EVERY_MESSAGES
                        gpt_e_counter = f"{current_count}/{GPT_E_RUN_EVERY_MESSAGES}"
                    except:
                        gpt_e_counter = None
                
                # רישום האינטראקציה המלאה
                log_success = log_interaction(
                    chat_id=chat_id,
                    telegram_message_id=str(message_id),
                    user_msg=user_msg,
                    bot_msg=bot_reply,
                    messages_for_gpt=original_messages_for_gpt or messages_for_log,
                    gpt_results=gpt_results,
                    timing_data=timing_data,
                    gpt_e_counter=gpt_e_counter
                )
                
                if log_success:
                    print(f"🔥 [INTERACTIONS_LOG] אינטראקציה נרשמה בטבלה המרכזית החדשה | chat_id={safe_str(chat_id)}")
                
            except Exception as interactions_log_err:
                logger.warning(f"[INTERACTIONS_LOG] שגיאה ברישום לטבלה המרכזית: {interactions_log_err}", source="message_handler")
            
        except Exception as log_exc:
            logger.error(f"❌ [BACKGROUND] שגיאה ברישום למסד נתונים: {log_exc}", source="message_handler")
        
        # שלב 5: רישום למסד נתונים (לתחזוקת הדוחות היומיים)
        try:
            # ✅ הלוגים נשמרים אוטומטית למסד נתונים
            # חישוב עלות כוללת
            total_cost_ils = 0
            if isinstance(gpt_result, dict) and gpt_result.get("usage"):
                total_cost_ils += gpt_result["usage"].get("cost_total_ils", 0)
            if summary_usage:
                total_cost_ils += summary_usage.get("cost_total_ils", 0)
            if gpt_c_result and isinstance(gpt_c_result, dict) and gpt_c_result.get("usage"):
                total_cost_ils += gpt_c_result["usage"].get("cost_total_ils", 0)
            
            # ✅ הלוגים נשמרים אוטומטית למסד הנתונים
            logger.info(f"📝 [BACKGROUND] נשמר למסד נתונים | chat_id={safe_str(chat_id)}", source="message_handler")
            
        except Exception as log_file_exc:
            logger.error(f"❌ [BACKGROUND] שגיאה ברישום למסד נתונים: {log_file_exc}", source="message_handler")
        
        # 🔍 לוג שקט לבדיקות (ללא הודעות לאדמין)
        if should_log_debug_prints():
            ran_components = []
            if should_run_gpt_c(user_msg) and gpt_c_result is not None:
                ran_components.append("GPT-C")
            if len(results) > 0 and results[0] is not None:
                ran_components.append("GPT-D")
            if len(results) > 1 and results[1] is not None:
                ran_components.append("GPT-E")
            
            if ran_components:
                print(f"[DEBUG] 🛠️ הרצת מעבדי פרופיל ברקע: {', '.join(ran_components)} | chat_id={safe_str(chat_id)}")
        
        logger.info(f"✅ [BACKGROUND] סיום משימות ברקע | chat_id={safe_str(chat_id)} | זמן תגובה אמיתי: {response_time:.2f}s | זמן כולל כולל רקע: {time.time() - user_request_start_time:.2f}s", source="message_handler")
        
        # שלב 5: התראות אדמין (אם יש שינויים)
        try:
            from unified_profile_notifications import send_profile_update_notification
            from profile_utils import _detect_profile_changes, get_user_profile_fast, get_user_summary_fast
            
            # 🔧 תיקון: שמירת הפרופיל הישן לפני כל העדכונים
            old_profile_before_updates = get_user_profile_fast(safe_str(chat_id))
            
            gpt_c_changes_list = []
            gpt_d_changes_list = []
            gpt_e_changes_list = []
            
            # GPT-C changes
            if should_run_gpt_c(user_msg) and gpt_c_result is not None and not isinstance(gpt_c_result, Exception):
                extracted_fields = gpt_c_result.get("extracted_fields", {}) if isinstance(gpt_c_result, dict) else {}
                new_profile = {**old_profile_before_updates, **extracted_fields}
                changes = _detect_profile_changes(old_profile_before_updates, new_profile)
                for change in changes:
                    gpt_c_changes_list.append({
                        'field': change['field'],
                        'old_value': change['old_value'] or 'ריק',
                        'new_value': change['new_value']
                    })
            
            # GPT-D changes
            gpt_d_res = results[0] if len(results) > 0 else None
            if gpt_d_res is not None and not isinstance(gpt_d_res, Exception):
                updated_profile, usage = gpt_d_res if isinstance(gpt_d_res, tuple) else (None, {})
                if updated_profile and isinstance(updated_profile, dict):
                    changes = _detect_profile_changes(old_profile_before_updates, updated_profile)
                    for change in changes:
                        gpt_d_changes_list.append({
                            'field': change['field'],
                            'old_value': change['old_value'] or 'ריק',
                            'new_value': change['new_value']
                        })
            
            # GPT-E changes
            gpt_e_res = results[1] if len(results) > 1 else None
            gpt_e_counter = None
            if gpt_e_res is not None and not isinstance(gpt_e_res, Exception):
                changes_dict = gpt_e_res.get("changes", {}) if isinstance(gpt_e_res, dict) else {}
                if changes_dict:
                    new_profile = {**old_profile_before_updates, **changes_dict}
                    changes = _detect_profile_changes(old_profile_before_updates, new_profile)
                    for change in changes:
                        gpt_e_changes_list.append({
                            'field': change['field'],
                            'old_value': change['old_value'] or 'ריק',
                            'new_value': change['new_value']
                        })
                    
                    # הוספת קאונטר GPT-E
                    try:
                        from chat_utils import get_user_stats_and_history
                        from gpt_e_handler import GPT_E_RUN_EVERY_MESSAGES
                        stats, _ = get_user_stats_and_history(safe_str(chat_id))
                        total_messages = stats.get("total_messages", 0)
                        gpt_e_counter = f"{total_messages}/{GPT_E_RUN_EVERY_MESSAGES}"
                    except:
                        gpt_e_counter = None
            
            # שליחת התראה רק אם יש שינויים
            if gpt_c_changes_list or gpt_d_changes_list or gpt_e_changes_list:
                # יצירת סיכום מהיר
                current_summary = get_user_summary_fast(safe_str(chat_id)) or ""
                
                send_profile_update_notification(
                    chat_id=safe_str(chat_id),
                    user_message=user_msg,
                    gpt_c_changes=gpt_c_changes_list if gpt_c_changes_list else None,
                    gpt_d_changes=gpt_d_changes_list if gpt_d_changes_list else None,
                    gpt_e_changes=gpt_e_changes_list if gpt_e_changes_list else None,
                    gpt_e_counter=gpt_e_counter,
                    summary=current_summary
                )
                
        except Exception as admin_err:
            logger.warning(f"[BACKGROUND] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
        
        # 📨 **הדבר האחרון בשרשרת**: שליחת התכתבות אנונימית לאדמין עם כל הנתונים המלאים!
        # ✅ כעת נשלח התראה אחרי שכל הדברים הקשורים לאותה הודעה הסתיימו
        try:
            # 🔧 תיקון: שימוש בזמן התגובה האמיתי שנמדד מיד אחרי שליחה למשתמש
            gpt_response_time = gpt_result.get("gpt_pure_latency", 0) if isinstance(gpt_result, dict) else 0
            
            # חישוב מונה GPT-E
            gpt_e_counter = None
            if gpt_e_result and isinstance(gpt_e_result, dict) and gpt_e_result.get("success"):
                try:
                    from chat_utils import get_total_user_messages_count
                    from gpt_e_handler import GPT_E_RUN_EVERY_MESSAGES
                    total_messages = get_total_user_messages_count(safe_str(chat_id))
                    current_count = total_messages % GPT_E_RUN_EVERY_MESSAGES
                    gpt_e_counter = f"מופעל לפי מונה הודעות כרגע המונה עומד על {current_count} מתוך {GPT_E_RUN_EVERY_MESSAGES}"
                except:
                    gpt_e_counter = None
            
            # 🔧 **התראה סופית לאדמין עם כל המידע האמיתי!**
            from admin_notifications import send_anonymous_chat_notification
            admin_notification_result = send_anonymous_chat_notification(
                user_msg,
                bot_reply,  # התשובה האמיתית במקום "⏳ טרם נענה"
                history_messages=original_history_messages,  # ✅ ההיסטוריה המקורית שנשלחה ל-GPT
                messages_for_gpt=original_messages_for_gpt,  # ✅ ההודעות המקוריות שנשלחו ל-GPT
                gpt_timing=gpt_response_time,
                user_timing=user_response_actual_time,
                chat_id=chat_id,
                gpt_b_result=summary_result,
                gpt_c_result=gpt_c_result,
                gpt_d_result=gpt_d_result,
                gpt_e_result=gpt_e_result,
                gpt_e_counter=gpt_e_counter,
                message_number=interaction_message_number
            )
            
            # 🔥 עדכון טבלת interactions_log עם הנוסח שנשלח לאדמין
            try:
                from interactions_logger import get_interactions_logger
                logger_instance = get_interactions_logger()
                
                # קבלת הנוסח שנשלח לאדמין (admin_notification_result הוא הטקסט עצמו)
                admin_notification_text = admin_notification_result if isinstance(admin_notification_result, str) else ''
                
                if admin_notification_text:
                    # עדכון הטבלה עם הנוסח לאדמין
                    try:
                        import psycopg2
                        conn = psycopg2.connect(logger_instance.db_url)
                        cur = conn.cursor()
                        
                        # עדכון השורה האחרונה עבור המשתמש הזה
                        cur.execute("""
                            UPDATE interactions_log 
                            SET admin_notification_text = %s 
                            WHERE chat_id = %s 
                            ORDER BY serial_number DESC 
                            LIMIT 1
                        """, (admin_notification_text, int(safe_str(chat_id))))
                        
                        conn.commit()
                        cur.close()
                        conn.close()
                        
                        print(f"🔥 [INTERACTIONS_LOG] עדכון הטבלה עם נוסח ההתראה לאדמין | chat_id={safe_str(chat_id)}")
                        
                    except ImportError:
                        logger.warning(f"[INTERACTIONS_LOG] psycopg2 לא זמין לעדכון הטבלה", source="message_handler")
                    
            except Exception as update_admin_err:
                logger.warning(f"[INTERACTIONS_LOG] שגיאה בעדכון נוסח ההתראה לאדמין: {update_admin_err}", source="message_handler")
            
            logger.info(f"📨 [FINAL] ההתראה הסופית נשלחה לאדמין אחרי שכל הדברים הסתיימו | chat_id={safe_str(chat_id)}", source="message_handler")
            
        except Exception as final_admin_err:
            logger.warning(f"[FINAL] שגיאה בשליחת ההתראה הסופית לאדמין: {final_admin_err}", source="message_handler")
        
        logger.info(f"✅ [BACKGROUND] סיום משימות ברקע | chat_id={safe_str(chat_id)} | זמן תגובה אמיתי: {response_time:.2f}s | זמן כולל כולל רקע: {time.time() - user_request_start_time:.2f}s", source="message_handler")
        
    except Exception as ex:
        logger.error(f"❌ [BACKGROUND] שגיאה במשימות ברקע: {ex}", source="message_handler")
        # לא נכשל אם המשימות ברקע נכשלות - המשתמש כבר קיבל תשובה

async def run_background_processors(chat_id, user_msg, bot_reply):
    """
    מפעיל את כל המעבדים ברקע במקביל - GPT-C, GPT-D, GPT-E
    """
    try:
        # רשימת משימות לביצוע במקביל
        tasks = []
        
        # GPT-C - עדכון פרופיל משתמש (sync function, run separately)
        gpt_c_task = None
        if should_run_gpt_c(user_msg):
            gpt_c_task = asyncio.create_task(asyncio.to_thread(extract_user_info, user_msg, safe_str(chat_id)))
            
        # GPT-D - עדכון חכם של פרופיל
        tasks.append(smart_update_profile_with_gpt_d_async(safe_str(chat_id), user_msg, bot_reply))
        
        # GPT-E - אימוג'ים ותכונות מתקדמות
        tasks.append(execute_gpt_e_if_needed(safe_str(chat_id)))
        
        # הפעלה במקביל של כל התהליכים ואיסוף תוצאות
        all_tasks = []
        if gpt_c_task:
            all_tasks.append(gpt_c_task)
        all_tasks.extend(tasks)
        
        results = []
        if all_tasks:
            results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # 🔍 לוג שקט לבדיקות (ללא הודעות לאדמין)
        if should_log_debug_prints():
            ran_components = []
            idx = 0
            if gpt_c_task:
                gpt_c_res = results[idx] if idx < len(results) else None
                idx += 1
                if gpt_c_res is not None and not isinstance(gpt_c_res, Exception):
                    ran_components.append("GPT-C")
            
            gpt_d_res = results[idx] if idx < len(results) else None
            idx += 1
            if gpt_d_res is not None and not isinstance(gpt_d_res, Exception):
                ran_components.append("GPT-D")
            
            gpt_e_res = results[idx] if idx < len(results) else None
            if gpt_e_res is not None and not isinstance(gpt_e_res, Exception):
                ran_components.append("GPT-E")
            
            if ran_components:
                print(f"[DEBUG] 🛠️ הרצת מעבדי פרופיל: {', '.join(ran_components)} | chat_id={safe_str(chat_id)}")
            
    except Exception as e:
        logger.error(f"❌ שגיאה בהפעלת מעבדים ברקע: {e}", source="message_handler")

async def handle_new_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש חדש לגמרי ברקע
    """
    try:
        logger.info("[Permissions] משתמש חדש - תחילת onboarding", source="message_handler")
        print("[Permissions] משתמש חדש - תחילת onboarding")

        from messages import get_welcome_messages
        welcome_text_list = get_welcome_messages()

        # שליחה הדרגתית של הודעות הברכה
        for i, text in enumerate(welcome_text_list):
            await send_system_message(update, chat_id, text)
            await asyncio.sleep(0.5)  # השהיה קצרה בין הודעות
            
        # בקשת קוד אישור
        from messages import get_code_request_message
        code_request_msg = get_code_request_message()
        await send_system_message(update, chat_id, code_request_msg)
        
        # איחוד כל התשובות לבוט לטקסט אחד
        bot_reply = "\n".join(welcome_text_list) + "\n" + code_request_msg
        
        # אם יש שגיאה כלשהי בתהליך
        if not welcome_text_list or not code_request_msg:
            from messages import error_human_funny_message
            error_msg = error_human_funny_message()
            await send_system_message(update, chat_id, error_msg)
            bot_reply = error_msg
            
        # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
        try:
            from db_manager import save_chat_message
            save_chat_message(
                chat_id=safe_str(chat_id),
                user_msg=user_msg,
                bot_msg=bot_reply
            )
        except Exception as save_err:
            logger.warning(f"[NEW_USER] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
            
        # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש חדש**
        try:
            from admin_notifications import send_anonymous_chat_notification
            send_anonymous_chat_notification(
                user_msg,
                bot_reply,
                history_messages=None,
                messages_for_gpt=None,
                gpt_timing=None,
                user_timing=None,
                chat_id=chat_id
            )
        except Exception as admin_err:
            logger.warning(f"[NEW_USER] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
            
    except Exception as e:
        logger.error(f"[Onboarding] שגיאה בטיפול במשתמש חדש: {e}", source="message_handler")
        await send_system_message(update, chat_id, "הייתה בעיה ברישום. אנא נסה שוב מאוחר יותר.")
        
        # 🔧 תיקון: שמירת הודעת שגיאה גם כן
        try:
            from db_manager import save_chat_message
            save_chat_message(
                chat_id=safe_str(chat_id),
                user_msg=user_msg,
                bot_msg="שגיאה ברישום משתמש חדש",
                source_file='live_chat',
                message_type='onboarding_error'
            )
        except Exception as save_err:
            logger.warning(f"[NEW_USER_ERROR] שגיאה בשמירת הודעת שגיאה: {save_err}", source="message_handler")
        
        # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש חדש בשגיאה**
        try:
            from admin_notifications import send_anonymous_chat_notification
            send_anonymous_chat_notification(
                user_msg,
                "שגיאה ברישום משתמש חדש",
                history_messages=None,
                messages_for_gpt=None,
                gpt_timing=None,
                user_timing=None,
                chat_id=chat_id
            )
        except Exception as admin_err:
            logger.warning(f"[NEW_USER_ERROR] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")

async def handle_unregistered_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש שיש לו שורה זמנית אבל לא נתן קוד נכון עדיין.
    מבקש קוד אישור, מוודא אותו ורק לאחר מכן שולח בקשת אישור תנאים.
    """
    try:
        logger.info("[Permissions] משתמש עם שורה זמנית - תהליך קבלת קוד", source="message_handler")
        print("[Permissions] משתמש עם שורה זמנית - תהליך קבלת קוד")

        user_input = user_msg.strip()
        bot_reply = ""

        # אם המשתמש שלח רק ספרות – מניח שזה קוד האישור
        if user_input.isdigit():
            code_input = user_input

            # 🆕 ניסיון רישום עם הקוד (מיזוג שורות לפי המדריך!)
            register_success = register_user_with_code_db(safe_str(chat_id), code_input)

            if register_success.get("success", False):
                # קוד אושר - מיזוג השורות הצליח
                bot_reply = code_approved_message()
                await send_system_message(update, chat_id, bot_reply, reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))

                # שליחת בקשת אישור תנאים (הודעת ה-"רק לפני שנתחיל…")
                await send_approval_message(update, chat_id)
                
                # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש לא מאושר**
                try:
                    from admin_notifications import send_anonymous_chat_notification
                    send_anonymous_chat_notification(
                        user_msg,
                        bot_reply,
                        history_messages=None,
                        messages_for_gpt=None,
                        gpt_timing=None,
                        user_timing=None,
                        chat_id=chat_id
                    )
                except Exception as admin_err:
                    logger.warning(f"[CODE_APPROVED] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
                
                # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
                try:
                    from db_manager import save_chat_message
                    save_chat_message(
                        chat_id=safe_str(chat_id),
                        user_msg=user_msg,
                        bot_msg=bot_reply
                    )
                except Exception as save_err:
                    logger.warning(f"[CODE_APPROVED] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
                
                # 🔧 הוסר: הקריאה הישנה להתראת אדמין - עכשיו זה קורה אוטומטית מתוך save_chat_message
                
                return

            else:
                # 🆕 קוד לא תקין – מגדיל מונה ומחזיר הודעת שגיאה (ישירות למסד נתונים!)
                attempt_num = register_success.get("attempt_num", 1)

                retry_msg = get_retry_message_by_attempt(attempt_num if attempt_num and attempt_num > 0 else 1)
                await send_system_message(update, chat_id, retry_msg)
                bot_reply = retry_msg
                
                # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
                try:
                    from db_manager import save_chat_message
                    save_chat_message(
                        chat_id=safe_str(chat_id),
                        user_msg=user_msg,
                        bot_msg=bot_reply,
                        source_file='live_chat',
                        message_type='onboarding_code_invalid'
                    )
                except Exception as save_err:
                    logger.warning(f"[CODE_INVALID] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
                
                # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש לא מאושר**
                try:
                    from admin_notifications import send_anonymous_chat_notification
                    send_anonymous_chat_notification(
                        user_msg,
                        bot_reply,
                        history_messages=None,
                        messages_for_gpt=None,
                        gpt_timing=None,
                        user_timing=None,
                        chat_id=chat_id
                    )
                except Exception as admin_err:
                    logger.warning(f"[CODE_INVALID] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
                
                return

        # אם לא קיבלנו קוד – שולחים בקשה ברורה להזין קוד
        bot_reply = get_code_request_message()
        await send_system_message(update, chat_id, bot_reply)
        
        # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
        try:
            from db_manager import save_chat_message
            save_chat_message(
                chat_id=safe_str(chat_id),
                user_msg=user_msg,
                bot_msg=bot_reply
            )
        except Exception as save_err:
            logger.warning(f"[NO_CODE] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
        
        # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש לא מאושר**
        try:
            from admin_notifications import send_anonymous_chat_notification
            send_anonymous_chat_notification(
                user_msg,
                bot_reply,
                history_messages=None,
                messages_for_gpt=None,
                gpt_timing=None,
                user_timing=None,
                chat_id=chat_id
            )
        except Exception as admin_err:
            logger.warning(f"[NO_CODE] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")

    except Exception as ex:
        # הוספת המשתמש לרשימת התאוששות
        add_user_to_recovery_list(safe_str(chat_id), f"Critical error: {str(ex)[:100]}", user_msg)
        logger.error(f"❌ שגיאה קריטית: {ex}", source="message_handler")

async def handle_pending_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש שעדיין לא אישר תנאים ברקע
    """
    try:
        bot_reply = ""
        
        if user_msg.strip() == APPROVE_BUTTON_TEXT():
            # אישור תנאים
            # 🔨 ניקוי cache לפני האישור - עברנו למסד נתונים
            # 🗑️ הסרת תלות ב-Google Sheets - עברנו למסד נתונים
            clear_result = {"success": True, "cleared_count": 0}
            if clear_result.get("success"):
                print(f"🔨 נוקו {clear_result.get('cleared_count', 0)} cache keys לפני אישור")
            
            # 🆕 אישור המשתמש ישירות במסד נתונים (לפי המדריך!)
            approval_result = approve_user_db_new(safe_str(chat_id))
            if approval_result.get("success"):
                # 🗑️ הסרת תלות ב-Google Sheets - עברנו למסד נתונים
                clear_result2 = {"success": True, "cleared_count": 0}
                if clear_result2.get("success"):
                    print(f"🔨 נוקו {clear_result2.get('cleared_count', 0)} cache keys אחרי אישור")
                # 🔧 החליפו ReplyKeyboardRemove במקלדת עם כפתור "אהלן" מוסתר למניעת קפיצת מקלדת
                bot_reply = full_access_message()
                await send_system_message(update, chat_id, bot_reply, reply_markup=ReplyKeyboardMarkup([["אהלן"]], one_time_keyboard=True, resize_keyboard=True))
                # לא שולחים מקלדת/הודעה נוספת – המשתמש יקבל תשובה מהבינה בלבד
                
                # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
                try:
                    from db_manager import save_chat_message
                    save_chat_message(
                        chat_id=safe_str(chat_id),
                        user_msg=user_msg,
                        bot_msg=bot_reply
                    )
                except Exception as save_err:
                    logger.warning(f"[APPROVED] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
                
                # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש שהתאושר זה עתה**
                try:
                    from admin_notifications import send_anonymous_chat_notification
                    send_anonymous_chat_notification(
                        user_msg,
                        bot_reply,
                        history_messages=None,
                        messages_for_gpt=None,
                        gpt_timing=None,
                        user_timing=None,
                        chat_id=chat_id
                    )
                except Exception as admin_err:
                    logger.warning(f"[APPROVED] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
                
                return
            else:
                # 🔧 תיקון באג: טיפול בכשל אישור
                error_msg = approval_result.get("message", "שגיאה לא ידועה באישור")
                bot_reply = f"⚠️ שגיאה באישור: {error_msg}\n\nאנא נסה שוב או פנה לתמיכה."
                await send_system_message(update, chat_id, bot_reply)
                logger.error(f"[Permissions] כשל באישור משתמש {safe_str(chat_id)}: {error_msg}", source="message_handler")
                
                # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
                try:
                    from db_manager import save_chat_message
                    save_chat_message(
                        chat_id=safe_str(chat_id),
                        user_msg=user_msg,
                        bot_msg=bot_reply,
                        source_file='live_chat',
                        message_type='onboarding_approval_error'
                    )
                except Exception as save_err:
                    logger.warning(f"[APPROVAL_ERROR] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
                
                # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש לא מאושר**
                try:
                    from admin_notifications import send_anonymous_chat_notification
                    send_anonymous_chat_notification(
                        user_msg,
                        bot_reply,
                        history_messages=None,
                        messages_for_gpt=None,
                        gpt_timing=None,
                        user_timing=None,
                        chat_id=chat_id
                    )
                except Exception as admin_err:
                    logger.warning(f"[APPROVAL_ERROR] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
                
                return

        elif user_msg.strip() == DECLINE_BUTTON_TEXT():
            # דחיית תנאים – הצגת הודעת האישור מחדש
            # במקום להחזיר את המשתמש לשלב הקוד (שעלול ליצור מבוי סתום),
            # נשלח שוב את הודעת האישור עם המקלדת כדי שיוכל לאשר במידת הצורך.
            await send_approval_message(update, chat_id)
            bot_reply = "דחיית תנאים - הודעת אישור נשלחה מחדש"
            
            # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
            try:
                from db_manager import save_chat_message
                save_chat_message(
                    chat_id=safe_str(chat_id),
                    user_msg=user_msg,
                    bot_msg=bot_reply,
                    source_file='live_chat',
                    message_type='onboarding_declined'
                )
            except Exception as save_err:
                logger.warning(f"[DECLINED] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
            
            # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש לא מאושר**
            try:
                from admin_notifications import send_anonymous_chat_notification
                send_anonymous_chat_notification(
                    user_msg,
                    bot_reply,
                    history_messages=None,
                    messages_for_gpt=None,
                    gpt_timing=None,
                    user_timing=None,
                    chat_id=chat_id
                )
            except Exception as admin_err:
                logger.warning(f"[DECLINED] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
            
            return

        else:
            # כל הודעה אחרת – להזכיר את הצורך באישור תנאי השימוש
            await send_approval_message(update, chat_id)
            bot_reply = "הודעה אחרת - הודעת אישור נשלחה"
            
            # 🔧 **תיקון מערכתי: שמירה למסד הנתונים + התראה לאדמין אוטומטית!**
            try:
                from db_manager import save_chat_message
                save_chat_message(
                    chat_id=safe_str(chat_id),
                    user_msg=user_msg,
                    bot_msg=bot_reply,
                    source_file='live_chat',
                    message_type='onboarding_pending'
                )
            except Exception as save_err:
                logger.warning(f"[PENDING] שגיאה בשמירת הודעה למסד נתונים: {save_err}", source="message_handler")
            
            # 🔧 **תיקון מערכתי: החזרת התראה ישירה למשתמש לא מאושר**
            try:
                from admin_notifications import send_anonymous_chat_notification
                send_anonymous_chat_notification(
                    user_msg,
                    bot_reply,
                    history_messages=None,
                    messages_for_gpt=None,
                    gpt_timing=None,
                    user_timing=None,
                    chat_id=chat_id
                )
            except Exception as admin_err:
                logger.warning(f"[PENDING] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
            
            return

    except Exception as e:
        logger.error(f"[Permissions] שגיאה בטיפול במשתמש ממתין לאישור: {e}", source="message_handler")

async def send_system_message(update, chat_id, text, reply_markup=None):
    """
    שולחת הודעת מערכת למשתמש
    """
    try:
        # 🔧 תיקון קריטי: Progressive timeout אופטימלי גם להודעות מערכת
        max_retries = 5  # 6 ניסיונות סה"כ (0-5)
        timeout_seconds = TimeoutConfig.TELEGRAM_API_TIMEOUT_PROGRESSIVE  # Progressive timeout אופטימלי! 🚀
        
        for attempt in range(max_retries + 1):
            current_timeout = timeout_seconds[min(attempt, len(timeout_seconds) - 1)]
            try:
                if reply_markup:
                    await asyncio.wait_for(
                        update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML"),
                        timeout=current_timeout
                    )
                else:
                    await asyncio.wait_for(
                        update.message.reply_text(text, parse_mode="HTML"),
                        timeout=current_timeout
                    )
                break  # הצלחה - יוצאים מהלולאה
                
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    next_timeout = timeout_seconds[min(attempt + 1, len(timeout_seconds) - 1)]
                    logger.warning(f"[SYSTEM_MSG_TIMEOUT] ⏰ Timeout after {current_timeout}s on attempt {attempt + 1}/{max_retries + 1} for chat_id={safe_str(chat_id)}, retrying with {next_timeout}s...", source="message_handler")
                    await asyncio.sleep(1)  # חכה רק שנייה אחת - מהיר יותר!
                    continue
                else:
                    raise Exception(f"System message timeout after {max_retries + 1} attempts (timeouts: {timeout_seconds})")
                    
            except Exception as e:
                if attempt < max_retries and ("network" in str(e).lower() or "timeout" in str(e).lower() or "connection" in str(e).lower()):
                    next_timeout = timeout_seconds[min(attempt + 1, len(timeout_seconds) - 1)]
                    logger.warning(f"[SYSTEM_MSG_RETRY] 🌐 Network error on attempt {attempt + 1}/{max_retries + 1}: {e}", source="message_handler")
                    await asyncio.sleep(1)  # חכה רק שנייה אחת - מהיר יותר!
                    continue
                else:
                    raise e
        
        # 🚀 הודעת מערכת נשלחה! עדכון היסטוריה יתבצע ברקע להאצת זמן תגובה
        # עדכון ההיסטוריה להודעות מערכת יתבצע ברקע (אם נדרש)
        
        logger.info(f"הודעת מערכת נשלחה: {text[:100]}...", source="message_handler", chat_id=chat_id)
        
    except Exception as e:
        logger.error(f"שליחת הודעת מערכת נכשלה: {e}", source="message_handler")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    הפונקציה הראשית שמטפלת בכל הודעה נכנסת מהמשתמש.
    קלט: update (אובייקט טלגרם), context (אובייקט קונטקסט)
    פלט: אין (מטפלת בכל הלוגיקה של הודעה)
    # מהלך מעניין: טיפול מלא ב-onboarding, הרשאות, לוגים, שילוב gpt, עדכון היסטוריה, והכל בצורה אסינכרונית.
    """
    
    # 🔧 תיקון מערכתי: חילוץ בטוח של מידע מההודעה
    chat_id, message_id, user_msg, message_type, extract_success = safe_extract_message_info(update)
    
    if not extract_success:
        logger.error("❌ [HANDLE_MESSAGE] כשל בחילוץ מידע מההודעה", source="message_handler")
        print("❌ [HANDLE_MESSAGE] כשל בחילוץ מידע מההודעה")
        return
    
    # 🔧 מניעת כפילות - בדיקה אם ההודעה כבר טופלה
    try:
        if chat_id and message_id:
            # בדיקה אם ההודעה כבר טופלה (בתוך 5 שניות)
            import time
            current_time = time.time()
            message_key = f"{chat_id}_{message_id}"
            
            # שימוש ב-context.bot_data לאחסון הודעות שטופלו
            if "processed_messages" not in context.bot_data:
                context.bot_data["processed_messages"] = {}
            
            # ניקוי הודעות ישנות (יותר מ-10 שניות)
            context.bot_data["processed_messages"] = {
                k: v for k, v in context.bot_data["processed_messages"].items() 
                if current_time - v < 10
            }
            
            # בדיקה אם ההודעה כבר טופלה
            if message_key in context.bot_data["processed_messages"]:
                logger.info(f"[DUPLICATE] Message {message_id} for chat {safe_str(chat_id)} already processed - skipping", source="message_handler")
                print(f"🔄 [DUPLICATE] Message {message_id} for chat {safe_str(chat_id)} already processed - skipping")
                return
            
            # סימון ההודעה כטופלת
            context.bot_data["processed_messages"][message_key] = current_time
            
    except Exception as e:
        logger.warning(f"[DUPLICATE_CHECK] Error in duplicate check: {e}", source="message_handler")
        # ממשיכים גם אם יש שגיאה בבדיקת כפילות

    # 🕐 מדידת זמן התחלה - מהרגע שהמשתמש לחץ אנטר
    user_request_start_time = time.time()
    
    try:
        # איפוס מצב תזכורת - המשתמש הגיב
        from gentle_reminders import mark_user_active
        mark_user_active(safe_str(chat_id))
        
        # 🔧 תיקון: טיפול בהודעות לא טקסטואליות
        if message_type != "text":
            # 🔧 DEBUG: בדיקה נוספת לוודא שזה באמת לא טקסט
            logger.info(f"[DEBUG_NON_TEXT] message_type={message_type}, user_msg={repr(user_msg)}", source="message_handler")
            
            # 🔧 תיקון זמני: אם יש טקסט בהודעה, נתייחס אליה כטקסט
            if user_msg and user_msg.strip():
                logger.warning(f"[DEBUG_NON_TEXT] OVERRIDE: Found text in 'non-text' message, treating as text | message_type={message_type} | text={repr(user_msg)}", source="message_handler")
                # נמשיך עם הטיפול הרגיל בהודעות טקסט
            else:
                # אין טקסט, נטפל בהודעה כהודעה לא-טקסטואלית
                if message_type == "voice":
                    logger.info(f"🎤 התקבלה הודעה קולית (לא נתמכת כרגע) | chat_id={safe_str(chat_id)}", source="message_handler")
                    voice_message = "🎤 מצטער, תמיכה בהודעות קוליות זמנית לא זמינה.\nאנא שלח את השאלה שלך בטקסט ואשמח לעזור! 😊"
                    await send_system_message(update, chat_id, voice_message)
                    
                    # 🔧 תיקון: הוספת התראת אדמין להודעה קולית
                    try:
                        from admin_notifications import send_anonymous_chat_notification
                        send_anonymous_chat_notification(
                            user_msg,
                            voice_message,
                            history_messages=None,
                            messages_for_gpt=None,
                            gpt_timing=None,
                            user_timing=None,
                            chat_id=chat_id
                        )
                    except Exception as admin_err:
                        logger.warning(f"[VOICE] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
                    
                    return
                else:
                    # הודעות לא-טקסט אחרות
                    from messages import get_unsupported_message_response
                    appropriate_response = get_unsupported_message_response(message_type)
                    await send_system_message(update, chat_id, appropriate_response)
                    
                    # 🔧 **תיקון מערכתי: שמירה + התראה ישירה למשתמש לא מאושר**
                    try:
                        from db_manager import save_chat_message
                        save_chat_message(
                            chat_id=safe_str(chat_id),
                            user_msg=user_msg,
                            bot_msg=appropriate_response,
                            source_file='live_chat',
                            message_type='unsupported_message'
                        )
                        
                        # שליחת התראה ישירה כי זה משתמש לא מאושר
                        from admin_notifications import send_anonymous_chat_notification
                        send_anonymous_chat_notification(
                            user_msg,
                            appropriate_response,
                            history_messages=None,
                            messages_for_gpt=None,
                            gpt_timing=None,
                            user_timing=None,
                            chat_id=chat_id
                        )
                    except Exception as admin_err:
                        logger.warning(f"[UNSUPPORTED] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
                    
                    return

        # 🚀 התחלת ניטור concurrent
        try:
            from concurrent_monitor import start_monitoring_user, end_monitoring_user
            monitoring_result = await start_monitoring_user(safe_str(chat_id), safe_str(message_id), update)
            if not monitoring_result:
                overload_message = "⏳ הבוט עמוס כרגע. אנא נסה שוב בעוד מספר שניות."
                await send_system_message(update, chat_id, overload_message)
                
                # 🔧 **תיקון מערכתי: שמירה + התראה ישירה למשתמש לא מאושר**
                try:
                    from db_manager import save_chat_message
                    save_chat_message(
                        chat_id=safe_str(chat_id),
                        user_msg=user_msg,
                        bot_msg=overload_message,
                        source_file='live_chat',
                        message_type='system_overload'
                    )
                    
                    # שליחת התראה ישירה כי זה משתמש לא מאושר
                    from admin_notifications import send_anonymous_chat_notification
                    send_anonymous_chat_notification(
                        user_msg,
                        overload_message,
                        history_messages=None,
                        messages_for_gpt=None,
                        gpt_timing=None,
                        user_timing=None,
                        chat_id=chat_id
                    )
                except Exception as admin_err:
                    logger.warning(f"[OVERLOAD] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
                
                return
        except Exception as e:
            logger.error(f"[MESSAGE_HANDLER] Error starting monitoring: {e}", source="message_handler")
            tech_error_message = "⚠️ שגיאה טכנית. נסה שוב בעוד כמה שניות."
            await send_system_message(update, chat_id, tech_error_message)
            
            # 🔧 **תיקון מערכתי: שמירה + התראה ישירה למשתמש לא מאושר**
            try:
                from db_manager import save_chat_message
                save_chat_message(
                    chat_id=safe_str(chat_id),
                    user_msg=user_msg,
                    bot_msg=tech_error_message,
                    source_file='live_chat',
                    message_type='tech_error'
                )
                
                # שליחת התראה ישירה כי זה משתמש לא מאושר
                from admin_notifications import send_anonymous_chat_notification
                send_anonymous_chat_notification(
                    user_msg,
                    tech_error_message,
                    history_messages=None,
                    messages_for_gpt=None,
                    gpt_timing=None,
                    user_timing=None,
                    chat_id=chat_id
                )
            except Exception as admin_err:
                logger.warning(f"[TECH_ERROR] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
            
            return

        logger.info(f"📩 התקבלה הודעה | chat_id={safe_str(chat_id)}, message_id={message_id}, תוכן={user_msg!r}", source="message_handler")
        
        # בדיקת הרשאות משתמש
        from db_manager import check_user_approved_status_db
        from messages import approval_text, approval_keyboard, get_welcome_messages, get_code_request_message
        
        user_status_result = check_user_approved_status_db(safe_str(chat_id))
        user_status = user_status_result.get("status", "error") if isinstance(user_status_result, dict) else "error"
        
        if user_status == "not_found":
            # משתמש חדש לגמרי
            await handle_new_user_background(update, context, chat_id, user_msg)
            await end_monitoring_user(safe_str(chat_id), True)
            return
        elif user_status == "pending_code":
            # משתמש שיש לו שורה זמנית אבל לא נתן קוד נכון
            await handle_unregistered_user_background(update, context, chat_id, user_msg)
            await end_monitoring_user(safe_str(chat_id), True)
            return
        elif user_status == "pending_approval":
            # משתמש שעדיין לא אישר תנאים
            await handle_pending_user_background(update, context, chat_id, user_msg)
            await end_monitoring_user(safe_str(chat_id), True)
            return
        elif user_status == "error":
            # שגיאה בבדיקת הרשאות
            permission_error_message = "⚠️ שגיאה טכנית בבדיקת הרשאות. נסה שוב בעוד כמה שניות."
            await send_system_message(update, chat_id, permission_error_message)
            await end_monitoring_user(safe_str(chat_id), False)
            
            # 🔧 **תיקון מערכתי: שמירה + התראה ישירה למשתמש לא מאושר**
            try:
                from db_manager import save_chat_message
                save_chat_message(
                    chat_id=safe_str(chat_id),
                    user_msg=user_msg,
                    bot_msg=permission_error_message,
                    source_file='live_chat',
                    message_type='permission_error'
                )
                
                # שליחת התראה ישירה כי זה משתמש לא מאושר
                from admin_notifications import send_anonymous_chat_notification
                send_anonymous_chat_notification(
                    user_msg,
                    permission_error_message,
                    history_messages=None,
                    messages_for_gpt=None,
                    gpt_timing=None,
                    user_timing=None,
                    chat_id=chat_id
                )
            except Exception as admin_err:
                logger.warning(f"[PERMISSION_ERROR] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
            
            return

        # משתמש מאושר - שולח תשובה מיד
        from db_manager import increment_user_message_count
        increment_user_message_count(safe_str(chat_id))
        
        # 🔧 הוסר: ההתראה עכשיו נשלחת אוטומטית מתוך save_chat_message
        # אין צורך בקריאה נפרדת - כל הודעה שנשמרת = התראה לאדמין
        
        # קבלת תשובה מ-GPT
        from gpt_a_handler import get_main_response
        from chat_utils import get_balanced_history_for_gpt
        
        # בניית היסטוריה להקשר - 20 הודעות משתמש + 20 הודעות בוט עם סיכומי GPT-B
        history_messages = get_balanced_history_for_gpt(safe_str(chat_id), user_limit=20, bot_limit=20)
        
        # 🔧 בניית הודעות מלאות עם כל הסיסטם פרומפטים
        from chat_utils import build_complete_system_messages
        
        # בניית כל הסיסטם פרומפטים במקום אחד
        system_messages = build_complete_system_messages(safe_str(chat_id), user_msg, include_main_prompt=True)
        
        # בניית הודעות GPT מלאות
        messages_for_gpt = system_messages.copy()
        
        # הוספת הודעות היסטוריה
        if history_messages:
            messages_for_gpt.extend(history_messages)
        
        # הוספת הודעת המשתמש הנוכחית
        messages_for_gpt.append({"role": "user", "content": user_msg})
        
        # קבלת תשובה מ-GPT
        gpt_result = get_main_response(messages_for_gpt, safe_str(chat_id))
        bot_reply = gpt_result.get("bot_reply") if isinstance(gpt_result, dict) else gpt_result
        
        if not bot_reply:
            error_msg = error_human_funny_message()
            await send_system_message(update, chat_id, error_msg)
            await end_monitoring_user(safe_str(chat_id), False)
            
            # 🔧 הוסר: ההתראה כבר נשלחת אוטומטית מתוך save_chat_message
            # אין צורך בקריאה נפרדת
            
            return

        # �� שליחת התשובה למשתמש מיד!
        telegram_send_time = await send_message(update, chat_id, bot_reply, is_bot_message=True, is_gpt_a_response=True)

        # 🔧 מדידת זמן תגובה אמיתי מיד אחרי שליחה בפועל לטלגרם - זה הזמן האמיתי!
        if telegram_send_time:
            user_response_actual_time = telegram_send_time - user_request_start_time
        else:
            # במקרה של כשלון, נשתמש בזמן נוכחי כגיבוי
            user_response_actual_time = time.time() - user_request_start_time

        # 🔧 כל השאר ברקע - המשתמש כבר קיבל תשובה!
        asyncio.create_task(handle_background_tasks(update, context, chat_id, user_msg, bot_reply, message_id, user_request_start_time, gpt_result, history_messages, messages_for_gpt, user_response_actual_time))
        
    except Exception as ex:
        logger.error(f"❌ שגיאה בטיפול בהודעה: {ex}", source="message_handler")
        # הוספת המשתמש לרשימת התאוששות
        add_user_to_recovery_list(safe_str(chat_id), f"Critical error in message handling: {str(ex)[:100]}", user_msg)
        await end_monitoring_user(safe_str(chat_id), False)
        return

    # סיום ניטור
    await end_monitoring_user(safe_str(chat_id), True)
