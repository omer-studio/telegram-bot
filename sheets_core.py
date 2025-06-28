"""
sheets_core.py - ליבה לטיפול ב-Google Sheets עם ביצועים מהירים
מכיל את כל הפונקציות הבסיסיות לקריאה וכתיבה לגיליונות
"""

import gspread
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from oauth2client.service_account import ServiceAccountCredentials
from config import setup_google_sheets, SUMMARY_FIELD, should_log_sheets_debug
from notifications import send_error_notification
from fields_dict import FIELDS_DICT

# ================================
# 🚀 מנגנון Cache לנתוני משתמשים
# ================================

_user_data_cache = {}  # Cache לנתוני משתמשים
_cache_timestamps = {}  # זמני יצירת Cache
CACHE_DURATION_SECONDS = 600  # 10 דקות cache (הוגדל מ-5 דקות)

# Cache נפרד לנתונים קריטיים עם זמן חיים ארוך יותר
_critical_data_cache = {}  # Cache לנתונים קריטיים (פרופיל משתמש, הרשאות)
_critical_cache_timestamps = {}
CRITICAL_CACHE_DURATION_SECONDS = 1800  # 30 דקות cache לנתונים קריטיים

# ===================================
# 📊 מונה קריאות Google Sheets API
# ===================================

_api_calls_count = 0  # מונה קריאות כולל
_api_calls_per_minute = {}  # מונה קריאות לפי דקה

def _increment_api_call():
    """מספר קריאה ל-Google Sheets API"""
    global _api_calls_count
    _api_calls_count += 1
    
    # מונה לפי דקה
    minute_key = int(time.time() / 60)
    if minute_key not in _api_calls_per_minute:
        _api_calls_per_minute[minute_key] = 0
    _api_calls_per_minute[minute_key] += 1
    
    # ניקוי דקות ישנות (שמור רק 5 דקות אחרונות)
    old_minutes = [k for k in _api_calls_per_minute.keys() if k < minute_key - 5]
    for old_minute in old_minutes:
        del _api_calls_per_minute[old_minute]
    
    debug_log(f"🔍 API call #{_api_calls_count} (this minute: {_api_calls_per_minute[minute_key]})")

def get_api_stats():
    """מחזיר סטטיסטיקות של קריאות API"""
    current_minute = int(time.time() / 60)
    calls_this_minute = _api_calls_per_minute.get(current_minute, 0)
    
    return {
        "total_calls": _api_calls_count,
        "calls_this_minute": calls_this_minute,
        "calls_per_minute": dict(_api_calls_per_minute)
    }

def _get_cache_key(operation: str, chat_id: str) -> str:
    """יוצר מפתח cache"""
    return f"{operation}:{chat_id}"

def _is_cache_valid(cache_key: str) -> bool:
    """בודק אם ה-cache עדיין תקף"""
    if cache_key not in _cache_timestamps:
        return False
    
    age = time.time() - _cache_timestamps[cache_key]
    return age < CACHE_DURATION_SECONDS

def _get_from_cache(cache_key: str):
    """מחזיר נתונים מה-cache אם תקפים"""
    if _is_cache_valid(cache_key):
        debug_log(f"📥 Cache HIT: {cache_key}")
        return _user_data_cache.get(cache_key)
    return None

def _get_from_critical_cache(cache_key: str):
    """מחזיר נתונים קריטיים מה-cache אם תקפים"""
    if cache_key not in _critical_cache_timestamps:
        return None
    
    age = time.time() - _critical_cache_timestamps[cache_key]
    if age < CRITICAL_CACHE_DURATION_SECONDS:
        debug_log(f"📥 Critical Cache HIT: {cache_key}")
        return _critical_data_cache.get(cache_key)
    return None

def _set_cache(cache_key: str, data):
    """שומר נתונים ב-cache"""
    _user_data_cache[cache_key] = data
    _cache_timestamps[cache_key] = time.time()
    debug_log(f"📤 Cache SET: {cache_key}")

def _set_critical_cache(cache_key: str, data):
    """שומר נתונים קריטיים ב-cache עם זמן חיים ארוך יותר"""
    _critical_data_cache[cache_key] = data
    _critical_cache_timestamps[cache_key] = time.time()
    debug_log(f"📤 Critical Cache SET: {cache_key}")

def _clear_user_cache(chat_id: str):
    """מנקה cache של משתמש ספציפי (למשל אחרי עדכון)"""
    keys_to_remove = [key for key in _user_data_cache.keys() if key.endswith(f":{chat_id}")]
    for key in keys_to_remove:
        if key in _user_data_cache:
            del _user_data_cache[key]
        if key in _cache_timestamps:
            del _cache_timestamps[key]
    
    # ניקוי גם מה-critical cache
    critical_keys_to_remove = [key for key in _critical_data_cache.keys() if key.endswith(f":{chat_id}")]
    for key in critical_keys_to_remove:
        if key in _critical_data_cache:
            del _critical_data_cache[key]
        if key in _critical_cache_timestamps:
            del _critical_cache_timestamps[key]
    
    debug_log(f"🗑️ Cache CLEARED for user {chat_id}")

def _cleanup_expired_cache():
    """ניקוי cache מיותר (נקרא מדי פעם)"""
    now = time.time()
    expired_keys = []
    
    for key, timestamp in _cache_timestamps.items():
        if (now - timestamp) > CACHE_DURATION_SECONDS:
            expired_keys.append(key)
    
    for key in expired_keys:
        if key in _user_data_cache:
            del _user_data_cache[key]
        if key in _cache_timestamps:
            del _cache_timestamps[key]
    
    # ניקוי critical cache
    critical_expired_keys = []
    for key, timestamp in _critical_cache_timestamps.items():
        if (now - timestamp) > CRITICAL_CACHE_DURATION_SECONDS:
            critical_expired_keys.append(key)
    
    for key in critical_expired_keys:
        if key in _critical_data_cache:
            del _critical_data_cache[key]
        if key in _critical_cache_timestamps:
            del _critical_cache_timestamps[key]
    
    total_cleaned = len(expired_keys) + len(critical_expired_keys)
    if total_cleaned > 0:
        debug_log(f"🧹 Cache CLEANUP: removed {total_cleaned} expired entries ({len(expired_keys)} regular, {len(critical_expired_keys)} critical)")

# ================================
# 🔧 פונקציות עזר
# ================================

def debug_log(message: str, component: str = "SheetsCore", chat_id: str = ""):
    """רישום debug עם תמיכה ב-chat_id"""
    if chat_id:
        print(f"[DEBUG][{component}][{chat_id}] {message}", flush=True)
    else:
        print(f"[DEBUG][{component}] {message}", flush=True)

def safe_int(val) -> int:
    """המרה בטוחה למספר שלם"""
    try:
        return int(float(str(val))) if val else 0
    except (ValueError, TypeError):
        return 0

def safe_float(val) -> float:
    """המרה בטוחה למספר עשרוני"""
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0

def clean_for_storage(data) -> str:
    """ניקוי נתונים לפני שמירה בגיליון"""
    if data is None:
        return ""
    text = str(data).strip()
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = ' '.join(text.split())
    return text

def validate_chat_id(chat_id) -> str:
    """וידוא ש-chat_id תקף"""
    return str(chat_id).strip()

def find_chat_id_in_sheet(sheet, chat_id: str, col: int = 1) -> Optional[int]:
    """
    מחפש chat_id בגיליון ומחזיר את מספר השורה
    עם cache לביצועים מהירים
    """
    chat_id = validate_chat_id(chat_id)
    cache_key = _get_cache_key("find_chat_id", f"{sheet.title}:{chat_id}")
    
    # בדיקת cache
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        all_chat_ids = sheet.col_values(col)
        
        for i, existing_chat_id in enumerate(all_chat_ids):
            if str(existing_chat_id).strip() == chat_id:
                row_num = i + 1
                _set_cache(cache_key, row_num)  # שמירה ב-cache
                return row_num
        
        _set_cache(cache_key, None)  # שמירה ב-cache שלא נמצא
        return None
        
    except Exception as e:
        debug_log(f"Error finding chat_id {chat_id} in sheet: {e}")
        return None

# ניקוי cache מיותר כל דקה
import threading
def _cache_cleanup_thread():
    while True:
        time.sleep(60)  # דקה
        try:
            _cleanup_expired_cache()
        except Exception as e:
            debug_log(f"Error in cache cleanup: {e}")

# הפעלת thread לניקוי cache
cleanup_thread = threading.Thread(target=_cache_cleanup_thread, daemon=True)
cleanup_thread.start()

def check_user_access(sheet, chat_id: str) -> Dict[str, Any]:
    try:
        chat_id = validate_chat_id(chat_id)
        
        # בדיקת critical cache קודם (הרשאות נשמרות יותר זמן)
        cache_key = _get_cache_key("user_access", chat_id)
        cached_access = _get_from_critical_cache(cache_key)
        if cached_access is not None:
            return cached_access
        
        # בדיקת cache רגיל
        cached_access = _get_from_cache(cache_key)
        if cached_access is not None:
            return cached_access
        
        row_index = find_chat_id_in_sheet(sheet, chat_id, col=1)
        
        if not row_index:
            result = {"status": "not_found", "code": None}
            _set_critical_cache(cache_key, result)  # שמירה ב-critical cache
            return result
        
        # מונה קריאות ל-API (2 קריאות: status + code)
        _increment_api_call()
        _increment_api_call()
        status = sheet.cell(row_index, 3).value
        code = sheet.cell(row_index, 2).value
        
        result = {"status": status, "code": code}
        _set_critical_cache(cache_key, result)  # שמירה ב-critical cache
        
        debug_log(f"User {chat_id} access check: status={status}, code={code}")
        return result
        
    except Exception as e:
        debug_log(f"Error checking access for {chat_id}: {e}")
        error_result = {"status": "error", "code": None}
        return error_result

def ensure_user_state_row(sheet_users, sheet_states, chat_id: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        
        row_index = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
        if row_index:
            debug_log(f"User {chat_id} already exists in user_states at row {row_index}")
            return True
        
        from utils import get_israel_time
        timestamp = get_israel_time().strftime('%Y-%m-%d %H:%M:%S')
        new_row = [chat_id, "0", "", "", "", timestamp, "0"]
        
        sheet_states.append_row(new_row)
        debug_log(f"Added new user {chat_id} to user_states")
        return True
        
    except Exception as e:
        debug_log(f"Error ensuring user state row for {chat_id}: {e}")
        send_error_notification(f"Error in ensure_user_state_row: {e}")
        return False

def register_user(sheet, chat_id: str, code_input: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        from utils import get_israel_time
        timestamp = get_israel_time().strftime('%Y-%m-%d %H:%M:%S')
        
        new_row = [chat_id, str(code_input), "pending", timestamp]
        sheet.append_row(new_row)
        
        # מחיקת cache אחרי רישום משתמש חדש
        _clear_user_cache(chat_id)
        
        debug_log(f"Registered new user {chat_id} with code {code_input}")
        return True
        
    except Exception as e:
        debug_log(f"Error registering user {chat_id}: {e}")
        send_error_notification(f"Error in register_user: {e}")
        return False

def approve_user(sheet, chat_id: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        row_index = find_chat_id_in_sheet(sheet, chat_id, col=1)
        
        if not row_index:
            debug_log(f"Cannot approve user {chat_id} - not found")
            return False
        
        sheet.update_cell(row_index, 3, "approved")
        
        # מחיקת cache אחרי עדכון סטטוס
        _clear_user_cache(chat_id)
        
        debug_log(f"Approved user {chat_id}")
        return True
        
    except Exception as e:
        debug_log(f"Error approving user {chat_id}: {e}")
        return False

def delete_row_by_chat_id(sheet_name: str, chat_id: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        gc, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        sheet_map = {"users": sheet_users, "states": sheet_states, "logs": sheet_log}
        sheet = sheet_map.get(sheet_name)
        
        if not sheet:
            debug_log(f"Unknown sheet name: {sheet_name}")
            return False
        
        row_index = find_chat_id_in_sheet(sheet, chat_id, col=1)
        if not row_index:
            debug_log(f"User {chat_id} not found in {sheet_name}")
            return False
        
        sheet.delete_rows(row_index)
        
        # מחיקת cache אחרי מחיקת משתמש
        _clear_user_cache(chat_id)
        
        debug_log(f"Deleted row {row_index} for user {chat_id} from {sheet_name}")
        return True
        
    except Exception as e:
        debug_log(f"Error deleting row for {chat_id} from {sheet_name}: {e}")
        send_error_notification(f"Error in delete_row_by_chat_id: {e}")
        return False

def get_user_state(chat_id: str) -> Dict[str, Any]:
    try:
        chat_id = validate_chat_id(chat_id)
        
        # בדיקת cache קודם
        cache_key = _get_cache_key("user_state", chat_id)
        cached_state = _get_from_cache(cache_key)
        if cached_state is not None:
            return cached_state
        
        # אם אין ב-cache, קורא מהשיטס
        gc, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        if not sheet_states:
            debug_log("sheet_states is None", chat_id=chat_id)
            return {}
        
        row_index = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
        if not row_index:
            debug_log(f"User {chat_id} not found in user_states")
            empty_state = {}
            _set_cache(cache_key, empty_state)  # cache גם תוצאות ריקות
            return empty_state
        
        # מונה קריאה ל-API
        _increment_api_call()
        row_data = sheet_states.row_values(row_index)
        
        state = {
            "chat_id": row_data[0] if len(row_data) > 0 else "",
            "code_try": safe_int(row_data[1]) if len(row_data) > 1 else 0,
            "summary": row_data[2] if len(row_data) > 2 else "",
            "last_updated": row_data[3] if len(row_data) > 3 else "",
            "profile_data": row_data[4] if len(row_data) > 4 else "",
            "created_at": row_data[5] if len(row_data) > 5 else "",
            "gpt_c_run_count": safe_int(row_data[6]) if len(row_data) > 6 else 0
        }
        
        if state["profile_data"]:
            try:
                state["profile_data"] = json.loads(state["profile_data"])
            except json.JSONDecodeError:
                debug_log(f"Invalid JSON in profile_data for user {chat_id}")
                state["profile_data"] = {}
        else:
            state["profile_data"] = {}
        
        # שמירה ב-cache
        _set_cache(cache_key, state)
        debug_log(f"Retrieved state for user {chat_id}")
        return state
        
    except Exception as e:
        debug_log(f"Error getting user state for {chat_id}: {e}")
        send_error_notification(f"Error in get_user_state: {e}")
        return {}

def update_user_state(chat_id: str, updates: Dict[str, Any]) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        gc, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        if not sheet_states:
            debug_log("sheet_states is None", chat_id=chat_id)
            return False
        
        row_index = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
        if not row_index:
            debug_log(f"User {chat_id} not found in user_states")
            return False
        
        column_mapping = {
            "code_try": 2, "summary": 3, "last_updated": 4,
            "profile_data": 5, "created_at": 6, "gpt_c_run_count": 7
        }
        
        updated_fields = []
        for field, value in updates.items():
            if field in column_mapping:
                col_index = column_mapping[field]
                
                if field == "profile_data" and isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False)
                
                sheet_states.update_cell(row_index, col_index, str(value))
                updated_fields.append(field)
                debug_log(f"Updated {field} for user {chat_id}")
        
        if updated_fields and "last_updated" not in updates:
            from utils import get_israel_time
            timestamp = get_israel_time().strftime('%Y-%m-%d %H:%M:%S')
            sheet_states.update_cell(row_index, column_mapping["last_updated"], timestamp)
            updated_fields.append("last_updated")
        
        debug_log(f"Updated fields {updated_fields} for user {chat_id}")
        
        # מחיקת cache אחרי עדכון
        _clear_user_cache(chat_id)
        
        return True
        
    except Exception as e:
        debug_log(f"Error updating user state for {chat_id}: {e}")
        send_error_notification(f"Error in update_user_state: {e}")
        return False

def increment_code_try_sync(sheet_states, chat_id: str) -> int:
    """עכשיו מעדכן מהיר + Google Sheets ברקע"""
    from utils import increment_code_try_fast
    return increment_code_try_fast(chat_id)  # מהיר!

def increment_gpt_c_run_count(chat_id: str) -> int:
    """עכשיו מעדכן מהיר + Google Sheets ברקע"""
    from utils import increment_gpt_c_run_count_fast
    return increment_gpt_c_run_count_fast(chat_id)  # מהיר!

def reset_gpt_c_run_count(chat_id: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        success = update_user_state(chat_id, {"gpt_c_run_count": 0})
        
        if success:
            debug_log(f"Reset GPT-C count for user {chat_id}")
        else:
            debug_log(f"Failed to reset GPT-C count for user {chat_id}")
        
        return success
        
    except Exception as e:
        debug_log(f"Error resetting GPT-C count for {chat_id}: {e}")
        send_error_notification(f"Error in reset_gpt_c_run_count: {e}")
        return False

def get_user_summary(chat_id: str) -> str:
    """עכשיו קורא מהיר מ-chat_history.json"""
    from utils import get_user_summary_fast
    return get_user_summary_fast(chat_id)  # מהיר!

def update_user_summary(chat_id: str, new_summary: str) -> bool:
    """עכשיו מעדכן מהיר + Google Sheets ברקע"""
    from utils import update_user_summary_fast
    update_user_summary_fast(chat_id, new_summary)  # מהיר!
    return True

def get_user_profile_data(chat_id: str) -> Dict[str, Any]:
    """עכשיו קורא מהיר מ-chat_history.json"""
    from utils import get_user_profile_fast
    return get_user_profile_fast(chat_id)  # מהיר!

def update_user_profile_data(chat_id: str, profile_updates: Dict[str, Any]) -> bool:
    """עכשיו מעדכן מהיר + Google Sheets ברקע"""
    from utils import update_user_profile_fast
    update_user_profile_fast(chat_id, profile_updates)  # מהיר!
    return True

def generate_summary_from_profile_data(profile_data: Dict[str, Any]) -> str:
    """
    יוצר summary אוטומטי מנתוני הפרופיל בהתבסס על fields_dict
    מסתכל רק על שדות שיש להם show_in_summary ושהם מלאים
    """
    if not profile_data:
        return ""
    
    summary_parts = []
    
    # עובר על השדות לפי הסדר שהם מופיעים ב-fields_dict
    for field_name, field_info in FIELDS_DICT.items():
        # רק שדות שיש להם show_in_summary
        if "show_in_summary" not in field_info:
            continue
            
        field_value = profile_data.get(field_name, "")
        
        # רק אם השדה מלא
        if field_value and str(field_value).strip():
            show_label = field_info["show_in_summary"]
            clean_value = str(field_value).strip()
            
            if show_label:  # יש label מיוחד
                summary_parts.append(f"{show_label} {clean_value}")
            else:  # אין label - רק הערך
                summary_parts.append(clean_value)
    
    return " | ".join(summary_parts)

def compose_emotional_summary(row: List[str]) -> str:
    try:
        if not row or len(row) < 4:
            return ""
        
        name = row[1] if len(row) > 1 else ""
        age = row[2] if len(row) > 2 else ""
        location = row[3] if len(row) > 3 else ""
        mood = row[4] if len(row) > 4 else ""
        
        summary_parts = []
        if name: summary_parts.append(f"שם: {name}")
        if age: summary_parts.append(f"גיל: {age}")
        if location: summary_parts.append(f"מיקום: {location}")
        if mood: summary_parts.append(f"מצב רוח: {mood}")
        
        return " | ".join(summary_parts) if summary_parts else ""
        
    except Exception as e:
        debug_log(f"Error composing emotional summary: {e}")
        return ""

def is_user_exists(chat_id: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        state = get_user_state(chat_id)
        return bool(state.get("chat_id"))
    except Exception as e:
        debug_log(f"Error checking if user exists {chat_id}: {e}")
        return False 