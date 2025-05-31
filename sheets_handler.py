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

def log_to_sheets(message_id, chat_id, user_msg, reply_text, reply_summary, 
                 main_usage, summary_usage, extract_usage, total_tokens, cost_usd, cost_ils):
    """
    שומר את כל נתוני השיחה בגיליון הלוגים.
    לוגיקה: כל שיחה, כל עלות, כל סיכום — הכל מתועד בלוגיים.
    """
    try:
           sheet_log.append_row([
        message_id,      # 1
        chat_id,         # 2
        user_msg,        # 3
        "",              # 4
        reply_text,      # 5
        reply_summary,   # 6
        "", "", "", "", "",   # 7-11: שדות ריקים
        total_tokens,    # 12
        "", "",          # 13-14: שדות ריקים
        "",              # 15: CACHED טוקנים
        cost_usd,        # 16
        cost_ils,        # 17
        main_usage[0],   # 18
        main_usage[1],   # 19
        main_usage[2],   # 20
        main_usage[4],   # 21
        summary_usage[1], # 22
        summary_usage[2], # 23
        summary_usage[3], # 24
        summary_usage[4], # 25
        extract_usage["prompt_tokens"],      # 26
        extract_usage["completion_tokens"],  # 27
        extract_usage["total_tokens"],       # 28
        extract_usage["model"],              # 29
        "", "", "", "",                     # 30-33: ריק
        "",                                 # 34: ריק
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 35 - זה עמודה AI!!!
    ])
        print("✅ נתונים נשמרו בגיליון הלוגים")
        return True
    except Exception as e:
        print(f"❌ שגיאה בשמירה לגיליון: {e}")
        raise

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
