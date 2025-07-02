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
from config import CHAT_HISTORY_PATH, DATA_DIR, USER_PROFILES_PATH
from config import should_log_debug_prints, should_log_message_debug

__all__: List[str] = [
    # Main fast-path helpers
    "get_user_profile_fast",
    "update_user_profile_fast",
    "get_user_summary_fast",
    "update_user_summary_fast",
    "increment_code_try_fast",
    "increment_gpt_c_run_count_fast",
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

# --- משתנה גלובלי לבקרת התראות אדמין (הכרחי לתאימות) ---
from utils import _disable_auto_admin_profile_notification  # type: ignore

# ---------------------------------------------------------------------------
# 🔍  קריאה וכתיבה מהירה לקובץ USER_PROFILES_PATH
# ---------------------------------------------------------------------------

def get_user_profile_fast(chat_id: str) -> Dict[str, Any]:
    """טוען במהירות את הפרופיל מקובץ JSON המקומי."""
    try:
        with open(USER_PROFILES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(chat_id), {})
    except Exception:
        return {}


def _update_user_profiles_file(chat_id: str, updates: Dict[str, Any]):
    """Low-level helper that writes the updated profile dictionary to disk."""
    try:
        try:
            with open(USER_PROFILES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        cid = str(chat_id)
        data.setdefault(cid, {}).update(updates)
        data[cid]["last_update"] = utils.get_israel_time().isoformat()

        with open(USER_PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logging.error(f"שגיאה בעדכון קובץ פרופילים: {exc}")


# ---------------------------------------------------------------------------
# 🔄  Sync helpers – local profile ⇄ Google Sheets
# ---------------------------------------------------------------------------

async def _sync_to_sheet_by_headers(sheet, chat_id: str, local_profile: Dict[str, Any]):
    """Synchronise fields by header names (not by fixed column indices)."""
    try:
        all_values = sheet.get_all_values()
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

        field_to_col = {h.lower(): i + 1 for i, h in enumerate(headers)}
        for field, value in local_profile.items():
            col_index = field_to_col.get(field.lower())
            if not col_index:
                continue
            try:
                sheet.update_cell(row_index, col_index, str(value))
            except Exception as e:
                logging.debug(f"שגיאה בעדכון שדה {field}: {e}")
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון לפי כותרות: {exc}")


async def _sync_local_to_sheets_background(chat_id: str):
    """Background task – push the local profile to Google Sheets."""
    try:
        local_profile = get_user_profile_fast(chat_id)
        if not local_profile:
            logging.warning(f"אין נתונים מקומיים למשתמש {chat_id}")
            return

        from sheets_core import setup_google_sheets
        gc, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        await _sync_to_sheet_by_headers(sheet_users, chat_id, local_profile)
        await _sync_to_sheet_by_headers(sheet_states, chat_id, local_profile)
        logging.info(f"✅ Google Sheets סונכרן עבור משתמש {chat_id}")
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון ל-Google Sheets: {exc}")


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
    changes: List[Dict[str, Any]] = []

    for field, new_val in new.items():
        if field in technical_fields:
            continue
        old_val = old.get(field)
        if field not in old:
            if new_val not in [None, ""]:
                changes.append({"field": field, "old_value": None, "new_value": new_val, "change_type": "added"})
        elif old_val != new_val:
            changes.append({"field": field, "old_value": old_val, "new_value": new_val, "change_type": "updated"})

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
    """שליחת הודעת אדמין מרוכזת על כל העדכון (GPT-C/D/E + summary)."""
    try:
        from notifications import send_admin_notification_raw

        lines: List[str] = [f"<b>✅ עדכון פרופיל למשתמש <code>{chat_id}</code> ✅</b>"]

        if user_msg:
            trimmed = user_msg.strip()[:100] + "..." if len(user_msg.strip()) > 100 else user_msg.strip()
            lines.append(f"<i>{trimmed}</i>")

        lines.append("")
        lines.append(f"<b>GPT-C</b>: {gpt_c_info}")
        # הצגת השדות שחולצו על ידי GPT-C
        if gpt_c_changes:
            for ch in gpt_c_changes:
                field = ch.get("field")
                old_val = _pretty_val(ch.get("old_value"))
                new_val = _pretty_val(ch.get("new_value"))
                ct = ch.get("change_type")
                if ct == "added":
                    lines.append(f"  ➕ {field}: [ריק] → [{new_val}]")
                elif ct == "updated":
                    lines.append(f"  ✏️ {field}: [{old_val}] → [{new_val}]")
                elif ct == "removed":
                    lines.append(f"  ➖ {field}: [{old_val}] → <i>נמחק</i>")

        lines.append("")
        lines.append(f"<b>GPT-D</b>: {gpt_d_info}")
        # הצגת שדות רק אם GPT-D באמת הופעל ויש שדות שמוזגו
        if gpt_d_changes:
            for ch in gpt_d_changes:
                field = ch.get("field")
                old_val = _pretty_val(ch.get("old_value"))
                new_val = _pretty_val(ch.get("new_value"))
                ct = ch.get("change_type")
                if ct == "added":
                    lines.append(f"  ➕ {field}: [ריק] → [{new_val}]")
                elif ct == "updated":
                    lines.append(f"  ✏️ {field}: [{old_val}] → [{new_val}]")
                elif ct == "removed":
                    lines.append(f"  ➖ {field}: [{old_val}] → <i>נמחק</i>")

        lines.append("")
        lines.append(f"<b>GPT-E</b>: {gpt_e_info}")
        # הצגת שדות רק אם GPT-E באמת הופעל ויש שדות חדשים
        if gpt_e_changes:
            for ch in gpt_e_changes:
                field = ch.get("field")
                old_val = _pretty_val(ch.get("old_value"))
                new_val = _pretty_val(ch.get("new_value"))
                ct = ch.get("change_type")
                if ct == "added":
                    lines.append(f"  ➕ {field}: [ריק] → [{new_val}]")
                elif ct == "updated":
                    lines.append(f"  ✏️ {field}: [{old_val}] → [{new_val}]")
                elif ct == "removed":
                    lines.append(f"  ➖ {field}: [{old_val}] → <i>נמחק</i>")

        if summary and summary.strip():
            lines.append("")
            lines.append(f"<b>Summary</b>: {summary[:200]}{'...' if len(summary) > 200 else ''}")

        # הצגת סנכרון רק אם יש שינויים בכלל
        if gpt_c_changes or gpt_d_changes or gpt_e_changes:
            lines.append("")
            lines.append("<b>סנכרון</b>: עודכן בקובץ user_profiles.json ולאחר מכן בגוגל שיטס - הכל מסונכרן")

        # 🔧 הוספת זמן בסוף ההודעה
        from utils import get_israel_time
        lines.append("")
        lines.append(f"⏰ {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}")

        send_admin_notification_raw("\n".join(lines))
    except Exception as exc:
        logging.error(f"_send_admin_profile_overview_notification failed: {exc}")


# ---------------------------------------------------------------------------
# 📌 Public API
# ---------------------------------------------------------------------------

def update_user_profile_fast(chat_id: str, updates: Dict[str, Any], send_admin_notification: bool = True):
    try:
        old_profile = get_user_profile_fast(chat_id)
        new_profile = {**old_profile, **updates}

        # auto-generate summary via Google-Sheets helper (optional)
        try:
            from sheets_core import generate_summary_from_profile_data
            auto_summary = generate_summary_from_profile_data(new_profile)
            # ✅ תמיד מעדכנים את הסיכום אם יש שינוי בפרופיל
            if auto_summary:
                new_profile["summary"] = auto_summary
                # הוספת הסיכום לעדכונים שנשלחים
                updates["summary"] = auto_summary
        except Exception as e:
            logging.debug(f"שגיאה ביצירת סיכום אוטומטי: {e}")

        changes = _detect_profile_changes(old_profile, new_profile)
        # ✅ הוסר _send_admin_profile_change_notification - משתמשים רק בהודעה המפורטת

        _update_user_profiles_file(chat_id, updates)
        if changes:
            _log_profile_changes_to_chat_history(chat_id, changes)

        # 🔧 תיקון: שימוש ב-asyncio.run במקום create_task בפונקציה סינכרונית
        try:
            import asyncio
            asyncio.run(_sync_local_to_sheets_background(chat_id))
        except RuntimeError:
            # אם כבר יש event loop פעיל, נשתמש ב-create_task
            try:
                asyncio.create_task(_sync_local_to_sheets_background(chat_id))
            except RuntimeError:
                # אם גם זה לא עובד, נדלג על הסנכרון
                logging.debug(f"לא ניתן לסנכרן ל-Sheets עבור משתמש {chat_id} - אין event loop")

        # ✅ שליחת הודעת אדמין אם יש שינויים
        if send_admin_notification and not _disable_auto_admin_profile_notification and changes:
            try:
                from notifications import send_admin_notification_raw
                changes_text = []
                for change in changes[:3]:  # רק 3 השינויים הראשונים
                    field = change.get("field", "")
                    old_val = _pretty_val(change.get("old_value", ""))
                    new_val = _pretty_val(change.get("new_value", ""))
                    change_type = change.get("change_type", "")
                    
                    if change_type == "added":
                        changes_text.append(f"➕ {field}: [{new_val}]")
                    elif change_type == "updated":
                        changes_text.append(f"✏️ {field}: [{old_val}] → [{new_val}]")
                    elif change_type == "removed":
                        changes_text.append(f"➖ {field}: [{old_val}] → נמחק")
                
                if changes_text:
                    message = f"<b>✅ עדכון פרופיל למשתמש <code>{chat_id}</code></b>\n\n" + "\n".join(changes_text)
                    send_admin_notification_raw(message)
            except Exception as e:
                logging.error(f"שגיאה בשליחת הודעת אדמין: {e}")

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
        # 🔧 תיקון: שימוש ב-asyncio.run במקום create_task בפונקציה סינכרונית
        try:
            import asyncio
            asyncio.run(_sync_local_to_sheets_background(chat_id))
        except RuntimeError:
            try:
                asyncio.create_task(_sync_local_to_sheets_background(chat_id))
            except RuntimeError:
                logging.debug(f"לא ניתן לסנכרן ל-Sheets עבור משתמש {chat_id} - אין event loop")
                return False
        logging.info(f"✅ סנכרון כפוי ל-Google Sheets עבור משתמש {chat_id}")
        return True
    except Exception as exc:
        logging.error(f"שגיאה בסנכרון כפוי: {exc}")
        return False


def cleanup_old_profiles(days_old: int = 90) -> int:
    try:
        cutoff = utils.get_effective_time("datetime") - timedelta(days=days_old)
        try:
            with open(USER_PROFILES_PATH, "r", encoding="utf-8") as f:
                profiles = json.load(f)
        except Exception:
            return 0
        to_remove = []
        for cid, profile in profiles.items():
            lu_str = profile.get("last_update", "")
            try:
                lu_dt = datetime.fromisoformat(lu_str.replace("Z", "+00:00")) if lu_str else None
            except Exception:
                lu_dt = None
            if not lu_dt or lu_dt < cutoff:
                to_remove.append(cid)
        for cid in to_remove:
            del profiles[cid]
        if to_remove:
            with open(USER_PROFILES_PATH, "w", encoding="utf-8") as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)
            logging.info(f"✅ נמחקו {len(to_remove)} פרופילים ישנים (>{days_old} ימים)")
        return len(to_remove)
    except Exception as exc:
        logging.error(f"שגיאה בניקוי פרופילים ישנים: {exc}")
        return 0


def get_profiles_stats() -> Dict[str, Any]:
    try:
        try:
            with open(USER_PROFILES_PATH, "r", encoding="utf-8") as f:
                profiles = json.load(f)
        except Exception:
            profiles = {}
        total = len(profiles)
        cutoff = utils.get_effective_time("datetime") - timedelta(days=30)
        active = 0
        for p in profiles.values():
            lu_str = p.get("last_update", "")
            try:
                lu_dt = datetime.fromisoformat(lu_str.replace("Z", "+00:00")) if lu_str else None
            except Exception:
                continue
            if lu_dt and lu_dt > cutoff:
                active += 1
        return {
            "total_profiles": total,
            "active_profiles": active,
            "inactive_profiles": total - active,
            "file_size_mb": os.path.getsize(USER_PROFILES_PATH) / (1024 * 1024) if os.path.exists(USER_PROFILES_PATH) else 0,
        }
    except Exception as exc:
        logging.error(f"שגיאה בקבלת סטטיסטיקות פרופילים: {exc}")
        return {} 