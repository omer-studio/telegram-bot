#!/usr/bin/env python3
"""
סקריפט מקיף לבדיקת כל המפתחות
"""

import os
import sys
import json

def check_all_keys():
    """בדיקת כל המפתחות במערכת"""
    print("🔍 בדיקת כל המפתחות במערכת")
    print("=" * 50)
    
    # הגדרת מפתחות לפי עדיפות
    critical_keys = {
        "TELEGRAM_BOT_TOKEN": {
            "name": "🤖 Telegram Bot Token",
            "required": True,
            "description": "מפתח לחיבור לטלגרם",
            "how_to_get": "BotFather בטלגרם → /newbot"
        },
        "OPENAI_API_KEY": {
            "name": "🧠 OpenAI API Key", 
            "required": True,
            "description": "מפתח לחיבור ל-OpenAI GPT",
            "how_to_get": "platform.openai.com → API Keys"
        },
        "DATABASE_URL": {
            "name": "🗄️ Database URL",
            "required": True,
            "description": "כתובת מסד נתונים",
            "how_to_get": "Render/Railway → PostgreSQL Database"
        }
    }
    
    optional_keys = {
        "ADMIN_BOT_TELEGRAM_TOKEN": {
            "name": "🔔 Admin Bot Token",
            "required": False,
            "description": "בוט נפרד להתראות (אופציונלי)",
            "how_to_get": "BotFather בטלגרם או השתמש באותו טוקן"
        },
        "GEMINI_API_KEY": {
            "name": "🤖 Gemini API Key",
            "required": False,
            "description": "מפתח ל-Google Gemini AI",
            "how_to_get": "makersuite.google.com → API key"
        },
        "DATABASE_EXTERNAL_URL": {
            "name": "🌐 External Database URL",
            "required": False,
            "description": "כתובת חיצונית למסד נתונים",
            "how_to_get": "בדרך כלל זהה ל-DATABASE_URL"
        },
        "RENDER_API_KEY": {
            "name": "🚀 Render API Key",
            "required": False,
            "description": "מפתח לניהול שרת Render",
            "how_to_get": "dashboard.render.com → API Keys"
        },
        "RENDER_SERVICE_ID": {
            "name": "🏗️ Render Service ID",
            "required": False,
            "description": "זיהוי השירות ב-Render",
            "how_to_get": "מה-URL של השירות ב-Render"
        }
    }
    
    try:
        # טעינת קונפיגורציה
        sys.path.append('/workspace')
        from config import config
        
        print("✅ קובץ התצורה נטען בהצלחה\n")
        
        # בדיקת מפתחות קריטיים
        print("🚨 מפתחות קריטיים (חובה!):")
        print("-" * 30)
        critical_missing = []
        
        for key, info in critical_keys.items():
            value = config.get(key, '')
            if not value or 'YOUR_' in str(value) or 'HERE' in str(value):
                print(f"❌ {info['name']}: חסר")
                print(f"   📝 {info['description']}")
                print(f"   🔗 איך משיגים: {info['how_to_get']}")
                critical_missing.append(key)
            else:
                masked = str(value)[:10] + '...' if len(str(value)) > 10 else str(value)
                print(f"✅ {info['name']}: {masked}")
            print()
        
        # בדיקת מפתחות אופציונליים
        print("\n🔧 מפתחות אופציונליים:")
        print("-" * 30)
        optional_missing = []
        
        for key, info in optional_keys.items():
            value = config.get(key, '')
            if not value or 'YOUR_' in str(value) or 'HERE' in str(value):
                print(f"⚠️  {info['name']}: חסר")
                print(f"   📝 {info['description']}")
                print(f"   🔗 איך משיגים: {info['how_to_get']}")
                optional_missing.append(key)
            else:
                masked = str(value)[:10] + '...' if len(str(value)) > 10 else str(value)
                print(f"✅ {info['name']}: {masked}")
            print()
        
        # סיכום
        print("\n📊 סיכום:")
        print("=" * 20)
        print(f"🚨 מפתחות קריטיים חסרים: {len(critical_missing)}")
        print(f"⚠️  מפתחות אופציונליים חסרים: {len(optional_missing)}")
        
        if critical_missing:
            print(f"\n🔥 דחוף! הבוט לא יעבוד בלי:")
            for key in critical_missing:
                print(f"   - {key}")
        
        # הוראות הבא
        print("\n🚀 הצעד הבא:")
        if critical_missing:
            print("1. השג את המפתחות הקריטיים החסרים")
            print("2. ערוך את /workspace/etc/secrets/config.json")
            print("3. הרץ שוב: python3 check_all_keys.py")
            print("4. כשהכל מוכן: python3 main.py")
        else:
            print("✅ כל המפתחות הקריטיים קיימים!")
            print("🎯 ניתן להריץ את הבוט: python3 main.py")
            
        return len(critical_missing) == 0
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת המפתחות: {e}")
        return False

def show_config_template():
    """הצגת תבנית לקובץ התצורה"""
    print("\n📝 תבנית לקובץ config.json:")
    print("=" * 30)
    
    template = {
        "TELEGRAM_BOT_TOKEN": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
        "OPENAI_API_KEY": "sk-proj-1234567890abcdefghijklmnop",
        "DATABASE_URL": "postgresql://user:pass@host:5432/dbname",
        "ADMIN_BOT_TELEGRAM_TOKEN": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
        "GEMINI_API_KEY": "AIzaSy1234567890abcdefghijklmnop",
        "DATABASE_EXTERNAL_URL": "postgresql://user:pass@host:5432/dbname",
        "RENDER_API_KEY": "rnd_1234567890abcdefghijklmnop",
        "RENDER_SERVICE_ID": "srv-1234567890abcdefghijklmnop"
    }
    
    print(json.dumps(template, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    print("🔑 בדיקת מפתחות מערכת הבוט")
    print("=" * 50)
    
    success = check_all_keys()
    
    if not success:
        print("\n" + "=" * 50)
        show_config_template()
        print("\n📚 למידע מפורט: עיין במדריך_מפתחות_מלא.md")
    else:
        print("\n🎉 כל המפתחות הקריטיים מוכנים!")
        print("🚀 הבוט מוכן לפעולה!")