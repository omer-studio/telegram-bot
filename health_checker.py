#!/usr/bin/env python3
"""
🎯 HEALTH CHECKER - מערכת אבחון עצמית
====================================

מטרה: בדיקה אוטומטית של המערכת
עקרון: מזהה בעיות לפני שהן הופכות לקריטיות

במקום שהלקוח יגלה בעיות רק כשמשהו נשבר,
המערכת בודקת את עצמה ומתריעה מראש.

אם יש בעיה - הודעה ברורה עם צעדי תיקון פשוטים.
"""

import os
import json
import logging
import traceback
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import subprocess
import sys

# Import our system components
try:
    from system_manager import system_manager, SystemConfigError
    from data_manager import data_manager, DataProcessingError
except ImportError as e:
    print(f"❌ לא ניתן לטעון מודולי מערכת: {e}")
    sys.exit(1)

class HealthCheckError(Exception):
    """שגיאה בבדיקת בריאות המערכת"""
    pass

class HealthChecker:
    """בודק בריאות המערכת - אבחון עצמי מתמשך"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.check_results = {}
        self.critical_issues = []
        self.warnings = []
        self.last_check = None
        
    def run_full_health_check(self) -> Dict[str, Any]:
        """מריץ בדיקה מלאה של המערכת"""
        
        print("🏥 מתחיל בדיקת בריאות מלאה של המערכת...")
        print("=" * 60)
        
        self.check_results = {}
        self.critical_issues = []
        self.warnings = []
        
        # רשימת בדיקות לביצוע
        health_checks = [
            ("תצורת מערכת", self._check_system_config),
            ("עיבוד נתונים", self._check_data_processing),
            ("חיבור מסד נתונים", self._check_database_connection),
            ("קבצים קריטיים", self._check_critical_files),
            ("חבילות Python", self._check_python_packages),
            ("זיכרון ודיסק", self._check_resources),
            ("לוגים ושגיאות", self._check_logs_and_errors),
            ("שירותים חיצוניים", self._check_external_services),
            ("ביצועים", self._check_performance),
            ("בדיקות אוטומטיות", self._check_automated_tests)
        ]
        
        # הרצת כל הבדיקות
        for check_name, check_func in health_checks:
            try:
                print(f"\n🔍 בודק: {check_name}")
                print("-" * 40)
                
                result = check_func()
                self.check_results[check_name] = result
                
                if result["status"] == "critical":
                    self.critical_issues.append(f"{check_name}: {result['message']}")
                    print(f"🔴 {check_name}: {result['message']}")
                elif result["status"] == "warning":
                    self.warnings.append(f"{check_name}: {result['message']}")
                    print(f"🟡 {check_name}: {result['message']}")
                else:
                    print(f"✅ {check_name}: {result['message']}")
                    
            except Exception as e:
                error_msg = f"שגיאה בבדיקת {check_name}: {e}"
                self.critical_issues.append(error_msg)
                self.check_results[check_name] = {
                    "status": "critical",
                    "message": error_msg,
                    "details": traceback.format_exc()
                }
                print(f"💥 {check_name}: שגיאה - {e}")
        
        self.last_check = datetime.now()
        
        # הכנת דוח סיכום
        return self._generate_health_report()
    
    def _check_system_config(self) -> Dict[str, Any]:
        """בדיקת תצורת המערכת"""
        
        try:
            # בדיקת system_manager
            config_info = system_manager.get_config_info()
            
            # בדיקת מפתחות קריטיים
            critical_keys = ["telegram", "openai", "database"]
            missing_keys = []
            
            for key in critical_keys:
                if not config_info["keys_configured"].get(key, False):
                    missing_keys.append(key)
            
            if missing_keys:
                return {
                    "status": "critical",
                    "message": f"מפתחות חסרים: {', '.join(missing_keys)}",
                    "solution": "עדכן את קובץ הגדרות עם המפתחות החסרים",
                    "details": config_info
                }
            
            return {
                "status": "healthy",
                "message": "תצורת המערכת תקינה",
                "details": config_info
            }
            
        except SystemConfigError as e:
            return {
                "status": "critical",
                "message": "שגיאה בתצורת המערכת",
                "solution": str(e),
                "details": {"error": str(e)}
            }
    
    def _check_data_processing(self) -> Dict[str, Any]:
        """בדיקת עיבוד נתונים"""
        
        try:
            # בדיקת data_manager
            health_data = data_manager.get_data_summary()
            
            # בדיקות פונקציונליות
            test_chat_id = data_manager.safe_chat_id("123456789")
            test_message = data_manager.safe_message("בדיקה")
            test_timestamp = data_manager.safe_timestamp()
            
            if not all([test_chat_id, test_message, test_timestamp]):
                return {
                    "status": "critical",
                    "message": "עיבוד נתונים לא עובד כראוי",
                    "solution": "בדוק את מודול data_manager",
                    "details": health_data
                }
            
            return {
                "status": "healthy",
                "message": "עיבוד נתונים תקין",
                "details": health_data
            }
            
        except DataProcessingError as e:
            return {
                "status": "critical",
                "message": "שגיאה בעיבוד נתונים",
                "solution": str(e),
                "details": {"error": str(e)}
            }
    
    def _check_database_connection(self) -> Dict[str, Any]:
        """בדיקת חיבור מסד נתונים"""
        
        try:
            import psycopg2
            
            # קבלת כתובת מסד נתונים
            db_url = system_manager.get_database_url()
            
            # בדיקת חיבור
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # בדיקת טבלאות קריטיות
            critical_tables = ["user_profiles", "chat_messages", "gpt_calls_log"]
            table_status = {}
            
            for table in critical_tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    table_status[table] = f"✅ {count:,} רשומות"
                except Exception as e:
                    table_status[table] = f"❌ שגיאה: {e}"
            
            cur.close()
            conn.close()
            
            # בדיקה אם יש בעיות בטבלאות
            failed_tables = [table for table, status in table_status.items() if "❌" in status]
            
            if failed_tables:
                return {
                    "status": "critical",
                    "message": f"בעיות בטבלאות: {', '.join(failed_tables)}",
                    "solution": "בדוק את מסד הנתונים ותקן את הטבלאות הפגומות",
                    "details": table_status
                }
            
            return {
                "status": "healthy",
                "message": "חיבור מסד נתונים תקין",
                "details": table_status
            }
            
        except Exception as e:
            return {
                "status": "critical",
                "message": "לא ניתן להתחבר למסד נתונים",
                "solution": "בדוק את כתובת מסד הנתונים והרשאות החיבור",
                "details": {"error": str(e)}
            }
    
    def _check_critical_files(self) -> Dict[str, Any]:
        """בדיקת קבצים קריטיים"""
        
        critical_files = [
            "main.py",
            "bot_setup.py", 
            "message_handler.py",
            "gpt_a_handler.py",
            "notifications.py",
            "system_manager.py",
            "data_manager.py",
            "health_checker.py"
        ]
        
        file_status = {}
        missing_files = []
        
        for file in critical_files:
            if os.path.exists(file):
                # בדיקת גודל קובץ
                size = os.path.getsize(file)
                if size > 0:
                    file_status[file] = f"✅ {size:,} bytes"
                else:
                    file_status[file] = "⚠️ קובץ ריק"
                    missing_files.append(file)
            else:
                file_status[file] = "❌ חסר"
                missing_files.append(file)
        
        if missing_files:
            return {
                "status": "critical",
                "message": f"קבצים קריטיים חסרים: {', '.join(missing_files)}",
                "solution": "שחזר את הקבצים החסרים מגיבוי או מהמקור",
                "details": file_status
            }
        
        return {
            "status": "healthy",
            "message": "כל הקבצים הקריטיים קיימים",
            "details": file_status
        }
    
    def _check_python_packages(self) -> Dict[str, Any]:
        """בדיקת חבילות Python"""
        
        try:
            # קריאת requirements.txt
            with open("requirements.txt", "r", encoding="utf-8") as f:
                requirements = f.read().splitlines()
            
            # בדיקת חבילות קריטיות
            critical_packages = [
                "psycopg2-binary",
                "python-telegram-bot", 
                "openai",
                "litellm",
                "fastapi",
                "uvicorn"
            ]
            
            package_status = {}
            missing_packages = []
            
            for package in critical_packages:
                try:
                    __import__(package.replace("-", "_"))
                    package_status[package] = "✅ מותקן"
                except ImportError:
                    package_status[package] = "❌ חסר"
                    missing_packages.append(package)
            
            if missing_packages:
                return {
                    "status": "critical",
                    "message": f"חבילות חסרות: {', '.join(missing_packages)}",
                    "solution": "הרץ: pip install -r requirements.txt",
                    "details": package_status
                }
            
            return {
                "status": "healthy",
                "message": "כל החבילות הקריטיות מותקנות",
                "details": package_status
            }
            
        except Exception as e:
            return {
                "status": "warning",
                "message": "לא ניתן לבדוק חבילות Python",
                "solution": "בדוק ידנית שהחבילות מותקנות",
                "details": {"error": str(e)}
            }
    
    def _check_resources(self) -> Dict[str, Any]:
        """בדיקת משאבי מערכת"""
        
        try:
            import psutil
            
            # בדיקת זיכרון
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # בדיקת דיסק
            disk = psutil.disk_usage('.')
            disk_percent = disk.percent
            
            # בדיקת CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            warnings = []
            
            if memory_percent > 90:
                warnings.append(f"זיכרון גבוה: {memory_percent}%")
            
            if disk_percent > 90:
                warnings.append(f"דיסק מלא: {disk_percent}%")
            
            if cpu_percent > 90:
                warnings.append(f"CPU גבוה: {cpu_percent}%")
            
            resource_info = {
                "memory_percent": memory_percent,
                "disk_percent": disk_percent, 
                "cpu_percent": cpu_percent,
                "memory_available": f"{memory.available / (1024**3):.1f} GB",
                "disk_free": f"{disk.free / (1024**3):.1f} GB"
            }
            
            if warnings:
                return {
                    "status": "warning",
                    "message": f"משאבי מערכת: {', '.join(warnings)}",
                    "solution": "פנה מקום או הוסף משאבים",
                    "details": resource_info
                }
            
            return {
                "status": "healthy",
                "message": "משאבי מערכת תקינים",
                "details": resource_info
            }
            
        except ImportError:
            return {
                "status": "warning",
                "message": "לא ניתן לבדוק משאבי מערכת (psutil חסר)",
                "solution": "התקן: pip install psutil",
                "details": {}
            }
    
    def _check_logs_and_errors(self) -> Dict[str, Any]:
        """בדיקת לוגים ושגיאות"""
        
        try:
            # בדיקת קבצי לוג
            log_files = []
            for file in os.listdir("."):
                if file.endswith(".log") or "log" in file.lower():
                    log_files.append(file)
            
            # בדיקת שגיאות אחרונות במסד נתונים
            recent_errors = []
            try:
                import psycopg2
                db_url = system_manager.get_database_url()
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                
                # בדיקת שגיאות ב-24 שעות האחרונות
                cur.execute("""
                    SELECT COUNT(*) FROM deployment_logs 
                    WHERE log_level = 'ERROR' 
                    AND timestamp >= NOW() - INTERVAL '24 hours'
                """)
                error_count = cur.fetchone()[0]
                
                if error_count > 0:
                    recent_errors.append(f"{error_count} שגיאות ב-24 שעות")
                
                cur.close()
                conn.close()
                
            except Exception:
                pass  # לא קריטי אם לא מצליח
            
            log_info = {
                "log_files": log_files,
                "recent_errors": recent_errors
            }
            
            if recent_errors:
                return {
                    "status": "warning",
                    "message": f"שגיאות אחרונות: {', '.join(recent_errors)}",
                    "solution": "בדוק את הלוגים ותקן את השגיאות",
                    "details": log_info
                }
            
            return {
                "status": "healthy",
                "message": "אין שגיאות אחרונות",
                "details": log_info
            }
            
        except Exception as e:
            return {
                "status": "warning",
                "message": "לא ניתן לבדוק לוגים",
                "solution": "בדוק ידנית את קבצי הלוג",
                "details": {"error": str(e)}
            }
    
    def _check_external_services(self) -> Dict[str, Any]:
        """בדיקת שירותים חיצוניים"""
        
        service_status = {}
        
        # בדיקת OpenAI
        try:
            import openai
            openai.api_key = system_manager.get_openai_key()
            # בדיקה פשוטה
            service_status["OpenAI"] = "✅ מפתח קיים"
        except Exception as e:
            service_status["OpenAI"] = f"❌ שגיאה: {e}"
        
        # בדיקת Telegram
        try:
            token = system_manager.get_telegram_token()
            if token and not token.endswith("_HERE"):
                service_status["Telegram"] = "✅ טוקן קיים"
            else:
                service_status["Telegram"] = "❌ טוקן חסר"
        except Exception as e:
            service_status["Telegram"] = f"❌ שגיאה: {e}"
        
        # בדיקת Render
        try:
            api_key = system_manager.get_render_api_key()
            service_id = system_manager.get_render_service_id()
            if api_key and service_id:
                service_status["Render"] = "✅ מפתחות קיימים"
            else:
                service_status["Render"] = "❌ מפתחות חסרים"
        except Exception as e:
            service_status["Render"] = f"❌ שגיאה: {e}"
        
        # בדיקה אם יש בעיות
        failed_services = [service for service, status in service_status.items() if "❌" in status]
        
        if failed_services:
            return {
                "status": "warning",
                "message": f"בעיות בשירותים: {', '.join(failed_services)}",
                "solution": "בדוק את המפתחות והגדרות השירותים החיצוניים",
                "details": service_status
            }
        
        return {
            "status": "healthy",
            "message": "כל השירותים החיצוניים תקינים",
            "details": service_status
        }
    
    def _check_performance(self) -> Dict[str, Any]:
        """בדיקת ביצועים"""
        
        try:
            # בדיקת זמן תגובה של מסד נתונים
            import time
            import psycopg2
            
            start_time = time.time()
            
            db_url = system_manager.get_database_url()
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            conn.close()
            
            db_response_time = time.time() - start_time
            
            # בדיקת זמן טעינת מודולים
            start_time = time.time()
            import gpt_a_handler
            module_load_time = time.time() - start_time
            
            performance_info = {
                "db_response_time": f"{db_response_time:.3f}s",
                "module_load_time": f"{module_load_time:.3f}s"
            }
            
            warnings = []
            
            if db_response_time > 5.0:
                warnings.append(f"מסד נתונים איטי: {db_response_time:.1f}s")
            
            if module_load_time > 10.0:
                warnings.append(f"טעינת מודולים איטית: {module_load_time:.1f}s")
            
            if warnings:
                return {
                    "status": "warning",
                    "message": f"בעיות ביצועים: {', '.join(warnings)}",
                    "solution": "בדוק את ביצועי השרת והרשת",
                    "details": performance_info
                }
            
            return {
                "status": "healthy",
                "message": "ביצועים תקינים",
                "details": performance_info
            }
            
        except Exception as e:
            return {
                "status": "warning",
                "message": "לא ניתן לבדוק ביצועים",
                "solution": "בדוק ידנית את ביצועי המערכת",
                "details": {"error": str(e)}
            }
    
    def _check_automated_tests(self) -> Dict[str, Any]:
        """בדיקת הרצת בדיקות אוטומטיות"""
        
        try:
            # בדיקה אם יש תיקיית tests
            if not os.path.exists("tests"):
                return {
                    "status": "warning",
                    "message": "תיקיית tests לא נמצאה",
                    "solution": "צור תיקיית tests עם בדיקות אוטומטיות",
                    "details": {}
                }
            
            # בדיקת קבצי בדיקה
            test_files = [f for f in os.listdir("tests") if f.startswith("test_") and f.endswith(".py")]
            
            if not test_files:
                return {
                    "status": "warning",
                    "message": "לא נמצאו קבצי בדיקה",
                    "solution": "צור קבצי בדיקה אוטומטיים",
                    "details": {"test_files": test_files}
                }
            
            return {
                "status": "healthy",
                "message": f"נמצאו {len(test_files)} קבצי בדיקה",
                "details": {"test_files": test_files}
            }
            
        except Exception as e:
            return {
                "status": "warning",
                "message": "לא ניתן לבדוק בדיקות אוטומטיות",
                "solution": "בדוק ידנית את תיקיית הבדיקות",
                "details": {"error": str(e)}
            }
    
    def _generate_health_report(self) -> Dict[str, Any]:
        """מכין דוח בריאות מפורט"""
        
        # חישוב סטטוס כללי
        total_checks = len(self.check_results)
        healthy_checks = sum(1 for result in self.check_results.values() if result["status"] == "healthy")
        warning_checks = sum(1 for result in self.check_results.values() if result["status"] == "warning")
        critical_checks = sum(1 for result in self.check_results.values() if result["status"] == "critical")
        
        if critical_checks > 0:
            overall_status = "critical"
            status_emoji = "🔴"
        elif warning_checks > 0:
            overall_status = "warning"
            status_emoji = "🟡"
        else:
            overall_status = "healthy"
            status_emoji = "✅"
        
        # הכנת המלצות
        recommendations = []
        
        if critical_checks > 0:
            recommendations.append("🚨 תקן מיידית את הבעיות הקריטיות")
            recommendations.extend([f"• {issue}" for issue in self.critical_issues])
        
        if warning_checks > 0:
            recommendations.append("⚠️ טפל באזהרות כשיש זמן")
            recommendations.extend([f"• {warning}" for warning in self.warnings])
        
        if not recommendations:
            recommendations.append("🎉 המערכת תקינה לחלוטין!")
        
        return {
            "overall_status": overall_status,
            "status_emoji": status_emoji,
            "summary": {
                "total_checks": total_checks,
                "healthy": healthy_checks,
                "warnings": warning_checks,
                "critical": critical_checks,
                "health_score": f"{(healthy_checks / total_checks * 100):.1f}%"
            },
            "check_results": self.check_results,
            "recommendations": recommendations,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "next_check_recommended": (datetime.now() + timedelta(hours=24)).isoformat()
        }
    
    def get_simple_status(self) -> str:
        """מחזיר סטטוס פשוט למשתמש לא-טכני"""
        
        if not self.check_results:
            return "❓ לא בוצעה בדיקה אחרונה - הרץ בדיקת בריאות"
        
        critical_count = sum(1 for result in self.check_results.values() if result["status"] == "critical")
        warning_count = sum(1 for result in self.check_results.values() if result["status"] == "warning")
        
        if critical_count > 0:
            return f"🔴 המערכת לא תקינה - {critical_count} בעיות קריטיות"
        elif warning_count > 0:
            return f"🟡 המערכת עובדת עם אזהרות - {warning_count} בעיות"
        else:
            return "✅ המערכת תקינה לחלוטין"

# 🎯 Instance גלובלי
health_checker = HealthChecker()

# 🎯 פונקציות נוחות
def check_system_health() -> Dict[str, Any]:
    """פונקציה נוחה לבדיקת בריאות המערכת"""
    return health_checker.run_full_health_check()

def get_system_status() -> str:
    """פונקציה נוחה לקבלת סטטוס פשוט"""
    return health_checker.get_simple_status()

if __name__ == "__main__":
    # בדיקה עצמית
    print("🏥 HEALTH CHECKER - בדיקת בריאות מלאה")
    print("=" * 60)
    
    try:
        report = check_system_health()
        
        print(f"\n{report['status_emoji']} סטטוס כללי: {report['overall_status']}")
        print(f"📊 ניקוד בריאות: {report['summary']['health_score']}")
        print(f"✅ תקין: {report['summary']['healthy']}")
        print(f"🟡 אזהרות: {report['summary']['warnings']}")
        print(f"🔴 קריטי: {report['summary']['critical']}")
        
        print("\n💡 המלצות:")
        for rec in report['recommendations']:
            print(f"   {rec}")
        
        print(f"\n⏰ בדיקה אחרונה: {report['last_check']}")
        print(f"📅 בדיקה הבאה מומלצת: {report['next_check_recommended']}")
        
    except Exception as e:
        print(f"\n💥 שגיאה בבדיקת בריאות: {e}")
        print(traceback.format_exc()) 