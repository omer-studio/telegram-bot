"""פונקציות עזר כלליות לבוט."""
import json
import os
import traceback
from datetime import datetime, timedelta
import requests
import time
import logging
from config import BOT_TRACE_LOG_PATH, CHAT_HISTORY_PATH, gpt_log_path, BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME, DATA_DIR, MAX_LOG_LINES_TO_KEEP, MAX_OLD_LOG_LINES, MAX_CHAT_HISTORY_MESSAGES, MAX_TRACEBACK_LENGTH, config
from config import should_log_debug_prints, should_log_message_debug, should_log_sheets_debug
import litellm
import pytz
import asyncio
from typing import Dict, Any, List, Tuple

# === Global control flags ===
# אם True – לא נשלחות התראות אדמין אוטומטיות מתוך update_user_profile_fast
_disable_auto_admin_profile_notification: bool = False

def get_israel_time():
    """מחזיר את הזמן הנוכחי בישראל"""
    israel_tz = pytz.timezone('Asia/Jerusalem')
    return datetime.now(israel_tz)

def log_event_to_file(event_data, filename=None):  # ללוג JSON
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

def update_chat_history(chat_id, user_msg, bot_summary):  # עדכון היסטוריה
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

def get_chat_history_messages(chat_id: str, limit: int = None) -> list:  # היסטוריה GPT
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

def get_user_stats_and_history(chat_id: str) -> tuple[dict, list]:  # סטטיסטיקות + היסטוריה
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

def get_user_stats(chat_id: str) -> dict:  # סטטיסטיקות משתמש
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
            greeting_guide = "תפתח בברכה 'בוקר טוב🤍' וביטוי של אנרגיה חיובית לתחילת היום"
        elif 11 <= hour < 16:
            greeting_guide = "תפתח בברכה 'צהריים טובים🤍' והתייחס לקצב היום או מה שקורה בשעות האלה"
        elif 16 <= hour < 18:
            greeting_guide = "תפתח בברכה 'אחר הצהריים טובים🤍' "
        elif 18 <= hour < 21:
            greeting_guide = "תפתח בברכה 'ערב טוב🤍' והתייחס לסיום היום או לתוכניות הערב"
        elif 21 <= hour < 24:
            greeting_guide = "תפתח בברכה 'לילה טוב🤍' ותשאל איך עבר היום - תהיה יותר רגוע ונעים"
        else:  # 0-5
            greeting_guide = "תפתח בברכה 'לילה טוב🤍' ותהיה מבין שזה שעת לילה מאוחרת אחרי חצות, שאל אם הכל בסדר"
            
        return f"{greeting_guide}. כן באמצע השיחה התייחס לזמן בצורה טבעית ורלוונטית."
        
    except Exception as e:
        logging.error(f"שגיאה בהנחיות ברכה: {e}")
        return "תפתח בברכה מתאימה לזמן והתייחס לשעה בצורה טבעית."

def get_weekday_context_instruction(chat_id: str | None = None, user_msg: str | None = None) -> str:
    """מחזיר הנחיה ספציפית לכל יום בשבוע.

    שיקול חדש (2025-06-28):
    ────────────────────────
    • אם המשתמש הזכיר כבר היום (יום מתחיל ב-05:00) אחת ממילות הימים
      ["שבת", "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי"],
      אין צורך לשלוח שוב את ההנחיה – הפונקציה תחזיר מחרוזת ריקה.
    • אם chat_id או user_msg לא ניתנו, נשמרת התנהגות קודמת (תמיד שולח).
    """
    try:
        # שמות ימי השבוע לבדיקה
        weekday_words = ["שבת", "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי"]

        # לא מזכירים יום-שבוע מחוץ לטווח 05:00-23:00
        if now.hour >= 23 or now.hour < 5:
            return ""

        # אם חסר chat_id או user_msg – ברירת מחדל
        smart_skip = False
        if chat_id is not None:
            now = get_israel_time()

            # קביעת התחלת היום (05:00). אם לפני 05:00 – שייך ליום הקודם.
            start_of_day = now.replace(hour=5, minute=0, second=0, microsecond=0)
            if now.hour < 5:
                start_of_day = start_of_day - timedelta(days=1)

            # 1) בדיקת ההודעה הנוכחית
            if user_msg and any(word in user_msg for word in weekday_words):
                smart_skip = True
            else:
                # 2) בדיקת היסטוריה של היום הנוכחי
                try:
                    with open(CHAT_HISTORY_PATH, encoding="utf-8") as f:
                        history_data = json.load(f)
                    history = history_data.get(str(chat_id), {}).get("history", [])
                except (FileNotFoundError, json.JSONDecodeError):
                    history = []

                for entry in reversed(history):  # מהר לענייו – סורק מהסוף
                    ts = entry.get("timestamp")
                    if not ts:
                        continue
                    try:
                        entry_dt = datetime.fromisoformat(ts)
                    except ValueError:
                        continue
                    # עוצר אם יצאנו מהיום הנוכחי
                    if entry_dt < start_of_day:
                        break
                    # בודק רק הודעות משתמש
                    if any(word in entry.get("user", "") for word in weekday_words):
                        smart_skip = True
                        break

        if smart_skip:
            return ""

        # ––– בניית הנחיה כבעבר –––
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
                
                # בדיקת התאמה דתית
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

def format_error_message(error: Exception, context: str = "") -> str:  # הודעת שגיאה
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

def log_error_stat(error_type: str) -> None:  # רישום שגיאה
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

def send_error_stats_report():  # דוח שגיאות
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

def send_usage_report(days_back: int = 1):  # דוח שימוש
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

def update_last_bot_message(chat_id, bot_summary):  # עדכון הודעה אחרונה
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

# הפונקציות get_chat_history ו-format_chat_history_for_gpt הוסרו
# כי הן כפולות לפונקציה get_chat_history_messages שקיימת כבר

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

def handle_secret_command(chat_id, user_msg):  # פקודות בדיקה ותחזוקה
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

def clear_from_sheets(chat_id):  # מחיקת נתונים
    from sheets_handler import delete_row_by_chat_id
    deleted_sheet = delete_row_by_chat_id(sheet_name=config["SHEET_USER_TAB"], chat_id=chat_id)
    deleted_state = delete_row_by_chat_id(sheet_name=config["SHEET_STATES_TAB"], chat_id=chat_id)
    return deleted_sheet, deleted_state

def _send_admin_secret_notification(message: str):  # התראת קוד סודי
    try:
        from notifications import send_admin_secret_command_notification
        send_admin_secret_command_notification(message)
    except Exception as e:
        logging.error(f"💥 שגיאה בשליחת התראת קוד סודי: {e}")

def show_log_status():  # מצב לוגים
    try:
        from config import (ENABLE_DEBUG_PRINTS, ENABLE_GPT_COST_DEBUG, ENABLE_SHEETS_DEBUG, ENABLE_PERFORMANCE_DEBUG, ENABLE_MESSAGE_DEBUG, ENABLE_DATA_EXTRACTION_DEBUG, DEFAULT_LOG_LEVEL)
        print(f"\n🎛️  מצב לוגים: {DEFAULT_LOG_LEVEL}")
        print(f"🐛 דיבאג: {'✅' if ENABLE_DEBUG_PRINTS else '❌'} | 💰 GPT: {'✅' if ENABLE_GPT_COST_DEBUG else '❌'} | 📋 נתונים: {'✅' if ENABLE_DATA_EXTRACTION_DEBUG else '❌'}")
        print(f"⏱️  ביצועים: {'✅' if ENABLE_PERFORMANCE_DEBUG else '❌'} | 💬 הודעות: {'✅' if ENABLE_MESSAGE_DEBUG else '❌'} | 📊 גיליונות: {'✅' if ENABLE_SHEETS_DEBUG else '❌'}")
    except ImportError as e:
        print(f"❌ שגיאת import: {e}")
    except Exception as e:
        print(f"❌ שגיאה: {e}")

# הפונקציות show_gpt_input_examples ו-show_personal_connection_examples הוסרו
# כי הן פונקציות debug מיותרות

# 🚀 מערכת ניהול פרופילים מהירה - עדכון כפול אוטומטי
def get_user_profile_fast(chat_id: str) -> Dict[str, Any]:
    """קריאה מהירה מקובץ user_profiles.json נפרד"""
    try:
        from config import USER_PROFILES_PATH
        with open(USER_PROFILES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get(str(chat_id), {})
    except:
        return {}

def update_user_profile_fast(chat_id: str, updates: Dict[str, Any]):
    """עדכון מהיר - מקור אחד של אמת"""
    try:
        # 1. קריאת הפרופיל הנוכחי לזיהוי שינויים
        old_profile = get_user_profile_fast(chat_id)
        
        # 2. יצירת הפרופיל החדש
        new_profile = old_profile.copy()
        new_profile.update(updates)
        
        # 3. זיהוי שינויים
        changes = _detect_profile_changes(old_profile, new_profile)
        
        # --- שליחת התראת אדמין על כל שינוי (אם לא מושבת) ---
        if changes and not _disable_auto_admin_profile_notification:
            try:
                _send_admin_profile_change_notification(chat_id, changes)
            except Exception as _notify_e:
                logging.error(f"Failed to send admin profile change notification: {_notify_e}")
        
        # 4. עדכון מיידי בקובץ פרופילים נפרד (המקור היחיד של האמת)
        _update_user_profiles_file(chat_id, updates)
        
        # 5. רישום שינויים להיסטוריית הצ'אט
        if changes:
            _log_profile_changes_to_chat_history(chat_id, changes)
        
        # 6. Google Sheets מתעדכן מהקובץ המקומי (ברקע)
        asyncio.create_task(_sync_local_to_sheets_background(chat_id))
        
    except Exception as e:
        logging.error(f"שגיאה בעדכון פרופיל מהיר: {e}")
        # עדכון בסיסי ללא זיהוי שינויים במקרה של שגיאה
        _update_user_profiles_file(chat_id, updates)
        asyncio.create_task(_sync_local_to_sheets_background(chat_id))

def _update_user_profiles_file(chat_id: str, updates: Dict[str, Any]):
    """עדכון קובץ user_profiles.json נפרד"""
    try:
        from config import USER_PROFILES_PATH
        
        # קריאה
        try:
            with open(USER_PROFILES_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        
        # עדכון
        chat_id_str = str(chat_id)
        if chat_id_str not in data:
            data[chat_id_str] = {}
        
        data[chat_id_str].update(updates)
        data[chat_id_str]["last_update"] = get_israel_time().isoformat()
        
        # שמירה
        with open(USER_PROFILES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logging.error(f"שגיאה בעדכון קובץ פרופילים: {e}")

def _update_chat_history_profile(chat_id: str, updates: Dict[str, Any]):
    """הוספת profile לקובץ chat_history.json הקיים - נשאר לתאימות לאחור"""
    try:
        # קריאה
        with open(CHAT_HISTORY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {}
    
    # עדכון
    if str(chat_id) not in data:
        data[str(chat_id)] = {"am_context": "", "history": [], "profile": {}}
    
    if "profile" not in data[str(chat_id)]:
        data[str(chat_id)]["profile"] = {}
    
    data[str(chat_id)]["profile"].update(updates)
    data[str(chat_id)]["last_updated"] = get_israel_time().isoformat()
    
    # שמירה
    with open(CHAT_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def _sync_local_to_sheets_background(chat_id: str):
    """מסנכרן את הקובץ המקומי ל-Google Sheets לפי שמות כותרות (לא מיקום!)"""
    try:
        # קריאה מהקובץ המקומי (המקור היחיד של האמת)
        local_profile = get_user_profile_fast(chat_id)
        
        if not local_profile:
            logging.warning(f"אין נתונים מקומיים למשתמש {chat_id}")
            return
        
        # עדכון Google Sheets מהנתונים המקומיים
        from sheets_core import setup_google_sheets, find_chat_id_in_sheet
        
        gc, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        # ✅ עדכון פרופיל בגיליון משתמשים - לפי כותרות!
        await _sync_to_sheet_by_headers(sheet_users, chat_id, local_profile)
        
        # ✅ עדכון בגיליון מצבים - לפי כותרות!
        await _sync_to_sheet_by_headers(sheet_states, chat_id, local_profile)
        
        logging.info(f"✅ Google Sheets סונכרן מהקובץ המקומי עבור משתמש {chat_id}")
        
    except Exception as e:
        logging.error(f"שגיאה בסנכרון ל-Google Sheets: {e}")
        # הבוט ממשיך לעבוד גם אם Google Sheets נכשל

async def _sync_to_sheet_by_headers(sheet, chat_id: str, local_profile: Dict[str, Any]):
    """מסנכרן נתונים לגיליון לפי שמות כותרות (לא מיקום עמודות!)"""
    try:
        # קריאת כל הנתונים כולל כותרות
        all_values = sheet.get_all_values()
        
        if not all_values or len(all_values) < 1:
            logging.warning(f"גיליון ריק או ללא כותרות")
            return
        
        # שורה ראשונה = כותרות
        headers = all_values[0]
        
        # מציאת אינדקס עמודת chat_id
        chat_id_col = None
        for i, header in enumerate(headers):
            if header.lower() == "chat_id":
                chat_id_col = i + 1  # gspread uses 1-based indexing
                break
        
        if not chat_id_col:
            logging.warning(f"לא נמצאה עמודת chat_id בגיליון")
            return
        
        # מציאת השורה של המשתמש
        from sheets_core import find_chat_id_in_sheet
        row_index = find_chat_id_in_sheet(sheet, chat_id, col=chat_id_col)
        
        # אם המשתמש לא קיים, יוצרים שורה חדשה
        if not row_index:
            row_index = len(all_values) + 1
            sheet.update_cell(row_index, chat_id_col, chat_id)
        
        # מיפוי דינמי של שדות לעמודות לפי כותרות
        field_to_col = {}
        for i, header in enumerate(headers):
            field_to_col[header.lower()] = i + 1  # gspread uses 1-based indexing
        
        # עדכון כל השדות מהקובץ המקומי לפי כותרות
        for field, value in local_profile.items():
            # חיפוש העמודה לפי שם השדה
            col_index = None
            
            # חיפוש ישיר
            if field.lower() in field_to_col:
                col_index = field_to_col[field.lower()]
            
            # חיפוש עם וריאציות נפוצות
            elif field == "summary" and "summary" in field_to_col:
                col_index = field_to_col["summary"]
            elif field == "last_update" and "last_update" in field_to_col:
                col_index = field_to_col["last_update"]
            elif field == "code_try" and "code_try" in field_to_col:
                col_index = field_to_col["code_try"]
            elif field == "gpt_c_run_count" and "gpt_c_run_count" in field_to_col:
                col_index = field_to_col["gpt_c_run_count"]
            
            # עדכון התא אם נמצאה העמודה
            if col_index:
                try:
                    sheet.update_cell(row_index, col_index, str(value))
                    logging.debug(f"עודכן שדה {field} בעמודה {col_index} עבור משתמש {chat_id}")
                except Exception as e:
                    logging.warning(f"שגיאה בעדכון שדה {field}: {e}")
        
        logging.info(f"✅ סונכרן פרופיל למשתמש {chat_id} לפי כותרות")
        
    except Exception as e:
        logging.error(f"שגיאה בסנכרון לפי כותרות: {e}")

def get_user_summary_fast(chat_id: str) -> str:
    """קריאה מהירה של סיכום משתמש מקובץ chat_history.json"""
    try:
        profile = get_user_profile_fast(chat_id)
        return profile.get("summary", "")
    except:
        return ""

def update_user_summary_fast(chat_id: str, summary: str):
    """עדכון מהיר של סיכום משתמש"""
    update_user_profile_fast(chat_id, {"summary": summary})

def increment_code_try_fast(chat_id: str) -> int:
    """הגדלה מהירה של מספר ניסיונות קוד"""
    try:
        profile = get_user_profile_fast(chat_id)
        current_tries = profile.get("code_try", 0)
        new_tries = current_tries + 1
        update_user_profile_fast(chat_id, {"code_try": new_tries})
        return new_tries
    except:
        return 1

def increment_gpt_c_run_count_fast(chat_id: str) -> int:
    """הגדלה מהירה של מספר הרצות GPT-C"""
    try:
        profile = get_user_profile_fast(chat_id)
        current_count = profile.get("gpt_c_run_count", 0)
        new_count = current_count + 1
        update_user_profile_fast(chat_id, {"gpt_c_run_count": new_count})
        return new_count
    except:
        return 1

# 🎯 מערכת עדכון תעודת זהות רגשית מלאה
def update_emotional_identity_fast(chat_id: str, emotional_data: Dict[str, Any]):
    """
    מעדכן את כל שדות התעודת זהות הרגשית - מקור אחד של אמת
    """
    try:
        # 1. קריאת הפרופיל הנוכחי לזיהוי שינויים
        old_profile = get_user_profile_fast(chat_id)
        
        # 2. הוספת timestamp
        emotional_data["last_update"] = get_israel_time().isoformat()
        
        # 3. יצירת הפרופיל החדש
        new_profile = old_profile.copy()
        new_profile.update(emotional_data)
        
        # 4. זיהוי שינויים
        changes = _detect_profile_changes(old_profile, new_profile)
        
        # 5. עדכון מהיר בקובץ פרופילים נפרד (המקור היחיד של האמת)
        _update_user_profiles_file(chat_id, emotional_data)
        
        # 6. רישום שינויים להיסטוריית הצ'אט
        if changes:
            _log_profile_changes_to_chat_history(chat_id, changes)
        
        # 7. Google Sheets מתעדכן מהקובץ המקומי (ברקע)
        asyncio.create_task(_sync_local_to_sheets_background(chat_id))
        
        logging.info(f"✅ תעודת זהות רגשית עודכנה עבור משתמש {chat_id}")
        return True
        
    except Exception as e:
        logging.error(f"שגיאה בעדכון תעודת זהות רגשית: {e}")
        # עדכון בסיסי ללא זיהוי שינויים במקרה של שגיאה
        emotional_data["last_update"] = get_israel_time().isoformat()
        _update_user_profiles_file(chat_id, emotional_data)
        asyncio.create_task(_sync_local_to_sheets_background(chat_id))
        return False

def get_emotional_identity_fast(chat_id: str) -> Dict[str, Any]:
    """קריאה מהירה של תעודת זהות רגשית מקובץ user_profiles.json נפרד"""
    return get_user_profile_fast(chat_id)

def ensure_emotional_identity_consistency(chat_id: str) -> bool:
    """
    מוודא שתעודת הזהות הרגשית זהה בשני המקומות
    מחזיר True אם הכל תקין, False אם יש אי התאמה
    """
    try:
        # קריאה מהקובץ המקומי
        local_profile = get_user_profile_fast(chat_id)
        
        # קריאה מ-Google Sheets (איטי יותר)
        from sheets_core import get_user_profile_data
        sheets_profile = get_user_profile_data(chat_id)
        
        # השוואה
        if local_profile == sheets_profile:
            logging.info(f"✅ תעודת זהות רגשית תואמת עבור משתמש {chat_id}")
            return True
        else:
            logging.warning(f"⚠️ אי התאמה בתעודת זהות רגשית עבור משתמש {chat_id}")
            logging.warning(f"מקומי: {local_profile}")
            logging.warning(f"Google Sheets: {sheets_profile}")
            return False
            
    except Exception as e:
        logging.error(f"שגיאה בבדיקת עקביות תעודת זהות רגשית: {e}")
        return False

def get_all_emotional_identity_fields() -> List[str]:
    """מחזיר את כל שדות התעודת זהות הרגשית"""
    return [
        "summary", "age", "pronoun_preference", "occupation_or_role", "attracted_to",
        "relationship_type", "self_religious_affiliation", "self_religiosity_level",
        "family_religiosity", "closet_status", "who_knows", "who_doesnt_know",
        "attends_therapy", "primary_conflict", "trauma_history", "goal_in_course",
        "language_of_strength", "date_first_seen", "coping_strategies", "fears_concerns",
        "future_vision", "other_insights", "last_update", "code_try", "gpt_c_run_count"
    ]

def validate_emotional_identity_data(emotional_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    בודק שכל השדות הנדרשים קיימים ומתאימים
    מחזיר (תקין, רשימת שגיאות)
    """
    errors = []
    required_fields = get_all_emotional_identity_fields()
    
    # בדיקת שדות חובה
    for field in ["summary", "age", "last_update"]:
        if field not in emotional_data or not emotional_data[field]:
            errors.append(f"שדה חובה חסר: {field}")
    
    # בדיקת ערכים תקינים
    if "age" in emotional_data:
        try:
            age = int(emotional_data["age"])
            if age < 13 or age > 120:
                errors.append("גיל לא תקין (חייב להיות בין 13 ל-120)")
        except:
            errors.append("גיל חייב להיות מספר")
    
    # בדיקת אורך סיכום
    if "summary" in emotional_data and len(emotional_data["summary"]) > 1000:
        errors.append("סיכום ארוך מדי (מקסימום 1000 תווים)")
    
    return len(errors) == 0, errors

def force_sync_to_sheets(chat_id: str) -> bool:
    """
    מכריח סנכרון מלא ל-Google Sheets
    שימושי במקרה של אי התאמה או שגיאה
    """
    try:
        # קריאה מהקובץ המקומי
        local_profile = get_user_profile_fast(chat_id)
        
        if not local_profile:
            logging.warning(f"אין נתונים מקומיים למשתמש {chat_id}")
            return False
        
        # סנכרון כפוי
        asyncio.create_task(_sync_local_to_sheets_background(chat_id))
        
        logging.info(f"✅ סנכרון כפוי ל-Google Sheets עבור משתמש {chat_id}")
        return True
        
    except Exception as e:
        logging.error(f"שגיאה בסנכרון כפוי: {e}")
        return False

def cleanup_old_profiles(days_old: int = 90) -> int:
    """
    מנקה פרופילים ישנים שלא היו פעילים יותר מ-X ימים
    מחזיר מספר הפרופילים שנמחקו
    """
    try:
        from config import USER_PROFILES_PATH
        from datetime import datetime, timedelta
        
        # קריאת קובץ הפרופילים
        try:
            with open(USER_PROFILES_PATH, 'r', encoding='utf-8') as f:
                profiles_data = json.load(f)
        except:
            return 0
        
        # חישוב תאריך גבול
        cutoff_date = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        
        # בדיקת כל הפרופילים
        profiles_to_remove = []
        for chat_id, profile in profiles_data.items():
            last_update_str = profile.get("last_update", "")
            if last_update_str:
                try:
                    last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
                    if last_update < cutoff_date:
                        profiles_to_remove.append(chat_id)
                except:
                    # אם יש שגיאה בפרסור התאריך, נמחק
                    profiles_to_remove.append(chat_id)
        
        # מחיקת פרופילים ישנים
        for chat_id in profiles_to_remove:
            del profiles_data[chat_id]
            removed_count += 1
        
        # שמירה חזרה
        if removed_count > 0:
            with open(USER_PROFILES_PATH, 'w', encoding='utf-8') as f:
                json.dump(profiles_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"✅ נמחקו {removed_count} פרופילים ישנים (יותר מ-{days_old} ימים)")
        
        return removed_count
        
    except Exception as e:
        logging.error(f"שגיאה בניקוי פרופילים ישנים: {e}")
        return 0

def get_profiles_stats() -> Dict[str, Any]:
    """
    מחזיר סטטיסטיקות על קובץ הפרופילים
    """
    try:
        from config import USER_PROFILES_PATH
        
        try:
            with open(USER_PROFILES_PATH, 'r', encoding='utf-8') as f:
                profiles_data = json.load(f)
        except:
            profiles_data = {}
        
        total_profiles = len(profiles_data)
        
        # חישוב פרופילים פעילים (עדכון ב-30 ימים האחרונים)
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)
        active_profiles = 0
        
        for profile in profiles_data.values():
            last_update_str = profile.get("last_update", "")
            if last_update_str:
                try:
                    last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
                    if last_update > cutoff_date:
                        active_profiles += 1
                except:
                    pass
        
        return {
            "total_profiles": total_profiles,
            "active_profiles": active_profiles,
            "inactive_profiles": total_profiles - active_profiles,
            "file_size_mb": os.path.getsize(USER_PROFILES_PATH) / (1024 * 1024) if os.path.exists(USER_PROFILES_PATH) else 0
        }
        
    except Exception as e:
        logging.error(f"שגיאה בקבלת סטטיסטיקות פרופילים: {e}")
        return {}

def _detect_profile_changes(old_profile: Dict[str, Any], new_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """מזהה שינויים בין פרופיל ישן לחדש ומחזיר רשימת השינויים"""
    changes = []
    
    # בדיקת כל השדות בפרופיל החדש
    for field, new_value in new_profile.items():
        old_value = old_profile.get(field)
        
        # אם השדה לא היה קיים או השתנה
        if field not in old_profile:
            if new_value is not None and new_value != "":
                changes.append({
                    "field": field,
                    "old_value": None,
                    "new_value": new_value,
                    "change_type": "added"
                })
        elif old_value != new_value:
            changes.append({
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "change_type": "updated"
            })
    
    # בדיקת שדות שנמחקו
    for field in old_profile:
        if field not in new_profile:
            changes.append({
                "field": field,
                "old_value": old_profile[field],
                "new_value": None,
                "change_type": "removed"
            })
    
    return changes

def _log_profile_changes_to_chat_history(chat_id: str, changes: List[Dict[str, Any]]):
    """רושם שינויים בפרופיל להיסטוריית הצ'אט"""
    if not changes:
        return
    
    try:
        # טעינת היסטוריית הצ'אט
        with open(CHAT_HISTORY_PATH, encoding="utf-8") as f:
            history_data = json.load(f)
        
        chat_id = str(chat_id)
        if chat_id not in history_data:
            history_data[chat_id] = {"am_context": "", "history": []}
        
        # יצירת הודעה על השינויים
        now = get_israel_time()
        simple_timestamp = f"{now.day}/{now.month} {now.hour:02d}:{now.minute:02d}"
        
        change_messages = []
        for change in changes:
            if change["change_type"] == "added":
                change_messages.append(f"נוסף: {change['field']} = {change['new_value']}")
            elif change["change_type"] == "updated":
                change_messages.append(f"עודכן: {change['field']} מ-{change['old_value']} ל-{change['new_value']}")
            elif change["change_type"] == "removed":
                change_messages.append(f"הוסר: {change['field']} (היה: {change['old_value']})")
        
        if change_messages:
            profile_update_message = f"[עדכון פרופיל] {' | '.join(change_messages)}"
            
            # הוספה להיסטוריה
            history_data[chat_id]["history"].append({
                "user": "",
                "bot": profile_update_message,
                "timestamp": now.isoformat(),
                "time": simple_timestamp,
                "type": "profile_update"
            })
            
            # שמירה
            with open(CHAT_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            
            if should_log_message_debug():
                logging.info(f"שינויים בפרופיל נרשמו להיסטוריה: {chat_id}")
    
    except Exception as e:
        logging.error(f"שגיאה ברישום שינויים בפרופיל: {e}")

# מערכת tracking מורכבת הוסרה (7 פונקציות מיותרות)

# [מערכת tracking מורכבת נמחקה - חסכנו ~200 שורות]
def should_send_time_greeting(chat_id: str) -> bool:
    """קובע האם יש צורך לשלוח ברכת זמן (בוקר טוב/לילה טוב).

    כללים:
    1. אם אין היסטוריה ➜ True.
    2. אם עברו פחות מ־2 שעות מההודעה/תגובה האחרונה ➜ False (שיחה רציפה).
    3. אם עברו ≥2 שעות אבל בלוק הזמן (morning/afternoon/evening/night) לא השתנה ➜ False.
    4. אם עברו ≥2 שעות *וגם* עברנו לבלוק זמן חדש ➜ True.
    """
    try:
        from datetime import datetime, timedelta

        now = get_israel_time()

        # קריאת היסטוריה גולמית
        try:
            with open(CHAT_HISTORY_PATH, encoding="utf-8") as f:
                history_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history_data = {}

        chat_id_str = str(chat_id)
        last_timestamp = None

        if chat_id_str in history_data and history_data[chat_id_str].get("history"):
            last_entry = history_data[chat_id_str]["history"][-1]
            try:
                last_timestamp = datetime.fromisoformat(last_entry.get("timestamp"))
            except Exception:
                last_timestamp = None

        # 1) אין היסטוריה כלל
        if last_timestamp is None:
            return True

        hours_since = (now - last_timestamp).total_seconds() / 3600.0

        # 2) שיחה רציפה (<2h)
        if hours_since < 2:
            return False

        # 3) עברו ≥2h – נבדוק שינוי בלוק זמן
        current_block = _get_time_of_day(now.hour)
        previous_block = _get_time_of_day(last_timestamp.hour)

        return current_block != previous_block

    except Exception as e:
        logging.error(f"שגיאה ב-should_send_time_greeting: {e}")
        return False

# === Admin Notification for profile changes ===
def _send_admin_profile_change_notification(chat_id: str, changes: List[Dict[str, Any]]):
    """שולח התראת אדמין מפורטת על שינויים בפרופיל."""
    if not changes:
        return

    try:
        from notifications import send_admin_notification

        # בניית הודעה מפורטת
        lines = [f"📝 <b>עדכון פרופיל</b> למשתמש <code>{chat_id}</code>:"]

        for change in changes:
            field = change.get("field")
            old_val = change.get("old_value") if change.get("old_value") not in [None, ""] else "—"
            new_val = change.get("new_value") if change.get("new_value") not in [None, ""] else "—"
            change_type = change.get("change_type")

            if change_type == "added":
                lines.append(f"➕ <b>{field}</b>: '{new_val}' (חדש)")
            elif change_type == "updated":
                lines.append(f"✏️ <b>{field}</b>: '{old_val}' → '{new_val}'")
            elif change_type == "removed":
                lines.append(f"➖ <b>{field}</b>: '{old_val}' → נמחק")
            else:
                # fallback
                lines.append(f"🔄 <b>{field}</b>: '{old_val}' → '{new_val}'")

        # שליחה
        send_admin_notification("\n".join(lines))
    except Exception as e:
        logging.error(f"_send_admin_profile_change_notification failed: {e}")

# === Overview Notification combining GPT info and summary ===
def _send_admin_profile_overview_notification(
    *,
    chat_id: str,
    user_msg: str,
    changes: List[Dict[str, Any]],
    gpt_c_info: str,
    gpt_d_info: str,
    gpt_e_info: str,
    summary: str = ""
):
    """שולח הודעת אדמין אחת עם סיכום הריצה, הודעת המשתמש, ה-GPTים והסאמרי."""
    try:
        from notifications import send_admin_notification

        # כותרת + הודעת המשתמש
        lines: List[str] = []
        lines.append("🛠️ <b>עדכון פרופיל (GPT)</b>")
        lines.append(f"<b>משתמש:</b> <code>{chat_id}</code>")
        if user_msg:
            user_msg_trimmed = user_msg.strip()[:300]
            lines.append("<b>הודעת משתמש:</b>")
            lines.append(f"<i>{user_msg_trimmed}</i>")

        # פרטי GPT
        lines.append("")
        lines.append(gpt_c_info)
        lines.append(gpt_d_info)
        lines.append(gpt_e_info)

        # סאמרי
        if summary is not None:
            lines.append("")
            lines.append("<b>Summary:</b>")
            lines.append(f"{summary if summary else '—'}")

        # שינויים (אם יש)
        if changes:
            lines.append("")
            lines.append("<b>Fields Changed:</b>")
            for ch in changes:
                field = ch.get("field")
                old_val = ch.get("old_value") if ch.get("old_value") not in [None, ""] else "—"
                new_val = ch.get("new_value") if ch.get("new_value") not in [None, ""] else "—"
                change_type = ch.get("change_type")
                if change_type == "added":
                    lines.append(f"➕ {field}: '{new_val}' (חדש)")
                elif change_type == "updated":
                    lines.append(f"✏️ {field}: '{old_val}' → '{new_val}'")
                elif change_type == "removed":
                    lines.append(f"➖ {field}: '{old_val}' → נמחק")

        send_admin_notification("\n".join(lines))
    except Exception as e:
        logging.error(f"_send_admin_profile_overview_notification failed: {e}")

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
