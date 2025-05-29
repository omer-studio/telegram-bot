"""
main.py — הבוט הראשי של הצ'אט

למה אנחנו עושים את זה?
=======================
אנחנו רוצים לדעת אם המשתמש נכנס בפעם הראשונה בחייו לצ'אט, ולכן:
1. בכל הודעה נכנסת, אנחנו קודם כל בודקים האם ה-chat_id של המשתמש קיים בעמודה הראשונה של גיליון 1 (access_codes).
2. אם לא מצאנו אותו שם, בודקים אם הוא קיים בעמודה הראשונה של גיליון user_states.
3. אם לא מצאנו אותו גם שם — זו הפעם הראשונה של המשתמש בצ'אט! נרשום אותו ב-user_states עם code_try=0 ונשלח לו הודעת קבלת פנים ("היי מלך!").
4. אם המשתמש כן קיים באחד הגיליונות, ממשיכים בתהליך הרגיל (בדיקת הרשאות, קוד גישה, אישור תנאים וכו').

כל לוגיקה של שליחת הודעות, ניהול משתמשים, שמירת היסטוריה, חישוב עלויות ועוד — הכל מתועד בלוג (לקובץ ולמסך) ובדוקומנטציה בראש כל פונקציה.
מטרת התיעוד היא שלא תצטרך להסביר שוב את ההיגיון — הכל כתוב בקוד.

"""

import logging
# משתיק את הלוגים של HTTP כדי שלא יראו את הטוקן
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)  # גם זה עוזר לעודפים
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from fastapi import FastAPI, Request
import uvicorn

app_fastapi = FastAPI()




# ייבוא המחלקות השונות
from config import TELEGRAM_BOT_TOKEN, SYSTEM_PROMPT, config
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
from gpt_handler import get_main_response, summarize_bot_reply, extract_user_profile_fields, calculate_total_cost
from sheets_handler import (
    get_user_summary, update_user_profile, log_to_sheets, check_user_access, register_user,
    approve_user, ensure_user_state_row
)
from notifications import send_startup_notification, handle_critical_error, handle_non_critical_error
from utils import log_event_to_file, update_chat_history, get_chat_history_messages

# הגדרת הלוגר — גם למסוף וגם לקובץ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    לוגיקת טיפול בכל הודעה נכנסת:
    --------------------------------
    1. בדיקה האם המשתמש פונה בפעם הראשונה (לא קיים לא בגיליון 1 ולא ב-user_states).
       אם כן — צורבים אותו ב-user_states (code_try=0), שולחים 'היי מלך!' ומסיימים טיפול.
    2. אם לא — ממשיכים בתהליך הרגיל (הרשאות, קוד, תנאים, היסטוריה, עלויות וכו').
    כל שלב מתועד בלוג וב-prinT.
    """

    logging.info("---- התחלת טיפול בהודעה ----")
    print("---- התחלת טיפול בהודעה ----")
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
        print(f"📩 התקבלה הודעה | chat_id={chat_id}, message_id={message_id}, תוכן={user_msg!r}")
    except Exception as ex:
        logging.error(f"❌ שגיאה בשליפת מידע מההודעה: {ex}")
        print(f"❌ שגיאה בשליפת מידע מההודעה: {ex}")
        await handle_critical_error(ex, None, None, update)
        return

    # שלב 1: בדיקת משתמש חדש (Onboarding)
    # -------------------------------------------------
    # למה? כי אנחנו רוצים לדעת אם זו פנייה ראשונה בחייו של המשתמש לצ'אט.
    # אם לא קיים לא בגיליון 1 ולא ב-user_states — נרשום אותו שם עם code_try=0.
    try:
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
              # שולח רצף הודעות וולקאם בפעם הראשונה והאחרונה כולל השהיה בינהם שייראה שבן אדם אנושי כתב את זה 
            await update.message.reply_text("היי מלך! 👑 אני רואה שזה שימוש ראשוני שלך...\nאיזה כיף! 🎉")
            await sleep(2)
            await update.message.reply_text("אתה תופתע לגלות איזה שימושי אני 😎\nאני יודע מה אתה חושב... בינה מלאכותית וזה...\nתן לי להפתיע אותך!! 🚀\n\nלפני שנתחיל בפעם הראשונה נצטרך כמה דברים 🧩")
            await sleep(3)
            await update.message.reply_text("בוא נתחיל במספר האישור שקיבלת 🔢\nמה מספר האישור שקיבלת?\n(תכתוב אותו נקי בלי מילים נוספות ✍️)")
            
            logging.info("📤 נשלחו הודועת וולקאם ראשונה ואחרונה'היי מלך' למשתמש חדש")
            print("📤 נשלחו הודעות וולקאם 'היי מלך' למשתמש חדש")
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

    # שלב 2: בדיקת משתמש וקוד גישה
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

    # שלב 3: טיפול ברישום משתמש חדש (הכנסת קוד)
    if not exists:
        logging.info(f"👤 משתמש לא קיים, בודק קוד גישה: {user_msg!r}")
        print(f"👤 משתמש לא קיים, בודק קוד גישה: {user_msg!r}")
        try:
            if register_user(context.bot_data["sheet"], chat_id, user_msg):
                logging.info(f"✅ קוד גישה אושר למשתמש {chat_id}")
                print(f"✅ קוד גישה אושר למשתמש {chat_id}")
                await update.message.reply_text("✅ קוד אושר. עכשיו שלח 'מאשר' כדי להמשיך 🙏")
                logging.info("📤 נשלחה הודעת אישור קוד למשתמש")
                print("📤 נשלחה הודעת אישור קוד למשתמש")
            else:
                logging.warning(f"❌ קוד גישה לא תקין עבור {chat_id}")
                print(f"❌ קוד גישה לא תקין עבור {chat_id}")
                await update.message.reply_text("🔒 לא זיהיתי את הקוד. נסה שוב או בקש קוד חדש.")
                logging.info("📤 נשלחה הודעת קוד לא תקין למשתמש")
                print("📤 נשלחה הודעת קוד לא תקין למשתמש")
        except Exception as ex:
            logging.error(f"❌ שגיאה בתהליך רישום משתמש חדש: {ex}")
            print(f"❌ שגיאה בתהליך רישום משתמש חדש: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
        logging.info("---- סיום טיפול בהודעה (משתמש לא קיים) ----")
        print("---- סיום טיפול בהודעה (משתמש לא קיים) ----")
        return

    # שלב 4: טיפול באישור תנאים
    if not approved:
        logging.info(f"📝 משתמש {chat_id} קיים אך לא מאושר, תוכן ההודעה: {user_msg!r}")
        print(f"📝 משתמש {chat_id} קיים אך לא מאושר, תוכן ההודעה: {user_msg!r}")
        try:
            if user_msg.strip().lower() == "מאשר":
                approve_user(context.bot_data["sheet"], chat_id)
                logging.info(f"🙌 משתמש {chat_id} אישר תנאים בהצלחה")
                print(f"🙌 משתמש {chat_id} אישר תנאים בהצלחה")
                await update.message.reply_text("מעולה, קיבלת גישה מלאה ✅ דבר אליי.")
                logging.info("📤 נשלחה הודעת גישה מלאה למשתמש")
                print("📤 נשלחה הודעת גישה מלאה למשתמש")
            else:
                await update.message.reply_text("📜 לפני שנתחיל, חשוב שתאשר שאתה לוקח אחריות על השימוש בצ׳אט הזה.\n\nשלח 'מאשר' כדי להמשיך.")
                logging.info("📤 נשלחה תזכורת לאישור תנאים למשתמש")
                print("📤 נשלחה תזכורת לאישור תנאים למשתמש")
        except Exception as ex:
            logging.error(f"❌ שגיאה בתהליך אישור תנאים: {ex}")
            print(f"❌ שגיאה בתהליך אישור תנאים: {ex}")
            await handle_critical_error(ex, chat_id, user_msg, update)
        logging.info("---- סיום טיפול בהודעה (משתמש לא מאושר) ----")
        print("---- סיום טיפול בהודעה (משתמש לא מאושר) ----")
        return

    # שלב 5: המשך טיפול במשתמש מאושר (מענה, לוגים וכו')
    logging.info("👨‍💻 משתמש מאושר, מתחיל תהליך מענה...")
    print("👨‍💻 משתמש מאושר, מתחיל תהליך מענה...")
    try:
        # שלב 1: הכנת קונטקסט
        logging.info("📚 שולף סיכום משתמש מהגיליון...")
        print("📚 שולף סיכום משתמש מהגיליון...")
        user_summary = get_user_summary(chat_id)
        logging.info(f"סיכום משתמש: {user_summary!r}")
        print(f"סיכום משתמש: {user_summary!r}")

        logging.info("📚 שולף היסטוריית שיחה...")
        print("📚 שולף היסטוריית שיחה...")
        history_messages = get_chat_history_messages(chat_id)
        logging.info(f"היסטוריית שיחה: {history_messages!r}")
        print(f"היסטוריית שיחה: {history_messages!r}")

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if user_summary:
            full_messages.append({"role": "system", "content": f"מידע על המשתמש: {user_summary}"})
        full_messages.extend(history_messages)
        full_messages.append({"role": "user", "content": user_msg})

        # שלב 2: שליחה ל-GPT
        logging.info("🤖 שולח ל-GPT הראשי...")
        print("🤖 שולח ל-GPT הראשי...")
        main_response = get_main_response(full_messages)
        reply_text, main_prompt, main_completion, main_total, main_model = main_response
        logging.info(f"✅ התקבלה תשובה מה-GPT. אורך תשובה: {len(reply_text)} תווים")
        print(f"✅ התקבלה תשובה מה-GPT. אורך תשובה: {len(reply_text)} תווים")

        # שלב 3: קיצור תשובה
        logging.info("✂️ מקצר את התשובה...")
        print("✂️ מקצר את התשובה...")
        summary_response = summarize_bot_reply(reply_text)
        reply_summary, sum_prompt, sum_completion, sum_total, sum_model = summary_response
        logging.info(f"סיכום תשובה: {reply_summary!r}")
        print(f"סיכום תשובה: {reply_summary!r}")

        # שלב 4: שליחת תשובה למשתמש
        logging.info("📤 שולח תשובה למשתמש...")
        print("📤 שולח תשובה למשתמש...")
        await update.message.reply_text(reply_text)
        logging.info("📨 תשובה נשלחה למשתמש")
        print("📨 תשובה נשלחה למשתמש")

        # שלב 5: חילוץ מידע אישי מהודעת המשתמש
        identity_fields = {}
        extract_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model": ""}
        try:
            logging.info("🔍 מחלץ מידע אישי מהודעת המשתמש...")
            print("🔍 מחלץ מידע אישי מהודעת המשתמש...")
            identity_fields, extract_usage = extract_user_profile_fields(user_msg)
            logging.info(f"מידע אישי שחולץ: {identity_fields!r}")
            print(f"מידע אישי שחולץ: {identity_fields!r}")
            if identity_fields:
                logging.info("👤 מעדכן פרופיל משתמש בגיליון...")
                print("👤 מעדכן פרופיל משתמש בגיליון...")
                update_user_profile(chat_id, identity_fields)
                logging.info("✅ הפרופיל עודכן בהצלחה")
                print("✅ הפרופיל עודכן בהצלחה")
            else:
                logging.info("ℹ️ לא נמצא מידע אישי לעדכון")
                print("ℹ️ לא נמצא מידע אישי לעדכון")
        except Exception as profile_error:
            logging.error(f"⚠️ שגיאה בעדכון פרופיל משתמש: {profile_error}")
            print(f"⚠️ שגיאה בעדכון פרופיל משתמש: {profile_error}")
            handle_non_critical_error(profile_error, chat_id, user_msg, "שגיאה בעדכון פרופיל משתמש")

        # שלב 6: חישוב עלויות
        logging.info("💰 מחשב עלויות...")
        print("💰 מחשב עלויות...")
        main_usage = (main_prompt, main_completion, main_total, "", main_model)
        summary_usage = ("", sum_prompt, sum_completion, sum_total, sum_model)
        total_tokens, cost_usd, cost_ils = calculate_total_cost(main_usage, summary_usage, extract_usage)
        logging.info(f"💸 עלות כוללת: ${cost_usd} (₪{cost_ils}), טוקנים: {total_tokens}")
        print(f"💸 עלות כוללת: ${cost_usd} (₪{cost_ils}), טוקנים: {total_tokens}")

        # שלב 7: עדכון היסטוריה ושמירת נתונים
        try:
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
                total_tokens, cost_usd, cost_ils
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
            print("✅ לוג מפורט נשמר לקובץ")
        except Exception as logging_error:
            logging.error(f"⚠️ שגיאה בשמירת לוגים/היסטוריה: {logging_error}")
            print(f"⚠️ שגיאה בשמירת לוגים/היסטוריה: {logging_error}")
            handle_non_critical_error(logging_error, chat_id, user_msg, "שגיאה בשמירת לוגים")

        # שלב 8: סיום תהליך
        total_time = (datetime.now() - datetime.fromisoformat(log_payload['timestamp_start'])).total_seconds()
        logging.info(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")
        print(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")
    except Exception as critical_error:
        logging.error(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
        print(f"❌ שגיאה קריטית במהלך טיפול בהודעה: {critical_error}")
        await handle_critical_error(critical_error, chat_id, user_msg, update)

    logging.info("---- סיום טיפול בהודעה ----")
    print("---- סיום טיפול בהודעה ----")

@app_fastapi.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await handle_message(update, ContextTypes.DEFAULT_TYPE(bot=app.bot))
        return {"ok": True}
    except Exception as ex:
        logging.error(f"❌ שגיאה ב-webhook: {ex}")
        return {"error": str(ex)}


def main():
    """
    אתחול הבוט: חיבור ל-Telegram ול-Google Sheets, הגדרת handlers, ניהול לוגים.
    """
    logging.info("========== אתחול הבוט ==========")
    print("========== אתחול הבוט ==========")
    print("🤖 הבוט מתחיל לרוץ... (ראה גם קובץ bot.log)")
    # שליחת התראה על אתחול
    try:
        logging.info("📢 שולח התראת התחלה לאדמין...")
        print("📢 שולח התראת התחלה לאדמין...")
        send_startup_notification()
        logging.info("✅ התראת התחלה נשלחה")
        print("✅ התראת התחלה נשלחה")
    except Exception as ex:
        logging.error(f"⚠️ שגיאה בשליחת התראת התחלה: {ex}")
        print(f"⚠️ שגיאה בשליחת התראת התחלה: {ex}")

    # יצירת הבוט והפעלתו
    try:
        logging.info("📡 מתחבר ל-Telegram...")
        print("📡 מתחבר ל-Telegram...")
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logging.info("✅ חיבור ל-Telegram הושלם")
        print("✅ חיבור ל-Telegram הושלם")
    except Exception as ex:
        logging.critical(f"❌ שגיאה ביצירת האפליקציה: {ex}")
        print(f"❌ שגיאה ביצירת האפליקציה: {ex}")
        raise

    # חיבור ל-Google Sheets (ודא שמחזיר גם sheet_states!)
    try:
        logging.info("🔗 מתחבר ל-Google Sheets...")
        print("🔗 מתחבר ל-Google Sheets...")
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
        sheet = gspread.authorize(creds).open_by_key("1qt5kEPu_YJcbpQNaMdz60r1JTSx9Po89yOIfyV80Q-c").worksheet("גיליון1")
        sheet_states = gspread.authorize(creds).open_by_key("1qt5kEPu_YJcbpQNaMdz60r1JTSx9Po89yOIfyV80Q-c").worksheet("user_states")
        app.bot_data["sheet"] = sheet
        app.bot_data["sheet_states"] = sheet_states
        logging.info("✅ חיבור ל-Google Sheets בוצע בהצלחה")
        print("✅ חיבור ל-Google Sheets בוצע בהצלחה")
    except Exception as ex:
        logging.critical(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        print(f"❌ שגיאה בהתחברות ל-Google Sheets: {ex}")
        raise

    logging.info("🚦 הבוט מוכן ומחכה להודעות! (Ctrl+C לעצירה)")
    print("✅ הבוט פועל! מחכה להודעות...")
    print("=" * 50)

if __name__ == "__main__":
    main()
    uvicorn.run(app_fastapi, host="0.0.0.0", port=10000)
