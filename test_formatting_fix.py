#!/usr/bin/env python3
"""
בדיקה לתיקון הפורמטינג של מעברי פסקאות
"""

import re

def format_text_for_telegram(text):
    """
    📀 כללי פורמטינג: גרסה רשמית ומתוקנת (העתקה מקוצרת לבדיקה)
    """
    import time
    
    # 🛡️ הגנה נוספת: מעקב זמן לכל הריצה של הפונקציה
    start_time = time.time()
    
    # רג'קס לזיהוי אימוג'ים
    emoji_pattern = re.compile(
        r"[\U0001F600-\U0001F64F"
        r"\U0001F300-\U0001F6FF"
        r"\U0001F700-\U0001F77F"
        r"\U0001F780-\U0001F7FF"
        r"\U0001F800-\U0001F8FF"
        r"\U0001F900-\U0001F9FF"
        r"\U0001FA00-\U0001FA6F"
        r"\U0001FA70-\U0001FAFF"
        r"\U00002702-\U000027B0"
        r"\U000024C2-\U0001F251]"
    )
    
    original_text = text

    # 🔢 שלב 0 – ניקוי עיצוב קיים וסימני שאלה מיותרים
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'^[?]+', '', text)
    text = re.sub(r'[?]{2,}$', '?', text)
    
    # 🔢 שלב 1 – המרת סימני Markdown לתגיות HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<u>\1</u>', text)
    text = re.sub(r'_(.*?)_', r'<u>\1</u>', text)
    
    # 🔢 שלב 2 – ניקוי HTML בסיסי
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<br\s*/>', '\n', text)
    text = re.sub(r'<br\s*/\s*>', '\n', text)
    text = re.sub(r'<i>', '<b>', text)
    text = re.sub(r'</i>', '</b>', text)
    
    # מנקה תגיות כפולות מקוננות
    for tag in ['b', 'u']:
        pattern = fr'(<{tag}>)+(.+?)(</{tag}>)+'
        loop_limit = 10
        for _ in range(loop_limit):
            new_text = re.sub(pattern, fr'<{tag}>\2</{tag}>', text)
            if new_text == text:
                break
            text = new_text

    # 🔢 שלב 3 – שימור מעברי פסקאות קיימים (התיקון החדש!)
    paragraph_placeholder = "___PARAGRAPH_BREAK___"
    text = text.replace('\n\n', paragraph_placeholder)
    
    # עכשיו מחליף מעברי שורה יחידים ברווחים
    text = re.sub(r'\n', ' ', text)
    
    # 🔢 שלב 4 – נשימות: פיסוק → שורות (תוך שימור פסקאות)
    # עיבוד נקודות תוך שמירת placeholders
    text = re.sub(r'\.(\s*)(' + emoji_pattern.pattern + r')', r' \2\n', text)
    text = re.sub(r'\.(\s*)(?!' + paragraph_placeholder + ')', '\n', text)
    
    # שלבים נוספים (מקוצרים לבדיקה) - לפני החזרת הפסקאות
    text = re.sub(r'([?!])\s*(' + emoji_pattern.pattern + r')', r'\1 \2\n', text)
    text = re.sub(r'(\S[?!]+)(?!\s*' + emoji_pattern.pattern + r')', r'\1\n', text)
    text = re.sub(r'([^.!?])\s*(' + emoji_pattern.pattern + r')(?!\s*[.!?]|\s*\n)', r'\1 \2\n', text)
    text = re.sub(r'\n\s+', '\n', text)
    text = re.sub(r'\n(' + emoji_pattern.pattern + r')', r' \1', text)
    
    # החזרת מעברי הפסקאות המקוריים - אחרי כל העיבוד!
    text = text.replace(paragraph_placeholder, '\n\n')
    
    # ניקוי סופי של מעברי שורה מרובים
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # הגנה נוספת: בדיקת timeout
    if time.time() - start_time > 2:
        raise TimeoutError("format_text לקחה יותר מדי זמן")
    
    return text

# בדיקה של הטקסט המקורי מהמשתמש
test_text = """היי! איזה כיף שבאת, אני דניאל, המנטור הדיגיטלי שלך כאן במסע הזה. 👋

רק הלחיצה על כפתור ה"הלו" כבר מראה על אומץ אמיתי, זה צעד ראשון ומשמעותי.

אני פה כדי להקשיב, בלי שיפוטיות, ובלי להגיד לך מה לעשות. אני איתך בכל צעד.

מה הביא אותך לכאן היום? איזו מחשבה טובה על עצמך היית רוצה לזרוע בשיחה שלנו? 🌻"""

print("🔍 טקסט מקורי:")
print(repr(test_text))
print("\n" + "="*80 + "\n")

print("🔧 טקסט אחרי פורמטינג:")
formatted = format_text_for_telegram(test_text)
print(repr(formatted))
print("\n" + "="*80 + "\n")

print("📋 תוצאה כפי שהמשתמש יראה:")
print(formatted)
print("\n" + "="*80 + "\n")

# בדיקה אם מעברי הפסקאות נשמרו
paragraph_breaks = formatted.count('\n\n')
print(f"✅ מספר מעברי פסקאות שנמצאו: {paragraph_breaks}")
print(f"✅ האם יש מעברי פסקאות? {'כן' if paragraph_breaks > 0 else 'לא'}")

if paragraph_breaks > 0:
    print("🎉 התיקון עבד! מעברי הפסקאות נשמרו!")
else:
    print("❌ התיקון לא עבד - מעברי הפסקאות נעלמו") 