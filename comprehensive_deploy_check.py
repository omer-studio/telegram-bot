#!/usr/bin/env python3
"""
comprehensive_deploy_check.py - בדיקות מקיפות לפני deploy
מאחד את כל הבדיקות הנחוצות לקובץ אחד פשוט וברור
"""

import sys
import subprocess
import time
import re
import json
import platform
import os
import glob
from typing import Tuple, List
from simple_config import TimeoutConfig

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
        """בדיקת syntax וייבוא קבצים קריטיים + בדיקת בריאות מערכתית"""
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
        
        # 🆕 בדיקת בריאות imports מערכתית
        try:
            print("\n🩺 מריץ בדיקת בריאות imports מערכתית...")
            import subprocess
            result = subprocess.run(
                ["python", "import_health_checker.py"], 
                capture_output=True, 
                text=True, 
                timeout=TimeoutConfig.SUBPROCESS_TIMEOUT
            )
            
            if result.returncode == 0:
                print("✅ בדיקת בריאות imports - מושלמת (100%)")
            elif result.returncode == 1:
                print("⚠️ בדיקת בריאות imports - יש אזהרות")
                if result.stdout:
                    print("פרטים:\n" + result.stdout[-500:])  # רק 500 תווים אחרונים
            else:
                error_msg = f"❌ בדיקת בריאות imports נכשלה (exit code: {result.returncode})"
                if result.stdout:
                    error_msg += f"\nפלט: {result.stdout[-300:]}"
                if result.stderr:
                    error_msg += f"\nשגיאה: {result.stderr[-300:]}"
                errors.append(error_msg)
                
        except FileNotFoundError:
            errors.append("❌ import_health_checker.py לא נמצא - בדיקת בריאות imports דילגה")
        except subprocess.TimeoutExpired:
            errors.append("❌ בדיקת בריאות imports תקעה (timeout)")
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת בריאות imports: {e}")
        
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
            from admin_notifications import send_admin_notification_raw
            from notifications import _load_critical_error_users
            
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
                    timeout=TimeoutConfig.SUBPROCESS_TIMEOUT
                )
            else:
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=TimeoutConfig.SUBPROCESS_TIMEOUT
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
                    timeout=TimeoutConfig.SUBPROCESS_TIMEOUT_MEDIUM
                )
            else:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=TimeoutConfig.SUBPROCESS_TIMEOUT_MEDIUM
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
    
    def check_timeout_config_usage(self) -> Tuple[bool, List[str]]:
        """🕐 בדיקת שימוש ב-TimeoutConfig במקום timeouts קשיחים"""
        errors = []
        
        try:
            print("🔍 בודק timeouts קשיחים...")
            
            # רשימת קבצים לבדיקה
            python_files = glob.glob("*.py") + glob.glob("**/*.py", recursive=True)
            
            hardcoded_timeouts = []
            for file_path in python_files:
                # דילוג על קבצים מיוחדים
                if file_path.startswith("venv/") or file_path.startswith("."):
                    continue
                if file_path == "simple_config.py":  # קובץ זה מותר להגדיר timeouts
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                    # חיפוש timeout=<מספר> באמצעות regex
                    timeout_pattern = r'timeout\s*=\s*(\d+)'
                    matches = re.finditer(timeout_pattern, content)
                    
                    for match in matches:
                        timeout_value = match.group(1)
                        line_number = content[:match.start()].count('\n') + 1
                        
                        # בדיקה אם זה באמת timeout קשיח ולא TimeoutConfig
                        line_content = lines[line_number - 1].strip()
                        
                        # אם השורה מכילה TimeoutConfig - זה בסדר
                        if "TimeoutConfig" in line_content:
                            continue
                        
                        # אם זה timeout קשיח - דיווח על זה
                        hardcoded_timeouts.append({
                            "file": file_path,
                            "line": line_number,
                            "timeout": timeout_value,
                            "context": line_content
                        })
                        
                except Exception as e:
                    continue
            
            if hardcoded_timeouts:
                errors.append(f"❌ נמצאו {len(hardcoded_timeouts)} timeouts קשיחים:")
                for timeout in hardcoded_timeouts[:10]:  # הצג רק 10 ראשונים
                    errors.append(f"   • {timeout['file']}:{timeout['line']} - timeout={timeout['timeout']}")
                    errors.append(f"     Context: {timeout['context'][:80]}...")
                
                if len(hardcoded_timeouts) > 10:
                    errors.append(f"   ... ועוד {len(hardcoded_timeouts) - 10} timeouts")
                
                errors.append("💡 פתרון: החלף timeout=<מספר> ב-TimeoutConfig.<TYPE>_TIMEOUT")
                errors.append("   דוגמה: timeout=10 → timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT")
                
                return False, errors
            else:
                print("✅ כל הtimeouts משתמשים ב-TimeoutConfig")
                return True, []
                
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת timeouts: {e}")
            return False, errors
    
    def check_timeout_config_imports(self) -> Tuple[bool, List[str]]:
        """🔍 בדיקת ייבוא נכון של TimeoutConfig"""
        warnings = []
        
        try:
            # בדיקת ייבוא TimeoutConfig
            from simple_config import TimeoutConfig
            
            # בדיקת קיום כל הtimeouts הנדרשים
            required_timeouts = [
                "HTTP_REQUEST_TIMEOUT",
                "TELEGRAM_SEND_TIMEOUT", 
                "GPT_PROCESSING_TIMEOUT",
                "SUBPROCESS_TIMEOUT",
                "DATABASE_QUERY_TIMEOUT"
            ]
            
            missing_timeouts = []
            for timeout_name in required_timeouts:
                if not hasattr(TimeoutConfig, timeout_name):
                    missing_timeouts.append(timeout_name)
                else:
                    timeout_value = getattr(TimeoutConfig, timeout_name)
                    print(f"✅ {timeout_name} = {timeout_value}")
            
            if missing_timeouts:
                warnings.append(f"⚠️ TimeoutConfig חסר timeouts: {', '.join(missing_timeouts)}")
                return False, warnings
            
            print("✅ TimeoutConfig מוגדר נכון עם כל הtimeouts הנדרשים")
            return True, []
            
        except ImportError as e:
            warnings.append(f"❌ לא ניתן לייבא TimeoutConfig: {e}")
            return False, warnings
        except Exception as e:
            warnings.append(f"❌ שגיאה בבדיקת TimeoutConfig: {e}")
            return False, warnings
    
    def check_system_consistency(self) -> Tuple[bool, List[str]]:
        """🎯 בדיקת עקביות מערכתית - אין קריאות קשיחות ואין כפילויות"""
        print("🔍 מבצע בדיקה: עקביות מערכתית")
        print("-" * 50)
        
        issues = []
        
        # 1. בדיקת קריאות קשיחות ל-config.json
        print("🔍 בודק קריאות קשיחות ל-config.json...")
        
        import glob
        import re
        
        python_files = glob.glob("*.py") + glob.glob("**/*.py", recursive=True)
        
        hardcoded_config_files = []
        for file_path in python_files:
            if file_path.startswith("venv/") or file_path.startswith("."):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # חיפוש קריאות open ישירות ל-config.json
                if re.search(r"open\s*\(\s*['\"].*config\.json['\"]", content):
                    hardcoded_config_files.append(file_path)
                    
            except Exception:
                continue
        
        if hardcoded_config_files:
            issues.append(f"❌ נמצאו {len(hardcoded_config_files)} קבצים עם קריאות קשיחות ל-config.json")
            for file_path in hardcoded_config_files[:5]:  # הצג רק 5 ראשונים
                issues.append(f"   • {file_path}")
            if len(hardcoded_config_files) > 5:
                issues.append(f"   • ועוד {len(hardcoded_config_files) - 5} קבצים...")
        else:
            print("✅ אין קריאות קשיחות ל-config.json")
        
        # 2. בדיקת המרות chat_id מחוץ לפונקציה המרכזית
        print("🔍 בודק המרות chat_id לא מרכזיות...")
        
        problematic_chat_id_files = []
        for file_path in python_files:
            if file_path.startswith("venv/") or file_path.startswith("."):
                continue
            if file_path in ["db_manager.py", "user_friendly_errors.py"]:  # קבצים שמותר להם
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # חיפוש safe_str(chat_id) או int(chat_id) שלא דרך safe_str או normalize_chat_id
                if re.search(r"(?<!safe_)str\s*\(\s*chat_id\s*\)", content) or re.search(r"int\s*\(\s*chat_id\s*\)", content):
                    problematic_chat_id_files.append(file_path)
                    
            except Exception:
                continue
        
        if problematic_chat_id_files:
            issues.append(f"❌ נמצאו {len(problematic_chat_id_files)} קבצים עם המרות chat_id לא מרכזיות")
            for file_path in problematic_chat_id_files[:5]:
                issues.append(f"   • {file_path}")
            if len(problematic_chat_id_files) > 5:
                issues.append(f"   • ועוד {len(problematic_chat_id_files) - 5} קבצים...")
        else:
            print("✅ כל המרות chat_id עוברות דרך הפונקציה המרכזית")
        
        # 3. בדיקת שימוש בfields_dict
        print("🔍 בודק שימוש ב-fields_dict...")
        
        files_without_fields_dict = []
        for file_path in python_files:
            if file_path.startswith("venv/") or file_path.startswith("."):
                continue
            if file_path in ["fields_dict.py", "config.py", "comprehensive_deploy_check.py"]:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # אם הקובץ מגדיר שמות שדות קשיחים
                if re.search(r"['\"](?:name|age|chat_id|user_id)['\"]", content) and "fields_dict" not in content:
                    # בדיקה נוספת - האם זה באמת שדה של DB
                    if "SELECT" in content or "INSERT" in content or "UPDATE" in content:
                        files_without_fields_dict.append(file_path)
                    
            except Exception:
                continue
        
        if files_without_fields_dict:
            issues.append(f"⚠️  נמצאו {len(files_without_fields_dict)} קבצים שאולי צריכים להשתמש ב-fields_dict")
            for file_path in files_without_fields_dict[:3]:
                issues.append(f"   • {file_path}")
        else:
            print("✅ שימוש ב-fields_dict נראה עקבי")
        
        if issues:
            print("\n❌ נמצאו בעיות עקביות מערכתית:")
            for issue in issues:
                print(f"   {issue}")
            print("\n💡 המלצות תיקון:")
            print("   1. החלף קריאות open ישירות ב-get_config() מ-config.py")
            print("   2. החלף unsafe_str(chat_id) ב-safe_str(chat_id) או normalize_chat_id()")
            print("   3. השתמש בשמות שדות מ-fields_dict.py")
            return False, issues
        else:
            print("✅ עקביות מערכתית - עבר בהצלחה!")
            return True, []
    
    def check_timing_measurement_patterns(self) -> Tuple[bool, List[str]]:
        """
        🔍 בדיקת דפוסי מדידת זמנים שגויים
        מחפש מקומות שמודדים זמן אחרי background tasks במקום מיד אחרי תשובה למשתמש
        """
        print("🔍 מבצע בדיקה: דפוסי מדידת זמנים")
        print("--------------------------------------------------")
        
        issues = []
        
        # רשימת קבצים לבדיקה
        files_to_check = [
            "message_handler.py",
            "gpt_a_handler.py", 
            "gpt_b_handler.py",
            "gpt_c_handler.py",
            "gpt_d_handler.py",
            "concurrent_monitor.py"
        ]
        
        dangerous_patterns = [
            # מדידה אחרי background tasks
            r"await.*background.*\n.*time\.time\(\).*user.*timing",
            r"await.*process.*\n.*time\.time\(\).*response.*time",
            r"await.*save.*\n.*time\.time\(\).*user.*time",
            # מדידה כללית אחרי await calls
            r"await.*\n.*time\.time\(\).*-.*start.*time",
        ]
        
        for file_path in files_to_check:
            if not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern in dangerous_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        context = match.group(0).replace('\n', ' → ')
                        issues.append({
                            "file": file_path,
                            "line": line_num,
                            "issue": "מדידת זמן לא מדויקת",
                            "context": context[:100] + "..." if len(context) > 100 else context,
                            "fix": "מדוד זמן מיד אחרי send_to_user(), לא אחרי background tasks"
                        })
                        
            except Exception as e:
                issues.append({
                    "file": file_path,
                    "error": f"שגיאה בבדיקה: {e}"
                })
        
        # בדיקה נוספת: מציאת measure_timing שלא משתמשים בו
        good_timing_usage = 0
        for file_path in files_to_check:
            if not os.path.exists(file_path):
                continue
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if "measure_timing" in content:
                    good_timing_usage += 1
            except:
                pass
        
        if good_timing_usage == 0:
            issues.append({
                "general": "לא נמצא שימוש ב-measure_timing context manager",
                "fix": "השתמש ב-utils.measure_timing() למדידות זמן חדשות"
            })
        
        if issues:
            print("❌ נמצאו בעיות במדידת זמנים:")
            errors_list = []
            for issue in issues:
                if "file" in issue and "line" in issue:
                    print(f"   ❌ {issue['file']}:{issue['line']} - {issue['issue']}")
                    print(f"      קונטקסט: {issue['context']}")
                    print(f"      תיקון: {issue['fix']}")
                    errors_list.append(f"{issue['file']}:{issue['line']} - {issue['issue']}")
                elif "general" in issue:
                    print(f"   ⚠️  {issue['general']}")
                    print(f"      תיקון: {issue['fix']}")
                    errors_list.append(issue['general'])
                elif "error" in issue:
                    print(f"   ⚠️  {issue['file']}: {issue['error']}")
                    errors_list.append(f"{issue['file']}: {issue['error']}")
            print("💡 עיקרון זהב: מדוד זמן מיד אחרי שליחה למשתמש, לא אחרי background tasks!")
            return False, errors_list
        else:
            print("✅ דפוסי מדידת זמנים תקינים")
            return True, []
    
    def check_backup_and_protection_systems(self) -> Tuple[bool, List[str]]:
        """🛡️ בדיקת מערכת הגיבוי והגנה על המסד נתונים"""
        print("🔍 מבצע בדיקה: מערכת הגיבוי והגנה על המסד נתונים")
        print("--------------------------------------------------")
        
        errors = []
        warnings = []
        
        # 1. בדיקת קיום קבצי מערכת הגיבוי
        print("🔍 בודק קיום קבצי מערכת הגיבוי...")
        backup_files = [
            "daily_backup.py",
            "data_integrity_monitor.py", 
            "setup_database_protection.py"
        ]
        
        for file_path in backup_files:
            if not os.path.exists(file_path):
                errors.append(f"❌ קובץ {file_path} לא קיים")
            else:
                print(f"✅ {file_path} קיים")
        
        # 2. בדיקת אם מערכת הגיבוי פועלת
        print("\n🔍 בודק פונקציונליות מערכת הגיבוי...")
        try:
            from daily_backup import run_daily_backup
            from data_integrity_monitor import run_full_integrity_check
            
            print("✅ מודולי הגיבוי מייבאים בהצלחה")
            
            # בדיקה בסיסית של פונקציונליות
            if not callable(run_daily_backup):
                errors.append("❌ run_daily_backup לא ניתן לקריאה")
            
            if not callable(run_full_integrity_check):
                errors.append("❌ run_full_integrity_check לא ניתן לקריאה")
            
        except ImportError as e:
            errors.append(f"❌ שגיאה בייבוא מודולי הגיבוי: {e}")
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת מערכת הגיבוי: {e}")
        
        # 3. בדיקת תיקיית גיבויים
        print("\n🔍 בודק תיקיית גיבויים...")
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            warnings.append(f"⚠️ תיקיית גיבויים {backup_dir} לא קיימת")
        else:
            print(f"✅ תיקיית גיבויים {backup_dir} קיימת")
            
            # בדיקה אם יש גיבויים קיימים
            import glob
            existing_backups = glob.glob(f"{backup_dir}/*")
            if existing_backups:
                print(f"✅ נמצאו {len(existing_backups)} קבצי גיבוי קיימים")
            else:
                warnings.append("⚠️ אין גיבויים קיימים בתיקיית הגיבויים")
        
        # 4. בדיקת הגנה על מסד הנתונים
        print("\n🔍 בודק מערכת הגנה על מסד הנתונים...")
        try:
            from setup_database_protection import test_protection_system
            
            print("✅ מודול הגנה על מסד הנתונים מייבא בהצלחה")
            
            # בדיקה קצרה של הגנה
            if not callable(test_protection_system):
                errors.append("❌ test_protection_system לא ניתן לקריאה")
            
        except ImportError as e:
            errors.append(f"❌ שגיאה בייבוא מודול הגנה: {e}")
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת הגנה: {e}")
        
        # 5. בדיקת מערכת הגיבוי המסודר החדשה
        print("\n🔍 בודק מערכת הגיבוי המסודר...")
        try:
            from organized_backup_system import run_organized_backup, list_organized_backups
            from schedule_internal_backup import run_backup_scheduler_background
            
            print("✅ מודולי הגיבוי המסודר מייבאים בהצלחה")
            
            # בדיקה בסיסית של פונקציונליות
            if not callable(run_organized_backup):
                errors.append("❌ run_organized_backup לא ניתן לקריאה")
            
            if not callable(run_backup_scheduler_background):
                errors.append("❌ run_backup_scheduler_background לא ניתן לקריאה")
            
        except ImportError as e:
            errors.append(f"❌ שגיאה בייבוא מודולי הגיבוי המסודר: {e}")
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת מערכת הגיבוי המסודר: {e}")
        
        # 6. בדיקת חיבור למסד הנתונים לגיבוי
        print("\n🔍 בודק חיבור למסד הנתונים לגיבוי...")
        try:
            from config import config
            db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
            
            if not db_url:
                errors.append("❌ לא נמצא URL למסד הנתונים לגיבוי")
            else:
                print("✅ URL למסד הנתונים קיים")
                
                # בדיקה בסיסית של חיבור
                import psycopg2
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    
                    # בדיקת טבלאות קריטיות
                    critical_tables = ["user_profiles", "chat_messages", "gpt_calls_log"]
                    for table in critical_tables:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cur.fetchone()[0]
                        print(f"✅ טבלה {table}: {count} רשומות")
                    
                    # בדיקת קבצי גיבוי מסודרים
                    backup_root = "backups/organized_backups"
                    if os.path.exists(backup_root):
                        backup_folders = [f for f in os.listdir(backup_root) if os.path.isdir(os.path.join(backup_root, f))]
                        if backup_folders:
                            print(f"✅ נמצאו {len(backup_folders)} תיקיות גיבוי מסודרות")
                            for folder in backup_folders[:3]:
                                print(f"   📁 {folder}/")
                        else:
                            warnings.append("⚠️ אין תיקיות גיבוי מסודרות - מערכת הגיבוי המסודר עדיין לא רצה")
                    else:
                        warnings.append("⚠️ תיקיית גיבוי מסודר לא קיימת - מערכת הגיבוי המסודר עדיין לא רצה")
                    
                    cur.close()
                    conn.close()
                    
                except Exception as e:
                    errors.append(f"❌ שגיאה בחיבור למסד הנתונים לגיבוי: {e}")
                    
        except Exception as e:
            errors.append(f"❌ שגיאה בבדיקת חיבור למסד הנתונים: {e}")
        
        # הכנת התוצאות
        all_issues = errors + warnings
        
        if errors:
            print("\n❌ נמצאו שגיאות במערכת הגיבוי והגנה:")
            for error in errors:
                print(f"   {error}")
            return False, all_issues
        elif warnings:
            print("\n⚠️ נמצאו אזהרות במערכת הגיבוי והגנה:")
            for warning in warnings:
                print(f"   {warning}")
            print("✅ מערכת הגיבוי והגנה פועלת עם אזהרות")
            return True, all_issues
        else:
            print("\n✅ מערכת הגיבוי והגנה פועלת בהצלחה!")
            return True, []
    
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
            ("מערכת הגיבוי והגנה", self.check_backup_and_protection_systems),
            ("סנכרון חתימות פונקציות", self.check_function_signatures),
            ("בדיקות Unit", self.check_unit_tests),
            ("צריכת זיכרון", self.check_memory_usage),
            ("תאימות ממשקי ליבה", self.check_interface_compatibility),
            ("רישום לוגים במסד נתונים", self.check_database_logging),
            ("מערכת Concurrent Handling", self.check_concurrent_system),
            ("שלמות requirements.txt", self.check_requirements_completeness),
            ("עקביות מערכתית", self.check_system_consistency),
            ("TimeoutConfig קשיחים", self.check_timeout_config_usage),
            ("TimeoutConfig ייבוא", self.check_timeout_config_imports),
            ("דפוסי מדידת זמנים", self.check_timing_measurement_patterns),
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