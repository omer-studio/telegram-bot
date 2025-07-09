#!/usr/bin/env python3

import re

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

def debug_format_text_for_telegram(text):
    """דיבאג של הפורמטינג צעד אחר צעד"""
    print(f"🚀 מתחיל פורמטינג: {text!r}")
    
    # שלב 1: ניקוי HTML קיים
    text = re.sub(r'<[^>]+>', '', text)
    print(f"אחרי ניקוי HTML: {text!r}")
    
    # שלב 2: המרת Markdown לHTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<u>\1</u>', text)
    text = re.sub(r'_(.*?)_', r'<u>\1</u>', text)
    print(f"אחרי Markdown: {text!r}")
    
    # שלב 3: רג'קסים לפיסוק + אימוג'י
    print(f"\n🔧 מתחיל רג'קסים:")
    
    # אם יש נקודה + אימוג'י
    old_text = text
    text = re.sub(r'\.(\s*)(' + emoji_pattern.pattern + r')(\s*)', r' \2\n', text)
    if text != old_text:
        print(f"אחרי נקודה+אימוג'י: {text!r}")
    
    # אם יש שאלה/קריאה + אימוג'י  
    old_text = text
    text = re.sub(r'([?!])(\s+)(' + emoji_pattern.pattern + r')', r'\1 \3\n', text)
    if text != old_text:
        print(f"אחרי שאלה/קריאה+אימוג'י: {text!r}")
    
    # כל נקודה ללא אימוג'י
    old_text = text
    text = re.sub(r'\.(\s*)(?!' + emoji_pattern.pattern + r')', '\n', text)
    if text != old_text:
        print(f"אחרי נקודה ללא אימוג'י: {text!r}")
    
    # כל שאלה/קריאה ללא אימוג'י
    old_text = text
    text = re.sub(r'([?!])(\s*)(?!' + emoji_pattern.pattern + r')', r'\1\n', text)
    if text != old_text:
        print(f"אחרי שאלה/קריאה ללא אימוג'י: {text!r}")
    
    # ניקויים
    text = re.sub(r'\n\s+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    print(f"✅ תוצאה סופית: {text!r}")
    return text

# בדיקה
text = "הבנת נכון! 😊"
result = debug_format_text_for_telegram(text)
print(f"\n📋 תצוגה: {result}") 