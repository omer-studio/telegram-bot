"""
fields_dict.py
--------------
קובץ זה מרכז את כל שמות השדות (fields) של המשתמשים והודעות במקום אחד.
הרציונל: כל שינוי/הוספה/עדכון של שדה יתבצע רק כאן, למניעת פיזור שמות שדות בקוד.
כל שדה מתועד בעברית, כולל label וטיפוס.

FIELDS_DICT - יש להשתמש אך ורק בשמות מה־DICT הזה בכל מקום בקוד, בטבלאות, וב־API!
אין להמציא שמות חדשים או לשנות שמות קיימים ללא עדכון ה־DICT!
כל שינוי/הוספה/עדכון של שדה יתבצע רק כאן.

כל שדה הוא dict עם מפתח 'label' (שם בעברית), 'type' (טיפוס ערך צפוי), 
'show_in_summary' (לתצוגה בסיכום) ו-'show_in_prompt' (טקסט מדויק מהפרומטים).
לדוג' - 'age': {'label': 'גיל', 'type': int, 'show_in_summary': 'בן', 'show_in_prompt': 'גיל (מספר בין 18 ל־99 בלבד)'}
"""

# (בגרסה זו השאלות כבר משולבות ישירות בתוך FIELDS_DICT — אין צורך בבלוק Legacy או בלולאה)

FIELDS_DICT = {
    # --- טבלת משתמשים ---
    "age": {"label": "גיל", "type": int, "show_in_summary": "בן", "show_in_prompt": "גיל (מספר בין 18 ל־99 בלבד)", "missing_question": "בן כמה אתה?"},
    "pronoun_preference": {"label": "לשון פניה (את/אתה/מעורב)", "type": str, "show_in_summary": "לשון פנייה:", "show_in_prompt": "לשון פניה מועדפת", "missing_question": ""},
    "occupation_or_role": {"label": "עיסוק (מה עושה בחיים?)", "type": str, "show_in_summary": "", "show_in_prompt": "עיסוק בפועל (למשל: סטודנט למשפטים, מורה, עובד בהייטק)", "missing_question": "מה אתה עושה בחיים?"},
    "attracted_to": {"label": "משיכה לגברים/נשים/שניהם (ועוד אופציות)", "type": str, "show_in_summary": "משיכה מינית:", "show_in_prompt": "משיכה מינית (למשל: \"נמשך לגברים בלבד\", \"גם לגברים וגם לנשים\")", "missing_question": "נמשך גם לנשים? או רק לגברים?"},
    "relationship_type": {"label": "מצב זוגי / משפחתי (כולל ילדים)", "type": str, "show_in_summary": "", "show_in_prompt": "מצב זוגי / משפחתי (למשל: רווק, גרוש, נשוי לגבר, בזוגיות עם גבר כבר 3 שנים)", "missing_question": "מצב משפחתי (רווק? נשוי? גרוש?)"},
    "parental_status": {"label": "ילדים/נכדים", "type": str, "show_in_summary": "", "show_in_prompt": "ילדים/נכדים (למשל: \"2 ילדים מהנישואים\", \"בעיצומו של תהליך פונדקאות\")", "missing_question": "יש ילדים?"},
    "self_religious_affiliation": {"label": "יהדות/ערבי/דרוזי/נוצרי/אתאיסט וכו'", "type": str, "show_in_summary": "", "show_in_prompt": "זהות דתית או אתנית (יהודי, ערבי, דרוזי, מוסלמי, נוצרי, אתאיסט וכו')", "missing_question": "יהודי? ערבי? נוצרי? וכו..."},
    "self_religiosity_level": {"label": "רמת דתיות", "type": str, "show_in_summary": "", "show_in_prompt": "רמת דתיות (חילוני, דתי, מסורתי, חרדי, לא דתי)", "missing_question": "חילוני? דתי?"},
    "family_religiosity": {"label": "רמת דתיות משפחתית", "type": str, "show_in_summary": "", "show_in_prompt": "הרקע הדתי במשפחה שגדלת בה (חילונית, דתית, חרדית, מסורתית)", "missing_question": "המשפחה שלך - דתית? מסורתית? חילונית?"},
    "closet_status": {"label": "האם בארון / יצא / חלקי", "type": str, "show_in_summary": "", "show_in_prompt": "מצב הארון (למשל: \"כולם יודעים חוץ מהמשפחה\", \"בארון לגמרי\")", "missing_question": "אתה בארון? לא בארון?"},
    "who_knows": {"label": "מי יודע עליו", "type": str, "show_in_summary": "יודעים עליו:", "show_in_prompt": "מי כן יודע עליו (שמות או קבוצות, כמו: אמא, אבא, חברים)", "missing_question": "מי כן יודע עליך?"},
    "who_doesnt_know": {"label": "מי לא יודע עליו", "type": str, "show_in_summary": "לא יודעים עליו:", "show_in_prompt": "מי לא יודע עליו (ציין במפורש, למשל: סבתא, הבוס)", "missing_question": ""},
    "attends_therapy": {"label": "האם הולך לטיפול פסיכולוגי/רגשי/קבוצה כרגע?", "type": str, "show_in_summary": "נמצא בטיפול:", "show_in_prompt": "האם הוא בטיפול רגשי / קבוצתי (למשל: \"מטופל אצל פסיכולוג\", \"חבר בקבוצת גברים\")", "missing_question": "אתה נמצא בטיפול כלשהו?"},
    "primary_conflict": {"label": "הסיפור / קונפליקט המרכזי שלו בחיים כרגע", "type": str, "show_in_summary": "הקונפליקט המרכזי:", "show_in_prompt": "הקונפליקט המרכזי בחייו כרגע", "missing_question": "מה הדבר המרכזי שאתה מתמודד איתו בהקשר של הנטייה המינית?"},
    "trauma_history": {"label": "טראומות אם ציין (תנסח בזהירות ובעדינות ועם הרחבה)", "type": str, "show_in_summary": "טראומות שצויינו:", "show_in_prompt": "טראומות משמעותיות מהעבר (בניסוח עדין וזהיר)", "missing_question": ""},
    "goal_in_course": {"label": "מה הוא רוצה שיקרה לו מהקורס (המטרות ששם לעצמו)", "type": str, "show_in_summary": "מטרות בקורס:", "show_in_prompt": "מה הוא רוצה להשיג כתוצאה מהקורס", "missing_question": "מה המטרות שלך מהקורס כאן?"},
    "language_of_strength": {"label": "משפטים מחזקים שהוא משתמש בהם (מה עוזר לו בזמנים קשים?)", "type": str, "show_in_summary": "משפטים שהוא אומר לעצמו ומחזקים אותו:", "show_in_prompt": "משפטים מחזקים", "missing_question": ""},
    "date_first_seen": {"label": "מתי התחילה השיחה איתו", "type": str, "show_in_summary": "", "show_in_prompt": "תאריך תחילת השיחה", "missing_question": ""},
    "coping_strategies": {"label": "מה מרים אותך? מה עוזר לך להתמודד?", "type": str, "show_in_summary": "מה ציין שעוזר לו להתמודד:", "show_in_prompt": "אסטרטגיות התמודדות", "missing_question": "מה מרים אותך? מה עוזר לך להתמודד?"},
    "fears_concerns": {"label": "פחדים וחששות", "type": str, "show_in_summary": "פחדים:", "show_in_prompt": "פחדים או חששות", "missing_question": "מה הפחד הכי גדול שלך?"},
    "future_vision": {"label": "מה החזון לעתיד", "type": str, "show_in_summary": "חזון לעתיד: ", "show_in_prompt": "איך היה רוצה לראות את עצמו בעתיד", "missing_question": "איך אתה רואה את עצמך בעתיד?"},
    "other_insights": {"label": "מידע אישי נוסף", "type": str, "show_in_summary": "", "show_in_prompt": "מידע אישי נוסף", "missing_question": "מה עוד בא לך לספר על עצמך?"},
    "last_update": {"label": "מתי עודכנה השורה לאחרונה (מתעדכן אוטומטית)", "type": str, "show_in_summary": "", "show_in_prompt": "", "missing_question": ""},
    "summary": {"label": "ת.ז רגשית בסיסית שנשלחת בכל הודעה לgpt כרקע חשוב על המשתתף", "type": str, "show_in_summary": "", "show_in_prompt": "", "missing_question": ""},

    # --- טבלת הודעות ---
    "message_id": {"label": "מזהה הודעה", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "chat_id": {"label": "מזהה משתמש", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "user_msg": {"label": "הודעת המשתמש", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "user_summary": {"label": "תמצות הודעת המשתמש", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "bot_reply": {"label": "תשובת הבוט", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "bot_summary": {"label": "סיכום תשובת הבוט", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "total_tokens": {"label": "סך כל הטוקנים", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "prompt_tokens_total": {"label": "סך טוקנים בפרומט", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "completion_tokens_total": {"label": "סך טוקנים בתשובה", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cached_tokens": {"label": "טוקנים במטמון", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "total_cost_usd": {"label": "עלות סופית בדולר", "type": float, "show_in_summary": "", "show_in_prompt": ""},
    "total_cost_ils": {"label": "עלות סופית באגורות", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_prompt_tokens_gpt_a": {"label": "טוקנים פרומט - gpt ראשי", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_completion_tokens_gpt_a": {"label": "טוקנים תשובה - gpt ראשי", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_total_tokens_gpt_a": {"label": "סך טוקנים - gpt ראשי", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cached_tokens_gpt_a": {"label": "כמה מתוכם זה קשד", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cost_gpt_a": {"label": "כמה עלתה הקריאה באגורות", "type": float, "show_in_summary": "", "show_in_prompt": ""},
    "model_gpt_a": {"label": "מודל gpt ראשי", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "usage_prompt_tokens_gpt_b": {"label": "טוקנים פרומט - gpt מקצר", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_completion_tokens_gpt_b": {"label": "טוקנים תשובה - gpt מקצר", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_total_tokens_gpt_b": {"label": "סך טוקנים - gpt מקצר", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cached_tokens_gpt_b": {"label": "כמה מתוכם קשד", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cost_gpt_b": {"label": "כמה עלה באגורות", "type": float, "show_in_summary": "", "show_in_prompt": ""},
    "model_gpt_b": {"label": "מודל gpt מקצר", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "usage_prompt_tokens_gpt_c": {"label": "טוקנים פרומט - gpt מחלץ משופר", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_completion_tokens_gpt_c": {"label": "טוקנים תשובה - gpt מחלץ משופר", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_total_tokens_gpt_c": {"label": "סך טוקנים - gpt מחלץ משופר", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cached_tokens_gpt_c": {"label": "כמה מתוכם קשד", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cost_gpt_c": {"label": "כמה עלה באגורות", "type": float, "show_in_summary": "", "show_in_prompt": ""},
    "model_gpt_c": {"label": "מודל gpt מחלץ משופר", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "usage_prompt_tokens_gpt_d": {"label": "טוקנים פרומט - gpt_d", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_completion_tokens_gpt_d": {"label": "טוקנים תשובה - gpt_d", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_total_tokens_gpt_d": {"label": "סך טוקנים - gpt_d", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cached_tokens_gpt_d": {"label": "כמה מתוכם קשד - gpt_d", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cost_gpt_d": {"label": "כמה עלה באגורות - gpt_d", "type": float, "show_in_summary": "", "show_in_prompt": ""},
    "model_gpt_d": {"label": "מודל gpt_d", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "usage_prompt_tokens_gpt_e": {"label": "טוקנים פרומט - gpt_e", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_completion_tokens_gpt_e": {"label": "טוקנים תשובה - gpt_e", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "usage_total_tokens_gpt_e": {"label": "סך טוקנים - gpt_e", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cached_tokens_gpt_e": {"label": "כמה מתוכם קשד - gpt_e", "type": int, "show_in_summary": "", "show_in_prompt": ""},
    "cost_gpt_e": {"label": "כמה עלה באגורות - gpt_e", "type": float, "show_in_summary": "", "show_in_prompt": ""},
    "model_gpt_e": {"label": "מודל gpt_e", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "timestamp": {"label": "טיימסטפ של ההודעה", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "date_only": {"label": "תאריך בלבד של ההודעה", "type": str, "show_in_summary": "", "show_in_prompt": ""},
    "time_only": {"label": "שעה בלבד של ההודעה", "type": str, "show_in_summary": "", "show_in_prompt": ""}
} 

# פונקציות נוחות לגישה לשדות
def get_user_profile_fields():
    """מחזיר רשימה של שדות פרופיל משתמש בלבד"""
    user_fields = [
        "age", "pronoun_preference", "occupation_or_role", "attracted_to", "relationship_type", 
        "parental_status", "self_religious_affiliation", "self_religiosity_level", "family_religiosity", 
        "closet_status", "who_knows", "who_doesnt_know", "attends_therapy", "primary_conflict", 
        "trauma_history", "goal_in_course", "language_of_strength", "date_first_seen", 
        "coping_strategies", "fears_concerns", "future_vision", "other_insights", "last_update", "summary"
    ]
    return [field for field in user_fields if field in FIELDS_DICT]

def get_summary_fields():
    """מחזיר רשימה של שדות לסיכום רגשי"""
    summary_fields = [
        "age", "pronoun_preference", "occupation_or_role", "attracted_to", "relationship_type",
        "self_religious_affiliation", "self_religiosity_level", "family_religiosity", "closet_status",
        "who_knows", "who_doesnt_know", "attends_therapy", "primary_conflict", "trauma_history",
        "goal_in_course", "language_of_strength", "date_first_seen", "coping_strategies",
        "fears_concerns", "future_vision"
        # ✅ הוסר last_update - זה שדה טכני שלא צריך להיות בסיכום
    ]
    return [field for field in summary_fields if field in FIELDS_DICT]

def get_fields_with_prompt_text():
    """מחזיר רשימה של שדות שיש להם טקסט לפרומט"""
    return [field for field, info in FIELDS_DICT.items() if info.get("show_in_prompt", "").strip()]

def get_field_prompt_text(field_name):
    """מחזיר את הטקסט של שדה לשימוש בפרומט"""
    return FIELDS_DICT.get(field_name, {}).get("show_in_prompt", "") 