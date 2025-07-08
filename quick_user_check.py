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
    """בדיקה מהירה של סטטוס משתמש"""
    try:
        # יבוא מודולים
        from config import setup_google_sheets
        # 🗑️ עברנו למסד נתונים - אין צורך ב-Google Sheets!
# from sheets_core import check_user_access, force_clear_user_cache
from db_manager import check_user_approved_status_db
from profile_utils import clear_user_cache_profile
        
        print(f"🔍 בודק סטטוס משתמש {chat_id}...")
        
        # חיבור לגיליון
        gs_client, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        # ניקוי cache
        print("🔨 מנקה cache...")
        cleared_count = force_clear_user_cache(chat_id)
        print(f"   נוקו {cleared_count} cache keys")
        
        # בדיקת סטטוס
        print("📊 בודק סטטוס...")
        access_result = check_user_access(sheet_users, chat_id)
        
        # הצגת התוצאות
        print("\n" + "="*50)
        print(f"📋 תוצאות בדיקה למשתמש {chat_id}")
        print("="*50)
        
        status = access_result.get("status", "unknown")
        code = access_result.get("code", "N/A")
        
        print(f"🔍 סטטוס: {status}")
        print(f"🔢 קוד: {code}")
        
        # פרשנות
        if status == "approved":
            print("✅ המשתמש מאושר - אמור לקבל גישה מלאה")
        elif status == "pending":
            print("⏳ המשתמש לא אישר תנאים - יקבל בקשת אישור")
        elif status == "not_found":
            print("❌ המשתמש לא נמצא - יקבל בקשת קוד")
        elif status == "error":
            print("🚨 שגיאה בבדיקת הסטטוס")
        else:
            print(f"⚠️ סטטוס לא מוכר: {status}")
        
        # בדיקת נתונים גולמיים
        print("\n🔍 נתונים גולמיים:")
        print(f"   access_result = {access_result}")
        
        # שמירת תוצאות
        result = {
            "chat_id": chat_id,
            "check_timestamp": datetime.now().isoformat(),
            "access_result": access_result,
            "cache_cleared": cleared_count
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
    
    print("🚀 בדיקה מהירה של סטטוס משתמש")
    print("="*50)
    
    result = check_user_status(chat_id)
    
    if result:
        print("\n✅ בדיקה הושלמה")
    else:
        print("\n❌ בדיקה נכשלה")

if __name__ == "__main__":
    main() 