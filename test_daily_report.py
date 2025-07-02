#!/usr/bin/env python3
"""
סקריפט בדיקה לדוח יומי
"""

import os
import sys
import asyncio
from datetime import datetime

# הוספת נתיב לפרויקט
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_prerequisites():
    """בודק את התנאים המקדימים לדוח"""
    print("🔍 בודק תנאים מקדימים...")
    
    # בדיקת תיקיית data
    if not os.path.exists("data"):
        print("❌ תיקיית data לא קיימת")
        return False
    else:
        print("✅ תיקיית data קיימת")
    
    # בדיקת קובץ לוג
    log_file = "data/gpt_usage_log.jsonl"
    if not os.path.exists(log_file):
        print(f"❌ קובץ לוג {log_file} לא קיים")
        return False
    else:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        print(f"✅ קובץ לוג קיים עם {len(lines)} רשומות")
    
    return True

async def test_daily_summary_function():
    """בדיקת הפונקציה send_daily_summary"""
    print("🧪 בודק פונקציית send_daily_summary...")
    
    try:
        # ניסוי לייבא את הפונקציה
        from daily_summary import send_daily_summary, _get_summary_for_date
        print("✅ הפונקציה יובאה בהצלחה")
        
        # בדיקת חישוב הסיכום ללא שליחה
        from datetime import datetime, timedelta
        import pytz
        
        # נסה לטעון pytz או השתמש ב-UTC
        try:
            tz = pytz.timezone("Europe/Berlin")
            today = datetime.now(tz).date()
        except:
            today = datetime.now().date()
            
        yesterday = today - timedelta(days=1)
        
        print(f"🗓️ בודק נתונים לתאריך: {yesterday}")
        summary_data = _get_summary_for_date(yesterday, None)
        
        if summary_data:
            print("✅ נמצאו נתונים לדוח:")
            print(f"   אינטראקציות: {summary_data['total_interactions']}")
            print(f"   עלות כוללת: {summary_data['total_cost_ils']:.2f} ₪")
            print(f"   קריאות API: {summary_data['total_api_calls']}")
        else:
            print("⚠️ לא נמצאו נתונים לתאריך זה")
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת הפונקציה: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_scheduler_integration():
    """בדיקת האינטגרציה עם המתזמן"""
    print("⏰ בודק אינטגרציה עם המתזמן...")
    
    try:
        from bot_setup import setup_admin_reports
        print("✅ פונקציית setup_admin_reports נמצאה")
        
        # בדיקה אם יש imports נכונים
        from apscheduler.schedulers.background import BackgroundScheduler
        print("✅ APScheduler זמין")
        
        return True
    except Exception as e:
        print(f"❌ שגיאה באינטגרציה: {e}")
        return False

async def main():
    print("🚀 מתחיל בדיקת מערכת דוחות יומיים")
    print("=" * 50)
    
    # בדיקות
    checks = [
        ("תנאים מקדימים", check_prerequisites()),
        ("פונקציית דוח יומי", await test_daily_summary_function()),
        ("אינטגרציה עם מתזמן", test_scheduler_integration())
    ]
    
    print("\n" + "=" * 50)
    print("📊 סיכום בדיקות:")
    
    passed = 0
    for name, result in checks:
        status = "✅ עבר" if result else "❌ נכשל"
        print(f"   {name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 תוצאה כוללת: {passed}/{len(checks)} בדיקות עברו")
    
    if passed == len(checks):
        print("🎉 כל הבדיקות עברו! המערכת אמורה לעבוד תקין.")
    else:
        print("⚠️ יש בעיות שצריך לתקן.")

if __name__ == "__main__":
    asyncio.run(main())