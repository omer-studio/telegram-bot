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
from utils import log_error_stat
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

def format_text_for_telegram(text):
    """
    ממיר פורמטים מווואטסאפ לפורמט HTML של טלגרם:
    - *טקסט* -> <b>טקסט</b> (bold)
    - _טקסט_ -> <i>טקסט</i> (italic)
    - מנקה תגי HTML לא נתמכים כמו <br>
    """
    # ניקוי תגי HTML לא נתמכים
    text = text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    
    # המרת כוכביות ל-bold (רק כשיש טקסט ביניהם ללא רווחים בקצוות)
    text = re.sub(r'\*([^\s*][^*]*[^\s*]|\S)\*', r'<b>\1</b>', text)
    
    # המרת קו תחתון ל-italic (רק כשיש טקסט ביניהם ללא רווחים בקצוות)
    text = re.sub(r'_([^\s_][^_]*[^\s_]|\S)_', r'<i>\1</i>', text)
    
    return text

# פונקציה לשליחת הודעה למשתמש (הועתקה מ-main.py כדי למנוע לולאת ייבוא)
async def send_message(update, chat_id, text, is_bot_message=True):
    """
    שולחת הודעה למשתמש בטלגרם, כולל לוגים ועדכון היסטוריה.
    קלט: update (אובייקט טלגרם), chat_id (int), text (str), is_bot_message (bool)
    פלט: אין (שולחת הודעה)
    # מהלך מעניין: עדכון היסטוריה ולוגים רק אם ההודעה נשלחה בהצלחה.
    """
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
            "timestamp": datetime.now().isoformat(),
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
        "timestamp": datetime.now().isoformat()
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
    
    try:
        log_payload = {
            "chat_id": None,
            "message_id": None,
            "timestamp_start": datetime.now().isoformat()
        }
        try:
            chat_id = update.message.chat_id
            message_id = update.message.message_id
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
                        "timestamp": datetime.now().isoformat(),
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
                        "timestamp": datetime.now().isoformat(),
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
            
            # בדיקה מהירה רק ב-user_states
            is_first_time = not find_chat_id_in_sheet(context.bot_data["sheet_states"], chat_id, col=1)
            
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
            
            # בדיקה מהירה - אם יש ב-user_states, כנראה מאושר
            exists_in_states = find_chat_id_in_sheet(context.bot_data["sheet_states"], chat_id, col=1)
            
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

            # שלב 1: איסוף הנתונים הנדרשים לתשובה טובה (מהיר)
            current_summary = get_user_summary(chat_id) or ""
            history_messages = get_chat_history_messages(chat_id)
            
            # בניית ההודעות ל-gpt_a
            messages_for_gpt = [{"role": "system", "content": SYSTEM_PROMPT}]
            if current_summary:
                messages_for_gpt.append({"role": "system", "content": f"מידע חשוב על היוזר (לשימושך והתייחסותך בעת מתן תשובה): {current_summary}"})
            messages_for_gpt.extend(history_messages)
            messages_for_gpt.append({"role": "user", "content": user_msg})

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
            if gpt_response.get("used_premium"):
                print(f"🎯 [MODEL_INFO] השתמש במודל מתקדם: {gpt_response.get('model')} | סיבה: {gpt_response.get('filter_reason')} | סוג: {gpt_response.get('match_type', 'N/A')}")
            else:
                print(f"🚀 [MODEL_INFO] השתמש במודל מהיר: {gpt_response.get('model')} | סיבה: {gpt_response.get('filter_reason')} | סוג: {gpt_response.get('match_type', 'N/A')}")

            # שלב 3: שליחת התשובה למשתמש (אלא אם כבר נשלחה דרך עריכת הודעה זמנית)
            await update_user_processing_stage(str(chat_id), "sending_response")
            if not gpt_response.get("message_already_sent", False):
                await send_message_with_retry(update, chat_id, bot_reply, is_bot_message=True)
            update_chat_history(chat_id, user_msg, "")
            
            # שלב 4: הפעלת משימות רקע (gpt_b, gpt_c, עדכון היסטוריה סופי, לוגים)
            await update_user_processing_stage(str(chat_id), "background_tasks")
            # העברת bot_reply כ-last_bot_message - זה יהיה ההודעה הנוכחית (לא מקוצרת עדיין)
            asyncio.create_task(handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, bot_reply))
            
            # סיום ניטור משתמש
            await end_monitoring_user(str(chat_id), True)

        except Exception as ex:
            await handle_critical_error(ex, chat_id, user_msg, update)
            await end_monitoring_user(str(chat_id), False)

    except Exception as ex:
        await handle_critical_error(ex, locals().get('chat_id'), locals().get('user_msg'), update)

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
        exists, code, approved = check_user_access(context.bot_data["sheet"], chat_id)
        if not exists:
            current_try = increment_code_try(context.bot_data["sheet_states"], chat_id)
            if current_try is None:
                current_try = 0
            if current_try == 0:
                current_try = 1

            if register_user(context.bot_data["sheet"], chat_id, user_msg):
                await update.message.reply_text(format_text_for_telegram(code_approved_message()))
                await send_approval_message(update, chat_id)
            else:
                if current_try == 1:
                    await update.message.reply_text(format_text_for_telegram(get_retry_message_by_attempt(current_try)))
                elif current_try == 2:
                    await update.message.reply_text(format_text_for_telegram(get_retry_message_by_attempt(current_try)))
                elif current_try == 3:
                    await update.message.reply_text(format_text_for_telegram(get_retry_message_by_attempt(current_try)))
                elif current_try >= 4:
                    await update.message.reply_text(format_text_for_telegram(not_approved_message()))
        elif not approved:
            if user_msg.strip() == APPROVE_BUTTON_TEXT:
                approve_user(context.bot_data["sheet"], chat_id)
                await update.message.reply_text(format_text_for_telegram(nice_keyboard_message()), reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))
                await update.message.reply_text(format_text_for_telegram(remove_keyboard_message()), reply_markup=ReplyKeyboardRemove())
                await update.message.reply_text(format_text_for_telegram(full_access_message()), parse_mode="HTML")
            elif user_msg.strip() == DECLINE_BUTTON_TEXT:
                await update.message.reply_text(format_text_for_telegram("כדי להמשיך, יש לאשר את התנאים."))
                await send_approval_message(update, chat_id)
            else:
                await send_approval_message(update, chat_id)
    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, last_bot_message):
    """מטפל בכל המשימות ברקע - gpt_b, gpt_c, עדכון היסטוריה, לוגים"""
    try:
        bot_reply = gpt_response["bot_reply"]
        
        # gpt_b: יצירת תמצית לתשובת הבוט (רק אם ההודעה ארוכה)
        new_summary_for_history = None
        summary_response = None
        
        # בדיקה אם ההודעה ארוכה מספיק כדי להצדיק סיכום
        if len(bot_reply) > 150:  # סף של 150 תווים
            try:
                print(f"[DEBUG] הודעת הבוט ארוכה ({len(bot_reply)} תווים), קורא ל-gpt_b לסיכום")
                summary_response = await asyncio.to_thread(
                    get_summary,
                    user_msg=user_msg,
                    bot_reply=bot_reply,
                    chat_id=chat_id,
                    message_id=message_id
                )
                new_summary_for_history = summary_response.get("summary")
            except Exception as e:
                logging.error(f"Error in gpt_b (summary): {e}")
        else:
            print(f"[DEBUG] הודעת הבוט קצרה ({len(bot_reply)} תווים), לא קורא ל-gpt_b")

        # עדכון היסטוריה סופי עם תמצית או תשובה מלאה
        if new_summary_for_history:
            update_last_bot_message(chat_id, new_summary_for_history)
        else:
            update_last_bot_message(chat_id, bot_reply)

        # gpt_c: עדכון פרופיל משתמש
        gpt_c_response = None
        gpt_d_usage = None
        gpt_e_result = None
        try:
            # בדיקה אם יש טעם להפעיל gpt_c
            if should_run_gpt_c(user_msg):
                # הגדלת מונה gpt_c
                gpt_c_run_count = increment_gpt_c_run_count(chat_id)
                print(f"[DEBUG] gpt_c_run_count incremented to: {gpt_c_run_count}")
                
                # בחירת ההודעה הנכונה ל-gpt_c: מקוצרת אם קוצרה, אחרת מקורית
                bot_message_for_gpt_c = new_summary_for_history if new_summary_for_history else bot_reply
                
                print(f"[DEBUG] קורא ל-gpt_c עם user_msg: {user_msg}")
                print(f"[DEBUG] bot_message_for_gpt_c: {bot_message_for_gpt_c}")
                
                # קבלת הפרופיל הקיים
                existing_profile = get_user_summary(chat_id)
                if existing_profile:
                    try:
                        existing_profile = json.loads(existing_profile)
                    except:
                        existing_profile = {}
                else:
                    existing_profile = {}
                
                # שימוש בפונקציה החכמה עם gpt_d
                updated_profile, combined_usage = smart_update_profile_with_gpt_d(
                    existing_profile=existing_profile,
                    user_message=user_msg,
                    interaction_id=message_id
                )
                
                # הפרדת נתוני gpt_c ו-gpt_d
                gpt_c_usage = {}
                gpt_d_usage = {}
                
                for key, value in combined_usage.items():
                    if key.startswith("gpt_d_") or key in ["field_conflict_resolution"]:
                        gpt_d_usage[key] = value
                    else:
                        gpt_c_usage[key] = value
                
                print(f"[DEBUG] מעדכן פרופיל עם: {updated_profile}")
                update_user_profile(chat_id, updated_profile)
                log_payload["gpt_c_data"] = gpt_c_usage
                log_payload["gpt_d_data"] = gpt_d_usage
                
                # gpt_e: בדיקה והפעלה אם צריך
                try:
                    user_state = get_user_state(chat_id)
                    last_gpt_e_timestamp = user_state.get("last_gpt_e_timestamp")
                    
                    gpt_e_result = execute_gpt_e_if_needed(
                        chat_id=chat_id,
                        gpt_c_run_count=gpt_c_run_count,
                        last_gpt_e_timestamp=last_gpt_e_timestamp
                    )
                    
                    if gpt_e_result:
                        print(f"[DEBUG] gpt_e executed successfully for chat_id={chat_id}")
                        log_payload["gpt_e_data"] = {
                            "success": gpt_e_result.get("success", False),
                            "changes_count": len(gpt_e_result.get("changes", {})),
                            "tokens_used": gpt_e_result.get("tokens_used", 0),
                            "execution_time": gpt_e_result.get("execution_time", 0),
                            "cost_data": gpt_e_result.get("cost_data", {}),
                            "errors": gpt_e_result.get("errors", [])
                        }
                    else:
                        print(f"[DEBUG] gpt_e conditions not met for chat_id={chat_id}")
                        
                except Exception as e:
                    print(f"[ERROR] שגיאה ב-gpt_e: {e}")
                    logging.error(f"Error in gpt_e: {e}")
                
            else:
                print(f"[DEBUG] לא קורא ל-gpt_c - ההודעה לא נראית מכילה מידע חדש: {user_msg}")
        except Exception as e:
            print(f"[ERROR] שגיאה ב-gpt_c: {e}")
            logging.error(f"Error in gpt_c (profile update): {e}")

        # שמירת לוגים ונתונים נוספים
        # נירמול ה-usage לפני השמירה ב-log
        clean_gpt_response = {k: v for k, v in gpt_response.items() if k != "bot_reply"}
        if "usage" in clean_gpt_response:
            clean_gpt_response["usage"] = normalize_usage_dict(clean_gpt_response["usage"], gpt_response.get("model", ""))
        
        log_payload.update({
            "gpt_a_response": bot_reply,
            "gpt_a_usage": clean_gpt_response,
            "timestamp_end": datetime.now().isoformat()
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
            
            print("[DEBUG] ---- log_to_sheets DEBUG ----")
            print(f"[DEBUG] message_id: {message_id}")
            print(f"[DEBUG] chat_id: {chat_id}")
            print(f"[DEBUG] user_msg: {user_msg}")
            print(f"[DEBUG] bot_reply: {bot_reply}")
            print(f"[DEBUG] reply_summary: {new_summary_for_history}")
            print(f"[DEBUG] gpt_a_usage: {gpt_a_usage}")
            print(f"[DEBUG] gpt_b_usage: {gpt_b_usage}")
            print(f"[DEBUG] gpt_c_usage: {gpt_c_usage}")
            print(f"[DEBUG] gpt_d_usage: {gpt_d_usage}")
            print(f"[DEBUG] gpt_e_usage: {gpt_e_usage}")
            print(f"[DEBUG] total_tokens_calc: {total_tokens_calc}")
            print(f"[DEBUG] total_cost_usd_calc: {total_cost_usd_calc}")
            print(f"[DEBUG] total_cost_ils_calc: {total_cost_ils_calc}")
            
            # קריאה ל-log_to_sheets
            log_to_sheets(
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
            print("[DEBUG] ---- END log_to_sheets DEBUG ----")
        except Exception as e:
            print(f"[ERROR] שגיאה ב-log_to_sheets: {e}")
            logging.error(f"Error in log_to_sheets: {e}")
        
        log_event_to_file(log_payload)
        logging.info("---- סיום טיפול בהודעה (משתמש מאושר) ----")
        print("---- סיום טיפול בהודעה (משתמש מאושר) ----")
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
