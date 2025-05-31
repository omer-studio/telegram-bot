import os
import json
from telegram.ext import Updater, CommandHandler

# הגדרת קבועים מהסביבה
ADMIN_BOT_TELEGRAM_TOKEN = os.getenv("ADMIN_BOT_TELEGRAM_TOKEN")
ADMIN_NOTIFICATION_CHAT_ID = int(os.getenv("ADMIN_NOTIFICATION_CHAT_ID"))

# דקורטור לבדוק שהפקודה נשלחת רק ממך
def only_admin(func):
    def wrapper(update, context):
        if update.effective_chat.id != ADMIN_NOTIFICATION_CHAT_ID:
            update.message.reply_text("אין לך הרשאה לפקודה הזאת.")
            return
        return func(update, context)
    return wrapper

# פקודה למחיקת היסטוריה של משתמש מסוים
@only_admin
def clear_history(update, context):
    if len(context.args) == 0:
        update.message.reply_text("נא להוסיף chat_id. לדוג': /clear_history 123456789")
        return

    user_chat_id = str(context.args[0])
    history_path = "/data/chat_history.json"
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                update.message.reply_text("שגיאה בקריאת קובץ ההיסטוריה.")
                return

        if user_chat_id in data:
            del data[user_chat_id]
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            update.message.reply_text(f"ההיסטוריה של {user_chat_id} נמחקה בהצלחה ✅")
        else:
            update.message.reply_text(f"לא נמצאה היסטוריה למשתמש {user_chat_id}")
    else:
        update.message.reply_text("קובץ ההיסטוריה לא נמצא.")

# פקודת בדיקה - שהבוט באוויר
@only_admin
def ping(update, context):
    update.message.reply_text("הבוט האדמיני עובד 🟢")

# פקודה להצגת כל המשתמשים לפי סדר פעילות אחרונה
@only_admin
def list_users(update, context):
    history_path = "/data/chat_history.json"
    if not os.path.exists(history_path):
        update.message.reply_text("קובץ ההיסטוריה לא נמצא.")
        return

    with open(history_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            update.message.reply_text("שגיאה בקריאת קובץ ההיסטוריה.")
            return

    if not data:
        update.message.reply_text("אין משתמשים פעילים כרגע.")
        return

    # בניית רשימת משתמשים לפי תאריך פעילות אחרונה
    users = []
    for chat_id, messages in data.items():
        if messages:
            last_msg = messages[-1]
            ts = last_msg.get("timestamp") or last_msg.get("time") or ""
            users.append((chat_id, ts))

    # למיין מהכי עדכני לישן
    users_sorted = sorted(users, key=lambda x: x[1], reverse=True)

    # בניית הודעה
    user_lines = [f"{i+1}. {u[0]} | {u[1]}" for i, u in enumerate(users_sorted)]
    msg = "רשימת משתמשים לפי פעילות אחרונה:\n\n" + "\n".join(user_lines)

    # הגבלת אורך טלגרם (4096 תווים) — חותך אם צריך
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n(נחתך)"

    update.message.reply_text(msg)

# פונקציה ראשית שמריצה את הבוט
def main():
    updater = Updater(token=ADMIN_BOT_TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # מוסיפים את הפקודות שרק האדמין רואה
    dp.add_handler(CommandHandler("clear_history", clear_history))
    dp.add_handler(CommandHandler("ping", ping))
    dp.add_handler(CommandHandler("list_users", list_users))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
