"""
מחלקת נתונים - כל פונקציות Google Sheets

# לוגיקת רישום משתמש חדש (חשוב!):
1. בכל הודעה נכנסת, קודם כל מחפשים את ה-chat_id בעמודה 1 של גיליון 1 ("access_codes").
2. אם נמצא – המשתמש כבר רשום והקוד כבר הוצמד, ממשיכים כרגיל.
3. אם לא נמצא – בודקים אם ה-chat_id קיים בעמודה 1 של גיליון user_states.
4. אם נמצא – המשתמש התחיל תהליך רישום אבל עדיין לא אישר קוד/תנאים, ממשיכים בתהליך.
5. אם לא נמצא גם שם – זה פנייה ראשונה אי פעם של המשתמש:
     - מוסיפים שורה חדשה לגיליון user_states – עמודה A: chat_id, עמודה B: code_try (תמיד 0).
     - מכאן ממשיכים בתהליך onboarding.
# This logic ensures new users are registered to user_states only on their first-ever interaction.
"""
from config import setup_google_sheets, SUMMARY_FIELD

# יצירת חיבור לגיליונות
sheet_users, sheet_log, sheet_states = setup_google_sheets()

def find_chat_id_in_sheet(sheet, chat_id, col=1):
    """
    מחפש chat_id בעמודה הנתונה (ברירת מחדל: עמודה 1) בגיליון.
    """
    try:
        values = sheet.col_values(col)
        for v in values[1:]:  # דילוג על כותרת
            if str(v).strip() == str(chat_id).strip():
                return True
        return False
    except Exception as e:
        print(f"שגיאה בחיפוש chat_id בגיליון: {e}")
        return False

def ensure_user_state_row(sheet_users, sheet_states, chat_id):
    """
    מממש את הלוגיקה: רושם משתמש חדש ב-user_states רק אם לא קיים באף גיליון.
    מחזיר True אם נוצרה שורה חדשה, False אם כבר קיים.
    """
    # 1. בדיקה בגיליון 1 (access_codes) – עמודה 1
    if find_chat_id_in_sheet(sheet_users, chat_id, col=1):
        return False  # כבר רשום במערכת (לא פנייה ראשונה)
    # 2. בדיקה ב-user_states – עמודה 1
    if find_chat_id_in_sheet(sheet_states, chat_id, col=1):
        return False  # התחיל תהליך רישום קודם
    # 3. לא נמצא – פנייה ראשונה: יצירת שורה חדשה
    try:
        sheet_states.append_row([str(chat_id), 0])  # code_try=0 בפנייה ראשונה
        print(f"✅ נרשם chat_id {chat_id} ל-user_states (פנייה ראשונה, code_try=0)")
        return True
    except Exception as e:
        print(f"שגיאה ביצירת שורה חדשה ב-user_states: {e}")
        return False

def get_user_summary(chat_id):
    """
    מחזיר את הסיכום של המשתמש מגיליון המשתמשים
    """
    try:
        all_records = sheet_users.get_all_records()
        
        for row in all_records:
            if str(row.get("chat_id")) == str(chat_id):
                summary = row.get("summery", "").strip()
                if summary:
                    return summary
        return ""
    except Exception as e:
        print(f"❌ שגיאה בקריאת סיכום משתמש: {e}")
        return ""

def update_user_profile(chat_id, field_values):
    """
    מעדכן פרופיל משתמש בגיליון המשתמשים
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
    יוצר סיכום רגשי מפרטי המשתמש
    """
    parts = []

    # גיל - תמיד ראשו
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

def log_to_sheets(message_id, chat_id, user_msg, reply_text, reply_summary, 
                 main_usage, summary_usage, extract_usage, total_tokens, cost_usd, cost_ils):
    """
    שומר את כל הנתונים בגיליון הלוגים
    """
    try:
        sheet_log.append_row([
            message_id,                       # A: MASSAGE ID
            chat_id,                          # B: CHAT ID  
            user_msg,                         # C: משתמש כתב
            "",                              # D: תימצות משתמש (ריק)
            reply_text,                       # E: בוט ענה
            reply_summary,                    # F: בוט תימצת
            "", "", "", "", "",               # G-K: שדות ריקים
            total_tokens,                     # L: סהכ טוקנים
            "", "",                           # M-N: ריקות
            "",                              # O: CACHED טוקנים
            cost_usd,                         # P: עלות בדולר
            cost_ils,                         # Q: עלות בשקל
            main_usage[0],                    # R: GPT ראשי - prompt tokens
            main_usage[1],                    # S: GPT ראשי - completion tokens  
            main_usage[2],                    # T: GPT ראשי - total tokens
            main_usage[4],                    # U: GPT ראשי - מודל
            summary_usage[1],                 # V: GPT מקצר - prompt tokens
            summary_usage[2],                 # W: GPT מקצר - completion tokens
            summary_usage[3],                 # X: GPT מקצר - total tokens  
            summary_usage[4],                 # Y: GPT מקצר - מודל
            extract_usage["prompt_tokens"],   # Z: GPT מחלץ - prompt tokens
            extract_usage["completion_tokens"], # AA: GPT מחלץ - completion tokens
            extract_usage["total_tokens"],    # AB: GPT מחלץ - total tokens
            extract_usage["model"],           # AC: GPT מחלץ - מודל
            "", "", "", "",                   # AD-AG: ריק
            "", "", "", "", ""                # AH-AK: ריק נוסף
        ])
        print("✅ נתונים נשמרו בגיליון הלוגים")
        return True
    except Exception as e:
        print(f"❌ שגיאה בשמירה לגיליון: {e}")
        raise

def check_user_access(sheet, chat_id):
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
    try:
        codes = sheet.col_values(1)  # עמודה A = access_code
        for i, code in enumerate(codes, start=2):  # שורה 2 ומעלה
            existing_id = sheet.cell(i, 3).value  # עמודה C = chat_id
            if code.strip() == code_input.strip() and (existing_id is None or existing_id == ""):
                sheet.update_cell(i, 3, str(chat_id))  # מכניס את ה-chat_id לעמודה C
                return True
        return False
    except Exception as e:
        print(f"שגיאה ברישום קוד גישה: {e}")
        return False

def approve_user(sheet, chat_id):
    """מסמן בטבלה שהמשתמש אישר תנאים"""
    try:
        cell = sheet.find(str(chat_id))
        if cell:
            header_cell = sheet.find("approved")  # עמודת "אישר תנאים?"
            if header_cell:
                sheet.update_cell(cell.row, header_cell.col, "TRUE")
                return True
        return False
    except Exception as e:
        print(f"❌ approve_user error: {e}")
        return False
