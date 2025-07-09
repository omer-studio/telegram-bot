#!/usr/bin/env python3

import re

def debug_format_text_for_telegram(text):
    """דיבאג צעד אחר צעד עם placeholders מתוקנים"""
    print(f"🚀 מתחיל: {text!r}")
    
    # שלב 1: ניקוי HTML
    text = re.sub(r'<[^>]+>', '', text)
    print(f"אחרי HTML: {text!r}")
    
    # שלב 2: Markdown 
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<u>\1</u>', text)
    text = re.sub(r'_(.*?)_', r'<u>\1</u>', text)
    print(f"אחרי Markdown: {text!r}")
    
    # שלב 3: פתרון עם placeholders מתוקנים!
    
    # 1. שמירת נקודה + אימוג'י ב-placeholder (מוחק נקודה)
    old_text = text
    text = re.sub(r'\.(\s*)([\U0001F600-\U0001F64F\U0001F300-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251])', r'<EMOJI_DOT>\2</EMOJI_DOT>', text)
    if text != old_text:
        print(f"אחרי נקודה+אימוג'י → placeholder: {text!r}")
    
    # 2. שמירת שאלה/קריאה + אימוג'י ב-placeholder (כולל הפיסוק!)
    old_text = text
    text = re.sub(r'([?!])(\s*)([\U0001F600-\U0001F64F\U0001F300-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251])', r'<EMOJI_PUNCT>\1 \3</EMOJI_PUNCT>', text)
    if text != old_text:
        print(f"אחרי שאלה/קריאה+אימוג'י → placeholder: {text!r}")
    
    # 3. כל נקודה שנשארה → מעבר שורה (מוחק נקודה)
    old_text = text
    text = re.sub(r'\.(\s*)', '\n', text)
    if text != old_text:
        print(f"אחרי נקודה רגילה: {text!r}")
    
    # 4. כל שאלה/קריאה שנשארה (לא כוללת placeholders!) → פיסוק + מעבר שורה
    old_text = text
    # שימוש ב-negative lookahead כדי לא לגעת בplaceholders
    text = re.sub(r'([?!])(\s*)(?!.*</EMOJI_PUNCT>)', r'\1\n', text)
    if text != old_text:
        print(f"אחרי שאלה/קריאה רגילה: {text!r}")
    
    # 5. החזרת placeholders למעברי שורה
    old_text = text
    text = re.sub(r'<EMOJI_DOT>(.*?)</EMOJI_DOT>', r' \1\n', text, flags=re.DOTALL)
    if text != old_text:
        print(f"אחרי החזרת נקודה+אימוג'י: {text!r}")
    
    old_text = text
    text = re.sub(r'<EMOJI_PUNCT>(.*?)</EMOJI_PUNCT>', r'\1\n', text, flags=re.DOTALL)
    if text != old_text:
        print(f"אחרי החזרת שאלה/קריאה+אימוג'י: {text!r}")
    
    # ניקוי בסיסי - אבל לא מסיר \n מהסוף
    text = re.sub(r'\n\s+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    # וידוא שיש \n בסוף (אלא אם הטקסט ריק)
    if text and not text.endswith('\n'):
        text += '\n'
    
    print(f"✅ תוצאה סופית: {text!r}")
    return text

# בדיקת המקרה הבעייתי
if __name__ == "__main__":
    print("🔍 דיבאג צעד אחר צעד:")
    print("=" * 60)
    
    test_case = "הבנת נכון! 😊"
    result = debug_format_text_for_telegram(test_case)
    
    print("\n" + "=" * 60)
    print(f"🎯 מצפה: 'הבנת נכון! 😊\\n'")
    print(f"🎯 קיבלתי: {result!r}")
    
    if result == "הבנת נכון! 😊\n":
        print("✅ SUCCESS!")
    else:
        print("❌ FAIL!")
        
    print("\n🔍 בדיקת מקרה פשוט:")
    simple_test = "זה נכון."
    simple_result = debug_format_text_for_telegram(simple_test)
    print(f"🎯 מצפה: 'זה נכון\\n'")
    print(f"🎯 קיבלתי: {simple_result!r}")
    
    if simple_result == "זה נכון\n":
        print("✅ SUCCESS!")
    else:
        print("❌ FAIL!") 