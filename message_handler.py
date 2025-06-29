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
    ADMIN_CHAT_ID
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

def format_text_for_telegram(text):
    """
    ממיר פורמטים מווואטסאפ לפורמט HTML של טלגרם:
    - *טקסט* -> <b>טקסט</b> (bold)
    - _טקסט_ -> <b>טקסט</b> (bold) – במקום italic
    - מנקה תגי HTML לא נתמכים (<br>) ומאחד הדגשות (<i> → <b>) תוך שמירת <u>
    """
    # 🐛 DEBUG: שמירת הטקסט המקורי
    original_text = text
    debug_info = {
        "original_length": len(text),
        "original_newlines": text.count('\n'),
        "original_dots": text.count('.'),
        "original_questions": text.count('?'),
        "original_exclamations": text.count('!'),
        "original_emojis": len(re.findall(r'[^\w\s<>]+', text, flags=re.UNICODE))
    }
    
    # ניקוי תגי HTML לא נתמכים
    text = text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    
    # המרת הדגשה נטויה (i) לבולד אחיד; שומר על underline (u) כפי שהוא
    text = text.replace('<i>', '<b>').replace('</i>', '</b>')
    
    # קיבוץ רווחי שורות מרובים לשורה ריקה אחת
    text = re.sub(r'\n\s*\n+', '\n\n', text.strip())
    
    # המרת כוכביות כפולות (**טקסט**) ל-bold (לפני טיפול בכוכבית בודדת)
    text = re.sub(r'\*\*([^\s*][^*]*[^\s*]|\S)\*\*', r'<b>\1</b>', text)
    
    # המרת כוכביות ל-bold (רק כשיש טקסט ביניהם לא רווחים בקצוות)
    text = re.sub(r'\*([^\s*][^*]*[^\s*]|\S)\*', r'<b>\1</b>', text)
    
    # המרת קו תחתון כפול (__טקסט__) ל-bold (לפני טיפול בודד)
    text = re.sub(r'__([^\s_][^_]*[^\s_]|\S)__', r'<b>\1</b>', text)
    
    # המרת קו תחתון ל-bold (רק כשיש טקסט ביניהם ללא רווחים בקצוות)
    text = re.sub(r'_([^\s_][^_]*[^\s_]|\S)_', r'<b>\1</b>', text)
    
    # 🚨🚨🚨 *** כללי נשימות טבעיות - אסור למחוק בשום מצב! *** 🚨🚨🚨
    # ⚠️  אזהרה: שינוי הכללים האלה יהרוס את הפורמט הטבעי של הטקסט! ⚠️
    # 🚫 אסור לשנות את הקוד הבא! 🚫
    # DO NOT DELETE OR MODIFY THESE RULES – BREAKS FORMATTING!
    if len(text) > 50 and text.count('\n') < len(text) // 60:
        # הגנה: אם הטקסט כבר מפורמט יפה (הרבה מעברי שורה) - לא לגעת
        if text.count('\n') > len(text) // 40:  # יותר ממעבר שורה אחד לכל 40 תווים
            pass  # לא לגעת בטקסט שכבר מפורמט
        else:
            # טיפול בנקודות ואימוג'ים - מחיקת הנקודות לחלוטין
            emoji_pattern = r"[^\w\s<>]+"
            # נקודה + אימוג'י + טקסט אחריו - מחיקת הנקודה
            text = re.sub(rf'\.(\s*)({emoji_pattern})(\s+)(?=[A-Za-z\u0590-\u05FF])', r'\2\n', text, flags=re.UNICODE)
            # נקודה + אימוג'י בסוף משפט - מחיקת הנקודה
            text = re.sub(rf'\.(\s*)({emoji_pattern})(?=\s*\n|\s*$)', r'\2\n', text, flags=re.UNICODE)
            # סימני שאלה וקריאה - רק מעבר שורה (ללא מחיקה)
            text = re.sub(r'([!?])(\s+)(?=[A-Za-z\u0590-\u05FF])', r'\1\n', text, flags=re.UNICODE)
            
            # הגנה מפני שורות קצרות מדי
            lines = text.split('\n')
            cleaned_lines = []
            for i, line in enumerate(lines):
                line = line.strip()
                if len(line) >= 3 or line == '' or i == len(lines) - 1:
                    cleaned_lines.append(line)
                else:
                    if cleaned_lines and cleaned_lines[-1] != '':
                        cleaned_lines[-1] = cleaned_lines[-1] + ' ' + line
                    else:
                        cleaned_lines.append(line)
            text = '\n'.join(cleaned_lines)

    # 🪄 ניקוי מעברי שורה מיותרים
    text = text.strip().replace('\r\n', '\n')
    # הגנה: לא ליצור רווח כפול חדש אלא אם כן היה במקור
    # אם יש 3+ מעברי שורה רצופים - נשאיר 2 (שורה ריקה אחת)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # ניקוי כפילויות של תגיות <b> מקוננות
    text = re.sub(r'<b>\s*<b>(.*?)</b>\s*</b>', r'<b>\1</b>', text, flags=re.DOTALL)
    
    # הגנה מפני אימוג'ים בודדים בשורה
    emoji_pattern = r"[^\w\s<>]+"
    lines = text.split('\n')
    cleaned_lines = []
    for i, line in enumerate(lines):
        line = line.strip()
        # אם השורה מכילה רק אימוג'ים קצרים - נחבר לשורה הקודמת
        if re.match(rf'^(\s*{emoji_pattern}\s*)+$', line, flags=re.UNICODE) and len(line.strip()) < 10:
            if cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines[-1] = cleaned_lines[-1] + ' ' + line.strip()
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # 🧹 ניקוי סופי של מעברי שורה כפולים שנוצרו מהטיפול באימוג'ים
    # *** הגנה: לא ליצור רווח כפול חדש אלא אם כן היה במקור ***
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 🚨🚨🚨 *** כללי הנשימות הטבעיות הסתיימו - אסור לשנות! *** 🚨🚨🚨
    # ⚠️  אזהרה: שינוי הקוד מעל יהרוס את הפורמט הטבעי של הטקסט! ⚠️
    # 🚫 אסור למחוק או לשנות את הכללים! 🚫
    # DO NOT DELETE OR MODIFY THESE RULES – BREAKS FORMATTING!
    
    # 🐛 DEBUG: עדכון מידע על הטקסט הסופי
    debug_info.update({
        "final_length": len(text),
        "final_newlines": text.count('\n'),
        "final_dots": text.count('.'),
        "final_questions": text.count('?'),
        "final_exclamations": text.count('!'),
        "final_emojis": len(re.findall(r'[^\w\s<>]+', text, flags=re.UNICODE)),
        "length_change": len(text) - len(original_text),
        "newlines_change": text.count('\n') - original_text.count('\n'),
        "dots_change": text.count('.') - original_text.count('.'),
        "questions_change": text.count('?') - original_text.count('?'),
        "exclamations_change": text.count('!') - original_text.count('!')
    })
    
    # 🐛 DEBUG: הדפסת מידע מפורט
    print("=" * 80)
    print("🔍 FORMAT_TEXT_FOR_TELEGRAM DEBUG")
    print("=" * 80)
    print(f"📊 STATS:")
    print(f"   אורך: {debug_info['original_length']} → {debug_info['final_length']} ({debug_info['length_change']:+d})")
    print(f"   מעברי שורה: {debug_info['original_newlines']} → {debug_info['final_newlines']} ({debug_info['newlines_change']:+d})")
    print(f"   נקודות: {debug_info['original_dots']} → {debug_info['final_dots']} ({debug_info['dots_change']:+d})")
    print(f"   סימני שאלה: {debug_info['original_questions']} → {debug_info['final_questions']} ({debug_info['questions_change']:+d})")
    print(f"   סימני קריאה: {debug_info['original_exclamations']} → {debug_info['final_exclamations']} ({debug_info['exclamations_change']:+d})")
    print(f"   אימוג'ים: {debug_info['original_emojis']} → {debug_info['final_emojis']}")
    print()
    print(f"📝 ORIGINAL TEXT ({len(original_text)} chars):")
    print(f"   {repr(original_text)}")
    print()
    print(f"✨ FORMATTED TEXT ({len(text)} chars):")
    print(f"   {repr(text)}")
    print()
    print(f"👀 VISUAL COMPARISON:")
    print("   ORIGINAL:")
    print(f"   {original_text}")
    print("   FORMATTED:")
    print(f"   {text}")
    print("=" * 80)
    
    return text

# פונקציה לשליחת הודעה למשתמש (הועתקה מ-main.py כדי למנוע לולאת ייבוא)
async def send_message(update, chat_id, text, is_bot_message=True):
    """
    שולחת הודעה למשתמש בטלגרם, כולל לוגים ועדכון היסטוריה.
    קלט: update (אובייקט טלגרם), chat_id (int), text (str), is_bot_message (bool)
    פלט: אין (שולחת הודעה)
    # מהלך מעניין: עדכון היסטוריה ולוגים רק אם ההודעה נשלחה בהצלחה.
    """
    # 🐛 DEBUG: מידע על השליחה
    print("=" * 80)
    print("📤 SEND_MESSAGE DEBUG")
    print("=" * 80)
    print(f"📊 CHAT_ID: {chat_id}")
    print(f"📊 IS_BOT_MESSAGE: {is_bot_message}")
    print(f"📝 ORIGINAL TEXT ({len(text)} chars):")
    print(f"   {repr(text)}")
    print(f"📊 NEWLINES: {text.count(chr(10))}")
    print(f"📊 DOTS: {text.count('.')}")
    print(f"📊 QUESTIONS: {text.count('?')}")
    print(f"📊 EXCLAMATIONS: {text.count('!')}")
    print("=" * 80)
    
    # מיפוי פורמטים לפני שליחה
    formatted_text = format_text_for_telegram(text)
    
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
    await update.message.reply_text(
        format_text_for_telegram(approval_msg),
        reply_markup=ReplyKeyboardMarkup(approval_keyboard(), one_time_keyboard=True, resize_keyboard=True)
    )

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
                    await update.message.reply_text(
                        format_text_for_telegram(voice_message)
                    )
                    
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
                    
                    await update.message.reply_text(format_text_for_telegram(appropriate_response))
                    await end_monitoring_user(str(chat_id), True)
                    return

            # 🚀 התחלת ניטור concurrent
            if not await start_monitoring_user(str(chat_id), str(message_id)):
                await update.message.reply_text(format_text_for_telegram("⏳ הבוט עמוס כרגע. אנא נסה שוב בעוד מספר שניות."))
                return

            did, reply = handle_secret_command(chat_id, user_msg)
            if did:
                await update.message.reply_text(format_text_for_telegram(reply))
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

        # שלב 2: בדיקה מהירה של הרשאות (רק ב-user_states)
        try:
            await update_user_processing_stage(str(chat_id), "permission_check")
            logging.info("🔍 בודק הרשאות משתמש מול הגיליון...")
            print("🔍 בודק הרשאות משתמש מול הגיליון...")
            
            # בדיקה מהירה - אם יש ב-user_states, כנראה מאושר - לפי כותרות
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
                    exists_in_states = find_chat_id_in_sheet(sheet_states, chat_id, col=chat_id_col)
                else:
                    # fallback למיקום קלאסי אם לא נמצאה עמודת chat_id
                    exists_in_states = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
            else:
                # fallback למיקום קלאסי אם אין כותרות
                exists_in_states = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
            
            if not exists_in_states:
                # אם לא קיים ב-user_states, עושים בדיקה מלאה ברקע
                asyncio.create_task(handle_unregistered_user_background(update, context, chat_id, user_msg))
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
            history_messages = get_chat_history_messages(chat_id)
            
            # יצירת טיימסטמפ והנחיות יום השבוע
            from utils import create_human_context_for_gpt, get_weekday_context_instruction, get_time_greeting_instruction
            timestamp = create_human_context_for_gpt(chat_id)
            weekday_instruction = get_weekday_context_instruction(chat_id, user_msg)
            # ברכה מותאמת זמן נשלחת רק בתחילת השיחה (אין היסטוריה קודמת)
            from utils import should_send_time_greeting
            greeting_instruction = ""
            try:
                if should_send_time_greeting(chat_id, user_msg):
                    greeting_instruction = get_time_greeting_instruction()
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
                await send_message_with_retry(update, chat_id, bot_reply, is_bot_message=True)

            # שלב 4: בדיקת חגים אחרי התשובה
            from utils import get_holiday_system_message
            try:
                holiday_message = get_holiday_system_message(str(chat_id), bot_reply)
                if holiday_message:
                    print(f"🎯 [HOLIDAY] שולח הודעת חג: {holiday_message}")
                    await send_message_with_retry(update, chat_id, holiday_message, is_bot_message=True)
            except Exception as holiday_err:
                logging.warning(f"[HOLIDAY] שגיאה בהערכת חגים: {holiday_err}")

            # אם כבר יצרנו רשומה מקדימה – אין צורך להוסיף שנית
            if not history_entry_created:
                update_chat_history(chat_id, user_msg, "")
            
            # 🕐 מדידת זמן סיום - מהרגע שהמשתמש לחץ אנטר עד התשובה
            user_request_end_time = time.time()
            total_user_experience_time = user_request_end_time - user_request_start_time
            
            # 📊 הדפסת מדידות מפורטות
            print(f"🎯 [USER_EXPERIENCE] Total time from webhook to response: {total_user_experience_time:.3f}s")
            if 'gpt_pure_latency' in gpt_response:
                gpt_pure_time = gpt_response.get('gpt_pure_latency', 0)
                overhead_time = total_user_experience_time - gpt_pure_time
                print(f"🎯 [USER_EXPERIENCE] GPT pure time: {gpt_pure_time:.3f}s | System overhead: {overhead_time:.3f}s")
                print(f"🎯 [USER_EXPERIENCE] Overhead percentage: {(overhead_time/total_user_experience_time)*100:.1f}%")
            
            # --- לוג רזה לכל הברכות שנשלחו ---
            sent_time_greeting = greeting_instruction.strip() if greeting_instruction else None
            sent_weekday_greeting = weekday_instruction.strip() if weekday_instruction else None
            sent_holiday_greeting = holiday_message.strip() if 'holiday_message' in locals() and holiday_message else None
            print(f"[GREETING] ⏰ זמן: {sent_time_greeting[:10] if sent_time_greeting else 'אין'} | 🎉 חג: {sent_holiday_greeting[:10] if sent_holiday_greeting else 'אין'} | 📅 יום: {sent_weekday_greeting[:10] if sent_weekday_greeting else 'אין'}")

            # שלב 5: הפעלת משימות רקע (gpt_b, gpt_c, עדכון היסטוריה סופי, לוגים)
            await update_user_processing_stage(str(chat_id), "background_tasks")
            # העברת bot_reply כ-last_bot_message - זה יהיה ההודעה הנוכחית (לא מקוצרת עדיין)
            asyncio.create_task(handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, bot_reply))
            
            # סיום ניטור משתמש
            await end_monitoring_user(str(chat_id), True)

        except Exception as ex:
            # ניסיון לחלץ chat_id מה-update אם הוא לא זמין ב-locals
            chat_id_from_update = None
            user_msg_from_update = None
            try:
                if update and hasattr(update, 'message') and hasattr(update.message, 'chat_id'):
                    chat_id_from_update = update.message.chat_id
                if update and hasattr(update, 'message') and hasattr(update.message, 'text'):
                    user_msg_from_update = update.message.text
            except:
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
        except:
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
        is_first_time = ensure_user_state_row(
            context.bot_data["sheet"],           
            context.bot_data["sheet_states"],    
            chat_id
        )
        if is_first_time:
            welcome_messages = get_welcome_messages()
            for message in welcome_messages:
                await send_message(update, chat_id, message)
    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def handle_unregistered_user_background(update, context, chat_id, user_msg):
    """מטפל במשתמש לא רשום ברקע"""
    try:
        # check_user_access מחזיר dict עם status ו-code
        access_result = check_user_access(context.bot_data["sheet"], chat_id)
        status = access_result.get("status", "not_found")
        code = access_result.get("code")
        
        if status == "not_found":
            # משתמש לא קיים - צריך לרשום קוד
            current_try = increment_code_try(context.bot_data["sheet_states"], chat_id)
            if current_try is None:
                current_try = 1

            if register_user(context.bot_data["sheet"], chat_id, user_msg):
                await update.message.reply_text(format_text_for_telegram(code_approved_message()))
                await send_approval_message(update, chat_id)
            else:
                if current_try <= 3:
                    await update.message.reply_text(format_text_for_telegram(get_retry_message_by_attempt(current_try)))
                else:
                    await update.message.reply_text(format_text_for_telegram(not_approved_message()))
                    
        elif status == "pending":
            # משתמש רשום אבל לא אישר תנאים
            if user_msg.strip() == APPROVE_BUTTON_TEXT():
                approve_user(context.bot_data["sheet"], chat_id)
                await update.message.reply_text(format_text_for_telegram(nice_keyboard_message()), reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))
                await update.message.reply_text(format_text_for_telegram(remove_keyboard_message()), reply_markup=ReplyKeyboardRemove())
                await update.message.reply_text(format_text_for_telegram(full_access_message()), parse_mode="HTML")
            elif user_msg.strip() == DECLINE_BUTTON_TEXT():
                await update.message.reply_text(format_text_for_telegram("כדי להמשיך, יש לאשר את התנאים."))
                await send_approval_message(update, chat_id)
            else:
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
        except:
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
        changes_list = _u._detect_profile_changes(existing_profile, updated_profile)

        # הכנת מידע GPT להתראה
        gpt_c_info_line = f"GPT-C: עודכנו {len(changes_list)} שדות"
        
        # GPT-D: רק אם יש ערך קיים בשדה שהוחלף
        gpt_d_should_run = False
        extracted_fields = {}
        for key, value in combined_usage.items():
            if not key.startswith("gpt_d_") and key not in ["field_conflict_resolution"]:
                # זה gpt_c usage, נחלץ את השדות שחולצו
                if key == "extracted_fields":
                    extracted_fields = value
                elif isinstance(value, dict) and "extracted_fields" in value:
                    extracted_fields = value["extracted_fields"]
        
        if extracted_fields:
            for field, new_value in extracted_fields.items():
                if field in existing_profile and existing_profile[field] and existing_profile[field] != "":
                    gpt_d_should_run = True
                    break
        
        gpt_d_info_line = "GPT-D: מיזוג בוצע" if gpt_d_usage and gpt_d_should_run else "GPT-D: לא הופעל (אין ערך קיים למיזוג)"

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
                except:
                    emotional_summary = ""
                
                _u._send_admin_profile_overview_notification(
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
        
        log_payload["gpt_c_data"] = gpt_c_usage
        log_payload["gpt_d_data"] = gpt_d_usage
        
        # gpt_e: ניתוח מתקדם
        try:
            user_state = get_user_state(chat_id)
            gpt_e_result = execute_gpt_e_if_needed(
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
        except Exception as e:
            logging.error(f"Error in gpt_e: {e}")
            
    except Exception as e:
        logging.error(f"Error in profile update: {e}")
    
    return gpt_c_usage, gpt_d_usage, gpt_e_result

async def handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, last_bot_message):
    """מטפל בכל המשימות ברקע - גרסה מקבילה ומהירה."""
    try:
        bot_reply = gpt_response["bot_reply"]
        
        # 🚀 הפעלת משימות במקביל לביצועים מהירים יותר
        summary_task = asyncio.create_task(_handle_gpt_b_summary(user_msg, bot_reply, chat_id, message_id))
        
        # המתנה לסיום הסיכום לפני הפעלת עדכון הפרופיל
        summary_response, new_summary_for_history = await summary_task
        
        # העברת הסיכום לעדכון הפרופיל (לא צריך - הסיכום של תעודת הזהות הרגשית נשלף בתוך הפונקציה)
        profile_task = asyncio.create_task(_handle_profile_updates(chat_id, user_msg, message_id, log_payload))
        gpt_c_usage, gpt_d_usage, gpt_e_result = await profile_task
        
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

async def send_message_with_retry(update, chat_id, text, is_bot_message=True, max_retries=3):
    formatted_text = format_text_for_telegram(text)
    
    for attempt in range(max_retries):
        try:
            await asyncio.wait_for(
                update.message.reply_text(formatted_text, parse_mode="HTML"),
                timeout=10.0
            )
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
                    await asyncio.wait_for(
                        update.message.reply_text(plain_text),
                        timeout=10.0
                    )
                    logging.warning(f"⚠️ [HTML_FALLBACK] נשלח טקסט רגיל במקום HTML | ניסיון: {attempt + 1}")
                    return True
                except Exception as plain_error:
                    logging.error(f"❌ [PLAIN_FALLBACK] גם טקסט רגיל נכשל | ניסיון: {attempt + 1} | שגיאה: {plain_error}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                logging.warning(f"⚠️ [RETRY] ניסיון {attempt + 1} נכשל, מנסה שוב | שגיאה: {e}")
            else:
                logging.error(f"❌ [FINAL_FAILURE] כל הניסיונות נכשלו | שגיאה: {e}")
                return False
    
    return False
