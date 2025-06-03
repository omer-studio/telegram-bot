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
                summary = row.get("summary", "").strip()
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
    """
    try:
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
                        print(f"📝 מעדכן {key} = '{value}' בעמודה {col_index}")
                        sheet_users.update_cell(idx + 2, col_index, str(value))
                        updated_fields.append(f"{key}: {value}")

                if updated_fields:
                    print(f"✅ עודכנו שדות: {', '.join(updated_fields)}")

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
    """
    parts = []

    # גיל - תמיד ראשון
    age = row.get("age", "").strip()
    if age and str(age) != "":
        parts.append(f"בן {age}")

    # הקשר דתי
    religious = row.get("religious_context", "").strip()
    if religious and religious != "":
        parts.append(religious)

    # מצב משפחתי
    relationship = row.get("relationship_type", "").strip()
    if relationship and relationship != "":
        parts.append(relationship)

    # מצב ארון
    closet = row.get("closet_status", "").strip()
    if closet and closet != "":
        parts.append(closet)

    # משיכה
    attracted = row.get("attracted_to", "").strip()
    if attracted and attracted != "":
        parts.append(f"נמשך ל{attracted}")

    # מי יודע
    who_knows = row.get("who_knows", "").strip()
    if who_knows and who_knows != "":
        parts.append(f"יודעים: {who_knows}")

    # טיפול
    therapy = row.get("attends_therapy", "").strip()
    if therapy and therapy != "":
        if "כן" in therapy or "הולך" in therapy:
            parts.append("בטיפול")
        elif "לא" in therapy:
            parts.append("לא בטיפול")

    # עיסוק
    job = row.get("occupation_or_role", "").strip()
    if job and job != "":
        parts.append(job)

    # קונפליקט מרכזי - קצר
    conflict = row.get("primary_conflict", "").strip()
    if conflict and conflict != "" and len(conflict) < 30:
        parts.append(f"קונפליקט: {conflict}")

    # מטרה בקורס - קצר
    goal = row.get("goal_in_course", "").strip()
    if goal and goal != "" and len(goal) < 30:
        parts.append(f"מטרה: {goal}")

    # אם אין מידע כלל
    if not parts:
        return ""

    # מחבר עם פסיקים
    summary = " | ".join(parts)

    # אם ארוך מדי, מקצר
    if len(summary) > 100:
        essential_parts = []
        if age:
            essential_parts.append(f"בן {age}")
        if religious:
            essential_parts.append(religious)
        if relationship:
            essential_parts.append(relationship)
        if closet:
            essential_parts.append(closet)

        summary = " | ".join(essential_parts)

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

        # שליפה ישירה מתוך main_usage לפי הסדר החדש (13 ערכים מלאים)
        main_prompt_tokens = safe_int(main_usage[0])  # טוקנים קלט GPT1
        main_completion_tokens = safe_int(main_usage[1])
        main_total_tokens = safe_int(main_usage[2])
        main_cached_tokens = safe_int(main_usage[3])
        main_model = main_usage[4]
        main_cost_gpt1 = safe_int(main_usage[11])
        main_cost_usd = safe_float(main_usage[9])
        main_cost_ils = safe_float(main_usage[10])

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
        def calculate_gpt_cost_agorot(prompt_tokens, completion_tokens):
            """חישוב עלות ב-GPT-4o באגורות"""
            prompt_cost = safe_float(prompt_tokens) * 0.000005  # $0.005 per 1K tokens
            completion_cost = safe_float(completion_tokens) * 0.000015  # $0.015 per 1K tokens
            total_cost_usd = prompt_cost + completion_cost
            return safe_int(total_cost_usd * 3.8 * 100)  # המרה לאגורות

        # חישוב עלויות אם לא סופקו
        if cost_gpt1 is None and main_usage and len(main_usage) >= 2:
            cost_gpt1 = calculate_gpt_cost_agorot(main_usage[0], main_usage[1])
        elif cost_gpt1 is None:
            cost_gpt1 = 0

        if cost_gpt2 is None and summary_usage and len(summary_usage) >= 3:
            cost_gpt2 = calculate_gpt_cost_agorot(summary_usage[1], summary_usage[2])
        elif cost_gpt2 is None:
            cost_gpt2 = 0

        if cost_gpt3 is None and extract_usage:
            if isinstance(extract_usage, (list, tuple)):
                cost_gpt3 = calculate_gpt_cost_agorot(
                    extract_usage[0] if len(extract_usage) > 0 else 0,
                    extract_usage[4] if len(extract_usage) > 4 else 0
                )
            elif isinstance(extract_usage, dict):
                cost_gpt3 = calculate_gpt_cost_agorot(
                    extract_usage.get("prompt_tokens", 0),
                    extract_usage.get("completion_tokens", 0)
                )
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
            # פרטי הודעה בסיסיים
            "MASSAGE ID": str(message_id),  # שם מדויק מהגיליון
            "CHAT ID": str(chat_id),        # שם מדויק מהגיליון
            "user_msg": user_msg if user_msg else "",
            "user_summary": "",  # לעתיד
            "bot_reply": reply_text if reply_text else "",
            "bot_summary": reply_summary if has_summary and reply_summary else "",
            
            # שדות ריקים
            "empty_1": "",
            "empty_2": "",  
            "empty_3": "",
            "empty_4": "",
            "empty_5": "",
            
            # סך טוקנים
            "total_tokens": safe_int(total_tokens),
            "prompt_tokens_total": prompt_tokens_total,
            "completion_tokens_total": completion_tokens_total,
            "cached_tokens": cached_tokens,
            
            # עלויות כוללות
            "total_cost_usd": clean_cost_usd if clean_cost_usd > 0 else "",
            "total_cost_ils": safe_int(clean_cost_ils * 100) if clean_cost_ils > 0 else "",  # באגורות
            
            # נתוני GPT1 (main)
            "usage_prompt_tokens_GPT1": safe_int(main_usage[0]) if main_usage and len(main_usage) > 0 else "",
            "usage_completion_tokens_GPT1": safe_int(main_usage[1]) if main_usage and len(main_usage) > 1 else "",
            "usage_total_tokens_GPT1": safe_int(main_usage[2]) if main_usage and len(main_usage) > 2 else "",
            "cached_tokens_gpt1": cached_tokens_gpt1 if cached_tokens_gpt1 > 0 else "",
            "cost_gpt1": cost_gpt1 if cost_gpt1 > 0 else "",
            "model_GPT1": main_usage[4] if main_usage and len(main_usage) > 4 else "",
            
            # נתוני GPT2 (summary)
            "usage_prompt_tokens_GPT2": safe_int(summary_usage[1]) if summary_usage and len(summary_usage) > 1 else "",
            "usage_completion_tokens_GPT2": safe_int(summary_usage[2]) if summary_usage and len(summary_usage) > 2 else "",
            "usage_total_tokens_GPT2": safe_int(summary_usage[3]) if summary_usage and len(summary_usage) > 3 else "",
            "cached_tokens_gpt2": cached_tokens_gpt2 if cached_tokens_gpt2 > 0 else "",
            "cost_gpt2": cost_gpt2 if cost_gpt2 > 0 else "",
            "model_GPT2": summary_usage[4] if summary_usage and len(summary_usage) > 4 else "",
            
            # נתוני GPT3 (extract)
            "usage_prompt_tokens_GPT3": extract_prompt_tokens,
            "usage_completion_tokens_GPT3": extract_completion_tokens,
            "usage_total_tokens_GPT3": extract_total_tokens,
            "cached_tokens_gpt3": cached_tokens_gpt3 if cached_tokens_gpt3 > 0 else "",
            "cost_gpt3": cost_gpt3 if cost_gpt3 > 0 else "",
            "model_GPT3": extract_model,
            
            # נתוני זמן
            "timestamp": timestamp_full,
            "date_only": date_only,
            "time_only": time_only
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

        # הדפסה מפורטת לבדיקה
        print(f"✅ לוג נרשם בהצלחה:")
        print(f"   📧 message_id: {message_id}")
        print(f"   👤 chat_id: {chat_id}")
        print(f"   📊 טוקנים: prompt={prompt_tokens_total}, completion={completion_tokens_total}, סה\"כ={total_tokens}")
        print(f"   💰 עלויות: GPT1={cost_gpt1}₪, GPT2={cost_gpt2}₪, GPT3={cost_gpt3}₪")
        print(f"   🌐 עלות כוללת: ${clean_cost_usd}")
        
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


