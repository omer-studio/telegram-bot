"""chat_utils.py
=================
Chat history management, greeting helpers, health checks and miscellaneous
light-weight helpers that used to live in utils.py.  Keeping them here makes
`utils.py` much leaner while preserving backwards-compatibility (they will be
re-exported from utils).
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
import re
import asyncio
import shutil

from simple_logger import logger
from config import (
    MAX_CHAT_HISTORY_MESSAGES,
    BOT_TRACE_LOG_FILENAME,
    BOT_ERRORS_FILENAME,
    MAX_OLD_LOG_LINES,
    gpt_log_path,
    MAX_TRACEBACK_LENGTH,
)
from config import should_log_debug_prints, should_log_message_debug
from db_manager import save_chat_message, get_chat_history, get_chat_history_enhanced, get_reminder_states_data, save_reminder_state, get_errors_stats_data, save_errors_stats_data
from user_friendly_errors import safe_str

# NOTE: circular import is safe here – utils only contains the base primitives
# we rely on (like `get_israel_time`).
import utils

__all__: List[str] = [
    # chat-history helpers
    "update_chat_history",
    "get_chat_history_messages",
    "get_chat_history_messages_fast",
    "get_user_stats_and_history",
    "get_user_stats",
    # 🆕 מערכת ספירת הודעות מערכתית
    "get_total_user_messages_count",
        "get_recent_history_for_gpt", 
    "count_user_messages_in_history",
    # context & greeting helpers
    "create_human_context_for_gpt",
    "get_time_greeting_instruction",
    "get_weekday_context_instruction",
    "should_send_time_greeting",
    # holiday / system helpers
    "get_holiday_system_message",
    "build_complete_system_messages",  # 🆕 פונקציה מרכזית לבניית סיסטם פרומפטים
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

# ============================================================================
# 📋 תיעוד מערכת ספירת הודעות
# ============================================================================

"""
🎯 מערכת ספירת הודעות מוחלפת - Single Source of Truth

BEFORE (הבעיה):
❌ מספר הודעות נספר מהיסטוריה מוגבלת (15-32 הודעות)
❌ המספר יורד כאשר מצטברות הודעות בוט
❌ אותה לוגיקה חוזרת במקומות רבים

AFTER (הפתרון):
✅ מספר הודעות רק מהמסד נתונים (get_total_user_messages_count)
✅ היסטוריה ל-GPT נפרדת (get_recent_history_for_gpt)
✅ ספירה מהיסטוריה ברורה (count_user_messages_in_history)

🛡️ כללי זהב:
1. **לספירת הודעות כולל** → `get_total_user_messages_count(chat_id)`
2. **להיסטוריה ל-GPT** → `get_recent_history_for_gpt(chat_id, limit)`
3. **לספירה מהיסטוריה נתונה** → `count_user_messages_in_history(history)`

🚫 אסור:
- לספור הודעות מ-get_chat_history_simple עם limit
- להשתמש ב-get_user_stats["total_messages"] (מיושן)
- לערבב בין היסטוריה ל-GPT למספר הודעות כולל
"""

def validate_message_counting_usage():
    """
    🔧 פונקציה לוידוא שהמערכת משמשת נכון
    
    קוראים לזה ב-CI או במצב debug כדי לוודא עקביות
    """
    warnings = []
    
    # בדיקה של קבצים שעלולים להשתמש בדפוסים ישנים
    problematic_patterns = [
        "len([msg for msg in.*history.*if.*role.*user",
        "get_user_stats.*total_messages",
        "get_chat_history_simple.*count",
    ]
    
    # כאן ניתן להוסיף לוגיקה לסריקת קבצים
    # לעת עתה, רק הודעה
    
    return {
        "status": "OK" if not warnings else "WARNINGS",
        "warnings": warnings,
        "recommendations": [
            "השתמש ב-get_total_user_messages_count למספר הודעות כולל",
            "השתמש ב-get_recent_history_for_gpt להיסטוריה ל-GPT",
            "השתמש ב-count_user_messages_in_history לספירה מהיסטוריה"
        ]
    }

def update_chat_history(chat_id: str, user_msg: str, bot_msg: str, **kwargs) -> bool:
    """
    🎯 פונקציה אחת פשוטה לעדכון היסטוריה - במקום פונקציות רבות
    
    עושה הכל:
    - שומרת הודעה במסד נתונים
    - מטפלת בשגיאות
    - לוגים פשוטים
    
    Args:
        chat_id: מזהה הצ'אט
        user_msg: הודעת המשתמש
        bot_msg: הודעת הבוט
        **kwargs: פרמטרים נוספים (gpt_type, gpt_model, וכו')
    
    Returns:
        True אם הצליח, False אם נכשל
    """
    try:
        # שמירה במסד נתונים
        success = save_chat_message(
            chat_id=chat_id,
            user_msg=user_msg,
            bot_msg=bot_msg,
            **kwargs
        )
        
        if success:
            logger.info(f"chat_id={safe_str(chat_id)} | נשמר בהצלחה", source="HISTORY_SAVE")
        else:
            logger.error(f"chat_id={safe_str(chat_id)} | נכשל בשמירה", source="HISTORY_SAVE")
        
        return success
        
    except Exception as e:
        logger.error(f"chat_id={safe_str(chat_id)} | שגיאה: {e}", source="HISTORY_SAVE_ERROR")
        return False

def get_chat_history_simple(chat_id: str, limit: int = 32) -> list:
    """
    🎯 פונקציה אחת פשוטה להיסטוריה - במקום 3 פונקציות שונות
    
    עושה הכל:
    - מביאה היסטוריה מהמסד נתונים
    - מסננת הודעות פנימיות
    - מחזירה בפורמט GPT
    - לוגים פשוטים
    
    Args:
        chat_id: מזהה הצ'אט
        limit: מספר מקסימלי של הודעות (ברירת מחדל: 32)
    
    Returns:
        רשימת הודעות בפורמט GPT
    """
    try:
        # 1. שליפה מהמסד נתונים
        rows = get_chat_history(chat_id, limit)
        
        # 2. המרה לפורמט GPT
        messages = []
        user_count = 0
        assistant_count = 0
        
        for row in rows:
            user_content = row[0] or ""  # user_msg
            bot_content = row[1] or ""   # bot_msg
            timestamp = row[2]           # timestamp
            
            # 3. סינון הודעות פנימיות (פשוט וברור)
            if bot_content and any(marker in bot_content for marker in [
                "[עדכון פרופיל]", "[הודעה אוטומטית מהבוט]", "[הודעה מערכת]", "[תשובת GPT-A]"
            ]):
                continue
            
            if user_content and user_content.startswith("[הודעה"):
                continue
            
            # 4. הוספת הודעות עם טיימסטמפ
            if user_content.strip():
                formatted_time = _format_timestamp_for_history(timestamp.isoformat() if timestamp else "")
                content = f"{formatted_time} {user_content}" if formatted_time else user_content
                messages.append({"role": "user", "content": content})
                user_count += 1
            
            if bot_content.strip():
                formatted_time = _format_timestamp_for_history(timestamp.isoformat() if timestamp else "")
                content = f"{formatted_time} {bot_content}" if formatted_time else bot_content
                messages.append({"role": "assistant", "content": content})
                assistant_count += 1
        
        # 5. לוג פשוט וברור
        logger.info(f"chat_id={safe_str(chat_id)} | בקשה: {limit} | קיבל: {len(messages)} (user={user_count}, assistant={assistant_count})", source="HISTORY")
        
        return messages
        
    except Exception as e:
        logger.error(f"chat_id={safe_str(chat_id)} | שגיאה: {e}", source="HISTORY_ERROR")
        return []

# ============================================================================
# 🎯 מערכת ספירת הודעות מערכתית - Single Source of Truth
# ============================================================================

def get_total_user_messages_count(chat_id: str) -> int:
    """
    🎯 מחזיר מספר כולל של הודעות משתמש מהמסד נתונים
    
    ⚠️ זו הפונקציה הרשמית למספר הודעות כולל!
    עודכנה לחשב ישירות מהמסד נתונים במקום להסתמך על מונה שעלול להיות לא מעודכן.
    
    Args:
        chat_id: מזהה המשתמש
        
    Returns:
        int: מספר הודעות כולל מהמסד נתונים
        
    Example:
        >>> total = get_total_user_messages_count("123456789")
        >>> print(f"המשתמש שלח {total} הודעות")
    """
    try:
        # 🔧 תיקון: חישוב ישיר מהמסד נתונים עם כל ההודעות (לא מוגבל)
        import psycopg2
        from config import config
        
        DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # ספירת כל הודעות המשתמש הלא ריקות
        cur.execute("""
            SELECT COUNT(*) FROM chat_messages 
            WHERE chat_id = %s AND user_msg IS NOT NULL AND user_msg != ''
        """, (safe_str(chat_id),))
        
        user_message_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return user_message_count
        
    except Exception as e:
        logger.error(f"chat_id={safe_str(chat_id)} | שגיאה בקבלת מספר הודעות: {e}", source="USER_COUNT_ERROR")
        return 0

def get_recent_history_for_gpt(chat_id: str, user_limit: int = 20, bot_limit: int = 20) -> list:
    """
    🎯 מחזיר בדיוק user_limit הודעות משתמש + bot_limit הודעות בוט
    עם סיכומי GPT-B במקום התשובות המלאות (אם יש סיכום)
    
    הלוגיקה הפשוטה:
    - יש סיכום GPT-B? השתמש בו
    - אין סיכום GPT-B? השתמש בהודעה המקורית
    
    Args:
        chat_id: מזהה המשתמש
        user_limit: כמה הודעות משתמש (ברירת מחדל: 20)
        bot_limit: כמה הודעות בוט (ברירת מחדל: 20)
        
    Returns:
        list: רשימת הודעות בפורמט GPT
    """
    try:
        # קבלת הודעות מהמסד נתונים
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # שאילתה לקבלת הודעות האחרונות
        cur.execute("""
            SELECT user_msg, bot_msg, timestamp, metadata
            FROM chat_messages
            WHERE chat_id = %s 
            AND (user_msg IS NOT NULL OR bot_msg IS NOT NULL)
            ORDER BY timestamp DESC
            LIMIT %s
        """, (chat_id, (user_limit + bot_limit) * 2))  # מספיק נתונים
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        if not rows:
            return []
        
        # מיון לפי זמן (הישן ביותר קודם)
        rows.reverse()
        
        # הפרדה להודעות משתמש ובוט
        user_messages = []
        bot_messages = []
        
        for row in rows:
            user_msg, bot_msg, timestamp, metadata = row
            
            if user_msg and user_msg.strip():
                user_messages.append({
                    "role": "user",
                    "content": user_msg.strip(),
                    "timestamp": timestamp
                })
            
            if bot_msg and bot_msg.strip():
                # 🎯 הלוגיקה הפשוטה: אם יש סיכום GPT-B - השתמש בו, אחרת בהודעה המקורית
                bot_content = bot_msg.strip()
                if metadata and isinstance(metadata, dict):
                    reply_summary = metadata.get('reply_summary', '')
                    if reply_summary and reply_summary.strip():
                        bot_content = reply_summary.strip()
                
                bot_messages.append({
                    "role": "assistant",
                    "content": bot_content,
                    "timestamp": timestamp
                })
        
        # הגבלה למספר הנדרש
        user_messages = user_messages[-user_limit:] if len(user_messages) > user_limit else user_messages
        bot_messages = bot_messages[-bot_limit:] if len(bot_messages) > bot_limit else bot_messages
        
        # שילוב ההודעות ומיון לפי זמן
        all_messages = user_messages + bot_messages
        all_messages.sort(key=lambda x: x["timestamp"])
        
        # הסרת timestamp מההודעות הסופיות
        result = []
        for msg in all_messages:
            result.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return result
        
    except Exception as e:
        logger.error(f"❌ שגיאה בקריאת היסטוריה: {e}", source="HISTORY_READ_ERROR")
        return []

def get_balanced_history_for_gpt(chat_id: str, user_limit: int = 20, bot_limit: int = 20) -> list:
    """
    🎯 מחזיר היסטוריה מאוזנת בדיוק לפי המספרים שצויינו
    
    מביא בדיוק user_limit הודעות משתמש ו-bot_limit הודעות בוט.
    ממשיך לקרוא מהמסד נתונים עד שמקבל את המספרים הנדרשים.
    
    Args:
        chat_id: מזהה המשתמש
        user_limit: כמה הודעות משתמש דרושות (ברירת מחדל: 20)
        bot_limit: כמה הודעות בוט דרושות (ברירת מחדל: 20)
        
    Returns:
        list: רשימת הודעות בפורמט GPT
        
    Example:
        >>> history = get_balanced_history_for_gpt("123456789", 20, 20)
        >>> print(f"נשלחו {len(history)} הודעות ל-GPT")
    """
    try:
        messages = []
        user_count = 0
        bot_count = 0
        batch_size = 50  # כמה הודעות לקרוא בכל פעם
        current_limit = batch_size
        
        # ממשיכים לקרוא עד שיש לנו מספיק הודעות משני הסוגים
        while (user_count < user_limit or bot_count < bot_limit) and current_limit <= 500:
            # קריאה מהמסד נתונים
            rows = get_chat_history(chat_id, current_limit)
            if not rows:
                break
                
            # איפוס המונים לחישוב מחדש
            temp_messages = []
            temp_user_count = 0
            temp_bot_count = 0
            
            for row in rows:
                user_content = row[0] or ""  # user_msg
                bot_content = row[1] or ""   # bot_msg
                timestamp = row[2]           # timestamp
                
                # סינון הודעות פנימיות (כמו בפונקציה המקורית)
                if bot_content and any(marker in bot_content for marker in [
                    "[עדכון פרופיל]", "[הודעה אוטומטית מהבוט]", "[הודעה מערכת]", "[תשובת GPT-A]"
                ]):
                    continue
                
                if user_content and user_content.startswith("[הודעה"):
                    continue
                
                # הוספת הודעות משתמש עד למגבלה
                if user_content.strip() and temp_user_count < user_limit:
                    formatted_time = _format_timestamp_for_history(timestamp.isoformat() if timestamp else "")
                    content = f"{formatted_time} {user_content}" if formatted_time else user_content
                    temp_messages.append({"role": "user", "content": content})
                    temp_user_count += 1
                
                # הוספת הודעות בוט עד למגבלה
                if bot_content.strip() and temp_bot_count < bot_limit:
                    formatted_time = _format_timestamp_for_history(timestamp.isoformat() if timestamp else "")
                    content = f"{formatted_time} {bot_content}" if formatted_time else bot_content
                    temp_messages.append({"role": "assistant", "content": content})
                    temp_bot_count += 1
                
                # אם הגענו למספרים שרצינו, נעצור
                if temp_user_count >= user_limit and temp_bot_count >= bot_limit:
                    break
            
            # עדכון התוצאות
            messages = temp_messages
            user_count = temp_user_count
            bot_count = temp_bot_count
            
            # אם לא הגענו למספרים שרצינו, ננסה לקרוא יותר הודעות
            if user_count < user_limit or bot_count < bot_limit:
                current_limit += batch_size
            else:
                break
        
        # הודעות כבר מגיעות מסודרות מהמסד נתונים (מהישן לחדש)
        # לא צריך מיון נוסף כי get_chat_history כבר מחזיר אותן בסדר הנכון
        
        logger.info(f"chat_id={safe_str(chat_id)} | בקשה: {user_limit}+{bot_limit} | קיבל: {len(messages)} (user={user_count}, assistant={bot_count})", source="BALANCED_HISTORY")
        
        return messages
        
    except Exception as e:
        logger.error(f"chat_id={safe_str(chat_id)} | שגיאה בהיסטוריה מאוזנת: {e}", source="BALANCED_HISTORY_ERROR")
        return []

def count_user_messages_in_history(history: list) -> int:
    """
    🎯 סופר הודעות משתמש בהיסטוריה נתונה
    
    ⚠️ זה רק לספירה מהיסטוריה שכבר יש!
    לא להתמש בזה למספר הודעות כולל.
    
    Args:
        history: רשימת הודעות בפורמט GPT
        
    Returns:
        int: מספר הודעות משתמש בהיסטוריה הנתונה
        
    Example:
        >>> count = count_user_messages_in_history(history_messages)
        >>> print(f"בהיסטוריה יש {count} הודעות משתמש")
    """
    if not history:
        return 0
    return len([msg for msg in history if msg.get("role") == "user"])

# ============================================================================
# 🗑️ פונקציות ישנות - לתאימות לאחור (יוסרו בעתיד)
# ============================================================================

def get_chat_history_messages(chat_id: str, limit: Optional[int] = None) -> list:
    """🗑️ פונקציה ישנה - להשתמש ב-get_chat_history_simple במקום"""
    return get_chat_history_simple(chat_id, limit or 30)

def get_chat_history_messages_fast(chat_id: str, limit: Optional[int] = None) -> list:
    """🗑️ פונקציה ישנה - להשתמש ב-get_chat_history_simple במקום"""
    return get_chat_history_simple(chat_id, limit or 15)

def get_chat_history_unified(chat_id: str, limit: int = 32, use_fast_mode: bool = True) -> list:
    """🗑️ פונקציה ישנה - להשתמש ב-get_chat_history_simple במקום"""
    return get_chat_history_simple(chat_id, limit)

# ============================================================================
# 🗑️ פונקציות מיותרות - יוסרו
# ============================================================================

# 🗑️ _HISTORY_CALLS_LOG = []
# 🗑️ log_history_call()
# 🗑️ get_history_calls_summary()
# 🗑️ validate_history_integrity()

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
        logger.warning(f"שגיאה בפרמוט טיימסטמפ: {e}", source="HISTORY_TIMESTAMP_FORMAT")
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
    # ⚠️ DEPRECATED: פונקציה זו מחשבת סטטיסטיקות מהיסטוריה מוגבלת!
    # להשתמש ב-get_total_user_messages_count() למספר הודעות אמיתי
    
    # סופר רק הודעות משתמש (לא בוט) מההיסטוריה המוגבלת
    user_messages = [entry["user"] for entry in history if entry.get("user")]
    basic_stats = {
        "total_messages": len(user_messages),  # ⚠️ זה מהיסטוריה מוגבלת בלבד!
        "first_contact": history[0]["timestamp"] if history else None,
        "last_contact": history[-1]["timestamp"] if history else None,
    }
    if not history:
        return basic_stats

    try:
        effective_now = utils.get_effective_time("datetime")
        first_contact_dt = datetime.fromisoformat(history[0]["timestamp"])
        last_contact_dt = datetime.fromisoformat(history[-1]["timestamp"])

        # 🔧 תיקון: וידוא timezone consistency
        import pytz
        israel_tz = pytz.timezone('Asia/Jerusalem')
        
        # אם effective_now אין לו timezone, מוסיפים
        if effective_now.tzinfo is None:
            effective_now = israel_tz.localize(effective_now)
        
        # אם התאריכים מההיסטוריה אין להם timezone, מוסיפים
        if first_contact_dt.tzinfo is None:
            first_contact_dt = israel_tz.localize(first_contact_dt)
        if last_contact_dt.tzinfo is None:
            last_contact_dt = israel_tz.localize(last_contact_dt)

        days_together = (effective_now - first_contact_dt).days
        hours_since_last = (effective_now - last_contact_dt).total_seconds() / 3600

        current_hour = effective_now.hour
        weekday = effective_now.weekday()
        weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]

        all_user_text = " ".join(user_messages).lower()
        topic_mentions = _extract_topics_from_text(all_user_text)

        basic_stats.update(
            {
                "days_knowing_each_other": days_together,
                "hours_since_last_message": round(hours_since_last, 1),
                "messages_per_day_avg": round(len(user_messages) / max(days_together, 1), 1),
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
    except Exception as e:
        logger.error(f"שגיאה בחישוב סטטיסטיקות מההיסטוריה: {e}", source="USER_STATS_CALCULATION")
        return basic_stats  # מחזיר לפחות את הסטטיסטיקות הבסיסיות


def get_user_stats_and_history(chat_id: str) -> Tuple[dict, list]:
    try:
        # שליפה ישירה מ-SQL באמצעות db_manager
        rows = get_chat_history(chat_id)  # ללא מגבלת הודעות
        if not rows:
            return {"total_messages": 0, "first_contact": None, "last_contact": None}, []
        
        # המרה לפורמט הישן לתאימות
        history = []
        for row in rows:
            history.append({
                "user": row[0] or "",
                "bot": row[1] or "",
                "timestamp": row[2].isoformat() if row[2] else ""
            })
        
        stats = _calculate_user_stats_from_history(history)
        return stats, history
    except Exception as e:
        logger.error(f"שגיאה בקבלת סטטיסטיקות: {e}", source="USER_STATS_FETCH")
        return {"total_messages": 0, "first_contact": None, "last_contact": None}, []


def get_user_stats(chat_id: str) -> dict:
    try:
        stats, _ = get_user_stats_and_history(chat_id)
        return stats
    except Exception as e:
        logger.error(f"שגיאה בקבלת סטטיסטיקות: {e}", source="USER_STATS_FETCH")
        return {"total_messages": 0, "first_contact": None, "last_contact": None}


# ---------------------------------------------------------------------------
# 🕒 Context & greeting helpers
# ---------------------------------------------------------------------------

def is_active_hours() -> bool:
    """בודק אם השעה הנוכחית בשעות פעילות (07:00-22:00) לשליחת הודעות."""
    try:
        current_hour = utils.get_israel_time().hour
        return 7 <= current_hour <= 22
    except Exception as e:
        logger.error(f"שגיאה בבדיקת שעות פעילות: {e}", source="ACTIVE_HOURS_CHECK")
        return True  # במקרה של שגיאה, נניח שזה שעות פעילות

def create_human_context_for_gpt(chat_id: str) -> str:
    try:
        now = utils.get_israel_time()
        return f"[{now.day}/{now.month} {now.hour:02d}:{now.minute:02d}]"
    except Exception as e:
        logger.error(f"שגיאה ביצירת הקשר זמן: {e}", source="HUMAN_CONTEXT_CREATION")
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
        logger.error(f"שגיאה בהנחיות ברכה: {e}", source="GREETING_INSTRUCTIONS")
        return "תפתח בברכה מתאימה לזמן והתייחס לשעה בצורה טבעית."


# ---------------- יום-שבוע / ברכת זמן ----------------


def get_weekday_context_instruction(chat_id: Optional[str] = None, user_msg: Optional[str] = None) -> str:
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
                # בדיקה אם הבוט כבר הזכיר יום שבוע היום (רק בהודעות הבוט)
                try:
                    # שליפה ישירה מ-SQL באמצעות db_manager
                    rows = get_chat_history(chat_id, 30)
                    history = [{"user": row[0], "bot": row[1], "timestamp": row[2]} for row in rows]
                except Exception:
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
                    
                    # בדיקה רק בהודעות הבוט (לא המשתמש)
                    bot_content = entry.get("bot", "")
                    
                    if any(word in bot_content for word in weekday_words):
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
        logger.error(f"שגיאה ביצירת הנחיית יום השבוע: {e}", source="WEEKDAY_INSTRUCTIONS")
        return ""


# ---------------------------------------------------------------------------
# 🎉 Holidays / special events helper
# ---------------------------------------------------------------------------

def get_holiday_system_message(chat_id: str, bot_reply: str = "") -> str:
    try:
        # בדיקת שעות פעילות - חגים נשלחים רק בשעות פעילות
        if not is_active_hours():
            return ""
        
        # 🗑️ עברנו למסד נתונים - אין צורך ב-Google Sheets!
        # from sheets_core import get_user_profile_data  # noqa – late import to avoid cycles
        from profile_utils import get_user_profile_fast  # המחליף במסד נתונים
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
        logger.error(f"שגיאה בפונקציה get_holiday_system_message: {e}", source="HOLIDAY_SYSTEM_MESSAGE")
        return ""


# ---------------------------------------------------------------------------
# 🗑️ Log maintenance & health helpers
# ---------------------------------------------------------------------------

def clean_old_logs() -> None:
    try:
        files_to_clean = [BOT_TRACE_LOG_FILENAME, BOT_ERRORS_FILENAME]
        for file_name in files_to_clean:
            file_path = os.path.join(gpt_log_path, file_name)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if len(lines) > MAX_OLD_LOG_LINES:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines[-MAX_OLD_LOG_LINES:])
                if should_log_debug_prints():
                    logger.info(f"נוקה קובץ: {file_name}", source="CLEAN_OLD_LOGS")
    except Exception as e:
        logger.error(f"שגיאה בניקוי לוגים: {e}", source="CLEAN_OLD_LOGS_ERROR")


# ---


def health_check() -> dict:
    from config import check_config_sanity
    from notifications import send_error_notification
    import lazy_litellm as litellm

    health = {
        "config_loaded": False,
        "sheets_connected": False,
        "openai_connected": False,
        "log_files_writable": False,
    }
    try:
        check_config_sanity()
        health["config_loaded"] = True
        # 🗑️ עברנו למסד נתונים - אין צורך ב-Google Sheets!
        # Google Sheets לא רלוונטי יותר - עובדים רק עם מסד נתונים
        health["sheets_connected"] = True  # תמיד True כי אין צורך ב-Sheets

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
        logger.error(f"⚕️ בעיה בבדיקת תקינות: {e}", source="HEALTH_CHECK_ERROR")
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
    """
    🚫 DISABLED: טבלת errors_stats הושבתה - סטטיסטיקות שגיאות לא נשמרות
    כל השגיאות נשמרות ב-system_logs או bot_error_logs לפי הצורך
    """
    try:
        # סטטיסטיקות שגיאות לא נשמרות - השגיאות עצמן נשמרות בלוגים הרגילים
        if should_log_debug_prints():
            logger.info(f"🔄 [DISABLED] errors_stats disabled - error '{error_type}' logged to regular logs", source="ERROR_STATS_LOGGING")
        return  # לא שומר סטטיסטיקות
        
        # הקוד הישן הושבת:
        # stats = get_errors_stats_data()
        # if not stats:
        #     stats = {}
        # stats[error_type] = stats.get(error_type, 0) + 1
        # save_errors_stats_data(stats)
        
    except Exception as e:
        logger.error(f"שגיאה בעדכון סטטיסטיקת שגיאות: {e}", source="ERROR_STATS_UPDATE")


def send_error_stats_report():
    """
    🚫 DISABLED: טבלת errors_stats הושבתה - אין דוח סטטיסטיקות שגיאות
    """
    from admin_notifications import send_admin_notification
    
    try:
        # אין יותר סטטיסטיקות שגיאות - הטבלה הושבתה
        if should_log_debug_prints():
            logger.info(f"🔄 [DISABLED] errors_stats disabled - no error stats report available", source="ERROR_STATS_REPORT")
        
        send_admin_notification("🚫 דוח שגיאות הושבת - הטבלה צומצמה לטובת ביצועים")
        return
        
        # הקוד הישן הושבת:
        # stats = get_errors_stats_data()
        # if not stats:
        #     send_admin_notification("אין נתוני שגיאות זמינים.")
        #     return
        # lines = [f"{k}: {v}" for k, v in sorted(stats.items(), key=lambda x: -x[1])]
        # send_admin_notification("📊 דוח שגיאות מצטבר:\n" + "\n".join(lines))
        
    except Exception as e:
        send_admin_notification(f"[send_error_stats_report] שגיאה בשליחת דוח שגיאות: {e}", source="ERROR_STATS_REPORT_ERROR")


def send_usage_report(days_back: int = 1):
    from admin_notifications import send_admin_notification
    effective_now = utils.get_effective_time("datetime")
    since = effective_now - timedelta(days=days_back)
    if not os.path.exists(gpt_log_path):
        send_admin_notification("אין לוג usage זמין.", source="USAGE_REPORT_NO_LOGS")
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
                        users.add(safe_str(chat_id))
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
        send_admin_notification(msg, source="USAGE_REPORT")
    except Exception as e:
        send_admin_notification(f"[send_usage_report] שגיאה בשליחת דוח usage: {e}", source="USAGE_REPORT_ERROR")


# ---------------------------------------------------------------------------
# 🔧 Misc helpers
# ---------------------------------------------------------------------------

def update_last_bot_message(chat_id, bot_summary):
    """עדכון הודעת הבוט האחרונה - לא נתמך ב-SQL (הודעות נשמרות בנפרד)"""
    try:
        # ב-SQL כל הודעה נשמרת בנפרד, אין צורך בעדכון
        # רק נוסיף הודעה חדשה אם יש תוכן
        if bot_summary and bot_summary.strip():
            save_chat_message(chat_id, "", bot_summary)
            
        if should_log_message_debug():
            logger.info(f"הודעת בוט עודכנה למשתמש {safe_str(chat_id)} (SQL)", source="LAST_BOT_MESSAGE_UPDATE")
    except Exception as e:
        logger.error(f"❌ שגיאה בעדכון תשובת בוט: {e}", source="LAST_BOT_MESSAGE_UPDATE_ERROR")


def cleanup_test_users():
    """ניקוי משתמשי בדיקה - עובד עם מסד הנתונים"""
    test_users = ['demo_user_6am', 'working_test_user', 'friday_morning_user', 'timestamp_test']
    try:
        # בשלב זה לא נתמך מחיקה מ-SQL
        # TODO: להוסיף פונקציית מחיקה ל-db_manager
        logger.info(f"🗑️ ניקוי משתמשי בדיקה - לא נתמך ב-SQL בשלב זה", source="CLEANUP_TEST_USERS")
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי היסטוריית הצ'אט: {e}", source="CLEANUP_TEST_USERS_ERROR")


    try:
        # קריאת תזכורות ממסד הנתונים
        reminders = get_reminder_states_data()
        
        if reminders:
            for tu in test_users:
                if tu in reminders:
                    # למחוק תזכורת צריך לעדכן אותה עם סטטוס מחוק
                    # או להוסיף פונקציית מחיקה נפרדת למסד הנתונים
                    logger.info(f"🗑️ נמצא משתמש בדיקה {tu} במערכת התזכורות (SQL)", source="CLEANUP_REMINDERS")
                    # TODO: להוסיף מחיקה אמיתית
                    
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי מערכת התזכורות: {e}", source="CLEANUP_REMINDERS_ERROR")


# ---------------------------------------------------------------------------
# 💬 System prompts condition logic (מרכז הלוגיקה)
# ---------------------------------------------------------------------------

def should_send_weekday_context(chat_id: str, user_msg: Optional[str] = None) -> bool:
    """בדיקה אם יש לשלוח הקשר יום השבוע"""
    try:
        weekday_words = ["שבת", "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי"]

        # בדיקת לילה: 21:00-05:00 - לא שולח בשעות האלה
        effective_now = utils.get_effective_time("datetime")
        current_hour = effective_now.hour
        if current_hour >= 21 or current_hour < 5:
            return False

        # בדיקה אם המשתמש הזכיר יום שבוע בהודעה הנוכחית
        if user_msg and any(word in user_msg for word in weekday_words):
            return False

        # בדיקה אם הבוט כבר הזכיר יום שבוע היום (רק בהודעות הבוט)
        try:
            rows = get_chat_history(chat_id, 30)
            history = [{"user": row[0], "bot": row[1], "timestamp": row[2]} for row in rows]
        except Exception:
            return False

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
            
            # בדיקה רק בהודעות הבוט (לא המשתמש)
            bot_content = entry.get("bot", "")
            
            if any(word in bot_content for word in weekday_words):
                return False

        return True
        
    except Exception as e:
        logger.error(f"שגיאה ב-should_send_weekday_context: {e}", source="WEEKDAY_CHECK")
        return False


def should_send_holiday_message(chat_id: str, user_msg: str = "") -> bool:
    """בדיקה אם יש לשלוח הודעת חג"""
    try:
        # בדיקת שעות פעילות - חגים נשלחים רק בשעות פעילות
        if not is_active_hours():
            return False
        
        # בדיקה אם יש חגים היום
        with open("special_events.json", "r", encoding="utf-8") as f:
            events = json.load(f)

        today = utils.get_effective_time("date").strftime("%Y-%m-%d")
        relevant_events = [event for event in events if event.get("date") == today]
        if not relevant_events:
            return False

        # בדיקה אם כבר הזכיר מילות מפתח של החג בהודעה הנוכחית
        if user_msg:
            user_msg_lower = user_msg.lower()
            for event in relevant_events:
                for keyword in event.get("keywords", []):
                    if keyword.lower() in user_msg_lower:
                        return False

        return True
        
    except Exception as e:
        logger.error(f"שגיאה ב-should_send_holiday_message: {e}", source="HOLIDAY_CHECK")
        return False


def get_weekday_content() -> str:
    """מחזיר את תוכן הנחיות יום השבוע (בלי לוגיקת תנאים)"""
    try:
        effective_now = utils.get_effective_time("datetime")
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
        logger.error(f"שגיאה ביצירת תוכן יום השבוע: {e}", source="WEEKDAY_CONTENT")
        return ""


def get_holiday_content() -> str:
    """מחזיר את תוכן הודעת החג (בלי לוגיקת תנאים)"""
    try:
        with open("special_events.json", "r", encoding="utf-8") as f:
            events = json.load(f)

        today = utils.get_effective_time("date").strftime("%Y-%m-%d")
        relevant_events = [event for event in events if event.get("date") == today]
        if not relevant_events:
            return ""

        event = relevant_events[0]
        return (
            f"בוט יקר!! שים לב שהיום זה יום מיוחד - יש מועד מיוחד בישראל: {event.get('event', '')}. "
            f"{event.get('suggestion', '')}"
        )
    except Exception as e:
        logger.error(f"שגיאה ביצירת תוכן חג: {e}", source="HOLIDAY_CONTENT")
        return ""


def should_send_time_greeting(chat_id: str, user_msg: Optional[str] = None) -> bool:
    """בדיקה אם יש לשלוח ברכה לפי זמן"""
    try:
        # בדיקה אם הבוט כבר הזכיר יום שבוע היום (רק בהודעות הבוט)
        try:
            # שליפה מ-SQL באמצעות db_manager
            rows = get_chat_history(chat_id, 30)
            if not rows:
                return False
        except Exception:
            return False

        chat_id_str = safe_str(chat_id)
        last_timestamp = None
        
        # בדיקת ההודעה האחרונה
        if rows:
            last_entry = rows[-1]
            try:
                last_timestamp = last_entry[2]  # timestamp
            except Exception:
                last_timestamp = None

        # תנאי 1: אם זה הודעת ברכה בסיסית - תמיד שולח
        if user_msg:
            basic_greeting_pattern = r'^(היי|שלום|אהלן|הי|שלום לך|אהלן לך).{0,2}$'
            if re.match(basic_greeting_pattern, user_msg.strip(), re.IGNORECASE):
                logger.info(f"זוהתה הודעת ברכה: '{user_msg}' עבור chat_id={safe_str(chat_id)}", source="GREETING_DEBUG")
                return True

        # תנאי 3: בדיקה אם עברו יותר מ-2 שעות מההודעה האחרונה
        effective_now = utils.get_effective_time("datetime")

        if last_timestamp is None:
            # אין טיימסטמפ תקין - לא שולח ברכה (מוסר תנאי 2)
            return False

        # וידוא שlast_timestamp הוא datetime object
        if not isinstance(last_timestamp, datetime):
            try:
                if isinstance(last_timestamp, str):
                    last_timestamp = datetime.fromisoformat(last_timestamp)
                else:
                    # אם זה לא string וגם לא datetime, לא שולח ברכה
                    return False
            except Exception:
                return False
        
        hours_since = (effective_now - last_timestamp).total_seconds() / 3600.0
        
        # שולח ברכה רק אם עברו יותר מ-3 שעות
        return hours_since >= 3
        
    except Exception as e:
        logger.error(f"שגיאה ב-should_send_time_greeting: {e}", source="GREETING_CHECK")
        return False


# ---------------------------------------------------------------------------
# 🎯 SYSTEM PROMPTS REGISTRY - מרכז אחד לכל הסיסטם פרומפטים
# ---------------------------------------------------------------------------

def get_system_prompts_registry():
    """
    🎯 מרכז אחד לכל הסיסטם פרומפטים - פשוט, ברור, ניתן לתחזוקה
    
    כל פרומפט מוגדר במקום אחד עם:
    - תנאי: מתי לשלוח
    - תוכן: מה לשלוח
    - סדר: באיזה סדר לשלוח
    
    זה מבטיח שלא יהיו הפתעות, כפילויות או לוגיקה מוסתרת
    """
    from prompts import SYSTEM_PROMPT
    from profile_utils import get_user_summary_fast
    
    def always_true(chat_id, user_msg):
        return True
    
    def should_send_time_greeting_check(chat_id, user_msg):
        """בדיקה אם יש לשלוח ברכה לפי זמן"""
        return should_send_time_greeting(chat_id, user_msg)

    def should_send_weekday_check(chat_id, user_msg):
        """בדיקה אם יש לשלוח הקשר יום השבוע"""
        return should_send_weekday_context(chat_id, user_msg)

    def should_send_holiday_check(chat_id, user_msg):
        """בדיקה אם יש לשלוח הודעת חג"""
        return should_send_holiday_message(chat_id, user_msg)

    def get_time_greeting_content(chat_id, user_msg):
        """מחזיר תוכן ברכת זמן"""
        return get_time_greeting_instruction()

    def get_weekday_content_wrapper(chat_id, user_msg):
        """מחזיר תוכן יום השבוע"""
        return get_weekday_content()

    def get_holiday_content_wrapper(chat_id, user_msg):
        """מחזיר תוכן חג"""
        return get_holiday_content()

    def get_user_summary_content(chat_id, user_msg):
        """מחזיר סיכום המשתמש"""
        try:
            current_summary = get_user_summary_fast(safe_str(chat_id)) or ""
            if current_summary:
                logger.info(f"[SUMMARY_DEBUG] Added summary system prompt for user {safe_str(chat_id)}: '{current_summary[:50]}{'...' if len(current_summary) > 50 else ''}'", source="chat_utils")
                return f"🎯 מידע על המשתמש: {current_summary}"
            else:
                logger.info(f"[SUMMARY_DEBUG] No summary found for user {safe_str(chat_id)}", source="chat_utils")
                return ""
        except Exception as e:
            logger.error(f"שגיאה בסיכום משתמש: {e}", source="USER_SUMMARY_CONTENT")
            return ""

    # 🎯 הרישום המרכזי - כל פרומפט במקום אחד עם סדר ברור
    return [
        {
            "name": "main_prompt",
            "condition": always_true,
            "content": lambda chat_id, user_msg: SYSTEM_PROMPT,
            "order": 1,
            "description": "הפרומפט הראשי של דניאל - תמיד נשלח"
        },
        {
            "name": "user_summary", 
            "condition": always_true,
            "content": get_user_summary_content,
            "order": 2,
            "description": "סיכום המשתמש - תמיד נשלח אם יש"
        },
        {
            "name": "time_greeting",
            "condition": should_send_time_greeting_check,
            "content": get_time_greeting_content,
            "order": 3,
            "description": "ברכות זמן - רק אם הודעת ברכה או עברו 3+ שעות"
        },
        {
            "name": "weekday_context",
            "condition": should_send_weekday_check, 
            "content": get_weekday_content_wrapper,
            "order": 4,
            "description": "יום השבוע - רק בשעות 05:00-21:00 ואם לא הוזכר כבר"
        },
        {
            "name": "holiday_message",
            "condition": should_send_holiday_check,
            "content": get_holiday_content_wrapper, 
            "order": 5,
            "description": "הודעות חגים - רק בשעות פעילות ואם יש חג היום"
        }
    ] 


def build_complete_system_messages(chat_id: str, user_msg: str = "", include_main_prompt: bool = True) -> List[Dict[str, str]]:
    """
    🎯 פונקציה מרכזית שבונה את כל הסיסטם פרומפטים במקום אחד
    
    עובד עם הרישום המרכזי - פשוט, ברור, ניתן לתחזוקה.
    כל פרומפט מוגדר במקום אחד עם תנאי ותוכן ברורים.
    
    Args:
        chat_id: מזהה המשתמש
        user_msg: הודעת המשתמש (לצורך הקשר)
        include_main_prompt: האם לכלול את הפרומפט הראשי של דניאל
    
    Returns:
        רשימה של הודעות סיסטם מוכנות ל-GPT
    """
    system_messages = []
    
    try:
        # קבלת הרישום המרכזי של כל הפרומפטים
        prompts_registry = get_system_prompts_registry()
        
        # מעבר על כל פרומפט לפי הסדר
        for prompt_config in sorted(prompts_registry, key=lambda x: x["order"]):
            try:
                # דילוג על הפרומפט הראשי אם לא נדרש
                if prompt_config["name"] == "main_prompt" and not include_main_prompt:
                    continue
                
                # בדיקת התנאי
                if prompt_config["condition"](safe_str(chat_id), user_msg):
                    # קבלת התוכן
                    content = prompt_config["content"](safe_str(chat_id), user_msg)
                    
                    # הוספה לרשימה אם יש תוכן
                    if content and content.strip():
                        system_messages.append({"role": "system", "content": content})
                        logger.debug(f"[SYSTEM_PROMPTS] Added '{prompt_config['name']}' for user {safe_str(chat_id)}", source="chat_utils")
                    else:
                        logger.debug(f"[SYSTEM_PROMPTS] Skipped '{prompt_config['name']}' - empty content for user {safe_str(chat_id)}", source="chat_utils")
                else:
                    logger.debug(f"[SYSTEM_PROMPTS] Skipped '{prompt_config['name']}' - condition failed for user {safe_str(chat_id)}", source="chat_utils")
                    
            except Exception as e:
                logger.warning(f"[SYSTEM_PROMPTS] Error processing '{prompt_config['name']}': {e}", source="chat_utils")
                
        logger.info(f"[SYSTEM_PROMPTS] Built {len(system_messages)} system messages for user {safe_str(chat_id)}", source="chat_utils")
        return system_messages
        
    except Exception as e:
        logger.error(f"[SYSTEM_PROMPTS] Critical error building system messages: {e}", source="chat_utils")
        # fallback - לפחות הפרומפט הראשי
        if include_main_prompt:
            try:
                from prompts import SYSTEM_PROMPT
                return [{"role": "system", "content": SYSTEM_PROMPT}]
            except Exception:
                return []
        return [] 