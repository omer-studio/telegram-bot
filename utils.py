"""
utils.py
--------
פונקציות עזר כלליות לבוט: שמירת לוגים, ניהול היסטוריה, סטטיסטיקות, בדיקת תקינות ועוד.
"""
import json
import os
import traceback
from datetime import datetime
import requests
import time
import logging
from config import BOT_TRACE_LOG_PATH, CHAT_HISTORY_PATH, gpt_log_path, BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME, DATA_DIR, MAX_LOG_LINES_TO_KEEP, MAX_OLD_LOG_LINES, MAX_CHAT_HISTORY_MESSAGES, MAX_TRACEBACK_LENGTH, config
from config import should_log_debug_prints, should_log_message_debug, should_log_sheets_debug
import litellm

# ==========================================================
# ניהול לוגים ושמירת מידע
# ==========================================================

def log_event_to_file(event_data, filename=None):
    """שומר אירוע ללוג בפורמט JSON lines"""
    try:
        if filename is None:
            filename = BOT_TRACE_LOG_PATH
        
        event_data["timestamp"] = datetime.now().isoformat()
        
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data, ensure_ascii=False) + "\n")
        
        if should_log_debug_prints():
            logging.debug(f"לוג נשמר: {filename}")
    except Exception as e:
        logging.error(f"שגיאה בשמירת לוג: {e}")
        if should_log_debug_prints():
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

        # הוספת האירוע החדש עם טיימסטאמפ מינימלי
        if (user_msg and user_msg.strip()) or (bot_summary and bot_summary.strip()):
            now = datetime.now()
            # יצירת טיימסטאמפ מינימלי לתצוגה: "27/12 14:01"
            simple_timestamp = f"{now.day:02d}/{now.month:02d} {now.hour:02d}:{now.minute:02d}"
            
            history_data[chat_id]["history"].append({
                "user": user_msg,
                "bot": bot_summary,
                "timestamp": now.isoformat(),  # פורמט מלא לחישובים פנימיים
                "time": simple_timestamp       # פורמט קצר לתצוגה ל-GPT: [27/12 14:01]
            })

        # שמירה על איקס הודעות אחרונות בלבד
        history_data[chat_id]["history"] = history_data[chat_id]["history"][-MAX_CHAT_HISTORY_MESSAGES:]

        # שמירה חזרה לקובץ
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        if should_log_message_debug():
            logging.info(f"היסטוריה עודכנה למשתמש {chat_id}")

    except Exception as e:
        logging.error(f"שגיאה בעדכון היסטוריה: {e}")


def get_chat_history_messages(chat_id: str, limit: int = None) -> list: # מחזיר את היסטוריית השיחה בפורמט המתאים ל-gpt (רשימת הודעות)
    """
    מחזיר את היסטוריית השיחה בפורמט המתאים ל-gpt (רשימת הודעות).
    קלט: chat_id (str), limit (int, optional) - מספר הודעות מקסימלי
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
    
    # קביעת מספר ההודעות לפי הפרמטר limit או ברירת מחדל של 15 זוגות (30 הודעות)
    max_entries = limit if limit is not None else 15
    
    if len(history) < max_entries:
        last_entries = history  #  שולח את כל ההיסטוריה אם יש פחות מ-max_entries הודעות
    else:
        last_entries = history[-max_entries:]  # רק max_entries אחרונות

    for entry in last_entries:
        # הוספת הטיימסטאמפ המינימלי להודעת המשתמש בלבד (חוסך טוקנים)
        user_content = entry["user"]
        if "time" in entry:  # אם יש טיימסטאמפ מינימלי - מציג כ [27/12 14:01]
            user_content = f"[{entry['time']}] {entry['user']}"
        
        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": entry["bot"]})  # תשובת הבוט ללא זמן

    
    if should_log_message_debug():
        logging.info(f"נטענו {len(messages)//2} הודעות מההיסטוריה של {chat_id}")
    return messages


def get_user_stats(chat_id: str) -> dict: # מחזיר סטטיסטיקות מועשרות על המשתמש לתחושה אנושית יותר
    """
    📊 מחזיר סטטיסטיקות מועשרות על המשתמש להקשר אנושי.
    
    🎯 מטרה: לאסוף נתונים עבור create_human_context_for_gpt()
    - מספר הודעות ותקופת הקשר
    - זמן מההודעה האחרונה  
    - הקשר זמן נוכחי (שעה, יום בשבוע)
    - ניתוח מילות מפתח רגשיות
    
    קלט: chat_id (str)
    פלט: dict עם מידע מפורט לשימוש מערכת ההקשר
    """
    try:
        with open(CHAT_HISTORY_PATH, encoding="utf-8") as f:
            history_data = json.load(f)
        
        chat_id = str(chat_id)
        if chat_id not in history_data:
            return {"total_messages": 0, "first_contact": None, "last_contact": None}
        
        history = history_data[chat_id]["history"]
        now = datetime.now()
        
        # נתונים בסיסיים קיימים
        basic_stats = {
            "total_messages": len(history),
            "first_contact": history[0]["timestamp"] if history else None,
            "last_contact": history[-1]["timestamp"] if history else None
        }
        
        if not history:
            return basic_stats
            
        # 🎯 העשרה חדשה - הקשר זמן ויחסים
        first_contact_dt = datetime.fromisoformat(history[0]["timestamp"])
        last_contact_dt = datetime.fromisoformat(history[-1]["timestamp"])
        
        # חישוב תקופת הקשר
        relationship_duration = now - first_contact_dt
        days_together = relationship_duration.days
        
        # זמן מההודעה האחרונה  
        time_since_last = now - last_contact_dt
        hours_since_last = time_since_last.total_seconds() / 3600
        
        # הקשר זמן יום/שבוע/חודש - לישראל
        israel_tz = datetime.now().astimezone()
        current_hour = israel_tz.hour
        weekday = israel_tz.weekday()  # 0=Monday, 6=Sunday
        day_of_month = israel_tz.day
        month = israel_tz.month
        
        # זיהוי זמן יום
        time_of_day = ""
        if 5 <= current_hour <= 11:
            time_of_day = "morning"
        elif 12 <= current_hour <= 17:
            time_of_day = "afternoon"  
        elif 18 <= current_hour <= 22:
            time_of_day = "evening"
        else:
            time_of_day = "night"
            
        # הקשר שבועי
        weekend_approaching = weekday >= 3  # חמישי-שבת
        is_weekend = weekday >= 5  # שבת-ראשון (5=שבת, 6=ראשון)
        
        # ניתוח תדירות הודעות
        messages_per_day = len(history) / max(days_together, 1)
        
        # 📊 מעקב אחר נושאים חוזרים (מילות מפתח פשוטות)
        user_messages = [entry["user"] for entry in history if entry.get("user")]
        all_user_text = " ".join(user_messages).lower()
        
        # מילות מפתח רגשיות בסיסיות
        emotional_keywords = {
            "stress": ["לחץ", "חרדה", "מתח", "עצוב", "קשה", "בוכה"],
            "hope": ["תקווה", "עתיד", "חלום", "רוצה", "מקווה", "אולי"],
            "family": ["משפחה", "אמא", "אבא", "אח", "אחות", "הורים"],
            "work": ["עבודה", "עובד", "בוס", "משרד", "קריירה", "לימודים"],
            "relationship": ["חבר", "חברה", "בן זוג", "נפגש", "דייט", "אהבה"]
        }
        
        topic_mentions = {}
        for topic, keywords in emotional_keywords.items():
            mentions = sum(all_user_text.count(keyword) for keyword in keywords)
            if mentions > 0:
                topic_mentions[topic] = mentions
        
        # 🔮 העשרה מתקדמת - הקשר תוכן
        enhanced_stats = basic_stats.copy()
        enhanced_stats.update({
            # יחסי זמן 
            "days_knowing_each_other": days_together,
            "hours_since_last_message": round(hours_since_last, 1),
            "messages_per_day_avg": round(messages_per_day, 1),
            
            # הקשר זמן נוכחי
            "current_time_of_day": time_of_day,
            "current_hour": current_hour,
            "is_weekend": is_weekend,
            "weekend_approaching": weekend_approaching,
            "day_of_month": day_of_month,
            "month": month,
            "weekday_name": ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"][weekday],
            
            # תובנות תוכן
            "main_topics_mentioned": topic_mentions,
            "total_user_words": len(all_user_text.split()),
            
            # הקשר ריגשי-זמני מועשר לGPT
            "relationship_context": f"אתם מדברים כבר {days_together} ימים, סה\"כ {len(history)} הודעות",
            "time_context": f"עברו {round(hours_since_last, 1)} שעות מההודעה האחרונה",
            "day_context": f"היום יום {['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון'][weekday]} בשעה {current_hour:02d}"
        })
        
        return enhanced_stats
        
    except Exception as e:
        logging.error(f"שגיאה בקבלת סטטיסטיקות: {e}")
        return {"total_messages": 0, "first_contact": None, "last_contact": None}


def create_human_context_for_gpt(chat_id: str) -> str:
    """
    🤖 יוצר מידע רקע חכם לGPT - ברכות יום וזמן בעברית.
    
    📋 לוגיקה:
    - ברכת זמן: רק אחרי פער של 3+ שעות (בוקר/צהריים/ערב/לילה טוב)
    - ברכת יום: רק פעם ביום אחרי פער של 6+ שעות (שאלות מותאמות לכל יום)
    - משתמשים חדשים: ללא הקשר (בונים קשר קודם)
    
    קלט: chat_id (str)
    פלט: str - הודעה בעברית או ריקה (אם לא רלוונטי)
    """
    try:
        stats = get_user_stats(chat_id)
        
        # 🚫 משתמשים חדשים - ללא הקשר זמן
        if stats["total_messages"] == 0:
            return ""
        
        hours_since = stats.get("hours_since_last_message", 0)
        current_hour = stats.get("current_hour", 12)
        weekday = stats.get("weekday_name", "")
        
        context_parts = []
        
        # 🌅 1. ברכת זמן (רק אחרי פער של 3+ שעות)
        # מטרה: ליצור תחושה של זמן אמת ונוכחות
        if hours_since >= 3:
            if 6 <= current_hour <= 11:
                context_parts.append("בוקר טוב!")
            elif 12 <= current_hour <= 15:
                context_parts.append("צהריים טובים!")
            elif 17 <= current_hour <= 21:
                context_parts.append("ערב טוב!")
            elif 21 <= current_hour <= 23 or 0 <= current_hour <= 3:
                context_parts.append("לילה טוב!")
        
        # 📅 2. ברכת יום (רק פעם ביום - אחרי פער של 6+ שעות)
        # מטרה: לתת ל-GPT רעיונות לשיחה מתאימים לכל יום בשבוע
        if hours_since >= 6:
            day_greetings = {
                "ראשון": "אגב היום יום ראשון, השעה {hour:02d}:{minute:02d} - איך מתחיל השבוע?",
                "שני": "אגב היום יום שני, השעה {hour:02d}:{minute:02d} - איך עובר עליך השבוע?", 
                "שלישי": "אגב היום יום שלישי, השעה {hour:02d}:{minute:02d} - איך מרגיש השבוע עד כה?",
                "רביעי": "אגב היום יום רביעי, השעה {hour:02d}:{minute:02d} - אמצע השבוע, איך זה עובר עליך?",
                "חמישי": "אגב היום יום חמישי, השעה {hour:02d}:{minute:02d} - איך עבר עליך השבוע? יש תוכניות לסופש?",
                "שישי": "אגב היום יום שישי, השעה {hour:02d}:{minute:02d} - איך אתה מסכם את השבוע? איפה אתה עושה ארוחת ערב הערב?",
                "שבת": "אגב היום שבת, השעה {hour:02d}:{minute:02d} - איך עובר עליך הסופש?"
            }
            
            if weekday in day_greetings:
                now = datetime.now()
                day_message = day_greetings[weekday].format(hour=now.hour, minute=now.minute)
                context_parts.append(day_message)
        
        # 🎯 החזרת הודעה מחוברת או ריקה
        # GPT יקבל את זה כ-system message ויחליט איך להשתמש בזה
        if context_parts:
            return " ".join(context_parts)
        else:
            return ""
            
    except Exception as e:
        logging.error(f"שגיאה ביצירת הקשר אנושי: {e}")
        return ""




def clean_old_logs() -> None: # מנקה לוגים ישנים (משאיר עד MAX_OLD_LOG_LINES שורות אחרונות)
    """
    מנקה לוגים ישנים (משאיר עד MAX_OLD_LOG_LINES שורות אחרונות).
    פלט: אין (מנקה קבצים)
    """
    try:
        files_to_clean = [BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME]
        
        for file_name in files_to_clean:
            file_path = os.path.join(DATA_DIR, file_name)
            if os.path.exists(file_path):
                # קריאת הקובץ
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # שמירת השורות האחרונות בלבד
                if len(lines) > MAX_OLD_LOG_LINES:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines[-MAX_OLD_LOG_LINES:])
                    
                if should_log_debug_prints():
                    logging.info(f"נוקה קובץ: {file_name}")
        
    except Exception as e:
        logging.error(f"שגיאה בניקוי לוגים: {e}")


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
            from gpt_utils import measure_llm_latency
            # בדיקה פשוטה - ניסיון ליצור completion קטן
            with measure_llm_latency("gpt-3.5-turbo"):
                response = litellm.completion(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5,
                    temperature=0
                )
            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                health["openai_connected"] = True
                if should_log_debug_prints():
                    print("✅ חיבור ל־OpenAI/LiteLLM תקין")
            else:
                if should_log_debug_prints():
                    print("❌ תשובה לא תקינה מ־OpenAI/LiteLLM")
        except Exception as openai_error:
            if should_log_debug_prints():
                print(f"❌ שגיאה בחיבור ל־OpenAI/LiteLLM: {openai_error}")
            health["openai_connected"] = False
        
        # בדיקת כתיבה לקבצים
        test_log = {"test": "health_check", "timestamp": datetime.now().isoformat()}
        with open("health_test.json", "w") as f:
            json.dump(test_log, f)
        os.remove("health_test.json")
        health["log_files_writable"] = True
    except Exception as e:
        logging.error(f"⚕️ בעיה בבדיקת תקינות: {e}")
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
    try:
        error_msg = f"🚨 שגיאה"
        if context:
            error_msg += f" ב{context}"
        
        error_msg += f":\n"
        error_msg += f"📍 סוג: {type(error).__name__}\n"
        error_msg += f"💬 הודעה: {str(error)}\n"
        error_msg += f"⏰ זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        
        # הוספת traceback רק בdebug mode
        if should_log_debug_prints():
            tb = traceback.format_exc()
            if len(tb) > MAX_TRACEBACK_LENGTH:
                tb = tb[:MAX_TRACEBACK_LENGTH] + "... (truncated)"
            error_msg += f"🔧 פרטים טכניים:\n{tb}"
        
        return error_msg
    except:
        return f"🚨 שגיאה בעיצוב הודעת שגיאה: {str(error)}"


def log_error_stat(error_type: str) -> None:
    """מעדכן קובץ errors_stats.json עם ספירה לכל error_type"""
    try:
        stats_path = os.path.join(DATA_DIR, "errors_stats.json")
        
        if should_log_debug_prints():
            print(f"[DEBUG][log_error_stat] error_type = {error_type} (type: {type(error_type)})")
        
        # טעינה או יצירת stats
        try:
            with open(stats_path, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            stats = {}
        
        if should_log_debug_prints():
            for k, v in stats.items():
                print(f"[DEBUG][log_error_stat] stats[{k}] = {v} (type: {type(v)})")
                if isinstance(v, (dict, list)):
                    print(f"[DEBUG][log_error_stat][ALERT] {k} או הערך שלו הוא dict/list!")
        
        stats[error_type] = stats.get(error_type, 0) + 1
        
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logging.error(f"שגיאה בעדכון סטטיסטיקת שגיאות: {e}")
        if should_log_debug_prints():
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
        logging.error(f"❌ שגיאה בעדכון תשובת בוט: {e}")


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
    if should_log_debug_prints():
        print(f"[SECRET_CMD] קיבלתי הודעה לבדוק קוד סודי | chat_id={chat_id} | text={user_msg!r} | timestamp={datetime.now().isoformat()}")

    action = SECRET_CODES.get(user_msg.strip())
    if not action:
        return False, None

    if should_log_debug_prints():
        print(f"[SECRET_CMD] קוד סודי מזוהה: {action} | chat_id={chat_id}")

    if action == "clear_history":
        cleared = clear_chat_history(chat_id)
        msg = "🧹 כל ההיסטוריה שלך נמחקה!" if cleared else "🤷‍♂️ לא נמצאה היסטוריה למחיקה."
        if should_log_debug_prints():
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
        if should_log_debug_prints():
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
        if should_log_debug_prints():
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
    if should_log_debug_prints():
        print(f"[CLEAR_HISTORY] מנסה למחוק היסטוריה | chat_id={chat_id} | path={path}")
    if not os.path.exists(path):
        if should_log_debug_prints():
            print(f"[CLEAR_HISTORY] קובץ היסטוריה לא קיים | path={path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if str(chat_id) in data:
            data.pop(str(chat_id))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if should_log_debug_prints():
                print(f"[CLEAR_HISTORY] נמחקה היסטוריה בהצלחה | chat_id={chat_id}")
            return True
        if should_log_debug_prints():
            print(f"[CLEAR_HISTORY] לא נמצאה היסטוריה למחיקה | chat_id={chat_id}")
        return False
    except Exception as e:
        logging.error(f"[ERROR-clear_chat_history] {e} | chat_id={chat_id}")
        log_event_to_file({
            "event": "clear_history_error",
            "chat_id": chat_id,
            "error": str(e)
        })
        return False

def clear_from_sheets(chat_id):
    """מוחק נתוני משתמש מהגיליונות"""
    from sheets_handler import delete_row_by_chat_id
    if should_log_debug_prints():
        print(f"[CLEAR_SHEETS] מנסה למחוק מהגיליונות | chat_id={chat_id}")
    deleted_sheet = delete_row_by_chat_id(sheet_name=config["SHEET_USER_TAB"], chat_id=chat_id)
    if should_log_debug_prints():
        print(f"[CLEAR_SHEETS] נמחק ב-{config['SHEET_USER_TAB']}: {deleted_sheet} | chat_id={chat_id}")
    deleted_state = delete_row_by_chat_id(sheet_name=config["SHEET_STATES_TAB"], chat_id=chat_id)
    if should_log_debug_prints():
        print(f"[CLEAR_SHEETS] נמחק ב-{config['SHEET_STATES_TAB']}: {deleted_state} | chat_id={chat_id}")
    return deleted_sheet, deleted_state

def _send_admin_secret_notification(message: str):
    """שולח הודעה לאדמין על שימוש בקוד סודי"""
    try:
        from notifications import send_admin_secret_command_notification
        send_admin_secret_command_notification(message)
    except Exception as e:
        logging.error(f"💥 שגיאה בשליחת התראת קוד סודי: {e}")

# 🎛️ פונקציה פשוטה להצגת מצב הלוגים
def show_log_status():
    """מציג את מצב הלוגים הנוכחי - פונקציה פשוטה ללא תלות בimports מסובכים"""
    try:
        from config import (ENABLE_DEBUG_PRINTS, ENABLE_GPT_COST_DEBUG, ENABLE_SHEETS_DEBUG,
                           ENABLE_PERFORMANCE_DEBUG, ENABLE_MESSAGE_DEBUG, ENABLE_DATA_EXTRACTION_DEBUG, DEFAULT_LOG_LEVEL)
        
        print("\n🎛️  מצב הלוגים הנוכחי:")
        print("=" * 40)
        print(f"📊 רמת לוג כללית:     {DEFAULT_LOG_LEVEL}")
        print(f"🐛 דיבאג כללי:        {'✅' if ENABLE_DEBUG_PRINTS else '❌'}")
        print(f"💰 עלויות GPT:        {'✅' if ENABLE_GPT_COST_DEBUG else '❌'}")
        print(f"📋 חילוץ נתונים:      {'✅' if ENABLE_DATA_EXTRACTION_DEBUG else '❌'}")
        print(f"⏱️  ביצועים:           {'✅' if ENABLE_PERFORMANCE_DEBUG else '❌'}")
        print(f"💬 הודעות:            {'✅' if ENABLE_MESSAGE_DEBUG else '❌'}")
        print(f"📊 גיליונות:          {'✅' if ENABLE_SHEETS_DEBUG else '❌'}")
        print("=" * 40)
        print("\n💡 לשינוי: ערוך את config.py או השתמש במשתני סביבה")
        print("   דוגמה: $env:ENABLE_GPT_COST_DEBUG=\"false\"; python main.py")
        
    except ImportError as e:
        print(f"❌ שגיאת import: {e}")
        print("💡 אפשר גם לערוך ידנית את config.py")
    except Exception as e:
        print(f"❌ שגיאה: {e}")

def show_gpt_input_examples():
    """
    🎯 דוגמאות למה ש-GPT מקבל כקלט - להבנה ובדיקה
    """
    print("\n" + "="*60)
    print("🤖 דוגמאות למה ש-GPT מקבל כהודעות קלט")
    print("="*60)
    
    print("\n📋 מבנה ההודעות:")
    print("1️⃣ System Prompt (קבוע)")
    print("2️⃣ מידע על המשתמש (אם קיים)")
    print("3️⃣ הקשר אנושי (זמן/יום - אם רלוונטי)")
    print("4️⃣ 15 זוגות הודעות אחרונות (30 הודעות)")
    print("5️⃣ ההודעה החדשה")
    
    print("\n🔍 דוגמה 1: משתמש חוזר אחרי כמה שעות ביום שישי")
    example1 = [
        {"role": "system", "content": "אתה בוט עברי חכם ומבין..."},
        {"role": "system", "content": "מידע חשוב על היוזר: אוהב פיצה, עובד בהייטק, גר בתל אביב"},
        {"role": "system", "content": "צהריים טובים! אגב היום יום שישי, השעה 14:30 - איך אתה מסכם את השבוע? איפה אתה עושה ארוחת ערב הערב?"},
        {"role": "user", "content": "[26/12 08:15] בוקר טוב"},
        {"role": "assistant", "content": "בוקר טוב! איך השינה?"},
        {"role": "user", "content": "[26/12 12:30] עבדתי קשה היום"},
        {"role": "assistant", "content": "נשמע מתיש, על מה עבדת?"},
        {"role": "user", "content": "[27/12 14:30] שלום מה קורה?"}
    ]
    
    print("\nהודעות ל-GPT:")
    for i, msg in enumerate(example1, 1):
        role = "🤖 מערכת" if msg["role"] == "system" else "👤 משתמש" if msg["role"] == "user" else "🤖 בוט"
        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        print(f"{i}. {role}: {content}")
    
    print("\n🔍 דוגמה 2: שיחה רציפה (ללא הקשר זמן)")
    example2 = [
        {"role": "system", "content": "אתה בוט עברי חכם ומבין..."},
        {"role": "system", "content": "מידע חשוב על היוזר: סטודנט למתמטיקה, גר בירושלים"},
        {"role": "user", "content": "[27/12 14:25] היי איך אתה?"},
        {"role": "assistant", "content": "שלום! אני בסדר, מה שלומך?"},
        {"role": "user", "content": "[27/12 14:27] אני טוב תודה"},
        {"role": "assistant", "content": "נהדר! איך עבר עליך היום?"},
        {"role": "user", "content": "[27/12 14:30] מה אתה חושב על הבחירות?"}
    ]
    
    print("\nהודעות ל-GPT (ללא הקשר זמן כי שיחה רציפה):")
    for i, msg in enumerate(example2, 1):
        role = "🤖 מערכת" if msg["role"] == "system" else "👤 משתמש" if msg["role"] == "user" else "🤖 בוט"
        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        print(f"{i}. {role}: {content}")
    
    print("\n🔍 דוגמה 3: משתמש חדש (בלי הקשר כלל)")
    example3 = [
        {"role": "system", "content": "אתה בוט עברי חכם ומבין..."},
        {"role": "user", "content": "היי מה קורה?"}
    ]
    
    print("\nהודעות ל-GPT (משתמש חדש - רק system + הודעה):")
    for i, msg in enumerate(example3, 1):
        role = "🤖 מערכת" if msg["role"] == "system" else "👤 משתמש"
        print(f"{i}. {role}: {msg['content']}")
    
    print("\n🔍 דוגמה 4: משתמש עם היסטוריה ארוכה (15 זוגות אחרונים)")
    print("במקרה של 50 הודעות בהיסטוריה - יישלחו רק:")
    print("• ההודעות הבסיסיות (system, user info, context)")
    print("• 15 זוגות הודעות אחרונות = 30 הודעות")
    print("• ההודעה הנוכחית")
    print("• סה\"כ: ~34 הודעות במקום 53")
    
    print("\n💡 הסבר טכני:")
    print("📍 get_chat_history_messages() מחזירה מקסימום 15 entries")
    print("📍 כל entry = זוג (user + assistant)")
    print("📍 זה אומר 15×2 = 30 הודעות מההיסטוריה")
    print("📍 + system messages + הודעה נוכחית")
    print("📍 create_human_context_for_gpt() מוסיף הקשר זמן רק כשרלוונטי")
    
    print("="*60)

# אם מפעילים את utils.py ישירות
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "log-status":
        show_log_status()
    elif len(sys.argv) > 1 and sys.argv[1] == "gpt-examples":
        show_gpt_input_examples()
    else:
        print("שימוש:")
        print("  python utils.py log-status     - מציג מצב לוגים")
        print("  python utils.py gpt-examples   - מציג דוגמאות קלט ל-GPT")
