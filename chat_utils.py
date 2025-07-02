"""chat_utils.py
=================
Chat history management, greeting helpers, health checks and miscellaneous
light-weight helpers that used to live in utils.py.  Keeping them here makes
`utils.py` much leaner while preserving backwards-compatibility (they will be
re-exported from utils).
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import re
import asyncio
import shutil

from config import (
    CHAT_HISTORY_PATH,
    MAX_CHAT_HISTORY_MESSAGES,
    BOT_TRACE_LOG_FILENAME,
    BOT_ERRORS_FILENAME,
    DATA_DIR,
    MAX_OLD_LOG_LINES,
    gpt_log_path,
    MAX_TRACEBACK_LENGTH,
)
from config import should_log_debug_prints, should_log_message_debug

# NOTE: circular import is safe here – utils only contains the base primitives
# we rely on (like `get_israel_time`).
import utils

__all__: List[str] = [
    # chat-history helpers
    "update_chat_history",
    "get_chat_history_messages",
    "get_user_stats_and_history",
    "get_user_stats",
    # context & greeting helpers
    "create_human_context_for_gpt",
    "get_time_greeting_instruction",
    "get_weekday_context_instruction",
    "should_send_time_greeting",
    # holiday / system helpers
    "get_holiday_system_message",
    # log / admin / health helpers
    "clean_old_logs",
    "health_check",
    "format_error_message",
    "log_error_stat",
    "send_error_stats_report",
    "send_usage_report",
    "update_last_bot_message",
    "cleanup_test_users",
]

# ---------------------------------------------------------------------------
# 📜 Chat-history helpers
# ---------------------------------------------------------------------------

def update_chat_history(chat_id, user_msg, bot_summary):
    """Update the persistent chat-history JSON file with backup and corruption protection."""
    try:
        file_path = CHAT_HISTORY_PATH
        # נסה לטעון את הקובץ
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except FileNotFoundError:
            history_data = {}
        except json.JSONDecodeError as e:
            logging.critical(f"⚠️ קובץ היסטוריה פגום! לא מאפסים אוטומטית – יש לתקן ידנית או לשחזר מגיבוי. שגיאה: {e}")
            # לא לאפס! לא לדרוס! להתריע חזק ולעצור
            raise RuntimeError("קובץ היסטוריה פגום – יש לתקן ידנית או לשחזר מגיבוי!")

        chat_id = str(chat_id)
        if chat_id not in history_data:
            history_data[chat_id] = {"am_context": "", "history": []}

        if (user_msg and user_msg.strip()) or (bot_summary and bot_summary.strip()):
            now = utils.get_israel_time()
            simple_timestamp = f"{now.day}/{now.month} {now.hour:02d}:{now.minute:02d}"
            history_data[chat_id]["history"].append(
                {
                    "user": user_msg,
                    "bot": bot_summary,
                    "timestamp": now.isoformat(),
                    "time": simple_timestamp,
                }
            )

        # Keep only the last N messages
        history_data[chat_id]["history"] = history_data[chat_id]["history"][-MAX_CHAT_HISTORY_MESSAGES:]

        # שמור גיבוי לפני כתיבה
        if os.path.exists(file_path):
            shutil.copyfile(file_path, file_path + ".bak")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        if should_log_message_debug():
            logging.info(f"היסטוריה עודכנה למשתמש {chat_id}")
    except Exception as e:
        logging.error(f"שגיאה בעדכון היסטוריה: {e}")


def get_chat_history_messages(chat_id: str, limit: int | None = None) -> list:
    """Return the last `limit` messages from the chat history in a GPT-friendly
    messages array."""
    try:
        with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
            history_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if should_log_message_debug():
            print(f"[HISTORY_DEBUG] לא נמצא קובץ היסטוריה: {CHAT_HISTORY_PATH}")
        return []

    chat_id = str(chat_id)
    if chat_id not in history_data or "history" not in history_data[chat_id]:
        if should_log_message_debug():
            print(f"[HISTORY_DEBUG] אין היסטוריה עבור chat_id={chat_id} בקובץ {CHAT_HISTORY_PATH}")
        return []

    history = history_data[chat_id]["history"]
    max_entries = limit * 2 if limit is not None else 30  # 🔧 כפול כי כל רשומה יכולה להכיל 2 הודעות
    last_entries = history if len(history) < max_entries else history[-max_entries:]

    messages: List[Dict[str, str]] = []
    user_count = 0
    assistant_count = 0
    for entry in last_entries:
        user_content = entry["user"]
        bot_content = entry["bot"]
        
        # 🚨 SECURITY: מנע הודעות פנימיות מלהישלח ל-GPT
        if bot_content and ("[עדכון פרופיל]" in bot_content or bot_content.startswith("[") and "]" in bot_content):
            if should_log_message_debug():
                print(f"[SECURITY] מסנן הודעה פנימית: {bot_content[:50]}...")
            continue
        
        # 🚨 SECURITY: מנע הודעות מערכת מלהישלח ל-GPT
        if user_content and user_content.startswith("[הודעה"):
            if should_log_message_debug():
                print(f"[SECURITY] מסנן הודעת מערכת מהמשתמש: {user_content[:50]}...")
            continue
        
        # 🚨 SECURITY: מנע הודעות מערכת מהבוט מלהישלח ל-GPT
        if bot_content and ("[הודעה אוטומטית מהבוט]" in bot_content or "[הודעה מערכת]" in bot_content):
            if should_log_message_debug():
                print(f"[SECURITY] מסנן הודעת מערכת מהבוט: {bot_content[:50]}...")
            continue
        
        # 🚨 SECURITY: מנע הודעות תשובה פנימיות מלהישלח ל-GPT
        if bot_content and "[תשובת GPT-A]" in bot_content:
            if should_log_message_debug():
                print(f"[SECURITY] מסנן הודעת תשובה פנימית: {bot_content[:50]}...")
            continue
        
        # הוספת טיימסטמפ לכל הודעה בפורמט [01/07 18:03]
        formatted_timestamp = _format_timestamp_for_history(entry.get("timestamp", ""))
        
        # הוספת הודעות עם טיימסטמפ
        if user_content.strip():
            user_content_with_time = f"{formatted_timestamp} {user_content}" if formatted_timestamp else user_content
            messages.append({"role": "user", "content": user_content_with_time})
            user_count += 1
        
        if bot_content.strip():
            bot_content_with_time = f"{formatted_timestamp} {bot_content}" if formatted_timestamp else bot_content
            messages.append({"role": "assistant", "content": bot_content_with_time})
            assistant_count += 1
        
        # 🔧 הגבלה על מספר ההודעות הכולל
        if limit and len(messages) >= limit:
            break

    if should_log_message_debug():
        print(f"[HISTORY_DEBUG] נשלחה היסטוריה מ-{CHAT_HISTORY_PATH} | chat_id={chat_id} | סה\"כ הודעות={len(messages)} | user={user_count} | assistant={assistant_count}")
    return messages


# ---------------------------------------------------------------------------
# 📊 Stats helpers
# ---------------------------------------------------------------------------

def _format_timestamp_for_history(timestamp_str: str) -> str:
    """המרת טיימסטמפ לפורמט הנדרש: [01/07 18:03]"""
    try:
        if not timestamp_str:
            return ""
        
        # המרת המחרוזת לאובייקט datetime
        if "T" in timestamp_str:
            # פורמט ISO
            dt = datetime.fromisoformat(timestamp_str.replace("Z", ""))
        else:
            # פורמט רגיל
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        
        # החזרת הפורמט הנדרש
        return f"[{dt.day:02d}/{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}]"
    except Exception as e:
        logging.warning(f"שגיאה בפרמוט טיימסטמפ: {e}")
        return ""

def _get_time_of_day(hour: int) -> str:
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "afternoon"
    if 18 <= hour <= 22:
        return "evening"
    return "night"


def _extract_topics_from_text(text: str) -> dict:
    emotional_keywords = {
        "stress": ["לחץ", "חרדה", "מתח", "עצוב", "קשה", "בוכה"],
        "hope": ["תקווה", "עתיד", "חלום", "רוצה", "מקווה", "אולי"],
        "family": ["משפחה", "אמא", "אבא", "אח", "אחות", "הורים"],
        "work": ["עבודה", "עובד", "בוס", "משרד", "קריירה", "לימודים"],
        "relationship": ["חבר", "חברה", "בן זוג", "נפגש", "דייט", "אהבה"],
    }
    topic_mentions = {}
    for topic, keywords in emotional_keywords.items():
        mentions = sum(text.count(keyword) for keyword in keywords)
        if mentions > 0:
            topic_mentions[topic] = mentions
    return topic_mentions


def _calculate_user_stats_from_history(history: list) -> dict:
    basic_stats = {
        "total_messages": len(history),
        "first_contact": history[0]["timestamp"] if history else None,
        "last_contact": history[-1]["timestamp"] if history else None,
    }
    if not history:
        return basic_stats

    effective_now = utils.get_effective_time("datetime")
    first_contact_dt = datetime.fromisoformat(history[0]["timestamp"])
    last_contact_dt = datetime.fromisoformat(history[-1]["timestamp"])

    days_together = (effective_now - first_contact_dt).days
    hours_since_last = (effective_now - last_contact_dt).total_seconds() / 3600

    current_hour = effective_now.hour
    weekday = effective_now.weekday()
    weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]

    user_messages = [entry["user"] for entry in history if entry.get("user")]
    all_user_text = " ".join(user_messages).lower()
    topic_mentions = _extract_topics_from_text(all_user_text)

    basic_stats.update(
        {
            "days_knowing_each_other": days_together,
            "hours_since_last_message": round(hours_since_last, 1),
            "messages_per_day_avg": round(len(history) / max(days_together, 1), 1),
            "current_time_of_day": _get_time_of_day(current_hour),
            "current_hour": current_hour,
            "is_weekend": weekday >= 5,
            "weekend_approaching": weekday >= 3,
            "weekday_name": weekday_names[weekday],
            "main_topics_mentioned": topic_mentions,
            "total_user_words": len(all_user_text.split()),
        }
    )
    return basic_stats


def get_user_stats_and_history(chat_id: str) -> Tuple[dict, list]:
    try:
        with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
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


def get_user_stats(chat_id: str) -> dict:
    try:
        stats, _ = get_user_stats_and_history(chat_id)
        return stats
    except Exception as e:
        logging.error(f"שגיאה בקבלת סטטיסטיקות: {e}")
        return {"total_messages": 0, "first_contact": None, "last_contact": None}


# ---------------------------------------------------------------------------
# 🕒 Context & greeting helpers
# ---------------------------------------------------------------------------

def create_human_context_for_gpt(chat_id: str) -> str:
    try:
        now = utils.get_israel_time()
        return f"[{now.day}/{now.month} {now.hour:02d}:{now.minute:02d}]"
    except Exception as e:
        logging.error(f"שגיאה ביצירת הקשר זמן: {e}")
        return ""


def get_time_greeting_instruction() -> str:
    try:
        now = utils.get_israel_time()
        hour = now.hour
        if 5 <= hour < 11:
            greeting_guide = "חשוב שתפתח את ההודעה בברכה 'בוקר טוב🤍' וביטוי של אנרגיה חיובית לתחילת היום"
        elif 11 <= hour < 16:
            greeting_guide = "חשוב שתפתח בברכה 'צהריים טובים🤍' והתייחס לקצב היום או מה שקורה בשעות האלה"
        elif 16 <= hour < 18:
            greeting_guide = "חשוב שתפתח בברכה 'אחר הצהריים טובים🤍' "
        elif 18 <= hour < 21:
            greeting_guide = "חשוב שתפתח בברכה 'ערב טוב🤍' והתייחס לסיום היום או לתוכניות הערב"
        elif 21 <= hour < 24:
            greeting_guide = "חשוב שתפתח בברכה 'לילה טוב🤍' ותשאל איך עבר היום - תהיה יותר רגוע ונעים"
        else:
            greeting_guide = "מאוד חשוב שתפתח בברכה 'לילה טוב🤍' ותהיה מבין שזה שעת לילה מאוחרת אחרי חצות, שאל אם הכל בסדר"
        return f"{greeting_guide}. כן באמצע השיחה התייחס לזמן בצורה טבעית ורלוונטית."
    except Exception as e:
        logging.error(f"שגיאה בהנחיות ברכה: {e}")
        return "תפתח בברכה מתאימה לזמן והתייחס לשעה בצורה טבעית."


# ---------------- יום-שבוע / ברכת זמן ----------------


def get_weekday_context_instruction(chat_id: str | None = None, user_msg: str | None = None) -> str:
    try:
        weekday_words = ["שבת", "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי"]

        # בדיקת לילה: 21:00-05:00 - לא שולח בשעות האלה
        effective_now = utils.get_effective_time("datetime")
        current_hour = effective_now.hour
        if current_hour >= 21 or current_hour < 5:
            return ""

        smart_skip = False
        if chat_id is not None:
            # בדיקה אם המשתמש הזכיר יום שבוע בהודעה הנוכחית
            if user_msg and any(word in user_msg for word in weekday_words):
                smart_skip = True
            else:
                # בדיקה אם כבר הוזכר יום שבוע היום (במשתמש או בבוט)
                try:
                    with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
                        history_data = json.load(f)
                    history = history_data.get(str(chat_id), {}).get("history", [])
                except (FileNotFoundError, json.JSONDecodeError):
                    history = []

                # בדיקה מתחילת היום הנוכחי (05:00)
                start_of_day = effective_now.replace(hour=5, minute=0, second=0, microsecond=0)
                
                for entry in reversed(history):
                    ts = entry.get("timestamp")
                    if not ts:
                        continue
                    try:
                        entry_dt = datetime.fromisoformat(ts)
                    except ValueError:
                        continue
                    if entry_dt < start_of_day:
                        break
                    
                    # בדיקה גם בהודעת המשתמש וגם בהודעת הבוט
                    user_content = entry.get("user", "")
                    bot_content = entry.get("bot", "")
                    
                    if any(word in user_content for word in weekday_words) or \
                       any(word in bot_content for word in weekday_words):
                        smart_skip = True
                        break

        if smart_skip:
            return ""

        # יצירת הנחיות יום השבוע
        weekday = effective_now.weekday()
        israel_weekday = (weekday + 1) % 7 + 1

        weekday_instructions = {
            1: "היום יום ראשון - אפשר להתייחס לכך שתחילת השבוע ואם יש לו תוכניות מסויימות",
            2: "היום יום שני",
            3: "היום יום שלישי",
            4: "היום יום רביעי",
            5: "היום יום חמישי - אפשר להתייחס לכך שנגמר השבוע - ומתחיל סופש אולי לבדוק אם יש לו תוכניות לסופש",
            6: "היום יום שישי - מתחיל סופש - זה יכול להיות טריגרי עבור אנשים מסויימים - עבור אחרים הם רק צמאים לזה - אפשר לשאול מה התוכניות שלו או איפה עושה ארוחת ערב הערב",
            7: "היום יום שבת - תבדוק איתו מה מצב הרוח שלו בשבת הזאת - זה בדרך כלל יום עם הרבה תובנות",
        }
        return weekday_instructions.get(israel_weekday, "")
    except Exception as e:
        logging.error(f"שגיאה ביצירת הנחיית יום השבוע: {e}")
        return ""


# ---------------------------------------------------------------------------
# 🎉 Holidays / special events helper
# ---------------------------------------------------------------------------

def get_holiday_system_message(chat_id: str, bot_reply: str = "") -> str:
    try:
        from sheets_core import get_user_profile_data  # noqa – late import to avoid cycles
        with open("special_events.json", "r", encoding="utf-8") as f:
            events = json.load(f)

        today = utils.get_effective_time("date").strftime("%Y-%m-%d")
        relevant_events = [event for event in events if event.get("date") == today]
        if not relevant_events:
            return ""

        if bot_reply:
            bot_reply_lower = bot_reply.lower()
            for event in relevant_events:
                for keyword in event.get("keywords", []):
                    if keyword.lower() in bot_reply_lower:
                        return ""

        event = relevant_events[0]
        return (
            f"בוט יקר!! שים לב שהיום זה יום מיוחד - יש מועד מיוחד בישראל: {event.get('event', '')}. "
            f"{event.get('suggestion', '')}"
        )
    except Exception as e:
        logging.error(f"שגיאה בפונקציה get_holiday_system_message: {e}")
        return ""


# ---------------------------------------------------------------------------
# 🗑️ Log maintenance & health helpers
# ---------------------------------------------------------------------------

def clean_old_logs() -> None:
    try:
        files_to_clean = [BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME]
        for file_name in files_to_clean:
            file_path = os.path.join(DATA_DIR, file_name)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if len(lines) > MAX_OLD_LOG_LINES:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines[-MAX_OLD_LOG_LINES:])
                if should_log_debug_prints():
                    logging.info(f"נוקה קובץ: {file_name}")
    except Exception as e:
        logging.error(f"שגיאה בניקוי לוגים: {e}")


# ---


def health_check() -> dict:
    from config import check_config_sanity
    from notifications import send_error_notification
    import litellm

    health = {
        "config_loaded": False,
        "sheets_connected": False,
        "openai_connected": False,
        "log_files_writable": False,
    }
    try:
        check_config_sanity()
        health["config_loaded"] = True
        from sheets_handler import sheet_users, sheet_log  # noqa – just to assert import
        health["sheets_connected"] = True

        try:
            from gpt_utils import measure_llm_latency
            with measure_llm_latency("gpt-3.5-turbo"):
                response = litellm.completion(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5,
                    temperature=0,
                )
            if response and getattr(response, "choices", None):
                health["openai_connected"] = True
        except Exception:
            health["openai_connected"] = False

        test_log = {"test": "health_check", "timestamp": utils.get_israel_time().isoformat()}
        with open("health_test.json", "w", encoding="utf-8") as f:
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


# --- Error / usage helpers -----------------------------------------------------------------------

def format_error_message(error: Exception, context: str = "") -> str:
    try:
        error_msg = "🚨 שגיאה"
        if context:
            error_msg += f" ב{context}"
        error_msg += ":\n"
        error_msg += f"📍 סוג: {type(error).__name__}\n"
        error_msg += f"💬 הודעה: {str(error)}\n"
        error_msg += f"⏰ זמן: {utils.get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}\n"
        if should_log_debug_prints():
            tb = traceback.format_exc()
            if len(tb) > MAX_TRACEBACK_LENGTH:
                tb = tb[:MAX_TRACEBACK_LENGTH] + "... (truncated)"
            error_msg += f"🔧 פרטים טכניים:\n{tb}"
        return error_msg
    except Exception:
        return f"🚨 שגיאה בעיצוב הודעת שגיאה: {str(error)}"


def log_error_stat(error_type: str) -> None:
    try:
        stats_path = os.path.join(DATA_DIR, "errors_stats.json")
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            stats = {}
        stats[error_type] = stats.get(error_type, 0) + 1
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"שגיאה בעדכון סטטיסטיקת שגיאות: {e}")


def send_error_stats_report():
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
        send_admin_notification("📊 דוח שגיאות מצטבר:\n" + "\n".join(lines))
    except Exception as e:
        send_admin_notification(f"[send_error_stats_report] שגיאה בשליחת דוח שגיאות: {e}")


def send_usage_report(days_back: int = 1):
    from notifications import send_admin_notification
    effective_now = utils.get_effective_time("datetime")
    since = effective_now - timedelta(days=days_back)
    if not os.path.exists(gpt_log_path):
        send_admin_notification("אין לוג usage זמין.")
        return
    try:
        users = set()
        messages = errors = 0
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


# ---------------------------------------------------------------------------
# 🔧 Misc helpers
# ---------------------------------------------------------------------------

def update_last_bot_message(chat_id, bot_summary):
    try:
        with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
            history_data = json.load(f)
        chat_id = str(chat_id)
        if chat_id in history_data and history_data[chat_id]["history"]:
            history_data[chat_id]["history"][-1]["bot"] = bot_summary
            with open(CHAT_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"❌ שגיאה בעדכון תשובת בוט: {e}")


def cleanup_test_users():
    test_users = ['demo_user_6am', 'working_test_user', 'friday_morning_user', 'timestamp_test']
    try:
        history_file = "data/chat_history.json"
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            for tu in test_users:
                if tu in history:
                    del history[tu]
                    logging.info(f"🗑️ הוסר משתמש בדיקה {tu} מהיסטוריית הצ'אט")
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"❌ שגיאה בניקוי היסטוריית הצ'אט: {e}")


    try:
        reminder_file = "data/reminder_state.json"
        if os.path.exists(reminder_file):
            with open(reminder_file, "r", encoding="utf-8") as f:
                reminders = json.load(f)
            for tu in test_users:
                if tu in reminders:
                    del reminders[tu]
                    logging.info(f"🗑️ הוסר משתמש בדיקה {tu} ממערכת התזכורות")
            with open(reminder_file, "w", encoding="utf-8") as f:
                json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"❌ שגיאה בניקוי מערכת התזכורות: {e}")


# ---------------------------------------------------------------------------
# 💬 Time-block greeting logic
# ---------------------------------------------------------------------------

def should_send_time_greeting(chat_id: str, user_msg: str | None = None) -> bool:
    try:
        # תנאי 1: אם זה הודעת ברכה בסיסית - תמיד שולח
        if user_msg:
            basic_greeting_pattern = r'^(היי|שלום|אהלן|הי|שלום לך|אהלן לך).{0,2}$'
            if re.match(basic_greeting_pattern, user_msg.strip(), re.IGNORECASE):
                print(f"[GREETING_DEBUG] זוהתה הודעת ברכה: '{user_msg}' עבור chat_id={chat_id}")
                return True

        # תנאי 3: בדיקה אם עברו יותר מ-2 שעות מההודעה האחרונה
        effective_now = utils.get_effective_time("datetime")

        try:
            with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # אין היסטוריה - לא שולח ברכה (מוסר תנאי 2)
            return False

        chat_id_str = str(chat_id)
        last_timestamp = None
        if chat_id_str in history_data and history_data[chat_id_str].get("history"):
            last_entry = history_data[chat_id_str]["history"][-1]
            try:
                last_timestamp = datetime.fromisoformat(last_entry.get("timestamp"))
            except Exception:
                last_timestamp = None

        if last_timestamp is None:
            # אין טיימסטמפ תקין - לא שולח ברכה (מוסר תנאי 2)
            return False

        hours_since = (effective_now - last_timestamp).total_seconds() / 3600.0
        
        # שולח ברכה רק אם עברו יותר מ-2 שעות
        return hours_since >= 2
        
    except Exception as e:
        logging.error(f"שגיאה ב-should_send_time_greeting: {e}")
        return False 