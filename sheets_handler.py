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
from gpt_handler import calculate_gpt_cost, USD_TO_ILS
from fields_dict import FIELDS_DICT
import json


# יצירת חיבור לגיליונות — הפונקציה חייבת להחזיר 3 גיליונות!
sheet_users, sheet_log, sheet_states = setup_google_sheets()

def find_chat_id_in_sheet(sheet, chat_id, col=1):
    """
    בודק אם chat_id קיים בעמודה מסוימת בגיליון.
    קלט: sheet (אובייקט גיליון), chat_id (str/int), col (int)
    פלט: True/False
    """
    print(f"[DEBUG] find_chat_id_in_sheet: chat_id={chat_id}, col={col}")
    logging.debug(f"[DEBUG] find_chat_id_in_sheet: chat_id={chat_id}, col={col}")
    try:
        values = sheet.col_values(col)
        for v in values[1:]:  # דילוג על כותרת
            if str(v).strip() == str(chat_id).strip():
                print(f"[find_chat_id_in_sheet] נמצא chat_id {chat_id} בעמודה {col}")
                print(f"[DEBUG] find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}")
                logging.debug(f"[DEBUG] find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}")
                return True
        print(f"[find_chat_id_in_sheet] לא נמצא chat_id {chat_id} בעמודה {col}")
        print(f"[DEBUG] find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}")
        logging.debug(f"[DEBUG] find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}")
        return False
    except Exception as e:
        print(f"שגיאה בחיפוש chat_id בגיליון: {e}")
        print(f"[DEBUG] find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}")
        logging.debug(f"[DEBUG] find_chat_id_in_sheet: סיום | chat_id={chat_id}, col={col}")
        return False

def ensure_user_state_row(sheet_users, sheet_states, chat_id):
    """
    בודק אם המשתמש קיים בגיליונות, ואם לא — מוסיף אותו ל-user_states.
    קלט: sheet_users, sheet_states, chat_id
    פלט: True אם זו פנייה ראשונה, אחרת False
    """
    print(f"[DEBUG] ensure_user_state_row: chat_id={chat_id}")
    logging.debug(f"[DEBUG] ensure_user_state_row: chat_id={chat_id}")
    # בדיקה בגיליון 1 (access_codes) — עמודה 1
    if find_chat_id_in_sheet(sheet_users, chat_id, col=1):
        print(f"[ensure_user_state_row] chat_id {chat_id} נמצא בגיליון 1 — לא פנייה ראשונה.")
        print(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        logging.debug(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        return False
    # בדיקה ב-user_states — עמודה 1
    if find_chat_id_in_sheet(sheet_states, chat_id, col=1):
        print(f"[ensure_user_state_row] chat_id {chat_id} כבר קיים ב-user_states — לא פנייה ראשונה.")
        print(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        logging.debug(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        return False
    # לא נמצא — פנייה ראשונה אי-פעם: יצירת שורה חדשה
    try:
        sheet_states.append_row([str(chat_id), 0])
        print(f"[ensure_user_state_row] ✅ נרשם chat_id {chat_id} ל-user_states (פנייה ראשונה, code_try=0)")
        # שליחת הודעה לאדמין
        from notifications import send_error_notification
        from messages import new_user_admin_message
        send_error_notification(new_user_admin_message(chat_id))
        print(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        logging.debug(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        return True
    except Exception as e:
        print(f"שגיאה ביצירת שורה חדשה ב-user_states: {e}")
        print(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        logging.debug(f"[DEBUG] ensure_user_state_row: סיום | chat_id={chat_id}")
        return False


def increment_code_try(sheet_states, chat_id):
    """
    מגדיל את מונה הניסיונות של המשתמש להזין קוד בגיליון user_states.
    קלט: sheet_states, chat_id
    פלט: מספר הניסיון הנוכחי (int)
    """
    print(f"[DEBUG] increment_code_try: chat_id={chat_id}")
    logging.debug(f"[DEBUG] increment_code_try: chat_id={chat_id}")
    try:
        records = sheet_states.get_all_records()
        header = sheet_states.row_values(1)
        for idx, row in enumerate(records):
            if str(row.get("chat_id")) == str(chat_id):
                current_try = row.get("code_try")
                if current_try is None or current_try == "":
                    current_try = 0
                else:
                    current_try = int(current_try)
                new_try = current_try + 1
                col_index = header.index("code_try") + 1
                sheet_states.update_cell(idx + 2, col_index, new_try)
                print(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
                logging.debug(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
                return new_try
        # אם לא נמצא שורה, מוסיף שורה עם code_try=0
        sheet_states.append_row([str(chat_id), 0])
        print(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
        logging.debug(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
        return 0
    except Exception as e:
        print(f"שגיאה בהעלאת code_try: {e}")
        # במקרה של שגיאה, מחזיר את המספר האחרון שנשמר בגיליון
        try:
            records = sheet_states.get_all_records()
            for row in records:
                if str(row.get("chat_id")) == str(chat_id):
                    current_try = row.get("code_try")
                    if current_try is None or current_try == "":
                        print(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
                        logging.debug(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
                        return 0
                    print(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
                    logging.debug(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
                    return int(current_try)
            # אם לא נמצא, מחזיר 0
            return 0
        except Exception as e2:
            print(f"שגיאה בקריאה חוזרת של code_try: {e2}")
            # אם לא מצליח לקרוא בכלל, מחזיר 1 כדי שלא ישבור
            print(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
            logging.debug(f"[DEBUG] increment_code_try: סיום | chat_id={chat_id}")
            return 1





def get_user_summary(chat_id):
    """
    מחזיר את סיכום המשתמש מהגיליון (summary).
    קלט: chat_id
    פלט: summary (str)
    """
    print(f"[DEBUG] get_user_summary: chat_id={chat_id}")
    logging.debug(f"[DEBUG] get_user_summary: chat_id={chat_id}")
    try:
        all_records = sheet_users.get_all_records()
        for row in all_records:
            if str(row.get("chat_id", "")).strip() == str(chat_id):
                summary = row.get("summary", "")
                if summary is not None:
                    summary = str(summary).strip()
                else:
                    summary = ""
                print(f"[DEBUG] get_user_summary: סיום | chat_id={chat_id}")
                logging.debug(f"[DEBUG] get_user_summary: סיום | chat_id={chat_id}")
                return summary
        print(f"[DEBUG] get_user_summary: סיום | chat_id={chat_id}")
        logging.debug(f"[DEBUG] get_user_summary: סיום | chat_id={chat_id}")
        return ""
    except Exception as e:
        print(f"❌ שגיאה בקריאת סיכום משתמש: {e}")
        logging.error(f"❌ שגיאה בקריאת סיכום משתמש: {e}")
        return ""

def update_user_profile(chat_id, field_values):
    """
    מעדכן את הפרופיל של המשתמש בגיליון לפי field_values.
    קלט: chat_id, field_values (dict)
    פלט: אין (מעדכן בגיליון)
    """
    print(f"[DEBUG] update_user_profile: chat_id={chat_id}, field_values={field_values}")
    logging.debug(f"[DEBUG] update_user_profile: chat_id={chat_id}, field_values={field_values}")
    if not isinstance(field_values, dict):
        logging.error(f"❌ update_user_profile קיבל טיפוס לא תקין: {type(field_values)}. הערך: {field_values}")
        raise TypeError(f"update_user_profile: field_values חייב להיות dict! קיבלתי: {type(field_values)}")
    try:
        all_records = sheet_users.get_all_records()
        header = sheet_users.row_values(1)
        print(f"📋 כותרות הגיליון: {header}")
        for idx, row in enumerate(all_records):
            if str(row.get("chat_id", "")) == str(chat_id):
                print(f"👤 מצא משתמש בשורה {idx + 2}")
                updated_fields = []
                for key, value in field_values.items():
                    if key in header and value is not None and str(value).strip() != "":
                        col_index = header.index(key) + 1
                        print(f"[DEBUG] updating field: {key} = '{value}' at col {col_index}")
                        logging.info(f"[DEBUG] updating field: {key} = '{value}' at col {col_index}")
                        try:
                            sheet_users.update_cell(idx + 2, col_index, str(value))
                            updated_fields.append(f"{key}: {value}")
                        except Exception as e:
                            print(f"❌ שגיאה בעדכון תא {key}: {e}")
                            logging.error(f"❌ שגיאה בעדכון תא {key}: {e}")
                    elif key not in header:
                        print(f"⚠️ שדה {key} לא קיים בגיליון, מדלג.")
                        logging.warning(f"⚠️ שדה {key} לא קיים בגיליון, מדלג.")
                if updated_fields:
                    print(f"[DEBUG] updated fields: {updated_fields}")
                    logging.info(f"[DEBUG] updated fields: {updated_fields}")
                    updated_row = sheet_users.row_values(idx + 2)
                    row_dict = dict(zip(header, updated_row))
                    summary = compose_emotional_summary(row_dict)
                    if SUMMARY_FIELD in header:
                        summary_col = header.index(SUMMARY_FIELD) + 1
                        print(f"📊 מעדכן סיכום בעמודה {summary_col}: '{summary}'")
                        try:
                            sheet_users.update_cell(idx + 2, summary_col, summary)
                        except Exception as e:
                            print(f"❌ שגיאה בעדכון סיכום: {e}")
                            logging.error(f"❌ שגיאה בעדכון סיכום: {e}")
                    else:
                        print(f"⚠️ לא נמצאה עמודת סיכום: {SUMMARY_FIELD}")
                        logging.warning(f"⚠️ לא נמצאה עמודת סיכום: {SUMMARY_FIELD}")
                else:
                    print("⚠️ לא עודכנו שדות - אין ערכים תקינים")
                    logging.info("⚠️ לא עודכנו שדות - אין ערכים תקינים")
                break
        else:
            print(f"❌ לא נמצא משתמש עם chat_id: {chat_id}")
            logging.warning(f"❌ לא נמצא משתמש עם chat_id: {chat_id}")
    except Exception as e:
        print(f"💥 שגיאה בעדכון פרופיל: {e}")
        logging.error(f"💥 שגיאה בעדכון פרופיל: {e}")
        import traceback
        traceback.print_exc()
    print(f"[DEBUG] update_user_profile: סיום | chat_id={chat_id}")
    logging.debug(f"[DEBUG] update_user_profile: סיום | chat_id={chat_id}")

def compose_emotional_summary(row):
    print(f"[DEBUG] compose_emotional_summary: row keys={list(row.keys())}")
    logging.debug(f"[DEBUG] compose_emotional_summary: row keys={list(row.keys())}")
    parts = []
    for key, value in row.items():
        v = str(value).strip()
        if v and key != "chat_id":
            field_name = FIELDS_DICT.get(key, key)
            if isinstance(field_name, dict):
                field_name = field_name.get("label", key)
            parts.append(f"{field_name}: {v}")
    if not parts:
        print(f"[DEBUG] compose_emotional_summary: סיום")
        logging.debug(f"[DEBUG] compose_emotional_summary: סיום")
        return "[אין מידע לסיכום]"
    summary = ", ".join(parts)
    if len(summary) > 200:
        summary = summary[:197] + "..."
    print(f"[DEBUG] compose_emotional_summary: סיום")
    logging.debug(f"[DEBUG] compose_emotional_summary: סיום")
    return summary

def log_to_sheets(
    message_id, chat_id, user_msg, reply_text, reply_summary,
    main_usage, summary_usage, extract_usage, total_tokens,
    cost_usd, cost_ils,
    prompt_tokens_total=None, completion_tokens_total=None, cached_tokens=None,
    cached_tokens_gpt1=None, cost_gpt1=None,
    cached_tokens_gpt2=None, cost_gpt2=None,
    cached_tokens_gpt3=None, cost_gpt3=None
):
    """
    שומר את כל נתוני השיחה בגיליון הלוגים.
    מחשב את כל הפרמטרים החסרים אוטומטית אם לא סופקו.
    """
    try:
        now = datetime.now()
        timestamp_full = now.strftime("%Y-%m-%d %H:%M:%S")
        date_only = now.strftime("%d/%m/%Y")
        time_only = now.strftime("%H:%M")

        header = sheet_log.row_values(1)
        row_data = [""] * len(header)

        # 🚨 תיקון 1: וידוא נתונים בסיסיים
        if not message_id:
            message_id = f"msg_{now.strftime('%Y%m%d_%H%M%S')}"
            print(f"⚠️ יצירת message_id זמני: {message_id}")
            
        if not chat_id:
            print("❌ שגיאה קריטית: chat_id ריק!")
            return False

        print(f"📝 שמירת לוג: message_id={message_id}, chat_id={chat_id}")

        # פונקציה לביטחון להמרת ערכים
        def safe_float(val):
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        def safe_int(val):
            try:
                return int(val) if val is not None else 0
            except (ValueError, TypeError):
                return 0

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

        # extract_usage תמיד dict
        extract_prompt_tokens = safe_int(extract_usage.get("prompt_tokens", 0))
        extract_completion_tokens = safe_int(extract_usage.get("completion_tokens", 0))
        extract_total_tokens = safe_int(extract_usage.get("total_tokens", 0))
        extract_model = extract_usage.get("model", "")
        extract_cost_agorot = safe_float(extract_usage.get("cost_agorot", 0))

        # --- חישוב ערכים מראש כדי למנוע גישה עצמית ל-values_to_log ---
        def safe_calc(calc_func, field_name):
            try:
                return calc_func()
            except Exception as e:
                from notifications import send_error_notification
                send_error_notification(f"❌ שגיאה בחישוב שדה {field_name}: {e}")
                return "-"

        prompt_tokens_total = safe_calc(lambda: (
            safe_int(main_usage.get("prompt_tokens", 0) - main_usage.get("cached_tokens", 0)) +
            safe_int(summary_usage.get("prompt_tokens", 0) - summary_usage.get("cached_tokens", 0)) +
            safe_int(extract_usage.get("prompt_tokens", 0) - extract_usage.get("cached_tokens", 0)) +
            (safe_int(merge_usage.get("prompt_tokens", 0) - merge_usage.get("cached_tokens", 0)) if 'merge_usage' in locals() else 0)
        ), "prompt_tokens_total")

        completion_tokens_total = safe_calc(lambda: (
            safe_int(main_usage.get("completion_tokens", 0)) +
            safe_int(summary_usage.get("completion_tokens", 0)) +
            safe_int(extract_usage.get("completion_tokens", 0)) +
            (safe_int(merge_usage.get("completion_tokens", 0)) if 'merge_usage' in locals() else 0)
        ), "completion_tokens_total")

        cached_tokens = safe_calc(lambda: (
            safe_int(main_usage.get("cached_tokens", 0)) +
            safe_int(summary_usage.get("cached_tokens", 0)) +
            safe_int(extract_usage.get("cached_tokens", 0)) +
            (safe_int(merge_usage.get("cached_tokens", 0)) if 'merge_usage' in locals() else 0)
        ), "cached_tokens")

        total_tokens = safe_calc(lambda: (
            safe_int(prompt_tokens_total) + safe_int(completion_tokens_total) + safe_int(cached_tokens)
        ), "total_tokens")

        # חישוב cached tokens (כרגע 0 כי OpenAI לא מחזיר)
        if cached_tokens is None:
            cached_tokens = 0
        if cached_tokens_gpt1 is None:
            cached_tokens_gpt1 = 0
        if cached_tokens_gpt2 is None:
            cached_tokens_gpt2 = 0
        if cached_tokens_gpt3 is None:
            cached_tokens_gpt3 = 0

        # 🚨 תיקון 3: חישוב עלויות מפורטות
        # שימוש בפונקציה המרכזית מ-gpt_handler במקום חישוב פנימי
        def get_gpt_costs(prompt_tokens, completion_tokens, cached_tokens=0):
            return calculate_gpt_cost(prompt_tokens, completion_tokens, cached_tokens)

        # חישוב עלויות אם לא סופקו
        if cost_gpt1 is None:
            costs = get_gpt_costs(main_usage.get("prompt_tokens", 0), main_usage.get("completion_tokens", 0), main_usage.get("cached_tokens", 0))
            cost_gpt1 = costs["cost_total_ils"]
        if cost_gpt2 is None:
            costs = get_gpt_costs(summary_usage.get("prompt_tokens", 0), summary_usage.get("completion_tokens", 0), summary_usage.get("cached_tokens", 0))
            cost_gpt2 = costs["cost_total_ils"]
        if cost_gpt3 is None:
            costs = get_gpt_costs(extract_usage.get("prompt_tokens", 0), extract_usage.get("completion_tokens", 0), extract_usage.get("cached_tokens", 0))
            cost_gpt3 = costs["cost_total_ils"]

        # 🚨 תיקון 4: ניקוי ערכי עלות
        def clean_cost_value(cost_val):
            if cost_val is None or cost_val == "":
                return 0
            if isinstance(cost_val, str):
                cleaned = cost_val.replace("$", "").replace("₪", "").replace(",", "").strip()
                try:
                    return safe_float(cleaned)
                except:
                    return 0
            return safe_float(cost_val)

        clean_cost_usd = clean_cost_value(cost_usd)
        clean_cost_ils = clean_cost_value(cost_ils)

        # האם הופעל סיכום (GPT2)?
        has_summary = summary_usage and len(summary_usage) > 0 and safe_float(summary_usage.get("completion_tokens", 0)) > 0

        # --- עלות כוללת בדולר (מחושב לפי טבלת עלויות) ---
        def format_money(value):
            if value is None:
                return None
            return float(f"{value:.10f}")  # או פשוט return float(value)

        # --- מיפוי ערכים מלא לפי דרישת המשתמש ---
        values_to_log = {
            "message_id": str(message_id),  # מזהה ייחודי להודעה
            "chat_id": str(chat_id),  # מזהה ייחודי למשתמש
            "user_msg": user_msg if user_msg else "",  # הודעת המשתמש
            "user_summary": "",  # תמצות הודעת המשתמש (לא לגעת)
            "bot_reply": reply_text if reply_text else "",  # תשובת הבוט
            "bot_summary": reply_summary if has_summary and reply_summary else "",  # סיכום תשובת הבוט
            "total_tokens": total_tokens,  # סך כל הטוקנים
            "prompt_tokens_total": prompt_tokens_total,  # סך טוקנים בפרומט
            "completion_tokens_total": completion_tokens_total,  # סך טוקנים בתשובה
            "cached_tokens": cached_tokens,  # סך טוקנים קש
            # עלות כוללת בדולר (מחושב לפי טבלת עלויות)
            "total_cost_usd": format_money(main_cost_usd),
            # עלות כוללת באגורות (מחושב לפי שער דולר)
            "total_cost_ils": format_money(main_cost_ils * 100),
            # --- GPT1 ---
            "usage_prompt_tokens_GPT1": safe_calc(lambda: safe_int(main_usage.get("prompt_tokens", 0) - main_usage.get("cached_tokens", 0)), "usage_prompt_tokens_GPT1"),
            "usage_completion_tokens_GPT1": safe_calc(lambda: safe_int(main_usage.get("completion_tokens", 0)), "usage_completion_tokens_GPT1"),
            "usage_total_tokens_GPT1": safe_calc(lambda: (
                safe_int(main_usage.get("cached_tokens", 0)) +
                safe_int(main_usage.get("completion_tokens", 0)) +
                safe_int(main_usage.get("prompt_tokens", 0))
            ), "usage_total_tokens_GPT1"),
            "cached_tokens_gpt1": safe_calc(lambda: safe_int(main_usage.get("cached_tokens", 0)), "cached_tokens_gpt1"),
            "cost_gpt1": format_money(main_cost_agorot),
            "model_GPT1": str(main_usage.get("model", "")),
            # --- GPT2 ---
            "usage_prompt_tokens_GPT2": safe_calc(lambda: safe_int(summary_usage.get("prompt_tokens", 0) - summary_usage.get("cached_tokens", 0)), "usage_prompt_tokens_GPT2"),
            "usage_completion_tokens_GPT2": safe_calc(lambda: safe_int(summary_usage.get("completion_tokens", 0)), "usage_completion_tokens_GPT2"),
            "usage_total_tokens_GPT2": safe_calc(lambda: (
                safe_int(summary_usage.get("cached_tokens", 0)) +
                safe_int(summary_usage.get("completion_tokens", 0)) +
                safe_int(summary_usage.get("prompt_tokens", 0))
            ), "usage_total_tokens_GPT2"),
            "cached_tokens_gpt2": safe_calc(lambda: safe_int(summary_usage.get("cached_tokens", 0)), "cached_tokens_gpt2"),
            "cost_gpt2": format_money(summary_cost_agorot),
            "model_GPT2": str(summary_usage.get("model", "")),
            # --- GPT3 ---
            "usage_prompt_tokens_GPT3": safe_calc(lambda: safe_int(extract_usage.get("prompt_tokens", 0) - extract_usage.get("cached_tokens", 0)), "usage_prompt_tokens_GPT3"),
            "usage_completion_tokens_GPT3": safe_calc(lambda: safe_int(extract_usage.get("completion_tokens", 0)), "usage_completion_tokens_GPT3"),
            "usage_total_tokens_GPT3": safe_calc(lambda: (
                safe_int(extract_usage.get("cached_tokens", 0)) +
                safe_int(extract_usage.get("completion_tokens", 0)) +
                safe_int(extract_usage.get("prompt_tokens", 0))
            ), "usage_total_tokens_GPT3"),
            "cached_tokens_gpt3": safe_calc(lambda: safe_int(extract_usage.get("cached_tokens", 0)), "cached_tokens_gpt3"),
            "cost_gpt3": format_money(extract_cost_agorot),
            "model_GPT3": str(extract_usage.get("model", "")),
            # --- GPT4 ---
            "usage_prompt_tokens_GPT4": safe_calc(lambda: safe_int(merge_usage.get("prompt_tokens", 0) - merge_usage.get("cached_tokens", 0)) if 'merge_usage' in locals() else 0, "usage_prompt_tokens_GPT4"),
            "usage_completion_tokens_GPT4": safe_calc(lambda: safe_int(merge_usage.get("completion_tokens", 0)) if 'merge_usage' in locals() else 0, "usage_completion_tokens_GPT4"),
            "usage_total_tokens_GPT4": safe_calc(lambda: (
                safe_int(merge_usage.get("cached_tokens", 0)) +
                safe_int(merge_usage.get("completion_tokens", 0)) +
                safe_int(merge_usage.get("prompt_tokens", 0))
            ) if 'merge_usage' in locals() else 0, "usage_total_tokens_GPT4"),
            "cached_tokens_GPT4": safe_calc(lambda: safe_int(merge_usage.get("cached_tokens", 0)) if 'merge_usage' in locals() else 0, "cached_tokens_GPT4"),
            "cost_GPT4": format_money(merge_usage.get("cost_agorot", 0)) if 'merge_usage' in locals() else "-",
            "model_GPT4": str(merge_usage.get("model", "")) if 'merge_usage' in locals() else "",
            # --- שדות נוספים ---
            "fields_updated_by_4gpt": str(fields_updated_by_4gpt) if 'fields_updated_by_4gpt' in locals() else "",
            "timestamp": timestamp_full,  # טיימסטפ מלא
            "date_only": date_only,  # תאריך בלבד
            "time_only": time_only,  # שעה בלבד
        }

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
                # הגנה: אם הערך הוא dict או list, המר אותו ל-str (json)
                if isinstance(val, (dict, list)):
                    print(f"[DEBUG] המרת ערך לשדה '{key}' מטיפוס {type(val)} ל-str (json)")
                    val = json.dumps(val, ensure_ascii=False)
                row_data[idx] = val
        # שמירה בגיליון
        sheet_log.insert_row(row_data, 3)

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

    if sheet_name == "user_states":
        worksheet = sheet_states
    elif sheet_name == "log":
        worksheet = sheet_log
    else:
        worksheet = sheet_users

    all_records = worksheet.get_all_records()
    header = worksheet.row_values(1)  # רשימת כותרות
    for idx, row in enumerate(all_records, start=2):  # מתחילים מ-2 כי שורה 1 זה כותרות
        if str(row.get("chat_id")) == str(chat_id):
            if sheet_name == "user_states":
                # מוחק את כל השורה
                worksheet.delete_row(idx)
                print(f"✅ נמחקה שורה לגמרי עבור chat_id {chat_id} בגיליון user_states (שורה {idx})")
            else:
                # מרוקן את כל העמודות חוץ מהעמודה הראשונה (קוד)
                for col in range(2, len(header) + 1):  # עמודה 2 עד סוף (1 זה הקוד)
                    worksheet.update_cell(idx, col, "")
                print(f"✅ נוקתה השורה עבור chat_id {chat_id} בגיליון1 (נשמר רק הקוד בשורה {idx})")
            return True
    print(f"❌ לא נמצאה שורה עם chat_id {chat_id} למחיקה בגיליון {sheet_name}")
    return False

# תודה1
