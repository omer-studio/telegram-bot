"""
message_handler.py
------------------
קובץ זה מרכז את כל הטיפול בהודעות ועיצוב, פורמטינג, ושליחה של הודעות.
הרציונל: ריכוז כל ניהול ההודעות, פורמטינג, שגיאות, וחוויית משתמש במקום אחד.
"""

import logging
import asyncio
import re
import json
import time
import telegram
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from config import (
    BOT_TOKEN, 
    ADMIN_NOTIFICATION_CHAT_ID, 
    ADMIN_BOT_TELEGRAM_TOKEN,
    MAX_MESSAGE_LENGTH,
    ADMIN_CHAT_ID,
    MAX_CODE_TRIES
)
from utils import log_error_stat, get_israel_time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from datetime import datetime
from utils import handle_secret_command, log_event_to_file, update_chat_history, get_chat_history_messages, update_last_bot_message
from config import should_log_message_debug, should_log_debug_prints
from messages import get_welcome_messages, get_retry_message_by_attempt, approval_text, approval_keyboard, APPROVE_BUTTON_TEXT, DECLINE_BUTTON_TEXT, code_approved_message, code_not_received_message, not_approved_message, nice_keyboard, nice_keyboard_message, remove_keyboard_message, full_access_message, error_human_funny_message, get_unsupported_message_response
from notifications import handle_critical_error
from sheets_handler import increment_code_try, get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user, ensure_user_state_row, find_chat_id_in_sheet, increment_gpt_c_run_count, get_user_state
from gpt_a_handler import get_main_response
from gpt_b_handler import get_summary
from gpt_c_handler import extract_user_info, should_run_gpt_c
from gpt_d_handler import smart_update_profile_with_gpt_d, smart_update_profile_with_gpt_d_async
from gpt_utils import normalize_usage_dict
from fields_dict import FIELDS_DICT
from gpt_e_handler import execute_gpt_e_if_needed
from concurrent_monitor import start_monitoring_user, update_user_processing_stage, end_monitoring_user
from notifications import mark_user_active
from utils import should_send_time_greeting, get_time_greeting_instruction
import profile_utils as _pu

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
        
        holiday_message = get_holiday_system_message(str(chat_id), bot_reply)
        if holiday_message:
            await send_system_message(update, chat_id, holiday_message)
            
    except Exception as e:
        logging.error(f"שגיאה בבדיקת חגים: {e}")

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
        logging.critical(f"🚨 BLOCKED INTERNAL MESSAGE TO USER! chat_id={chat_id} | text={text[:100]}")
        print(f"🚨🚨🚨 CRITICAL: חסימת הודעה פנימית למשתמש! chat_id={chat_id}")
        return
    
    # 🐛 DEBUG: מידע על השליחה
    print("=" * 80)
    print("📤 SEND_MESSAGE DEBUG")
    print("=" * 80)
    print(f"📊 CHAT_ID: {chat_id}")
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
        print(f"[SEND_MESSAGE] chat_id={chat_id} | text={formatted_text.replace(chr(10), ' ')[:120]}", flush=True)
    
    try:
        bot_id = None
        if hasattr(update, 'message') and hasattr(update.message, 'bot') and update.message.bot:
            bot_id = getattr(update.message.bot, 'id', None)
        elif hasattr(update, 'bot'):
            bot_id = getattr(update.bot, 'id', None)
        
        if should_log_debug_prints():
            print(f"[DEBUG] SENDING MESSAGE: from bot_id={bot_id} to chat_id={chat_id}", flush=True)
    except Exception as e:
        if should_log_debug_prints():
            print(f"[DEBUG] לא הצלחתי להוציא bot_id: {e}", flush=True)
    import sys; sys.stdout.flush()
    try:
        sent_message = await update.message.reply_text(formatted_text, parse_mode="HTML")
        
        if should_log_message_debug():
            print(f"[TELEGRAM_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}", flush=True)
        
        logging.info(f"[TELEGRAM_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}")
    except Exception as e:
        if should_log_message_debug():
            print(f"[ERROR] שליחת הודעה נכשלה: {e}", flush=True)
        
        logging.error(f"[ERROR] שליחת הודעה נכשלה: {e}")
        log_event_to_file({
            "chat_id": chat_id,
            "bot_message": formatted_text,
            "timestamp": get_israel_time().isoformat(),
            "error": str(e)
        })
        try:
            from notifications import send_error_notification
            send_error_notification(error_message=f"[send_message] שליחת הודעה נכשלה: {e}", chat_id=chat_id, user_msg=formatted_text)
        except Exception as notify_err:
            if should_log_message_debug():
                print(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}", flush=True)
            logging.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}")
        return
    if is_bot_message:
        update_chat_history(chat_id, "[הודעה אוטומטית מהבוט]", formatted_text)
    log_event_to_file({
        "chat_id": chat_id,
        "bot_message": formatted_text,
        "timestamp": get_israel_time().isoformat()
    })
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
        await update.message.reply_text(
            approval_msg,
            reply_markup=ReplyKeyboardMarkup(approval_keyboard(), one_time_keyboard=True, resize_keyboard=True)
        )
        
        # עדכון היסטוריה ולוגים
        update_chat_history(chat_id, "[הודעה אוטומטית מהבוט]", approval_msg)
        log_event_to_file({
            "chat_id": chat_id,
            "bot_message": approval_msg,
            "timestamp": get_israel_time().isoformat(),
            "message_type": "approval_request"
        })
        
    except Exception as e:
        logging.error(f"[ERROR] שליחת הודעת אישור נכשלה: {e}")
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
    from prompts import SYSTEM_PROMPT  # העברתי לכאן כדי למנוע circular import

    # 🐞 דיבאג היסטוריה - כמה הודעות יש בקובץ
    try:
        from chat_utils import get_user_stats_and_history
        chat_id = update.message.chat_id if hasattr(update, 'message') and hasattr(update.message, 'chat_id') else None
        if chat_id:
            stats, history = get_user_stats_and_history(chat_id)
            print(f"[HISTORY_DEBUG] יש {len(history)} הודעות היסטוריה לצ'אט {chat_id}")
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
            mark_user_active(chat_id)
            
            if update.message.text:
                user_msg = update.message.text
            else:
                # זיהוי סוג ההודעה ושליחת הודעה מותאמת
                message_type = detect_message_type(update.message)
                
                # 🔧 תיקון זמני: הסרת תמיכה בהודעות קוליות
                # (עד שנפתור את בעיית ffmpeg בסביבת הענן)
                if message_type == "voice":
                    logging.info(f"🎤 התקבלה הודעה קולית (לא נתמכת כרגע) | chat_id={chat_id}")
                    print(f"[VOICE_MSG_DISABLED] chat_id={chat_id} | message_id={message_id}")
                    
                    # הודעה למשתמש שהתכונה לא זמינה כרגע
                    voice_message = "🎤 מצטער, תמיכה בהודעות קוליות זמנית לא זמינה.\nאנא שלח את השאלה שלך בטקסט ואשמח לעזור! 😊"
                    await send_system_message(update, chat_id, voice_message)
                    
                    # רישום להיסטוריה ולוגים
                    log_event_to_file({
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "message_type": "voice",
                        "timestamp": get_israel_time().isoformat(),
                        "event_type": "voice_temporarily_disabled"
                    })
                    
                    await end_monitoring_user(str(chat_id), True)
                    return
                
                else:
                    # הודעות לא-טקסט אחרות (לא voice)
                    appropriate_response = get_unsupported_message_response(message_type)
                    
                    logging.info(f"📩 התקבלה הודעה מסוג {message_type} | chat_id={chat_id}")
                    print(f"[NON_TEXT_MSG] chat_id={chat_id} | message_id={message_id} | type={message_type}")
                    
                    # רישום להיסטוריה ולוגים
                    log_event_to_file({
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "message_type": message_type,
                        "bot_response": appropriate_response,
                        "timestamp": get_israel_time().isoformat(),
                        "event_type": "unsupported_message"
                    })
                    
                    await send_system_message(update, chat_id, appropriate_response)
                    await end_monitoring_user(str(chat_id), True)
                    return

            # 🚀 התחלת ניטור concurrent
            try:
                monitoring_result = await start_monitoring_user(str(chat_id), str(message_id))
                if not monitoring_result:
                    await send_system_message(update, chat_id, "⏳ הבוט עמוס כרגע. אנא נסה שוב בעוד מספר שניות.")
                    return
            except Exception as e:
                logging.error(f"[MESSAGE_HANDLER] Error starting monitoring: {e}")
                import traceback
                logging.error(f"[MESSAGE_HANDLER] Traceback: {traceback.format_exc()}")
                await send_system_message(update, chat_id, "⚠️ שגיאה טכנית. נסה שוב בעוד כמה שניות.")
                return

            did, reply = handle_secret_command(chat_id, user_msg)
            if did:
                await send_system_message(update, chat_id, reply)
                await end_monitoring_user(str(chat_id), True)
                return
            log_payload["chat_id"] = chat_id
            log_payload["message_id"] = message_id
            log_payload["user_msg"] = user_msg
            logging.info(f"📩 התקבלה הודעה | chat_id={chat_id}, message_id={message_id}, תוכן={user_msg!r}")
            print(f"[IN_MSG] chat_id={chat_id} | message_id={message_id} | text={user_msg.replace(chr(10), ' ')[:120]}")
        except Exception as ex:
            logging.error(f"❌ שגיאה בשליפת מידע מההודעה: {ex}")
            print(f"❌ שגיאה בשליפת מידע מההודעה: {ex}")
            
            # 🔧 הוספה: רישום בטוח למשתמש לרשימת התאוששות
            try:
                from notifications import safe_add_user_to_recovery_list
                if 'chat_id' in locals():
                    # הערה: כאן אין הודעה מקורית כי השגיאה היא בextraction של ההודעה עצמה
                    safe_add_user_to_recovery_list(str(chat_id), f"Message extraction error: {str(ex)[:50]}", "")
            except Exception:
                pass
            
            await handle_critical_error(ex, None, None, update)
            await end_monitoring_user(str(chat_id) if 'chat_id' in locals() else "unknown", False)
            return

        # שלב 1: בדיקה מהירה אם זה משתמש חדש (רק ב-user_states)
        try:
            await update_user_processing_stage(str(chat_id), "onboarding_check")
            logging.info("[Onboarding] בודק האם המשתמש פונה בפעם הראשונה בחייו...")
            print("[Onboarding] בודק האם המשתמש פונה בפעם הראשונה בחייו...")
            
            # בדיקה מהירה רק ב-user_states - לפי כותרות
            from sheets_core import find_chat_id_in_sheet
            sheet_states = context.bot_data["sheet_states"]
            
            # קריאת כותרות למציאת עמודת chat_id
            all_values = sheet_states.get_all_values()
            if all_values and len(all_values) > 0:
                headers = all_values[0]
                chat_id_col = None
                for i, header in enumerate(headers):
                    if header.lower() == "chat_id":
                        chat_id_col = i + 1  # gspread uses 1-based indexing
                        break
                
                if chat_id_col:
                    is_first_time = not find_chat_id_in_sheet(sheet_states, chat_id, col=chat_id_col)
                else:
                    # fallback למיקום קלאסי אם לא נמצאה עמודת chat_id
                    is_first_time = not find_chat_id_in_sheet(sheet_states, chat_id, col=1)
            else:
                # fallback למיקום קלאסי אם אין כותרות
                is_first_time = not find_chat_id_in_sheet(sheet_states, chat_id, col=1)
            
            if is_first_time:
                # אם זה משתמש חדש, עושים את כל הבדיקות המלאות ברקע
                asyncio.create_task(handle_new_user_background(update, context, chat_id, user_msg))
                await end_monitoring_user(str(chat_id), True)
                return
            else:
                logging.info("[Onboarding] המשתמש כבר התחיל או עבר תהליך רישום קודם.")
                print("[Onboarding] המשתמש כבר התחיל או עבר תהליך רישום קודם.")
        except Exception as ex:
            logging.error(f"[Onboarding] ❌ שגיאה באתחול משתמש חדש: {ex}")
            print(f"[Onboarding] ❌ שגיאה באתחול משתמש חדש: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            await end_monitoring_user(str(chat_id), False)
            return

        # שלב 2: בדיקה מהירה של הרשאות - בדיקת קיום והרשאה
        try:
            await update_user_processing_stage(str(chat_id), "permission_check")
            logging.info("🔍 בודק הרשאות משתמש מול הגיליון...")
            print("🔍 בודק הרשאות משתמש מול הגיליון...")
            
            # בדיקה מלאה של הרשאות במקום בדיקה רק של קיום
            access_result = check_user_access(context.bot_data["sheet"], chat_id)
            status = access_result.get("status", "not_found")
            
            if status == "not_found":
                # משתמש לא קיים - טיפול ברקע
                asyncio.create_task(handle_unregistered_user_background(update, context, chat_id, user_msg))
                await end_monitoring_user(str(chat_id), True)
                return
                
            elif status == "pending":
                # משתמש קיים אבל לא אישר תנאים - טיפול באישור
                asyncio.create_task(handle_pending_user_background(update, context, chat_id, user_msg))
                await end_monitoring_user(str(chat_id), True)
                return
                
        except Exception as ex:
            logging.error(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            print(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            await end_monitoring_user(str(chat_id), False)
            return

        # שלב 3: משתמש מאושר
        # בדיקה אם זה הכפתור "אהלן" - אם כן, מסירים את המקלדת
        if user_msg.strip() == "אהלן":
            await update.message.reply_text(
                "שמח לראות אותך! 😊",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # עדכון היסטוריה
            update_chat_history(chat_id, user_msg, "שמח לראות אותך! 😊")
            
            await end_monitoring_user(str(chat_id), True)
            return
        
        # שליחת תשובה מיד!
        await update_user_processing_stage(str(chat_id), "gpt_a")
        logging.info("👨‍💻 משתמש מאושר, שולח תשובה מיד...")
        print("👨‍💻 משתמש מאושר, שולח תשובה מיד...")

        try:
            # --- יצירת רשומה בהיסטוריה מראש ---
            # מונע מצב הודעה כפולה לפני שמירת תשובת GPT,
            # וכך נמנע שליחת ברכת "בוקר/לילה טוב" כפולה (Race-condition).
            history_entry_created = False
            try:
                update_chat_history(chat_id, user_msg, "")
                history_entry_created = True
            except Exception as hist_err:
                logging.warning(f"[HISTORY] לא הצלחתי ליצור רשומת היסטוריה מוקדמת: {hist_err}")

            # שלב 1: איסוף הנתונים הנדרשים לתשובה טובה (מהיר)
            current_summary = get_user_summary(chat_id) or ""
            history_messages = get_chat_history_messages(chat_id, limit=15)  # 🔧 הגבלה ל-15 הודעות לחסוך בטוקנים
            
            # יצירת טיימסטמפ והנחיות יום השבוע
            from utils import create_human_context_for_gpt, get_weekday_context_instruction, get_time_greeting_instruction
            from utils import should_send_time_greeting
            
            # ברכה מותאמת זמן נשלחת לפי תנאים (שיחה ראשונה, הודעת ברכה, החלפת בלוק זמן)
            greeting_instruction = ""
            weekday_instruction = ""
            
            try:
                if should_send_time_greeting(chat_id, user_msg):
                    # שליחת הנחיות ברכת זמן ויום שבוע
                    weekday_instruction = get_weekday_context_instruction(chat_id, user_msg)
                    greeting_instruction = get_time_greeting_instruction()
                    print(f"[GREETING_DEBUG] שולח ברכה + יום שבוע עבור chat_id={chat_id}")
                else:
                    print(f"[GREETING_DEBUG] לא שולח ברכה עבור chat_id={chat_id} - המשך שיחה רגיל")
            except Exception as greet_err:
                logging.warning(f"[GREETING] שגיאה בהערכת greeting: {greet_err}")
            
            # בניית ההודעות ל-gpt_a
            messages_for_gpt = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            # 🔍 [DEBUG] הודעת ראשי SYSTEM_PROMPT
            print(f"\n🔍 [MESSAGE_BUILD_DEBUG] === BUILDING MESSAGES FOR GPT ===")
            print(f"🎯 [SYSTEM_1] MAIN PROMPT - Length: {len(SYSTEM_PROMPT)} chars")
            
            # הוספת ברכת זמן אם יש
            if greeting_instruction:
                messages_for_gpt.append({"role": "system", "content": greeting_instruction})
                print(f"🎯 [SYSTEM_2] TIME GREETING - Content: {greeting_instruction}")
            
            if weekday_instruction:
                messages_for_gpt.append({"role": "system", "content": weekday_instruction})
                print(f"🎯 [SYSTEM_3] WEEKDAY - Content: {weekday_instruction}")
            
            # הוספת הודעת חגים אם רלוונטי
            from chat_utils import get_holiday_system_message
            holiday_instruction = get_holiday_system_message(str(chat_id))
            if holiday_instruction:
                messages_for_gpt.append({"role": "system", "content": holiday_instruction})
                print(f"🎯 [SYSTEM_4] HOLIDAY - Content: {holiday_instruction}")
            
            # הוספת שדות חסרים אם יש
            from gpt_a_handler import create_missing_fields_system_message
            missing_fields_instruction, missing_text = create_missing_fields_system_message(str(chat_id))
            if missing_fields_instruction:
                messages_for_gpt.append({"role": "system", "content": missing_fields_instruction})
                print(f"🎯 [SYSTEM_5] MISSING FIELDS - Found {len(missing_text.split(','))} missing fields")
            
            # ⭐ הוספת המידע על המשתמש לפני ההיסטוריה - ממוקם אסטרטגית
            if current_summary:
                messages_for_gpt.append({"role": "system", "content": f"""🎯 **מידע קריטי על המשתמש שמדבר מולך כרגע** - השתמש במידע הזה כדי להבין מי מדבר מולך ולהתאים את התשובה שלך:

{current_summary}

⚠️ **הנחיות חשובות לשימוש במידע:**
• השתמש רק במידע שהמשתמש באמת סיפר לך - אל תמציא או תוסיף דברים
• תראה לו שאתה מכיר אותו ונזכר בדברים שהוא אמר לך
• התייחס למידע הזה בצורה טבעית ורלוונטית לשיחה
• זה המידע שעוזר לך להיות דניאל המטפל שלו - תשתמש בו בחכמה"""})
                print(f"🎯 [SYSTEM_6] USER SUMMARY (PRE-HISTORY) - Length: {len(current_summary)} chars | Preview: {current_summary[:80]}...")
                print(f"🔍 [SUMMARY_DEBUG] User {chat_id}: '{current_summary}' (source: user_profiles.json)")
            
            # 📚 הוספת ההיסטוריה בצמידות להודעה החדשה
            print(f"📚 [HISTORY] Adding {len(history_messages)} history messages (all with timestamps) - positioned close to new message...")
            messages_for_gpt.extend(history_messages)
            
            # הוספת ההודעה החדשה עם טיימסטמפ באותו פורמט כמו בהיסטוריה
            from chat_utils import _format_timestamp_for_history
            import utils
            current_timestamp = _format_timestamp_for_history(utils.get_israel_time().isoformat())
            user_msg_with_timestamp = f"{current_timestamp} {user_msg}" if current_timestamp else user_msg
            messages_for_gpt.append({"role": "user", "content": user_msg_with_timestamp})
            print(f"👤 [USER_MSG] Length: {len(user_msg_with_timestamp)} chars | With timestamp: {current_timestamp}")
            print(f"📊 [FINAL_COUNT] Total messages: {len(messages_for_gpt)}")
            print(f"🔍 [MESSAGE_BUILD_DEBUG] === READY TO SEND ===\n")

            # שלב 2: שליחת תשובה מ-gpt_a
            logging.info(f"📤 [GPAT_A] שולח {len(messages_for_gpt)} הודעות ל-GPT-A")
            print(f"📤 [GPT_A] שולח {len(messages_for_gpt)} הודעות ל-GPT-A")
            
            bot_reply = await get_main_response(messages_for_gpt, chat_id)
            
            if not bot_reply:
                error_msg = error_human_funny_message()
                await send_system_message(update, chat_id, error_msg)
                await end_monitoring_user(str(chat_id), False)
                return

            # שלב 3: עדכון היסטוריה עם התשובה הסופית
            if history_entry_created:
                # רשומה כבר קיימת, מעדכן אותה עם התשובה
                update_last_bot_message(chat_id, bot_reply)
            else:
                # יוצר רשומה חדשה
                update_chat_history(chat_id, user_msg, bot_reply)

            # שלב 4: שליחת התשובה למשתמש עם פורמטינג מתקדם
            await send_message(update, chat_id, bot_reply, is_bot_message=True, is_gpt_a_response=True)

            # שלב 5: רישום והפעלת כל התהליכים ברקע במקביל
            try:
                # חישוב זמן מענה
                response_time = time.time() - user_request_start_time
                log_payload["response_time"] = response_time
                log_payload["timestamp_end"] = get_israel_time().isoformat()
                log_payload["bot_reply"] = bot_reply
                
                # רישום לשיטס - מהיר וללא המתנה
                asyncio.create_task(log_to_sheets(chat_id, user_msg, bot_reply, response_time))
                
                # הפעלת כל הטיפולים ברקע - GPT-C, GPT-D, GPT-E
                asyncio.create_task(run_background_processors(chat_id, user_msg, bot_reply))
                
                # עדכון מידע עבור ניטור ביצועים
                await update_user_processing_stage(str(chat_id), "completed")
                
                logging.info(f"✅ [SUCCESS] chat_id={chat_id} | זמן מענה: {response_time:.2f}s")
                print(f"✅ [SUCCESS] chat_id={chat_id} | זמן מענה: {response_time:.2f}s")
                
            except Exception as ex:
                logging.error(f"❌ שגיאה בטיפולים ברקע: {ex}")
                # אל תעצרי את הזרם - המשתמש כבר קיבל תשובה
                
        except Exception as ex:
            logging.error(f"❌ שגיאה בטיפול בהודעה: {ex}")
            print(f"❌ שגיאה בטיפול בהודעה: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            await end_monitoring_user(str(chat_id), False)
            return

        # סיום ניטור
        await end_monitoring_user(str(chat_id), True)

    except Exception as ex:
        logging.error(f"❌ שגיאה קריטית בטיפול בהודעה: {ex}")
        print(f"❌ שגיאה קריטית בטיפול בהודעה: {ex}")
        await handle_critical_error(ex, None, None, update)
        if 'chat_id' in locals():
            await end_monitoring_user(str(chat_id), False)

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
            gpt_c_task = asyncio.create_task(asyncio.to_thread(extract_user_info, user_msg, chat_id))
            
        # GPT-D - עדכון חכם של פרופיל
        tasks.append(smart_update_profile_with_gpt_d_async(chat_id, user_msg, bot_reply))
        
        # GPT-E - אימוג'ים ותכונות מתקדמות
        tasks.append(execute_gpt_e_if_needed(chat_id, user_msg, bot_reply))
        
        # הפעלה במקביל של כל התהליכים
        all_tasks = []
        if gpt_c_task:
            all_tasks.append(gpt_c_task)
        all_tasks.extend(tasks)
        
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
            
    except Exception as e:
        logging.error(f"❌ שגיאה בהפעלת מעבדים ברקע: {e}")

async def handle_new_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש חדש לגמרי ברקע
    """
    try:
        logging.info("[Onboarding] משתמש חדש - מתחיל תהליך רישום מלא")
        print("[Onboarding] משתמש חדש - מתחיל תהליך רישום מלא")
        
        # רישום ראשוני
        register_result = register_user(chat_id, update.message.from_user)
        
        if register_result.get("success"):
            # שליחת הודעות ברכה
            welcome_messages = get_welcome_messages()
            for msg in welcome_messages:
                await send_system_message(update, chat_id, msg)
                await asyncio.sleep(0.5)  # הפסקה קטנה בין הודעות
            
            # שליחת בקשת אישור תנאים
            await send_approval_message(update, chat_id)
            
        else:
            error_msg = "מצטער, הייתה בעיה ברישום. אנא נסה שוב."
            await send_system_message(update, chat_id, error_msg)
            
    except Exception as e:
        logging.error(f"[Onboarding] שגיאה בטיפול במשתמש חדש: {e}")
        await send_system_message(update, chat_id, "הייתה בעיה ברישום. אנא נסה שוב מאוחר יותר.")

async def handle_unregistered_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש לא רשום ברקע
    """
    try:
        logging.info("[Permissions] משתמש לא רשום - מנחה לרישום")
        print("[Permissions] משתמש לא רשום - מנחה לרישום")
        
        unregistered_msg = "נראה שאתה משתמש חדש! 😊\nאני דניאל, המטפל הדיגיטלי שלך.\nבואו נתחיל בתהליך הכרות קצר."
        await send_system_message(update, chat_id, unregistered_msg)
        
        # הפניה להליך רישום
        await handle_new_user_background(update, context, chat_id, user_msg)

    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def handle_pending_user_background(update, context, chat_id, user_msg):
    """
    טיפול במשתמש שעדיין לא אישר תנאים ברקע
    """
    try:
        if user_msg.strip() == APPROVE_BUTTON_TEXT:
            # אישור תנאים
            approval_result = approve_user(chat_id)
            if approval_result.get("success"):
                await send_system_message(update, chat_id, code_approved_message(), reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))
            else:
                await send_system_message(update, chat_id, "הייתה בעיה באישור. אנא נסה שוב.")
                
        elif user_msg.strip() == DECLINE_BUTTON_TEXT:
            # דחיית תנאים
            decline_msg = not_approved_message()
            await send_system_message(update, chat_id, decline_msg, reply_markup=ReplyKeyboardRemove())
            
        else:
            # הודעה על הצורך באישור תנאים
            pending_msg = "אנא אשר את תנאי השימוש על ידי לחיצה על הכפתור 'מאשר' למטה."
            await send_approval_message(update, chat_id)
            
    except Exception as e:
        logging.error(f"[Permissions] שגיאה בטיפול במשתמש ממתין לאישור: {e}")

async def send_system_message(update, chat_id, text, reply_markup=None):
    """
    שולחת הודעת מערכת למשתמש ללא פורמטינג מתקדם
    """
    try:
        if reply_markup:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await update.message.reply_text(text, parse_mode="HTML")
            
        # עדכון היסטוריה ולוגים
        update_chat_history(chat_id, "[הודעה אוטומטית מהבוט]", text)
        log_event_to_file({
            "chat_id": chat_id,
            "bot_message": text,
            "timestamp": get_israel_time().isoformat(),
            "message_type": "system_message"
        })
        
    except Exception as e:
        logging.error(f"שליחת הודעת מערכת נכשלה: {e}")
