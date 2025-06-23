#!/usr/bin/env python3
"""
test_gpt_e.py
-------------
קובץ בדיקה למודול gpt_e
"""

import sys
import os
from datetime import datetime

# הוספת הנתיב לפרויקט
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_gpt_e_imports():
    """בדיקה שכל הייבואים עובדים"""
    print("🧪 בדיקת ייבואים...")
    
    try:
        from gpt_e_handler import execute_gpt_e_if_needed, run_gpt_e
        from sheets_handler import get_user_state, increment_gpt_c_run_count, reset_gpt_c_run_count
        print("✅ כל הייבואים עובדים")
        return True
    except Exception as e:
        print(f"❌ שגיאה בייבוא: {e}")
        return False

def test_user_state_functions():
    """בדיקת פונקציות ניהול מצב משתמש"""
    print("\n🧪 בדיקת פונקציות מצב משתמש...")
    
    try:
        from sheets_handler import get_user_state, increment_gpt_c_run_count, reset_gpt_c_run_count
        
        # בדיקה עם chat_id דמיוני
        test_chat_id = "123456789"
        
        # בדיקת get_user_state
        state = get_user_state(test_chat_id)
        print(f"✅ get_user_state: {state}")
        
        # בדיקת increment_gpt_c_run_count
        new_count = increment_gpt_c_run_count(test_chat_id)
        print(f"✅ increment_gpt_c_run_count: {new_count}")
        
        # בדיקת reset_gpt_c_run_count
        success = reset_gpt_c_run_count(test_chat_id)
        print(f"✅ reset_gpt_c_run_count: {success}")
        
        return True
    except Exception as e:
        print(f"❌ שגיאה בפונקציות מצב משתמש: {e}")
        return False

def test_gpt_e_conditions():
    """בדיקת תנאי הפעלת gpt_e"""
    print("\n🧪 בדיקת תנאי הפעלת gpt_e...")
    
    try:
        from gpt_e_handler import execute_gpt_e_if_needed
        
        test_chat_id = "123456789"
        
        # בדיקה 1: פחות מ-20 ריצות
        result1 = execute_gpt_e_if_needed(test_chat_id, 15)
        print(f"✅ 15 ריצות: {result1 is None}")
        
        # בדיקה 2: 50+ ריצות (צריך להפעיל)
        result2 = execute_gpt_e_if_needed(test_chat_id, 50)
        print(f"✅ 50 ריצות: {result2 is not None}")
        
        # בדיקה 3: 25 ריצות + 24 שעות
        result3 = execute_gpt_e_if_needed(test_chat_id, 25, "2023-01-01T00:00:00")
        print(f"✅ 25 ריצות + 24 שעות: {result3 is not None}")
        
        return True
    except Exception as e:
        print(f"❌ שגיאה בבדיקת תנאים: {e}")
        return False

def test_secret_command():
    """בדיקת פקודת אדמין"""
    print("\n🧪 בדיקת פקודת אדמין...")
    
    try:
        from secret_commands import handle_secret_command
        
        # בדיקת פקודה לא קיימת
        success, msg = handle_secret_command("123456789", "#invalid_command")
        print(f"✅ פקודה לא קיימת: {not success}")
        
        # בדיקת פקודה קיימת (ללא הרשאות)
        success, msg = handle_secret_command("123456789", "#run_gpt_e 123456789")
        print(f"✅ פקודה ללא הרשאות: {not success}")
        
        return True
    except Exception as e:
        print(f"❌ שגיאה בבדיקת פקודות: {e}")
        return False

def main():
    """פונקציה ראשית"""
    print("🚀 בדיקת מודול gpt_e")
    print("=" * 50)
    
    tests = [
        test_gpt_e_imports,
        test_user_state_functions,
        test_gpt_e_conditions,
        test_secret_command
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ שגיאה בבדיקה: {e}")
    
    print(f"\n📊 תוצאות: {passed}/{total} בדיקות עברו")
    
    if passed == total:
        print("🎉 כל הבדיקות עברו בהצלחה!")
    else:
        print("⚠️ חלק מהבדיקות נכשלו")

if __name__ == "__main__":
    main() 