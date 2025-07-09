#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
טסט פשוט וישיר לפונקציית הפורמטינג - ללא תלויות מורכבות
"""

import re

# 🎨 Constants - העתקה ישירה מהפונקציה המקורית
EMOJI_PATTERN = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]'

def simple_format_text_for_telegram(text):
    """
    📝 פונקציה פשוטה לטסט - העתקה ישירה של הלוגיקה הבסיסית
    """
    if not text:
        return ""
    
    # שלב 1: ניקוי HTML בסיסי
    text = re.sub(r'<[^>]+>', '', text)
    
    # שלב 2: Markdown → HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<u>\1</u>', text)
    text = re.sub(r'_(.*?)_', r'<u>\1</u>', text)
    
    # שלב 3: פיסוק ואימוג'ים
    
    # כלל 1: נקודה + אימוג'י → מוחק נקודה, שומר אימוג'י + מעבר שורה  
    text = re.sub(fr'\.(\s*)({EMOJI_PATTERN})', r' \2\n', text)
    
    # כלל 2: שאלה/קריאה + אימוג'י → שומר הכל + מעבר שורה
    text = re.sub(fr'([?!])(\s*)({EMOJI_PATTERN})', r'\1 \3\n', text)
    
    # כלל 3: נקודה בלבד → מוחק + מעבר שורה
    text = re.sub(r'\.(\s*)', r'\n', text)
    
    # כלל 4: שאלה/קריאה בלבד (בלי אימוג'י) → מעבר שורה
    text = re.sub(fr'([?!])(\s*)(?!.*{EMOJI_PATTERN})', r'\1\n', text)
    
    # ניקוי סופי
    text = re.sub(r'\n\s+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    # וידוא מעבר שורה בסוף (אלא אם ריק)
    if text and not text.endswith('\n'):
        text += '\n'
    
    return text

def test_all_cases():
    """בדיקה פשוטה של כל המקרים"""
    print("🧪 בדיקות פורמטינג פשוטות:")
    print("=" * 50)
    
    test_cases = [
        # (input, expected, description)
        ("הבנת נכון! 😊", "הבנת נכון! 😊\n", "קריאה + אימוג'י"),
        ("מה שלומך? 🤔", "מה שלומך? 🤔\n", "שאלה + אימוג'י"),
        ("זה נכון. 👍", "זה נכון 👍\n", "נקודה + אימוג'י (נקודה נמחקת)"),
        ("איך אתה? מה שלומך!", "איך אתה?\nמה שלומך!\n", "פיסוק בלי אימוג'י"),
        ("זה נכון. זה טוב.", "זה נכון\nזה טוב\n", "נקודות נמחקות"),
        ("**בולד** ו*קו תחתון*", "<b>בולד</b> ו<u>קו תחתון</u>\n", "Markdown"),
        ("מעולה! 😊 זה נכון. איך אתה?", "מעולה! 😊\nזה נכון\nאיך אתה?\n", "מקרה מורכב"),
        ("", "", "טקסט ריק"),
        ("😊", "😊\n", "רק אימוג'י"),
        ("!", "!\n", "רק פיסוק"),
        (".", "", "נקודה בלבד - נמחקת"),
    ]
    
    success_count = 0
    total_tests = len(test_cases)
    
    for i, (input_text, expected, description) in enumerate(test_cases, 1):
        result = simple_format_text_for_telegram(input_text)
        success = result == expected
        status = "✅" if success else "❌"
        
        print(f"{status} Test {i:2}: {description}")
        print(f"   Input:    {input_text!r}")
        print(f"   Expected: {expected!r}")
        print(f"   Got:      {result!r}")
        
        if success:
            success_count += 1
        print()
    
    print(f"📊 תוצאות: {success_count}/{total_tests} הצליחו")
    return success_count == total_tests

if __name__ == '__main__':
    try:
        success = test_all_cases()
        if success:
            print("🎉 כל הטסטים עברו!")
            exit(0)
        else:
            print("❌ יש טסטים שנכשלו!")
            exit(1)
    except Exception as e:
        print(f"💥 שגיאה בטסטים: {e}")
        exit(1) 