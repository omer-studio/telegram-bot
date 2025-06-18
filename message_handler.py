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
from gpt_handler import get_main_response, summarize_bot_reply, gpt_e
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
                if user_msg.strip() == "✅קראתי את הכל ואני מאשר - כל מה שנכתב בצ'אט כאן הוא באחריותי":
                    approve_user(context.bot_data["sheet"], chat_id)
                    await update.message.reply_text(nice_keyboard_message(), reply_markup=ReplyKeyboardMarkup(nice_keyboard(), one_time_keyboard=True, resize_keyboard=True))
                    await update.message.reply_text(remove_keyboard_message(), reply_markup=ReplyKeyboardRemove())
                    await update.message.reply_text(full_access_message(), parse_mode="HTML")
                    logging.info("📤 נשלחה הודעת גישה מלאה למשתמש")
                    print("📤 נשלחה הודעת גישה מלאה למשתמש")
                elif user_msg.strip() == "❌לא מאשר":
                    await update.message.reply_text(DECLINE_BUTTON_TEXT())
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
            logging.info("📚 שולף סיכום משתמש מהגיליון...")
            print("📚 שולף סיכום משתמש מהגיליון...")
            user_summary = get_user_summary(chat_id)
            logging.info(f"סיכום משתמש: {user_summary!r}")
            print(f"סיכום משתמש: {user_summary!r}")

            logging.info("📚 שולף היסטוריית שיחה...")
            print("📚 שולף היסטוריית שיחה...")
            history_messages = get_chat_history_messages(chat_id)
            logging.info(f"היסטוריית שיחה: (נשלחו {len(history_messages)} הודעות אחרונות משני הצדדים)")
            print(f"היסטוריית שיחה: (נשלחו {len(history_messages)} הודעות אחרונות משני הצדדים)")

            full_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            if user_summary:
                full_messages.append({"role": "system", "content": f"מידע חשוב על היוזר (לשימושך והתייחסותך בעת מתן תשובה): {user_summary}"})
            full_messages.extend(history_messages)
            full_messages.append({"role": "user", "content": user_msg})

            logging.info("🤖 שולח ל-GPT הראשי...")
            print("🤖 שולח ל-GPT הראשי...")
            perf_gpt_start = time.time()
            main_response = get_main_response(full_messages)
            perf_gpt_end = time.time()
            print(f"[PERF] זמן קריאה ל-GPT: {perf_gpt_end - perf_gpt_start:.2f} שניות")
            print(f"[PERF] זמן מהגעת הודעה עד שליחת בקשה ל-GPT: {perf_gpt_start - perf_received_to_gpt_start:.2f} שניות")
            
            reply_text = main_response["bot_reply"]
            main_usage = {k: v for k, v in main_response.items() if k != "bot_reply"}
            main_prompt_tokens = main_usage.get("prompt_tokens", 0)
            main_completion_tokens = main_usage.get("completion_tokens", 0)
            main_total_tokens = main_usage.get("total_tokens", 0)
            main_cached_tokens = main_usage.get("cached_tokens", 0)
            main_model = main_usage.get("model", "")
            main_cost_gpt_a = main_usage.get("cost_gpt_a", 0)
            main_cost_total_usd = main_usage.get("cost_total", 0)
            main_cost_total_ils = main_usage.get("cost_total_ils", 0)

            logging.info(f"✅ התקבלה תשובה מה-GPT. אורך תשובה: {len(reply_text)} תווים")
            print(f"✅ התקבלה תשובה מה-GPT. אורך תשובה: {len(reply_text)} תווים")

            # --- עדכון היסטוריית שיחה (מיד, לפני שליחת התשובה) ---
            num_words = len(reply_text.split())
            if num_words > 50:
                logging.info(f"✂️ התשובה מעל 50 מילים - מבצע סיכום ({num_words} מילים)")
                sum_response = summarize_bot_reply(reply_text)
                summary_usage = {k: v for k, v in sum_response.items() if k != "bot_summary"}
                reply_summary = sum_response.get("bot_summary", reply_text)
                sum_prompt = summary_usage.get("prompt_tokens", 0)
                sum_completion = summary_usage.get("completion_tokens", 0)
                sum_total = summary_usage.get("total_tokens", 0)
                sum_model = summary_usage.get("model", "")
            else:
                logging.info(f"✂️ התשובה קצרה - לא מבצע סיכום ({num_words} מילים)")
                reply_summary = reply_text
                summary_usage = {}
                sum_prompt = sum_completion = sum_total = 0
                sum_model = ""

            logging.info("💾 מעדכן היסטוריית שיחה..."); print("💾 מעדכן היסטוריית שיחה...")
            update_chat_history(chat_id, user_msg, reply_summary)
            logging.info("✅ היסטוריית שיחה עודכנה"); print("✅ היסטוריית שיחה עודכנה")

            # --- שליחת תשובה למשתמש ---
            reply_text_one_line = reply_text.replace("\n", " ").replace("\r", " ")
            print(f"[📤 הודעת בוט]: {reply_text_one_line}")
            logging.info("📨 תשובה נשלחה למשתמש")
            print("📨 תשובה נשלחה למשתמש")
            print(f"[DEBUG] about to send reply from bot to user: chat_id={chat_id}")
            perf_send_start = time.time()
            await send_message(update, chat_id, reply_text)
            perf_send_end = time.time()
            print(f"[PERF] זמן שליחת הודעה ל-Telegram: {perf_send_end - perf_send_start:.2f} שניות")

            # --- כל שאר הפעולות ירוצו ברקע ---
            async def post_reply_tasks():
                try:
                    print("[DEBUG][post_reply_tasks] --- START ---")
                    # עדכון ת.ז רגשית, גיליון, לוגים
                    logging.info("🔍 מתחיל עדכון חכם של ת.ז הרגשית..."); print("🔍 מתחיל עדכון חכם של ת.ז הרגשית...")
                    print(f"[DEBUG][post_reply_tasks] user_summary: {user_summary} (type: {type(user_summary)})")
                    if isinstance(user_summary, str):
                        import json
                        try:
                            existing_profile = json.loads(user_summary)
                        except Exception as e:
                            print(f"[DEBUG][post_reply_tasks] Failed to json.loads user_summary: {e}")
                            existing_profile = {}
                    elif isinstance(user_summary, dict):
                        existing_profile = user_summary
                    else:
                        existing_profile = {}
                    print(f"[DEBUG][post_reply_tasks] existing_profile: {existing_profile} (type: {type(existing_profile)})")
                    # קריאה ל-gpt_e עם הסיכום הקיים
                    existing_summary = existing_profile.get("summary", "") if isinstance(existing_profile, dict) else ""
                    # הוספת הקשר מההיסטוריה - ההודעה האחרונה של הבוט
                    last_bot_message = ""
                    for msg in reversed(history_messages):
                        if msg.get("role") == "assistant":
                            last_bot_message = msg.get("content", "")
                            break
                    print(f"[DEBUG][post_reply_tasks] לפני קריאה ל-gpt_e:")
                    print(f"[DEBUG][post_reply_tasks] existing_summary: {existing_summary}")
                    print(f"[DEBUG][post_reply_tasks] user_msg: {user_msg}")
                    print(f"[DEBUG][post_reply_tasks] last_bot_message: {last_bot_message}")
                    print(f"[DEBUG][post_reply_tasks] קורא ל-gpt_e...")
                    gpt_e_result = gpt_e(existing_summary, user_msg, last_bot_message)
                    
                    print(f"[DEBUG][post_reply_tasks] אחרי קריאה ל-gpt_e:")
                    print(f"[DEBUG][post_reply_tasks] gpt_e_result: {gpt_e_result}")
                    
                    if gpt_e_result is None:
                        # אין שינוי - משתמשים בפרופיל הקיים
                        updated_profile = existing_profile
                        extract_usage = {}
                    else:
                        # יש שינוי - מעדכנים את הפרופיל
                        updated_summary = gpt_e_result.get("updated_summary", "")
                        full_data = gpt_e_result.get("full_data", {})
                        updated_profile = {**existing_profile, **full_data}
                        if updated_summary:
                            updated_profile["summary"] = updated_summary
                        extract_usage = {k: v for k, v in gpt_e_result.items() if k not in ["updated_summary", "full_data"]}
                    
                    print(f"[DEBUG][post_reply_tasks] updated_profile: {updated_profile} (type: {type(updated_profile)})")
                    print(f"[DEBUG][post_reply_tasks] extract_usage: {extract_usage} (type: {type(extract_usage)})")
                    identity_fields = updated_profile if updated_profile and updated_profile != existing_profile else {}
                    print(f"[DEBUG][post_reply_tasks] identity_fields: {identity_fields} (type: {type(identity_fields)})")
                    if updated_profile and updated_profile != existing_profile:
                        print(f"[DEBUG][post_reply_tasks] update_user_profile called with: {updated_profile}")
                        logging.info(f"[DEBUG] update_user_profile called with: {updated_profile}")
                        update_user_profile(chat_id, updated_profile)
                        logging.info("📝 ת.ז רגשית עודכנה בהצלחה"); print("📝 ת.ז רגשית עודכנה בהצלחה")

                    logging.info("💰 מחשב עלויות..."); print("💰 מחשב עלויות...")
                    logging.info("💾 שומר נתוני שיחה בגיליון..."); print("💾 שומר נתוני שיחה בגיליון...")
                    try:
                        log_to_sheets(
                            message_id, chat_id, user_msg, reply_text, reply_summary,
                            main_usage, summary_usage, extract_usage,
                            main_total_tokens, main_cost_total_usd, main_cost_total_ils,
                            merge_usage=None, fields_updated_by_gpt_e=None
                        )
                        logging.info("✅ נתוני שיחה נשמרו בגיליון"); print("✅ נתוני שיחה נשמרו בגיליון")
                    except Exception as e:
                        import traceback
                        from notifications import send_error_notification
                        tb = traceback.format_exc()
                        error_msg = (
                            f"❌ שגיאה בשמירה לגיליון:\n"
                            f"סוג: {type(e).__name__}\n"
                            f"שגיאה: {e}\n"
                            f"chat_id: {chat_id}\n"
                            f"message_id: {message_id}\n"
                            f"user_msg: {str(user_msg)[:100]}\n"
                            f"traceback:\n{tb}"
                        )
                        print(error_msg)
                        send_error_notification(error_message=error_msg, chat_id=chat_id, user_msg=user_msg, error_type="sheets_log_error")
                        logging.error("❌ שגיאה בשמירה לגיליון (נשלחה התראה לאדמין בלבד, המשתמש לא רואה כלום)")

                    logging.info("💾 שומר לוג מפורט לקובץ..."); print("💾 שומר לוג מפורט לקובץ...")
                    print(f"[DEBUG][post_reply_tasks] log_payload BEFORE update: {log_payload}")
                    log_payload.update({
                        "user_summary": user_summary,
                        "identity_fields": identity_fields,
                        "gpt_reply": reply_text,
                        "summary_saved": reply_summary,
                        "tokens": {
                            "main_prompt": main_prompt_tokens,
                            "main_completion": main_completion_tokens,
                            "main_total": main_total_tokens,
                            "summary_prompt": sum_prompt,
                            "summary_completion": sum_completion,
                            "summary_total": sum_total,
                            "extract_prompt": extract_usage.get("prompt_tokens", 0) if isinstance(extract_usage, dict) else 0,
                            "extract_completion": extract_usage.get("completion_tokens", 0) if isinstance(extract_usage, dict) else 0,
                            "extract_total": extract_usage.get("total_tokens", 0) if isinstance(extract_usage, dict) else 0,
                            "total_all": main_total_tokens,
                            "main_cost_total_usd": main_cost_total_usd,
                            "main_cost_total_ils": main_cost_total_ils
                        }
                    })
                    print(f"[DEBUG][post_reply_tasks] log_payload AFTER update: {log_payload}")
                    log_event_to_file(log_payload)
                    logging.info("✅ לוג מפורט נשמר לקובץ"); print("✅ לוג מפורט נשמר לקובץ")

                    total_time = (datetime.now() - datetime.fromisoformat(log_payload['timestamp_start'])).total_seconds()
                    logging.info(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")
                    print(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")

                    print(f"[HIST] נשלח פרומט + {len(history_messages)} הודעות היסטוריה + הודעה חדשה: {user_msg.replace(chr(10), ' ')[:80]}")
                except Exception as critical_error:
                    import traceback
                    import sys
                    logging.error(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
                    print(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
                    print("[DEBUG][post_reply_tasks][EXCEPTION] locals:")
                    for k, v in locals().items():
                        print(f"[DEBUG][post_reply_tasks][EXCEPTION] {k} = {v} (type: {type(v)})")
                    print(traceback.format_exc())
                    await handle_critical_error(critical_error, chat_id, user_msg, update)
                logging.info("---- סיום טיפול בהודעה ----"); print("---- סיום טיפול בהודעה ----")

            asyncio.create_task(post_reply_tasks())
            return

        except Exception as critical_error:
            logging.error(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
            print(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
            await handle_critical_error(critical_error, chat_id, user_msg, update)

        logging.info("---- סיום טיפול בהודעה ----")
        print("---- סיום טיפול בהודעה ----")

    except Exception as e:
        import traceback
        from notifications import send_error_notification
        tb = traceback.format_exc()
        chat_id = None
        user_msg = None
        try:
            chat_id = update.effective_chat.id if update and update.effective_chat else None
            user_msg = update.message.text if update and update.message else None
        except Exception:
            pass
        send_error_notification(error_message=f"שגיאה בטיפול בהודעה:\n{e}\n{tb}", chat_id=chat_id, user_msg=user_msg)
        if update and update.message:
            await update.message.reply_text(error_human_funny_message())
    finally:
        print("🏁 [DEBUG] handle_message מסיים (בהצלחה או בשגיאה)") 
        # תודה1

async def send_message_with_retry(update, chat_id, text, max_retries=3):
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
