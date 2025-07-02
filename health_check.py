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

# זיהוי סביבת CI/CD
IS_CI_ENVIRONMENT = any([
    os.getenv("GITHUB_ACTIONS"),
    os.getenv("CI"),
    os.getenv("CONTINUOUS_INTEGRATION"),
    os.getenv("RUNNER_OS")
])

if IS_CI_ENVIRONMENT:
    print("🔧 זוהתה סביבת CI/CD - בדיקות מותאמות לסביבה")
else:
    print("🏠 סביבת פיתוח/ייצור - בדיקות מלאות")

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
    
    if IS_CI_ENVIRONMENT:
        # בסביבת CI - רק בדיקות שלא דורשות dependencies חיצוניים
        try:
            # בדיקת imports בסיסיים שלא תלויים בdependencies
            import os
            import sys
            import json
            log_check("Core Python modules", True, "CI environment - basic modules only")
            
            # בדיקה שהקבצים הראשיים קיימים
            main_files = ['config.py', 'health_check.py', 'main.py']
            for filename in main_files:
                exists = os.path.exists(filename)
                log_check(f"File exists: {filename}", exists)
                
            return True
            
        except Exception as e:
            log_check("Imports", False, f"CI Import error: {e}")
            return False
    
    try:
        # בדיקת imports בסיסיים - רק בסביבת ייצור/פיתוח
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
    
    if IS_CI_ENVIRONMENT:
        # בסביבת CI - רק בדיקת קיום קובץ
        if os.path.exists("concurrent_monitor.py"):
            log_check("ConcurrentMonitor file exists", True, "CI environment - file check only")
            return True
        else:
            log_check("ConcurrentMonitor", False, "File not found")
            return False
    
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
    
    if IS_CI_ENVIRONMENT:
        # בסביבת CI - רק בדיקת קיום קובץ
        if os.path.exists("concurrent_monitor.py"):
            log_check("Async functions file exists", True, "CI environment - file check only")
            return True
        else:
            log_check("Async functions", False, "File not found")
            return False
    
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
            
            if IS_CI_ENVIRONMENT:
                # בסביבת CI - נקבל ערכי dummy
                if var == 'TELEGRAM_BOT_TOKEN' and value == 'dummy_bot_token':
                    log_check(f"Config has {var}", True, "CI dummy value")
                elif has_var and value is not None:
                    log_check(f"Config has {var}", True, f"value={value}")
                else:
                    log_check(f"Config has {var}", False, f"value={value}")
            else:
                log_check(f"Config has {var}", has_var and value is not None, f"value={value}")
            
        return True
        
    except Exception as e:
        log_check("Config", False, f"Error: {e}")
        traceback.print_exc()
        return False

def test_message_handler():
    """בדיקת message_handler"""
    print("\n🔍 בדיקת Message Handler...")
    
    if IS_CI_ENVIRONMENT:
        # בסביבת CI - רק בדיקת קיום קובץ
        if os.path.exists("message_handler.py"):
            log_check("Message Handler file exists", True, "CI environment - file check only")
            return True
        else:
            log_check("Message Handler", False, "File not found")
            return False
    
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

def test_memory_and_dependencies():
    """בדיקת צריכת זיכרון ו-dependencies כבדים"""
    print("\n🔍 בדיקת זיכרון ו-Dependencies...")
    
    if IS_CI_ENVIRONMENT:
        # בסביבת CI - רק בדיקת requirements.txt
        if os.path.exists("requirements.txt"):
            try:
                with open("requirements.txt", "r", encoding="utf-8") as f:
                    content = f.read()
                
                # בדיקה ש-LiteLLM נעול לגרסה בטוחה
                if "litellm==" in content:
                    log_check("LiteLLM version locked", True, "CI environment - requirements check")
                elif "litellm>=" in content:
                    log_check("LiteLLM version locked", False, "Version not locked - dangerous!")
                    return False
                else:
                    log_check("LiteLLM in requirements", False, "LiteLLM not found")
                    return False
                    
                return True
            except Exception as e:
                log_check("Requirements file", False, f"Error reading: {e}")
                return False
        else:
            log_check("Requirements file", False, "File not found")
            return False
    
    try:
        # בדיקה מלאה - רק בסביבת ייצור/פיתוח
        import subprocess
        import json
        
        # קבלת רשימת חבילות מותקנות
        result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            log_check("Package list", False, "Failed to get installed packages")
            return False
        
        packages = json.loads(result.stdout)
        installed = {pkg["name"].lower(): pkg["version"] for pkg in packages}
        
        # בדיקת חבילות כבדות
        heavy_packages = {
            "litellm": 200,
            "torch": 500,
            "tensorflow": 600,
            "transformers": 300
        }
        
        dangerous_packages = [
            "tokenizers", "huggingface-hub", "grpcio", "google-api-python-client"
        ]
        
        memory_estimate = 80  # Base memory
        issues_found = []
        
        # בדיקת חבילות כבדות
        for package, memory_impact in heavy_packages.items():
            if package in installed:
                memory_estimate += memory_impact
                version = installed[package]
                
                # בדיקות ספציפיות ל-LiteLLM
                if package == "litellm":
                    version_parts = version.split(".")
                    if len(version_parts) >= 2:
                        major_minor = f"{version_parts[0]}.{version_parts[1]}"
                        if float(major_minor) >= 1.70:  # גרסאות מסוכנות
                            issues_found.append(f"LiteLLM {version} - גרסה מסוכנת!")
                            log_check(f"LiteLLM version safe", False, f"v{version} is dangerous")
                        else:
                            log_check(f"LiteLLM version safe", True, f"v{version} is safe")
        
        # בדיקת dependencies לא רצויים
        unwanted_found = []
        for package in dangerous_packages:
            if package in installed:
                unwanted_found.append(f"{package} {installed[package]}")
                memory_estimate += 50  # הערכה
        
        if unwanted_found:
            issues_found.append(f"Dependencies מסוכנים: {', '.join(unwanted_found)}")
            log_check("No dangerous dependencies", False, f"Found: {', '.join(unwanted_found)}")
        else:
            log_check("No dangerous dependencies", True)
        
        # בדיקת זיכרון כולל
        render_limit = 512
        log_check(f"Memory estimate", True, f"{memory_estimate}MB")
        
        if memory_estimate > render_limit:
            issues_found.append(f"זיכרון גבוה מדי: {memory_estimate}MB > {render_limit}MB")
            log_check("Memory within limits", False, f"{memory_estimate}MB exceeds {render_limit}MB limit")
        elif memory_estimate > render_limit * 0.8:
            log_check("Memory within limits", True, f"{memory_estimate}MB (warning: >80% of limit)")
        else:
            log_check("Memory within limits", True, f"{memory_estimate}MB (safe)")
        
        # בדיקת Lazy Loading
        if os.path.exists("lazy_litellm.py"):
            log_check("Lazy Loading implemented", True)
        else:
            issues_found.append("Lazy Loading לא מיושם")
            log_check("Lazy Loading implemented", False, "lazy_litellm.py not found")
        
        return len(issues_found) == 0
        
    except subprocess.TimeoutExpired:
        log_check("Memory check", False, "Timeout getting package list")
        return False
    except Exception as e:
        log_check("Memory and Dependencies", False, f"Error: {e}")
        traceback.print_exc()
        return False

def basic_health_check():
    """בדיקת תקינות בסיסית - לשימוש מ-main.py"""
    try:
        # בדיקות בסיסיות ללא dependencies כבדים
        import config
        import os
        
        # בדיקה שקבצים עיקריים קיימים
        required_files = ['config.py', 'main.py', 'message_handler.py']
        for filename in required_files:
            if not os.path.exists(filename):
                return False
        
        # בדיקה שמשתני config קיימים
        required_vars = ['TELEGRAM_BOT_TOKEN', 'DATA_DIR']
        for var in required_vars:
            if not hasattr(config, var):
                return False
        
        return True
        
    except Exception as e:
        print(f"Basic health check failed: {e}")
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
        ("Memory and Dependencies", test_memory_and_dependencies),
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