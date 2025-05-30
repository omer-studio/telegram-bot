"""
פונקציות עזר כלליות - לוגים, היסטוריה וכלים נוספים
"""
import json
import os
from datetime import datetime
from config import LOG_FILE_PATH, LOG_LIMIT


def log_event_to_file(log_data):
    """
    רושם אירועים לקובץ הלוגים הראשי
    """
    try:
        file_path = "/data/bot_trace_log.jsonl"
        log_data["timestamp_end"] = datetime.now().isoformat()

        # קריאת לוגים קיימים
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        # הוספת לוג חדש
        lines.append(json.dumps(log_data, ensure_ascii=False, indent=2))

        # שמירה על מגבלת הלוגים (למשל 200)
        lines = lines[-200:]

        # שמירה חזרה לקובץ
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"📝 לוג נשמר: {file_path}")

    except Exception as e:
        print(f"❌ שגיאה בשמירת לוג: {e}")



def update_chat_history(chat_id, user_msg, bot_summary):
    """
    מעדכן את היסטוריית השיחה של המשתמש
    """
    try:
        file_path = "/data/chat_history.json"

        # טעינת היסטוריה קיימת
        try:
            with open(file_path, encoding="utf-8") as f:
                history_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history_data = {}

        chat_id = str(chat_id)

        # יצירת היסטוריה חדשה למשתמש אם לא קיימת
        if chat_id not in history_data:
            history_data[chat_id] = {"am_context": "", "history": []}

        # הוספת האירוע החדש
        history_data[chat_id]["history"].append({
            "user": user_msg,
            "bot": bot_summary,
            "timestamp": datetime.now().isoformat()
        })

        # שמירה על 5 הודעות אחרונות בלבד
        history_data[chat_id]["history"] = history_data[chat_id]["history"][-5:]

        # שמירה חזרה לקובץ
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        print(f"📚 היסטוריה עודכנה למשתמש {chat_id}")

    except Exception as e:
        print(f"❌ שגיאה בעדכון היסטוריה: {e}")



def get_chat_history_messages(chat_id):
    """
    מחזיר את היסטוריית השיחה בפורמט המתאים ל-GPT
    """
    try:
        with open("chat_history.json", encoding="utf-8") as f:
            history_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    chat_id = str(chat_id)
    
    if chat_id not in history_data or "history" not in history_data[chat_id]:
        return []
    
    messages = []
    for entry in history_data[chat_id]["history"]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["bot"]})
    
    print(f"📖 נטענו {len(messages)//2} הודעות מההיסטוריה של {chat_id}")
    return messages


def get_user_stats(chat_id):
    """
    מחזיר סטטיסטיקות על המשתמש
    """
    try:
        with open("chat_history.json", encoding="utf-8") as f:
            history_data = json.load(f)
        
        chat_id = str(chat_id)
        if chat_id not in history_data:
            return {"total_messages": 0, "first_contact": None, "last_contact": None}
        
        history = history_data[chat_id]["history"]
        
        return {
            "total_messages": len(history),
            "first_contact": history[0]["timestamp"] if history else None,
            "last_contact": history[-1]["timestamp"] if history else None
        }
        
    except Exception as e:
        print(f"❌ שגיאה בקבלת סטטיסטיקות: {e}")
        return {"total_messages": 0, "first_contact": None, "last_contact": None}


def clean_old_logs():
    """
    מנקה לוגים ישנים (ניתן לקרוא מעת לעת)
    """
    try:
        files_to_clean = ["bot_trace_log.jsonl", "bot_errors.jsonl"]
        
        for file_name in files_to_clean:
            if os.path.exists(file_name):
                # שמירה על 1000 שורות אחרונות בלבד
                with open(file_name, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                if len(lines) > 1000:
                    with open(file_name, "w", encoding="utf-8") as f:
                        f.writelines(lines[-1000:])
                    print(f"🧽 נוקה קובץ: {file_name}")
        
    except Exception as e:
        print(f"❌ שגיאה בניקוי לוגים: {e}")


def get_system_health():
    """
    בדיקת תקינות המערכת
    """
    health = {
        "config_loaded": False,
        "sheets_connected": False,
        "openai_connected": False,
        "log_files_writable": False
    }
    
    try:
        # בדיקת קונפיגורציה
        from config import config
        health["config_loaded"] = True
        
        # בדיקת חיבור לשיטס
        from sheets_handler import sheet_users, sheet_log
        health["sheets_connected"] = True
        
        # בדיקת OpenAI
        from config import client
        health["openai_connected"] = True
        
        # בדיקת כתיבה לקבצים
        test_log = {"test": "health_check", "timestamp": datetime.now().isoformat()}
        with open("health_test.json", "w") as f:
            json.dump(test_log, f)
        os.remove("health_test.json")
        health["log_files_writable"] = True
        
    except Exception as e:
        print(f"⚕️ בעיה בבדיקת תקינות: {e}")
    
    return health


def format_error_message(error, context=""):
    """
    מעצב הודעת שגיאה בצורה ברורה
    """
    import traceback
    
    error_msg = f"🚨 שגיאה"
    if context:
        error_msg += f" ב{context}"
    
    error_msg += f":\n"
    error_msg += f"📍 סוג: {type(error).__name__}\n"
    error_msg += f"💬 הודעה: {str(error)}\n"
    error_msg += f"⏰ זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
    
    # מידע טכני מפורט
    tb = traceback.format_exc()
    if len(tb) > 500:
        tb = tb[:500] + "... (קוצר)"
    
    error_msg += f"🔧 פרטים טכניים:\n{tb}"
    
    return error_msg
