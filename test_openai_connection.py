#!/usr/bin/env python3
"""
סקריפט בדיקה לחיבור OpenAI
"""

import os
import sys

def test_openai_connection():
    """בדיקת חיבור OpenAI לאחר תיקון התצורה"""
    print("🔍 בודק הגדרות OpenAI...")
    
    try:
        # בדיקת טעינת קונפיגורציה
        from config import OPENAI_API_KEY
        print("✅ קובץ התצורה נטען בהצלחה")
        
        # בדיקת מפתח API
        if OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_OPENAI_API_KEY_HERE":
            print(f"✅ מפתח OpenAI API מוגדר: {OPENAI_API_KEY[:10]}...")
            
            # הגדרת משתנה סביבה
            os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY
            
            # בדיקת חיבור
            try:
                import lazy_litellm as litellm
                print("🔄 מבצע בדיקת חיבור...")
                
                response = litellm.completion(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=5,
                    temperature=0
                )
                
                if response and hasattr(response, 'choices'):
                    print("✅ חיבור OpenAI תקין!")
                    print(f"📝 תשובה: {response.choices[0].message.content}")
                    return True
                else:
                    print("❌ חיבור OpenAI נכשל - אין תשובה תקינה")
                    return False
                    
            except Exception as e:
                print(f"❌ חיבור OpenAI נכשל: {e}")
                return False
                
        else:
            print("❌ מפתח OpenAI API לא מוגדר כראוי")
            print("📝 ערוך את הקובץ /workspace/etc/secrets/config.json")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה בטעינת התצורה: {e}")
        return False

def run_health_check():
    """הרצת בדיקת תקינות מלאה"""
    print("\n🏥 מריץ בדיקת תקינות מלאה...")
    
    try:
        from chat_utils import health_check
        health = health_check()
        
        print("\n📊 תוצאות בדיקת תקינות:")
        for key, value in health.items():
            status = "✅" if value else "❌"
            print(f"  {status} {key}: {value}")
        
        if health.get('openai_connected', False):
            print("\n🎉 בעיית חיבור OpenAI נפתרה!")
            return True
        else:
            print("\n⚠️ בעיית חיבור OpenAI עדיין קיימת")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה בבדיקת תקינות: {e}")
        return False

if __name__ == "__main__":
    print("🚀 בדיקת חיבור OpenAI")
    print("=" * 40)
    
    # בדיקת חיבור בסיסית
    connection_ok = test_openai_connection()
    
    # בדיקת תקינות מלאה
    health_ok = run_health_check()
    
    print("\n📋 סיכום:")
    if connection_ok and health_ok:
        print("✅ כל הבדיקות עברו בהצלחה!")
        print("🎯 הבוט מוכן לפעולה")
    else:
        print("❌ יש בעיות שדורשות תיקון")
        print("📚 עיין במסמך: פתרון_שגיאת_openai.md")