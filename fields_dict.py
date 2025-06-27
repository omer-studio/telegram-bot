"""
fields_dict.py
--------------
קובץ זה מרכז את כל שמות השדות (fields) של המשתמשים והודעות במקום אחד.
הרציונל: כל שינוי/הוספה/עדכון של שדה יתבצע רק כאן, למניעת פיזור שמות שדות בקוד.
כל שדה מתועד בעברית, כולל label וטיפוס.

FIELDS_DICT - יש להשתמש אך ורק בשמות מה־DICT הזה בכל מקום בקוד, בטבלאות, וב־API!
אין להמציא שמות חדשים או לשנות שמות קיימים ללא עדכון ה־DICT!
כל שינוי/הוספה/עדכון של שדה יתבצע רק כאן.

כל שדה הוא dict עם מפתח 'label' (שם בעברית) ו-'type' (טיפוס ערך צפוי).
לדוג' - 'age': {'label': 'גיל', 'type': int}
"""

FIELDS_DICT = {
    # --- טבלת משתמשים ---
    "age": {"label": "גיל", "type": int, "show_in_summary": "בן"},
    "pronoun_preference": {"label": "לשון פניה (את/אתה/מעורב)", "type": str, "show_in_summary": "לשון פנייה:"},
    "occupation_or_role": {"label": "עיסוק (מה עושה בחיים?)", "type": str, "show_in_summary": ""},
    "attracted_to": {"label": "משיכה לגברים/נשים/שניהם (ועוד אופציות)", "type": str, "show_in_summary": "משיכה מינית:"},
    "relationship_type": {"label": "מצב זוגי / משפחתי (כולל ילדים)", "type": str, "show_in_summary": ""},
    "self_religious_affiliation": {"label": "יהדות/ערבי/דרוזי/נוצרי/אתאיסט וכו'", "type": str, "show_in_summary": ""},
    "self_religiosity_level": {"label": "רמת דתיות", "type": str, "show_in_summary": ""},
    "family_religiosity": {"label": "רמת דתיות משפחתית", "type": str, "show_in_summary": ""},
    "closet_status": {"label": "האם בארון / יצא / חלקי", "type": str, "show_in_summary": ""},
    "who_knows": {"label": "מי יודע עליו", "type": str, "show_in_summary": "יודעים עליו:"},
    "who_doesnt_know": {"label": "מי לא יודע עליו", "type": str, "show_in_summary": "לא יודעים עליו:"},
    "attends_therapy": {"label": "האם הולך לטיפול פסיכולוגי/רגשי/קבוצה כרגע?", "type": str, "show_in_summary": "נמצא בטיפול:"},
    "primary_conflict": {"label": "הסיפור / קונפליקט המרכזי שלו בחיים כרגע", "type": str, "show_in_summary": ""},
    "trauma_history": {"label": "טראומות אם ציין (תנסח בזהירות ובעדינות ועם הרחבה)", "type": str, "show_in_summary": "טראומות שצויינו:"},
    "goal_in_course": {"label": "מה הוא רוצה שיקרה לו מהקורס (המטרות ששם לעצמו)", "type": str, "show_in_summary": "מטרות בקורס:"},
    "language_of_strength": {"label": "משפטים מחזקים שהוא משתמש בהם (מה עוזר לו בזמנים קשים?)", "type": str, "show_in_summary": "משפטים שהוא אומר לעצמו ומחזקים אותו:"},
    "date_first_seen": {"label": "מתי התחילה השיחה איתו", "type": str, "show_in_summary": ""},
    "coping_strategies": {"label": "מה מרים אותך? מה עוזר לך להתמודד?", "type": str, "show_in_summary": "מה ציין שעוזר לו להתמודד:"},
    "fears_concerns": {"label": "פחדים וחששות", "type": str, "show_in_summary": "פחדים:"},
    "future_vision": {"label": "מה החזון לעתיד", "type": str, "show_in_summary": "חזון לעתיד: "},
    "last_update": {"label": "מתי עודכנה השורה לאחרונה (מתעדכן אוטומטית)", "type": str, "show_in_summary": ""},
    "summary": {"label": "ת.ז רגשית בסיסית שנשלחת בכל הודעה לgpt כרקע חשוב על המשתתף", "type": str, "show_in_summary": ""},

    # --- טבלת הודעות ---
    "message_id": {"label": "מזהה הודעה", "type": str},
    "chat_id": {"label": "מזהה משתמש", "type": str},
    "user_msg": {"label": "הודעת המשתמש", "type": str},
    "user_summary": {"label": "תמצות הודעת המשתמש", "type": str},
    "bot_reply": {"label": "תשובת הבוט", "type": str},
    "bot_summary": {"label": "סיכום תשובת הבוט", "type": str},
    "total_tokens": {"label": "סך כל הטוקנים", "type": int},
    "prompt_tokens_total": {"label": "סך טוקנים בפרומט", "type": int},
    "completion_tokens_total": {"label": "סך טוקנים בתשובה", "type": int},
    "cached_tokens": {"label": "טוקנים במטמון", "type": int},
    "total_cost_usd": {"label": "עלות סופית בדולר", "type": float},
    "total_cost_ils": {"label": "עלות סופית באגורות", "type": int},
    "usage_prompt_tokens_gpt_a": {"label": "טוקנים פרומט - gpt ראשי", "type": int},
    "usage_completion_tokens_gpt_a": {"label": "טוקנים תשובה - gpt ראשי", "type": int},
    "usage_total_tokens_gpt_a": {"label": "סך טוקנים - gpt ראשי", "type": int},
    "cached_tokens_gpt_a": {"label": "כמה מתוכם זה קשד", "type": int},
    "cost_gpt_a": {"label": "כמה עלתה הקריאה באגורות", "type": float},
    "model_gpt_a": {"label": "מודל gpt ראשי", "type": str},
    "usage_prompt_tokens_gpt_b": {"label": "טוקנים פרומט - gpt מקצר", "type": int},
    "usage_completion_tokens_gpt_b": {"label": "טוקנים תשובה - gpt מקצר", "type": int},
    "usage_total_tokens_gpt_b": {"label": "סך טוקנים - gpt מקצר", "type": int},
    "cached_tokens_gpt_b": {"label": "כמה מתוכם קשד", "type": int},
    "cost_gpt_b": {"label": "כמה עלה באגורות", "type": float},
    "model_gpt_b": {"label": "מודל gpt מקצר", "type": str},
    "usage_prompt_tokens_gpt_c": {"label": "טוקנים פרומט - gpt מחלץ משופר", "type": int},
    "usage_completion_tokens_gpt_c": {"label": "טוקנים תשובה - gpt מחלץ משופר", "type": int},
    "usage_total_tokens_gpt_c": {"label": "סך טוקנים - gpt מחלץ משופר", "type": int},
    "cached_tokens_gpt_c": {"label": "כמה מתוכם קשד", "type": int},
    "cost_gpt_c": {"label": "כמה עלה באגורות", "type": float},
    "model_gpt_c": {"label": "מודל gpt מחלץ משופר", "type": str},
    "usage_prompt_tokens_gpt_d": {"label": "טוקנים פרומט - gpt_d", "type": int},
    "usage_completion_tokens_gpt_d": {"label": "טוקנים תשובה - gpt_d", "type": int},
    "usage_total_tokens_gpt_d": {"label": "סך טוקנים - gpt_d", "type": int},
    "cached_tokens_gpt_d": {"label": "כמה מתוכם קשד - gpt_d", "type": int},
    "cost_gpt_d": {"label": "כמה עלה באגורות - gpt_d", "type": float},
    "model_gpt_d": {"label": "מודל gpt_d", "type": str},
    "usage_prompt_tokens_gpt_e": {"label": "טוקנים פרומט - gpt_e", "type": int},
    "usage_completion_tokens_gpt_e": {"label": "טוקנים תשובה - gpt_e", "type": int},
    "usage_total_tokens_gpt_e": {"label": "סך טוקנים - gpt_e", "type": int},
    "cached_tokens_gpt_e": {"label": "כמה מתוכם קשד - gpt_e", "type": int},
    "cost_gpt_e": {"label": "כמה עלה באגורות - gpt_e", "type": float},
    "model_gpt_e": {"label": "מודל gpt_e", "type": str},
    "timestamp": {"label": "טיימסטפ של ההודעה", "type": str},
    "date_only": {"label": "תאריך בלבד של ההודעה", "type": str},
    "time_only": {"label": "שעה בלבד של ההודעה", "type": str}
} 