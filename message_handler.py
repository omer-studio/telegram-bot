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
from secret_commands import handle_secret_command
from messages import get_welcome_messages, get_retry_message_by_attempt, approval_text, approval_keyboard, APPROVE_BUTTON_TEXT, DECLINE_BUTTON_TEXT, code_approved_message, code_not_received_message, not_approved_message, nice_keyboard, nice_keyboard_message, remove_keyboard_message, full_access_message, error_human_funny_message
from notifications import handle_critical_error
from sheets_handler import increment_code_try, get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user, ensure_user_state_row
from gpt_handler import get_main_response, summarize_bot_reply, gpt_c
from utils import log_event_to_file, update_chat_history, get_chat_history_messages
from fields_dict import FIELDS_DICT
import asyncio
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

        try:
            # שלב 1: בדיקת משתמש חדש (Onboarding)
            logging.info("[Onboarding] בודק האם המשתמש פונה בפעם הראשונה בחייו...")
            print("[Onboarding] בודק האם המשתמש פונה בפעם הראשונה בחייו...")
            is_first_time = ensure_user_state_row(
                context.bot_data["sheet"],           # גיליון 1 (access_codes)
                context.bot_data["sheet_states"],    # גיליון user_states
                chat_id
            )
            if is_first_time:
                logging.info("[Onboarding] משתמש חדש - נוסף ל-user_states (code_try=0)")
                print("[Onboarding] משתמש חדש - נוסף ל-user_states (code_try=0)")
                welcome_messages = get_welcome_messages()  # שלוף את כל הודעות קבלת הפנים
                for message in welcome_messages:
                    await send_message(update, chat_id, message)  # שלח את כל ההודעות אחת אחרי השנייה

                logging.info("📤 נשלחו הודעות וולקאם למשתמש חדש")
                print("📤 נשלחו הודעות וולקאם למשתמש חדש")
                logging.info("---- סיום טיפול בהודעה (משתמש חדש) ----")
                print("---- סיום טיפול בהודעה (משתמש חדש) ----")
                return
            else:
                logging.info("[Onboarding] המשתמש כבר התחיל או עבר תהליך רישום קודם.")
                print("[Onboarding] המשתמש כבר התחיל או עבר תהליך רישום קודם.")
        except Exception as ex:
            logging.error(f"[Onboarding] ❌ שגיאה באתחול משתמש חדש: {ex}")
            print(f"[Onboarding] ❌ שגיאה באתחול משתמש חדש: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            return

        # --- מדידת זמן: קבלת הודעה עד שליחת בקשה ל-GPT ---
        perf_received_to_gpt_start = time.time()

        try:
            logging.info("🔍 בודק הרשאות משתמש מול הגיליון...")
            print("🔍 בודק הרשאות משתמש מול הגיליון...")
            exists, code, approved = check_user_access(context.bot_data["sheet"], chat_id)
            logging.info(f"סטטוס משתמש: קיים={exists}, קוד={code}, מאושר={approved}")
            print(f"סטטוס משתמש: קיים={exists}, קוד={code}, מאושר={approved}")
        except Exception as ex:
            logging.error(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            print(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            return

        if not exists:
            logging.info(f"👤 משתמש לא קיים, בודק קוד גישה: {user_msg!r}")
            print(f"👤 משתמש לא קיים, בודק קוד גישה: {user_msg!r}")
            try:
                current_try = increment_code_try(context.bot_data["sheet_states"], chat_id)
                if current_try is None:
                    current_try = 0  # להתחלה

                if current_try == 0:
                    current_try = 1

                if register_user(context.bot_data["sheet"], chat_id, user_msg):
                    logging.info(f"✅ קוד גישה אושר למשתמש {chat_id}")
                    print(f"✅ קוד גישה אושר למשתמש {chat_id}")
                    await update.message.reply_text(code_approved_message())
                    
                    await send_approval_message(update, chat_id)

                    logging.info("📤 נשלחה הודעת אישור קוד למשתמש")
                    print("📤 נשלחה הודעת אישור קוד למשתמש")
                else:
                    logging.warning(f"❌ קוד גישה לא תקין עבור {chat_id}")
                    print(f"❌ קוד גישה לא תקין עבור {chat_id}")               
                    
                    if current_try == 1:
                        await update.message.reply_text(get_retry_message_by_attempt(current_try))
                    elif current_try == 2:
                        await update.message.reply_text(get_retry_message_by_attempt(current_try))
                    elif current_try == 3:
                        await update.message.reply_text(get_retry_message_by_attempt(current_try))
                    elif current_try >= 4:
                        await update.message.reply_text(not_approved_message())
                    logging.info("📤 נשלחה הודעת קוד לא תקין למשתמש")
                    print("📤 נשלחה הודעת קוד לא תקין למשתמש")

            except Exception as ex:
                logging.error(f"❌ שגיאה בתהליך רישום משתמש חדש: {ex}")
                print(f"❌ שגיאה בתהליך רישום משתמש חדש: {ex}")
                await handle_critical_error(ex, chat_id, user_msg, update)

            logging.info("---- סיום טיפול בהודעה (משתמש לא קיים) ----")
            print("---- סיום טיפול בהודעה (משתמש לא קיים) ----")
            return

        try:
            logging.info("🔍 בודק הרשאות משתמש מול הגיליון...")
            print("🔍 בודק הרשאות משתמש מול הגיליון...")
            exists, code, approved = check_user_access(context.bot_data["sheet"], chat_id)
            logging.info(f"סטטוס משתמש: קיים={exists}, קוד={code}, מאושר={approved}")
            print(f"סטטוס משתמש: קיים={exists}, קוד={code}, מאושר={approved}")
        except Exception as ex:
            logging.error(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            print(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
            return

        if not approved:
            logging.info(f"📝 משתמש {chat_id} קיים אך לא מאושר, תוכן ההודעה: {user_msg!r}")
            print(f"📝 משתמש {chat_id} קיים אך לא מאושר, תוכן ההודעה: {user_msg!r}")
            try:
                if user_msg.strip() == APPROVE_BUTTON_TEXT:
                    approve_user(context.bot_data["sheet"], chat_id)
                    await update.message.reply_text(nice_keyboard_message(), reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))
                    await update.message.reply_text(remove_keyboard_message(), reply_markup=ReplyKeyboardRemove())
                    await update.message.reply_text(full_access_message(), parse_mode="HTML")
                    logging.info("📤 נשלחה הודעת גישה מלאה למשתמש")
                    print("📤 נשלחה הודעת גישה מלאה למשתמש")
                elif user_msg.strip() == DECLINE_BUTTON_TEXT:
                    await update.message.reply_text("כדי להמשיך, יש לאשר את התנאים.")
                    await send_approval_message(update, chat_id)
                    return
                else:
                    await send_approval_message(update, chat_id)
                    logging.info("📤 נשלחה תזכורת לאישור תנאים למשתמש")
                    print("📤 נשלחה תזכורת לאישור תנאים למשתמש")

            except Exception as ex:
                logging.error(f"❌ שגיאה בתהליך אישור תנאים: {ex}")
                print(f"❌ שגיאה בתהליך אישור תנאים: {ex}")
                await handle_critical_error(ex, chat_id, user_msg, update)
            logging.info("---- סיום טיפול בהודעה (משתמש לא מאושר) ----")
            print("---- סיום טיפול בהודעה (משתמש לא מאושר) ----")
            return

        logging.info("👨‍💻 משתמש מאושר, מתחיל תהליך מענה...")
        print("👨‍💻 משתמש מאושר, מתחיל תהליך מענה...")

        try:
            # שלב 1: איסוף היסטוריה ונתונים
            user_summary_data = get_user_summary(context.bot_data["sheet"], chat_id) or {}
            current_summary = user_summary_data.get("summary", "")
            history_messages = get_chat_history_messages(chat_id)
            
            # בניית ההודעות ל-GPT-A
            messages_for_gpt = [{"role": "system", "content": SYSTEM_PROMPT}]
            if current_summary:
                messages_for_gpt.append({"role": "system", "content": f"מידע חשוב על היוזר (לשימושך והתייחסותך בעת מתן תשובה): {current_summary}"})
            messages_for_gpt.extend(history_messages)
            messages_for_gpt.append({"role": "user", "content": user_msg})

            last_bot_message = next((msg.get("content", "") for msg in reversed(history_messages) if msg.get("role") == "assistant"), "")

            # שלב 2: קריאה ל-GPT-A למענה ראשי
            gpt_response = await asyncio.to_thread(
                get_main_response,
                full_messages=messages_for_gpt,
                chat_id=chat_id,
                message_id=message_id
            )
            bot_reply = gpt_response["bot_reply"]

            # שלב 3: שליחת התשובה למשתמש ועדכון היסטוריה ראשוני
            await send_message_with_retry(update, chat_id, bot_reply, is_bot_message=True)
            update_chat_history(chat_id, "user", user_msg) 

            # שלב 4: הפעלת משימות רקע (GPT-B, gpt_c, עדכון היסטוריה סופי, לוגים)
            async def post_reply_tasks(reply_from_bot, summary_before_update):
                # GPT-B: יצירת תמצית לתשובת הבוט
                new_summary_for_history = None
                try:
                    summary_response = await asyncio.to_thread(
                        summarize_bot_reply,
                        reply_text=reply_from_bot,
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
                    update_chat_history(chat_id, "bot", reply_from_bot)

                # gpt_c: עדכון פרופיל משתמש
                try:
                    gpt_e_response = await asyncio.to_thread(
                        gpt_c,
                        user_message=user_msg,
                        last_bot_message=last_bot_message,
                        chat_id=chat_id,
                        message_id=message_id
                    )
                    if gpt_e_response and gpt_e_response.get("full_data"):
                        updated_profile = user_summary_data.copy()
                        updated_profile.update(gpt_e_response.get("full_data", {}))
                        if gpt_e_response.get("updated_summary"):
                            updated_profile["summary"] = gpt_e_response.get("updated_summary")
                        
                        update_user_profile(chat_id, updated_profile)
                        log_payload["gpt_e_data"] = {k: v for k, v in gpt_e_response.items() if k not in ["updated_summary", "full_data"]}
                except Exception as e:
                    logging.error(f"Error in gpt_c (profile update): {e}")

                # שמירת לוגים ונתונים נוספים
                log_payload.update({
                    "gpt_a_response": reply_from_bot,
                    "gpt_a_usage": {k: v for k, v in gpt_response.items() if k != "bot_reply"},
                    "timestamp_end": datetime.now().isoformat()
                })
                log_event_to_file(log_payload)
                logging.info("---- סיום טיפול בהודעה (משתמש מאושר) ----")
                print("---- סיום טיפול בהודעה (משתמש מאושר) ----")

            asyncio.create_task(post_reply_tasks(bot_reply, current_summary))

        except Exception as ex:
            await handle_critical_error(ex, chat_id, user_msg, update)

    except Exception as ex:
        await handle_critical_error(ex, locals().get('chat_id'), locals().get('user_msg'), update)

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
