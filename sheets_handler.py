"""
sheets_handler.py
-----------------
קובץ זה אחראי על כל האינטראקציה בין הבוט לגיליונות Google Sheets.
הרציונל: ריכוז כל ניהול המשתמשים, הרשאות, לוגים, עדכונים, רישום, וסיכומים מול Sheets במקום אחד.

למה הקובץ הזה קיים?
==================
הקובץ הזה אחראי על כל האינטראקציה בין הבוט לגיליונות Google Sheets, לצורך:
- זיהוי משתמשים חדשים (Onboarding) — לדעת אם מישהו פונה בפעם הראשונה בחייו לבוט!
- ניהול הרשאות, בדיקת קוד, אישור תנאים
- רישום משתמשים חדשים בדיוק במקום הנכון (user_states)
- שמירת לוגים, עדכון פרופיל, סיכום רגשי וכו'

למה בודקים גם בגיליון 1 וגם ב-user_states?
------------------------------------------
אנחנו רוצים לדעת אם המשתמש נכנס בפעם הראשונה בחייו לצ'אט, ולכן:
1. קודם כל בודקים האם ה-chat_id של המשתמש קיים בעמודה הראשונה של גיליון 1 (access_codes או "גיליון1").
2. אם לא מצאנו אותו שם, בודקים אם הוא קיים בעמודה הראשונה של גיליון user_states.
3. אם לא מצאנו אותו גם שם — זו הפעם הראשונה של המשתמש בצ'אט! נרשום אותו ב-user_states עם code_try=0.

כל פונקציה כאן כוללת תיעוד ולוגיקה ברורה למה עושים כל שלב, ויש לוגים (וגם print) לכל פעולה קריטית.
"""

from config import setup_google_sheets, SUMMARY_FIELD
from datetime import datetime
import logging
from gpt_utils import calculate_gpt_cost, USD_TO_ILS
from fields_dict import FIELDS_DICT
import json
from dataclasses import dataclass, asdict
from typing import Optional

def debug_log(message: str, function_name: str = "", chat_id: str = ""):
    """
    פונקציה מרכזית לdebug שמונעת כפילות בlogs
    """
    if chat_id:
        full_message = f"[DEBUG] {function_name}: {message} | chat_id={chat_id}"
    else:
        full_message = f"[DEBUG] {function_name}: {message}"
    
    print(full_message)
    logging.debug(full_message)

# יצירת חיבור לגיליונות — הפונקציה חייבת להחזיר 3 גיליונות!
sheet_users, sheet_log, sheet_states = setup_google_sheets()

def find_chat_id_in_sheet(sheet, chat_id, col=1):
    """
    בודק אם chat_id קיים בעמודה מסוימת בגיליון.
    קלט: sheet (אובייקט גיליון), chat_id (str/int), col (int)
    פלט: True/False
    """
    debug_log(f"find_chat_id_in_sheet: chat_id={chat_id}, col={col}", "find_chat_id_in_sheet")
    try:
        values = sheet.col_values(col)
        for v in values[1:]:  # דילוג על כותרת
            if str(v).strip() == str(chat_id).strip():
                debug_log(f"נמצא chat_id {chat_id} בעמודה {col}", "find_chat_id_in_sheet", chat_id)
                debug_log("סיום", "find_chat_id_in_sheet", chat_id)
                return True
        debug_log(f"find_chat_id_in_sheet] לא נמצא chat_id {chat_id} בעמודה {col}", "find_chat_id_in_sheet")
        debug_log("find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}", "find_chat_id_in_sheet")
        logging.debug(f"find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}", "find_chat_id_in_sheet")
        return False
    except Exception as e:
        debug_log(f"שגיאה בחיפוש chat_id בגיליון: {e}", "find_chat_id_in_sheet")
        debug_log("find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}", "find_chat_id_in_sheet")
        logging.debug(f"find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}", "find_chat_id_in_sheet")
        return False

def ensure_user_state_row(sheet_users, sheet_states, chat_id):
    """
    בודק אם המשתמש קיים בגיליונות, ואם לא — מוסיף אותו ל-user_states.
    קלט: sheet_users, sheet_states, chat_id
    פלט: True אם זו פנייה ראשונה, אחרת False
    """
    debug_log(f"ensure_user_state_row: chat_id={chat_id}", "ensure_user_state_row")
    logging.debug(f"ensure_user_state_row: chat_id={chat_id}")
    # בדיקה בגיליון 1 (access_codes) — עמודה 1
    if find_chat_id_in_sheet(sheet_users, chat_id, col=1):
        debug_log(f"[ensure_user_state_row] chat_id {chat_id} נמצא בגיליון 1 — לא פנייה ראשונה.", "ensure_user_state_row")
        debug_log("ensure_user_state_row: סיום | chat_id={chat_id}", "ensure_user_state_row")
        logging.debug(f"ensure_user_state_row: סיום | chat_id={chat_id}")
        return False
    # בדיקה ב-user_states — עמודה 1
    if find_chat_id_in_sheet(sheet_states, chat_id, col=1):
        debug_log(f"[ensure_user_state_row] chat_id {chat_id} כבר קיים ב-user_states — לא פנייה ראשונה.", "ensure_user_state_row")
        debug_log("ensure_user_state_row: סיום | chat_id={chat_id}", "ensure_user_state_row")
        logging.debug(f"ensure_user_state_row: סיום | chat_id={chat_id}")
        return False
    # לא נמצא — פנייה ראשונה אי-פעם: יצירת שורה חדשה
    try:
        sheet_states.append_row([str(chat_id), 0])
        debug_log(f"[ensure_user_state_row] ✅ נרשם chat_id {chat_id} ל-user_states (פנייה ראשונה, code_try=0)", "ensure_user_state_row")
        # שליחת הודעה לאדמין
        from notifications import send_error_notification
        from messages import new_user_admin_message
        send_error_notification(new_user_admin_message(chat_id))
        debug_log("ensure_user_state_row: סיום | chat_id={chat_id}", "ensure_user_state_row")
        logging.debug(f"ensure_user_state_row: סיום | chat_id={chat_id}")
        return True
    except Exception as e:
        debug_log(f"שגיאה ביצירת שורה חדשה ב-user_states: {e}", "ensure_user_state_row")
        debug_log("ensure_user_state_row: סיום | chat_id={chat_id}", "ensure_user_state_row")
        logging.debug(f"ensure_user_state_row: סיום | chat_id={chat_id}")
        return False


def increment_code_try(sheet_states, chat_id):
    """
    מגדיל את מונה הניסיונות של המשתמש להזין קוד בגיליון user_states.
    קלט: sheet_states, chat_id
    פלט: מספר הניסיון הנוכחי (int)
    """
    debug_log(f"increment_code_try: chat_id={chat_id}", "increment_code_try")
    logging.debug(f"increment_code_try: chat_id={chat_id}")
    try:
        records = sheet_states.get_all_records()
        header = sheet_states.row_values(1)
        for idx, row in enumerate(records):
            if str(row.get("chat_id")) == str(chat_id):
                current_try = row.get("code_try")
                if current_try is None or current_try == "":
                    current_try = 0
                else:
                    try:
                        current_try = int(current_try)
                    except (ValueError, TypeError):
                        current_try = 0
                new_try = current_try + 1
                col_index = header.index("code_try") + 1
                sheet_states.update_cell(idx + 2, col_index, new_try)
                debug_log("increment_code_try: סיום | chat_id={chat_id}", "increment_code_try")
                logging.debug(f"increment_code_try: סיום | chat_id={chat_id}")
                return new_try
        # אם לא נמצא שורה, מוסיף שורה עם code_try=0
        sheet_states.append_row([str(chat_id), 0])
        debug_log("increment_code_try: סיום | chat_id={chat_id}", "increment_code_try")
        logging.debug(f"increment_code_try: סיום | chat_id={chat_id}")
        return 0
    except Exception as e:
        debug_log(f"שגיאה בהעלאת code_try: {e}", "increment_code_try")
        # במקרה של שגיאה, מחזיר את המספר האחרון שנשמר בגיליון
        try:
            records = sheet_states.get_all_records()
            for row in records:
                if str(row.get("chat_id")) == str(chat_id):
                    current_try = row.get("code_try")
                    if current_try is None or current_try == "":
                        debug_log("increment_code_try: סיום | chat_id={chat_id}", "increment_code_try")
                        logging.debug(f"increment_code_try: סיום | chat_id={chat_id}")
                        return 0
                    debug_log("increment_code_try: סיום | chat_id={chat_id}", "increment_code_try")
                    logging.debug(f"increment_code_try: סיום | chat_id={chat_id}")
                    return int(current_try)
            # אם לא נמצא, מחזיר 0
            return 0
        except Exception as e2:
            debug_log(f"שגיאה בקריאה חוזרת של code_try: {e2}", "increment_code_try")
            # אם לא מצליח לקרוא בכלל, מחזיר 1 כדי שלא ישבור
            debug_log("increment_code_try: סיום | chat_id={chat_id}", "increment_code_try")
            logging.debug(f"increment_code_try: סיום | chat_id={chat_id}")
            return 1

def safe_int(val):
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0

def safe_float(val):
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

def get_user_summary(chat_id):
    """
    מחזיר את סיכום המשתמש מהגיליון (summary).
    קלט: chat_id
    פלט: summary (str)
    """
    debug_log(f"get_user_summary: chat_id={chat_id}", "get_user_summary")
    logging.debug(f"get_user_summary: chat_id={chat_id}")
    try:
        all_records = sheet_users.get_all_records()
        for row in all_records:
            if str(row.get("chat_id", "")).strip() == str(chat_id):
                summary = row.get("summary", "")
                if summary is not None:
                    summary = str(summary).strip()
                else:
                    summary = ""
                debug_log("get_user_summary: סיום | chat_id={chat_id}", "get_user_summary")
                logging.debug(f"get_user_summary: סיום | chat_id={chat_id}")
                return summary
        debug_log("get_user_summary: סיום | chat_id={chat_id}", "get_user_summary")
        logging.debug(f"get_user_summary: סיום | chat_id={chat_id}")
        return ""
    except Exception as e:
        debug_log(f"❌ שגיאה בקריאת סיכום משתמש: {e}", "get_user_summary")
        logging.error(f"❌ שגיאה בקריאת סיכום משתמש: {e}")
        return ""

def update_user_profile(chat_id, field_values):
    """
    מעדכן את הפרופיל של המשתמש בגיליון לפי field_values.
    קלט: chat_id, field_values (dict)
    פלט: אין (מעדכן בגיליון)
    """
    debug_log(f"update_user_profile: chat_id={chat_id}, field_values={field_values}", "update_user_profile")
    logging.debug(f"update_user_profile: chat_id={chat_id}, field_values={field_values}")
    if not isinstance(field_values, dict):
        logging.error(f"❌ update_user_profile קיבל טיפוס לא תקין: {type(field_values)}. הערך: {field_values}")
        raise TypeError(f"update_user_profile: field_values חייב להיות dict! קיבלתי: {type(field_values)}")
    try:
        all_records = sheet_users.get_all_records()
        header = sheet_users.row_values(1)
        debug_log(f"📋 כותרות הגיליון: {header}", "update_user_profile")
        for idx, row in enumerate(all_records):
            if str(row.get("chat_id", "")) == str(chat_id):
                debug_log(f"👤 מצא משתמש בשורה {idx + 2}", "update_user_profile")
                updated_fields = []
                for key, value in field_values.items():
                    if key in header and value is not None and str(value).strip() != "":
                        col_index = header.index(key) + 1
                        debug_log(f"[DEBUG] updating field: {key} = '{value}' at col {col_index}", "update_user_profile")
                        logging.info(f"[DEBUG] updating field: {key} = '{value}' at col {col_index}")
                        try:
                            sheet_users.update_cell(idx + 2, col_index, str(value))
                            updated_fields.append(f"{key}: {value}")
                        except Exception as e:
                            debug_log(f"❌ שגיאה בעדכון תא {key}: {e}", "update_user_profile")
                            logging.error(f"❌ שגיאה בעדכון תא {key}: {e}")
                    elif key not in header:
                        debug_log(f"⚠️ שדה {key} לא קיים בגיליון, מדלג.", "update_user_profile")
                        logging.warning(f"⚠️ שדה {key} לא קיים בגיליון, מדלג.")
                if updated_fields:
                    debug_log(f"[DEBUG] updated fields: {updated_fields}", "update_user_profile")
                    logging.info(f"[DEBUG] updated fields: {updated_fields}")
                    # שמור את summary בדיוק כפי שהוחזר מה-gpt
                    if "summary" in field_values and SUMMARY_FIELD in header:
                        summary_col = header.index(SUMMARY_FIELD) + 1
                        summary_val = field_values["summary"]
                        debug_log(f"📊 מעדכן סיכום בעמודה {summary_col}: '{summary_val}' (מה-gpt)", "update_user_profile")
                        try:
                            sheet_users.update_cell(idx + 2, summary_col, summary_val)
                        except Exception as e:
                            debug_log(f"❌ שגיאה בעדכון סיכום: {e}", "update_user_profile")
                            logging.error(f"❌ שגיאה בעדכון סיכום: {e}")
                else:
                    debug_log("⚠️ לא עודכנו שדות - אין ערכים תקינים", "update_user_profile")
                    logging.info("⚠️ לא עודכנו שדות - אין ערכים תקינים")
                break
        else:
            debug_log(f"❌ לא נמצא משתמש עם chat_id: {chat_id}", "update_user_profile")
            logging.warning(f"❌ לא נמצא משתמש עם chat_id: {chat_id}")
    except Exception as e:
        debug_log(f"💥 שגיאה בעדכון פרופיל: {e}", "update_user_profile")
        logging.error(f"💥 שגיאה בעדכון פרופיל: {e}")
        import traceback
        traceback.print_exc()
    debug_log("update_user_profile: סיום | chat_id={chat_id}", "update_user_profile")
    logging.debug(f"update_user_profile: סיום | chat_id={chat_id}")

def compose_emotional_summary(row):
    summary_fields = [
        "age", "pronoun_preference", "occupation_or_role", "attracted_to", "relationship_type",
        "self_religious_affiliation", "self_religiosity_level", "family_religiosity", "closet_status",
        "who_knows", "who_doesnt_know", "attends_therapy", "primary_conflict", "trauma_history",
        "goal_in_course", "language_of_strength", "date_first_seen", "coping_strategies",
        "fears_concerns", "future_vision", "last_update"
    ]
    debug_log(f"compose_emotional_summary: row keys={list(row.keys())}", "compose_emotional_summary")
    logging.debug(f"compose_emotional_summary: row keys={list(row.keys())}")
    parts = []
    for key in summary_fields:
        value = str(row.get(key, "")).strip()
        if value:
            field_info = FIELDS_DICT.get(key, {})
            show_in_summary = field_info.get("show_in_summary", "")
            if show_in_summary:  # אם הוגדר show_in_summary
                part = f"{show_in_summary} {value}"
            else:  # fallback ל-label
                field_name = field_info.get("label", key)
                part = f"{field_name}: {value}"
            parts.append(part)
    if not parts:
        debug_log("compose_emotional_summary: סיום", "compose_emotional_summary")
        logging.debug("compose_emotional_summary: סיום")
        return "[אין מידע לסיכום]"
    summary = ", ".join(parts)
    if len(summary) > 200:
        summary = summary[:197] + "..."
    debug_log("compose_emotional_summary: סיום", "compose_emotional_summary")
    logging.debug("compose_emotional_summary: סיום")
    return summary

def clean_for_storage(data):
    """
    מקבלת dict ומחזירה dict חדש שבו כל ערך שהוא dict או list מומר ל-json string (רק ברמה הראשונה).
    שאר הערכים נשארים כמו שהם.
    """
    import json
    clean = {}
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            clean[k] = json.dumps(v, ensure_ascii=False)
        else:
            clean[k] = v
    return clean

def log_to_sheets(
    message_id, chat_id, user_msg, reply_text, reply_summary,
    main_usage, summary_usage, extract_usage, total_tokens,
    cost_usd, cost_ils,
    prompt_tokens_total=None, completion_tokens_total=None, cached_tokens=None,
    cached_tokens_gpt_a=None, cost_gpt_a=None,
    cached_tokens_gpt_b=None, cost_gpt_b=None,
    cached_tokens_gpt_c=None, cost_gpt_c=None,
    merge_usage=None, fields_updated_by_gpt_c=None,
    gpt_d_usage=None, gpt_e_usage=None
):
    """
    שומר את כל נתוני השיחה בגיליון הלוגים.
    מחשב את כל הפרמטרים החסרים אוטומטית אם לא סופקו.
    """
    try:
        # גישה לגיליון הלוגים
        from config import setup_google_sheets
        _, sheet_log, _ = setup_google_sheets()
        
        now = datetime.now()
        timestamp_full = now.strftime("%Y-%m-%d %H:%M:%S")
        date_only = now.strftime("%d/%m/%Y")
        time_only = now.strftime("%H:%M")

        header = sheet_log.row_values(1)
        row_data = [""] * len(header)

        # 🚨 תיקון 1: וידוא נתונים בסיסיים
        if not message_id:
            message_id = f"msg_{now.strftime('%Y%m%d_%H%M%S')}"
            debug_log(f"⚠️ יצירת message_id זמני: {message_id}", "log_to_sheets")
            
        if not chat_id:
            debug_log("❌ שגיאה קריטית: chat_id ריק!", "log_to_sheets")
            return False

        debug_log(f"📝 שמירת לוג: message_id={message_id}, chat_id={chat_id}", "log_to_sheets")

        # פונקציה לביטחון להמרת ערכים


        # שליפה ישירה מתוך main_usage לפי שמות (dict)
        main_prompt_tokens = safe_int(main_usage.get("prompt_tokens", 0))
        main_completion_tokens = safe_int(main_usage.get("completion_tokens", 0))
        main_total_tokens = safe_int(main_usage.get("total_tokens", 0))
        main_cached_tokens = safe_int(main_usage.get("cached_tokens", 0))
        main_model = main_usage.get("model", "")
        main_cost_agorot = safe_float(main_usage.get("cost_agorot", 0))
        main_cost_usd = safe_float(main_usage.get("cost_total", 0))
        main_cost_ils = safe_float(main_usage.get("cost_total_ils", 0))

        # summary_usage תמיד dict
        summary_prompt_tokens = safe_int(summary_usage.get("prompt_tokens", 0))
        summary_completion_tokens = safe_int(summary_usage.get("completion_tokens", 0))
        summary_total_tokens = safe_int(summary_usage.get("total_tokens", 0))
        summary_model = summary_usage.get("model", "")
        summary_cost_agorot = safe_float(summary_usage.get("cost_agorot", 0))
        summary_cost_ils = safe_float(summary_usage.get("cost_total_ils", 0))

        # extract_usage תמיד dict
        extract_prompt_tokens = safe_int(extract_usage.get("prompt_tokens", 0))
        extract_completion_tokens = safe_int(extract_usage.get("completion_tokens", 0))
        extract_total_tokens = safe_int(extract_usage.get("total_tokens", 0))
        extract_model = extract_usage.get("model", "")
        extract_cost_agorot = safe_float(extract_usage.get("cost_agorot", 0))
        extract_cost_ils = safe_float(extract_usage.get("cost_total_ils", 0))

        # --- חישוב ערכים מראש כדי למנוע גישה עצמית ל-values_to_log ---
        def safe_calc(calc_func, field_name):
            try:
                return calc_func()
            except Exception as e:
                print(f"[safe_calc] שגיאה בחישוב {field_name}: {e}")
                return 0

        main_prompt_clean = safe_int(main_usage.get("prompt_tokens", 0)) - safe_int(main_usage.get("cached_tokens", 0))
        summary_prompt_clean = safe_int(summary_usage.get("prompt_tokens", 0)) - safe_int(summary_usage.get("cached_tokens", 0))
        extract_prompt_clean = safe_int(extract_usage.get("prompt_tokens", 0)) - safe_int(extract_usage.get("cached_tokens", 0))

        prompt_tokens_total = safe_calc(lambda: (
            main_prompt_clean +
            summary_prompt_clean +
            extract_prompt_clean +
            (safe_int(merge_usage.get("prompt_tokens", 0) - merge_usage.get("cached_tokens", 0)) if merge_usage is not None else 0)
        ), "prompt_tokens_total")

        completion_tokens_total = safe_calc(lambda: (
            safe_int(main_usage.get("completion_tokens", 0)) +
            safe_int(summary_usage.get("completion_tokens", 0)) +
            safe_int(extract_usage.get("completion_tokens", 0)) +
            (safe_int(merge_usage.get("completion_tokens", 0)) if merge_usage is not None else 0)
        ), "completion_tokens_total")

        cached_tokens = safe_calc(lambda: (
            safe_int(main_usage.get("cached_tokens", 0)) +
            safe_int(summary_usage.get("cached_tokens", 0)) +
            safe_int(extract_usage.get("cached_tokens", 0)) +
            (safe_int(merge_usage.get("cached_tokens", 0)) if merge_usage is not None else 0)
        ), "cached_tokens")

        total_tokens = safe_calc(lambda: (
            safe_int(prompt_tokens_total) + safe_int(completion_tokens_total) + safe_int(cached_tokens)
        ), "total_tokens")

        # חישוב עלויות אחידות
        main_costs = calculate_costs_unified(main_usage)
        summary_costs = calculate_costs_unified(summary_usage)
        extract_costs = calculate_costs_unified(extract_usage)
        gpt_d_costs = calculate_costs_unified(gpt_d_usage) if gpt_d_usage else {"cost_usd": 0, "cost_ils": 0, "cost_agorot": 0}
        gpt_e_costs = calculate_costs_unified(gpt_e_usage) if gpt_e_usage else {"cost_usd": 0, "cost_ils": 0, "cost_agorot": 0}

        # חישוב סכומים כוללים נכון
        total_cost_usd = (
            main_costs["cost_usd"] + 
            summary_costs["cost_usd"] + 
            extract_costs["cost_usd"] +
            gpt_d_costs["cost_usd"] +
            gpt_e_costs["cost_usd"]
        )
        total_cost_ils = total_cost_usd * USD_TO_ILS
        total_cost_agorot = total_cost_ils * 100

        # 🚨 תיקון 4: ניקוי ערכי עלות
        def clean_cost_value(cost_val):
            if cost_val is None or cost_val == "":
                return 0
            
            try:
                if isinstance(cost_val, str):
                    cost_val = cost_val.replace("$", "").replace(",", "").strip()
                return round(float(cost_val), 6)
            except (ValueError, TypeError):
                return 0
        
        # האם הופעל סיכום (gpt_b)?
        has_summary = summary_usage and len(summary_usage) > 0 and safe_float(summary_usage.get("completion_tokens", 0)) > 0

        # האם הופעל gpt_c (חילוץ)?
        has_extract = extract_usage and len(extract_usage) > 0 and safe_float(extract_usage.get("completion_tokens", 0)) > 0

        # האם הופעל gpt_d?
        has_gpt_d = gpt_d_usage and len(gpt_d_usage) > 0 and safe_float(gpt_d_usage.get("completion_tokens", 0)) > 0

        # האם הופעל gpt_e?
        has_gpt_e = gpt_e_usage and len(gpt_e_usage) > 0 and safe_float(gpt_e_usage.get("completion_tokens", 0)) > 0

        # --- עלות כוללת בדולר (מחושב לפי טבלת עלויות) ---
        def format_money(value):
            if value is None:
                return None
            return round(float(value), 5)

        # חישוב אגורות מדויק לפי ערך בדולרים
        def agorot_from_usd(cost_usd):
            return round(float(cost_usd) * USD_TO_ILS * 100, 5)

        # --- מיפוי ערכים מלא לפי דרישת המשתמש ---
        values_to_log = {
            "message_id": str(message_id),
            "chat_id": str(chat_id),
            "user_msg": user_msg if user_msg else "",
            "user_summary": "",
            "bot_reply": reply_text if reply_text else "",
            "bot_summary": reply_summary if reply_summary else "",
            "total_tokens": total_tokens,
            "prompt_tokens_total": prompt_tokens_total,
            "completion_tokens_total": completion_tokens_total,
            "cached_tokens": cached_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "total_cost_ils": round(total_cost_agorot, 2),  # באגורות!
            "usage_prompt_tokens_gpt_a": safe_calc(lambda: safe_int(main_usage.get("prompt_tokens", 0) - main_usage.get("cached_tokens", 0)), "usage_prompt_tokens_gpt_a"),
            "usage_completion_tokens_gpt_a": safe_calc(lambda: safe_int(main_usage.get("completion_tokens", 0)), "usage_completion_tokens_gpt_a"),
            "usage_total_tokens_gpt_a": safe_calc(lambda: safe_int(main_usage.get("total_tokens", 0)), "usage_total_tokens_gpt_a"),
            "cached_tokens_gpt_a": safe_calc(lambda: safe_int(main_usage.get("cached_tokens", 0)), "cached_tokens_gpt_a"),
            "cost_gpt_a": main_costs["cost_agorot"],
            "model_gpt_a": str(main_usage.get("model", "")),
            "timestamp": timestamp_full,
            "date_only": date_only,
            "time_only": time_only,
        }
        # הוספת שדות gpt_c תמיד אם extract_usage הוא dict (גם אם ריק)
        if isinstance(extract_usage, dict):
            values_to_log.update({
                "usage_prompt_tokens_gpt_c": safe_calc(lambda: safe_int(extract_usage.get("prompt_tokens", 0) - extract_usage.get("cached_tokens", 0)), "usage_prompt_tokens_gpt_c"),
                "usage_completion_tokens_gpt_c": safe_calc(lambda: safe_int(extract_usage.get("completion_tokens", 0)), "usage_completion_tokens_gpt_c"),
                "usage_total_tokens_gpt_c": safe_calc(lambda: safe_int(extract_usage.get("total_tokens", 0)), "usage_total_tokens_gpt_c"),
                "cached_tokens_gpt_c": safe_calc(lambda: safe_int(extract_usage.get("cached_tokens", 0)), "cached_tokens_gpt_c"),
                "cost_gpt_c": extract_costs["cost_agorot"],
                "model_gpt_c": str(extract_usage.get("model", "")),
            })
        
        # הוספת שדות gpt_b רק אם יש סיכום
        if has_summary:
            values_to_log.update({
                "usage_prompt_tokens_gpt_b": safe_calc(lambda: safe_int(summary_usage.get("prompt_tokens", 0) - summary_usage.get("cached_tokens", 0)), "usage_prompt_tokens_gpt_b"),
                "usage_completion_tokens_gpt_b": safe_calc(lambda: safe_int(summary_usage.get("completion_tokens", 0)), "usage_completion_tokens_gpt_b"),
                "usage_total_tokens_gpt_b": safe_calc(lambda: (
                    safe_int(summary_usage.get("cached_tokens", 0)) +
                    safe_int(summary_usage.get("completion_tokens", 0)) +
                    safe_int(summary_usage.get("prompt_tokens", 0))
                ), "usage_total_tokens_gpt_b"),
                "cached_tokens_gpt_b": safe_calc(lambda: safe_int(summary_usage.get("cached_tokens", 0)), "cached_tokens_gpt_b"),
                "cost_gpt_b": summary_costs["cost_agorot"],
                "model_gpt_b": str(summary_usage.get("model", "")),
            })
        
        # הוספת שדות gpt_d רק אם הופעל
        if has_gpt_d:
            values_to_log.update({
                "usage_prompt_tokens_gpt_d": safe_calc(lambda: safe_int(gpt_d_usage.get("prompt_tokens", 0) - gpt_d_usage.get("cached_tokens", 0)), "usage_prompt_tokens_gpt_d"),
                "usage_completion_tokens_gpt_d": safe_calc(lambda: safe_int(gpt_d_usage.get("completion_tokens", 0)), "usage_completion_tokens_gpt_d"),
                "usage_total_tokens_gpt_d": safe_calc(lambda: safe_int(gpt_d_usage.get("total_tokens", 0)), "usage_total_tokens_gpt_d"),
                "cached_tokens_gpt_d": safe_calc(lambda: safe_int(gpt_d_usage.get("cached_tokens", 0)), "cached_tokens_gpt_d"),
                "cost_gpt_d": gpt_d_costs["cost_agorot"],
                "model_gpt_d": str(gpt_d_usage.get("model", "")),
            })

        # הוספת שדות gpt_e רק אם הופעל
        if has_gpt_e:
            values_to_log.update({
                "usage_prompt_tokens_gpt_e": safe_calc(lambda: safe_int(gpt_e_usage.get("prompt_tokens", 0) - gpt_e_usage.get("cached_tokens", 0)), "usage_prompt_tokens_gpt_e"),
                "usage_completion_tokens_gpt_e": safe_calc(lambda: safe_int(gpt_e_usage.get("completion_tokens", 0)), "usage_completion_tokens_gpt_e"),
                "usage_total_tokens_gpt_e": safe_calc(lambda: safe_int(gpt_e_usage.get("total_tokens", 0)), "usage_total_tokens_gpt_e"),
                "cached_tokens_gpt_e": safe_calc(lambda: safe_int(gpt_e_usage.get("cached_tokens", 0)), "cached_tokens_gpt_e"),
                "cost_gpt_e": gpt_e_costs["cost_agorot"],
                "model_gpt_e": str(gpt_e_usage.get("model", "")),
            })

        # 🚨 דיבאגים חזקים לפני שמירה
        def debug_usage_dict(name, usage):
            print(f"[DEBUG] ---- {name} ----")
            if usage is None:
                print(f"[DEBUG] {name} is None")
                return
            for k, v in usage.items():
                print(f"[DEBUG] {name}[{k}] = {v} (type: {type(v)})")
                if isinstance(v, (dict, list)):
                    print(f"[DEBUG][ALERT] {name}[{k}] הוא {type(v)}! ערך: {v}")
        debug_usage_dict('main_usage', main_usage)
        debug_usage_dict('summary_usage', summary_usage)
        debug_usage_dict('extract_usage', extract_usage)
        debug_usage_dict('merge_usage', merge_usage)
        # דיבאג על values_to_log לפני ניקוי
        print("[DEBUG] ---- values_to_log BEFORE clean_for_storage ----")
        for k, v in values_to_log.items():
            print(f"[DEBUG] values_to_log[{k}] = {v} (type: {type(v)})")
            if isinstance(v, (dict, list)):
                print(f"[DEBUG][ALERT] values_to_log[{k}] הוא {type(v)}! ערך: {v}")

        # 🚨 ניקוי עדין: המרת dict/list ל-json string לפני הכנסת row_data
        values_to_log = clean_for_storage(values_to_log)
        # דיבאג על values_to_log אחרי ניקוי
        print("[DEBUG] ---- values_to_log AFTER clean_for_storage ----")
        for k, v in values_to_log.items():
            print(f"[DEBUG] values_to_log[{k}] = {v} (type: {type(v)})")
            if isinstance(v, (dict, list)):
                print(f"[DEBUG][ALERT] values_to_log[{k}] הוא {type(v)}! ערך: {v}")

        # בדיקת assert שאין dict/list אחרי הניקוי (למניעת באגים עתידיים)
        for k, v in values_to_log.items():
            if isinstance(v, (dict, list)):
                # לוג אזהרה בעברית
                print(f"# ⚠️ אזהרה: ערך לשדה '{k}' נשאר dict/list אחרי ניקוי! זה באג מסוכן. הערך: {v}")
                import logging
                logging.warning(f"# ⚠️ אזהרה: ערך לשדה '{k}' נשאר dict/list אחרי ניקוי! זה באג מסוכן. הערך: {v}")
                raise AssertionError(f"אסור לשמור dict/list ישירות! שדה: {k}, ערך: {v}")

        # 🚨 תיקון 6: וידוא שכל הכותרות קיימות וההכנסה תקינה
        missing_headers = []
        for key in values_to_log.keys():
            if key not in header:
                missing_headers.append(key)
        if missing_headers:
            print(f"⚠️ כותרות חסרות בגיליון: {missing_headers}")
            from notifications import send_error_notification
            send_error_notification(f"⚠️ כותרות חסרות בגיליון: {missing_headers}")

        # הכנסת ערכים לפי header (מתעלם מעמודות מיותרות)
        for key, val in values_to_log.items():
            if key in header:
                idx = header.index(key)
                row_data[idx] = val
        # שמירה בגיליון
        sheet_log.insert_row(row_data, 3)

        # שמירה נוספת ל-gpt_usage_log.jsonl עבור daily_summary
        try:
            log_gpt_usage_to_file(message_id, chat_id, main_usage, summary_usage, extract_usage, gpt_d_usage, gpt_e_usage, total_cost_ils)
        except Exception as e:
            print(f"[WARNING] שגיאה בשמירת לוג usage: {e}")

        # --- אחרי בניית values_to_log, לוג דיבאג על תקינות כל שדה ---
        try:
            debug_fields = []
            for k, v in values_to_log.items():
                if v == "-":
                    debug_fields.append(f"❌ {k}='-' (שגיאה)")
                else:
                    debug_fields.append(f"✅ {k}='{v}'")
            debug_msg = "[DEBUG] fields_to_log: " + ", ".join(debug_fields)
            print(debug_msg)
            # אפשר גם לכתוב ללוג קובץ אם תרצה
        except Exception as e:
            print(f"[DEBUG] שגיאה בלוג דיבאג שדות: {e}")

        return True

    except Exception as e:
        import traceback
        from notifications import send_error_notification
        tb = traceback.format_exc()
        print(f"[DEBUG][EXCEPTION] {tb}")
        error_msg = (
            f"❌ שגיאה בשמירה לגיליון:\n"
            f"סוג: {type(e).__name__}\n"
            f"שגיאה: {e}\n"
            f"chat_id: {chat_id}\n"
            f"message_id: {message_id}\n"
            f"user_msg: {str(user_msg)[:100]}\n"
            f"traceback:\n{tb}"
        )
        print(error_msg)
        send_error_notification(error_message=error_msg, chat_id=chat_id, user_msg=user_msg, error_type="sheets_log_error")
        return False



def check_user_access(sheet, chat_id):
    """
    בודק אם למשתמש יש הרשאה בגיליון 1 ומחזיר את הסטטוס.
    לוגיקה: אם chat_id קיים — מחזירים קוד ומצב אישור.
    """
    try:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("chat_id")) == str(chat_id):
                access_code = row.get("access_code")
                approved = str(row.get("approved")).strip().lower() == "true"
                return True, access_code, approved
        return False, None, False
    except Exception as e:
        print(f"שגיאה בבדיקת משתמש: {e}")
        return False, None, False

def register_user(sheet, chat_id, code_input):
    """
    מאפשר רישום משתמש חדש בגיליון 1 אם הקוד תקין.
    לוגיקה: מוצא קוד פנוי ורושם שם את ה-chat_id.
    """
    try:
        code_cell = sheet.find(code_input)  # מוצא את השורה של הקוד המדויק!
        if code_cell:
            row = code_cell.row
            chat_id_cell = sheet.cell(row, 3).value  # עמודה C (chat_id)
            if not chat_id_cell or str(chat_id_cell).strip() == "":
                sheet.update_cell(row, 3, str(chat_id))  # מעדכן בעמודה C באותה שורה!
                print(f"[register_user] קוד {code_input} אושר ל-chat_id {chat_id} בשורה {row}")
                return True
        print(f"[register_user] קוד {code_input} לא תקין או כבר שויך")
        return False
    except Exception as e:
        print(f"שגיאה ברישום קוד גישה: {e}")
        return False


def approve_user(sheet, chat_id):
    """
    מסמן בטבלה שהמשתמש אישר תנאים.
    לוגיקה: עדכון עמודת 'approved' בהתאם ל-chat_id.
    """
    try:
        cell = sheet.find(str(chat_id))
        if cell:
            header_cell = sheet.find("approved")  # עמודת "אישר תנאים?"
            if header_cell:
                sheet.update_cell(cell.row, header_cell.col, "TRUE")
                print(f"[approve_user] משתמש {chat_id} אישר תנאים.")
                return True
        print(f"[approve_user] לא נמצא chat_id {chat_id} או עמודה מתאימה")
        return False
    except Exception as e:
        print(f"❌ approve_user error: {e}")
        return False

def delete_row_by_chat_id(sheet_name, chat_id):
    """
    מוחק שורה מהגיליון לפי chat_id (בעמודה B).
    בגיליון user_states מוחק את כל השורה.
    בגיליון1 (users) מרוקן את השורה חוץ מהעמודה הראשונה (הקוד).
    """
    from config import setup_google_sheets

    sheet_users, sheet_log, sheet_states = setup_google_sheets()

    from config import config
    if sheet_name == config["SHEET_STATES_TAB"]:
        worksheet = sheet_states
    elif sheet_name == config["SHEET_LOG_TAB"]:
        worksheet = sheet_log
    else:
        worksheet = sheet_users

    all_records = worksheet.get_all_records()
    header = worksheet.row_values(1)  # רשימת כותרות
    for idx, row in enumerate(all_records, start=2):  # מתחילים מ-2 כי שורה 1 זה כותרות
        if str(row.get("chat_id")) == str(chat_id):
            if sheet_name == config["SHEET_STATES_TAB"]:
                # מוחק את כל השורה
                worksheet.delete_row(idx)
                print(f"✅ נמחקה שורה לגמרי עבור chat_id {chat_id} בגיליון {config['SHEET_STATES_TAB']} (שורה {idx})")
            else:
                # מרוקן את כל העמודות חוץ מהעמודה הראשונה (קוד)
                for col in range(2, len(header) + 1):  # עמודה 2 עד סוף (1 זה הקוד)
                    worksheet.update_cell(idx, col, "")
                print(f"✅ נוקתה השורה עבור chat_id {chat_id} בגיליון {config['SHEET_USER_TAB']} (נשמר רק הקוד בשורה {idx})")
            return True
    print(f"❌ לא נמצאה שורה עם chat_id {chat_id} למחיקה בגיליון {sheet_name}")
    return False

# תודה1

# =============================================
# ⚠️⚠️⚠️  אזהרה קריטית למפתח  ⚠️⚠️⚠️
# כל שמירה חדשה של נתונים לגיליון/לוג (Google Sheets, JSONL וכו')
# חייבת לעבור דרך הפונקציה clean_for_storage או להשתמש ב-dataclass/פונקציה קיימת שמבצעת ניקוי!
# אסור בתכלית האיסור לשמור dict או list ישירות – זה יגרום לבאגים קשים (unhashable type: 'dict')!
# אם אתה מוסיף שמירה חדשה – תוודא שהיא עוברת ניקוי כמו בדוגמאות הקיימות.
#
# CRITICAL WARNING FOR DEVELOPERS:
# Any new data save (to Sheets/logs/JSONL/etc) MUST go through clean_for_storage or an existing dataclass/cleaning function!
# Never save dict or list directly – always sanitize first, or you will get hard-to-debug errors (unhashable type: 'dict')!
# =============================================

# דוגמה ל-dataclass לייצוג שורת לוג
@dataclass
class LogRow:
    message_id: str
    chat_id: str
    user_msg: str
    user_summary: str
    bot_reply: str
    bot_summary: str
    total_tokens: int
    prompt_tokens_total: int
    completion_tokens_total: int
    cached_tokens: int
    total_cost_usd: float
    total_cost_ils: float
    # ... הוסף שדות נוספים לפי הצורך ...

# דוגמה לשימוש:
# log_row = LogRow(...)
# values_to_log = clean_for_storage(asdict(log_row))
# (המשך שמירה כרגיל)

def calculate_costs_unified(usage_dict):
    """חישוב אחיד של כל העלויות"""
    # בדיקה אם יש כבר עלויות מחושבות
    cost_total = usage_dict.get("cost_total", 0)
    
    # אם אין עלות מחושבת, נחשב אותה
    if cost_total == 0:
        prompt_tokens = usage_dict.get("prompt_tokens", 0)
        completion_tokens = usage_dict.get("completion_tokens", 0)
        cached_tokens = usage_dict.get("cached_tokens", 0)
        from config import GPT_MODELS
        model = usage_dict.get("model", GPT_MODELS["gpt_a"])
        
        # קריאה לפונקציה המרכזית לחישוב עלויות (ללא completion_response)
        cost_data = calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens, model)
        cost_total = cost_data.get("cost_total", 0)
        print(f"[DEBUG] calculate_costs_unified recalculated cost: {cost_total} for {model}")
    
    cost_ils = cost_total * USD_TO_ILS
    cost_agorot = cost_ils * 100
    
    return {
        "cost_usd": round(cost_total, 6),
        "cost_ils": round(cost_ils, 4),
        "cost_agorot": round(cost_agorot, 2)
    }

def get_user_state(chat_id: str) -> dict:
    """
    מחזיר את מצב המשתמש מגיליון user_states.
    
    :param chat_id: מזהה המשתמש
    :return: מילון עם מצב המשתמש (gpt_c_run_count, last_gpt_e_timestamp וכו')
    """
    print(f"[DEBUG] get_user_state: chat_id={chat_id}")
    logging.debug(f"[DEBUG] get_user_state: chat_id={chat_id}")
    
    try:
        all_records = sheet_states.get_all_records()
        header = sheet_states.row_values(1)
        
        for row in all_records:
            if str(row.get("chat_id", "")).strip() == str(chat_id):
                # יצירת מילון עם כל השדות הקיימים
                user_state = {}
                for key in header:
                    value = row.get(key, "")
                    
                    # המרת ערכים מספריים
                    if key == "gpt_c_run_count":
                        try:
                            value = int(value) if value else 0
                        except (ValueError, TypeError):
                            value = 0
                    
                    user_state[key] = value
                
                print(f"[DEBUG] Retrieved user state for chat_id={chat_id}: {user_state}")
                logging.debug(f"[DEBUG] Retrieved user state for chat_id={chat_id}: {user_state}")
                
                return user_state
        
        # אם המשתמש לא נמצא, החזרת מילון ריק
        print(f"[DEBUG] User not found in user_states for chat_id={chat_id}")
        logging.debug(f"[DEBUG] User not found in user_states for chat_id={chat_id}")
        
        return {}
        
    except Exception as e:
        print(f"[ERROR] get_user_state failed for chat_id={chat_id}: {e}")
        logging.error(f"[ERROR] get_user_state failed for chat_id={chat_id}: {e}")
        return {}

def update_user_state(chat_id: str, updates: dict) -> bool:
    """
    מעדכן את מצב המשתמש בגיליון user_states.
    
    :param chat_id: מזהה המשתמש
    :param updates: מילון עם השדות לעדכון
    :return: True אם הצליח, False אחרת
    """
    print(f"[DEBUG] update_user_state: chat_id={chat_id}, updates={updates}")
    logging.debug(f"[DEBUG] update_user_state: chat_id={chat_id}, updates={updates}")
    
    try:
        all_records = sheet_states.get_all_records()
        header = sheet_states.row_values(1)
        
        for idx, row in enumerate(all_records):
            if str(row.get("chat_id", "")).strip() == str(chat_id):
                print(f"👤 מצא משתמש בשורה {idx + 2}")
                updated_fields = []
                
                for key, value in updates.items():
                    if key in header:
                        col_index = header.index(key) + 1
                        print(f"[DEBUG] updating state field: {key} = '{value}' at col {col_index}")
                        logging.info(f"[DEBUG] updating state field: {key} = '{value}' at col {col_index}")
                        
                        try:
                            sheet_states.update_cell(idx + 2, col_index, str(value))
                            updated_fields.append(f"{key}: {value}")
                        except Exception as e:
                            print(f"❌ שגיאה בעדכון שדה מצב {key}: {e}")
                            logging.error(f"❌ שגיאה בעדכון שדה מצב {key}: {e}")
                    else:
                        print(f"⚠️ שדה מצב {key} לא קיים בגיליון, מדלג.")
                        logging.warning(f"⚠️ שדה מצב {key} לא קיים בגיליון, מדלג.")
                
                if updated_fields:
                    print(f"[DEBUG] updated state fields: {updated_fields}")
                    logging.info(f"[DEBUG] updated state fields: {updated_fields}")
                else:
                    print("⚠️ לא עודכנו שדות מצב - אין ערכים תקינים")
                    logging.info("⚠️ לא עודכנו שדות מצב - אין ערכים תקינים")
                
                print(f"[DEBUG] update_user_state: סיום | chat_id={chat_id}")
                logging.debug(f"[DEBUG] update_user_state: סיום | chat_id={chat_id}")
                return True
        
        # אם לא נמצא, מוסיף שורה חדשה
        print(f"❌ לא נמצא משתמש עם chat_id: {chat_id}, מוסיף שורה חדשה")
        logging.warning(f"❌ לא נמצא משתמש עם chat_id: {chat_id}, מוסיף שורה חדשה")
        
        # יצירת שורה חדשה עם chat_id וערכים ברירת מחדל
        new_row = [""] * len(header)
        new_row[0] = str(chat_id)  # עמודה ראשונה היא chat_id
        
        # הוספת העדכונים לשורה החדשה
        for key, value in updates.items():
            if key in header:
                col_index = header.index(key)
                new_row[col_index] = str(value)
        
        sheet_states.append_row(new_row)
        print(f"✅ נוספה שורה חדשה עבור chat_id {chat_id}")
        logging.info(f"✅ נוספה שורה חדשה עבור chat_id {chat_id}")
        
        print(f"[DEBUG] update_user_state: סיום | chat_id={chat_id}")
        logging.debug(f"[DEBUG] update_user_state: סיום | chat_id={chat_id}")
        
        return True
        
    except Exception as e:
        print(f"💥 שגיאה בעדכון מצב משתמש: {e}")
        logging.error(f"💥 שגיאה בעדכון מצב משתמש: {e}")
        import traceback
        traceback.print_exc()
        return False

def increment_gpt_c_run_count(chat_id: str) -> int:
    """
    מגדיל את מונה gpt_c_run_count ב-1 ומחזיר את הערך החדש.
    
    :param chat_id: מזהה המשתמש
    :return: הערך החדש של gpt_c_run_count
    """
    print(f"[DEBUG] increment_gpt_c_run_count: chat_id={chat_id}")
    logging.debug(f"[DEBUG] increment_gpt_c_run_count: chat_id={chat_id}")
    
    try:
        all_records = sheet_states.get_all_records()
        header = sheet_states.row_values(1)
        
        # חיפוש המשתמש
        for i, row in enumerate(all_records, start=2):  # מתחיל מ-2 כי שורה 1 היא header
            if str(row.get("chat_id", "")).strip() == str(chat_id):
                # מציאת עמודת gpt_c_run_count
                gpt_c_run_count_col = None
                for j, col_name in enumerate(header, start=1):
                    if col_name == "gpt_c_run_count":
                        gpt_c_run_count_col = j
                        break
                
                if gpt_c_run_count_col is None:
                    # יצירת עמודה חדשה אם לא קיימת
                    gpt_c_run_count_col = len(header) + 1
                    sheet_states.update_cell(1, gpt_c_run_count_col, "gpt_c_run_count")
                    print(f"[DEBUG] Created new column gpt_c_run_count at position {gpt_c_run_count_col}")
                
                # קריאת הערך הנוכחי
                current_value = row.get("gpt_c_run_count", 0)
                if isinstance(current_value, str):
                    try:
                        current_value = int(current_value)
                    except ValueError:
                        current_value = 0
                
                # הגדלת הערך
                new_value = current_value + 1
                
                # עדכון התא
                sheet_states.update_cell(i, gpt_c_run_count_col, new_value)
                
                print(f"[DEBUG] Incremented gpt_c_run_count from {current_value} to {new_value} for chat_id={chat_id}")
                logging.info(f"[DEBUG] Incremented gpt_c_run_count from {current_value} to {new_value} for chat_id={chat_id}")
                
                return new_value
        
        # אם המשתמש לא נמצא, יצירת רשומה חדשה
        print(f"[DEBUG] User not found in user_states, creating new record for chat_id={chat_id}")
        
        # הוספת שורה חדשה
        new_row = [""] * len(header)
        new_row[0] = str(chat_id)  # chat_id בעמודה הראשונה
        
        # הוספת gpt_c_run_count אם לא קיים
        if "gpt_c_run_count" not in header:
            header.append("gpt_c_run_count")
            new_row.append(1)
        else:
            gpt_c_run_count_idx = header.index("gpt_c_run_count")
            new_row[gpt_c_run_count_idx] = 1
        
        sheet_states.append_row(new_row)
        
        print(f"[DEBUG] Created new user record with gpt_c_run_count=1 for chat_id={chat_id}")
        logging.info(f"[DEBUG] Created new user record with gpt_c_run_count=1 for chat_id={chat_id}")
        
        return 1
        
    except Exception as e:
        print(f"[ERROR] increment_gpt_c_run_count failed for chat_id={chat_id}: {e}")
        logging.error(f"[ERROR] increment_gpt_c_run_count failed for chat_id={chat_id}: {e}")
        return 0

def reset_gpt_c_run_count(chat_id: str) -> bool:
    """
    מאפס את מונה gpt_c_run_count ל-0 ומעדכן את last_gpt_e_timestamp.
    
    :param chat_id: מזהה המשתמש
    :return: True אם הצליח, False אם נכשל
    """
    print(f"[DEBUG] reset_gpt_c_run_count: chat_id={chat_id}")
    logging.debug(f"[DEBUG] reset_gpt_c_run_count: chat_id={chat_id}")
    
    try:
        from datetime import datetime
        
        all_records = sheet_states.get_all_records()
        header = sheet_states.row_values(1)
        
        # חיפוש המשתמש
        for i, row in enumerate(all_records, start=2):  # מתחיל מ-2 כי שורה 1 היא header
            if str(row.get("chat_id", "")).strip() == str(chat_id):
                # מציאת עמודות נדרשות
                gpt_c_run_count_col = None
                last_gpt_e_timestamp_col = None
                
                for j, col_name in enumerate(header, start=1):
                    if col_name == "gpt_c_run_count":
                        gpt_c_run_count_col = j
                    elif col_name == "last_gpt_e_timestamp":
                        last_gpt_e_timestamp_col = j
                
                # יצירת עמודות אם לא קיימות
                if gpt_c_run_count_col is None:
                    gpt_c_run_count_col = len(header) + 1
                    sheet_states.update_cell(1, gpt_c_run_count_col, "gpt_c_run_count")
                    print(f"[DEBUG] Created new column gpt_c_run_count at position {gpt_c_run_count_col}")
                
                if last_gpt_e_timestamp_col is None:
                    last_gpt_e_timestamp_col = len(header) + 1
                    sheet_states.update_cell(1, last_gpt_e_timestamp_col, "last_gpt_e_timestamp")
                    print(f"[DEBUG] Created new column last_gpt_e_timestamp at position {last_gpt_e_timestamp_col}")
                
                # עדכון הערכים
                current_timestamp = datetime.now().isoformat()
                
                sheet_states.update_cell(i, gpt_c_run_count_col, 0)
                sheet_states.update_cell(i, last_gpt_e_timestamp_col, current_timestamp)
                
                print(f"[DEBUG] Reset gpt_c_run_count to 0 and updated last_gpt_e_timestamp to {current_timestamp} for chat_id={chat_id}")
                logging.info(f"[DEBUG] Reset gpt_c_run_count to 0 and updated last_gpt_e_timestamp to {current_timestamp} for chat_id={chat_id}")
                
                return True
        
        # אם המשתמש לא נמצא, יצירת רשומה חדשה
        print(f"[DEBUG] User not found in user_states, creating new record for chat_id={chat_id}")
        
        current_timestamp = datetime.now().isoformat()
        
        # הוספת שורה חדשה
        new_row = [""] * len(header)
        new_row[0] = str(chat_id)  # chat_id בעמודה הראשונה
        
        # הוספת עמודות אם לא קיימות
        if "gpt_c_run_count" not in header:
            header.append("gpt_c_run_count")
            new_row.append(0)
        else:
            gpt_c_run_count_idx = header.index("gpt_c_run_count")
            new_row[gpt_c_run_count_idx] = 0
        
        if "last_gpt_e_timestamp" not in header:
            header.append("last_gpt_e_timestamp")
            new_row.append(current_timestamp)
        else:
            last_gpt_e_timestamp_idx = header.index("last_gpt_e_timestamp")
            new_row[last_gpt_e_timestamp_idx] = current_timestamp
        
        sheet_states.append_row(new_row)
        
        print(f"[DEBUG] Created new user record with gpt_c_run_count=0 and last_gpt_e_timestamp={current_timestamp} for chat_id={chat_id}")
        logging.info(f"[DEBUG] Created new user record with gpt_c_run_count=0 and last_gpt_e_timestamp={current_timestamp} for chat_id={chat_id}")
        
        return True

    except Exception as e:
        print(f"[ERROR] reset_gpt_c_run_count failed for chat_id={chat_id}: {e}")
        logging.error(f"[ERROR] reset_gpt_c_run_count failed for chat_id={chat_id}: {e}")
        return False

def log_gpt_usage_to_file(message_id, chat_id, main_usage, summary_usage, extract_usage, gpt_d_usage, gpt_e_usage, total_cost_ils):
    """
    כותב רישום אינטראקציה אחד ל-gpt_usage_log.jsonl עבור daily_summary.
    כל אינטראקציה = קריאה אחת ל-gpt_a, אז יש בדיוק רישום אחד לאינטראקציה.
    """
    from datetime import datetime
    import json
    import os
    from config import gpt_log_path
    
    try:
        # יצירת רישום אחד לאינטראקציה (מבוסס על gpt_a שתמיד קיים)
        interaction_entry = {
            "timestamp": datetime.now().isoformat(),
            "interaction_id": message_id,
            "chat_id": str(chat_id),
            "type": "gpt_a",  # זה המזהה העיקרי לאינטראקציה
            "cost_total_ils": total_cost_ils,
            "has_gpt_b": bool(summary_usage and summary_usage.get("total_tokens", 0) > 0),
            "has_gpt_c": bool(extract_usage and extract_usage.get("total_tokens", 0) > 0),
            "has_gpt_d": bool(gpt_d_usage and gpt_d_usage.get("total_tokens", 0) > 0),
            "has_gpt_e": bool(gpt_e_usage and gpt_e_usage.get("total_tokens", 0) > 0),
        }
        
        # הוספת פרטי usage אם קיימים
        if main_usage:
            interaction_entry["gpt_a_tokens"] = main_usage.get("total_tokens", 0)
            interaction_entry["gpt_a_cost"] = main_usage.get("cost_total_ils", 0)
        
        # יצירת תיקייה אם לא קיימת
        os.makedirs(os.path.dirname(gpt_log_path), exist_ok=True)
        
        # כתיבה לקובץ
        with open(gpt_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(interaction_entry, ensure_ascii=False) + "\n")
        
        print(f"[DEBUG] רישום אינטראקציה נשמר ל-{gpt_log_path}: {message_id}")
        
    except Exception as e:
        print(f"[ERROR] log_gpt_usage_to_file failed: {e}")
        import traceback
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")