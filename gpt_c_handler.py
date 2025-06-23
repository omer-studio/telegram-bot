"""
gpt_c_handler.py
----------------
מנוע gpt_c: חילוץ פרופיל nano (profile extraction nano)
"""

import logging
import litellm
from prompts import PROFILE_EXTRACTION_ENHANCED_PROMPT

def gpt_c(user_message, last_bot_message="", chat_id=None, message_id=None):
    """
    מפעיל את gpt_c (nano) לחילוץ פרופיל רגשי מהודעת משתמש.
    """
    try:
        metadata = {"gpt_identifier": "gpt_c", "chat_id": chat_id, "message_id": message_id}
        if last_bot_message:
            user_content = f"שאלת הבוט לצורך הקשר בלבד:\n{last_bot_message}\n\nתשובת המשתמש לצורך חילוץ מידע:\n{user_message}"
        else:
            user_content = f"תשובת המשתמש לצורך חילוץ מידע:\n{user_message}"
        response = litellm.completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROFILE_EXTRACTION_ENHANCED_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3,
            max_tokens=500,
            metadata=metadata,
            store=True
        )
        content = response.choices[0].message.content.strip()
        usage = response.usage.__dict__ if hasattr(response.usage, "__dict__") else {}
        return {"content": content, "usage": usage, "model": response.model}
    except Exception as e:
        logging.error(f"[gpt_c] Error: {e}")
        return {"content": "[שגיאה בחילוץ]", "usage": {}, "model": "gpt-4o-mini"}

def should_run_gpt_c(user_message):
    """
    בודק אם יש טעם להפעיל gpt_c על הודעה נתונה.
    מחזיר False רק על הודעות שאנחנו בטוחים שלא מכילות מידע חדש.
    הכלל: gpt_c מופעל תמיד, אלא אם כן ההודעה היא משהו שלא יכול להכיל מידע חדש.
    """
    if not user_message or not user_message.strip():
        return False
    message = user_message.strip()
    # ביטויים בסיסיים שלא יכולים להכיל מידע חדש
    base_phrases = [
        'היי', 'שלום', 'מה שלומך', 'מה נשמע', 'מה קורה', 'מה המצב',
        'תודה', 'תודה רבה', 'תודה לך', 'תודה מאוד', 'תודה ענקית', 'תודהה',
        'בסדר', 'אוקיי', 'אוקי', 'בסדר גמור', 'בסדר מושלם', 'אוקייי',
        'אני מבין', 'אה', 'וואו', 'מעניין', 'נכון', 'אכן', 'אה אה',
        'כן', 'לא', 'אולי', 'יכול להיות', 'אפשרי',
        'אני לא יודע', 'לא יודע', 'לא בטוח', 'לא יודע מה להגיד', 'אין לי מושג',
        'בהחלט', 'בטח', 'כמובן', 'ברור', 'ודאי', 'בוודאי',
        'מעולה', 'נהדר', 'מדהים', 'פנטסטי', 'מושלם',
        'אה אוקיי', 'אה בסדר', 'אה הבנתי', 'אה נכון',
        'כן לא', 'כן אולי', 'אולי כן', 'אולי לא',
        'אה אוקיי תודה', 'אה בסדר תודה', 'אה הבנתי תודה',
        'טוב', 'טוב מאוד', 'טוב מאד', 'לא רע', 'לא רע בכלל',
        'בסדר גמור', 'בסדר מושלם', 'בסדר לגמרי', 'בסדר לחלוטין',
        'מצוין', 'מצויין', 'מעולה', 'נהדר', 'מדהים', 'פנטסטי',
        'אני בסדר', 'אני טוב', 'אני מצוין', 'אני מעולה',
        'הכל טוב', 'הכל בסדר', 'הכל מצוין', 'הכל מעולה',
        'סבבה', 'סבבה גמורה', 'סבבה מושלמת',
        'קול', 'קול לגמרי', 'קול לחלוטין',
        'אחלה', 'אחלה גמורה', 'אחלה מושלמת',
        'יופי', 'יופי גמור', 'יופי מושלם',
        'מעולה', 'מעולה גמורה', 'מעולה מושלמת',
        'נהדר', 'נהדר לגמרי', 'נהדר לחלוטין',
        'מדהים', 'מדהים לגמרי', 'מדהים לחלוטין',
        'פנטסטי', 'פנטסטי לגמרי', 'פנטסטי לחלוטין',
        'מושלם', 'מושלם לגמרי', 'מושלם לחלוטין',
        'אני אוקיי', 'אני בסדר גמור', 'אני בסדר מושלם',
        'אני טוב מאוד', 'אני טוב מאד', 'אני טוב לגמרי',
        'אני מצוין לגמרי', 'אני מעולה לגמרי', 'אני נהדר לגמרי',
        'אני מדהים לגמרי', 'אני פנטסטי לגמרי', 'אני מושלם לגמרי',
        'טוב אחי', 'בסדר אחי', 'מעולה אחי', 'נהדר אחי', 'מדהים אחי',
        'סבבה אחי', 'קול אחי', 'אחלה אחי', 'יופי אחי', 'מושלם אחי',
        'אני בסדר אחי', 'אני טוב אחי', 'אני מעולה אחי', 'אני נהדר אחי',
        'הכל טוב אחי', 'הכל בסדר אחי', 'הכל מעולה אחי',
        'אחי', 'אח', 'אחיי', 'אחייי', 'אחיייי',
        'אחי טוב', 'אחי בסדר', 'אחי מעולה', 'אחי נהדר', 'אחי מדהים',
        'אחי סבבה', 'אחי קול', 'אחי אחלה', 'אחי יופי', 'אחי מושלם'
    ]
    # אימוג'י בלבד
    emoji_only = ['👍', '👎', '❤️', '😊', '😢', '😡', '🤔', '😅', '😂', '😭']
    # נקודות בלבד
    dots_only = ['...', '....', '.....', '......']
    # סימני קריאה בלבד
    exclamation_only = ['!!!', '!!!!', '!!!!!']
    # בדיקה אם ההודעה היא בדיוק ביטוי בסיסי
    message_lower = message.lower()
    for phrase in base_phrases:
        if message_lower == phrase.lower():
            return False
    # בדיקה אם ההודעה היא ביטוי בסיסי + תווים נוספים
    for phrase in base_phrases:
        phrase_lower = phrase.lower()
        # בדיקה אם ההודעה מתחילה בביטוי הבסיסי
        if message_lower.startswith(phrase_lower):
            # מה שנשאר אחרי הביטוי הבסיסי
            remaining = message_lower[len(phrase_lower):].strip()
            # אם מה שנשאר הוא רק תווים מותרים, אז לא להפעיל gpt_c
            if remaining in ['', '!', '?', ':)', ':(', '!:)', '?:(', '!:(', '?:)', '...', '....', '.....', '......', '!!!', '!!!!', '!!!!!']:
                return False
            # אם מה שנשאר הוא רק אימוג'י או שילוב של תווים מותרים
            import re
            # הסרת רווחים מהתחלה ומהסוף
            remaining_clean = remaining.strip()
            # בדיקה אם מה שנשאר הוא רק תווים מותרים
            allowed_chars = r'^[!?:\.\s\(\)]+$'
            if re.match(allowed_chars, remaining_clean):
                return False
    # בדיקה אם ההודעה היא רק אימוג'י
    if message in emoji_only:
        return False
    # בדיקה אם ההודעה היא רק נקודות
    if message in dots_only:
        return False
    # בדיקה אם ההודעה היא רק סימני קריאה
    if message in exclamation_only:
        return False
    # בדיקה אם ההודעה היא ביטוי + אימוג'י
    for phrase in base_phrases:
        phrase_lower = phrase.lower()
        if message_lower.startswith(phrase_lower):
            remaining = message_lower[len(phrase_lower):].strip()
            # בדיקה אם מה שנשאר הוא רק אימוג'י
            if remaining in ['👍', '👎', '❤️', '😊', '😢', '😡', '🤔', '😅', '😂', '😭']:
                return False
    # אם הגענו לכאן, ההודעה יכולה להכיל מידע חדש
    return True 