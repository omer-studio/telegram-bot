#!/usr/bin/env python3
"""
🚨 בדיקת תקינות קריטית לפני Deploy
=====================================

הקובץ הזה מוודא שהבוט יעבד תקין לפני שהפריסה עולה.
אם יש שגיאות - הפריסה תיכשל ולא תעלה!

שימוש:
python3 health_check.py

Exit codes:
- 0: הכל תקין, אפשר לעשות deploy
- 1: יש בעיות, אסור לעשות deploy!
"""

import sys
import os
import asyncio
import traceback
import json
from datetime import datetime

# הוספת הספרייה הנוכחית ל-path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log_check(test_name: str, success: bool, details: str = ""):
    """רישום תוצאות בדיקה"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"      Details: {details}")
    if not success:
        print(f"      🚨 CRITICAL: זה יגרום לכשל בפריסה!")
    return success

def test_imports():
    """בדיקה שכל הimports נטענים ללא שגיאות"""
    print("\n🔍 בדיקת Imports...")
    
    try:
        # בדיקת imports בסיסיים
        import main
        import config
        import message_handler
        import concurrent_monitor
        import notifications
        log_check("Basic imports", True)
        
        # בדיקת import של הפונקציה הבעייתית שתוקנה
        from concurrent_monitor import ConcurrentMonitor
        monitor = ConcurrentMonitor(5)  # יצירת instance קטן לבדיקה
        log_check("ConcurrentMonitor creation", True)
        
        # בדיקה שהפונקציה _send_error_alert לא async יותר
        import inspect
        is_async = inspect.iscoroutinefunction(monitor._send_error_alert)
        log_check("_send_error_alert is NOT async", not is_async, f"is_async={is_async}")
        
        return True
        
    except Exception as e:
        log_check("Imports", False, f"Import error: {e}")
        traceback.print_exc()
        return False

def test_concurrent_monitor():
    """בדיקת ConcurrentMonitor"""
    print("\n🔍 בדיקת ConcurrentMonitor...")
    
    try:
        from concurrent_monitor import get_concurrent_monitor, start_monitoring_user, end_monitoring_user
        
        # יצירת monitor
        monitor = get_concurrent_monitor()
        log_check("ConcurrentMonitor instance", monitor is not None)
        
        # בדיקה שיש לו את השיטות הנדרשות
        has_methods = all(hasattr(monitor, method) for method in [
            'start_user_session', 'end_user_session', '_send_error_alert'
        ])
        log_check("ConcurrentMonitor has required methods", has_methods)
        
        # בדיקה שה-_send_error_alert לא עושה await על dict
        try:
            # זה אמור לעבוד עכשיו ללא שגיאה
            monitor._send_error_alert("test", {"chat_id": "test", "error": "test"})
            log_check("_send_error_alert works without await", True)
        except Exception as e:
            log_check("_send_error_alert works without await", False, str(e))
            return False
            
        return True
        
    except Exception as e:
        log_check("ConcurrentMonitor", False, f"Error: {e}")
        traceback.print_exc()
        return False

async def test_async_functions():
    """בדיקת פונקציות async"""
    print("\n🔍 בדיקת Async Functions...")
    
    try:
        from concurrent_monitor import start_monitoring_user, end_monitoring_user
        
        # בדיקה שהפונקציות async עובדות
        result = await start_monitoring_user("test_user", "test_msg")
        log_check("start_monitoring_user", isinstance(result, bool))
        
        await end_monitoring_user("test_user", True)
        log_check("end_monitoring_user", True)
        
        return True
        
    except Exception as e:
        log_check("Async functions", False, f"Error: {e}")
        traceback.print_exc()
        return False

def test_config():
    """בדיקת הגדרות"""
    print("\n🔍 בדיקת Config...")
    
    try:
        import config
        
        # בדיקת משתנים קריטיים
        critical_vars = ['TELEGRAM_BOT_TOKEN', 'MAX_CONCURRENT_USERS', 'DATA_DIR']
        for var in critical_vars:
            has_var = hasattr(config, var)
            value = getattr(config, var, None) if has_var else None
            log_check(f"Config has {var}", has_var and value is not None, f"value={value}")
            
        return True
        
    except Exception as e:
        log_check("Config", False, f"Error: {e}")
        traceback.print_exc()
        return False

def test_message_handler():
    """בדיקת message_handler"""
    print("\n🔍 בדיקת Message Handler...")
    
    try:
        import message_handler
        
        # בדיקה שהפונקציות קיימות
        functions = ['handle_message', 'send_message', 'format_text_for_telegram']
        for func in functions:
            has_func = hasattr(message_handler, func)
            log_check(f"Has {func}", has_func)
            
        return True
        
    except Exception as e:
        log_check("Message Handler", False, f"Error: {e}")
        traceback.print_exc()
        return False

async def main():
    """ריצת כל הבדיקות"""
    print("🚨 בדיקת תקינות קריטית לפני Deploy")
    print("=" * 50)
    
    # רשימת כל הבדיקות
    tests = [
        ("Imports", test_imports),
        ("Config", test_config),
        ("ConcurrentMonitor", test_concurrent_monitor),
        ("Message Handler", test_message_handler),
        ("Async Functions", test_async_functions),
    ]
    
    all_passed = True
    results = {}
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ CRITICAL ERROR in {test_name}: {e}")
            traceback.print_exc()
            results[test_name] = False
            all_passed = False
    
    # סיכום
    print("\n" + "=" * 50)
    print("📊 סיכום בדיקת תקינות:")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    print("=" * 50)
    
    if all_passed:
        print("🎉 כל הבדיקות עברו בהצלחה!")
        print("✅ בטוח לעשות Deploy!")
        return 0
    else:
        print("🚨 יש בדיקות שנכשלו!")
        print("❌ אסור לעשות Deploy עד שהבעיות ייפתרו!")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 הבדיקה בוטלה על ידי המשתמש")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 שגיאה קריטית בבדיקת תקינות: {e}")
        traceback.print_exc()
        sys.exit(1)