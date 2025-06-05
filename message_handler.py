"""
message_handler.py — טיפול בהודעות טלגרם

מכיל את הפונקציה הראשית שמטפלת בכל הודעה נכנסת (handle_message), כולל כל הלוגיקה של הרשאות, רישום, מענה, לוגים ועוד.
כל שינוי לוגי יש לעשות בזהירות! אין לשנות לוגיקה, רק להעביר קוד.
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from datetime import datetime
import logging
from secret_commands import handle_secret_command
from messages import get_welcome_messages, get_retry_message_by_attempt, approval_text, approval_keyboard, APPROVE_BUTTON_TEXT, DECLINE_BUTTON_TEXT, code_approved_message, code_not_received_message, not_approved_message, nice_keyboard, nice_keyboard_message, remove_keyboard_message, full_access_message
from notifications import handle_critical_error
from sheets_handler import increment_code_try, get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user, ensure_user_state_row
from gpt_handler import get_main_response, summarize_bot_reply, smart_update_profile
from utils import log_event_to_file, update_chat_history, get_chat_history_messages
from config import SYSTEM_PROMPT, CRITICAL_ERRORS_PATH
from fields_dict import FIELDS_DICT

# פונקציה לשליחת הודעה למשתמש (הועתקה מ-main.py כדי למנוע לולאת ייבוא)
async def send_message(update, chat_id, text, is_bot_message=True):
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
            send_error_notification(f"[send_message] שליחת הודעה נכשלה: {e}", chat_id=chat_id, user_msg=text)
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
    await update.message.reply_text(
        approval_text() + "\n\nאנא לחץ על 'מאשר' או 'לא מאשר' במקלדת למטה.",
        reply_markup=ReplyKeyboardMarkup(approval_keyboard(), one_time_keyboard=True, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    הפונקציה הראשית שמטפלת בכל הודעה נכנסת מהמשתמש.
    אין לשנות לוגיקה! רק להעביר קוד.
    """
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
                full_messages.append({"role": "system", "content": f"מידע על המשתמש: {user_summary}"})
            full_messages.extend(history_messages)
            full_messages.append({"role": "user", "content": user_msg})

            logging.info("🤖 שולח ל-GPT הראשי...")
            print("🤖 שולח ל-GPT הראשי...")
            
            main_response = get_main_response(full_messages)
            
            reply_text = main_response["bot_reply"]
            main_usage = main_response  # כל usage dict
            main_prompt_tokens = main_usage.get("prompt_tokens", 0)
            main_completion_tokens = main_usage.get("completion_tokens", 0)
            main_total_tokens = main_usage.get("total_tokens", 0)
            main_cached_tokens = main_usage.get("cached_tokens", 0)
            main_model = main_usage.get("model", "")
            main_cost_gpt1 = main_usage.get("cost_gpt1", 0)
            main_cost_total_usd = main_usage.get("cost_total", 0)
            main_cost_total_ils = main_usage.get("cost_total_ils", 0)

            logging.info(f"✅ התקבלה תשובה מה-GPT. אורך תשובה: {len(reply_text)} תווים")
            print(f"✅ התקבלה תשובה מה-GPT. אורך תשובה: {len(reply_text)} תווים")

            # שלח למשתמש מיד את התשובה המלאה
            reply_text_one_line = reply_text.replace("\n", " ").replace("\r", " ")
            print(f"[📤 הודעת בוט]: {reply_text_one_line}")
            logging.info("📨 תשובה נשלחה למשתמש")
            print("📨 תשובה נשלחה למשתמש")
            print(f"[DEBUG] about to send reply from bot to user: chat_id={chat_id}")
            await send_message(update, chat_id, reply_text)

            # עכשיו, אם צריך, בצע סיכום ברקע ועדכן לוגים/היסטוריה/גיליון
            num_words = len(reply_text.split())
            if num_words > 50:
                logging.info(f"✂️ התשובה מעל 50 מילים - מבצע סיכום ({num_words} מילים)")
                summary_response = summarize_bot_reply(reply_text)

                try:
                    if isinstance(summary_response, tuple) and len(summary_response) >= 5:
                        reply_summary = summary_response[0]
                        sum_prompt = summary_response[1]
                        sum_completion = summary_response[2]
                        sum_total = summary_response[3]
                        sum_model = summary_response[4]
                        print("✅ סיכום פוצח בהצלחה")
                    else:
                        print(f"⚠️ summarize_bot_reply החזיר פורמט לא צפוי: {summary_response}")
                        reply_summary = reply_text  # נשתמש בטקסט המקורי
                        sum_prompt = sum_completion = sum_total = 0
                        sum_model = ""
                except Exception as e:
                    print(f"💥 שגיאה בפירוק סיכום: {e}")
                    reply_summary = reply_text
                    sum_prompt = sum_completion = sum_total = 0
                    sum_model = ""
            else:
                logging.info(f"✂️ התשובה קצרה - לא מבצע סיכום ({num_words} מילים)")
                reply_summary = reply_text
                sum_prompt = sum_completion = sum_total = 0
                sum_model = ""

            # המשך עדכון לוגים/היסטוריה/גיליון (כמו קודם)
            try:
                logging.info("🔍 מתחיל עדכון חכם של ת.ז הרגשית...")
                if isinstance(user_summary, str):
                    import json
                    try:
                        existing_profile = json.loads(user_summary)
                    except Exception:
                        existing_profile = {}
                elif isinstance(user_summary, dict):
                    existing_profile = user_summary
                else:
                    existing_profile = {}
                updated_profile, extract_usage, merge_usage = smart_update_profile(existing_profile, user_msg)
                identity_fields = updated_profile
                if updated_profile and updated_profile != existing_profile:
                    print(f"[DEBUG] update_user_profile called with: {updated_profile}")
                    logging.info(f"[DEBUG] update_user_profile called with: {updated_profile}")
                    update_user_profile(chat_id, updated_profile)
                    logging.info("📝 ת.ז רגשית עודכנה בהצלחה")
            except Exception as e:
                logging.error(f"❌ שגיאה בעדכון ת.ז רגשית: {e}")
                identity_fields = {}
                extract_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model": ""}
                merge_usage = None

            logging.info("💰 מחשב עלויות...")
            print("💰 מחשב עלויות...")
            main_usage = (
                main_prompt_tokens,         # 0
                main_completion_tokens,     # 1
                main_total_tokens,          # 2
                main_cached_tokens,         # 3
                main_model,                 # 4
                main_cost_gpt1,             # 5
                main_cost_total_usd,        # 6
                main_cost_total_ils,        # 7
                main_total_tokens,          # 8
                main_cost_total_usd,        # 9
                main_cost_total_ils,        # 10
                main_model                  # 11
            )
            summary_usage = ("", sum_prompt, sum_completion, sum_total, sum_model)
            
            logging.info(f"💸 עלות כוללת: ${main_cost_total_usd} (₪{main_cost_total_ils}), טוקנים: {main_total_tokens}")
            print(f"💸 עלות כוללת: ${main_cost_total_usd} (₪{main_cost_total_ils}), טוקנים: {main_total_tokens}")

            logging.info("💾 מעדכן היסטוריית שיחה...")
            print("💾 מעדכן היסטוריית שיחה...")
            update_chat_history(chat_id, user_msg, reply_summary)
            logging.info("✅ היסטוריית שיחה עודכנה")
            print("✅ היסטוריית שיחה עודכנה")

            logging.info("💾 שומר נתוני שיחה בגיליון...")
            print("💾 שומר נתוני שיחה בגיליון...")
            log_to_sheets(
                message_id, chat_id, user_msg, reply_text, reply_summary,
                main_usage, summary_usage, extract_usage,
                main_total_tokens, main_cost_total_usd, main_cost_total_ils
            )
            logging.info("✅ נתוני שיחה נשמרו בגיליון")
            print("✅ נתוני שיחה נשמרו בגיליון")

            logging.info("💾 שומר לוג מפורט לקובץ...")
            print("💾 שומר לוג מפורט לקובץ...")
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
                    "extract_prompt": extract_usage[0] if isinstance(extract_usage, (list, tuple)) and len(extract_usage) > 0 else 0,
                    "extract_completion": extract_usage[4] if isinstance(extract_usage, (list, tuple)) and len(extract_usage) > 4 else 0,
                    "extract_total": extract_usage[5] if isinstance(extract_usage, (list, tuple)) and len(extract_usage) > 5 else 0,
                    "total_all": main_total_tokens,
                    "main_cost_total_usd": main_cost_total_usd,
                    "main_cost_total_ils": main_cost_total_ils
                }
            })
            log_event_to_file(log_payload)
            logging.info("✅ לוג מפורט נשמר לקובץ")
            print("✅ לוג מפורט נשמר לקובץ")

            total_time = (datetime.now() - datetime.fromisoformat(log_payload['timestamp_start'])).total_seconds()
            logging.info(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")
            print(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")

            print(f"[HIST] נשלח פרומט + {len(history_messages)} הודעות היסטוריה + הודעה חדשה: {user_msg.replace(chr(10), ' ')[:80]}")

        except Exception as critical_error:
            logging.error(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
            print(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
            await handle_critical_error(critical_error, chat_id, user_msg, update)

        logging.info("---- סיום טיפול בהודעה ----")
        print("---- סיום טיפול בהודעה ----")

    except Exception as ultimate_error:
        print(f"🚨 [ULTIMATE_ERROR] שגיאה כללית לא צפויה: {ultimate_error}")
        print(f"🚨 [ULTIMATE_ERROR] Type: {type(ultimate_error)}")
        try:
            await update.message.reply_text(
                "😅  אופס! קרתה תקלה טכנית לא צפויה איזה פאדיחות. "
                "הבוט ממשיך לעבוד פשוט יקח לו קצת זמן לענות, אנא נסה שוב בעוד רגע."
            )
        except:
            print("🚨 [ULTIMATE_ERROR] לא הצלחתי אפילו לשלוח הודעת שגיאה למשתמש")
        try:
            import traceback
            error_details = {
                "timestamp": datetime.now().isoformat(),
                "error_type": str(type(ultimate_error)),
                "error_message": str(ultimate_error),
                "traceback": traceback.format_exc(),
                "chat_id": getattr(update.message, 'chat_id', 'unknown') if hasattr(update, 'message') else 'unknown'
            }
            with open(CRITICAL_ERRORS_PATH, "a", encoding="utf-8") as f:
                import json
                f.write(json.dumps(error_details, ensure_ascii=False) + "\n")
            print("✅ [ULTIMATE_ERROR] השגיאה נשמרה לקובץ critical_errors.jsonl")
        except:
            print("🚨 [ULTIMATE_ERROR] לא הצלחתי אפילו לשמור את השגיאה לקובץ")
    finally:
        print("🏁 [DEBUG] handle_message מסיים (בהצלחה או בשגיאה)") 