"""
sheets_handler.py - ממשק ראשי ל-Google Sheets עם אריכטקטורה חכמה ורזה
"""

# ייבוא הפונקציונליות החדשה מהקבצים הרזים - יבואים ספציפיים במקום wildcard
from sheets_core import (
    debug_log, safe_int, safe_float, check_user_access,
    ensure_user_state_row, register_user, approve_user,
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
