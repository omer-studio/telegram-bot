"""
message_handler.py
------------------
קובץ זה מרכז את כל הטיפול בהודעות ועיצוב, פורמטינג, ושליחה של הודעות.
הרציונל: ריכוז כל ניהול ההודעות, פורמטינג, שגיאות, וחוויית משתמש במקום אחד.
"""

import asyncio
import re
import json
import time

# 🚀 יבוא המערכת החדשה - פשוטה ועקבית
from simple_config import config, TimeoutConfig
from simple_logger import logger
from simple_data_manager import data_manager
from db_manager import safe_str, safe_operation

from utils import get_israel_time
from chat_utils import log_error_stat, update_chat_history, get_chat_history_messages, get_chat_history_simple, update_last_bot_message
# Telegram types (ignored if telegram package absent in testing env)
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove  # type: ignore
from telegram.ext import ContextTypes  # type: ignore
from datetime import datetime
# 🗑️ handle_secret_command הוסרה - עברנו לפקודות טלגרם רגילות
from config import should_log_message_debug, should_log_debug_prints
from messages import get_welcome_messages, get_retry_message_by_attempt, approval_text, approval_keyboard, APPROVE_BUTTON_TEXT, DECLINE_BUTTON_TEXT, code_approved_message, code_not_received_message, not_approved_message, nice_keyboard, nice_keyboard_message, remove_keyboard_message, full_access_message, error_human_funny_message, get_unsupported_message_response, get_code_request_message
from notifications import handle_critical_error
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
from chat_utils import should_send_time_greeting, get_time_greeting_instruction
from prompts import SYSTEM_PROMPT
import profile_utils as _pu
import traceback
# 🆕 פונקציות חדשות למסד נתונים - לפי המדריך!
import db_manager
from db_manager import register_user_with_code_db, check_user_approved_status_db, approve_user_db_new, increment_code_try_db_new, save_gpt_chat_message

from chat_utils import get_weekday_context_instruction, get_holiday_system_message

# 🎨 Constants - מניעת כפילויות
EMOJI_PATTERN = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]'

# 🚀 OPTIMIZED: Pre-compiled regex patterns for fast formatting
import re
_HTML_CLEAN_PATTERN = re.compile(r'<[^>]+>')
_BOLD_PATTERN = re.compile(r'\*\*(.*?)\*\*')
_BOLD_UNDERSCORE_PATTERN = re.compile(r'__(.*?)__')
_UNDERLINE_PATTERN = re.compile(r'\*(.*?)\*')
_UNDERLINE_UNDERSCORE_PATTERN = re.compile(r'_(.*?)_')
_DOT_EMOJI_PATTERN = re.compile(fr'\.(\s*)({EMOJI_PATTERN})')
_PUNCT_EMOJI_PATTERN = re.compile(fr'([?!])(\s*)({EMOJI_PATTERN})')
_DOT_ONLY_PATTERN = re.compile(r'\.(\s*)')
_PUNCT_ONLY_PATTERN = re.compile(fr'([?!])(\s*)(?!.*{EMOJI_PATTERN})')
_NEWLINE_SPACES_PATTERN = re.compile(r'\n\s+')
_MULTIPLE_NEWLINES_PATTERN = re.compile(r'\n{3,}')

def safe_extract_message_info(update):
    """
    🔧 פונקציה מרכזית לחילוץ בטוח של chat_id, message_id ותוכן הודעה
    מחזירה: (chat_id, message_id, message_text, message_type, success)
    """
    try:
        if not update or not hasattr(update, 'message') or not update.message:
            return None, None, None, "unknown", False
        
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        message_text = update.message.text or ""
        message_type = "text"
        
        # בדיקת סוגי הודעות מיוחדות
        if hasattr(update.message, 'voice') and update.message.voice:
            message_type = "voice"
        elif hasattr(update.message, 'document') and update.message.document:
            message_type = "document"
        elif hasattr(update.message, 'photo') and update.message.photo:
            message_type = "photo"
        
        return chat_id, message_id, message_text, message_type, True
        
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
        update_chat_history(safe_str(chat_id), "", approval_msg)
        logger.info("הודעת אישור נשלחה", source="message_handler", chat_id=chat_id)
        
    except Exception as e:
        logger.error(f"❌ שליחת הודעת אישור נכשלה: {e}", source="message_handler")
        await send_system_message(update, chat_id, approval_msg)

def format_text_for_telegram(text):
    """
    📝 פורמטינג מהיר ואופטימלי - הכללים של המשתמש:
    • נקודה/שאלה/קריאה + אימוג'י → אימוג'י באותה שורה + מעבר שורה  
    • אם נקודה בלבד → מוחקים אותה + מעבר שורה
    • פיסוק רגיל → מעבר שורה
    
    🚀 אופטימיזציה: Pre-compiled regex patterns לביצועים מהירים
    """
    try:
        if not text:
            return ""
        
        # שלב 1: ניקוי HTML בסיסי (מהיר יותר)
        text = _HTML_CLEAN_PATTERN.sub('', text)
        
        # שלב 2: Markdown → HTML (מהיר יותר)
        text = _BOLD_PATTERN.sub(r'<b>\1</b>', text)
        text = _BOLD_UNDERSCORE_PATTERN.sub(r'<b>\1</b>', text)
        text = _UNDERLINE_PATTERN.sub(r'<u>\1</u>', text)
        text = _UNDERLINE_UNDERSCORE_PATTERN.sub(r'<u>\1</u>', text)
        
        # שלב 3: פיסוק ואימוג'ים - מהיר ברק! 🚀
        
        # כלל 1: נקודה + אימוג'י → מוחק נקודה, שומר אימוג'י + מעבר שורה  
        text = _DOT_EMOJI_PATTERN.sub(r' \2\n', text)
        
        # כלל 2: שאלה/קריאה + אימוג'י → שומר הכל + מעבר שורה
        text = _PUNCT_EMOJI_PATTERN.sub(r'\1 \3\n', text)
        
        # כלל 3: נקודה בלבד → מוחק + מעבר שורה
        text = _DOT_ONLY_PATTERN.sub(r'\n', text)
        
        # כלל 4: שאלה/קריאה בלבד (בלי אימוג'י) → מעבר שורה
        text = _PUNCT_ONLY_PATTERN.sub(r'\1\n', text)
        
        # ניקוי סופי (מהיר יותר)
        text = _NEWLINE_SPACES_PATTERN.sub('\n', text)  # מסיר רווחים אחרי מעבר שורה
        text = _MULTIPLE_NEWLINES_PATTERN.sub('\n\n', text)  # מגביל מעברי שורה כפולים
        text = text.strip()
        
        # וידוא מעבר שורה בסוף (אלא אם ריק)
        if text and not text.endswith('\n'):
            text += '\n'
        
        return text
        
    except Exception as e:
        # 🛡️ Error handling - המשתמש יקבל תשובה גם אם הפורמטינג נכשל
        logger.error(f"🚨 שגיאה בפורמטינג: {e} | טקסט: {text[:50]}...", source="message_handler")
        
        # fallback פשוט - מחזיר את הטקסט המקורי עם \n בסוף
        try:
            fallback_text = str(text or "").strip()
            return fallback_text + '\n' if fallback_text else ""
        except:
            return "שגיאה בפורמטינג - הודעה לא זמינה\n"

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
    פלט: אין (שולחת הודעה)
    # מהלך מעניין: עדכון היסטוריה ולוגים רק אם ההודעה נשלחה בהצלחה.
    """
    
    # 🚨 CRITICAL SECURITY CHECK: מנע שליחת הודעות פנימיות למשתמש!
    if text and ("[עדכון פרופיל]" in text or "[PROFILE_CHANGE]" in text or 
                 (text.startswith("[") and "]" in text and any(keyword in text for keyword in ["עדכון", "debug", "admin", "system"]))):
        logger.critical(f"🚨 BLOCKED INTERNAL MESSAGE TO USER! chat_id={safe_str(chat_id)} | text={text[:100]}", source="message_handler")
        print(f"🚨🚨🚨 CRITICAL: חסימת הודעה פנימית למשתמש! chat_id={safe_str(chat_id)}")
        return
    
    # 🚀 פורמטינג מהיר - עכשיו זה כבר מהיר אז אפשר לעשות לפני שליחה!
    if is_gpt_a_response:
        formatted_text = format_text_for_telegram(text)
    else:
        formatted_text = format_text_for_telegram(text)
    
    # 🔧 תיקון קריטי: Progressive timeout מהיר יותר
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
        except Exception as notify_err:
            logger.error(f"❌ [NOTIFY_ERROR] התראה לאדמין נכשלה: {notify_err}", source="message_handler")
        return
    
    if is_bot_message:
        update_chat_history(safe_str(chat_id), "", formatted_text)
    
    logger.info(f"📤 [SENT] הודעה נשלחה | chat_id={safe_str(chat_id)}", source="message_handler")

async def handle_formatting_background(chat_id, original_text, sent_message):
    """
    🔧 פונקציה חדשה: טיפול בפורמטינג ברקע
    """
    try:
        # זה יכול לקחת זמן - אבל המשתמש כבר קיבל תשובה!
        formatted_text = format_text_for_telegram(original_text)
        
        # אם הפורמטינג שינה משהו משמעותי, אפשר לעדכן
        if len(formatted_text) != len(original_text.strip() + '\n'):
            logger.info(f"🔧 [BACKGROUND_FORMAT] פורמטינג הושלם ברקע | chat_id={safe_str(chat_id)}", source="message_handler")
        
    except Exception as e:
        logger.warning(f"⚠️ [BACKGROUND_FORMAT] שגיאה בפורמטינג ברקע: {e}", source="message_handler")

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
        
        # 📨 שליחת התכתבות אנונימית לאדמין (ברקע)
        try:
            from admin_notifications import send_anonymous_chat_notification
            # 🔧 תיקון: שימוש בזמן התגובה האמיתי שנמדד מיד אחרי שליחה למשתמש
            gpt_response_time = gpt_result.get("gpt_pure_latency", 0) if isinstance(gpt_result, dict) else 0
            
            send_anonymous_chat_notification(
                user_msg, 
                bot_reply, 
                history_messages, 
                messages_for_gpt,
                gpt_timing=gpt_response_time,
                user_timing=user_response_actual_time,  # 🔧 תיקון: זמן אמיתי!
                chat_id=chat_id
            )
        except Exception as admin_chat_err:
            logger.warning(f"שגיאה בשליחת התכתבות לאדמין: {admin_chat_err}", source="message_handler")

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
        
        logger.info(f"🔄 [BACKGROUND] התחלת משימות ברקע | chat_id={safe_str(chat_id)} | זמן תגובה אמיתי: {response_time:.2f}s", source="message_handler")
        
        # שלב 1: עדכון היסטוריה
        try:
            update_chat_history(safe_str(chat_id), user_msg, bot_reply)
        except Exception as hist_err:
            logger.warning(f"[BACKGROUND] שגיאה בעדכון היסטוריה: {hist_err}", source="message_handler")
        
        # 🔧 תיקון: טעינת היסטוריה מחדש אחרי השמירה כדי שהמונה יעלה
        try:
            updated_history_messages = get_chat_history_simple(safe_str(chat_id), limit=32)
            # עדכון ההיסטוריה לשליחת התראה עם המונה הנכון
            history_messages = updated_history_messages if updated_history_messages else history_messages
            print(f"🔄 [BACKGROUND] היסטוריה עודכנה: {len(history_messages)} הודעות")
        except Exception as hist_reload_err:
            logger.warning(f"[BACKGROUND] שגיאה בטעינת היסטוריה מחדש: {hist_reload_err}", source="message_handler")
        
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
        
        # שלב 4: רישום למסד נתונים
        try:
            # איסוף נתונים מלאים לרישום  
            # ✅ השתמש בפונקציה מהמסד נתונים
            from profile_utils import get_user_summary_fast
            current_summary = get_user_summary_fast(safe_str(chat_id)) or ""
            history_messages = get_chat_history_simple(safe_str(chat_id), limit=32)
            
            # בניית הודעות מלאות לרישום
            messages_for_log = [{"role": "system", "content": SYSTEM_PROMPT}]
            if current_summary:
                messages_for_log.append({"role": "system", "content": f"🎯 מידע על המשתמש: {current_summary}"})
            if history_messages:
                messages_for_log.extend(history_messages)
            messages_for_log.append({"role": "user", "content": user_msg})
            
            # ✅ רישום למסד נתונים
            save_gpt_chat_message(
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
            
            logger.info(f"💾 [BACKGROUND] נשמר למסד נתונים | chat_id={safe_str(chat_id)}", source="message_handler")
            
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
    טיפול במשתמש חדש לגמרי ברקע - שליחת 3 הודעות קבלת פנים
    """
    try:
        logger.info("[Onboarding] משתמש חדש - שליחת הודעות קבלת פנים", source="message_handler")
        print("[Onboarding] משתמש חדש - שליחת הודעות קבלת פנים")
        
        # 🆕 יוצר שורה זמנית למשתמש חדש (לפי המדריך!)
        register_result = register_user_with_code_db(safe_str(chat_id), None)

        if register_result.get("success"):
            # שליחת 3 הודעות קבלת פנים למשתמש חדש
            welcome_messages = get_welcome_messages()
            for i, msg in enumerate(welcome_messages):
                await send_system_message(update, chat_id, msg)
                if i < len(welcome_messages) - 1:  # לא לחכות אחרי ההודעה האחרונה
                    await asyncio.sleep(0.5)
            
            logger.info(f"[Onboarding] נשלחו {len(welcome_messages)} הודעות קבלת פנים למשתמש {safe_str(chat_id)}", source="message_handler")
            print(f"[Onboarding] נשלחו {len(welcome_messages)} הודעות קבלת פנים למשתמש {safe_str(chat_id)}")

        else:
            error_msg = "מצטער, הייתה בעיה ברישום. אנא נסה שוב."
            await send_system_message(update, chat_id, error_msg)
            
    except Exception as e:
        logger.error(f"[Onboarding] שגיאה בטיפול במשתמש חדש: {e}", source="message_handler")
        await send_system_message(update, chat_id, "הייתה בעיה ברישום. אנא נסה שוב מאוחר יותר.")

async def handle_unregistered_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש שיש לו שורה זמנית אבל לא נתן קוד נכון עדיין.
    מבקש קוד אישור, מוודא אותו ורק לאחר מכן שולח בקשת אישור תנאים.
    """
    try:
        logger.info("[Permissions] משתמש עם שורה זמנית - תהליך קבלת קוד", source="message_handler")
        print("[Permissions] משתמש עם שורה זמנית - תהליך קבלת קוד")

        user_input = user_msg.strip()

        # אם המשתמש שלח רק ספרות – מניח שזה קוד האישור
        if user_input.isdigit():
            code_input = user_input

            # 🆕 ניסיון רישום עם הקוד (מיזוג שורות לפי המדריך!)
            register_success = register_user_with_code_db(safe_str(chat_id), code_input)

            if register_success.get("success", False):
                # קוד אושר - מיזוג השורות הצליח
                await send_system_message(update, chat_id, code_approved_message(), reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))

                # שליחת בקשת אישור תנאים (הודעת ה-"רק לפני שנתחיל…")
                await send_approval_message(update, chat_id)
                return

            else:
                # 🆕 קוד לא תקין – מגדיל מונה ומחזיר הודעת שגיאה (ישירות למסד נתונים!)
                attempt_num = register_success.get("attempt_num", 1)

                retry_msg = get_retry_message_by_attempt(attempt_num if attempt_num and attempt_num > 0 else 1)
                await send_system_message(update, chat_id, retry_msg)
                return

        # אם לא קיבלנו קוד – שולחים בקשה ברורה להזין קוד
        await send_system_message(update, chat_id, get_code_request_message())

    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def handle_pending_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש שעדיין לא אישר תנאים ברקע
    """
    try:
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
                await send_system_message(update, chat_id, full_access_message(), reply_markup=ReplyKeyboardRemove())
                # לא שולחים מקלדת/הודעה נוספת – המשתמש יקבל תשובה מהבינה בלבד
                return

        elif user_msg.strip() == DECLINE_BUTTON_TEXT():
            # דחיית תנאים – הצגת הודעת האישור מחדש
            # במקום להחזיר את המשתמש לשלב הקוד (שעלול ליצור מבוי סתום),
            # נשלח שוב את הודעת האישור עם המקלדת כדי שיוכל לאשר במידת הצורך.
            await send_approval_message(update, chat_id)
            return

        else:
            # כל הודעה אחרת – להזכיר את הצורך באישור תנאי השימוש
            await send_approval_message(update, chat_id)
            return

    except Exception as e:
        logger.error(f"[Permissions] שגיאה בטיפול במשתמש ממתין לאישור: {e}", source="message_handler")

async def send_system_message(update, chat_id, text, reply_markup=None):
    """
    שולחת הודעת מערכת למשתמש ללא פורמטינג מתקדם
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
        
        # 🔧 תיקון: שמירת הודעת מערכת נכון - הבוט שלח, לא המשתמש
        update_chat_history(safe_str(chat_id), "", text)  # הודעת מערכת - אין הודעת משתמש
        # 🗑️ הוחלף ב-logger פשוט
        logger.info(f"הודעת מערכת נשלחה: {text[:100]}...", source="message_handler", chat_id=chat_id)
        
    except Exception as e:
        logger.error(f"שליחת הודעת מערכת נכשלה: {e}", source="message_handler")

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
        
        # 📨 שליחת התכתבות אנונימית לאדמין (ברקע)
        try:
            from admin_notifications import send_anonymous_chat_notification
            # 🔧 תיקון: שימוש בזמן התגובה האמיתי שנמדד מיד אחרי שליחה למשתמש
            gpt_response_time = gpt_result.get("gpt_pure_latency", 0) if isinstance(gpt_result, dict) else 0
            
            send_anonymous_chat_notification(
                user_msg, 
                bot_reply, 
                history_messages, 
                messages_for_gpt,
                gpt_timing=gpt_response_time,
                user_timing=user_response_actual_time,  # 🔧 תיקון: זמן אמיתי!
                chat_id=chat_id
            )
        except Exception as admin_chat_err:
            logger.warning(f"שגיאה בשליחת התכתבות לאדמין: {admin_chat_err}", source="message_handler")

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
        
        logger.info(f"🔄 [BACKGROUND] התחלת משימות ברקע | chat_id={safe_str(chat_id)} | זמן תגובה אמיתי: {response_time:.2f}s", source="message_handler")
        
        # שלב 1: עדכון היסטוריה
        try:
            update_chat_history(safe_str(chat_id), user_msg, bot_reply)
        except Exception as hist_err:
            logger.warning(f"[BACKGROUND] שגיאה בעדכון היסטוריה: {hist_err}", source="message_handler")
        
        # 🔧 תיקון: טעינת היסטוריה מחדש אחרי השמירה כדי שהמונה יעלה
        try:
            updated_history_messages = get_chat_history_simple(safe_str(chat_id), limit=32)
            # עדכון ההיסטוריה לשליחת התראה עם המונה הנכון
            history_messages = updated_history_messages if updated_history_messages else history_messages
            print(f"🔄 [BACKGROUND] היסטוריה עודכנה: {len(history_messages)} הודעות")
        except Exception as hist_reload_err:
            logger.warning(f"[BACKGROUND] שגיאה בטעינת היסטוריה מחדש: {hist_reload_err}", source="message_handler")
        
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
        
        # שלב 4: רישום למסד נתונים
        try:
            # איסוף נתונים מלאים לרישום  
            # ✅ השתמש בפונקציה מהמסד נתונים
            from profile_utils import get_user_summary_fast
            current_summary = get_user_summary_fast(safe_str(chat_id)) or ""
            history_messages = get_chat_history_simple(safe_str(chat_id), limit=32)
            
            # בניית הודעות מלאות לרישום
            messages_for_log = [{"role": "system", "content": SYSTEM_PROMPT}]
            if current_summary:
                messages_for_log.append({"role": "system", "content": f"🎯 מידע על המשתמש: {current_summary}"})
            if history_messages:
                messages_for_log.extend(history_messages)
            messages_for_log.append({"role": "user", "content": user_msg})
            
            # ✅ רישום למסד נתונים
            save_gpt_chat_message(
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
            
            logger.info(f"💾 [BACKGROUND] נשמר למסד נתונים | chat_id={safe_str(chat_id)}", source="message_handler")
            
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
        
        logger.info(f"✅ [BACKGROUND] סיום משימות ברקע | chat_id={safe_str(chat_id)} | זמן תגובה אמיתי: {response_time:.2f}s | זמן כולל כולל רקע: {time.time() - user_request_start_time:.2f}s", source="message_handler")
        
    except Exception as ex:
        logger.error(f"❌ [BACKGROUND] שגיאה במשימות ברקע: {ex}", source="message_handler")
        # לא נכשל אם המשימות ברקע נכשלות - המשתמש כבר קיבל תשובה


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
            if message_type == "voice":
                logger.info(f"🎤 התקבלה הודעה קולית (לא נתמכת כרגע) | chat_id={safe_str(chat_id)}", source="message_handler")
                voice_message = "🎤 מצטער, תמיכה בהודעות קוליות זמנית לא זמינה.\nאנא שלח את השאלה שלך בטקסט ואשמח לעזור! 😊"
                await send_system_message(update, chat_id, voice_message)
                return
            else:
                # הודעות לא-טקסט אחרות
                from messages import get_unsupported_message_response
                appropriate_response = get_unsupported_message_response(message_type)
                await send_system_message(update, chat_id, appropriate_response)
                return

        # 🚀 התחלת ניטור concurrent
        try:
            from concurrent_monitor import start_monitoring_user, end_monitoring_user
            monitoring_result = await start_monitoring_user(safe_str(chat_id), str(message_id), update)
            if not monitoring_result:
                await send_system_message(update, chat_id, "⏳ הבוט עמוס כרגע. אנא נסה שוב בעוד מספר שניות.")
                return
        except Exception as e:
            logger.error(f"[MESSAGE_HANDLER] Error starting monitoring: {e}", source="message_handler")
            await send_system_message(update, chat_id, "⚠️ שגיאה טכנית. נסה שוב בעוד כמה שניות.")
            return

        logger.info(f"📩 התקבלה הודעה | chat_id={safe_str(chat_id)}, message_id={message_id}, תוכן={user_msg!r}", source="message_handler")
        
        # בדיקת הרשאות משתמש
        from db_manager import check_user_approved_status_db
        from messages import approval_text, approval_keyboard, get_welcome_messages, get_code_request_message
        
        user_status = check_user_approved_status_db(safe_str(chat_id))
        
        if user_status == "new":
            # משתמש חדש לגמרי
            await handle_new_user_background(update, context, chat_id, user_msg)
            await end_monitoring_user(safe_str(chat_id), True)
            return
        elif user_status == "unregistered":
            # משתמש שיש לו שורה זמנית אבל לא נתן קוד נכון
            await handle_unregistered_user_background(update, context, chat_id, user_msg)
            await end_monitoring_user(safe_str(chat_id), True)
            return
        elif user_status == "pending":
            # משתמש שעדיין לא אישר תנאים
            await handle_pending_user_background(update, context, chat_id, user_msg)
            await end_monitoring_user(safe_str(chat_id), True)
            return

        # משתמש מאושר - שולח תשובה מיד
        from db_manager import increment_user_message_count
        increment_user_message_count(safe_str(chat_id))
        
        # קבלת תשובה מ-GPT
        from gpt_a_handler import get_main_response
        from chat_utils import get_chat_history_simple
        
        # בניית היסטוריה להקשר
        history_messages = get_chat_history_simple(safe_str(chat_id), limit=15)
        
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
            from user_friendly_errors import error_human_funny_message
            error_msg = error_human_funny_message()
            await send_system_message(update, chat_id, error_msg)
            await end_monitoring_user(safe_str(chat_id), False)
            return

        # 🚀 שליחת התשובה למשתמש מיד!
        await send_message(update, chat_id, bot_reply, is_bot_message=True, is_gpt_a_response=True)

        # 🔧 מדידת זמן תגובה אמיתי מיד אחרי שליחה למשתמש
        user_response_actual_time = time.time() - user_request_start_time

        # 🔧 כל השאר ברקע - המשתמש כבר קיבל תשובה!
        asyncio.create_task(handle_background_tasks(update, context, chat_id, user_msg, bot_reply, message_id, user_request_start_time, gpt_result, history_messages, messages_for_gpt, user_response_actual_time))
        
    except Exception as ex:
        logger.error(f"❌ שגיאה בטיפול בהודעה: {ex}", source="message_handler")
        from notifications import handle_critical_error
        await handle_critical_error(ex, chat_id, user_msg, update)
        await end_monitoring_user(safe_str(chat_id), False)
        return

    # סיום ניטור
    await end_monitoring_user(safe_str(chat_id), True)
