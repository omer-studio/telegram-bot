#!/usr/bin/env python3
"""
quick_user_check.py
==================
בדיקה מהירה של סטטוס אישור משתמש ספציפי

🚀 איך להריץ:
python quick_user_check.py [chat_id]
"""

import sys
import json
from datetime import datetime

# הוספת הנתיב הנוכחי
sys.path.append('.')

def check_user_status(chat_id):
    """בדיקה מהירה של סטטוס משתמש - 🗑️ עברנו למסד נתונים"""
    try:
        # 🗑️ יבוא ממסד נתונים במקום Google Sheets
        from db_manager import check_user_approved_status_db
        from profile_utils import clear_user_cache_profile, get_user_profile_fast
        
        print(f"🔍 בודק סטטוס משתמש {chat_id} במסד נתונים...")
        
        # ניקוי cache (אם יש)
        print("🔨 מנקה cache...")
        try:
            clear_result = clear_user_cache_profile(chat_id)
            cleared_count = clear_result.get("cleared_count", 0) if isinstance(clear_result, dict) else 0
            print(f"   נוקו {cleared_count} cache keys")
        except Exception as cache_err:
            print(f"   ⚠️ לא ניתן לנקות cache: {cache_err}")
            cleared_count = 0
        
        # בדיקת סטטוס במסד נתונים
        print("📊 בודק סטטוס במסד נתונים...")
        access_result = check_user_approved_status_db(chat_id)
        
        # בדיקת פרופיל משתמש
        print("👤 בודק פרופיל משתמש...")
        user_profile = get_user_profile_fast(chat_id)
        
        # הצגת התוצאות
        print("\n" + "="*50)
        print(f"📋 תוצאות בדיקה למשתמש {chat_id}")
        print("="*50)
        
        if isinstance(access_result, dict):
            status = access_result.get("status", "unknown")
            approved = access_result.get("approved", False)
        else:
            status = "error"
            approved = False
        
        print(f"🔍 סטטוס: {status}")
        print(f"✅ מאושר: {approved}")
        
        # פרשנות
        if status == "found" and approved:
            print("✅ המשתמש מאושר - אמור לקבל גישה מלאה")
        elif status == "found" and not approved:
            print("⏳ המשתמש לא אישר תנאים - יקבל בקשת אישור")
        elif status == "not_found":
            print("❌ המשתמש לא נמצא - יקבל בקשת קוד")
        else:
            print(f"⚠️ סטטוס: {status}")
        
        # הצגת פרופיל
        if user_profile:
            print(f"\n👤 פרופיל משתמש:")
            print(f"   שם: {user_profile.get('name', 'לא צוין')}")
            print(f"   סיכום: {user_profile.get('summary', 'אין')[:100]}...")
            print(f"   הודעות GPT-C: {user_profile.get('gpt_c_run_count', 0)}")
        else:
            print("\n�� אין פרופיל משתמש")
        
        # בדיקת נתונים גולמיים
        print("\n🔍 נתונים גולמיים:")
        print(f"   access_result = {access_result}")
        
        # שמירת תוצאות
        result = {
            "chat_id": chat_id,
            "check_timestamp": datetime.now().isoformat(),
            "access_result": access_result,
            "user_profile": user_profile,
            "cache_cleared": cleared_count,
            "source": "database"  # מציין שהנתונים מהמסד
        }
        
        with open(f"user_check_{chat_id}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 תוצאות נשמרו בקובץ: user_check_{chat_id}.json")
        
        return access_result
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת משתמש: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """פונקציה ראשית"""
    if len(sys.argv) < 2:
        print("❌ חסר chat_id")
        print("📋 שימוש: python quick_user_check.py [chat_id]")
        print("📋 דוגמה: python quick_user_check.py 5676571979")
        return
    
    chat_id = sys.argv[1]
    
    print("🚀 בדיקה מהירה של סטטוס משתמש (מסד נתונים)")
    print("="*50)
    
    result = check_user_status(chat_id)
    
    if result:
        print("\n✅ בדיקה הושלמה")
    else:
        print("\n❌ בדיקה נכשלה")

if __name__ == "__main__":
    main() 