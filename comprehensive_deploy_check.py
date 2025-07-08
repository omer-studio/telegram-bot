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
import time
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
    
    def check_function_signatures(self) -> Tuple[bool, List[str]]:
        """בדיקת סנכרון חתימות פונקציות"""
        errors = []
        
        try:
            from tests.test_function_signature_sync import test_function_signatures
            test_function_signatures()
            print("✅ סנכרון חתימות פונקציות - תקין")
            return True, []
        except Exception as e:
            errors.append(f"❌ בעיה בסנכרון חתימות פונקציות: {e}")
            return False, errors

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
                    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                    capture_output=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=30
                )
            else:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=30
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
    
    def check_requirements_completeness(self) -> Tuple[bool, List[str]]:
        """בדיקת שלמות requirements.txt - וידוא שכל החבילות הנדרשות קיימות"""
        errors = []
        
        try:
            # קריאת requirements.txt
            with open('requirements.txt', 'r', encoding='utf-8') as f:
                requirements_content = f.read()
            
            # חבילות קריטיות שחייבות להיות ב-requirements.txt
            critical_packages = [
                'psycopg2-binary',  # 🔧 נדרש לחיבור PostgreSQL
                'python-telegram-bot',  # נדרש לבוט
                'openai',  # נדרש ל-GPT
                'litellm',  # נדרש ל-LiteLLM
                'gspread',  # נדרש לגיליונות Google
                'fastapi',  # נדרש לשרת
                'uvicorn',  # נדרש לשרת
                'python-dotenv',  # נדרש להגדרות
                'requests',  # נדרש לבקשות HTTP
                'Flask',  # נדרש לשרת
                'psutil',  # נדרש לניטור מערכת
                'APScheduler',  # נדרש לתזמון
                'pytz',  # נדרש לזמן
                'pytest',  # נדרש לבדיקות
                'pyluach',  # נדרש ללוח עברי
                'python-dateutil',  # נדרש לעיבוד תאריכים
                'asyncio',  # נדרש לאסינכרוניות
                'anthropic',  # נדרש ל-Anthropic
                'google-generativeai',  # נדרש ל-Gemini
            ]
            
            missing_packages = []
            for package in critical_packages:
                # בדיקה אם החבילה קיימת ב-requirements.txt
                if package not in requirements_content:
                    missing_packages.append(package)
                else:
                    print(f"✅ {package} - קיים ב-requirements.txt")
            
            if missing_packages:
                errors.append(f"❌ חבילות חסרות ב-requirements.txt: {', '.join(missing_packages)}")
                return False, errors
            
            print(f"✅ כל {len(critical_packages)} החבילות הקריטיות קיימות ב-requirements.txt")
            
            # בדיקה נוספת - וידוא שהקובץ לא מכיל שגיאות syntax
            lines = requirements_content.split('\n')
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line and not line.startswith('#') and '==' not in line and '>=' not in line and '<=' not in line:
                    if not re.match(r'^[a-zA-Z0-9_-]+(\[.*\])?$', line):
                        errors.append(f"❌ שורה {i}: פורמט לא תקין - '{line}'")
            
            if errors:
                return False, errors
            
            print("✅ פורמט requirements.txt תקין")
            return True, []
            
        except FileNotFoundError:
            errors.append("❌ קובץ requirements.txt לא נמצא")
            return False, errors
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת requirements.txt: {e}")
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
            else:
                return False, [f"❌ שגיאה בהרצת pip list: {result.stderr}"]
                
        except Exception as e:
            return False, [f"❌ שגיאה בבדיקת זיכרון: {e}"]
    
    def check_interface_compatibility(self) -> Tuple[bool, List[str]]:
        """בדיקת תאימות ממשקי ליבה - כעת במסד נתונים"""
        errors = []
        
        try:
            # בדיקת פונקציות ליבה במסד הנתונים
            from profile_utils import get_user_summary_fast, update_user_profile_fast
            from db_wrapper import reset_gpt_c_run_count_wrapper
            
            # בדיקת פונקציות קיימות
            if not callable(get_user_summary_fast):
                errors.append("❌ get_user_summary_fast לא ניתן לקריאה")
            
            if not callable(update_user_profile_fast):
                errors.append("❌ update_user_profile_fast לא ניתן לקריאה")
                
            if not callable(reset_gpt_c_run_count_wrapper):
                errors.append("❌ reset_gpt_c_run_count_wrapper לא ניתן לקריאה")
            
            if not errors:
                print("✅ ממשקי ליבה תקינים")
            
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת תאימות: {e}")
        
        return len(errors) == 0, errors

    def check_database_logging(self) -> Tuple[bool, List[str]]:
        """בדיקת רישום לוגים במסד הנתונים (עבר מגיליונות לDB)"""
        errors = []
        
        try:
            from config import config
            import psycopg2
            
            # בדיקת חיבור למסד הנתונים
            print("🔍 בודק חיבור למסד הנתונים...")
            db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
            if not db_url:
                errors.append("❌ לא נמצא URL למסד הנתונים")
                return False, errors
            
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # בדיקת טבלת chat_messages
            print("🔍 בודק טבלת chat_messages...")
            cur.execute("SELECT COUNT(*) FROM chat_messages")
            message_count = cur.fetchone()[0]
            
            if message_count < 1:
                errors.append("❌ טבלת chat_messages ריקה")
                return False, errors
            
            print(f"✅ טבלת chat_messages מכילה {message_count} הודעות")
            
            # בדיקת טבלת gpt_calls_log
            print("🔍 בודק טבלת gpt_calls_log...")
            cur.execute("SELECT COUNT(*) FROM gpt_calls_log")
            gpt_calls_count = cur.fetchone()[0]
            
            print(f"✅ טבלת gpt_calls_log מכילה {gpt_calls_count} קריאות GPT")
            
            # בדיקת טבלת user_profiles
            print("🔍 בודק טבלת user_profiles...")
            cur.execute("SELECT COUNT(*) FROM user_profiles")
            profiles_count = cur.fetchone()[0]
            
            if profiles_count < 1:
                errors.append("❌ טבלת user_profiles ריקה")
                return False, errors
            
            print(f"✅ טבלת user_profiles מכילה {profiles_count} פרופילים")
            
            # בדיקת הודעות אחרונות
            print("🔍 בודק הודעות אחרונות...")
            cur.execute("""
                SELECT COUNT(DISTINCT chat_id) 
                FROM chat_messages 
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            active_users = cur.fetchone()[0]
            
            print(f"✅ משתמשים פעילים בשבוע האחרון: {active_users}")
            
            cur.close()
            conn.close()
            
            return True, []
            
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת מסד נתונים: {e}")
            return False, errors
    
    def check_concurrent_system(self) -> Tuple[bool, List[str]]:
        """בדיקת מערכת Concurrent Handling"""
        errors = []
        
        try:
            import concurrent_monitor
            from concurrent_monitor import get_concurrent_monitor, start_monitoring_user, end_monitoring_user
            
            print("✅ concurrent_monitor - יובא בהצלחה")
            
            # בדיקת יצירת monitor
            monitor = get_concurrent_monitor()
            if not monitor:
                errors.append("❌ get_concurrent_monitor - לא מחזיר monitor")
                return False, errors
            
            print("✅ get_concurrent_monitor - עובד")
            
            # בדיקת הגדרות timeout
            from concurrent_monitor import UserSession
            test_session = UserSession(
                chat_id="test_123",
                start_time=time.time(),
                message_id="test_msg",
                stage="test",
                queue_position=1
            )
            
            if test_session.max_allowed_time != 50.0:
                errors.append(f"❌ timeout לא נכון: {test_session.max_allowed_time} (צריך להיות 50.0)")
            else:
                print("✅ timeout מוגדר נכון: 50.0 שניות")
            
            # בדיקת is_timeout
            if test_session.is_timeout():
                errors.append("❌ is_timeout מחזיר True לסשן חדש")
            else:
                print("✅ is_timeout עובד נכון לסשן חדש")
            
            # בדיקת סשן ישן (timeout)
            old_session = UserSession(
                chat_id="old_test",
                start_time=time.time() - 50,  # 50 שניות אחורה
                message_id="old_msg",
                stage="old",
                queue_position=1
            )
            
            if not old_session.is_timeout():
                errors.append("❌ is_timeout לא מזהה סשן ישן")
            else:
                print("✅ is_timeout מזהה סשן ישן נכון")
            
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת Concurrent: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
        
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
            ("סנכרון חתימות פונקציות", self.check_function_signatures),
            ("בדיקות Unit", self.check_unit_tests),
            ("צריכת זיכרון", self.check_memory_usage),
            ("תאימות ממשקי ליבה", self.check_interface_compatibility),
            ("רישום לוגים במסד נתונים", self.check_database_logging),
            ("מערכת Concurrent Handling", self.check_concurrent_system),
            ("שלמות requirements.txt", self.check_requirements_completeness),
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