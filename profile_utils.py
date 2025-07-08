"""profile_utils.py
====================
ניהול תעודת הזהות הרגשית (פרופיל) – פונקציות שהועברו מ-utils.py לשמירה על קוד רזה.
כל הפונקציות מיובאות חזרה ב-utils לצורך תאימות לאחור.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import utils  # time helpers + log_event_to_file live there
from config import should_log_debug_prints, should_log_message_debug
from db_manager import save_user_profile, get_user_profile
from fields_dict import FIELDS_DICT

__all__: List[str] = [
    # Main fast-path helpers
    "get_user_profile_fast",
    "update_user_profile_fast",
    "get_user_summary_fast",
    "update_user_summary_fast",
    "increment_code_try_fast",
    "increment_gpt_c_run_count_fast",
    "clear_user_cache_profile",
    # Emotional-identity API
    "update_emotional_identity_fast",
    "get_emotional_identity_fast",
    "ensure_emotional_identity_consistency",
    "get_all_emotional_identity_fields",
    "validate_emotional_identity_data",
    # Maintenance helpers
    "force_sync_to_sheets",
    "cleanup_old_profiles",
    "get_profiles_stats",
    "_send_admin_profile_overview_notification",
    "_detect_profile_changes",
]

# 🚨 כל השימושים ב-USER_PROFILES_PATH הוסרו – הכל עובר דרך מסד הנתונים בלבד

def clear_user_cache_profile(chat_id: str) -> Dict[str, Any]:
    """
    מנקה cache של פרופיל משתמש ספציפי.
    מחזיר מידע על ההצלחה וכמות ה-cache keys שנוקו.
    """
    try:
        # במערכת הנוכחית אין cache file-based, אז זה placeholder
        # שמחזיר תמיד הצלחה ללא ניקוי בפועל
        logging.debug(f"[CACHE_CLEAR] ניסה לנקות cache עבור משתמש {chat_id}")
        
        return {
            "success": True,
            "cleared_count": 0,
            "message": "No file-based cache to clear in current system"
        }
    except Exception as e:
        logging.error(f"שגיאה בניקוי cache למשתמש {chat_id}: {e}")
        return {
            "success": False,
            "cleared_count": 0,
            "error": str(e)
        }


def get_user_profile_fast(chat_id: str) -> Dict[str, Any]:
    """טוען במהירות את הפרופיל מ-SQL database."""
    try:
        profile_json = get_user_profile(chat_id)
        if profile_json:
            return profile_json
        return {}
    except Exception as e:
        logging.error(f"שגיאה בשליפת פרופיל: {e}")
        return {}


def _update_user_profiles_file(chat_id: str, updates: Dict[str, Any]):
    """Writes *updates* into SQL database (minimal logic only)."""
    try:
        # 🚦 Mini-sanity: convert numeric strings like "35" in the *age* field to int 35
        if "age" in updates and isinstance(updates["age"], str) and updates["age"].isdigit():
            updates = {**updates, "age": int(updates["age"])}  # shallow copy – keep immutability

        # Load existing data (if any)
        try:
            existing_profile = get_user_profile(chat_id) or {}
        except Exception:
            existing_profile = {}

        # Merge updates
        updated_profile = {**existing_profile, **updates}
        updated_profile["last_update"] = utils.get_israel_time().isoformat()

        # Save to SQL
        save_user_profile(chat_id, updated_profile)
        
    except Exception as exc:
        logging.error(f"שגיאה בעדכון פרופיל: {exc}")


# ---------------------------------------------------------------------------
# 🔄  Sync helpers – local profile ⇄ Google Sheets
# ---------------------------------------------------------------------------

async def _sync_to_sheet_by_headers(sheet, chat_id: str, local_profile: Dict[str, Any]):
    """Synchronise fields by header names - 🗑️ עברנו למסד נתונים"""
    try:
        # 🗑️ עברנו למסד נתונים - Google Sheets לא נדרש יותר
        logging.info(f"🗑️ פונקציה זו הוסרה - עברנו למסד נתונים עבור {chat_id}")
        return  # פשוט מחזיר בלי לעשות כלום
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון לפי כותרות: {exc}")


async def _sync_local_to_sheets_background(chat_id: str):
    """Background task - 🗑️ עברנו למסד נתונים"""
    try:
        # 🗑️ עברנו למסד נתונים - סנכרון Google Sheets לא נדרש יותר
        logging.info(f"🗑️ פונקציה זו הוסרה - עברנו למסד נתונים עבור {chat_id}")
        return  # פשוט מחזיר בלי לעשות כלום
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון ל-Google Sheets: {exc}")


def _sync_local_to_sheets_sync(chat_id: str):
    """Synchronous wrapper - 🗑️ עברנו למסד נתונים"""
    try:
        # 🗑️ עברנו למסד נתונים - סנכרון Google Sheets לא נדרש יותר
        logging.info(f"🗑️ פונקציה זו הוסרה - עברנו למסד נתונים עבור {chat_id}")
        return  # פשוט מחזיר בלי לעשות כלום
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון ל-Google Sheets: {exc}")


def _sync_to_sheet_by_headers_sync(sheet, chat_id: str, local_profile: Dict[str, Any]):
    """Synchronous version of _sync_to_sheet_by_headers."""
    try:
        from sheets_core import get_sheet_all_values_cached
        all_values = get_sheet_all_values_cached(sheet)
        if not all_values:
            logging.warning("גיליון ריק או ללא כותרות")
            return

        headers = all_values[0]
        chat_id_col = next((i + 1 for i, h in enumerate(headers) if h.lower() == "chat_id"), None)
        if not chat_id_col:
            logging.warning("עמודת chat_id לא נמצאה בגיליון")
            return

        from sheets_core import find_chat_id_in_sheet
        row_index = find_chat_id_in_sheet(sheet, chat_id, col=chat_id_col) or len(all_values) + 1
        if row_index == len(all_values) + 1:
            sheet.update_cell(row_index, chat_id_col, chat_id)

        # ✅ שיפור: וידוא שכל העמודות קיימות לפני עדכון
        for field, value in local_profile.items():
            try:
                from sheets_core import ensure_column_exists
                col_index = ensure_column_exists(sheet, field)
                
                if col_index:
                    sheet.update_cell(row_index, col_index, str(value))
                    # לוג מיוחד לעדכון הסיכום
                    if field.lower() == "summary":
                        logging.info(f"[SHEETS_SYNC] עודכן סיכום בגוגל שיטס למשתמש {chat_id}: '{value}'")
                    # לוג מיוחד לעדכון השם
                    elif field.lower() == "name":
                        logging.info(f"[SHEETS_SYNC] עודכן שם בגוגל שיטס למשתמש {chat_id}: '{value}'")
                else:
                    logging.warning(f"⚠️ לא ניתן ליצור עמודה '{field}' עבור משתמש {chat_id}")
            except Exception as e:
                logging.debug(f"שגיאה בעדכון שדה {field}: {e}")
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון לפי כותרות: {exc}")


def _schedule_sheets_sync_safely(chat_id: str):
    """Safe wrapper to schedule sheets sync without coroutine issues."""
    try:
        # נסה להשתמש בפונקציה סינכרונית
        _sync_local_to_sheets_sync(chat_id)
    except Exception as exc:
        logging.debug(f"שגיאה בסנכרון לשיטס עבור משתמש {chat_id}: {exc}")
        # אם יש בעיה, לפחות נציין זאת ללוג
        print(f"⚠️ לא ניתן לסנכרן משתמש {chat_id} לשיטס - ימשיך לעבוד מקומית")


# ---------------------------------------------------------------------------
# ✏️  High-level profile update helpers
# ---------------------------------------------------------------------------

def _detect_profile_changes(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    technical_fields = {
        "gpt_c_run_count",
        "code_try",
        "last_update",
        "date_first_seen",
        "timestamp",
        "created_at",
        "updated_at",
    }
    numeric_fields = {"total_messages_count"}  # אפשר להרחיב בעתיד
    changes: List[Dict[str, Any]] = []

    for field, new_val in new.items():
        if field in technical_fields:
            continue
        old_val = old.get(field)
        # חריג: בשדות מספריים, 0 וריק נחשבים אותו דבר
        if field in numeric_fields:
            if (old_val in [None, "", 0] and new_val in [None, "", 0]):
                continue  # לא שינוי אמיתי
        if field not in old:
            if new_val not in [None, ""]:
                changes.append({"field": field, "old_value": None, "new_value": new_val, "change_type": "added"})
                if field.lower() == "name":
                    logging.info(f"[PROFILE_CHANGE] Added name for user: '{new_val}'")
        elif old_val != new_val:
            changes.append({"field": field, "old_value": old_val, "new_value": new_val, "change_type": "updated"})
            if field.lower() == "name":
                logging.info(f"[PROFILE_CHANGE] Updated name for user: '{old_val}' → '{new_val}'")

    for field in old:
        if field not in new and field not in technical_fields:
            changes.append({"field": field, "old_value": old[field], "new_value": None, "change_type": "removed"})
    return changes


def _log_profile_changes_to_chat_history(chat_id: str, changes: List[Dict[str, Any]]):
    """רושם שינויים בפרופיל להיסטוריה לצורכי מעקב (לא נשלח למשתמש)."""
    
    # 🚨 SECURITY FIX: לא מוסיף הודעות פרופיל להיסטוריה
    # כדי למנוע חשיפה של מידע פרטי למשתמש דרך GPT context
    
    # רק לוג פנימי לקובץ debug
    import logging
    try:
        msg_parts = []
        for ch in changes:
            match ch["change_type"]:
                case "added":
                    msg_parts.append(f"נוסף: {ch['field']} = {ch['new_value']}")
                case "updated":
                    msg_parts.append(f"עודכן: {ch['field']} מ-{ch['old_value']} ל-{ch['new_value']}")
                case "removed":
                    msg_parts.append(f"הוסר: {ch['field']} (היה: {ch['old_value']})")
        
        log_message = f"[PROFILE_CHANGE] chat_id={chat_id} | {' | '.join(msg_parts)}"
        logging.info(log_message)
        print(f"🔒 {log_message}")
        
    except Exception as e:
        logging.error(f"שגיאה ברישום שינויים: {e}")


# --- admin notification minimal (HTML formatted) --------------------------------

def _pretty_val(val):
    return "[ריק]" if val in [None, "", [], {}] else str(val)


# --- overview admin notification (HTML) -----------------------------------

def _send_admin_profile_overview_notification(
    *,
    chat_id: str,
    user_msg: str,
    gpt_c_changes: List[Dict[str, Any]],
    gpt_d_changes: List[Dict[str, Any]],
    gpt_e_changes: List[Dict[str, Any]],
    gpt_c_info: str,
    gpt_d_info: str,
    gpt_e_info: str,
    summary: str = "",
):
    """שליחת הודעת אדמין מרוכזת על כל העדכון (GPT-C/D/E + summary) לפי התבנית המדויקת."""
    try:
        from notifications import send_admin_notification_raw
        from utils import get_israel_time

        # ✅ שליחה רק אם יש שינויים
        if not (gpt_c_changes or gpt_d_changes or gpt_e_changes):
            return

        lines: List[str] = []
        
        # 1. כותרת עדכון פרופיל
        lines.append(f"✅ עדכון פרופיל למשתמש {chat_id} ✅")
        
        # 2. תוכן ההודעה המלא (לא מצונזר)
        if user_msg and user_msg.strip():
            lines.append(f"{user_msg.strip()}")
        
        lines.append("")  # שורה ריקה
        
        # 3. GPT-C: שינויים או "אין שינויים"
        lines.append("*GPT-C:*")
        if gpt_c_changes:
            for ch in gpt_c_changes:
                field = ch.get("field")
                # דילוג על שדות טכניים
                if field in ["chat_id", "last_update", "date_first_seen", "code_try", "gpt_c_run_count"]:
                    continue
                old_val = _pretty_val(ch.get("old_value"))
                new_val = _pretty_val(ch.get("new_value"))
                lines.append(f"  ➕ {field}: {old_val} → {new_val}")
        else:
            lines.append("  אין שינויים")
        
        lines.append("")  # שורה ריקה
        
        # 4. GPT-D: שינויים או "אין שינויים"  
        lines.append("*GPT-D:* שדות")
        if gpt_d_changes:
            for ch in gpt_d_changes:
                field = ch.get("field")
                # דילוג על שדות טכניים
                if field in ["chat_id", "last_update", "date_first_seen", "code_try", "gpt_c_run_count"]:
                    continue
                old_val = _pretty_val(ch.get("old_value"))
                new_val = _pretty_val(ch.get("new_value"))
                lines.append(f"  ➕ {field}: {old_val} → {new_val}")
        else:
            lines.append("  אין שינויים")
        
        lines.append("")  # שורה ריקה
        
        # 5. GPT-E: שינויים + קאונטר או "אין שינויים"
        lines.append("GPT-E:")
        if gpt_e_changes:
            for ch in gpt_e_changes:
                field = ch.get("field")
                # דילוג על שדות טכניים
                if field in ["chat_id", "last_update", "date_first_seen", "code_try", "gpt_c_run_count"]:
                    continue
                old_val = _pretty_val(ch.get("old_value"))
                new_val = _pretty_val(ch.get("new_value"))
                lines.append(f"  ➕ {field}: {old_val} → {new_val}")
        else:
            # הוספת קאונטר גם כשאין שינויים
            try:
                from chat_utils import get_user_stats_and_history
                from gpt_e_handler import GPT_E_RUN_EVERY_MESSAGES
                stats, _ = get_user_stats_and_history(chat_id)
                total_messages = stats.get("total_messages", 0)
                lines.append(f"  אין שינויים {total_messages}/{GPT_E_RUN_EVERY_MESSAGES}")
            except:
                lines.append("  אין שינויים")
        
        lines.append("")  # שורה ריקה
        lines.append("")  # שורה ריקה נוספת
        
        # 6. שדה SUMMARY: תוכן השדה המסכם במלואו
        lines.append("שדה SUMMARY:")
        if summary and summary.strip():
            lines.append(f"{summary.strip()}")
        else:
            lines.append("אין סיכום")
        
        lines.append("")  # שורה ריקה
        lines.append("")  # שורה ריקה נוספת
        
        # 7. זמן עדכון ושם הטבלה
        current_time = get_israel_time().strftime('%d/%m/%Y %H:%M:%S')
        lines.append(f"⏰ {current_time} - עודכן במסד נתונים בטבלת user_profiles")

        # שליחת ההודעה
        notification_text = "\n".join(lines)
        send_admin_notification_raw(notification_text)
        
    except Exception as exc:
        logging.error(f"_send_admin_profile_overview_notification failed: {exc}")
        # גיבוי - שליחת הודעה בסיסית במקרה של שגיאה
        try:
            from notifications import send_admin_notification_raw
            send_admin_notification_raw(f"⚠️ שגיאה בהודעת עדכון פרופיל למשתמש {chat_id}: {exc}")
        except:
            pass


# ---------------------------------------------------------------------------
# 📝  Auto-summary generation (moved from sheets_core.py)
# ---------------------------------------------------------------------------

def generate_summary_from_profile_data(profile_data: Dict[str, Any]) -> str:
    """
    Generates an emotional summary string from a user's profile data dict.
    This function is now independent of Google Sheets.
    """
    if not profile_data:
        return ""

    def get_field_priority(field_name):
        # Default priority is high to ensure unknown fields are included
        priority = FIELDS_DICT.get(field_name, {}).get("priority", 99)
        # Ensure priority is a number, default to 99 if not
        return priority if isinstance(priority, (int, float)) else 99

    # Sort fields by priority (lower number = higher priority)
    sorted_fields = sorted(profile_data.keys(), key=get_field_priority)

    summary_parts = []
    technical_fields = {"chat_id", "name", "last_update", "date_first_seen", "code", "code_try", "gpt_c_run_count", "summary"}

    for field in sorted_fields:
        if field in technical_fields:
            continue
        
        value = profile_data.get(field)
        
        # Ensure value is a string and not empty/None
        if isinstance(value, str) and value.strip() and value.strip() != 'לא צוין':
            summary_parts.append(value.strip())
            
    return " | ".join(summary_parts)

# ---------------------------------------------------------------------------
# 📌 Public API (continued)
# ---------------------------------------------------------------------------

def update_user_profile_fast(chat_id: str, updates: Dict[str, Any], send_admin_notification: bool = True):
    try:
        old_profile = get_user_profile_fast(chat_id)
        new_profile = {**old_profile, **updates}

        # auto-generate summary via Google-Sheets helper (optional)
        try:
            auto_summary = generate_summary_from_profile_data(new_profile)
            logging.debug(f"[SUMMARY_DEBUG] Generated auto summary: '{auto_summary}' for user {chat_id}")
            # ✅ תמיד מעדכנים את הסיכום אם יש שינוי בפרופיל
            if auto_summary:
                new_profile["summary"] = auto_summary
                # הוספת הסיכום לעדכונים שנשלחים
                updates["summary"] = auto_summary
                logging.debug(f"[SUMMARY_DEBUG] Updated profile summary for user {chat_id}: '{auto_summary}'")
            else:
                logging.debug(f"[SUMMARY_DEBUG] Empty auto summary generated for user {chat_id}")
        except Exception as e:
            logging.debug(f"שגיאה ביצירת סיכום אוטומטי: {e}")

        changes = _detect_profile_changes(old_profile, new_profile)
        # ✅ הוסר _send_admin_profile_change_notification - משתמשים רק בהודעה המפורטת

        _update_user_profiles_file(chat_id, updates)
        if changes:
            _log_profile_changes_to_chat_history(chat_id, changes)

        # 🔧 תיקון: שימוש בפונקציה סינכרונית בטוחה
        # _schedule_sheets_sync_safely(chat_id) # ⚠️ מנוטרל - עובדים רק עם מסד הנתונים

        # ✅ ההודעה המפורטת נשלחת ממקום אחר - אין צורך בהודעה נוספת כאן

        return True
    except Exception as e:
        logging.error(f"Error updating profile for {chat_id}: {e}")
        return False


def get_user_summary_fast(chat_id: str) -> str:
    try:
        profile = get_user_profile_fast(chat_id)
        return profile.get("summary", "")
    except Exception as exc:
        logging.debug(f"Error getting summary for {chat_id}: {exc}")
        return ""


def update_user_summary_fast(chat_id: str, summary: str):
    update_user_profile_fast(chat_id, {"summary": summary})


def increment_code_try_fast(chat_id: str) -> int:
    try:
        profile = get_user_profile_fast(chat_id)
        new_val = profile.get("code_try", 0) + 1
        update_user_profile_fast(chat_id, {"code_try": new_val})
        return new_val
    except Exception:
        return 1


def increment_gpt_c_run_count_fast(chat_id: str) -> int:
    try:
        profile = get_user_profile_fast(chat_id)
        new_val = profile.get("gpt_c_run_count", 0) + 1
        update_user_profile_fast(chat_id, {"gpt_c_run_count": new_val})
        return new_val
    except Exception:
        return 1


# ---------------------------------------------------------------------------
# 🌱  Emotional-identity helpers
# ---------------------------------------------------------------------------

def update_emotional_identity_fast(chat_id: str, emotional_data: Dict[str, Any]):
    try:
        # ✅ תיקון: הוספת timestamp לנתונים הרגשיים
        emotional_data["last_update"] = utils.get_israel_time().isoformat()
        
        # ✅ תיקון: שימוש ב-update_user_profile_fast במקום _update_user_profiles_file ישירות
        # זה יבטיח שהסיכום יתעדכן אוטומטית
        update_user_profile_fast(chat_id, emotional_data, send_admin_notification=False)
        
        logging.info(f"✅ תעודת זהות רגשית עודכנה עבור משתמש {chat_id}")
        return True
    except Exception as exc:
        logging.error(f"שגיאה בעדכון תעודת זהות רגשית: {exc}")
        # ✅ תיקון: גם במקרה של שגיאה, נשתמש ב-update_user_profile_fast
        try:
            emotional_data["last_update"] = utils.get_israel_time().isoformat()
            update_user_profile_fast(chat_id, emotional_data, send_admin_notification=False)
        except Exception as fallback_exc:
            logging.error(f"שגיאה גם בניסיון הגיבוי: {fallback_exc}")
        return False


def get_emotional_identity_fast(chat_id: str) -> Dict[str, Any]:
    return get_user_profile_fast(chat_id)


def ensure_emotional_identity_consistency(chat_id: str) -> bool:
    try:
        local_profile = get_user_profile_fast(chat_id)
        from sheets_core import get_user_profile_data
        sheets_profile = get_user_profile_data(chat_id)
        matched = local_profile == sheets_profile
        logging.info(
            f"✅ תעודת זהות רגשית {'תואמת' if matched else 'לא תואמת'} עבור משתמש {chat_id}"
        )
        return matched
    except Exception as exc:
        logging.error(f"שגיאה בבדיקת עקביות תעודת זהות רגשית: {exc}")
        return False


def get_all_emotional_identity_fields() -> List[str]:
    return [
        "summary",
        "name",
        "age",
        "pronoun_preference",
        "occupation_or_role",
        "attracted_to",
        "relationship_type",
        "self_religious_affiliation",
        "self_religiosity_level",
        "family_religiosity",
        "closet_status",
        "who_knows",
        "who_doesnt_know",
        "attends_therapy",
        "primary_conflict",
        "trauma_history",
        "goal_in_course",
        "language_of_strength",
        "date_first_seen",
        "coping_strategies",
        "fears_concerns",
        "future_vision",
        "other_insights",
        "last_update",
        "code_try",
        "gpt_c_run_count",
    ]


def validate_emotional_identity_data(emotional_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    for field in ["summary", "age", "last_update"]:
        if not emotional_data.get(field):
            errors.append(f"שדה חובה חסר: {field}")
    if "age" in emotional_data:
        try:
            age = int(emotional_data["age"])
            if age < 13 or age > 120:
                errors.append("גיל לא תקין (חייב להיות בין 13 ל-120)")
        except Exception:
            errors.append("גיל חייב להיות מספר")
    if "summary" in emotional_data and len(emotional_data["summary"]) > 1000:
        errors.append("סיכום ארוך מדי (מקסימום 1000 תווים)")
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# 🛠️  Maintenance helpers
# ---------------------------------------------------------------------------

def force_sync_to_sheets(chat_id: str) -> bool:
    try:
        local_profile = get_user_profile_fast(chat_id)
        if not local_profile:
            logging.warning(f"אין נתונים מקומיים למשתמש {chat_id}")
            return False
        # 🔧 תיקון: שימוש בפונקציה סינכרונית בטוחה
        try:
            _sync_local_to_sheets_sync(chat_id)
        except Exception as exc:
            logging.error(f"שגיאה בסנכרון כפוי: {exc}")
            return False
        logging.info(f"✅ סנכרון כפוי ל-Google Sheets עבור משתמש {chat_id}")
        return True
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון כפוי: {exc}")
        return False


def cleanup_old_profiles(days_old: int = 90) -> int:
    try:
        # Placeholder for DB cleanup if needed
        pass
    except Exception as exc:
        logging.error(f"שגיאה בניקוי פרופילים ישנים: {exc}")
        return 0


def get_profiles_stats() -> Dict[str, Any]:
    try:
        # Placeholder for DB stats if needed
        pass
    except Exception as exc:
        logging.error(f"שגיאה בקבלת סטטיסטיקות פרופילים: {exc}")
        return {} 