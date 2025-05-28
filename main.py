"""
🤖 הבוט הראשי - קובץ מנהל שמתאם בין כל המחלקות
זה כמו המנכ"ל של החברה - רואה את התמונה הכללית ומתאם בין המחלקות
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ייבוא המחלקות השונות
from config import TELEGRAM_BOT_TOKEN, SYSTEM_PROMPT, config
from gpt_handler import get_main_response, summarize_bot_reply, extract_user_profile_fields, calculate_total_cost
from sheets_handler import get_user_summary, update_user_profile, log_to_sheets
from notifications import send_startup_notification, handle_critical_error, handle_non_critical_error
from utils import log_event_to_file, update_chat_history, get_chat_history_messages

# הגדרת לוגים
logging.basicConfig(level=logging.INFO)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🎯 הפונקציה המרכזית שמטפלת בכל הודעה
    זה כמו המפה של התרחיש ב-Make או Zapier
    """
    # שלב 1: איסוף מידע בסיסי
    log_payload = {
        "chat_id": update.message.chat_id,
        "message_id": update.message.message_id,
        "timestamp_start": datetime.now().isoformat()
    }

    user_msg = update.message.text
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    log_payload["user_msg"] = user_msg

    from sheets_handler import check_user_access, register_user

    # בדיקת מצב המשתמש מול הטבלה
    exists, code, approved = check_user_access(context.bot_data["sheet"], chat_id)

    # אם המשתמש לא רשום – נבדוק אם ההודעה שלו היא קוד גישה
    if not exists:
        if register_user(context.bot_data["sheet"], chat_id, user_msg):
            await update.message.reply_text("✅ קוד אושר. עכשיו שלח 'מאשר' כדי להמשיך 🙏")
        else:
            await update.message.reply_text("🔒 לא זיהיתי את הקוד. נסה שוב או בקש קוד חדש.")
        return

    # אם הוא רשום אבל עדיין לא אישר
    if not approved:
        if user_msg.strip().lower() == "מאשר":
            approve_user(context.bot_data["sheet"], chat_id)
            await update.message.reply_text("מעולה, קיבלת גישה מלאה ✅ דבר אליי.")
        else:
            await update.message.reply_text("📜 לפני שנתחיל, חשוב שתאשר שאתה לוקח אחריות על השימוש בצ׳אט הזה.\n\nשלח 'מאשר' כדי להמשיך 🙏")
        return

    
    logging.info(f"📨 התקבלה הודעה מ-{chat_id}: {user_msg}")

    try:
        # שלב 2: הכנת ההודעה ל-GPT
        user_summary = get_user_summary(chat_id)
        history_messages = get_chat_history_messages(chat_id)
        
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if user_summary:
            full_messages.append({
                "role": "system", 
                "content": f"מידע על המשתמש: {user_summary}"
            })
        
        full_messages.extend(history_messages)
        full_messages.append({"role": "user", "content": user_msg})
        
        # שלב 3: קבלת תשובה מ-GPT הראשי
        print("🤖 שולח ל-GPT ראשי...")
        main_response = get_main_response(full_messages)
        reply_text, main_prompt, main_completion, main_total, main_model = main_response
        
        # שלב 4: קיצור התשובה
        print("✂️ מקצר את התשובה...")
        summary_response = summarize_bot_reply(reply_text)
        reply_summary, sum_prompt, sum_completion, sum_total, sum_model = summary_response
        
        # שלב 5: שליחת תשובה מהירה למשתמש
        await update.message.reply_text(reply_text)
        print(f"✅ תשובה נשלחה למשתמש תוך {(datetime.now() - datetime.fromisoformat(log_payload['timestamp_start'])).total_seconds():.2f} שניות")
        
        # שלב 6: עדכונים ברקע (המשתמש כבר קיבל תשובה)
        print("🔄 מתחיל עדכונים ברקע...")
        
        # חילוץ מידע אישי
        identity_fields = {}
        extract_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model": ""}
        
        try:
            print("🔍 מחלץ מידע אישי...")
            identity_fields, extract_usage = extract_user_profile_fields(user_msg)
            
            if identity_fields:
                print("👤 מעדכן פרופיל משתמש...")
                update_user_profile(chat_id, identity_fields)
                print("✅ פרופיל עודכן")
        except Exception as profile_error:
            handle_non_critical_error(
                profile_error, chat_id, user_msg, 
                "שגיאה בעדכון פרופיל משתמש"
            )
        
        # שלב 7: חישוב עלויות
        print("💰 מחשב עלויות...")
        main_usage = (main_prompt, main_completion, main_total, "", main_model)
        summary_usage = ("", sum_prompt, sum_completion, sum_total, sum_model)
        
        total_tokens, cost_usd, cost_ils = calculate_total_cost(
            main_usage, summary_usage, extract_usage
        )
        
        print(f"💸 עלות כוללת: ${cost_usd} (₪{cost_ils}) | טוקנים: {total_tokens}")
        
        # שלב 8: שמירת נתונים
        try:
            print("💾 שומר נתונים...")
            # עדכון היסטוריה
            update_chat_history(chat_id, user_msg, reply_summary)
            
            # שמירה בגוגל שיטס
            log_to_sheets(
                message_id, chat_id, user_msg, reply_text, reply_summary,
                main_usage, summary_usage, extract_usage, 
                total_tokens, cost_usd, cost_ils
            )
            
            # שמירת לוג מפורט
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
            print("✅ כל הנתונים נשמרו")
            
        except Exception as logging_error:
            handle_non_critical_error(
                logging_error, chat_id, user_msg,
                "שגיאה בשמירת לוגים"
            )
        
        # שלב 9: סיכום
        total_time = (datetime.now() - datetime.fromisoformat(log_payload['timestamp_start'])).total_seconds()
        print(f"🏁 סה״כ זמן עיבוד: {total_time:.2f} שניות")
        print("=" * 50)

    except Exception as critical_error:
      # שגיאה קריטית - המשתמש לא קיבל תשובה
      await handle_critical_error(critical_error, chat_id, user_msg, update)



def main():
    """
    🚀 הפונקציה הראשית שמפעילה את הבוט
    """
    print("🤖 הבוט מתחיל לרוץ...")
    
    # שליחת התראה לאדמין שהבוט התחיל
    try:
        send_startup_notification()
    except:
        print("⚠️ שגיאה בשליחת התראת התחלה (לא קריטי)")
    
    # יצירת הבוט והפעלתו
    print("📡 מתחבר לטלגרם...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ הבוט פועל! מחכה להודעות...")
    print("📍 לעצירה: Ctrl+C")
    print("=" * 50)

    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(config["SERVICE_ACCOUNT_DICT"], scope)
    sheet = gspread.authorize(creds).open_by_key("1qt5kEPu_YJcbpQNaMdz60r1JTSx9Po89yOIfyV80Q-c").worksheet("גיליון1")

    app.bot_data["sheet"] = sheet  # ⬅️ זה מכניס את הגיליון לשימוש בתוך context

    
    app.run_polling()


if __name__ == "__main__":
    main()
