# secret_commands.py
# קובץ זה אחראי על קודים סודיים שמוחקים מידע למשתמשים
# כל קוד סודי מבצע פעולה אחרת (למשל: מחיקת היסטוריה, מחיקת שורה מהגיליון)
# כאן אפשר להוסיף בעתיד עוד קודים סודיים בקלות
# כל פעולה נרשמת גם ללוג וגם בפרינט, וגם נשלחת הודעה למשתמש

import os
import json
from sheets_handler import delete_row_by_chat_id
from utils import log_event_to_file  # ודא שהפונקציה קיימת! (יש כמעט בוודאות)

# כאן שמים את כל הקודים הסודיים והשם של הפעולה (לפי מה שנבחר)
SECRET_CODES = {
    "#487chaCha2025": "clear_history",    # מוחק היסטוריית שיחה
    "#512SheetBooM": "clear_sheets",      # מוחק מידע מהגיליונות
    "#734TotalZap": "clear_all"           # מוחק הכל (היסטוריה + גיליונות)
}

def handle_secret_command(chat_id, text):
    """
    הפונקציה בודקת אם הודעה היא קוד סודי
    אם כן — מפעילה את הפעולה המתאימה, רושמת ללוג, ומחזירה הודעה למשתמש
    אם לא — מחזירה False, None (שום דבר לא קרה)
    """
    action = SECRET_CODES.get(text.strip())
    if not action:
        return False, None

    # לכל פעולה יש טיפול משלה
    if action == "clear_history":
        cleared = clear_chat_history(chat_id)
        msg = "🧹 כל ההיסטוריה שלך נמחקה! (chat_history)" if cleared else "🤷‍♂️ לא נמצאה היסטוריה למחיקה."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_history — {'נמחק' if cleared else 'לא נמצא'}")
        log_event_to_file("secret_command", {
            "chat_id": chat_id,
            "action": "clear_history",
            "result": cleared
        })
        return True, msg

    if action == "clear_sheets":
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "🗑️ כל הנתונים שלך נמחקו מהגיליונות!" if (deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא מידע למחיקה בגיליונות."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_sheets — sheet: {deleted_sheet}, state: {deleted_state}")
        log_event_to_file("secret_command", {
            "chat_id": chat_id,
            "action": "clear_sheets",
            "deleted_sheet": deleted_sheet,
            "deleted_state": deleted_state
        })
        return True, msg

    if action == "clear_all":
        cleared = clear_chat_history(chat_id)
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "💣 הכל נמחק! (היסטוריה + גיליונות)" if (cleared or deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא שום מידע למחיקה."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_all — history: {cleared}, sheet: {deleted_sheet}, state: {deleted_state}")
        log_event_to_file("secret_command", {
            "chat_id": chat_id,
            "action": "clear_all",
            "cleared_history": cleared,
            "deleted_sheet": deleted_sheet,
            "deleted_state": deleted_state
        })
        return True, msg

    # אם מסיבה כלשהי לא מצאנו פעולה מתאימה
    return False, None

def clear_chat_history(chat_id):
    """
    מוחק את כל ההיסטוריה (chat_history.json) של אותו chat_id בלבד
    מחזיר True אם נמחק, אחרת False
    """
    path = "/data/chat_history.json"
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if str(chat_id) in data:
            data.pop(str(chat_id))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        return False
    except Exception as e:
        print(f"[ERROR-clear_chat_history] {e}")
        return False

def clear_from_sheets(chat_id):
    """
    מוחק את השורה של המשתמש בגיליונות (access_codes בגיליון1, user_states).
    מחזיר tuple: (האם נמחק בגיליון1, האם נמחק ב-user_states)
    """
    deleted_sheet = delete_row_by_chat_id(sheet_name="גיליון1", chat_id=chat_id)
    deleted_state = delete_row_by_chat_id(sheet_name="user_states", chat_id=chat_id)
    return deleted_sheet, deleted_state

# דוגמה להוספת קוד סודי חדש:
# פשוט הוסף ל-SECRET_CODES עוד שורה, ותכתוב פונקציה חדשה עם אותו מבנה
# למשל:
# SECRET_CODES["#999SuperErase"] = "super_erase"
# ואז תוסיף:
# def super_erase(chat_id):
#     ... פה קוד למחיקה מיוחדת ...
