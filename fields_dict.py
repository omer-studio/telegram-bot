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
    "age": {"label": "גיל", "type": int},
    "pronoun_preference": {"label": "לשון פניה (את/אתה/מעורב)", "type": str},
    "occupation_or_role": {"label": "עיסוק (מה עושה בחיים?)", "type": str},
    "attracted_to": {"label": "משיכה לגברים/נשים/שניהם (ועוד אופציות)", "type": str},
    "relationship_type": {"label": "מצב זוגי / משפחתי (כולל ילדים)", "type": str},
    "self_religious_affiliation": {"label": "יהדות/ערבי/דרוזי/נוצרי/אתאיסט וכו'", "type": str},
    "self_religiosity_level": {"label": "רמת דתיות", "type": str},
    "family_religiosity": {"label": "רמת דתיות משפחתית", "type": str},
    "closet_status": {"label": "האם בארון / יצא / חלקי", "type": str},
    "who_knows": {"label": "מי יודע עליו", "type": str},
    "who_doesnt_know": {"label": "מי לא יודע עליו", "type": str},
    "attends_therapy": {"label": "האם הולך לטיפול פסיכולוגי/רגשי/קבוצה כרגע?", "type": str},
    "primary_conflict": {"label": "הסיפור / קונפליקט המרכזי שלו בחיים כרגע", "type": str},
    "trauma_history": {"label": "טראומות אם ציין (להתנסח בזהירות ובעדינות ועם הרחבה)", "type": str},
    "goal_in_course": {"label": "מה הוא רוצה שיקרה לו מהקורס (המטרות ששם לעצמו)", "type": str},
    "language_of_strength": {"label": "משפטים מחזקים שהוא משתמש בהם (מה עוזר לו בזמנים קשים?)", "type": str},
    "date_first_seen": {"label": "מתי התחילה השיחה איתו", "type": str},
    "coping_strategies": {"label": "מה מרים אותך? מה עוזר לך להתמודד?", "type": str},
    "fears_concerns": {"label": "פחדים וחששות", "type": str},
    "future_vision": {"label": "מה החזון לעתיד", "type": str},
    "last_update": {"label": "מתי עודכנה השורה לאחרונה (מתעדכן אוטומטית)", "type": str},
    "summary": {"label": "ת.ז רגשית בסיסית שנשלחת בכל הודעה לGPT כרקע חשוב על המשתתף", "type": str},

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
    "usage_prompt_tokens_GPT1": {"label": "טוקנים פרומט - GPT ראשי", "type": int},
    "usage_completion_tokens_GPT1": {"label": "טוקנים תשובה - GPT ראשי", "type": int},
    "usage_total_tokens_GPT1": {"label": "סך טוקנים - GPT ראשי", "type": int},
    "cached_tokens_gpt1": {"label": "כמה מתוכם זה קשד", "type": int},
    "cost_gpt1": {"label": "כמה עלתה הקריאה באגורות", "type": float},
    "model_GPT1": {"label": "מודל GPT ראשי", "type": str},
    "usage_prompt_tokens_GPT2": {"label": "טוקנים פרומט - GPT מקצר", "type": int},
    "usage_completion_tokens_GPT2": {"label": "טוקנים תשובה - GPT מקצר", "type": int},
    "usage_total_tokens_GPT2": {"label": "סך טוקנים - GPT מקצר", "type": int},
    "cached_tokens_gpt2": {"label": "כמה מתוכם קשד", "type": int},
    "cost_gpt2": {"label": "כמה עלה באגורות", "type": float},
    "model_GPT2": {"label": "מודל GPT מקצר", "type": str},
    "usage_prompt_tokens_GPT3": {"label": "טוקנים פרומט - GPT מחלץ", "type": int},
    "usage_completion_tokens_GPT3": {"label": "טוקנים תשובה - GPT מחלץ", "type": int},
    "usage_total_tokens_GPT3": {"label": "סך טוקנים - GPT מחלץ", "type": int},
    "cached_tokens_gpt3": {"label": "כמה מתוכם קשד", "type": int},
    "cost_gpt3": {"label": "כמה עלה באגורות", "type": float},
    "model_GPT3": {"label": "מודל GPT מחלץ", "type": str},
    "usage_prompt_tokens_GPT4": {"label": "טוקנים פרומט - GPT מיזוג חכם ת.ז רגשית", "type": int},
    "usage_completion_tokens_GPT4": {"label": "טוקנים תשובה - GPT מיזוג חכם ת.ז רגשית", "type": int},
    "usage_total_tokens_GPT4": {"label": "סך טוקנים - GPT מיזוג חכם ת.ז רגשית", "type": int},
    "cached_tokens_GPT4": {"label": "כמה מתוכם קשד", "type": int},
    "cost_GPT4": {"label": "כמה עלה באגורות", "type": float},
    "model_GPT4": {"label": "מודל GPT מיזוג חכם ת.ז רגשית", "type": str},
    "fields_updated_by_4gpt": {"label": "איזה פריטים חדשים נשמרו מGPT 3  או 4", "type": str},
    "timestamp": {"label": "טיימסטפ של ההודעה", "type": str},
    "date_only": {"label": "תאריך בלבד של ההודעה", "type": str},
    "time_only": {"label": "שעה בלבד של ההודעה", "type": str}
} 