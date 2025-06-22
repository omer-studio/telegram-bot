"""
message_handler.py
------------------
קובץ זה מטפל בכל הודעה נכנסת מהמשתמש בטלגרם.
הרציונל: ריכוז כל הלוגיקה של טיפול בהודעות, הרשאות, רישום, מענה, לוגים, ושילוב GPT.
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from datetime import datetime
import logging
import asyncio
from secret_commands import handle_secret_command
from messages import get_welcome_messages, get_retry_message_by_attempt, approval_text, approval_keyboard, APPROVE_BUTTON_TEXT, DECLINE_BUTTON_TEXT, code_approved_message, code_not_received_message, not_approved_message, nice_keyboard, nice_keyboard_message, remove_keyboard_message, full_access_message, error_human_funny_message
from notifications import handle_critical_error
from sheets_handler import increment_code_try, get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user, ensure_user_state_row, find_chat_id_in_sheet
from gpt_handler import get_main_response, summarize_bot_reply, gpt_c, normalize_usage_dict
from utils import log_event_to_file, update_chat_history, get_chat_history_messages
from fields_dict import FIELDS_DICT
import time

# פונקציה לשליחת הודעה למשתמש (הועתקה מ-main.py כדי למנוע לולאת ייבוא)
async def send_message(update, chat_id, text, is_bot_message=True):
    """
    שולחת הודעה למשתמש בטלגרם, כולל לוגים ועדכון היסטוריה.
    קלט: update (אובייקט טלגרם), chat_id (int), text (str), is_bot_message (bool)
    פלט: אין (שולחת הודעה)
    # מהלך מעניין: עדכון היסטוריה ולוגים רק אם ההודעה נשלחה בהצלחה.
    """
    print(f"[SEND_MESSAGE] chat_id={chat_id} | text={text.replace(chr(10), ' ')[:120]}", flush=True)
    try:
        bot_id = None
        if hasattr(update, 'message') and hasattr(update.message, 'bot') and update.message.bot:
            bot_id = getattr(update.message.bot, 'id', None)
        elif hasattr(update, 'bot'):
            bot_id = getattr(update.bot, 'id', None)
        print(f"[DEBUG] SENDING MESSAGE: from bot_id={bot_id} to chat_id={chat_id}", flush=True)
    except Exception as e:
        print(f"[DEBUG] לא הצלחתי להוציא bot_id: {e}", flush=True)
    import sys; sys.stdout.flush()
    try:
        sent_message = await update.message.reply_text(text, parse_mode="HTML")
        print(f"[TELEGRAM_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}", flush=True)
        logging.info(f"[TELEGRAM_REPLY] message_id={getattr(sent_message, 'message_id', None)} | chat_id={chat_id}")
    except Exception as e:
        print(f"[ERROR] שליחת הודעה נכשלה: {e}", flush=True)
        logging.error(f"[ERROR] שליחת הודעה נכשלה: {e}")
        log_event_to_file({
            "chat_id": chat_id,
            "bot_message": text,
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        })
        try:
            from notifications import send_error_notification
            send_error_notification(error_message=f"[send_message] שליחת הודעה נכשלה: {e}", chat_id=chat_id, user_msg=text)
        except Exception as notify_err:
            print(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}", flush=True)
            logging.error(f"[ERROR] לא הצלחתי לשלוח התראה לאדמין: {notify_err}")
        return
    if is_bot_message:
        update_chat_history(chat_id, "[הודעה אוטומטית מהבוט]", text)
    log_event_to_file({
        "chat_id": chat_id,
        "bot_message": text,
        "timestamp": datetime.now().isoformat()
    })
    print(f"[BOT_MSG] {text.replace(chr(10), ' ')[:120]}")

# פונקציה לשליחת הודעת אישור (הועתקה מ-main.py)
async def send_approval_message(update, chat_id):
    """
    שולחת הודעת אישור תנאים למשתמש, עם מקלדת מותאמת.
    קלט: update, chat_id
    פלט: אין (שולחת הודעה)
    """
    await update.message.reply_text(
        approval_text() + "\n\nאנא לחץ על 'מאשר' או 'לא מאשר' במקלדת למטה.",
        reply_markup=ReplyKeyboardMarkup(approval_keyboard(), one_time_keyboard=True, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    הפונקציה הראשית שמטפלת בכל הודעה נכנסת מהמשתמש.
    קלט: update (אובייקט טלגרם), context (אובייקט קונטקסט)
    פלט: אין (מטפלת בכל הלוגיקה של הודעה)
    # מהלך מעניין: טיפול מלא ב-onboarding, הרשאות, לוגים, שילוב GPT, עדכון היסטוריה, והכל בצורה אסינכרונית.
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
                logging.error(f"❌ שגיאה - אין טקסט בהודעה | chat_id={chat_id}")
                await update.message.reply_text("❌ לא קיבלתי טקסט בהודעה.")
                return
            did, reply = handle_secret_command(chat_id, user_msg)
            if did:
                await update.message.reply_text(reply)
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
            return

        # שלב 1: בדיקה מהירה אם זה משתמש חדש (רק ב-user_states)
        try:
            logging.info("[Onboarding] בודק האם המשתמש פונה בפעם הראשונה בחייו...")
            print("[Onboarding] בודק האם המשתמש פונה בפעם הראשונה בחייו...")
            
            # בדיקה מהירה רק ב-user_states
            is_first_time = not find_chat_id_in_sheet(context.bot_data["sheet_states"], chat_id, col=1)
            
            if is_first_time:
                # אם זה משתמש חדש, עושים את כל הבדיקות המלאות ברקע
                asyncio.create_task(handle_new_user_background(update, context, chat_id, user_msg))
                return
            else:
                logging.info("[Onboarding] המשתמש כבר התחיל או עבר תהליך רישום קודם.")
                print("[Onboarding] המשתמש כבר התחיל או עבר תהליך רישום קודם.")
        except Exception as ex:
            logging.error(f"[Onboarding] ❌ שגיאה באתחול משתמש חדש: {ex}")
            print(f"[Onboarding] ❌ שגיאה באתחול משתמש חדש: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            return

        # שלב 2: בדיקה מהירה של הרשאות (רק ב-user_states)
        try:
            logging.info("🔍 בודק הרשאות משתמש מול הגיליון...")
            print("🔍 בודק הרשאות משתמש מול הגיליון...")
            
            # בדיקה מהירה - אם יש ב-user_states, כנראה מאושר
            exists_in_states = find_chat_id_in_sheet(context.bot_data["sheet_states"], chat_id, col=1)
            
            if not exists_in_states:
                # אם לא קיים ב-user_states, עושים בדיקה מלאה ברקע
                asyncio.create_task(handle_unregistered_user_background(update, context, chat_id, user_msg))
                return
                
        except Exception as ex:
            logging.error(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            print(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            return

        # שלב 3: משתמש מאושר - שליחת תשובה מיד!
        logging.info("👨‍💻 משתמש מאושר, שולח תשובה מיד...")
        print("👨‍💻 משתמש מאושר, שולח תשובה מיד...")

        try:
            # שלב 1: איסוף הנתונים הנדרשים לתשובה טובה (מהיר)
            current_summary = get_user_summary(chat_id) or ""
            history_messages = get_chat_history_messages(chat_id)
            
            # בניית ההודעות ל-GPT-A
            messages_for_gpt = [{"role": "system", "content": SYSTEM_PROMPT}]
            if current_summary:
                messages_for_gpt.append({"role": "system", "content": f"מידע חשוב על היוזר (לשימושך והתייחסותך בעת מתן תשובה): {current_summary}"})
            messages_for_gpt.extend(history_messages)
            messages_for_gpt.append({"role": "user", "content": user_msg})

            last_bot_message = next((msg.get("content", "") for msg in reversed(history_messages) if msg.get("role") == "assistant"), "")

            # שלב 2: קריאה ל-GPT-A למענה ראשי (זה מה שיקבע את איכות התשובה)
            gpt_response = await asyncio.to_thread(
                get_main_response,
                full_messages=messages_for_gpt,
                chat_id=chat_id,
                message_id=message_id
            )
            bot_reply = gpt_response["bot_reply"]

            # שלב 3: שליחת התשובה למשתמש ועדכון היסטוריה ראשוני
            await send_message_with_retry(update, chat_id, bot_reply, is_bot_message=True)
            update_chat_history(chat_id, user_msg, "")
            
            # שלב 4: הפעלת משימות רקע (GPT-B, gpt_c, עדכון היסטוריה סופי, לוגים)
            asyncio.create_task(handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, last_bot_message))

        except Exception as ex:
            await handle_critical_error(ex, chat_id, user_msg, update)

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
                await update.message.reply_text(code_approved_message())
                await send_approval_message(update, chat_id)
            else:
                if current_try == 1:
                    await update.message.reply_text(get_retry_message_by_attempt(current_try))
                elif current_try == 2:
                    await update.message.reply_text(get_retry_message_by_attempt(current_try))
                elif current_try == 3:
                    await update.message.reply_text(get_retry_message_by_attempt(current_try))
                elif current_try >= 4:
                    await update.message.reply_text(not_approved_message())
        elif not approved:
            if user_msg.strip() == APPROVE_BUTTON_TEXT:
                approve_user(context.bot_data["sheet"], chat_id)
                await update.message.reply_text(nice_keyboard_message(), reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))
                await update.message.reply_text(remove_keyboard_message(), reply_markup=ReplyKeyboardRemove())
                await update.message.reply_text(full_access_message(), parse_mode="HTML")
            elif user_msg.strip() == DECLINE_BUTTON_TEXT:
                await update.message.reply_text("כדי להמשיך, יש לאשר את התנאים.")
                await send_approval_message(update, chat_id)
            else:
                await send_approval_message(update, chat_id)
    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def handle_background_tasks(update, context, chat_id, user_msg, message_id, log_payload, gpt_response, last_bot_message):
    """מטפל בכל המשימות ברקע - GPT-B, gpt_c, עדכון היסטוריה, לוגים"""
    try:
        bot_reply = gpt_response["bot_reply"]
        
        # GPT-B: יצירת תמצית לתשובת הבוט
        new_summary_for_history = None
        summary_response = None
        try:
            summary_response = await asyncio.to_thread(
                summarize_bot_reply,
                reply_text=bot_reply,
                chat_id=chat_id,
                original_message_id=message_id
            )
            new_summary_for_history = summary_response.get("summary")
        except Exception as e:
            logging.error(f"Error in GPT-B (summary): {e}")

        # עדכון היסטוריה סופי עם תמצית או תשובה מלאה
        if new_summary_for_history:
            update_chat_history(chat_id, "bot_summary", new_summary_for_history)
        else:
            update_chat_history(chat_id, "bot", bot_reply)

        # gpt_c: עדכון פרופיל משתמש
        gpt_c_response = None
        try:
            print(f"[DEBUG] קורא ל-gpt_c עם user_msg: {user_msg}")
            gpt_c_response = await asyncio.to_thread(
                gpt_c,
                user_message=user_msg,
                last_bot_message=last_bot_message,
                chat_id=chat_id,
                message_id=message_id
            )
            print(f"[DEBUG] gpt_c החזיר: {gpt_c_response}")
            if gpt_c_response and gpt_c_response.get("full_data"):
                updated_profile = {}
                updated_profile.update(gpt_c_response.get("full_data", {}))
                if gpt_c_response.get("updated_summary"):
                    updated_profile["summary"] = gpt_c_response.get("updated_summary")
                
                print(f"[DEBUG] מעדכן פרופיל עם: {updated_profile}")
                update_user_profile(chat_id, updated_profile)
                log_payload["gpt_c_data"] = {k: v for k, v in gpt_c_response.items() if k not in ["updated_summary", "full_data"]}
            else:
                print(f"[DEBUG] gpt_c לא החזיר נתונים תקינים")
        except Exception as e:
            print(f"[ERROR] שגיאה ב-gpt_c: {e}")
            logging.error(f"Error in gpt_c (profile update): {e}")

        # שמירת לוגים ונתונים נוספים
        log_payload.update({
            "gpt_a_response": bot_reply,
            "gpt_a_usage": {k: v for k, v in gpt_response.items() if k != "bot_reply"},
            "timestamp_end": datetime.now().isoformat()
        })
        
        # רישום לגיליון Google Sheets
        try:
            # חילוץ נתונים מ-gpt_response
            gpt_a_usage = normalize_usage_dict(gpt_response.get("usage", {}), gpt_response.get("usage", {}).get("model", "gpt-4o"))
            
            # חילוץ נתונים מ-summary_response (עם בדיקת None)
            gpt_b_usage = normalize_usage_dict(summary_response.get("usage", {}) if summary_response else {}, summary_response.get("usage", {}).get("model", "gpt-4.1-nano") if summary_response else "gpt-4.1-nano")
            
            # חילוץ נתונים מ-gpt_c_response (עם בדיקת None)
            gpt_e_usage = normalize_usage_dict(gpt_c_response if gpt_c_response else {}, gpt_c_response.get("model", "gpt-4.1-nano") if gpt_c_response else "gpt-4.1-nano")
            
            # חישוב סכומים
            total_tokens_calc = (
                gpt_a_usage.get("total_tokens", 0) + 
                gpt_b_usage.get("total_tokens", 0) + 
                gpt_e_usage.get("total_tokens", 0)
            )
            
            total_cost_usd_calc = (
                gpt_a_usage.get("cost_total", 0) + 
                gpt_b_usage.get("cost_total", 0) + 
                gpt_e_usage.get("cost_total", 0)
            )
            
            total_cost_ils_calc = (
                gpt_a_usage.get("cost_total_ils", 0) + 
                gpt_b_usage.get("cost_total_ils", 0) + 
                gpt_e_usage.get("cost_total_ils", 0)
            )
            
            print("[DEBUG] ---- log_to_sheets DEBUG ----")
            print(f"[DEBUG] message_id: {message_id}")
            print(f"[DEBUG] chat_id: {chat_id}")
            print(f"[DEBUG] user_msg: {user_msg}")
            print(f"[DEBUG] bot_reply: {bot_reply}")
            print(f"[DEBUG] reply_summary: {new_summary_for_history}")
            print(f"[DEBUG] gpt_a_usage: {gpt_a_usage}")
            print(f"[DEBUG] gpt_b_usage: {gpt_b_usage}")
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
                extract_usage=gpt_e_usage,
                total_tokens=total_tokens_calc,
                cost_usd=total_cost_usd_calc,
                cost_ils=total_cost_ils_calc
            )
            print("[DEBUG] ---- END log_to_sheets DEBUG ----")
        except Exception as e:
            print(f"[ERROR] שגיאה ב-log_to_sheets: {e}")
            logging.error(f"Error in log_to_sheets: {e}")
        
        log_event_to_file(log_payload)
        logging.info("---- סיום טיפול בהודעה (משתמש מאושר) ----")
        print("---- סיום טיפול בהודעה (משתמש מאושר) ----")

    except Exception as ex:
        await handle_critical_error(ex, chat_id, user_msg, update)

async def send_message_with_retry(update, chat_id, text, is_bot_message=True, max_retries=3):
    for attempt in range(max_retries):
        try:
            await update.message.reply_text(text, parse_mode="HTML")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            else:
                import logging
                logging.error(f"Failed to send message after {max_retries} attempts: {e}")
                return False
