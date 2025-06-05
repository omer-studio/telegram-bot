"""
sheets_handler.py — ניהול גישה, הרשאות ולוגים ב-Google Sheets

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


# יצירת חיבור לגיליונות — הפונקציה חייבת להחזיר 3 גיליונות!
sheet_users, sheet_log, sheet_states = setup_google_sheets()

def find_chat_id_in_sheet(sheet, chat_id, col=1):
    """
    מחפש chat_id בעמודה נתונה (ברירת מחדל: עמודה 1).
    למה? כדי לדעת אם המשתמש כבר מוכר במערכת.
    """
    try:
        values = sheet.col_values(col)
        for v in values[1:]:  # דילוג על כותרת
            if str(v).strip() == str(chat_id).strip():
                print(f"[find_chat_id_in_sheet] נמצא chat_id {chat_id} בעמודה {col}")
                return True
        print(f"[find_chat_id_in_sheet] לא נמצא chat_id {chat_id} בעמודה {col}")
        return False
    except Exception as e:
        print(f"שגיאה בחיפוש chat_id בגיליון: {e}")
        return False

def ensure_user_state_row(sheet_users, sheet_states, chat_id):
    """
    לוגיקת Onboarding — רושם משתמש חדש ב-user_states רק אם לא קיים לא בגיליון 1 ולא ב-user_states.
    למה? כי רק אם זו פנייה ראשונה אי-פעם, יש לרשום את המשתמש ב-user_states עם code_try=0.
    מחזיר True אם נוצרה שורה חדשה (פנייה ראשונה), אחרת False.
    """
    # בדיקה בגיליון 1 (access_codes) — עמודה 1
    if find_chat_id_in_sheet(sheet_users, chat_id, col=1):
        print(f"[ensure_user_state_row] chat_id {chat_id} נמצא בגיליון 1 — לא פנייה ראשונה.")
        return False
    # בדיקה ב-user_states — עמודה 1
    if find_chat_id_in_sheet(sheet_states, chat_id, col=1):
        print(f"[ensure_user_state_row] chat_id {chat_id} כבר קיים ב-user_states — לא פנייה ראשונה.")
        return False
    # לא נמצא — פנייה ראשונה אי-פעם: יצירת שורה חדשה
    try:
        sheet_states.append_row([str(chat_id), 0])
        print(f"[ensure_user_state_row] ✅ נרשם chat_id {chat_id} ל-user_states (פנייה ראשונה, code_try=0)")
        return True
    except Exception as e:
        print(f"שגיאה ביצירת שורה חדשה ב-user_states: {e}")
        return False


def increment_code_try(sheet_states, chat_id):
    """
    מעלה את ערך code_try ב-user_states ב-1 למשתמש הרלוונטי.
    אם לא קיים, מוסיף שורה עם code_try=0 (עוד לא ניסה).
    במקרה של שגיאה מחזיר את הערך האחרון שנמצא (ולא None או 0).
    """
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
                return new_try
        # אם לא נמצא שורה, מוסיף שורה עם code_try=0
        sheet_states.append_row([str(chat_id), 0])
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
                        return 0
                    return int(current_try)
            # אם לא נמצא, מחזיר 0
            return 0
        except Exception as e2:
            print(f"שגיאה בקריאה חוזרת של code_try: {e2}")
            # אם לא מצליח לקרוא בכלל, מחזיר 1 כדי שלא ישבור
            return 1





def get_user_summary(chat_id):
    """
    מחזיר את הסיכום של המשתמש מגיליון המשתמשים.
    לוגיקה: מגיש את הנתונים ל-GPT עבור קונטקסט אישי.
    """
    try:
        all_records = sheet_users.get_all_records()
        for row in all_records:
            if str(row.get("chat_id")) == str(chat_id):
                summary = row.get(FIELDS_DICT['summary'], "").strip()
                if summary:
                    return summary
        return ""
    except Exception as e:
        print(f"❌ שגיאה בקריאת סיכום משתמש: {e}")
        return ""

def update_user_profile(chat_id, field_values):
    """
    מעדכן פרופיל משתמש בגיליון המשתמשים.
    לכל שדה שמעודכן — מתעדכן גם סיכום רגשי.
    חובה: field_values חייב להיות dict בלבד!
    """
    if not isinstance(field_values, dict):
        logging.error(f"❌ update_user_profile קיבל טיפוס לא תקין: {type(field_values)}. הערך: {field_values}")
        raise TypeError(f"update_user_profile: field_values חייב להיות dict! קיבלתי: {type(field_values)}")
    try:
        print(f"[DEBUG] update_user_profile: chat_id={chat_id}, field_values={field_values}")
        logging.info(f"[DEBUG] update_user_profile: chat_id={chat_id}, field_values={field_values}")
        print(f"🔄 מעדכן פרופיל למשתמש {chat_id} עם שדות: {field_values}")

        all_records = sheet_users.get_all_records()
        header = sheet_users.row_values(1)
        print(f"📋 כותרות הגיליון: {header}")

        for idx, row in enumerate(all_records):
            if str(row.get("chat_id")) == str(chat_id):
                print(f"👤 מצא משתמש בשורה {idx + 2}")
                updated_fields = []

                for key, value in field_values.items():
                    if key in header and value:
                        col_index = header.index(key) + 1
                        print(f"[DEBUG] updating field: {key} = '{value}' at col {col_index}")
                        logging.info(f"[DEBUG] updating field: {key} = '{value}' at col {col_index}")
                        sheet_users.update_cell(idx + 2, col_index, str(value))
                        updated_fields.append(f"{key}: {value}")

                if updated_fields:
                    print(f"[DEBUG] updated fields: {updated_fields}")
                    logging.info(f"[DEBUG] updated fields: {updated_fields}")

                    # מעדכן סיכום
                    updated_row = sheet_users.row_values(idx + 2)
                    row_dict = dict(zip(header, updated_row))
                    summary = compose_emotional_summary(row_dict)

                    if SUMMARY_FIELD in header:
                        summary_col = header.index(SUMMARY_FIELD) + 1
                        print(f"📊 מעדכן סיכום בעמודה {summary_col}: '{summary}'")
                        sheet_users.update_cell(idx + 2, summary_col, summary)
                    else:
                        print(f"⚠️ לא נמצאה עמודת סיכום: {SUMMARY_FIELD}")
                else:
                    print("⚠️ לא עודכנו שדות - אין ערכים תקינים")

                break
        else:
            print(f"❌ לא נמצא משתמש עם chat_id: {chat_id}")

    except Exception as e:
        print(f"💥 שגיאה בעדכון פרופיל: {e}")
        import traceback
        traceback.print_exc()

def compose_emotional_summary(row):
    """
    יוצר סיכום רגשי מפרטי המשתמש (עבור קונטקסט ל-GPT).
    כעת כל שדה שקיים בפרופיל ושאינו ריק נכנס לסיכום.
    הפורמט: שם שדה: ערך, שם שדה: ערך, ...
    לדוג' -> age: 25, relationship_type: נשוי+2, trauma_history: ...
    חותך ל-200 תווים לכל היותר.
    אם אין מידע בכלל, מחזיר [אין מידע לסיכום]
    """
    # --- אוסף את כל השדות שאינם ריקים (חוץ מ-chat_id) ---
    parts = []
    for key, value in row.items():
        v = str(value).strip()
        if v and key != FIELDS_DICT["chat_id"]:
            # Use Hebrew name from FIELDS_DICT if you want aesthetics
            field_name = FIELDS_DICT.get(key, key)
            parts.append(f"{field_name}: {v}")
    # --- אם אין מידע בכלל ---
    if not parts:
        return "[אין מידע לסיכום]"
    # --- מחבר את כל השדות בפסיקים ---
    summary = ", ".join(parts)
    # --- קיצור אם ארוך מדי ---
    if len(summary) > 200:
        summary = summary[:197] + "..."
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
        main_cost_gpt1 = safe_int(main_usage.get("cost_gpt1", 0))
        main_cost_usd = safe_float(main_usage.get("cost_total", 0))
        main_cost_ils = safe_float(main_usage.get("cost_total_ils", 0))

        # אם summary_usage או extract_usage קיימים, נוסיף אותם
        summary_prompt_tokens = safe_int(summary_usage[1]) if summary_usage and len(summary_usage) > 1 else 0
        summary_completion_tokens = safe_int(summary_usage[2]) if summary_usage and len(summary_usage) > 2 else 0
        summary_total_tokens = safe_int(summary_usage[3]) if summary_usage and len(summary_usage) > 3 else 0
        summary_model = summary_usage[4] if summary_usage and len(summary_usage) > 4 else ""

        # --- תיקון: תמיכה גם ב-tuple וגם ב-dict ל-extract_usage ---
        if isinstance(extract_usage, (list, tuple)):
            extract_prompt_tokens = safe_int(extract_usage[0]) if len(extract_usage) > 0 else 0
            extract_completion_tokens = safe_int(extract_usage[4]) if len(extract_usage) > 4 else 0
            extract_total_tokens = safe_int(extract_usage[5]) if len(extract_usage) > 5 else 0
            extract_model = extract_usage[11] if len(extract_usage) > 11 else ""
        elif isinstance(extract_usage, dict):
            extract_prompt_tokens = safe_int(extract_usage.get("prompt_tokens", 0))
            extract_completion_tokens = safe_int(extract_usage.get("completion_tokens", 0))
            extract_total_tokens = safe_int(extract_usage.get("total_tokens", 0))
            extract_model = extract_usage.get("model", "")
        else:
            extract_prompt_tokens = extract_completion_tokens = extract_total_tokens = 0
            extract_model = ""

        # סיכום כולל
        prompt_tokens_total = main_prompt_tokens + summary_prompt_tokens + extract_prompt_tokens
        completion_tokens_total = main_completion_tokens + summary_completion_tokens + extract_completion_tokens
        total_tokens = main_total_tokens + summary_total_tokens + extract_total_tokens
        cached_tokens = main_cached_tokens

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
        if cost_gpt1 is None and main_usage and len(main_usage) >= 2:
            costs = get_gpt_costs(main_usage[0], main_usage[1], main_usage[3] if len(main_usage) > 3 else 0)
            cost_gpt1 = costs["cost_agorot"]
        elif cost_gpt1 is None:
            cost_gpt1 = 0

        if cost_gpt2 is None and summary_usage and len(summary_usage) >= 3:
            costs = get_gpt_costs(summary_usage[1], summary_usage[2])
            cost_gpt2 = costs["cost_agorot"]
        elif cost_gpt2 is None:
            cost_gpt2 = 0

        if cost_gpt3 is None and extract_usage:
            if isinstance(extract_usage, (list, tuple)):
                costs = get_gpt_costs(
                    extract_usage[0] if len(extract_usage) > 0 else 0,
                    extract_usage[4] if len(extract_usage) > 4 else 0
                )
                cost_gpt3 = costs["cost_agorot"]
            elif isinstance(extract_usage, dict):
                costs = get_gpt_costs(
                    extract_usage.get("prompt_tokens", 0),
                    extract_usage.get("completion_tokens", 0)
                )
                cost_gpt3 = costs["cost_agorot"]
            else:
                cost_gpt3 = 0
        elif cost_gpt3 is None:
            cost_gpt3 = 0

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
        has_summary = summary_usage and len(summary_usage) > 0 and safe_float(summary_usage[2]) > 0

        # 🚨 תיקון 5: מיפוי מדויק לכותרות הגיליון
        values_to_log = {
            FIELDS_DICT["message_id"]: str(message_id),
            FIELDS_DICT["chat_id"]: str(chat_id),
            FIELDS_DICT["user_msg"]: user_msg if user_msg else "",
            FIELDS_DICT["user_summary"]: "",  # future
            FIELDS_DICT["bot_reply"]: reply_text if reply_text else "",
            FIELDS_DICT["bot_summary"]: reply_summary if has_summary and reply_summary else "",
            
            # שדות ריקים
            FIELDS_DICT["empty_1"]: "",
            FIELDS_DICT["empty_2"]: "",  
            FIELDS_DICT["empty_3"]: "",
            FIELDS_DICT["empty_4"]: "",
            FIELDS_DICT["empty_5"]: "",
            
            # סך טוקנים
            FIELDS_DICT["total_tokens"]: safe_int(total_tokens),
            FIELDS_DICT["prompt_tokens_total"]: prompt_tokens_total,
            FIELDS_DICT["completion_tokens_total"]: completion_tokens_total,
            FIELDS_DICT["cached_tokens"]: cached_tokens,
            
            # עלויות כוללות
            FIELDS_DICT["total_cost_usd"]: clean_cost_usd if clean_cost_usd > 0 else "",
            FIELDS_DICT["total_cost_ils"]: safe_int(clean_cost_ils * 100) if clean_cost_ils > 0 else "",  # באגורות
            
            # נתוני GPT1 (main)
            FIELDS_DICT["usage_prompt_tokens_GPT1"]: main_usage.get("prompt_tokens", ""),
            FIELDS_DICT["usage_completion_tokens_GPT1"]: main_usage.get("completion_tokens", ""),
            FIELDS_DICT["usage_total_tokens_GPT1"]: main_usage.get("total_tokens", ""),
            FIELDS_DICT["cached_tokens_gpt1"]: main_usage.get("cached_tokens", ""),
            FIELDS_DICT["cost_gpt1"]: main_usage.get("cost_gpt1", ""),
            FIELDS_DICT["model_GPT1"]: main_usage.get("model", ""),
            
            # נתוני GPT2 (summary)
            FIELDS_DICT["usage_prompt_tokens_GPT2"]: safe_int(summary_usage[1]) if summary_usage and len(summary_usage) > 1 else "",
            FIELDS_DICT["usage_completion_tokens_GPT2"]: safe_int(summary_usage[2]) if summary_usage and len(summary_usage) > 2 else "",
            FIELDS_DICT["usage_total_tokens_GPT2"]: safe_int(summary_usage[3]) if summary_usage and len(summary_usage) > 3 else "",
            FIELDS_DICT["cached_tokens_gpt2"]: cached_tokens_gpt2 if cached_tokens_gpt2 > 0 else "",
            FIELDS_DICT["cost_gpt2"]: cost_gpt2 if cost_gpt2 > 0 else "",
            FIELDS_DICT["model_GPT2"]: summary_usage[4] if summary_usage and len(summary_usage) > 4 else "",
            
            # נתוני GPT3 (extract)
            FIELDS_DICT["usage_prompt_tokens_GPT3"]: extract_prompt_tokens,
            FIELDS_DICT["usage_completion_tokens_GPT3"]: extract_completion_tokens,
            FIELDS_DICT["usage_total_tokens_GPT3"]: extract_total_tokens,
            FIELDS_DICT["cached_tokens_gpt3"]: cached_tokens_gpt3 if cached_tokens_gpt3 > 0 else "",
            FIELDS_DICT["cost_gpt3"]: cost_gpt3 if cost_gpt3 > 0 else "",
            FIELDS_DICT["model_GPT3"]: extract_model,
            
            # נתוני זמן
            FIELDS_DICT["timestamp"]: timestamp_full,
            FIELDS_DICT["date_only"]: date_only,
            FIELDS_DICT["time_only"]: time_only
        }

        # 🚨 תיקון 6: וידוא שכל הכותרות קיימות וההכנסה תקינה
        missing_headers = []
        for key in values_to_log.keys():
            if key not in header:
                missing_headers.append(key)
        
        if missing_headers:
            print(f"⚠️ כותרות חסרות בגיליון: {missing_headers}")

        # הכנסת ערכים לפי header
        for key, val in values_to_log.items():
            if key in header:
                idx = header.index(key)
                row_data[idx] = val
            else:
                print(f"⚠️ כותרת לא נמצאה: {key}")

        # שמירה בגיליון
        sheet_log.append_row(row_data)

        return True

    except Exception as e:
        print(f"❌ שגיאה בשמירה לגיליון: {e}")
        import traceback
        traceback.print_exc()
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


