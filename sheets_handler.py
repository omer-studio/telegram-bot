"""
sheets_handler.py - ממשק ראשי ל-Google Sheets עם אריכטקטורה חכמה ורזה
"""

# ייבוא הפונקציונליות החדשה מהקבצים הרזים
from sheets_core import *
from sheets_advanced import *

# ייבואים נוספים נדרשים
import asyncio
import logging
from config import SUMMARY_FIELD, setup_google_sheets, should_log_sheets_debug
from messages import new_user_admin_message
from notifications import send_error_notification
from fields_dict import FIELDS_DICT

# יצירת חיבור לגיליונות (מתקן - מחזיר 3 ערכים, לא 4)
sheet_users, sheet_log, sheet_states = setup_google_sheets()

# Aliases לתאימות לאחור:
debug_log = debug_log
log_to_sheets = log_to_sheets_async
update_user_profile = update_user_profile_async
increment_code_try = increment_code_try_async

print("✅ sheets_handler.py טען בהצלחה עם אריכטקטורה חדשה!")
