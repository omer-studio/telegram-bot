"""
🤖 הבוט הראשי - קובץ מנהל שמתאם בין כל המחלקות
כולל לוגים מפורטים לכל שלב ושלב - כל פעולה תירשם ללוג!
"""

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ייבוא המחלקות השונות
from config import TELEGRAM_BOT_TOKEN, SYSTEM_PROMPT, config
from gpt_handler import get_main_response, summarize_bot_reply, extract_user_profile_fields, calculate_total_cost
from sheets_handler import get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user, approve_user
from notifications import send_startup_notification, handle_critical_error, handle_non_critical_error
from utils import log_event_to_file, update_chat_history, get_chat_history_messages

# הגדרת הלוגר - גם למסוף וגם לקובץ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("---- התחלת טיפול בהודעה ----")
    log_payload = {
        "chat_id": None,
        "message_id": None,
        "timestamp_start": datetime.now().isoformat()
    }

    # קבלת נתונים בסיסיים מההודעה
    try:
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        user_msg = update.message.text
        log_payload["chat_id"] = chat_id
        log_payload["message_id"] = message_id
        log_payload["user_msg"] = user_msg
        logging.info(f"📩 התקבלה הודעה | chat_id={chat_id}, message_id={message_id}, תוכן={user_msg!r}")
    except Exception as ex:
        logging.error(f"❌ שגיאה בשליפת מידע מההודעה: {ex}")
        await handle_critical_error(ex, None, None, update)
        return

    # בדיקת משתמש וקוד גישה
    try:
        logging.info("🔍 בודק הרשאות משתמש מול הגיליון...")
        exists, code, approved = check_user_access(context.bot_data["sheet"], chat_id)
        logging.info(f"סטטוס משתמש: קיים={exists}, קוד={code}, מאושר={approved}")
    except Exception as ex:
        logging.error(f"❌ שגיאה בגישה לטבלת משתמשים: {ex}")
        await handle_critical_error(ex, chat_id, user_msg, update)
        return

    # טיפול ברישום משתמש חדש
    if not exists:
        logging.info(f"👤 משתמש לא קיים, בודק קוד גישה: {user_msg!r}")
        try:
            if register_user(context.bot_data["sheet"], chat_id, user_msg):
                logging.info(f"✅ קוד גישה אושר למשתמש {chat_id}")
                await update.message.reply_text("✅ קוד אושר. עכשיו שלח 'מאשר' כדי להמשיך 🙏")
                logging.info("📤 נשלחה הודעת אישור קוד למשתמש")
            else:
                logging.warning(f"❌ קוד גישה לא תקין עבור {chat_id}")
                await update.message.reply_text("🔒 לא זיהיתי את הקוד. נסה שוב או בקש קוד חדש.")
                logging.info("📤 נשלחה הודעת קוד לא תקין למשתמש")
        except Exception as ex:
            logging.error(f"❌ שגיאה בתהליך רישום משתמש חדש: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
        logging.info("---- סיום טיפול בהודעה (משתמש לא קיים) ----")
        return

    # טיפול באישור תנאים
    if not approved:
        logging.info(f"📝 משתמש {chat_id} קיים אך לא מאושר, תוכן ההודעה: {user_msg!r}")
        try:
            if user_msg.strip().lower() == "מאשר":
                approve_user(context.bot_data["sheet"], chat_id)
                logging.info(f"🙌 משתמש {chat_id} אישר תנאים בהצלחה")
                await update.message.reply_text("מעולה, קיבלת גישה מלאה ✅ דבר אליי.")
                logging.info("📤 נשלחה הודעת גישה מלאה למשתמש")
            else:
                await update.message.reply_text("📜 לפני שנתחיל, חשוב שתאשר שאתה לוקח אחריות על השימוש בצ׳אט הזה.\n\nשלח 'מאשר' כדי להמשיך")
                logging.info("📤 נשלחה תזכורת לאישור תנאים למשתמש")
        except Exception as ex:
            logging.error(f"❌ שגיאה בתהליך אישור תנאים: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
        logging.info("---- סיום טיפול בהודעה (משתמש לא מאושר) ----")
        return

    # המשך טיפול בהודעה רגילה
    logging.info("👨‍💻 משתמש מאושר, מתחיל תהליך מענה...")
    try:
        # שלב 1: הכנת קונטקסט
        logging.info("📚 שולף סיכום משתמש מהגיליון...")
        user_summary = get_user_summary(chat_id)
        logging.info(f"סיכום משתמש: {user_summary!r}")

        logging.info("📚 שולף היסטוריית שיחה...")
        history_messages = get_chat_history_messages(chat_id)
        logging.info(f"היסטוריית שיחה: {history_messages!r}")

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if user_summary:
            full_messages.append({"role": "system", "content": f"מידע על המשתמש: {user_summary}"})
        full_messages.extend(history_messages)
        full_messages.append({"role": "user", "content": user_msg})

        # שלב 2: שליחה ל-GPT
        logging.info("🤖 שולח ל-GPT הראשי...")
        main_response = get_main_response(full_messages)
        reply_text, main_prompt, main_completion, main_total, main_model = main_response
        logging.info(f"✅ התקבלה תשובה מה-GPT. אורך תשובה: {len(reply_text)} תווים")

        # שלב 3: קיצור תשובה
        logging.info("✂️ מקצר את התשובה...")
        summary_response = summarize_bot_reply(reply_text)
        reply_summary, sum_prompt, sum_completion, sum_total, sum_model = summary_response
        logging.info(f"סיכום תשובה: {reply_summary!r}")

        # שלב 4: שליחת תשובה למשתמש
        logging.info("📤 שולח תשובה למשתמש...")
        await update.message.reply_text(reply_text)
        logging.info("📨 תשובה נשלחה למשתמש")

        # שלב 5: חילוץ מידע אישי מהודעת המשתמש
        identity_fields = {}
        extract_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model": ""}
        try:
            logging.info("🔍 מחלץ מידע אישי מהודעת המשתמש...")
            identity_fields, extract_usage = extract_user_profile_fields(user_msg)
            logging.info(f"מידע אישי שחולץ: {identity_fields!r}")
            if identity_fields:
                logging.info("👤 מעדכן פרופיל משתמש בגיליון...")
                update_user_profile(chat_id, identity_fields)
                logging.info("✅ הפרופיל עודכן בהצלחה")
            else:
                logging.info("ℹ️ לא נמצא מידע אישי לעדכון")
        except Exception as profile_error:
            logging.error(f"⚠️ שגיאה בעדכון פרופיל משתמש: {profile_error}")
            handle_non_critical_error(profile_error, chat_id, user_msg, "שגיאה בעדכון פרופיל משתמש")

        # שלב 6: חישוב עלויות
        logging.info("💰 מחשב עלויות...")
        main_usage = (main_prompt, main_completion, main_total, "", main_model)
        summary_usage = ("", sum_prompt, sum_completion, sum_total, sum_model)
        total_tokens, cost_usd, cost_ils = calculate_total_cost(main_usage, summary_usage, extract_usage)
        logging.info(f"💸 עלות כוללת: ${cost_usd} (₪{cost_ils}), טוקנים: {total_tokens}")

        # שלב 7: עדכון היסטוריה ושמירת נתונים
        try:
            logging.info("💾 מעדכן היסטוריית שיחה...")
            update_chat_history(chat_id, user_msg, reply_summary)
            logging.info("✅ היסטוריית שיחה עודכנה")

            logging.info("💾 שומר נתוני שיחה בגיליון...")
            log_to_sheets(
                message_id, chat_id, user_msg, reply_text, reply_summary,
                main_usage, summary_usage, extract_usage,
                total_tokens, cost_usd, cost_ils
            )
            logging.info("✅ נתוני שיחה נשמרו בגיליון")

            logging.info("💾 שומר לוג מפורט לקובץ...")
            log_payload.update({
                "user_summary": user_summary,
                "identity_fields": identity_fields,
                "gpt_reply": reply_text,
                "summary_saved": reply_summary,
                "tokens": {
                    "main_prompt": main_prompt,
                    "main_completion": main_completion,
                    "main_total": main_total,
                    "summary_prompt": sum_prompt,
                    "summary_completion": sum_completion,
                    "summary_total": sum_total,
                    "extract_prompt": extract_usage["prompt_tokens"],
                    "extract_completion": extract_usage["completion_tokens"],
                    "extract_total": extract_usage["total_tokens"],
                    "total_all": total_tokens,
                    "cost_usd": cost_usd,
                    "cost_ils": cost_ils
                }
            })
            log_event_to_file(log_payload)
            logging.info("✅ לוג מפורט נשמר לקובץ")
        except Exception as logging_error:
            logging.error(f"⚠️ שגיאה בשמירת לוגים/היסטוריה: {logging_error}")
            handle_non_critical_error(logging_error, chat_id, user_msg, "שגיאה בשמירת לוגים")

        # שלב 8: סיום תהליך
        total_time = (datetime.now() - datetime.fromisoformat(log_payload['timestamp_start'])).total_seconds()
        logging.info(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")
    except Exception as critical_error:
        logging.error(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
        await handle_critical_error(critical_error, chat_id, user_msg, update)

    logging.info("---- סיום טיפול בהודעה ----")

def main():
    logging.info("========== אתחול הבוט ==========")
    print("🤖 הבוט מתחיל לרוץ... (ראה גם קובץ bot.log)")
    # שליחת התראה על אתחול
    try:
        logging.info("📢 שולח התראת התחלה לאדמין...")
        send_startup_notification()
        logging.info("✅ התראת התחלה נשלחה")
    except Exception as ex:
        logging.error(f"⚠️ שגיאה בשליחת התראת התחלה: {ex}")

    # יצירת הבוט והפעלתו
    try:
        logging.info("📡 מתחבר ל-Telegram...")
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logging.info("✅ חיבור ל-Telegram הושלם")
    except Exception as ex:
        logging.critical(f"❌ שגיאה ביצירת האפליקציה: {ex}")
        raise

    # חיבור ל-Google Sheets
    try:
        logging.info("🔗 מתחבר ל-Google Sheets...")
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
        sheet = gspread.authorize(creds).open_by_key("1qt5kEPu_YJcbpQNaMdz60r1JTSx9Po89yOIfyV80Q-c").worksheet("גיליון1")
        app.bot_data["sheet"] = sheet
        logging.info("✅ חיבור ל-Google Sheets בוצע בהצלחה")
    except Exception as ex:
        logging.critical(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        raise

    logging.info("🚦 הבוט מוכן ומחכה להודעות! (Ctrl+C לעצירה)")
    print("✅ הבוט פועל! מחכה להודעות...")
    print("=" * 50)
    try:
        app.run_polling()
        logging.info("🛑 הבוט הופסק (run_polling הסתיים)")
    except Exception as ex:
        logging.critical(f"❌ שגיאה בהרצת loop של הבוט: {ex}")
        raise

if __name__ == "__main__":
    main()
