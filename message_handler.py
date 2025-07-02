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
from gpt_d_handler import smart_update_profile_with_gpt_d
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

    # 🔢 שלב 0 – ניקוי עיצוב קיים
    # מנקה תגיות HTML קיימות כדי למנוע בלבול
    text = re.sub(r'<[^>]+>', '', text)
    
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
    text = re.sub(r'([?!])\s*(' + emoji_pattern.pattern + r')', r'\1 \2\n', text)
    text = re.sub(r'([?!])(?!\s*' + emoji_pattern.pattern + r')', r'\1\n', text)
    
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
    
    # שורות שמכילות רק אימוג'ים → מחוברות לשורה שמעליה
    lines = text.split('\n')
    cleaned = []
    for i, line in enumerate(lines):
        if emoji_pattern.fullmatch(line.strip()) and i > 0:
            cleaned[-1] += ' ' + line.strip()
        else:
            cleaned.append(line.strip())
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
            if not await start_monitoring_user(str(chat_id), str(message_id)):
                await send_system_message(update, chat_id, "⏳ הבוט עמוס כרגע. אנא נסה שוב בעוד מספר שניות.")
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

        # שלב 3: משתמש מאושר - שליחת תשובה מיד!
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
            
            # ברכה מותאמת זמן נשלחת רק בתחילת השיחה (אין היסטוריה קודמת)
            greeting_instruction = ""
            timestamp = ""
            weekday_instruction = ""
            
            try:
                if should_send_time_greeting(chat_id, user_msg):
                    # רק אם צריך לשלוח ברכה - מוסיף גם טיימסטמפ ויום שבוע
                    timestamp = create_human_context_for_gpt(chat_id)
                    weekday_instruction = get_weekday_context_instruction(chat_id, user_msg)
                    greeting_instruction = get_time_greeting_instruction()
                    print(f"[GREETING_DEBUG] שולח ברכה + טיימסטמפ + יום שבוע עבור chat_id={chat_id}")
                else:
                    print(f"[GREETING_DEBUG] לא שולח ברכה עבור chat_id={chat_id} - המשך שיחה רגיל")
            except Exception as greet_err:
                logging.warning(f"[GREETING] שגיאה בהערכת greeting: {greet_err}")
            
            # בניית ההודעות ל-gpt_a
            messages_for_gpt = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            # 🔍 [DEBUG] הודעת ראשי SYSTEM_PROMPT
            print(f"\n🔍 [MESSAGE_BUILD_DEBUG] === BUILDING MESSAGES FOR GPT ===")
            print(f"🎯 [SYSTEM_1] MAIN PROMPT - Length: {len(SYSTEM_PROMPT)} chars")
            
            if current_summary:
                messages_for_gpt.append({"role": "system", "content": f"מידע חשוב על היוזר (לשימושך והתייחסותך בעת מתן תשובה): {current_summary}\n\nחשוב מאוד: השתמש רק במידע שהמשתמש סיפר לך בפועל. אל תמציא מידע נוסף או תערבב עם דוגמאות מהפרומפט. תראה לו שאתה מכיר אותו - אבל רק על בסיס מה שהוא באמת סיפר."})
                print(f"🎯 [SYSTEM_2] USER SUMMARY - Length: {len(current_summary)} chars | Preview: {current_summary[:80]}...")
                print(f"🔍 [SUMMARY_DEBUG] User {chat_id}: '{current_summary}' (source: user_profiles.json)")
            
            # הוספת טיימסטמפ והנחיות זמן
            if timestamp:
                messages_for_gpt.append({"role": "system", "content": timestamp})
                print(f"🎯 [SYSTEM_3] TIMESTAMP - Content: {timestamp}")
            if greeting_instruction:
                messages_for_gpt.append({"role": "system", "content": greeting_instruction})
                print(f"🎯 [SYSTEM_4] GREETING - Content: {greeting_instruction}")
            if weekday_instruction:
                messages_for_gpt.append({"role": "system", "content": weekday_instruction})
                print(f"🎯 [SYSTEM_5] WEEKDAY - Content: {weekday_instruction}")
            
            print(f"📚 [HISTORY] Adding {len(history_messages)} history messages...")
            messages_for_gpt.extend(history_messages)
            
            # הוספת ההודעה החדשה עם טיימסטמפ
            user_msg_with_timestamp = f"{timestamp} {user_msg}" if timestamp else user_msg
            messages_for_gpt.append({"role": "user", "content": user_msg_with_timestamp})
            print(f"👤 [USER_MSG] Length: {len(user_msg_with_timestamp)} chars | With timestamp: {bool(timestamp)}")
            print(f"📊 [FINAL_COUNT] Total messages: {len(messages_for_gpt)}")
            print(f"🔍 [MESSAGE_BUILD_DEBUG] === READY TO SEND ===\n")

            # שלב 2: קריאה ל-gpt_a למענה ראשי עם מנגנון הודעות זמניות
            print(f"[DEBUG] 🔥 Calling get_main_response_with_timeout...")
            from gpt_a_handler import get_main_response_with_timeout
            gpt_response = await get_main_response_with_timeout(
                full_messages=messages_for_gpt,
                chat_id=chat_id,
                message_id=message_id,
                update=update
            )
            print(f"[DEBUG] get_main_response_with_timeout returned: {gpt_response}")
            bot_reply = gpt_response["bot_reply"]
            
            # הדפסת מידע על בחירת המודל
            used_extra_emotion = gpt_response.get("used_extra_emotion", gpt_response.get("used_premium"))
            if used_extra_emotion:
                print(f"🎯 [MODEL_INFO] השתמש במודל Extra-Emotion: {gpt_response.get('model')} | סיבה: {gpt_response.get('filter_reason')} | סוג: {gpt_response.get('match_type', 'N/A')}")
            else:
                print(f"🚀 [MODEL_INFO] השתמש במודל ברירת-מחדל: {gpt_response.get('model')} | סיבה: {gpt_response.get('filter_reason')} | סוג: {gpt_response.get('match_type', 'N/A')}")

            # שלב 3: שליחת התשובה למשתמש (אלא אם כבר נשלחה דרך עריכת הודעה זמנית)
            await update_user_processing_stage(str(chat_id), "sending_response")
            if not gpt_response.get("message_already_sent", False):
                await send_gpta_response(update, chat_id, bot_reply)

            # 🚀 שלב 4: הפעלת כל המשימות ברקע מיד אחרי שליחת התשובה - בלי לחכות!
            await update_user_processing_stage(str(chat_id), "background_tasks")
            
            # הפעלת כל המשימות ברקע במקביל אמיתי
            background_tasks = [
                # משימת רקע 1: סיכום ועדכון פרופיל
                asyncio.create_task(handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, bot_reply)),
                
                # משימת רקע 2: בדיקת חגים - הוסרה זמנית עד לתיקון
                asyncio.create_task(_handle_holiday_check(update, chat_id, bot_reply)),
                
                # משימת רקע 3: עדכון היסטוריה - הוסרה זמנית עד לתיקון
                # asyncio.create_task(_handle_history_update(chat_id, user_msg, history_entry_created))
            ]
            
            # המתנה לכל המשימות לסיום במקביל
            results = await asyncio.gather(*background_tasks, return_exceptions=True)
            
            # חילוץ התוצאות - יש שני tasks
            background_result = results[0] if not isinstance(results[0], Exception) else None
            holiday_result = results[1] if not isinstance(results[1], Exception) else None
            
            # עדכון היסטוריה (אחרי שיש לנו את הסיכום)
            if background_result:
                summary_response, new_summary_for_history, gpt_c_usage, gpt_d_usage, gpt_e_result = background_result
                update_last_bot_message(chat_id, new_summary_for_history or bot_reply)
            else:
                summary_response, new_summary_for_history, gpt_c_usage, gpt_d_usage, gpt_e_result = None, None, {}, {}, None
                update_last_bot_message(chat_id, bot_reply)

            # שמירת לוגים ונתונים נוספים
            # נירמול ה-usage לפני השמירה ב-log
            clean_gpt_response = {k: v for k, v in gpt_response.items() if k != "bot_reply"}
            if "usage" in clean_gpt_response:
                clean_gpt_response["usage"] = normalize_usage_dict(clean_gpt_response["usage"], gpt_response.get("model", ""))
            
            log_payload.update({
                "gpt_a_response": bot_reply,
                "gpt_a_usage": clean_gpt_response,
                "timestamp_end": get_israel_time().isoformat()
            })
            
            # רישום לגיליון Google Sheets
            try:
                from config import GPT_MODELS
                
                # חילוץ נתונים מ-gpt_response
                gpt_a_usage = normalize_usage_dict(gpt_response.get("usage", {}), gpt_response.get("model", GPT_MODELS["gpt_a"]))
                
                # חילוץ נתונים מ-summary_response (עם בדיקת None)
                gpt_b_usage = summary_response.get("usage", {}) if summary_response else {}
                if not gpt_b_usage and summary_response:
                    gpt_b_usage = normalize_usage_dict(summary_response.get("usage", {}), summary_response.get("usage", {}).get("model", GPT_MODELS["gpt_b"]))
                
                # חילוץ נתונים מ-gpt_c_response (עם בדיקת None)
                gpt_c_usage = log_payload.get("gpt_c_data", {})
                
                # חילוץ נתונים מ-gpt_e_result (עם בדיקת None)
                gpt_e_usage = {}
                if gpt_e_result and gpt_e_result.get("cost_data"):
                    gpt_e_usage = gpt_e_result["cost_data"]
                
                # חישוב סכומים
                total_tokens_calc = (
                    gpt_a_usage.get("total_tokens", 0) + 
                    gpt_b_usage.get("total_tokens", 0) + 
                    gpt_c_usage.get("total_tokens", 0) +
                    (gpt_d_usage.get("total_tokens", 0) if gpt_d_usage else 0) +
                    (gpt_e_usage.get("total_tokens", 0) if gpt_e_usage else 0)
                )
                
                total_cost_usd_calc = (
                    gpt_a_usage.get("cost_total", 0) + 
                    gpt_b_usage.get("cost_total", 0) + 
                    gpt_c_usage.get("cost_total", 0) +
                    (gpt_d_usage.get("cost_total", 0) if gpt_d_usage else 0) +
                    (gpt_e_usage.get("cost_total", 0) if gpt_e_usage else 0)
                )
                
                total_cost_ils_calc = (
                    gpt_a_usage.get("cost_total_ils", 0) + 
                    gpt_b_usage.get("cost_total_ils", 0) + 
                    gpt_c_usage.get("cost_total_ils", 0) +
                    (gpt_d_usage.get("cost_total_ils", 0) if gpt_d_usage else 0) +
                    (gpt_e_usage.get("cost_total_ils", 0) if gpt_e_usage else 0)
                )
                
                # דיבאג רזה ומלא מידע
                print(f"[DEBUG] msg={message_id} | user='{user_msg[:35]}{'...' if len(user_msg) > 35 else ''}' | bot='{bot_reply[:35]}{'...' if len(bot_reply) > 35 else ''}' | summary='{(new_summary_for_history[:35] if new_summary_for_history else '') + ('...' if new_summary_for_history and len(new_summary_for_history) > 35 else '')}' | tokens={total_tokens_calc} | cost=${total_cost_usd_calc:.4f} | chat={chat_id}")
                
                # קריאה ל-log_to_sheets (async)
                await log_to_sheets(
                    message_id=message_id,
                    chat_id=chat_id,
                    user_msg=user_msg,
                    reply_text=bot_reply,
                    reply_summary=new_summary_for_history or "",
                    main_usage=gpt_a_usage,
                    summary_usage=gpt_b_usage,
                    extract_usage=gpt_c_usage,
                    total_tokens=total_tokens_calc,
                    cost_usd=total_cost_usd_calc,
                    cost_ils=total_cost_ils_calc,
                    gpt_d_usage=gpt_d_usage,
                    gpt_e_usage=gpt_e_usage
                )
            except Exception as e:
                print(f"[ERROR] שגיאה ב-log_to_sheets: {e}")
                logging.error(f"Error in log_to_sheets: {e}")
            
            log_event_to_file(log_payload)
            logging.info("✅ סיום טיפול בהודעה")
            print("✅ סיום טיפול בהודעה")
            print("📱 מחכה להודעה חדשה ממשתמש בטלגרם...")

        except Exception as ex:
            # ניסיון לחלץ chat_id מה-update אם הוא לא זמין ב-locals
            chat_id_from_update = None
            user_msg_from_update = None
            try:
                if update and hasattr(update, 'message') and hasattr(update.message, 'chat_id'):
                    chat_id_from_update = update.message.chat_id
                if update and hasattr(update, 'message') and hasattr(update.message, 'text'):
                    user_msg_from_update = update.message.text
            except (AttributeError, TypeError) as e:
                logging.warning(f"Error extracting chat_id from update in outer exception: {e}")
                pass
                
            await handle_critical_error(ex, chat_id_from_update, user_msg_from_update, update)

    except Exception as ex:
        # ניסיון לחלץ chat_id מה-update אם הוא לא זמין ב-locals
        chat_id_from_update = None
        user_msg_from_update = None
        try:
            if update and hasattr(update, 'message') and hasattr(update.message, 'chat_id'):
                chat_id_from_update = update.message.chat_id
            if update and hasattr(update, 'message') and hasattr(update.message, 'text'):
                user_msg_from_update = update.message.text
        except (AttributeError, TypeError) as e:
            logging.warning(f"Error extracting chat_id from update: {e}")
            pass
        
        await handle_critical_error(ex, chat_id_from_update, user_msg_from_update, update)

    log_event_to_file({
        "event": "user_message_processed", 
        "timestamp": get_israel_time().isoformat()
    })
    logging.info("✅ סיום טיפול בהודעה")
    print("✅ סיום טיפול בהודעה")

async def handle_new_user_background(update, context, chat_id, user_msg):
    """מטפל במשתמש חדש ברקע"""
    try:
        # הוספת לוג להודעה נכנסת
        print(f"[IN_MSG] chat_id={chat_id} | message_id={update.message.message_id} | text={user_msg.replace(chr(10), ' ')[:120]} (NEW USER)")
        
        is_first_time = ensure_user_state_row(
            context.bot_data["sheet"],           
            context.bot_data["sheet_states"],    
            chat_id
        )
        if is_first_time:
            welcome_messages = get_welcome_messages()
            for message in welcome_messages:
                await send_system_message(update, chat_id, message)
    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def handle_unregistered_user_background(update, context, chat_id, user_msg):
    """מטפל במשתמש לא רשום ברקע"""
    try:
        # הוספת לוג להודעה נכנסת
        print(f"[IN_MSG] chat_id={chat_id} | message_id={update.message.message_id} | text={user_msg.replace(chr(10), ' ')[:120]} (UNREGISTERED)")
        
        # משתמש לא קיים - צריך לרשום קוד
        if register_user(context.bot_data["sheet"], chat_id, user_msg):
            # קוד תקין - הצלחה!
            await send_system_message(update, chat_id, code_approved_message())
            await send_approval_message(update, chat_id)
        else:
            # קוד לא תקין - הגדלת מספר הניסיון ושליחת הודעת שגיאה
            from sheets_core import increment_code_try_sync
            current_try = increment_code_try_sync(context.bot_data["sheet_states"], chat_id)
            if current_try <= 0:
                current_try = 1
                
            if current_try <= 3:
                await send_system_message(update, chat_id, get_retry_message_by_attempt(current_try))
            else:
                await send_system_message(update, chat_id, not_approved_message())
                
    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def handle_pending_user_background(update, context, chat_id, user_msg):
    """מטפל במשתמש שמחכה לאישור תנאים"""
    try:
        # הוספת לוג להודעה נכנסת
        print(f"[IN_MSG] chat_id={chat_id} | message_id={update.message.message_id} | text={user_msg.replace(chr(10), ' ')[:120]} (PENDING)")
        
        # משתמש רשום אבל לא אישר תנאים
        if user_msg.strip() == APPROVE_BUTTON_TEXT():
            # משתמש אישר תנאים
            approve_user(context.bot_data["sheet"], chat_id)
            
            # (הוסרו שליחת nice_keyboard_message ו-remove_keyboard_message)
            
            await send_system_message(update, chat_id, full_access_message())
        elif user_msg.strip() == DECLINE_BUTTON_TEXT():
            # משתמש לא אישר תנאים
            await send_system_message(update, chat_id, "כדי להמשיך, יש לאשר את התנאים.")
            await send_approval_message(update, chat_id)
        else:
            # משתמש כתב משהו אחר - שולח שוב את הודעת האישור
            await send_approval_message(update, chat_id)
                
    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def _handle_gpt_b_summary(user_msg, bot_reply, chat_id, message_id):
    """מטפל בסיכום ההודעה עם gpt_b."""
    if len(bot_reply) <= 150:  # הודעה קצרה - לא צריך סיכום
        if should_log_debug_prints():
            print(f"[MSG_SUMMARY] הודעה קצרה ({len(bot_reply)} תווים), ללא סיכום")
        return None, None
    
    try:
        if should_log_debug_prints():
            print(f"[MSG_SUMMARY] הודעה ארוכה ({len(bot_reply)} תווים), מבקש סיכום")
        summary_response = await asyncio.to_thread(
            get_summary, user_msg=user_msg, bot_reply=bot_reply, 
            chat_id=chat_id, message_id=message_id
        )
        return summary_response, summary_response.get("summary")
    except Exception as e:
        logging.error(f"Error in gpt_b (summary): {e}")
        return None, None

async def _handle_profile_updates(chat_id, user_msg, message_id, log_payload):
    """מטפל בעדכון הפרופיל עם gpt_c/d ו-gpt_e."""
    gpt_c_usage, gpt_d_usage, gpt_e_result = {}, {}, None
    
    try:
        if not should_run_gpt_c(user_msg):
            print(f"[DEBUG] לא צריך gpt_c - ההודעה לא מכילה מידע חדש")
            return gpt_c_usage, gpt_d_usage, gpt_e_result
        
        # הפעלת gpt_c
        gpt_c_run_count = increment_gpt_c_run_count(chat_id)
        print(f"[DEBUG] gpt_c_run_count: {gpt_c_run_count}")
        
        # קבלת פרופיל קיים
        existing_profile = get_user_summary(chat_id)
        try:
            existing_profile = json.loads(existing_profile) if existing_profile else {}
        except (json.JSONDecodeError, TypeError) as e:
            logging.warning(f"Error parsing existing profile JSON: {e}")
            existing_profile = {}
        
        # עדכון פרופיל עם gpt_d
        updated_profile, combined_usage = smart_update_profile_with_gpt_d(
            existing_profile=existing_profile,
            user_message=user_msg,
            interaction_id=message_id
        )
        
        # הפרדת נתוני gpt_c ו-gpt_d
        for key, value in combined_usage.items():
            if key.startswith("gpt_d_") or key in ["field_conflict_resolution"]:
                gpt_d_usage[key] = value
            else:
                gpt_c_usage[key] = value
        
        # 1. עדכון פרופיל מהיר בקובץ המקומי  ➜ Google Sheets יסתנכרן ברקע
        # השבתת התראות אוטומטיות זמנית כדי שלא תישלח הודעה כפולה
        import utils as _u
        _u._disable_auto_admin_profile_notification = True
        await update_user_profile(chat_id, updated_profile)
        _u._disable_auto_admin_profile_notification = False

        # חישוב שינויים להשוואה עבור התראות אדמין
        changes_list = _pu._detect_profile_changes(existing_profile, updated_profile)

        # הכנת מידע GPT להתראה
        gpt_c_info_line = f"GPT-C: עודכנו {len(changes_list)} שדות"
        
        # GPT-D: רק אם יש ערך קיים בשדה שהוחלף
        gpt_d_should_run = False
        extracted_fields = {}
        
        # חילוץ השדות שחולצו מ-GPT-C
        for key, value in combined_usage.items():
            if key == "extracted_fields":
                extracted_fields = value
                break
            elif isinstance(value, dict) and "extracted_fields" in value:
                extracted_fields = value["extracted_fields"]
                break
        
        # אם לא מצאנו ב-combined_usage, ננסה לחלץ ישירות מ-GPT-C
        if not extracted_fields:
            from gpt_c_handler import extract_user_info
            gpt_c_result = extract_user_info(user_msg)
            if isinstance(gpt_c_result, dict):
                extracted_fields = gpt_c_result.get("extracted_fields", {})
        
        # ✅ תיקון: עדכון הפרופיל עם השדות שחולצו מ-GPT-C אם לא עודכנו עדיין
        if extracted_fields and not any(ch.get("field") in extracted_fields for ch in changes_list):
            # אם השדות שחולצו לא נכללו בעדכון, נוסיף אותם
            for field, value in extracted_fields.items():
                changes_list.append({
                    "field": field,
                    "old_value": existing_profile.get(field, ""),
                    "new_value": value,
                    "change_type": "added" if not existing_profile.get(field) else "updated"
                })
        
        if extracted_fields:
            for field, new_value in extracted_fields.items():
                if field in existing_profile and existing_profile[field] and existing_profile[field] != "":
                    gpt_d_should_run = True
                    break
        
        gpt_d_info_line = "GPT-D: מיזוג בוצע" if gpt_d_usage and gpt_d_should_run else "GPT-D: לא הופעל (אין ערך קיים למיזוג)"

        # gpt_e: ניתוח מתקדם - מעביר לכאן כדי שהאדמין יקבל הודעה גם על GPT-E
        try:
            user_state = get_user_state(chat_id)
            # 🔧 תיקון: קריאה async לפונקציה execute_gpt_e_if_needed
            gpt_e_result = await execute_gpt_e_if_needed(
                chat_id=chat_id,
                gpt_c_run_count=gpt_c_run_count,
                last_gpt_e_timestamp=user_state.get("last_gpt_e_timestamp")
            )
            
            if gpt_e_result:
                log_payload["gpt_e_data"] = {
                    "success": gpt_e_result.get("success", False),
                    "changes_count": len(gpt_e_result.get("changes", {})),
                    "tokens_used": gpt_e_result.get("tokens_used", 0),
                    "cost_data": gpt_e_result.get("cost_data", {})
                }
                
                # 🔧 הוספת שינויים של GPT-E ל-changes_list
                gpt_e_changes = gpt_e_result.get("changes", {})
                if gpt_e_changes:
                    for field, new_value in gpt_e_changes.items():
                        changes_list.append({
                            "field": field,
                            "old_value": "",  # GPT-E לא מחזיר ערך ישן
                            "new_value": new_value,
                            "change_type": "added"  # GPT-E בדרך כלל מוסיף שדות חדשים
                        })
        except Exception as e:
            logging.error(f"Error in gpt_e: {e}")
            gpt_e_result = None

        if gpt_e_result:
            gpt_e_info_line = f"GPT-E: הופעל ({len(gpt_e_result.get('changes', {}))} שדות)"
        else:
            gpt_e_info_line = (
                f"GPT-E: לא הופעל (מופעל כל 25 ריצות GPT-C, כרגע בספירה {gpt_c_run_count})"
            )

        # שליחת הודעת אדמין מאוחדת - אם יש פעילות של GPT-C/D/E
        has_gpt_c_activity = bool(extracted_fields)  # GPT-C החזיר שדות
        has_gpt_d_activity = bool(gpt_d_usage and gpt_d_should_run)  # GPT-D הופעל
        has_gpt_e_activity = bool(gpt_e_result and gpt_e_result.get('changes'))  # GPT-E החזיר שינויים
        
        # ✅ תיקון: נשלח הודעה גם אם יש רק פעילות GPT-C (חילוץ שדות)
        if has_gpt_c_activity or has_gpt_d_activity or has_gpt_e_activity:  # ✅ נשלח אם יש פעילות כלשהי
            try:
                # קבלת הסיכום של תעודת הזהות הרגשית
                user_summary = get_user_summary(chat_id)
                try:
                    if user_summary:
                        profile_data = json.loads(user_summary) if isinstance(user_summary, str) else user_summary
                        emotional_summary = profile_data.get("summary", "")
                    else:
                        emotional_summary = ""
                except (json.JSONDecodeError, TypeError, AttributeError) as e:
                    logging.warning(f"Error parsing user summary JSON: {e}")
                    emotional_summary = ""
                
                _pu._send_admin_profile_overview_notification(
                    chat_id=str(chat_id),
                    user_msg=user_msg,
                    changes=changes_list,
                    gpt_c_info=gpt_c_info_line,
                    gpt_d_info=gpt_d_info_line,
                    gpt_e_info=gpt_e_info_line,
                    summary=emotional_summary
                )
            except Exception as _e_notify:
                logging.error(f"Failed to send overview admin notification: {_e_notify}")
        else:
            # 🟢 לוג קצר כשאין פעילות
            logging.info(f"✅ [ADMIN] אין פעילות GPT-C/D/E למשתמש {chat_id} - לא נשלחה הודעה")
        
        # 🔧 עדכון בפועל של הפרופיל אם יש שינויים של GPT-E
        if gpt_e_result and gpt_e_result.get('changes'):
            try:
                gpt_e_changes = gpt_e_result.get('changes', {})
                if gpt_e_changes:
                    await update_user_profile(chat_id, gpt_e_changes)
                    logging.info(f"✅ [GPT-E] עדכון פרופיל הושלם עבור משתמש {chat_id}: {list(gpt_e_changes.keys())}")
            except Exception as update_error:
                logging.error(f"❌ [GPT-E] שגיאה בעדכון פרופיל: {update_error}")
        
        log_payload["gpt_c_data"] = gpt_c_usage
        log_payload["gpt_d_data"] = gpt_d_usage
        
        # 🔧 הסרה: GPT-E כבר רץ למעלה, לא צריך לרוץ שוב
        # gpt_e: ניתוח מתקדם
        # try:
        #     user_state = get_user_state(chat_id)
        #     gpt_e_result = await execute_gpt_e_if_needed(
        #         chat_id=chat_id,
        #         gpt_c_run_count=gpt_c_run_count,
        #         last_gpt_e_timestamp=user_state.get("last_gpt_e_timestamp")
        #     )
        #     
        #     if gpt_e_result:
        #         log_payload["gpt_e_data"] = {
        #             "success": gpt_e_result.get("success", False),
        #             "changes_count": len(gpt_e_result.get("changes", {})),
        #             "tokens_used": gpt_e_result.get("tokens_used", 0),
        #             "cost_data": gpt_e_result.get("cost_data", {})
        #         }
        # except Exception as e:
        #     logging.error(f"Error in gpt_e: {e}")
            
    except Exception as e:
        logging.error(f"Error in profile update: {e}")
    
    return gpt_c_usage, gpt_d_usage, gpt_e_result

async def handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, last_bot_message):
    """מטפל בכל המשימות ברקע - גרסה מקבילה ומהירה."""
    try:
        bot_reply = gpt_response["bot_reply"]
        
        # 🚀 הפעלת כל המשימות במקביל אמיתי - בלי לחכות!
        tasks = [
            asyncio.create_task(_handle_gpt_b_summary(user_msg, bot_reply, chat_id, message_id)),
            asyncio.create_task(_handle_profile_updates(chat_id, user_msg, message_id, log_payload))
        ]
        
        # המתנה לכל המשימות לסיום במקביל
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # חילוץ התוצאות
        summary_result = results[0] if not isinstance(results[0], Exception) else (None, None)
        profile_result = results[1] if not isinstance(results[1], Exception) else ({}, {}, None)
        
        summary_response, new_summary_for_history = summary_result if summary_result else (None, None)
        gpt_c_usage, gpt_d_usage, gpt_e_result = profile_result if profile_result else ({}, {}, None)
        
        # עדכון היסטוריה (אחרי שיש לנו את הסיכום)
        update_last_bot_message(chat_id, new_summary_for_history or bot_reply)

        # שמירת לוגים ונתונים נוספים
        # נירמול ה-usage לפני השמירה ב-log
        clean_gpt_response = {k: v for k, v in gpt_response.items() if k != "bot_reply"}
        if "usage" in clean_gpt_response:
            clean_gpt_response["usage"] = normalize_usage_dict(clean_gpt_response["usage"], gpt_response.get("model", ""))
        
        log_payload.update({
            "gpt_a_response": bot_reply,
            "gpt_a_usage": clean_gpt_response,
            "timestamp_end": get_israel_time().isoformat()
        })
        
        # רישום לגיליון Google Sheets
        try:
            from config import GPT_MODELS
            
            # חילוץ נתונים מ-gpt_response
            gpt_a_usage = normalize_usage_dict(gpt_response.get("usage", {}), gpt_response.get("model", GPT_MODELS["gpt_a"]))
            
            # חילוץ נתונים מ-summary_response (עם בדיקת None)
            gpt_b_usage = summary_response.get("usage", {}) if summary_response else {}
            if not gpt_b_usage and summary_response:
                gpt_b_usage = normalize_usage_dict(summary_response.get("usage", {}), summary_response.get("usage", {}).get("model", GPT_MODELS["gpt_b"]))
            
            # חילוץ נתונים מ-gpt_c_response (עם בדיקת None)
            gpt_c_usage = log_payload.get("gpt_c_data", {})
            
            # חילוץ נתונים מ-gpt_e_result (עם בדיקת None)
            gpt_e_usage = {}
            if gpt_e_result and gpt_e_result.get("cost_data"):
                gpt_e_usage = gpt_e_result["cost_data"]
            
            # חישוב סכומים
            total_tokens_calc = (
                gpt_a_usage.get("total_tokens", 0) + 
                gpt_b_usage.get("total_tokens", 0) + 
                gpt_c_usage.get("total_tokens", 0) +
                (gpt_d_usage.get("total_tokens", 0) if gpt_d_usage else 0) +
                (gpt_e_usage.get("total_tokens", 0) if gpt_e_usage else 0)
            )
            
            total_cost_usd_calc = (
                gpt_a_usage.get("cost_total", 0) + 
                gpt_b_usage.get("cost_total", 0) + 
                gpt_c_usage.get("cost_total", 0) +
                (gpt_d_usage.get("cost_total", 0) if gpt_d_usage else 0) +
                (gpt_e_usage.get("cost_total", 0) if gpt_e_usage else 0)
            )
            
            total_cost_ils_calc = (
                gpt_a_usage.get("cost_total_ils", 0) + 
                gpt_b_usage.get("cost_total_ils", 0) + 
                gpt_c_usage.get("cost_total_ils", 0) +
                (gpt_d_usage.get("cost_total_ils", 0) if gpt_d_usage else 0) +
                (gpt_e_usage.get("cost_total_ils", 0) if gpt_e_usage else 0)
            )
            
            # דיבאג רזה ומלא מידע
            print(f"[DEBUG] msg={message_id} | user='{user_msg[:35]}{'...' if len(user_msg) > 35 else ''}' | bot='{bot_reply[:35]}{'...' if len(bot_reply) > 35 else ''}' | summary='{(new_summary_for_history[:35] if new_summary_for_history else '') + ('...' if new_summary_for_history and len(new_summary_for_history) > 35 else '')}' | tokens={total_tokens_calc} | cost=${total_cost_usd_calc:.4f} | chat={chat_id}")
            
            # קריאה ל-log_to_sheets (async)
            await log_to_sheets(
                message_id=message_id,
                chat_id=chat_id,
                user_msg=user_msg,
                reply_text=bot_reply,
                reply_summary=new_summary_for_history or "",
                main_usage=gpt_a_usage,
                summary_usage=gpt_b_usage,
                extract_usage=gpt_c_usage,
                total_tokens=total_tokens_calc,
                cost_usd=total_cost_usd_calc,
                cost_ils=total_cost_ils_calc,
                gpt_d_usage=gpt_d_usage,
                gpt_e_usage=gpt_e_usage
            )
        except Exception as e:
            print(f"[ERROR] שגיאה ב-log_to_sheets: {e}")
            logging.error(f"Error in log_to_sheets: {e}")
        
        log_event_to_file(log_payload)
        logging.info("✅ סיום טיפול בהודעה")
        print("✅ סיום טיפול בהודעה")
        print("📱 מחכה להודעה חדשה ממשתמש בטלגרם...")

    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def send_system_message(update, chat_id, text, max_retries=3):
    """
    שולחת הודעה מערכת כמו שהיא, ללא שום פורמטינג אוטומטי.
    משמש להודעות פתיחה, הודעות שגיאה, הודעות מערכת וכו'.
    """
    
    # 🚨 CRITICAL SECURITY CHECK: מנע שליחת הודעות פנימיות למשתמש!
    if text and ("[עדכון פרופיל]" in text or "[PROFILE_CHANGE]" in text or 
                 (text.startswith("[") and "]" in text and any(keyword in text for keyword in ["עדכון", "debug", "admin", "system"]))):
        logging.critical(f"🚨 BLOCKED INTERNAL MESSAGE TO USER! chat_id={chat_id} | text={text[:100]}")
        print(f"🚨🚨🚨 CRITICAL: חסימת הודעה פנימית למשתמש! chat_id={chat_id}")
        print(f"🚨 הודעה חסומה: {text[:200]}...")
        
        # שליחת התראה לאדמין על הניסיון
        try:
            from notifications import send_error_notification
            send_error_notification(
                error_message=f"🚨 CRITICAL: ניסיון לשלוח הודעה פנימית למשתמש! chat_id={chat_id}", 
                chat_id=chat_id, 
                user_msg=f"הודעה חסומה: {text[:200]}..."
            )
        except Exception as notify_err:
            logging.error(f"Failed to send critical security notification: {notify_err}")
        
        return False

    # 🐛 DEBUG: מידע על השליחה
    print("=" * 80)
    print("📤 SEND_SYSTEM_MESSAGE DEBUG")
    print("=" * 80)
    print(f"📊 CHAT_ID: {chat_id}")
    print(f"📝 ORIGINAL TEXT ({len(text)} chars):")
    print(f"   {repr(text)}")
    print(f"📊 NEWLINES: {text.count(chr(10))}")
    print(f"📊 DOTS: {text.count('.')}")
    print("=" * 80)
    
    # 🚫 אין פורמטינג - הטקסט נשלח כמו שהוא
    formatted_text = text
    print(f"🚫 [SYSTEM] שליחת הודעה מערכת ללא פורמטינג")
    
    if should_log_message_debug():
        print(f"[SEND_SYSTEM_MESSAGE] chat_id={chat_id} | text={formatted_text.replace(chr(10), ' ')[:120]}", flush=True)
    
    try:
        bot_id = None
        if hasattr(update, 'message') and hasattr(update.message, 'bot') and update.message.bot:
            bot_id = getattr(update.message.bot, 'id', None)
        elif hasattr(update, 'bot'):
            bot_id = getattr(update.bot, 'id', None)
        
        if should_log_debug_prints():
            print(f"[DEBUG] SENDING SYSTEM MESSAGE: from bot_id={bot_id} to chat_id={chat_id}", flush=True)
    except Exception as e:
        if should_log_debug_prints():
            print(f"[DEBUG] לא הצלחתי להוציא bot_id: {e}", flush=True)
    
    import sys; sys.stdout.flush()
    
    for attempt in range(max_retries):
        try:
            sent_message = await asyncio.wait_for(
                update.message.reply_text(formatted_text, parse_mode="HTML"),
                timeout=10.0
            )
            
            if should_log_message_debug():
                print(f"[TELEGRAM_SYSTEM_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}", flush=True)
            
            logging.info(f"[TELEGRAM_SYSTEM_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}")
            
            # עדכון היסטוריה ולוגים
            update_chat_history(chat_id, "[הודעה מערכת]", formatted_text)
            log_event_to_file({
                "chat_id": chat_id,
                "system_message": formatted_text,
                "timestamp": get_israel_time().isoformat()
            })
            if should_log_message_debug():
                print(f"[SYSTEM_MSG] {formatted_text.replace(chr(10), ' ')[:120]}")
            
            return True
            
        except asyncio.TimeoutError:
            logging.warning(f"Timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
        except Exception as e:
            error_msg = str(e).lower()
            
            # אם השגיאה קשורה לפורמט HTML, ננסה בלי parse_mode
            if "parse entities" in error_msg or "unsupported start tag" in error_msg or "br" in error_msg:
                try:
                    plain_text = re.sub(r'<[^>]+>', '', formatted_text)
                    sent_message = await asyncio.wait_for(
                        update.message.reply_text(plain_text),
                        timeout=10.0
                    )
                    logging.warning(f"⚠️ [SYSTEM_HTML_FALLBACK] נשלח טקסט רגיל במקום HTML | ניסיון: {attempt + 1}")
                    
                    # עדכון היסטוריה ולוגים גם עבור fallback
                    update_chat_history(chat_id, "[הודעה מערכת]", plain_text)
                    log_event_to_file({
                        "chat_id": chat_id,
                        "system_message": plain_text,
                        "timestamp": get_israel_time().isoformat(),
                        "fallback_used": True
                    })
                    
                    return True
                except Exception as plain_error:
                    logging.error(f"❌ [SYSTEM_PLAIN_FALLBACK] גם טקסט רגיל נכשל | ניסיון: {attempt + 1} | שגיאה: {plain_error}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                logging.warning(f"⚠️ [SYSTEM_RETRY] ניסיון {attempt + 1} נכשל, מנסה שוב | שגיאה: {e}")
            else:
                logging.error(f"❌ [SYSTEM_FINAL_FAILURE] כל הניסיונות נכשלו | שגיאה: {e}")
                
                # רישום שגיאה סופית
                log_event_to_file({
                    "chat_id": chat_id,
                    "system_message": formatted_text,
                    "timestamp": get_israel_time().isoformat(),
                    "error": str(e),
                    "final_failure": True
                })
                try:
                    from notifications import send_error_notification
                    send_error_notification(error_message=f"[send_system_message] שליחת הודעה מערכת נכשלה: {e}", chat_id=chat_id, user_msg=formatted_text)
                except Exception as notify_err:
                    if should_log_message_debug():
                        print(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}", flush=True)
                    logging.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}")
                
                return False
    
    return False

async def send_gpta_response(update, chat_id, text, max_retries=3):
    """
    מפעילה את הפורמטינג על תשובות GPT-A ואז שולחת אותן.
    משמש רק לתשובות מהמודל הראשי (GPT-A).
    """
    
    # 🚨 CRITICAL SECURITY CHECK: מנע שליחת הודעות פנימיות למשתמש!
    if text and ("[עדכון פרופיל]" in text or "[PROFILE_CHANGE]" in text or 
                 (text.startswith("[") and "]" in text and any(keyword in text for keyword in ["עדכון", "debug", "admin", "system"]))):
        logging.critical(f"🚨 BLOCKED INTERNAL MESSAGE TO USER! chat_id={chat_id} | text={text[:100]}")
        print(f"🚨🚨🚨 CRITICAL: חסימת הודעה פנימית למשתמש! chat_id={chat_id}")
        print(f"🚨 הודעה חסומה: {text[:200]}...")
        
        # שליחת התראה לאדמין על הניסיון
        try:
            from notifications import send_error_notification
            send_error_notification(
                error_message=f"🚨 CRITICAL: ניסיון לשלוח הודעה פנימית למשתמש! chat_id={chat_id}", 
                chat_id=chat_id, 
                user_msg=f"הודעה חסומה: {text[:200]}..."
            )
        except Exception as notify_err:
            logging.error(f"Failed to send critical security notification: {notify_err}")
        
        return False

    # 🐛 DEBUG: מידע על השליחה
    print("=" * 80)
    print("📤 SEND_GPTA_RESPONSE DEBUG")
    print("=" * 80)
    print(f"📊 CHAT_ID: {chat_id}")
    print(f"📝 ORIGINAL TEXT ({len(text)} chars):")
    print(f"   {repr(text)}")
    print(f"📊 NEWLINES: {text.count(chr(10))}")
    print(f"📊 DOTS: {text.count('.')}")
    print(f"📊 QUESTIONS: {text.count('?')}")
    print(f"📊 EXCLAMATIONS: {text.count('!')}")
    print("=" * 80)
    
    # 🔧 פורמטינג עבור תשובות GPT-A
    print(f"🔧 [GPTA_FORMATTING] מתחיל פורמטינג לתשובת GPTA: {len(text)} chars")
    formatted_text = format_text_for_telegram(text)
    print(f"🔧 [GPTA_FORMATTING] פורמטינג הושלם | אורך: {len(formatted_text)} chars")
    
    if should_log_message_debug():
        print(f"[SEND_GPTA_RESPONSE] chat_id={chat_id} | text={formatted_text.replace(chr(10), ' ')[:120]}", flush=True)
    
    try:
        bot_id = None
        if hasattr(update, 'message') and hasattr(update.message, 'bot') and update.message.bot:
            bot_id = getattr(update.message.bot, 'id', None)
        elif hasattr(update, 'bot'):
            bot_id = getattr(update.bot, 'id', None)
        
        if should_log_debug_prints():
            print(f"[DEBUG] SENDING GPTA RESPONSE: from bot_id={bot_id} to chat_id={chat_id}", flush=True)
    except Exception as e:
        if should_log_debug_prints():
            print(f"[DEBUG] לא הצלחתי להוציא bot_id: {e}", flush=True)
    
    import sys; sys.stdout.flush()
    
    for attempt in range(max_retries):
        try:
            sent_message = await asyncio.wait_for(
                update.message.reply_text(formatted_text, parse_mode="HTML"),
                timeout=10.0
            )
            
            if should_log_message_debug():
                print(f"[TELEGRAM_GPTA_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}", flush=True)
            
            logging.info(f"[TELEGRAM_GPTA_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}")
            
            # עדכון היסטוריה ולוגים
            update_chat_history(chat_id, "[תשובת GPT-A]", formatted_text)
            log_event_to_file({
                "chat_id": chat_id,
                "gpta_response": formatted_text,
                "timestamp": get_israel_time().isoformat()
            })
            if should_log_message_debug():
                print(f"[GPTA_RESPONSE] {formatted_text.replace(chr(10), ' ')[:120]}")
            
            return True
            
        except asyncio.TimeoutError:
            logging.warning(f"Timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
        except Exception as e:
            error_msg = str(e).lower()
            
            # אם השגיאה קשורה לפורמט HTML, ננסה בלי parse_mode
            if "parse entities" in error_msg or "unsupported start tag" in error_msg or "br" in error_msg:
                try:
                    plain_text = re.sub(r'<[^>]+>', '', formatted_text)
                    sent_message = await asyncio.wait_for(
                        update.message.reply_text(plain_text),
                        timeout=10.0
                    )
                    logging.warning(f"⚠️ [GPTA_HTML_FALLBACK] נשלח טקסט רגיל במקום HTML | ניסיון: {attempt + 1}")
                    
                    # עדכון היסטוריה ולוגים גם עבור fallback
                    update_chat_history(chat_id, "[תשובת GPT-A]", plain_text)
                    log_event_to_file({
                        "chat_id": chat_id,
                        "gpta_response": plain_text,
                        "timestamp": get_israel_time().isoformat(),
                        "fallback_used": True
                    })
                    
                    return True
                except Exception as plain_error:
                    logging.error(f"❌ [GPTA_PLAIN_FALLBACK] גם טקסט רגיל נכשל | ניסיון: {attempt + 1} | שגיאה: {plain_error}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                logging.warning(f"⚠️ [GPTA_RETRY] ניסיון {attempt + 1} נכשל, מנסה שוב | שגיאה: {e}")
            else:
                logging.error(f"❌ [GPTA_FINAL_FAILURE] כל הניסיונות נכשלו | שגיאה: {e}")
                
                # רישום שגיאה סופית
                log_event_to_file({
                    "chat_id": chat_id,
                    "gpta_response": formatted_text,
                    "timestamp": get_israel_time().isoformat(),
                    "error": str(e),
                    "final_failure": True
                })
                try:
                    from notifications import send_error_notification
                    send_error_notification(error_message=f"[send_gpta_response] שליחת תשובת GPT-A נכשלה: {e}", chat_id=chat_id, user_msg=formatted_text)
                except Exception as notify_err:
                    if should_log_message_debug():
                        print(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}", flush=True)
                    logging.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}")
                
                return False
    
    return False
