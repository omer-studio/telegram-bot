"""פונקציות עזר כלליות לבוט."""
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
import pytz

def get_israel_time():
    """מחזיר את הזמן הנוכחי בישראל"""
    israel_tz = pytz.timezone('Asia/Jerusalem')
    return datetime.now(israel_tz)

def log_event_to_file(event_data, filename=None):  # שומר אירוע ללוג בפורמט JSON lines
    try:
        if filename is None:
            filename = BOT_TRACE_LOG_PATH
        event_data["timestamp"] = get_israel_time().isoformat()
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data, ensure_ascii=False) + "\n")
        if should_log_debug_prints():
            logging.debug(f"לוג נשמר: {filename}")
    except Exception as e:
        logging.error(f"שגיאה בשמירת לוג: {e}")
        if should_log_debug_prints():
            print(traceback.format_exc())

def update_chat_history(chat_id, user_msg, bot_summary):  # מעדכן היסטוריית שיחה בקובץ JSON
    try:
        file_path = CHAT_HISTORY_PATH
        try:  # טעינת היסטוריה קיימת
            with open(file_path, encoding="utf-8") as f:
                history_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history_data = {}
        chat_id = str(chat_id)
        if chat_id not in history_data:
            history_data[chat_id] = {"am_context": "", "history": []}
        if (user_msg and user_msg.strip()) or (bot_summary and bot_summary.strip()):
            now = get_israel_time()
            simple_timestamp = f"{now.day}/{now.month} {now.hour:02d}:{now.minute:02d}"
            history_data[chat_id]["history"].append({
                "user": user_msg,
                "bot": bot_summary,
                "timestamp": now.isoformat(),
                "time": simple_timestamp
            })
        history_data[chat_id]["history"] = history_data[chat_id]["history"][-MAX_CHAT_HISTORY_MESSAGES:]  # שמירת מגבלה
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        if should_log_message_debug():
            logging.info(f"היסטוריה עודכנה למשתמש {chat_id}")
    except Exception as e:
        logging.error(f"שגיאה בעדכון היסטוריה: {e}")

def get_chat_history_messages(chat_id: str, limit: int = None) -> list:  # מחזיר היסטוריית שיחה בפורמט GPT
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
    max_entries = limit if limit is not None else 15
    if len(history) < max_entries:
        last_entries = history
    else:
        last_entries = history[-max_entries:]
    for entry in last_entries:
        user_content = entry["user"]
        if "time" in entry:
            user_content = f"[{entry['time']}] {entry['user']}"
        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": entry["bot"]})
    if should_log_message_debug():
        logging.info(f"נטענו {len(messages)//2} הודעות מההיסטוריה של {chat_id}")
    return messages

def get_user_stats_and_history(chat_id: str) -> tuple[dict, list]:  # מחזיר סטטיסטיקות והיסטוריה בקריאה אחת
    try:
        with open(CHAT_HISTORY_PATH, encoding="utf-8") as f:
            history_data = json.load(f)
        chat_id = str(chat_id)
        if chat_id not in history_data:
            return {"total_messages": 0, "first_contact": None, "last_contact": None}, []
        history = history_data[chat_id]["history"]
        stats = _calculate_user_stats_from_history(history)
        return stats, history
    except Exception as e:
        logging.error(f"שגיאה בקבלת סטטיסטיקות: {e}")
        return {"total_messages": 0, "first_contact": None, "last_contact": None}, []

def _get_time_of_day(hour: int) -> str:
    """מחזיר את זמן היום לפי השעה."""
    if 5 <= hour <= 11: return "morning"
    elif 12 <= hour <= 17: return "afternoon"
    elif 18 <= hour <= 22: return "evening"
    else: return "night"

def _extract_topics_from_text(text: str) -> dict:
    """מחלץ נושאים רגשיים מטקסט המשתמש."""
    emotional_keywords = {
        "stress": ["לחץ", "חרדה", "מתח", "עצוב", "קשה", "בוכה"],
        "hope": ["תקווה", "עתיד", "חלום", "רוצה", "מקווה", "אולי"],
        "family": ["משפחה", "אמא", "אבא", "אח", "אחות", "הורים"],
        "work": ["עבודה", "עובד", "בוס", "משרד", "קריירה", "לימודים"],
        "relationship": ["חבר", "חברה", "בן זוג", "נפגש", "דייט", "אהבה"]
    }
    topic_mentions = {}
    for topic, keywords in emotional_keywords.items():
        mentions = sum(text.count(keyword) for keyword in keywords)
        if mentions > 0:
            topic_mentions[topic] = mentions
    return topic_mentions

def _calculate_user_stats_from_history(history: list) -> dict:
    """מחשב סטטיסטיקות מהיסטוריה - גרסה רזה."""
    basic_stats = {"total_messages": len(history), "first_contact": history[0]["timestamp"] if history else None, "last_contact": history[-1]["timestamp"] if history else None}
    if not history:
        return basic_stats
    
    # חישובי זמן בסיסיים
    now = get_israel_time()
    first_contact_dt = datetime.fromisoformat(history[0]["timestamp"])
    last_contact_dt = datetime.fromisoformat(history[-1]["timestamp"])
    days_together = (now - first_contact_dt).days
    hours_since_last = (now - last_contact_dt).total_seconds() / 3600
    
    # מידע על זמן נוכחי
    israel_tz = get_israel_time()
    current_hour, weekday, day_of_month, month = israel_tz.hour, israel_tz.weekday(), israel_tz.day, israel_tz.month
    weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    
    # ניתוח תוכן משתמש
    user_messages = [entry["user"] for entry in history if entry.get("user")]
    all_user_text = " ".join(user_messages).lower()
    topic_mentions = _extract_topics_from_text(all_user_text)
    
    # הרכבת תוצאה מלאה
    basic_stats.update({
        "days_knowing_each_other": days_together, 
        "hours_since_last_message": round(hours_since_last, 1), 
        "messages_per_day_avg": round(len(history) / max(days_together, 1), 1),
        "current_time_of_day": _get_time_of_day(current_hour), 
        "current_hour": current_hour, 
        "is_weekend": weekday >= 5, 
        "weekend_approaching": weekday >= 3,
        "day_of_month": day_of_month, 
        "month": month, 
        "weekday_name": weekday_names[weekday],
        "main_topics_mentioned": topic_mentions, 
        "total_user_words": len(all_user_text.split()),
        "relationship_context": f"אתם מדברים כבר {days_together} ימים, סה\"כ {len(history)} הודעות",
        "time_context": f"עברו {round(hours_since_last, 1)} שעות מההודעה האחרונה",
        "day_context": f"היום יום {weekday_names[weekday]} בשעה {current_hour:02d}"
    })
    return basic_stats

def get_user_stats(chat_id: str) -> dict:  # מחזיר סטטיסטיקות מועשרות על המשתמש
    try:
        stats, _ = get_user_stats_and_history(chat_id)
        return stats
    except Exception as e:
        logging.error(f"שגיאה בקבלת סטטיסטיקות: {e}")
        return {"total_messages": 0, "first_contact": None, "last_contact": None}

def create_human_context_for_gpt(chat_id: str) -> str:
    """שולח טיימסטמפ מצומצם לGPT (ללא יום שבוע - זה יבוא בנפרד)."""
    try:
        now = get_israel_time()
        # טיימסטמפ בפורמט [28/6 18:26] - ללא יום שבוע
        timestamp = f"[{now.day}/{now.month} {now.hour:02d}:{now.minute:02d}]"
        
        return timestamp
    except Exception as e:
        logging.error(f"שגיאה ביצירת הקשר זמן: {e}")
        return ""

def get_time_greeting_instruction() -> str:
    """מחזיר הנחיה למודל לפתוח בברכה מתאימה לזמן"""
    try:
        now = get_israel_time()
        hour = now.hour
        
        if 5 <= hour < 11:
            greeting_guide = "תפתח בברכה 'בוקר טוב!' וביטוי של אנרגיה חיובית לתחילת היום"
        elif 11 <= hour < 16:
            greeting_guide = "תפתח בברכה 'צהריים טובים!' והתייחס לקצב היום או מה שקורה בשעות האלה"
        elif 16 <= hour < 20:
            greeting_guide = "תפתח בברכה 'ערב טוב!' והתייחס לסיום היום או לתוכניות הערב"
        elif 20 <= hour < 24:
            greeting_guide = "תפתח בברכה 'ערב טוב!' או 'לילה טוב!' והיה יותר רגוע ונעים"
        else:  # 0-5
            greeting_guide = "תפתח בברכה 'לילה טוב!' והיה מבין שזה זמן מאוחר, שאל אם הכל בסדר"
            
        return f"{greeting_guide}. כן באמצע השיחה התייחס לזמן בצורה טבעית ורלוונטית."
        
    except Exception as e:
        logging.error(f"שגיאה בהנחיות ברכה: {e}")
        return "תפתח בברכה מתאימה לזמן והתייחס לשעה בצורה טבעית."

def get_weekday_context_instruction() -> str:
    """מחזיר הנחיה ספציפית לכל יום בשבוע"""
    try:
        now = get_israel_time()
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        weekday_instructions = {
            0: "היום יום ב' - תחילת שבוע. שאל אותו: 'איך התחיל השבוע? יש תוכניות מיוחדות השבוע? איך הוא מרגיש עם התחלת שבוע חדש?' התייחס באופן חיובי ועודד אותו לשבוע הקרב.",
            1: "היום יום ג'. שאל אותו: 'איך עבר השבוע עד כה? מה הדבר הכי טוב שקרה השבוע? יש משהו שמאתגר אותך השבוע?' תן לו חיזוק ועצות אם צריך.",
            2: "היום יום ד' - אמצע השבוע. שאל אותו: 'איך אתה מרגיש באמצע השבוע? מה עוד נשאר לך לעשות עד הסופש? יש משהו שאתה מצפה לו השבוע?' עזור לו לעבור את החלק השני של השבוע.",
            3: "היום יום ה' - לקראת הסופש. שאל אותו: 'איך אתה מסכם את השבוע? מה הדבר הכי טוב שקרה? יש תוכניות לסופש?' התרגש איתו לקראת הסופש ועזור לו לתכנן.",
            4: "היום יום ו' - ערב שבת. שאל אותו: 'איך אתה מכין את השבת? יש ארוחת שבת מיוחדת? עם מי אתה נפגש הערב?' התעניין בתוכניות השבת שלו ובמשפחה.",
            5: "היום שבת - יום מנוחה. שאל אותו: 'איך עובר השבת? עושה משהו נחמד היום? נפגש עם משפחה או חברים?' היה רגוע ונעים, התאם לאווירת השבת.",
            6: "היום יום א' - סוף הסופש. שאל אותו: 'איך היה הסופש? מה עשית? איך אתה מרגיש לקראת השבוע החדש מחר?' עזור לו להתכונן נפשית לשבוע הבא."
        }
        
        return weekday_instructions.get(weekday, "")
        
    except Exception as e:
        logging.error(f"שגיאה ביצירת הנחיית יום השבוע: {e}")
        return ""



def get_holiday_system_message(chat_id: str) -> str:
    """
    מחזיר הודעת SYSTEM לחגים דתיים רלוונטיים לפי זהות דתית ורמת דתיות.
    
    הלוגיקה:
    1. self_religious_affiliation (זהות): יהודי/ערבי/דרוזי/נוצרי/אתאיסט/שומרוני
    2. self_religiosity_level (רמת דתיות): דתי/חילוני/מסורתי/חרדי/דתי לאומי/לא דתי
    
    דוגמאות:
    - אין מידע → יהודי חילוני (ברירת מחדל)
    - יהודי + דתי → חגים + צומות יהודיים
    - יהודי + חילוני → רק חגים יהודיים (לא צומות)
    - ערבי → חגים מוסלמיים
    - דרוזי → חגים דרוזיים
    - אתאיסט → כמו יהודי חילוני (אירועים כלליים + חגים יהודיים)
    
    הערה: חודש הגאווה ואירועים כלליים מתייחסים אליהם כאותו דבר.
    """
    try:
        from sheets_core import get_user_profile_data
        from datetime import datetime
        import json
        import os
        
        # קבלת נתוני המשתמש
        user_data = get_user_profile_data(chat_id)
        if not user_data:
            return ""
        
        religious_affiliation = user_data.get("self_religious_affiliation", "").lower() if user_data.get("self_religious_affiliation") else ""
        religiosity_level = user_data.get("self_religiosity_level", "").lower() if user_data.get("self_religiosity_level") else ""
        
        # שלב 1: זיהוי זהות דתית/אתנית מ-self_religious_affiliation
        # ברירת מחדל: יהודי (אם אין מידע)
        is_jewish = True  
        is_muslim = False
        is_christian = False  
        is_druze = False
        
        if religious_affiliation:
            if "יהודי" in religious_affiliation or "jewish" in religious_affiliation:
                is_jewish = True
            elif "ערבי" in religious_affiliation:
                is_jewish = False
                if "נוצרי" in religious_affiliation or "christian" in religious_affiliation:
                    is_christian = True  # ערבי נוצרי מפורש
                else:
                    is_muslim = True     # ערבי ללא פירוט → מוסלמי (ברירת מחדל)
            elif "דרוזי" in religious_affiliation or "druze" in religious_affiliation:
                is_jewish = False
                is_druze = True
            elif "נוצרי" in religious_affiliation or "christian" in religious_affiliation:
                is_jewish = False 
                is_christian = True
            elif "אתאיסט" in religious_affiliation or "atheist" in religious_affiliation:
                is_jewish = True  # אתאיסט = יהודי חילוני
            elif "שומרוני" in religious_affiliation:
                is_jewish = True  # שומרוני נחשב יהודי לצורך חגים
        
        # שלב 2: זיהוי רמת דתיות מ-self_religiosity_level + ברירות מחדל חכמות
        is_religious = False  # דתי/חרדי/מסורתי (יקבל צומות)
        is_secular = True     # חילוני/לא דתי (לא יקבל צומות)
        
        if religiosity_level:
            if any(word in religiosity_level for word in ["דתי", "חרדי", "מסורתי", "שומר מסורת", "דתי לאומי"]):
                is_religious = True  
                is_secular = False
            elif any(word in religiosity_level for word in ["חילוני", "לא דתי"]):
                is_secular = True
                is_religious = False
        else:
            # ברירות מחדל כשאין מידע על רמת דתיות:
            if is_jewish:
                # יהודי ללא מידע → חילוני (ברירת מחדל)
                is_secular = True
                is_religious = False
            elif is_druze:
                # דרוזי ללא מידע → דתי (רוב המשפחות דתיות)
                is_secular = False
                is_religious = True
            elif is_muslim or is_christian:
                # מוסלמי/נוצרי ללא מידע → נניח שמחגגים חגים
                is_secular = False
                is_religious = True
        
        now = get_israel_time()
        today_str = now.strftime("%Y-%m-%d")
        
        # קריאת הטבלה מהקובץ
        try:
            events_file = os.path.join(os.path.dirname(__file__), "special_events.json")
            with open(events_file, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"לא ניתן לקרוא קובץ special_events.json: {e}")
            return ""
        
        # מציאת אירועים רלוונטיים לתאריך היום
        relevant_events = []
        for event in events_data:
            if event["date"] == today_str:
                audience = event["audience"]
                
                # בדיקת התאמה לזהות דתית ורמת דתיות של המשתמש
                should_include = False
                
                if audience == "all":
                    should_include = True
                elif audience == "jewish_family" and is_jewish:
                    # חגים יהודיים - לכל היהודים (דתיים וחילוניים)
                    should_include = True
                elif audience == "jewish_fast" and is_jewish and is_religious:
                    # צומות יהודיים - רק ליהודים דתיים/מסורתיים/חרדים
                    should_include = True
                elif audience == "muslim" and is_muslim:
                    # חגים מוסלמיים - לכל המוסלמים
                    should_include = True
                elif audience == "christian" and is_christian:
                    # חגים נוצריים - לכל הנוצרים
                    should_include = True
                elif audience == "druze" and is_druze:
                    # חגים דרוזיים - לכל הדרוזים
                    should_include = True
                elif audience == "lgbtq":  
                    # חודש הגאווה - אירוע כללי לכולם
                    should_include = True
                elif audience == "mixed":
                    # אירועים מעורבים - לכולם
                    should_include = True
                
                if should_include:
                    relevant_events.append(event)
        
        # יצירת הודעות
        if relevant_events:
            messages = []
            for event in relevant_events:
                suggestion = event["suggestion"]
                event_name = event["event"]
                messages.append(f"שים לב: היום {event_name}. {suggestion}")
            
            return " ".join(messages)
        
        return ""
        
    except Exception as e:
        logging.error(f"שגיאה בבדיקת חגים דתיים: {e}")
        return ""

def clean_old_logs() -> None:  # מנקה לוגים ישנים
    try:
        files_to_clean = [BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME]
        for file_name in files_to_clean:
            file_path = os.path.join(DATA_DIR, file_name)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                if len(lines) > MAX_OLD_LOG_LINES:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines[-MAX_OLD_LOG_LINES:])
                if should_log_debug_prints():
                    logging.info(f"נוקה קובץ: {file_name}")
    except Exception as e:
        logging.error(f"שגיאה בניקוי לוגים: {e}")

def health_check() -> dict:  # בדיקת תקינות המערכת
    from config import check_config_sanity
    from notifications import send_error_notification
    health = {"config_loaded": False, "sheets_connected": False, "openai_connected": False, "log_files_writable": False}
    try:
        check_config_sanity()
        health["config_loaded"] = True
        from sheets_handler import sheet_users, sheet_log
        health["sheets_connected"] = True
        try:  # בדיקת חיבור ל־OpenAI/LiteLLM
            from gpt_utils import measure_llm_latency
            with measure_llm_latency("gpt-3.5-turbo"):
                response = litellm.completion(model="gpt-3.5-turbo", messages=[{"role": "user", "content": "test"}], max_tokens=5, temperature=0)
            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                health["openai_connected"] = True
        except Exception:
            health["openai_connected"] = False
        # בדיקת כתיבה לקבצים
        test_log = {"test": "health_check", "timestamp": get_israel_time().isoformat()}
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

def format_error_message(error: Exception, context: str = "") -> str:  # מעצב הודעת שגיאה בצורה ברורה
    try:
        error_msg = f"🚨 שגיאה"
        if context:
            error_msg += f" ב{context}"
        error_msg += f":\n"
        error_msg += f"📍 סוג: {type(error).__name__}\n"
        error_msg += f"💬 הודעה: {str(error)}\n"
        error_msg += f"⏰ זמן: {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}\n"
        # הוספת traceback רק בdebug mode
        if should_log_debug_prints():
            tb = traceback.format_exc()
            if len(tb) > MAX_TRACEBACK_LENGTH:
                tb = tb[:MAX_TRACEBACK_LENGTH] + "... (truncated)"
            error_msg += f"🔧 פרטים טכניים:\n{tb}"
        return error_msg
    except:
        return f"🚨 שגיאה בעיצוב הודעת שגיאה: {str(error)}"

def log_error_stat(error_type: str) -> None:  # מעדכן קובץ errors_stats.json עם ספירה לכל error_type
    try:
        stats_path = os.path.join(DATA_DIR, "errors_stats.json")
        try:
            with open(stats_path, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            stats = {}
        stats[error_type] = stats.get(error_type, 0) + 1
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"שגיאה בעדכון סטטיסטיקת שגיאות: {e}")

def send_error_stats_report():  # שולח דוח שגיאות מצטבר לאדמין
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

def send_usage_report(days_back: int = 1):  # שולח דוח usage יומי/שבועי לאדמין
    from datetime import timedelta
    from notifications import send_admin_notification
    if not os.path.exists(gpt_log_path):
        send_admin_notification("אין לוג usage זמין.")
        return
    try:
        users = set()
        messages = 0
        errors = 0
        now = get_israel_time()
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

def update_last_bot_message(chat_id, bot_summary):  # מעדכן את השדה 'bot' של השורה האחרונה בהיסטוריה
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

def add_to_chat_history(user_id, user_message, bot_response):
    """מוסיף הודעה להיסטוריית הצ'אט"""
    try:
        # קובץ ההיסטוריה
        history_file = "data/chat_history.json"
        
        # טוען את הנתונים הקיימים או יוצר קובץ חדש
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = {}
        
        # יוצר רשומה למשתמש אם לא קיימת
        if str(user_id) not in history:
            history[str(user_id)] = {
                "am_context": "",
                "history": []
            }
        
        # מוסיף את ההודעה החדשה
        new_entry = {
            "user": user_message,
            "bot": bot_response,
            "timestamp": get_israel_time().isoformat()
        }
        
        history[str(user_id)]["history"].append(new_entry)
        
        # שומר את הנתונים
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            
        logging.info(f"💾 נוספה הודעה להיסטוריה עבור משתמש {user_id}")
        
    except Exception as e:
        logging.error(f"❌ שגיאה בהוספת הודעה להיסטוריה: {e}")

def get_chat_history(user_id, limit=None):
    """מחזיר את ההיסטוריה של משתמש מסוים"""
    try:
        history_file = "data/chat_history.json"
        
        if not os.path.exists(history_file):
            return []
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        user_history = history.get(str(user_id), {}).get("history", [])
        
        if limit:
            return user_history[-limit:]
        
        return user_history
        
    except Exception as e:
        logging.error(f"❌ שגיאה בקריאת היסטוריה: {e}")
        return []

def format_chat_history_for_gpt(user_id, limit=10):
    """מעצב את היסטוריית הצ'אט בפורמט מתאים ל-GPT"""
    history = get_chat_history(user_id, limit)
    
    if not history:
        return ""
    
    formatted_history = "היסטוריית שיחות קודמות:\n"
    for entry in history[-limit:]:  # לוקח את ה-limit אחרונות
        formatted_history += f"משתמש: {entry['user']}\n"
        formatted_history += f"בוט: {entry['bot']}\n"
        formatted_history += f"זמן: {entry['timestamp']}\n---\n"
    
    return formatted_history

def cleanup_test_users():
    """מנקה משתמשי בדיקה מקבצי הנתונים"""
    test_users = ['demo_user_6am', 'working_test_user', 'friday_morning_user', 'timestamp_test']
    
    # ניקוי מקובץ ההיסטוריה
    try:
        history_file = "data/chat_history.json"
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            for test_user in test_users:
                if test_user in history:
                    del history[test_user]
                    logging.info(f"🗑️ הוסר משתמש בדיקה {test_user} מהיסטוריית הצ'אט")
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"❌ שגיאה בניקוי היסטוריית הצ'אט: {e}")
    
    # ניקוי מקובץ התזכורות
    try:
        reminder_file = "data/reminder_state.json"
        if os.path.exists(reminder_file):
            with open(reminder_file, 'r', encoding='utf-8') as f:
                reminders = json.load(f)
            
            for test_user in test_users:
                if test_user in reminders:
                    del reminders[test_user]
                    logging.info(f"🗑️ הוסר משתמש בדיקה {test_user} ממערכת התזכורות")
            
            with open(reminder_file, 'w', encoding='utf-8') as f:
                json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"❌ שגיאה בניקוי מערכת התזכורות: {e}")

SECRET_CODES = {  # פקודות סודיות
    "#487chaCha2025": "clear_history",    # מוחק היסטוריית שיחה
    "#512SheetBooM": "clear_sheets",      # מוחק מידע מהגיליונות
    "#734TotalZap": "clear_all",          # מוחק הכל (היסטוריה + גיליונות)
    "#999PerformanceCheck": "performance_info",  # מידע על ביצועים ו-cache
    "#888ResetCache": "reset_cache",      # איפוס cache של Google Sheets
}

def handle_secret_command(chat_id, user_msg):  # טיפול בפקודות סודיות למטרות בדיקה ותחזוקה
    action = SECRET_CODES.get(user_msg.strip())
    if not action:
        return False, None
    if action == "clear_history":
        cleared = clear_chat_history(chat_id)
        msg = "🧹 כל ההיסטוריה שלך נמחקה!" if cleared else "🤷‍♂️ לא נמצאה היסטוריה למחיקה."
        log_event_to_file({"event": "secret_command", "timestamp": get_israel_time().isoformat(), "chat_id": chat_id, "action": "clear_history", "result": cleared})
        _send_admin_secret_notification(f"❗ הופעל קוד סודי למחיקת היסטוריה בצ'אט {chat_id}.")
        return True, msg
    if action == "clear_sheets":
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "🗑️ כל הנתונים שלך נמחקו מהגיליונות!" if (deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא מידע למחיקה בגיליונות."
        log_event_to_file({"event": "secret_command", "timestamp": get_israel_time().isoformat(), "chat_id": chat_id, "action": "clear_sheets", "deleted_sheet": deleted_sheet, "deleted_state": deleted_state})
        _send_admin_secret_notification(f"❗ הופעל קוד סודי למחיקת נתונים בגיליונות בצ'אט {chat_id}.")
        return True, msg
    if action == "clear_all":
        cleared = clear_chat_history(chat_id)
        deleted_sheet, deleted_state = clear_from_sheets(chat_id)
        msg = "💣 הכל נמחק! (היסטוריה + גיליונות)" if (cleared or deleted_sheet or deleted_state) else "🤷‍♂️ לא נמצא שום מידע למחיקה."
        log_event_to_file({"event": "secret_command", "timestamp": get_israel_time().isoformat(), "chat_id": chat_id, "action": "clear_all", "cleared_history": cleared, "deleted_sheet": deleted_sheet, "deleted_state": deleted_state})
        _send_admin_secret_notification(f"❗ הופעל קוד סודי למחיקת **הכל** בצ'אט {chat_id}.")
        return True, msg
    
    if action == "performance_info":
        try:
            from config import get_sheets_cache_info
            from gpt_a_handler import get_filter_analytics
            
            cache_info = get_sheets_cache_info()
            filter_analytics = get_filter_analytics()
            
            msg = f"📊 **דוח ביצועים:**\n\n"
            msg += f"🗂️ **Google Sheets Cache:**\n"
            msg += f"• סטטוס: {cache_info['status']}\n"
            msg += f"• גיל: {cache_info['age_seconds']} שניות\n\n"
            msg += f"🎯 **GPT Model Filter:**\n"
            msg += f"• סך החלטות: {filter_analytics.get('total_decisions', 0)}\n"
            msg += f"• שימוש מודל מתקדם: {filter_analytics.get('premium_usage', 0)}%\n"
            msg += f"• פילוח: {filter_analytics.get('percentages', {})}\n\n"
            msg += f"💡 **טיפים לשיפור ביצועים:**\n"
            msg += f"• Cache חוסך ~2-3 שניות בכל גישה\n"
            msg += f"• המודל המהיר חוסך ~40% בעלויות\n"
            msg += f"• מקביליות GPT-B+GPT-C חוסכת ~3-5 שניות"
            
            _send_admin_secret_notification(f"ℹ️ הופעל קוד סודי לדוח ביצועים בצ'אט {chat_id}.")
            return True, msg
        except Exception as e:
            return True, f"❌ שגיאה בקבלת מידע ביצועים: {e}"
    
    if action == "reset_cache":
        try:
            from config import reset_sheets_cache
            reset_sheets_cache()
            msg = "🔄 Cache של Google Sheets אופס בהצלחה!\nהגישה הבאה תיצור חיבור חדש."
            _send_admin_secret_notification(f"🔄 הופעל קוד סודי לאיפוס cache בצ'אט {chat_id}.")
            return True, msg
        except Exception as e:
            return True, f"❌ שגיאה באיפוס cache: {e}"

    return False, None

def clear_chat_history(chat_id):  # מוחק היסטוריית צ'אט ספציפי
    path = CHAT_HISTORY_PATH
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
        logging.error(f"[ERROR-clear_chat_history] {e} | chat_id={chat_id}")
        log_event_to_file({"event": "clear_history_error", "chat_id": chat_id, "error": str(e)})
        return False

def clear_from_sheets(chat_id):  # מוחק נתוני משתמש מהגיליונות
    from sheets_handler import delete_row_by_chat_id
    deleted_sheet = delete_row_by_chat_id(sheet_name=config["SHEET_USER_TAB"], chat_id=chat_id)
    deleted_state = delete_row_by_chat_id(sheet_name=config["SHEET_STATES_TAB"], chat_id=chat_id)
    return deleted_sheet, deleted_state

def _send_admin_secret_notification(message: str):  # שולח הודעה לאדמין על שימוש בקוד סודי
    try:
        from notifications import send_admin_secret_command_notification
        send_admin_secret_command_notification(message)
    except Exception as e:
        logging.error(f"💥 שגיאה בשליחת התראת קוד סודי: {e}")

def show_log_status():  # מציג את מצב הלוגים הנוכחי
    try:
        from config import (ENABLE_DEBUG_PRINTS, ENABLE_GPT_COST_DEBUG, ENABLE_SHEETS_DEBUG, ENABLE_PERFORMANCE_DEBUG, ENABLE_MESSAGE_DEBUG, ENABLE_DATA_EXTRACTION_DEBUG, DEFAULT_LOG_LEVEL)
        print(f"\n🎛️  מצב לוגים: {DEFAULT_LOG_LEVEL}")
        print(f"🐛 דיבאג: {'✅' if ENABLE_DEBUG_PRINTS else '❌'} | 💰 GPT: {'✅' if ENABLE_GPT_COST_DEBUG else '❌'} | 📋 נתונים: {'✅' if ENABLE_DATA_EXTRACTION_DEBUG else '❌'}")
        print(f"⏱️  ביצועים: {'✅' if ENABLE_PERFORMANCE_DEBUG else '❌'} | 💬 הודעות: {'✅' if ENABLE_MESSAGE_DEBUG else '❌'} | 📊 גיליונות: {'✅' if ENABLE_SHEETS_DEBUG else '❌'}")
    except ImportError as e:
        print(f"❌ שגיאת import: {e}")
    except Exception as e:
        print(f"❌ שגיאה: {e}")

def show_gpt_input_examples():  # דוגמאות למה ש-GPT מקבל כקלט
    print("🤖 מבנה GPT: System + User Info + Context + 15 זוגות הודעות + הודעה חדשה")

def show_personal_connection_examples():  # דוגמאות להצעות החיבור האישי
    print("🧠 הצעות חיבור: אחרי 4+ שעות | משפחה (3+), לחץ (2+), עבודה (3+) | זמנים מיוחדים")



# אם מפעילים את utils.py ישירות
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "cleanup-test":
            cleanup_test_users()
            print("✅ ניקוי משתמשי בדיקה הושלם")
        elif command == "clean-old-errors":
            print("🧹 מנקה שגיאות ישנות...")
            try:
                from notifications import clear_old_critical_error_users
                removed_count = clear_old_critical_error_users()
                print(f"✅ הוסרו {removed_count} שגיאות ישנות")
            except Exception as e:
                print(f"❌ שגיאה: {e}")
        else:
            print(f"❌ פקודה לא ידועה: {command}")
            print("פקודות זמינות:")
            print("  cleanup-test - ניקוי משתמשי בדיקה")
            print("  clean-old-errors - ניקוי שגיאות ישנות")
    else:
        print("שימוש: python utils.py [פקודה]")
        print("פקודות זמינות:")
        print("  cleanup-test - ניקוי משתמשי בדיקה")
        print("  clean-old-errors - ניקוי שגיאות ישנות")
