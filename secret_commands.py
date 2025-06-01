import os
import json
from sheets_handler import delete_row_by_chat_id

# הגדר כאן את הקודים הסודיים והפונקציות שלהם
SECRET_CODES = {
    "#487chaCha2025": "clear_history",
    "#512SheetBooM": "clear_sheets",
    "#734TotalZap": "clear_all"
}

def handle_secret_command(chat_id, text):
    """
    אם ההודעה היא קוד סודי - מפעיל את הפקודה המתאימה.
    מחזיר: (בוצעה פעולה, הודעת תגובה)
    """
    action = SECRET_CODES.get(text.strip())
    if not action:
        return False, None

    if action == "clear_history":
        cleared = clear_chat_history(chat_id)
        msg = "🧹 כל ההיסטוריה שלך נמחקה! (chat_history)"
        if not cleared:
            msg = "🤷‍♂️ לא נמצאה היסטוריה למחיקה."
        return True, msg

    if action == "clear_sheets":
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        if deleted_sheet or deleted_state:
            msg = "🗑️ כל הנתונים שלך נמחקו מהגיליונות!"
        else:
            msg = "🤷‍♂️ לא נמצא מידע למחיקה בגיליונות."
        return True, msg

    if action == "clear_all":
        cleared = clear_chat_history(chat_id)
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        if cleared or deleted_sheet or deleted_state:
            msg = "💣 הכל נמחק! (היסטוריה + גיליונות)"
        else:
            msg = "🤷‍♂️ לא נמצא שום מידע למחיקה."
        return True, msg

    return False, None

def clear_chat_history(chat_id):
    """ מוחק את כל ההיסטוריה (chat_history.json) של אותו chat_id בלבד """
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
        return False

def clear_from_sheets(chat_id):
    """
    מוחק את השורה של המשתמש בגיליונות (access_codes בגיליון1, user_states).
    מחזיר (האם נמחק בגיליון1, האם נמחק ב-user_states)
    """
    deleted_sheet = delete_row_by_chat_id(sheet_name="גיליון1", chat_id=chat_id)
    deleted_state = delete_row_by_chat_id(sheet_name="user_states", chat_id=chat_id)
    return deleted_sheet, deleted_state
