"""
utils.py
--------
כלים שימושיים לכל חלקי הבוט: רישום אירועים, ניהול היסטוריה, סטטיסטיקות, בדיקות תקינות, פקודות סודיות.
הרציונל: כלים שימושיים לכל חלקי הבוט, מופרדים מהלוגיקה הראשית.
"""
import json
import os
from datetime import datetime
from config import BOT_TRACE_LOG_PATH, CHAT_HISTORY_PATH, gpt_log_path, BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME, DATA_DIR, MAX_LOG_LINES_TO_KEEP, MAX_OLD_LOG_LINES, MAX_CHAT_HISTORY_MESSAGES, MAX_TRACEBACK_LENGTH, config


def log_event_to_file(log_data: dict) -> None:
    """
    רושם אירועים לקובץ הלוגים הראשי (bot_trace_log.jsonl)
    קלט: log_data (dict)
    פלט: אין (שומר לקובץ)
    """
    try:
        file_path = BOT_TRACE_LOG_PATH
        log_data["timestamp_end"] = datetime.now().isoformat()

        # קריאת לוגים קיימים
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        # הוספת לוג חדש
        lines.append(json.dumps(log_data, ensure_ascii=False))

        # שמירה על מגבלת הלוגים
        lines = lines[-MAX_LOG_LINES_TO_KEEP:]

        # שמירה חזרה לקובץ
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"📝 לוג נשמר: {file_path}")

    except Exception as e:
        import traceback
        print(f"❌ שגיאה בשמירת לוג: {e}")
        print(traceback.format_exc())



def update_chat_history(chat_id, user_msg, bot_summary): # מעדכן את היסטוריית השיחה של המשתמש בקובץ JSON ייעודי
    """
    מעדכן את היסטוריית השיחה של המשתמש בקובץ JSON ייעודי.
    קלט: chat_id (str/int), user_msg (str), bot_summary (str)
    פלט: אין (שומר בקובץ)
    """
    try:
        file_path = CHAT_HISTORY_PATH

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
        if (user_msg and user_msg.strip()) or (bot_summary and bot_summary.strip()):
            history_data[chat_id]["history"].append({
                "user": user_msg,
                "bot": bot_summary,
                "timestamp": datetime.now().isoformat()
            })

        # שמירה על איקס הודעות אחרונות בלבד
        history_data[chat_id]["history"] = history_data[chat_id]["history"][-MAX_CHAT_HISTORY_MESSAGES:]

        # שמירה חזרה לקובץ
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        print(f"📚 היסטוריה עודכנה למשתמש {chat_id}")

    except Exception as e:
        print(f"❌ שגיאה בעדכון היסטוריה: {e}")



def get_chat_history_messages(chat_id: str) -> list: # מחזיר את היסטוריית השיחה בפורמט המתאים ל-gpt (רשימת הודעות)
    """
    מחזיר את היסטוריית השיחה בפורמט המתאים ל-gpt (רשימת הודעות).
    קלט: chat_id (str)
    פלט: list של dict (role, content)
    """
    try:
        with open(CHAT_HISTORY_PATH, encoding="utf-8") as f:
            history_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    chat_id = str(chat_id)
    
    if chat_id not in history_data or "history" not in history_data[chat_id]:
        return []
    
    messages = []
    history = history_data[chat_id]["history"]
    if len(history) < 15:
        last_entries = history  #  שולח את כל ההיסטוריה אם יש -  פחות מ-איקס הודעות
    else:
        last_entries = history[-5:]  # רק 5 אחרונות

    for entry in last_entries:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["bot"]})

    
    print(f"📖 נטענו {len(messages)//2} הודעות מההיסטוריה של {chat_id}")
    return messages


def get_user_stats(chat_id: str) -> dict: # מחזיר סטטיסטיקות על המשתמש (מספר הודעות, תאריכים)
    """
    מחזיר סטטיסטיקות על המשתמש (מספר הודעות, תאריכים).
    קלט: chat_id (str)
    פלט: dict
    """
    try:
        with open(CHAT_HISTORY_PATH, encoding="utf-8") as f:
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


def clean_old_logs() -> None: # מנקה לוגים ישנים (משאיר עד MAX_OLD_LOG_LINES שורות אחרונות)
    """
    מנקה לוגים ישנים (משאיר עד MAX_OLD_LOG_LINES שורות אחרונות).
    פלט: אין (מנקה קבצים)
    """
    try:
        files_to_clean = [BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME]
        
        for file_name in files_to_clean:
            if os.path.exists(file_name):
                # שמירה על MAX_OLD_LOG_LINES שורות אחרונות בלבד
                with open(file_name, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                if len(lines) > MAX_OLD_LOG_LINES:
                    with open(file_name, "w", encoding="utf-8") as f:
                        f.writelines(lines[-MAX_OLD_LOG_LINES:])
                    print(f"🧽 נוקה קובץ: {file_name}")
        
    except Exception as e:
        print(f"❌ שגיאה בניקוי לוגים: {e}")


def health_check() -> dict: # בדיקת תקינות המערכת (config, sheets, openai, כתיבה לקבצים)
    """
    בדיקת תקינות המערכת (config, sheets, openai, כתיבה לקבצים).
    פלט: dict עם סטטוס לכל רכיב.
    """
    from config import check_config_sanity
    from notifications import send_error_notification
    health = {
        "config_loaded": False,
        "sheets_connected": False,
        "openai_connected": False,
        "log_files_writable": False
    }
    try:
        check_config_sanity()
        health["config_loaded"] = True
        from sheets_handler import sheet_users, sheet_log
        health["sheets_connected"] = True
        
        # בדיקת חיבור ל־OpenAI/LiteLLM
        try:
            import litellm
            # בדיקה פשוטה - ניסיון ליצור completion קטן
            response = litellm.completion(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
                temperature=0
            )
            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                health["openai_connected"] = True
                print("✅ חיבור ל־OpenAI/LiteLLM תקין")
            else:
                print("❌ תשובה לא תקינה מ־OpenAI/LiteLLM")
        except Exception as openai_error:
            print(f"❌ שגיאה בחיבור ל־OpenAI/LiteLLM: {openai_error}")
            health["openai_connected"] = False
        
        # בדיקת כתיבה לקבצים
        test_log = {"test": "health_check", "timestamp": datetime.now().isoformat()}
        with open("health_test.json", "w") as f:
            json.dump(test_log, f)
        os.remove("health_test.json")
        health["log_files_writable"] = True
    except Exception as e:
        print(f"⚕️ בעיה בבדיקת תקינות: {e}")
        try:
            send_error_notification(f"[HEALTH_CHECK] בעיה בבדיקת תקינות: {e}")
        except Exception:
            pass
    return health


def format_error_message(error: Exception, context: str = "") -> str: # מעצב הודעת שגיאה בצורה ברורה (כולל traceback)
    """
    מעצב הודעת שגיאה בצורה ברורה (כולל traceback).
    קלט: error (Exception), context (str)
    פלט: str
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
    if len(tb) > MAX_TRACEBACK_LENGTH:
        tb = tb[:MAX_TRACEBACK_LENGTH] + "... (קוצר)"
    
    error_msg += f"🔧 פרטים טכניים:\n{tb}"
    
    return error_msg


def log_error_stat(error_type: str) -> None:
    """
    מעדכן קובץ errors_stats.json עם ספירה לכל error_type
    """
    stats_path = os.path.join(DATA_DIR, "errors_stats.json")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    try:
        print(f"[DEBUG][log_error_stat] error_type = {error_type} (type: {type(error_type)})")
        if os.path.exists(stats_path):
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
        else:
            stats = {}
        for k, v in stats.items():
            print(f"[DEBUG][log_error_stat] stats[{k}] = {v} (type: {type(v)})")
            if isinstance(k, (dict, list)) or isinstance(v, (dict, list)):
                print(f"[DEBUG][log_error_stat][ALERT] {k} או הערך שלו הוא dict/list!")
        stats[error_type] = stats.get(error_type, 0) + 1
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import traceback
        print(f"[log_error_stat] שגיאה בעדכון סטטיסטיקת שגיאות: {e}")
        print(traceback.format_exc())


def send_error_stats_report():
    """
    שולח דוח שגיאות מצטבר לאדמין (ספירה לפי סוג שגיאה)
    """
    from notifications import send_admin_notification
    stats_path = os.path.join(DATA_DIR, "errors_stats.json")
    if not os.path.exists(stats_path):
        send_admin_notification("אין נתוני שגיאות זמינים.")
        return
    try:
        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)
        if not stats:
            send_admin_notification("אין שגיאות שנרשמו.")
            return
        lines = [f"{k}: {v}" for k, v in sorted(stats.items(), key=lambda x: -x[1])]
        msg = "\n".join(lines)
        send_admin_notification(f"📊 דוח שגיאות מצטבר:\n{msg}")
    except Exception as e:
        send_admin_notification(f"[send_error_stats_report] שגיאה בשליחת דוח שגיאות: {e}")


def send_usage_report(days_back: int = 1):
    """
    שולח דוח usage יומי/שבועי לאדמין (מספר משתמשים, הודעות, ממוצע תקלות למשתמש)
    """
    from datetime import timedelta
    from notifications import send_admin_notification
    if not os.path.exists(gpt_log_path):
        send_admin_notification("אין לוג usage זמין.")
        return
    try:
        users = set()
        messages = 0
        errors = 0
        now = datetime.now()
        since = now - timedelta(days=days_back)
        with open(gpt_log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp")
                    if not ts:
                        continue
                    dt = datetime.fromisoformat(ts.replace("Z", "")) if "T" in ts else datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    if dt < since:
                        continue
                    chat_id = entry.get("chat_id")
                    if chat_id:
                        users.add(str(chat_id))
                    messages += 1
                    if entry.get("error"):
                        errors += 1
                except Exception:
                    continue
        avg_errors = errors / messages if messages else 0
        msg = (
            f"📊 דוח usage {days_back} ימים אחרונים:\n"
            f"משתמשים ייחודיים: {len(users)}\n"
            f"הודעות: {messages}\n"
            f"שגיאות: {errors}\n"
            f"ממוצע שגיאות להודעה: {avg_errors:.2%}"
        )
        send_admin_notification(msg)
    except Exception as e:
        send_admin_notification(f"[send_usage_report] שגיאה בשליחת דוח usage: {e}")


def update_last_bot_message(chat_id, bot_summary):
    """
    מעדכן את השדה 'bot' של השורה האחרונה בהיסטוריה של המשתמש.
    קלט: chat_id (str/int), bot_summary (str)
    פלט: אין (מעדכן בקובץ)
    """
    try:
        file_path = CHAT_HISTORY_PATH
        with open(file_path, encoding="utf-8") as f:
            history_data = json.load(f)
        chat_id = str(chat_id)
        if chat_id in history_data and history_data[chat_id]["history"]:
            history_data[chat_id]["history"][-1]["bot"] = bot_summary
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ שגיאה בעדכון תשובת בוט: {e}")


# ========================================
# פקודות סודיות - Secret Commands
# ========================================

SECRET_CODES = {
    "#487chaCha2025": "clear_history",    # מוחק היסטוריית שיחה
    "#512SheetBooM": "clear_sheets",      # מוחק מידע מהגיליונות
    "#734TotalZap": "clear_all",          # מוחק הכל (היסטוריה + גיליונות)
}

def handle_secret_command(chat_id, user_msg):
    """
    טיפול בפקודות סודיות למטרות בדיקה ותחזוקה.
    קלט: chat_id, user_msg
    פלט: (bool, str) - האם טופל והתשובה
    """
    print(f"[SECRET_CMD] קיבלתי הודעה לבדוק קוד סודי | chat_id={chat_id} | text={user_msg!r} | timestamp={datetime.now().isoformat()}")

    action = SECRET_CODES.get(user_msg.strip())
    if not action:
        return False, None

    print(f"[SECRET_CMD] קוד סודי מזוהה: {action} | chat_id={chat_id}")

    if action == "clear_history":
        cleared = clear_chat_history(chat_id)
        msg = "🧹 כל ההיסטוריה שלך נמחקה!" if cleared else "🤷‍♂️ לא נמצאה היסטוריה למחיקה."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_history — {'נמחק' if cleared else 'לא נמצא'}")
        log_event_to_file({
            "event": "secret_command",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "action": "clear_history",
            "result": cleared
        })
        _send_admin_secret_notification(
            f"❗ הופעל קוד סודי למחיקת היסטוריה בצ'אט {chat_id}.\n"
            f"נמחקה אך ורק ההיסטוריה של משתמש זה."
        )
        return True, msg

    if action == "clear_sheets":
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "🗑️ כל הנתונים שלך נמחקו מהגיליונות!" if (deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא מידע למחיקה בגיליונות."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_sheets — sheet: {deleted_sheet}, state: {deleted_state}")
        log_event_to_file({
            "event": "secret_command",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "action": "clear_sheets",
            "deleted_sheet": deleted_sheet,
            "deleted_state": deleted_state
        })
        _send_admin_secret_notification(
            f"❗ הופעל קוד סודי למחיקת נתונים בגיליונות בצ'אט {chat_id}.\n"
            f"נמחק אך ורק מידע של משתמש זה.\n"
            f"{config['SHEET_USER_TAB']}: {'הצליח' if deleted_sheet else 'לא הצליח'}, {config['SHEET_STATES_TAB']}: {'הצליח' if deleted_state else 'לא הצליח'}"
        )
        return True, msg

    if action == "clear_all":
        cleared = clear_chat_history(chat_id)
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "💣 הכל נמחק! (היסטוריה + גיליונות)" if (cleared or deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא שום מידע למחיקה."
        print(f"[SECRET_CMD] {chat_id} ביקש clear_all — history: {cleared}, sheet: {deleted_sheet}, state: {deleted_state}")
        log_event_to_file({
            "event": "secret_command",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "action": "clear_all",
            "cleared_history": cleared,
            "deleted_sheet": deleted_sheet,
            "deleted_state": deleted_state
        })
        _send_admin_secret_notification(
            f"❗ הופעל קוד סודי למחיקת **הכל** בצ'אט {chat_id}.\n"
            f"נמחק הכל של משתמש זה בלבד.\n"
            f"היסטוריה: {'✔️' if cleared else '❌'} | {config['SHEET_USER_TAB']}: {'✔️' if deleted_sheet else '❌'} | {config['SHEET_STATES_TAB']}: {'✔️' if deleted_state else '❌'}"
        )
        return True, msg

    return False, None

def clear_chat_history(chat_id):
    """מוחק היסטוריית צ'אט ספציפי"""
    path = CHAT_HISTORY_PATH
    print(f"[CLEAR_HISTORY] מנסה למחוק היסטוריה | chat_id={chat_id} | path={path}")
    if not os.path.exists(path):
        print(f"[CLEAR_HISTORY] קובץ היסטוריה לא קיים | path={path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if str(chat_id) in data:
            data.pop(str(chat_id))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[CLEAR_HISTORY] נמחקה היסטוריה בהצלחה | chat_id={chat_id}")
            return True
        print(f"[CLEAR_HISTORY] לא נמצאה היסטוריה למחיקה | chat_id={chat_id}")
        return False
    except Exception as e:
        print(f"[ERROR-clear_chat_history] {e} | chat_id={chat_id}")
        log_event_to_file({
            "event": "clear_history_error",
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "error": str(e)
        })
        return False

def clear_from_sheets(chat_id):
    """מוחק נתוני משתמש מהגיליונות"""
    from sheets_handler import delete_row_by_chat_id
    print(f"[CLEAR_SHEETS] מנסה למחוק מהגיליונות | chat_id={chat_id}")
    deleted_sheet = delete_row_by_chat_id(sheet_name=config["SHEET_USER_TAB"], chat_id=chat_id)
    print(f"[CLEAR_SHEETS] נמחק ב-{config['SHEET_USER_TAB']}: {deleted_sheet} | chat_id={chat_id}")
    deleted_state = delete_row_by_chat_id(sheet_name=config["SHEET_STATES_TAB"], chat_id=chat_id)
    print(f"[CLEAR_SHEETS] נמחק ב-{config['SHEET_STATES_TAB']}: {deleted_state} | chat_id={chat_id}")
    return deleted_sheet, deleted_state

def _send_admin_secret_notification(message: str):
    """שולח הודעה לאדמין על שימוש בקוד סודי"""
    try:
        from notifications import send_admin_secret_command_notification
        send_admin_secret_command_notification(message)
    except Exception as e:
        print(f"💥 שגיאה בשליחת התראת קוד סודי: {e}")
