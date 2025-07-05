#!/usr/bin/env python3
"""
comprehensive_deploy_check.py - בדיקות מקיפות לפני deploy
מאחד את כל הבדיקות הנחוצות לקובץ אחד פשוט וברור
"""

import os
import sys
import subprocess
import json
import re
import inspect
import platform
from typing import Dict, List, Tuple

class ComprehensiveDeployChecker:
    """בודק מקיף לפני deploy - מאחד את כל הבדיקות הנחוצות"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.total_checks = 0
        
    def run_check(self, check_name: str, check_func) -> bool:
        """מריץ בדיקה אחת ומעדכן סטטיסטיקות"""
        self.total_checks += 1
        print(f"\n🔍 מבצע בדיקה: {check_name}")
        print("-" * 50)
        
        try:
            success, messages = check_func()
            if success:
                print(f"✅ {check_name} - עבר בהצלחה!")
                self.success_count += 1
                return True
            else:
                print(f"❌ {check_name} - נכשל!")
                for msg in messages:
                    if msg.startswith("❌"):
                        self.errors.append(f"{check_name}: {msg}")
                    else:
                        self.warnings.append(f"{check_name}: {msg}")
                return False
        except Exception as e:
            print(f"💥 {check_name} - שגיאה: {e}")
            self.errors.append(f"{check_name}: שגיאה בלתי צפויה - {e}")
            return False
    
    def check_gpt_a_functionality(self) -> Tuple[bool, List[str]]:
        """הבדיקה הכי חשובה - GPT-A עובד"""
        errors = []
        
        try:
            import lazy_litellm as litellm
            from gpt_a_handler import get_main_response_sync
            
            # בדיקה אמיתית של GPT-A
            test_messages = [
                {"role": "system", "content": "אתה בוט עוזר. תענה רק 'בדיקה עברה' בלי שום דבר נוסף."},
                {"role": "user", "content": "היי"}
            ]
            
            # בדיקה תואמת Windows/Linux
            if platform.system() == "Windows":
                print("🪟 Windows detected - using simple timeout")
                result = get_main_response_sync(
                    test_messages, 
                    "comprehensive_test", 
                    "comprehensive_test", 
                    False, 
                    "health_check", 
                    "comprehensive_test"
                )
            else:
                # ב-Linux נשתמש ב-SIGALRM
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("GPT-A timeout - לא הגיב תוך 30 שניות")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
                try:
                    result = get_main_response_sync(
                        test_messages, 
                        "comprehensive_test", 
                        "comprehensive_test", 
                        False, 
                        "health_check", 
                        "comprehensive_test"
                    )
                finally:
                    signal.alarm(0)
            
            if not result or not result.get("bot_reply"):
                errors.append("❌ GPT-A לא מחזיר תשובה")
                return False, errors
            
            bot_reply = result.get("bot_reply", "").strip()
            if len(bot_reply) < 3:
                errors.append(f"❌ GPT-A מחזיר תשובה קצרה מדי: '{bot_reply}'")
                return False, errors
            
            print(f"✅ GPT-A עובד! תשובה: '{bot_reply[:50]}...'")
            return True, []
            
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת GPT-A: {e}")
            return False, errors
    
    def check_syntax_and_imports(self) -> Tuple[bool, List[str]]:
        """בדיקת syntax וייבוא קבצים קריטיים"""
        errors = []
        critical_files = [
            "config.py", "bot_setup.py", "message_handler.py", 
            "gpt_a_handler.py", "notifications.py", "main.py"
        ]
        
        for filename in critical_files:
            try:
                # בדיקת syntax
                with open(filename, 'r', encoding='utf-8') as f:
                    compile(f.read(), filename, 'exec')
                print(f"✅ {filename} - syntax תקין")
                
                # בדיקת import
                module_name = filename.replace('.py', '')
                __import__(module_name)
                print(f"✅ {filename} - import מוצלח")
                
            except Exception as e:
                errors.append(f"❌ {filename} - שגיאה: {e}")
        
        return len(errors) == 0, errors
    
    def check_critical_configuration(self) -> Tuple[bool, List[str]]:
        """בדיקת הגדרות קריטיות"""
        errors = []
        
        try:
            import config
            
            critical_configs = [
                ("TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN),
                ("GPT_MODELS", config.GPT_MODELS),
                ("GPT_PARAMS", config.GPT_PARAMS),
                ("GPT_FALLBACK_MODELS", config.GPT_FALLBACK_MODELS),
            ]
            
            for name, value in critical_configs:
                if not value:
                    errors.append(f"❌ config.{name} - חסר או ריק")
                else:
                    print(f"✅ config.{name} - קיים")
            
            # בדיקה ספציפית ל-GPT-A
            if "gpt_a" not in config.GPT_MODELS:
                errors.append("❌ config.GPT_MODELS['gpt_a'] - חסר")
            else:
                print("✅ config.GPT_MODELS['gpt_a'] - קיים")
            
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת config: {e}")
        
        return len(errors) == 0, errors
    
    def check_notifications_system(self) -> Tuple[bool, List[str]]:
        """בדיקת מערכת התראות"""
        errors = []
        
        try:
            import notifications
            from notifications import send_admin_notification_raw, _load_critical_error_users
            
            # בדיקה בסיסית
            print("✅ notifications - יובא בהצלחה")
            
            # בדיקת תיקיית data
            if not os.path.exists("data"):
                os.makedirs("data", exist_ok=True)
                print("✅ תיקיית data - נוצרה")
            else:
                print("✅ תיקיית data - קיימת")
            
            # בדיקת טעינת משתמשים קריטיים
            try:
                _load_critical_error_users()
                print("✅ _load_critical_error_users - עובד")
            except Exception as e:
                errors.append(f"❌ _load_critical_error_users נכשל: {e}")
            
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת התראות: {e}")
        
        return len(errors) == 0, errors
    
    def check_unit_tests(self) -> Tuple[bool, List[str]]:
        """הרצת בדיקות unit (unittest + pytest)"""
        errors = []
        
        # בדיקה 1: unittest
        try:
            print("🔍 מריץ unittest...")
            # תיקון encoding ב-Windows
            if platform.system() == "Windows":
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                    capture_output=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=60
                )
            else:
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            
            if result.returncode == 0:
                print("✅ unittest עבר בהצלחה")
            else:
                stderr_clean = result.stderr.replace('\x9f', '?').replace('\x00', '') if result.stderr else ""
                errors.append(f"❌ unittest נכשל: {stderr_clean}")
                
        except subprocess.TimeoutExpired:
            errors.append("❌ unittest - timeout")
        except Exception as e:
            errors.append(f"❌ שגיאה בהרצת unittest: {e}")
        
        # בדיקה 2: pytest
        try:
            print("🔍 מריץ pytest...")
            # תיקון encoding ב-Windows
            if platform.system() == "Windows":
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "-v", "--tb=short"],
                    capture_output=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=60
                )
            else:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            
            if result.returncode == 0:
                print("✅ pytest עבר בהצלחה")
            else:
                errors.append(f"❌ pytest נכשל: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            errors.append("❌ pytest - timeout")
        except Exception as e:
            errors.append(f"❌ שגיאה בהרצת pytest: {e}")
        
        if not errors:
            print("✅ כל בדיקות unit עברו בהצלחה")
            return True, []
        else:
            return False, errors
    
    def check_memory_usage(self) -> Tuple[bool, List[str]]:
        """בדיקת צריכת זיכרון"""
        warnings = []
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                
                # חבילות כבדות
                heavy_packages = {
                    "litellm": 150,
                    "torch": 500,
                    "tensorflow": 600,
                    "transformers": 300
                }
                
                total_memory = 80  # base memory
                found_heavy = []
                
                for pkg in packages:
                    name = pkg["name"].lower()
                    if name in heavy_packages:
                        memory = heavy_packages[name]
                        total_memory += memory
                        found_heavy.append(f"{pkg['name']} {pkg['version']} (~{memory}MB)")
                
                print(f"📊 אומדן זיכרון: ~{total_memory}MB")
                
                if found_heavy:
                    print(f"📦 חבילות כבדות: {', '.join(found_heavy)}")
                
                # במצב Legacy - אזהרה בלבד
                if total_memory > 921:
                    warnings.append(f"⚠️ צריכת זיכרון גבוהה: {total_memory}MB (מעל 921MB)")
                
                return True, warnings
                
        except Exception as e:
            return False, [f"❌ שגיאה בבדיקת זיכרון: {e}"]
    
    def check_interface_compatibility(self) -> Tuple[bool, List[str]]:
        """בדיקת תאימות ממשקי ליבה"""
        errors = []
        
        try:
            from sheets_handler import register_user, approve_user
            
            for fn_name, fn in [("register_user", register_user), ("approve_user", approve_user)]:
                sig = inspect.signature(fn)
                
                # בדיקת פרמטרים
                if not (1 <= len(sig.parameters) <= 2):
                    errors.append(f"❌ {fn_name}: ציפיתי ל-1-2 פרמטרים, קיבלתי {len(sig.parameters)}")
                
                # בדיקת החזרת success
                src = inspect.getsource(fn)
                if not re.search(r"return\s+\{[^}]*['\"]success['\"]", src):
                    errors.append(f"❌ {fn_name}: אין 'success' בהחזרת הפונקציה")
            
            if not errors:
                print("✅ ממשקי ליבה תקינים")
            
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת תאימות: {e}")
        
        return len(errors) == 0, errors
    
    def run_all_checks(self) -> bool:
        """מריץ את כל הבדיקות"""
        print("🚀 מתחיל בדיקות מקיפות לפני deploy...")
        print("=" * 60)
        
        # רשימת כל הבדיקות בסדר חשיבות
        checks = [
            ("GPT-A עובד (הכי חשוב!)", self.check_gpt_a_functionality),
            ("Syntax וייבוא קבצים", self.check_syntax_and_imports),
            ("הגדרות קריטיות", self.check_critical_configuration),
            ("מערכת התראות", self.check_notifications_system),
            ("בדיקות Unit", self.check_unit_tests),
            ("צריכת זיכרון", self.check_memory_usage),
            ("תאימות ממשקי ליבה", self.check_interface_compatibility),
        ]
        
        # הרצת כל הבדיקות
        for check_name, check_func in checks:
            self.run_check(check_name, check_func)
        
        # הדפסת תוצאות
        print("\n" + "=" * 60)
        print("📋 תוצאות בדיקה מקיפה:")
        print("=" * 60)
        
        print(f"✅ בדיקות שעברו: {self.success_count}/{self.total_checks}")
        
        if self.errors:
            print("\n❌ שגיאות קריטיות:")
            for error in self.errors:
                print(f"   {error}")
        
        if self.warnings:
            print("\n⚠️ אזהרות:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if not self.errors:
            print(f"\n🎉 כל הבדיקות הקריטיות עברו!")
            if self.warnings:
                print("⚠️ יש אזהרות - אבל אפשר לפרוס")
            else:
                print("✅ מוכן לפריסה ללא אזהרות!")
            return True
        else:
            print(f"\n💀 יש שגיאות קריטיות - אסור לפרוס!")
            return False

def main():
    """פונקציה ראשית"""
    checker = ComprehensiveDeployChecker()
    success = checker.run_all_checks()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 הפריסה מאושרת לביצוע!")
        sys.exit(0)
    else:
        print("🚫 הפריסה נחסמה - יש לתקן את השגיאות")
        sys.exit(1)

if __name__ == "__main__":
    main() 