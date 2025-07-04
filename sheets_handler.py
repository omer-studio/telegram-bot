"""
sheets_handler.py - ממשק ראשי ל-Google Sheets עם אריכטקטורה חכמה ורזה
"""

# ייבוא הפונקציונליות החדשה מהקבצים הרזים - יבואים ספציפיים במקום wildcard
from sheets_core import (
    debug_log, safe_int, safe_float, check_user_access,
    ensure_user_state_row, register_user as _core_register_user, approve_user as _core_approve_user,
    delete_row_by_chat_id, get_user_state, update_user_state, increment_code_try_sync,
    get_user_summary, update_user_profile_data, find_chat_id_in_sheet, increment_gpt_c_run_count,
    reset_gpt_c_run_count
)
from sheets_advanced import (
    SheetsQueueManager, sheets_queue_manager, log_to_sheets_sync, 
    update_user_profile_sync, log_to_sheets_async, update_user_profile_async,
    increment_code_try_async, clean_cost_value, format_money, calculate_costs_unified
)

# ייבואים נוספים נדרשים
import asyncio
import logging
from config import SUMMARY_FIELD, setup_google_sheets, should_log_sheets_debug
from messages import new_user_admin_message
from notifications import send_error_notification
from fields_dict import FIELDS_DICT

# יצירת חיבור לגיליונות (מתקן - עכשיו מחזיר 4 ערכים כמצופה)
gs_client, sheet_users, sheet_log, sheet_states = setup_google_sheets()

# Aliases לתאימות לאחור:
debug_log = debug_log
log_to_sheets = log_to_sheets_async
update_user_profile = update_user_profile_async
increment_code_try = increment_code_try_async

# פונקציות נוספות שנדרשות:
find_chat_id_in_sheet = find_chat_id_in_sheet
increment_gpt_c_run_count = increment_gpt_c_run_count
reset_gpt_c_run_count = reset_gpt_c_run_count

# Sheet objects שנדרשים לייבוא חיצוני:
sheet_users = sheet_users
sheet_log = sheet_log
sheet_states = sheet_states

print("✅ sheets_handler.py טען בהצלחה עם אריכטקטורה חדשה!")

# -----------------------------------------------------
# עטיפות תאימות (Backward-compatibility wrappers)
# -----------------------------------------------------

def register_user(chat_id, code_input=None):
    """
    Wrapper for sheets_core.register_user providing a dict response as
    expected by message_handler. When code_input is provided, attempts to
    attach the chat_id to that code. Falls back to legacy behaviour if
    code_input is None.
    """
    try:
        if code_input is not None:
            # נסיון רישום מלא עם קוד
            success = _core_register_user(sheet_users, str(chat_id), str(code_input))
            # מבטיח שקיימת שורה ב-user_states (לצורך מונים עתידיים)
            ensure_user_state_row(sheet_users, sheet_states, str(chat_id))
            
            # 🔧 תיקון קריטי: ניקוי cache אחרי רישום מוצלח
            if success:
                from sheets_core import _clear_user_cache
                _clear_user_cache(str(chat_id))
                print(f"[REGISTER_DEBUG] רישום מוצלח + ניקוי cache עבור {chat_id}")
            
            return {"success": bool(success)}

        # 🔙 Legacy path – ללא קוד (לא מומלץ)
        state_ok = ensure_user_state_row(sheet_users, sheet_states, str(chat_id))
        return {"success": bool(state_ok)}

    except Exception as e:
        logging.error(f"[SheetsHandler] register_user wrapper failed for {chat_id}: {e}")
        try:
            send_error_notification(error_message=f"register_user wrapper error: {e}", chat_id=str(chat_id))
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def approve_user(chat_id):
    """
    Wrapper around sheets_core.approve_user returning a dict like
    {"success": bool} as expected by message_handler.
    """
    try:
        success = _core_approve_user(sheet_users, str(chat_id))
        
        # 🔧 תיקון קריטי: ניקוי cache אחרי אישור מוצלח
        if success:
            from sheets_core import _clear_user_cache
            _clear_user_cache(str(chat_id))
            print(f"[APPROVE_DEBUG] אישור מוצלח + ניקוי cache עבור {chat_id}")
        
        if not success:
            try:
                # התראה לאדמין על כישלון אישור
                send_error_notification(error_message="approve_user failed", chat_id=str(chat_id))
            except Exception:
                pass
        return {"success": bool(success)}
    except Exception as e:
        logging.error(f"[SheetsHandler] approve_user wrapper failed for {chat_id}: {e}")
        try:
            send_error_notification(error_message=f"approve_user wrapper error: {e}", chat_id=str(chat_id))
        except Exception:
            pass
        return {"success": False, "error": str(e)}
