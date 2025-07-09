#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
טסט אוטומטי לפונקציית הפורמטינג
מונע רגרסיות עתידיות
"""

import unittest
import sys
import os

# 🛡️ תיקון encoding לWindows
import locale
try:
    if sys.platform.startswith('win'):
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        # Set console encoding for Windows
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
except:
    pass  # אם זה נכשל, נמשיך בלי encoding fix

# הוספת נתיב לimport
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 🛡️ Import בטוח שלא תלוי בconfig מורכב
try:
    from message_handler import format_text_for_telegram
except ImportError as e:
    print(f"⚠️ Warning: Could not import format_text_for_telegram: {e}")
    # יצירת mock function לטסטים
    def format_text_for_telegram(text):
        return str(text or "").strip() + '\n' if text else ""

class TestFormatting(unittest.TestCase):
    """בדיקות אוטומטיות לפורמטינג"""
    
    def test_punctuation_with_emoji(self):
        """בדיקת פיסוק + אימוג'י - המקרה הבעייתי המקורי"""
        # הקלט הבעייתי שתיקנו
        input_text = "הבנת נכון! 😊"
        expected = "הבנת נכון! 😊\n"
        result = format_text_for_telegram(input_text)
        self.assertEqual(result, expected, "האימוג'י חייב להישאר עם הפיסוק")
    
    def test_question_with_emoji(self):
        """בדיקת שאלה + אימוג'י"""
        input_text = "מה שלומך? 🤔"
        expected = "מה שלומך? 🤔\n"
        result = format_text_for_telegram(input_text)
        self.assertEqual(result, expected)
    
    def test_period_with_emoji(self):
        """בדיקת נקודה + אימוג'י (נקודה נמחקת)"""
        input_text = "זה נכון. 👍"
        expected = "זה נכון 👍\n"
        result = format_text_for_telegram(input_text)
        self.assertEqual(result, expected, "נקודה + אימוג'י: נקודה נמחקת")
    
    def test_punctuation_without_emoji(self):
        """בדיקת פיסוק בלי אימוג'י"""
        input_text = "איך אתה? מה שלומך!"
        expected = "איך אתה?\nמה שלומך!\n"
        result = format_text_for_telegram(input_text)
        self.assertEqual(result, expected)
    
    def test_period_without_emoji(self):
        """בדיקת נקודה בלי אימוג'י (נמחקת)"""
        input_text = "זה נכון. זה טוב."
        expected = "זה נכון\nזה טוב\n"
        result = format_text_for_telegram(input_text)
        self.assertEqual(result, expected, "נקודות חייבות להיעלם")
    
    def test_markdown_formatting(self):
        """בדיקת Markdown"""
        input_text = "**בולד** ו*קו תחתון*"
        expected = "<b>בולד</b> ו<u>קו תחתון</u>\n"
        result = format_text_for_telegram(input_text)
        self.assertEqual(result, expected)
    
    def test_mixed_complex_case(self):
        """בדיקת מקרה מורכב - מעורב"""
        input_text = "מעולה! 😊 זה נכון. איך אתה?"
        expected = "מעולה! 😊\nזה נכון\nאיך אתה?\n"
        result = format_text_for_telegram(input_text)
        self.assertEqual(result, expected)
    
    def test_empty_and_edge_cases(self):
        """בדיקת מקרים קיצוניים"""
        # טקסט ריק
        self.assertEqual(format_text_for_telegram(""), "")
        
        # רק אימוג'י
        self.assertEqual(format_text_for_telegram("😊"), "😊\n")
        
        # רק פיסוק
        self.assertEqual(format_text_for_telegram("!"), "!\n")
        
        # נקודה בלבד (נמחקת - לא נשאר כלום)
        self.assertEqual(format_text_for_telegram("."), "")

if __name__ == '__main__':
    # 🛡️ הגדרות בטוחות לטסטים
    try:
        unittest.main(verbosity=2)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1) 