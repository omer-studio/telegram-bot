"""
sheets_core.py - כל הפעולות הבסיסיות של Google Sheets
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from config import setup_google_sheets, SUMMARY_FIELD, should_log_sheets_debug
from notifications import send_error_notification
from fields_dict import FIELDS_DICT

def debug_log(message: str, component: str = "SheetsCore", chat_id: str = ""):
    log_message = f"[{component}]"
    if chat_id:
        log_message += f"[{chat_id}]"
    log_message += f" {message}"
    logging.debug(log_message)

def safe_int(val) -> int:
    try:
        return int(val) if val else 0
    except (ValueError, TypeError):
        return 0

def safe_float(val) -> float:
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0

def clean_for_storage(data) -> str:
    if isinstance(data, str):
        return data.replace('\n', ' ').replace('\r', ' ')[:500]
    elif isinstance(data, (int, float)):
        return str(data)
    elif data is None:
        return ""
    else:
        return str(data)[:500]

def validate_chat_id(chat_id) -> str:
    if not chat_id:
        raise ValueError("chat_id cannot be empty")
    return str(chat_id)

def find_chat_id_in_sheet(sheet, chat_id: str, col: int = 1) -> Optional[int]:
    if not sheet:
        debug_log(f"Sheet is None, cannot search for chat_id {chat_id}")
        return None
    
    try:
        chat_id = validate_chat_id(chat_id)
        col_values = sheet.col_values(col)
        
        for i, value in enumerate(col_values, start=1):
            if str(value) == chat_id:
                debug_log(f"Found chat_id {chat_id} at row {i}")
                return i
        
        debug_log(f"chat_id {chat_id} not found in column {col}")
        return None
        
    except Exception as e:
        debug_log(f"Error searching for chat_id {chat_id}: {e}")
        return None

def check_user_access(sheet, chat_id: str) -> Dict[str, Any]:
    try:
        chat_id = validate_chat_id(chat_id)
        row_index = find_chat_id_in_sheet(sheet, chat_id, col=1)
        
        if not row_index:
            return {"status": "not_found", "code": None}
        
        status = sheet.cell(row_index, 3).value
        code = sheet.cell(row_index, 2).value
        
        debug_log(f"User {chat_id} access check: status={status}, code={code}")
        return {"status": status, "code": code}
        
    except Exception as e:
        debug_log(f"Error checking access for {chat_id}: {e}")
        return {"status": "error", "code": None}

def ensure_user_state_row(sheet_users, sheet_states, chat_id: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        
        row_index = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
        if row_index:
            debug_log(f"User {chat_id} already exists in user_states at row {row_index}")
            return True
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        new_row = [chat_id, str(code_input), "pending", timestamp]
        sheet.append_row(new_row)
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
        debug_log(f"Approved user {chat_id}")
        return True
        
    except Exception as e:
        debug_log(f"Error approving user {chat_id}: {e}")
        return False

def delete_row_by_chat_id(sheet_name: str, chat_id: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        gc, sheet_users, sheet_logs, sheet_states = setup_google_sheets()
        
        sheet_map = {"users": sheet_users, "states": sheet_states, "logs": sheet_logs}
        sheet = sheet_map.get(sheet_name)
        
        if not sheet:
            debug_log(f"Unknown sheet name: {sheet_name}")
            return False
        
        row_index = find_chat_id_in_sheet(sheet, chat_id, col=1)
        if not row_index:
            debug_log(f"User {chat_id} not found in {sheet_name}")
            return False
        
        sheet.delete_rows(row_index)
        debug_log(f"Deleted row {row_index} for user {chat_id} from {sheet_name}")
        return True
        
    except Exception as e:
        debug_log(f"Error deleting row for {chat_id} from {sheet_name}: {e}")
        send_error_notification(f"Error in delete_row_by_chat_id: {e}")
        return False

def get_user_state(chat_id: str) -> Dict[str, Any]:
    try:
        chat_id = validate_chat_id(chat_id)
        gc, sheet_users, sheet_logs, sheet_states = setup_google_sheets()
        
        if not sheet_states:
            debug_log("sheet_states is None", chat_id=chat_id)
            return {}
        
        row_index = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
        if not row_index:
            debug_log(f"User {chat_id} not found in user_states")
            return {}
        
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
        
        debug_log(f"Retrieved state for user {chat_id}")
        return state
        
    except Exception as e:
        debug_log(f"Error getting user state for {chat_id}: {e}")
        send_error_notification(f"Error in get_user_state: {e}")
        return {}

def update_user_state(chat_id: str, updates: Dict[str, Any]) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        gc, sheet_users, sheet_logs, sheet_states = setup_google_sheets()
        
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
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sheet_states.update_cell(row_index, column_mapping["last_updated"], timestamp)
            updated_fields.append("last_updated")
        
        debug_log(f"Updated fields {updated_fields} for user {chat_id}")
        return True
        
    except Exception as e:
        debug_log(f"Error updating user state for {chat_id}: {e}")
        send_error_notification(f"Error in update_user_state: {e}")
        return False

def increment_code_try_sync(sheet_states, chat_id: str) -> int:
    try:
        chat_id = validate_chat_id(chat_id)
        row_index = find_chat_id_in_sheet(sheet_states, chat_id, col=1)
        
        if not row_index:
            debug_log(f"User {chat_id} not found in user_states")
            return 0
        
        current_tries = safe_int(sheet_states.cell(row_index, 2).value)
        new_tries = current_tries + 1
        
        sheet_states.update_cell(row_index, 2, str(new_tries))
        debug_log(f"Incremented code_try for user {chat_id}: {current_tries} → {new_tries}")
        
        return new_tries
        
    except Exception as e:
        debug_log(f"Error incrementing code_try for {chat_id}: {e}")
        send_error_notification(f"Error in increment_code_try_sync: {e}")
        return 0

def increment_gpt_c_run_count(chat_id: str) -> int:
    try:
        chat_id = validate_chat_id(chat_id)
        current_state = get_user_state(chat_id)
        
        if not current_state:
            debug_log(f"Cannot increment gpt_c for unknown user {chat_id}")
            return 0
        
        current_count = current_state.get("gpt_c_run_count", 0)
        new_count = current_count + 1
        
        success = update_user_state(chat_id, {"gpt_c_run_count": new_count})
        if success:
            debug_log(f"Incremented GPT-C count for user {chat_id}: {current_count} → {new_count}")
            return new_count
        else:
            debug_log(f"Failed to increment GPT-C count for user {chat_id}")
            return current_count
            
    except Exception as e:
        debug_log(f"Error incrementing GPT-C count for {chat_id}: {e}")
        send_error_notification(f"Error in increment_gpt_c_run_count: {e}")
        return 0

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
    try:
        chat_id = validate_chat_id(chat_id)
        state = get_user_state(chat_id)
        return state.get("summary", "")
    except Exception as e:
        debug_log(f"Error getting user summary for {chat_id}: {e}")
        return ""

def update_user_summary(chat_id: str, new_summary: str) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        return update_user_state(chat_id, {"summary": new_summary})
    except Exception as e:
        debug_log(f"Error updating user summary for {chat_id}: {e}")
        return False

def get_user_profile_data(chat_id: str) -> Dict[str, Any]:
    try:
        chat_id = validate_chat_id(chat_id)
        state = get_user_state(chat_id)
        return state.get("profile_data", {})
    except Exception as e:
        debug_log(f"Error getting user profile for {chat_id}: {e}")
        return {}

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

def update_user_profile_data(chat_id: str, profile_updates: Dict[str, Any]) -> bool:
    try:
        chat_id = validate_chat_id(chat_id)
        current_profile = get_user_profile_data(chat_id)
        current_profile.update(profile_updates)
        
        # יצירת summary אוטומטי מהנתונים החדשים
        auto_summary = generate_summary_from_profile_data(current_profile)
        
        # עדכון הטיימסטאפ
        current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # עדכון נתוני הפרופיל עם summary אוטומטי ו-last_update
        updates_to_save = {
            "profile_data": current_profile,
            "summary": auto_summary,
            "last_updated": current_timestamp
        }
        
        debug_log(f"Auto-generated summary for user {chat_id}: {auto_summary}")
        debug_log(f"Updated last_update timestamp: {current_timestamp}")
        
        return update_user_state(chat_id, updates_to_save)
        
    except Exception as e:
        debug_log(f"Error updating user profile for {chat_id}: {e}")
        return False

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