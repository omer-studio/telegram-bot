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
from utils import handle_secret_command
from config import should_log_message_debug, should_log_debug_prints
from messages import get_welcome_messages, get_retry_message_by_attempt, approval_text, approval_keyboard, APPROVE_BUTTON_TEXT, DECLINE_BUTTON_TEXT, code_approved_message, code_not_received_message, not_approved_message, nice_keyboard, nice_keyboard_message, remove_keyboard_message, full_access_message, error_human_funny_message, get_unsupported_message_response, get_code_request_message
from notifications import handle_critical_error
# 🗑️ הסרת כל הייבואים מ-sheets_handler - עברנו למסד נתונים!
# ✅ החלפה לפונקציות מסד נתונים ו-profile_utils  
import profile_utils as _pu
from gpt_a_handler import get_main_response
from gpt_b_handler import get_summary
from gpt_c_handler import extract_user_info, should_run_gpt_c
from gpt_d_handler import smart_update_profile_with_gpt_d, smart_update_profile_with_gpt_d_async
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

def format_text_for_telegram(text):
    """
    📀 כללי פורמטינג: גרסה רשמית ומתוקנת
    מטרה: לטשטש את הפער בין שפה אנושית לשפה מודלית ולייצר טקסט טבעי, מדורג וקריא
    """
    import re
    import time
    
    # 🛡️ הגנה נוספת: מעקב זמן לכל הריצה של הפונקציה
    start_time = time.time()
    
    # רג'קס לזיהוי אימוג'ים
    emoji_pattern = re.compile(
        r"[\U0001F600-\U0001F64F"
        r"\U0001F300-\U0001F6FF"
        r"\U0001F700-\U0001F77F"
        r"\U0001F780-\U0001F7FF"
        r"\U0001F800-\U0001F8FF"
        r"\U0001F900-\U0001F9FF"
        r"\U0001FA00-\U0001FA6F"
        r"\U0001FA70-\U0001FAFF"
        r"\U00002702-\U000027B0"
        r"\U000024C2-\U0001F251]"
    )
    
    original_text = text
    debug_info = {
        "removed_dots": 0,
        "added_line_breaks": 0,
        "total_emojis": 0,
        "emojis_removed": 0,
        "text_length_before": len(text),
        "text_length_after": 0,
        "formatting_applied": True
    }

    # 🔢 שלב 0 – ניקוי עיצוב קיים וסימני שאלה מיותרים
    # מנקה תגיות HTML קיימות כדי למנוע בלבול
    text = re.sub(r'<[^>]+>', '', text)
    
    # תיקון: הסרת סימני שאלה בודדים בתחילת ובסוף הטקסט
    text = re.sub(r'^[?]+', '', text)  # הסר סימני שאלה מתחילת הטקסט
    text = re.sub(r'[?]{2,}$', '?', text)  # שמור רק סימן שאלה אחד בסוף
    
    # 🔢 שלב 1 – המרת סימני Markdown לתגיות HTML
    # 🔁 המרות: תחילה ממירים הדגשה כפולה (bold), אחר כך הדגשה בודדת (underline), כדי למנוע חפיפות
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<u>\1</u>', text)
    text = re.sub(r'_(.*?)_', r'<u>\1</u>', text)
    
    # 🔢 שלב 2 – ניקוי HTML בסיסי
    # <br>, <br/>, <br /> → \n
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<br\s*/>', '\n', text)
    text = re.sub(r'<br\s*/\s*>', '\n', text)
    # <i> → <b>
    text = re.sub(r'<i>', '<b>', text)
    text = re.sub(r'</i>', '</b>', text)
    
    # מנקה תגיות כפולות מקוננות (כמו <b><b>טקסט</b></b> או <u><u>טקסט</u></u>) עם הגבלת לולאה בטוחה
    for tag in ['b', 'u']:
        pattern = fr'(<{tag}>)+(.+?)(</{tag}>)+'
        loop_limit = 10
        for _ in range(loop_limit):
            new_text = re.sub(pattern, fr'<{tag}>\2</{tag}>', text)
            if new_text == text:
                break
            text = new_text

    # 🔢 שלב 3 – ניקוי ראשוני של מעברי שורה
    # שומר רק על מעברי שורה כפולים (\n\n) – כל שאר מעברי השורה נמחקים זמנית
    text = re.sub(r'\n(?!\n)', ' ', text)
    
    # 🔢 שלב 4 – נשימות: פיסוק → שורות
    # 🨁 כל משפט = נשימה → מסתיים במעבר שורה
    
    # ספירת נקודות לפני המחיקה
    debug_info["removed_dots"] = len(re.findall(r'\.(\s*)', text))
    
    # . 🧽 → 🧽\n (מעבר שורה רק אחרי האימוג'י)
    text = re.sub(r'\.(\s*)(' + emoji_pattern.pattern + r')', r' \2\n', text)
    
    # . → מוחלף ב־\n
    text = re.sub(r'\.(\s*)', '\n', text)
    
    # ? או ! → נשארים + \n, אלא אם אחריהם אימוג'י – ואז השבירה תבוא אחרי האימוג'י
    # כלל קריטי: אין שבירה בין סימן שאלה/קריאה לאימוג'י. רק אחרי שניהם יחד
    # תיקון: רק אם הסימן מגיע אחרי תו שאינו רווח (למנוע סימנים בודדים)
    text = re.sub(r'([?!])\s*(' + emoji_pattern.pattern + r')', r'\1 \2\n', text)
    text = re.sub(r'(\S[?!]+)(?!\s*' + emoji_pattern.pattern + r')', r'\1\n', text)
    
    # כלל חדש: אם יש אימוג'י באמצע משפט → נשמר + \n אחרי האימוג'י
    # אבל רק אם אין פיסוק לפניו
    text = re.sub(r'([^.!?])\s*(' + emoji_pattern.pattern + r')(?!\s*[.!?]|\s*\n)', r'\1 \2\n', text)

    # 🔢 שלב 5 – ניקוי רווחים אחרי החלפת נקודות
    text = re.sub(r'\n\s+', '\n', text)

    # 🔢 שלב 6 – מניעת אימוג'ים בתחילת שורה
    # אין לאפשר מצב שבו שורה מתחילה באימוג'י (כולל אחרי פסקה)
    # מחברים אימוג'י לשורה שלפניו, גם אם יש רווח/מעבר שורה ביניהם
    # כולל מקרים כמו ?\n🤔 → ? 🤔\n
    text = re.sub(r'\n(' + emoji_pattern.pattern + r')', r' \1', text)

    # 🔢 שלב 7 – אימוג'י לפני תגיות <b> / <u>
    # אם אימוג'י מופיע מיד לפני תגית (עם או בלי רווח/פיסוק) – נכניס אותו לתוך התגית
    text = re.sub(r'(' + emoji_pattern.pattern + r')[\s.,]*(<(b|u)>)', r'\2\1 ', text)

    # 🔢 שלב 8 – הגבלת אימוג'ים + רג'קס זיהוי
    # יחס מקסימלי: 1 אימוג'י לכל 40 תווים
    # שימור מבוקר לפי פיזור תווים
    all_emojis = emoji_pattern.findall(text)
    debug_info["total_emojis"] = len(all_emojis)
    
    if len(all_emojis) > 0:
        allowed = max(1, len(text) // 40)
        if len(all_emojis) > allowed:
            keep_every = len(all_emojis) // allowed if allowed < len(all_emojis) else 1
            keep = {i for i in range(len(all_emojis)) if i % keep_every == 0}
            
            count = -1
            def emoji_replacer(m):
                nonlocal count
                count += 1
                return m.group(0) if count in keep else ''
            
            text = emoji_pattern.sub(emoji_replacer, text)
            debug_info["emojis_removed"] = len(all_emojis) - len(emoji_pattern.findall(text))

    # 🔢 שלב 9 – ניקוי סופי
    # רצף של יותר מ־2 מעברי שורה → מצמצמים ל־2 בלבד
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # שורות שמכילות רק אימוג'ים או סימני שאלה בודדים → מחוברות לשורה שמעליה
    lines = text.split('\n')
    cleaned = []
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        # אם זו שורה עם אימוג'י בלבד, או סימן שאלה בודד - מחבר לשורה קודמת
        if ((emoji_pattern.fullmatch(line_stripped) or line_stripped == '?') and i > 0 and cleaned):
            # מוסיף לשורה הקודמת במקום ליצור שורה נפרדת
            cleaned[-1] += ' ' + line_stripped if line_stripped != '?' else '?'
        else:
            cleaned.append(line_stripped)
    text = '\n'.join(cleaned)

    # 🛠️ שלב 10 – DEBUG INFO
    debug_info["text_length_after"] = len(text)
    debug_info["added_line_breaks"] = text.count('\n')
    
    # 🛡️ הגנה נוספת: בדיקת timeout
    if time.time() - start_time > 2:
        raise TimeoutError("format_text לקחה יותר מדי זמן — ייתכן לולאה אינסופית")
    
    # לצורך בדיקות: שמור גם את הטקסט לפני ואחרי הפורמטינג
    debug_info["original_text"] = original_text
    debug_info["formatted_text"] = text
    
    return text

async def _handle_holiday_check(update, chat_id, bot_reply):
    """
    בודק אם יש חג או אירוע מיוחד היום ושולח הודעה מתאימה
    """
    try:
        from chat_utils import get_holiday_system_message
        
        holiday_message = get_holiday_system_message(safe_str(chat_id), bot_reply)
        if holiday_message:
            await send_system_message(update, chat_id, holiday_message)
            
    except Exception as e:
        logger.error(f"שגיאה בבדיקת חגים: {e}", source="message_handler")

# פונקציה לשליחת הודעה למשתמש (הועתקה מ-main.py כדי למנוע לולאת ייבוא)
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
    
    # 🐛 DEBUG: מידע על השליחה
    print("=" * 80)
    print("📤 SEND_MESSAGE DEBUG")
    print("=" * 80)
    print(f"📊 CHAT_ID: {safe_str(chat_id)}")
    print(f"📊 IS_BOT_MESSAGE: {is_bot_message}")
    print(f"📊 IS_GPT_A_RESPONSE: {is_gpt_a_response}")
    print(f"📝 ORIGINAL TEXT ({len(text)} chars):")
    print(f"   {repr(text)}")
    print(f"📊 NEWLINES: {text.count(chr(10))}")
    print(f"📊 DOTS: {text.count('.')}")
    print(f"📊 QUESTIONS: {text.count('?')}")
    print(f"📊 EXCLAMATIONS: {text.count('!')}")
    print("=" * 80)
    
    # 🔧 פורמטינג רק עבור תשובות מGPTA
    if is_gpt_a_response:
        print(f"🔧 [FORMATTING] מתחיל פורמטינג לתשובת GPTA: {len(text)} chars")
        formatted_text = format_text_for_telegram(text)
        print(f"🔧 [FORMATTING] פורמטינג הושלם | אורך: {len(formatted_text)} chars")
    else:
        formatted_text = text
        print(f"🚫 [FORMATTING] דולג על פורמטינג (לא תשובת GPTA)")
    
    if should_log_message_debug():
        print(f"[SEND_MESSAGE] chat_id={safe_str(chat_id)} | text={formatted_text.replace(chr(10), ' ')[:120]}", flush=True)
    
    try:
        bot_id = None
        if hasattr(update, 'message') and hasattr(update.message, 'bot') and update.message.bot:
            bot_id = getattr(update.message.bot, 'id', None)
        elif hasattr(update, 'bot'):
            bot_id = getattr(update.bot, 'id', None)
        
        if should_log_debug_prints():
            print(f"[DEBUG] SENDING MESSAGE: from bot_id={bot_id} to chat_id={safe_str(chat_id)}", flush=True)
    except Exception as e:
        if should_log_debug_prints():
            print(f"[DEBUG] לא הצלחתי להוציא bot_id: {e}", flush=True)
    import sys; sys.stdout.flush()
    
    # 🔧 תיקון קריטי: Progressive timeout אופטימלי ו-retry mechanism למניעת timeout errors
    try:
        max_retries = 5  # 6 ניסיונות סה"כ (0-5)
        timeout_seconds = TimeoutConfig.TELEGRAM_API_TIMEOUT_PROGRESSIVE  # Progressive timeout אופטימלי! 🚀
        
        for attempt in range(max_retries + 1):
            current_timeout = timeout_seconds[min(attempt, len(timeout_seconds) - 1)]
            try:
                # שליחה עם timeout הדרגתי אופטימלי
                sent_message = await asyncio.wait_for(
                    update.message.reply_text(formatted_text, parse_mode="HTML"),
                    timeout=current_timeout
                )
                
                if should_log_message_debug():
                    print(f"[TELEGRAM_REPLY] ✅ Success on attempt {attempt + 1} with {current_timeout}s timeout | message_id={getattr(sent_message, 'message_id', None)} | chat_id={safe_str(chat_id)}", flush=True)
                
                logger.info(f"[TELEGRAM_REPLY] ✅ Success on attempt {attempt + 1} with {current_timeout}s timeout | message_id={getattr(sent_message, 'message_id', None)} | chat_id={safe_str(chat_id)}", source="message_handler")
                break  # הצלחה - יוצאים מהלולאה
                
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    next_timeout = timeout_seconds[min(attempt + 1, len(timeout_seconds) - 1)]
                    logger.warning(f"[TELEGRAM_TIMEOUT] ⏰ Timeout after {current_timeout}s on attempt {attempt + 1}/{max_retries + 1} for chat_id={safe_str(chat_id)}, retrying with {next_timeout}s...", source="message_handler")
                    print(f"⚠️ [TELEGRAM_TIMEOUT] ⏰ Timeout after {current_timeout}s - retrying with {next_timeout}s timeout...")
                    await asyncio.sleep(1)  # חכה רק שנייה אחת - מהיר יותר!
                    continue
                else:
                    # כל הניסיונות נכשלו - זורקים שגיאה
                    raise Exception(f"Telegram API timeout after {max_retries + 1} attempts (timeouts: {timeout_seconds})")
                    
            except Exception as e:
                if attempt < max_retries and ("network" in str(e).lower() or "timeout" in str(e).lower() or "connection" in str(e).lower()):
                    next_timeout = timeout_seconds[min(attempt + 1, len(timeout_seconds) - 1)]
                    logger.warning(f"[TELEGRAM_RETRY] 🌐 Network error on attempt {attempt + 1}/{max_retries + 1}: {e}", source="message_handler")
                    print(f"⚠️ [TELEGRAM_RETRY] 🌐 Network error - retrying with {next_timeout}s timeout...")
                    await asyncio.sleep(1)  # חכה רק שנייה אחת - מהיר יותר!
                    continue
                else:
                    # שגיאה שלא ניתן לתקן או גמרנו הניסיונות
                    raise e
        else:
            # אם הגענו לכאן זה אומר שכל הניסיונות נכשלו (לא אמור לקרות)
            raise Exception(f"Failed to send message after {max_retries + 1} attempts")
                     
    except Exception as e:
        if should_log_message_debug():
            print(f"[ERROR] שליחת הודעה נכשלה: {e}", flush=True)
        
        logger.error(f"[ERROR] שליחת הודעה נכשלה: {e}", source="message_handler")
        # 🗑️ הסרת log_event_to_file - עברנו למסד נתונים
        try:
            from notifications import send_error_notification
            send_error_notification(error_message=f"[send_message] שליחת הודעה נכשלה: {e}", chat_id=safe_str(chat_id), user_msg=formatted_text)
        except Exception as notify_err:
            if should_log_message_debug():
                print(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}", flush=True)
            logger.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}", source="message_handler")
        return
    if is_bot_message:
        # 🔧 תיקון: שמירת הודעת מערכת נכון - הבוט שלח, לא המשתמש
        update_chat_history(safe_str(chat_id), "", formatted_text)  # הודעת מערכת - אין הודעת משתמש
    # 🗑️ הוחלף ב-logger פשוט
    logger.info(f"הודעה נשלחה: {formatted_text[:100]}...", source="message_handler", chat_id=chat_id)
    if should_log_message_debug():
        print(f"[BOT_MSG] {formatted_text.replace(chr(10), ' ')[:120]}")

# פונקציה לשליחת הודעת אישור (הועתקה מ-main.py)
async def send_approval_message(update, chat_id):
    """
    שולחת הודעת אישור תנאים למשתמש, עם מקלדת מותאמת.
    קלט: update, chat_id
    פלט: אין (שולחת הודעה)
    """
    approval_msg = approval_text() + "\n\nאנא לחץ על 'מאשר' או 'לא מאשר' במקלדת למטה."
    # ❌ לא עושים פורמטינג להודעות מערכת - רק לתשובות GPT-A
    
    try:
        # 🔧 תיקון קריטי: Progressive timeout אופטימלי גם להודעת אישור
        max_retries = 5  # 6 ניסיונות סה"כ (0-5)
        timeout_seconds = TimeoutConfig.TELEGRAM_API_TIMEOUT_PROGRESSIVE  # Progressive timeout אופטימלי! 🚀
        
        for attempt in range(max_retries + 1):
            current_timeout = timeout_seconds[min(attempt, len(timeout_seconds) - 1)]
            try:
                await asyncio.wait_for(
                    update.message.reply_text(
                        approval_msg,
                        reply_markup=ReplyKeyboardMarkup(approval_keyboard(), one_time_keyboard=True, resize_keyboard=True)
                    ),
                    timeout=current_timeout
                )
                break  # הצלחה - יוצאים מהלולאה
                
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    next_timeout = timeout_seconds[min(attempt + 1, len(timeout_seconds) - 1)]
                    logger.warning(f"[APPROVAL_MSG_TIMEOUT] ⏰ Timeout after {current_timeout}s on attempt {attempt + 1}/{max_retries + 1} for chat_id={safe_str(chat_id)}, retrying with {next_timeout}s...", source="message_handler")
                    await asyncio.sleep(1)  # חכה רק שנייה אחת - מהיר יותר!
                    continue
                else:
                    raise Exception(f"Approval message timeout after {max_retries + 1} attempts (timeouts: {timeout_seconds})")
                    
            except Exception as e:
                if attempt < max_retries and ("network" in str(e).lower() or "timeout" in str(e).lower() or "connection" in str(e).lower()):
                    next_timeout = timeout_seconds[min(attempt + 1, len(timeout_seconds) - 1)]
                    logger.warning(f"[APPROVAL_MSG_RETRY] 🌐 Network error on attempt {attempt + 1}/{max_retries + 1}: {e}", source="message_handler")
                    await asyncio.sleep(1)  # חכה רק שנייה אחת - מהיר יותר!
                    continue
                else:
                    raise e
        
        # 🔧 תיקון: עדכון היסטוריה נכון - הבוט שלח, לא המשתמש
        update_chat_history(safe_str(chat_id), "", approval_msg)  # הודעת מערכת - אין הודעת משתמש
        # 🗑️ הוחלף ב-logger פשוט
        logger.info("הודעת אישור נשלחה", source="message_handler", chat_id=chat_id)
        
    except Exception as e:
        logger.error(f"[ERROR] שליחת הודעת אישור נכשלה: {e}", source="message_handler")
        # ניסיון שליחה רגילה ללא מקלדת
        await send_system_message(update, chat_id, approval_msg)

def detect_message_type(message):
    """
    מזהה את סוג ההודעה שהתקבלה.
    קלט: message (telegram Message object)
    פלט: str - סוג ההודעה
    """
    if message.voice:
        return "voice"
    elif message.photo:
        return "photo"
    elif message.video:
        return "video"
    elif message.document:
        return "document"
    elif message.sticker:
        return "sticker"
    elif message.audio:
        return "audio"
    elif message.animation:
        return "animation"
    elif message.video_note:
        return "video_note"
    elif message.location:
        return "location"
    elif message.contact:
        return "contact"
    else:
        return "unknown"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    הפונקציה הראשית שמטפלת בכל הודעה נכנסת מהמשתמש.
    קלט: update (אובייקט טלגרם), context (אובייקט קונטקסט)
    פלט: אין (מטפלת בכל הלוגיקה של הודעה)
    # מהלך מעניין: טיפול מלא ב-onboarding, הרשאות, לוגים, שילוב gpt, עדכון היסטוריה, והכל בצורה אסינכרונית.
    """
    
    # 🔧 מניעת כפילות - בדיקה אם ההודעה כבר טופלה
    try:
        chat_id = update.message.chat_id if hasattr(update, 'message') and hasattr(update.message, 'chat_id') else None
        message_id = update.message.message_id if hasattr(update, 'message') and hasattr(update.message, 'message_id') else None
        
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

    # 🐞 דיבאג היסטוריה - כמה הודעות יש בקובץ
    try:
        from chat_utils import get_user_stats_and_history
        chat_id = update.message.chat_id if hasattr(update, 'message') and hasattr(update.message, 'chat_id') else None
        if chat_id:
            stats, history = get_user_stats_and_history(safe_str(chat_id))
            print(f"[HISTORY_DEBUG] יש {len(history)} הודעות היסטוריה לצ'אט {safe_str(chat_id)}")
            for i, entry in enumerate(history[-3:]):
                user = entry.get('user', '')
                bot = entry.get('bot', '')
                print(f"  {i}: user=\"{user}\" | bot=\"{bot[:60]}{'...' if len(bot)>60 else ''}\"")
    except Exception as e:
        print(f"[HISTORY_DEBUG] שגיאה בדיבאג היסטוריה: {e}")

    # 🕐 מדידת זמן התחלה - מהרגע שהמשתמש לחץ אנטר
    user_request_start_time = time.time()
    
    try:
        log_payload = {
            "chat_id": None,
            "message_id": None,
            "timestamp_start": get_israel_time().isoformat()
        }
        try:
            chat_id = update.message.chat_id
            message_id = update.message.message_id
            
            # איפוס מצב תזכורת - המשתמש הגיב
            mark_user_active(safe_str(chat_id))
            
            if update.message.text:
                user_msg = update.message.text
            else:
                # זיהוי סוג ההודעה ושליחת הודעה מותאמת
                message_type = detect_message_type(update.message)
                
                # 🔧 תיקון זמני: הסרת תמיכה בהודעות קוליות
                # (עד שנפתור את בעיית ffmpeg בסביבת הענן)
                if message_type == "voice":
                    logger.info(f"🎤 התקבלה הודעה קולית (לא נתמכת כרגע) | chat_id={safe_str(chat_id)}", source="message_handler")
                    print(f"[VOICE_MSG_DISABLED] chat_id={safe_str(chat_id)} | message_id={message_id}")
                    
                    # הודעה למשתמש שהתכונה לא זמינה כרגע
                    voice_message = "🎤 מצטער, תמיכה בהודעות קוליות זמנית לא זמינה.\nאנא שלח את השאלה שלך בטקסט ואשמח לעזור! 😊"
                    await send_system_message(update, chat_id, voice_message)
                    
                    # רישום להיסטוריה ולוגים
                    # 🗑️ הוחלף ב-logger פשוט
                    logger.info("הודעה קולית נדחתה - תכונה זמנית לא זמינה", source="message_handler", chat_id=chat_id)
                    
                    await end_monitoring_user(safe_str(chat_id), True)
                    return
                
                else:
                    # הודעות לא-טקסט אחרות (לא voice)
                    appropriate_response = get_unsupported_message_response(message_type)
                    
                    logger.info(f"📩 התקבלה הודעה מסוג {message_type} | chat_id={safe_str(chat_id)}", source="message_handler")
                    print(f"[NON_TEXT_MSG] chat_id={safe_str(chat_id)} | message_id={message_id} | type={message_type}")
                    
                    # רישום להיסטוריה ולוגים  
                    # 🗑️ הוחלף ב-logger פשוט
                    logger.info(f"הודעה לא נתמכת מסוג {message_type}", source="message_handler", chat_id=chat_id)
                    
                    await send_system_message(update, chat_id, appropriate_response)
                    await end_monitoring_user(safe_str(chat_id), True)
                    return

            # 🚀 התחלת ניטור concurrent עם progressive notifications
            try:
                monitoring_result = await start_monitoring_user(safe_str(chat_id), str(message_id), update)
                if not monitoring_result:
                    await send_system_message(update, chat_id, "⏳ הבוט עמוס כרגע. אנא נסה שוב בעוד מספר שניות.")
                    return
            except Exception as e:
                logger.error(f"[MESSAGE_HANDLER] Error starting monitoring: {e}", source="message_handler")
                logger.error(f"[MESSAGE_HANDLER] Traceback: {traceback.format_exc()}", source="message_handler")
                await send_system_message(update, chat_id, "⚠️ שגיאה טכנית. נסה שוב בעוד כמה שניות.")
                return

            # 🗑️ פקודות סודיות הוסרו - עברנו לפקודות טלגרם רגילות /show_logs, /search_logs
            log_payload["chat_id"] = safe_str(chat_id)
            log_payload["message_id"] = message_id
            log_payload["user_msg"] = user_msg
            logger.info(f"📩 התקבלה הודעה | chat_id={safe_str(chat_id)}, message_id={message_id}, תוכן={user_msg!r}", source="message_handler")
            
            # 🔧 CRITICAL DEBUG: רישום כל הודעה נכנסת למסד נתונים למעקב
            try:
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO chat_messages (chat_id, user_msg, gpt_response, timestamp)
                        VALUES (%s, %s, %s, NOW())
                    ''', (
                        f"INCOMING_{safe_str(chat_id)}",
                        f"📥 הודעה נכנסת: {user_msg}",
                        "INCOMING_MESSAGE_LOG"
                    ))
                    conn.commit()
            except Exception as db_err:
                pass  # אל תיכשל בגלל דיבאג
            
            print(f"[IN_MSG] chat_id={safe_str(chat_id)} | message_id={message_id} | text={user_msg.replace(chr(10), ' ')[:120]}")
        except Exception as ex:
            logger.error(f"❌ שגיאה בשליפת מידע מההודעה: {ex}", source="message_handler")
            print(f"❌ שגיאה בשליפת מידע מההודעה: {ex}")
            
            # 🔧 הוספה: רישום בטוח למשתמש לרשימת התאוששות
            try:
                from notifications import safe_add_user_to_recovery_list
                if 'chat_id' in locals():
                    # הערה: כאן אין הודעה מקורית כי השגיאה היא בextraction של ההודעה עצמה
                    safe_add_user_to_recovery_list(safe_str(chat_id), f"Message extraction error: {str(ex)[:50]}", "")
            except Exception as e:
                logger.warning(f"[handle_message] שגיאה ברישום לרשימת התאוששות: {e}", source="message_handler")
            
            await handle_critical_error(ex, None, None, update)
            await end_monitoring_user(safe_str(chat_id) if 'chat_id' in locals() else "unknown", False)
            return

        # שלב 1: בדיקה מהירה של הרשאות משתמש - לפי המדריך!
        try:
            await update_user_processing_stage(safe_str(chat_id), "permission_check")
            logger.info("🔍 בודק הרשאות משתמש במסד נתונים...", source="message_handler")
            print("🔍 בודק הרשאות משתמש במסד נתונים...")
            
            # 🔨 ניקוי cache לפני בדיקת הרשאות (למקרה שהcache תקוע)
            try:
                # 🗑️ הסרנו cache clearing - עברנו למסד נתונים
                clear_result = {"success": True, "cleared_count": 0}
                if clear_result.get("success") and clear_result.get("cleared_count", 0) > 0:
                    print(f"🔨 נוקו {clear_result.get('cleared_count', 0)} cache keys לפני בדיקת הרשאות")
            except Exception as cache_err:
                print(f"⚠️ שגיאה בניקוי cache: {cache_err}")
            
            # 🆕 בדיקה מלאה של הרשאות ישירות במסד נתונים (לפי המדריך!)
            access_result = check_user_approved_status_db(safe_str(chat_id))
            status = access_result.get("status", "not_found")
            
            if status == "not_found":
                # משתמש חדש לגמרי - שליחת 3 הודעות קבלת פנים
                logger.info("[Onboarding] משתמש חדש - שליחת הודעות קבלת פנים", source="message_handler")
                print("[Onboarding] משתמש חדש - שליחת הודעות קבלת פנים")
                asyncio.create_task(handle_new_user_background(update, context, chat_id, user_msg))
                await end_monitoring_user(safe_str(chat_id), True)
                return
                
            elif status == "pending_code":
                # משתמש קיים עם שורה זמנית - צריך קוד
                logger.info("[Permissions] משתמש עם שורה זמנית - בקשת קוד", source="message_handler")
                print("[Permissions] משתמש עם שורה זמנית - בקשת קוד")
                asyncio.create_task(handle_unregistered_user_background(update, context, chat_id, user_msg))
                await end_monitoring_user(safe_str(chat_id), True)
                return
                
            elif status == "pending_approval":
                # משתמש קיים עם קוד אבל לא אישר תנאים - טיפול באישור
                logger.info("[Permissions] משתמש ממתין לאישור תנאים", source="message_handler")
                print("[Permissions] משתמש ממתין לאישור תנאים")
                asyncio.create_task(handle_pending_user_background(update, context, chat_id, user_msg))
                await end_monitoring_user(safe_str(chat_id), True)
                return
                
        except Exception as ex:
            logger.error(f"❌ שגיאה בבדיקת הרשאות משתמש: {ex}", source="message_handler")
            print(f"❌ שגיאה בבדיקת הרשאות משתמש: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            await end_monitoring_user(safe_str(chat_id), False)
            return

        # שלב 3: משתמש מאושר
        # אין טיפול מיוחד ב"אהלן" – כל הודעה, כולל 'אהלן', תנותב ישירות לבינה
        await update_user_processing_stage(safe_str(chat_id), "gpt_a")
        logger.info("👨‍💻 משתמש מאושר, שולח תשובה מיד...", source="message_handler")
        print("👨‍💻 משתמש מאושר, שולח תשובה מיד...")

        # 📊 עדכון מונה הודעות למשתמש
        try:
            from db_manager import increment_user_message_count
            increment_user_message_count(safe_str(chat_id))
        except Exception as count_err:
            logger.warning(f"⚠️ שגיאה בעדכון מונה הודעות: {count_err}", source="message_handler")

        try:
            # 🔧 תיקון קריטי: שליחת הודעת ביניים מהירה אחרי 3 שניות
            temp_message_task = None
            temp_message_sent = False
            
            async def send_temp_message():
                nonlocal temp_message_sent
                await asyncio.sleep(TimeoutConfig.TEMP_MESSAGE_DELAY)  # חכה לפי תצורה מרכזית
                if not temp_message_sent:
                    try:
                        temp_msg = "⏳ אני עובד על תשובה בשבילך... זה מיד אצלך... 🚀"
                        await send_system_message(update, chat_id, temp_msg)
                        temp_message_sent = True
                        logger.info(f"📤 [TEMP_MSG] נשלחה הודעה זמנית | chat_id={safe_str(chat_id)}", source="message_handler")
                    except Exception as temp_err:
                        logger.warning(f"⚠️ [TEMP_MSG] לא הצלחתי לשלוח הודעה זמנית: {temp_err}", source="message_handler")
            
            # התחלת הודעת ביניים ברקע
            temp_message_task = asyncio.create_task(send_temp_message())

            # 🔧 תיקון קריטי: איסוף נתונים מהיר בלבד - בלי Google Sheets!
            # שלב 1: איסוף נתונים מהיר מקובץ מקומי בלבד
            current_summary = ""
            history_messages = []
            
            print(f"🔧 [DEBUG] מתחיל טעינת נתונים עבור {safe_str(chat_id)}")
            
            try:
                print(f"🔧 [DEBUG] מייבא get_chat_history_simple")
                from chat_utils import get_chat_history_simple
                
                print(f"🔧 [DEBUG] קורא להיסטוריה עבור {safe_str(chat_id)}")
                history_messages = get_chat_history_simple(safe_str(chat_id), limit=32)
                print(f"🔧 [DEBUG] היסטוריה הוחזרה: {len(history_messages) if history_messages else 0} הודעות")
                
                # DEBUG: שמירה במסד נתונים
                try:
                    with db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO chat_messages (chat_id, user_msg, gpt_response, timestamp)
                            VALUES (%s, %s, %s, NOW())
                        ''', (
                            f"DEBUG_{safe_str(chat_id)}",
                            f"🔧 HISTORY_DEBUG: קיבלתי {len(history_messages) if history_messages else 0} הודעות היסטוריה",
                            "DEBUG_ENTRY"
                        ))
                        conn.commit()
                except Exception as db_err:
                    pass  # אל תיכשל בגלל דיבאג
                
                print(f"🔧 [DEBUG] מייבא get_user_summary_fast")
                from profile_utils import get_user_summary_fast
                
                print(f"🔧 [DEBUG] קורא לסיכום עבור {safe_str(chat_id)}")
                current_summary = get_user_summary_fast(safe_str(chat_id)) or ""
                print(f"🔧 [DEBUG] סיכום הוחזר: '{current_summary}'")
                
                print(f"✅ [DEBUG] טעינת נתונים הושלמה בהצלחה עבור {safe_str(chat_id)}")
                    
            except Exception as data_err:
                print(f"🚨 [HISTORY_DEBUG] שגיאה בטעינת נתונים עבור {safe_str(chat_id)}: {data_err}")
                print(f"🚨 [HISTORY_DEBUG] exception type: {type(data_err).__name__}")
                print(f"🚨 [HISTORY_DEBUG] full traceback:")
                traceback.print_exc()
                
                # שמירת השגיאה במסד נתונים למעקב
                try:
                    with db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO chat_messages (chat_id, user_msg, gpt_response, timestamp)
                            VALUES (%s, %s, %s, NOW())
                        ''', (
                            f"ERROR_{safe_str(chat_id)}",
                            f"🚨 HISTORY_ERROR: {type(data_err).__name__}: {str(data_err)[:200]}",
                            f"ERROR_TRACEBACK: {traceback.format_exc()[:500]}"
                        ))
                        conn.commit()
                except Exception as db_err:
                    pass  # אל תיכשל בגלל דיבאג
                
                logger.warning(f"[FAST_DATA] שגיאה באיסוף נתונים מהיר: {data_err}", source="message_handler")
                # אין נתונים - ממשיכים בלי היסטוריה (מעדיפים מהירות על שלמות נתונים)
            
            # בניית ההודעות ל-gpt_a - מינימלי ומהיר
            messages_for_gpt = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            # הוספת סיכום משתמש אם יש (מהיר)
            if current_summary:
                messages_for_gpt.append({"role": "system", "content": f"🎯 מידע על המשתמש: {current_summary}"})
            
            # הוספת היסטוריה (מהיר)
            print(f"🔍 [HISTORY_DEBUG] history_messages לאחר טעינה: {len(history_messages) if history_messages else 0} הודעות")
            if history_messages:
                messages_for_gpt.extend(history_messages)
                print(f"✅ [HISTORY_DEBUG] הוספו {len(history_messages)} הודעות היסטוריה ל-messages_for_gpt")
            else:
                print(f"❌ [HISTORY_DEBUG] לא הוספו הודעות היסטוריה - history_messages ריק!")
            
            # הוספת ההודעה החדשה
            messages_for_gpt.append({"role": "user", "content": user_msg})
            
            print(f"📤 [GPT_A] שולח {len(messages_for_gpt)} הודעות ל-GPT-A (מהיר)")

            # שלב 2: שליחת תשובה מ-gpt_a - זה השלב הכי חשוב!
            gpt_result = get_main_response(messages_for_gpt, safe_str(chat_id))
            bot_reply = gpt_result.get("bot_reply") if isinstance(gpt_result, dict) else gpt_result
            
            if not bot_reply:
                error_msg = error_human_funny_message()
                await send_system_message(update, chat_id, error_msg)
                await end_monitoring_user(safe_str(chat_id), False)
                return

            # 🔧 תיקון: ביטול הודעת ביניים אם התשובה הגיעה מהר
            if temp_message_task and not temp_message_task.done():
                temp_message_task.cancel()
                temp_message_sent = True  # מונע שליחה כפולה

            # שלב 3: שליחת התשובה למשתמש מיד!
            await send_message(update, chat_id, bot_reply, is_bot_message=True, is_gpt_a_response=True)

            # 📨 שליחת התכתבות אנונימית לאדמין
            try:
                from admin_notifications import send_anonymous_chat_notification
                # חישוב זמני תגובה
                current_time = time.time()
                user_response_time = current_time - user_request_start_time
                gpt_response_time = gpt_result.get("gpt_pure_latency", 0) if isinstance(gpt_result, dict) else 0
                
                send_anonymous_chat_notification(
                    user_msg, 
                    bot_reply, 
                    history_messages, 
                    messages_for_gpt,
                    gpt_timing=gpt_response_time,
                    user_timing=user_response_time
                )
            except Exception as admin_chat_err:
                logger.warning(f"שגיאה בשליחת התכתבות לאדמין: {admin_chat_err}", source="message_handler")

            # 🔧 תיקון: כל השאר ברקע - המשתמש כבר קיבל תשובה!
            asyncio.create_task(handle_background_tasks(update, context, chat_id, user_msg, bot_reply, message_id, user_request_start_time, gpt_result))
            
        except Exception as ex:
            logger.error(f"❌ שגיאה בטיפול בהודעה: {ex}", source="message_handler")
            print(f"❌ שגיאה בטיפול בהודעה: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            await end_monitoring_user(safe_str(chat_id), False)
            return

        # סיום ניטור
        await end_monitoring_user(safe_str(chat_id), True)

    except Exception as ex:
        logger.error(f"❌ שגיאה קריטית בטיפול בהודעה: {ex}", source="message_handler")
        print(f"❌ שגיאה קריטית בטיפול בהודעה: {ex}")
        await handle_critical_error(ex, None, None, update)
        if 'chat_id' in locals():
            await end_monitoring_user(safe_str(chat_id), False)

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

async def handle_background_tasks(update, context, chat_id, user_msg, bot_reply, message_id, user_request_start_time, gpt_result):
    """
    🔧 פונקציה חדשה: מטפלת בכל המשימות ברקע אחרי שהמשתמש קיבל תשובה
    זה מבטיח שהמשתמש מקבל תשובה מהר, וכל השאר קורה ברקע
    """
    try:
        # חישוב זמן מענה
        response_time = time.time() - user_request_start_time
        
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
        
        logger.info(f"🔄 [BACKGROUND] התחלת משימות ברקע | chat_id={safe_str(chat_id)} | זמן תגובה: {response_time:.2f}s", source="message_handler")
        
        # שלב 1: עדכון היסטוריה
        try:
            update_chat_history(safe_str(chat_id), user_msg, bot_reply)
        except Exception as hist_err:
            logger.warning(f"[BACKGROUND] שגיאה בעדכון היסטוריה: {hist_err}", source="message_handler")
        
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
        
        logger.info(f"✅ [BACKGROUND] סיום משימות ברקע | chat_id={safe_str(chat_id)} | זמן כולל: {time.time() - user_request_start_time:.2f}s", source="message_handler")
        
        # שלב 5: התראות אדמין (אם יש שינויים)
        try:
            from profile_utils import _send_admin_profile_overview_notification, _detect_profile_changes, get_user_profile_fast, get_user_summary_fast
            
            # 🔧 תיקון: שמירת הפרופיל הישן לפני כל העדכונים
            old_profile_before_updates = get_user_profile_fast(safe_str(chat_id))
            
            gpt_c_changes = []
            gpt_d_changes = []
            gpt_e_changes = []
            
            # GPT-C changes
            if should_run_gpt_c(user_msg) and gpt_c_result is not None and not isinstance(gpt_c_result, Exception):
                extracted_fields = gpt_c_result.get("extracted_fields", {}) if isinstance(gpt_c_result, dict) else {}
                new_profile = {**old_profile_before_updates, **extracted_fields}
                gpt_c_changes = _detect_profile_changes(old_profile_before_updates, new_profile)
            
            # GPT-D changes
            gpt_d_res = results[0] if len(results) > 0 else None
            if gpt_d_res is not None and not isinstance(gpt_d_res, Exception):
                updated_profile, usage = gpt_d_res if isinstance(gpt_d_res, tuple) else (None, {})
                if updated_profile and isinstance(updated_profile, dict):
                    gpt_d_changes = _detect_profile_changes(old_profile_before_updates, updated_profile)
            
            # GPT-E changes
            gpt_e_res = results[1] if len(results) > 1 else None
            if gpt_e_res is not None and not isinstance(gpt_e_res, Exception):
                changes = gpt_e_res.get("changes", {}) if isinstance(gpt_e_res, dict) else {}
                if changes:
                    new_profile = {**old_profile_before_updates, **changes}
                    gpt_e_changes = _detect_profile_changes(old_profile_before_updates, new_profile)
            
            # שליחת התראה רק אם יש שינויים
            if gpt_c_changes or gpt_d_changes or gpt_e_changes:
                # ✅ תיקון: בניית מידע רק למודלים עם שינויים בפועל
                gpt_c_info = f"GPT-C: {len(gpt_c_changes)} שדות" if gpt_c_changes else ""
                gpt_d_info = f"GPT-D: {len(gpt_d_changes)} שדות" if gpt_d_changes else ""
                
                # ✅ הוספת קאונטר ל-GPT-E רק אם יש שינויים
                gpt_e_info = ""
                if gpt_e_changes:
                    try:
                        from chat_utils import get_user_stats_and_history
                        from gpt_e_handler import GPT_E_RUN_EVERY_MESSAGES
                        stats, _ = get_user_stats_and_history(safe_str(chat_id))
                        total_messages = stats.get("total_messages", 0)
                        gpt_e_counter = f" ({total_messages}/{GPT_E_RUN_EVERY_MESSAGES})"
                    except:
                        gpt_e_counter = ""
                    
                    gpt_e_info = f"GPT-E: {len(gpt_e_changes)} שדות{gpt_e_counter}"
                
                # יצירת סיכום מהיר
                current_summary = get_user_summary_fast(safe_str(chat_id)) or ""
                
                _send_admin_profile_overview_notification(
                    chat_id=safe_str(chat_id),
                    user_msg=user_msg,
                    gpt_c_changes=gpt_c_changes,
                    gpt_d_changes=gpt_d_changes,
                    gpt_e_changes=gpt_e_changes,
                    gpt_c_info=gpt_c_info,
                    gpt_d_info=gpt_d_info,
                    gpt_e_info=gpt_e_info,
                    summary=current_summary
                )
                
        except Exception as admin_err:
            logger.warning(f"[BACKGROUND] שגיאה בשליחת התראה לאדמין: {admin_err}", source="message_handler")
        
        logger.info(f"✅ [BACKGROUND] סיום משימות ברקע | chat_id={safe_str(chat_id)} | זמן כולל: {time.time() - user_request_start_time:.2f}s", source="message_handler")
        
    except Exception as ex:
        logger.error(f"❌ [BACKGROUND] שגיאה במשימות ברקע: {ex}", source="message_handler")
        # לא נכשל אם המשימות ברקע נכשלות - המשתמש כבר קיבל תשובה
