#!/usr/bin/env python3
"""
auth_monitor.py
===============
🚨 מוניטור מיידי לבעיות הרשאות ואבטחה

סקריפט זה רץ כל הזמן וצופה אחרי:
1. בעיות הרשאות (משתמשים מאושרים שלא מזוהים)
2. סטטוסים לא צפויים
3. שגיאות בקוד האוטוריזציה
4. הודעות שגויות למשתמשים מאושרים

השימוש:
python auth_monitor.py --once   # בדיקה חד-פעמית
python auth_monitor.py          # מוניטור מתמשך
"""

import os
import re
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Set
import subprocess
from simple_logger import logger

class AuthorizationMonitor:
    """מוניטור הרשאות בזמן אמת"""
    
    def __init__(self):
        self.issues_found = []
        self.last_check = datetime.now()
        self.alert_threshold = 3  # מספר בעיות שמפעיל התראה
        
    def check_message_handler_integrity(self) -> List[str]:
        """בדיקת תקינות קובץ message_handler.py"""
        issues = []
        
        try:
            with open('message_handler.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # בדיקות קריטיות
            required_patterns = [
                (r'elif status == "approved":', "בדיקה מפורשת למשתמש מאושר"),
                (r'else:', "טיפול בסטטוס לא צפוי"),
                (r'handle_unregistered_user_background', "קריאה לטיפול במשתמש לא רשום"),
                (r'משתמש מאושר מזוהה', "לוג לזיהוי משתמש מאושר"),
                (r'\[AUTH_CHECK\]', "לוגים מפורטים לאוטוריזציה")
            ]
            
            for pattern, description in required_patterns:
                if not re.search(pattern, content):
                    issues.append(f"❌ חסר: {description}")
                    
            # בדיקת מבנה תקין
            if_count = len(re.findall(r'if status == "not_found":', content))
            elif_pending_count = len(re.findall(r'elif status == "pending":', content))
            elif_approved_count = len(re.findall(r'elif status == "approved":', content))
            else_count = len(re.findall(r'else:', content))
            
            if if_count != 1 or elif_pending_count != 1 or elif_approved_count != 1:
                issues.append(f"❌ מבנה if-elif-else לא תקין: if={if_count}, elif_pending={elif_pending_count}, elif_approved={elif_approved_count}")
                
        except Exception as e:
            issues.append(f"❌ שגיאה בבדיקת message_handler.py: {e}")
            
        return issues
    
    def check_for_unexpected_status_logs(self) -> List[str]:
        """חיפוש לוגים של סטטוסים לא צפויים"""
        issues = []
        
        # בדיקה של לוגי הבוט (אם קיימים)
        log_files = ['auth_monitor.log', 'logs/bot.log', 'logs/error.log']
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        recent_lines = f.readlines()[-100:]  # 100 שורות אחרונות
                    
                    # חיפוש בעיות
                    for i, line in enumerate(recent_lines):
                        if 'סטטוס לא צפוי' in line:
                            issues.append(f"⚠️ נמצא לוג של סטטוס לא צפוי: {line.strip()}")
                        
                        if 'AUTH_CHECK' in line and ('error' in line.lower() or 'unknown' in line.lower()):
                            issues.append(f"⚠️ בעיה בבדיקת הרשאות: {line.strip()}")
                            
                except Exception as e:
                    issues.append(f"❌ שגיאה בקריאת {log_file}: {e}")
                    
        return issues
    
    def check_authorization_tests(self) -> List[str]:
        """הרצת בדיקות האוטוריזציה"""
        issues = []
        
        try:
            # הרצת הבדיקות המתמחות בהרשאות
            result = subprocess.run(
                ['python', '-m', 'pytest', 'tests/test_authorization_fix.py', '-v'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                issues.append(f"❌ בדיקות הרשאות נכשלו!")
                if result.stderr:
                    issues.append(f"   שגיאה: {result.stderr[:200]}...")
                if result.stdout:
                    issues.append(f"   פלט: {result.stdout[:200]}...")
            else:
                logger.info("✅ בדיקות הרשאות עברו בהצלחה")
                
        except subprocess.TimeoutExpired:
            issues.append("❌ בדיקות הרשאות - timeout")
        except Exception as e:
            issues.append(f"❌ שגיאה בהרצת בדיקות הרשאות: {e}")
            
        return issues
    
    def check_sheets_core_integrity(self) -> List[str]:
        """בדיקת תקינות sheets_core.py - 🗑️ עברנו למסד נתונים"""
        issues = []
        
        try:
            # 🗑️ עברנו למסד נתונים - sheets_core.py לא קיים יותר
            issues.append("ℹ️ sheets_core.py הוסר - עברנו למסד נתונים 100%")
            
            # במקום זה, נבדוק שהפונקציות קיימות במסד נתונים
            try:
                from db_manager import check_user_approved_status_db, approve_user_db_new, register_user_with_code_db
                issues.append("✅ פונקציות מסד נתונים זמינות")
            except ImportError as import_err:
                issues.append(f"❌ פונקציות מסד נתונים לא זמינות: {import_err}")
                
        except Exception as e:
            issues.append(f"❌ שגיאה בבדיקת מסד נתונים: {e}")
            
        return issues
    
    def run_comprehensive_check(self) -> Dict[str, List[str]]:
        """הרצת בדיקה מקיפה"""
        results = {
            'message_handler': self.check_message_handler_integrity(),
            'sheets_core': self.check_sheets_core_integrity(),
            'logs_analysis': self.check_for_unexpected_status_logs(),
            'authorization_tests': self.check_authorization_tests()
        }
        
        return results
    
    def send_alert_if_needed(self, results: Dict[str, List[str]]):
        """שליחת התראה אם יש בעיות"""
        total_issues = sum(len(issues) for issues in results.values())
        
        if total_issues >= self.alert_threshold:
            alert_msg = f"""
🚨 התראת אבטחה - בעיות הרשאות זוהו!

📊 סיכום:
- message_handler.py: {len(results['message_handler'])} בעיות
- sheets_core.py: {len(results['sheets_core'])} בעיות  
- ניתוח לוגים: {len(results['logs_analysis'])} בעיות
- בדיקות אוטומטיות: {len(results['authorization_tests'])} בעיות

🔧 פעולות מיידיות נדרשות:
1. בדוק את הקוד בקובצי message_handler.py ו-sheets_core.py
2. הרץ את הבדיקות האוטומטיות
3. תקן את הבעיות לפני deploy
4. וודא שהמשתמשים המאושרים מזוהים נכון

זמן התראה: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            print(alert_msg)
            logger.critical(alert_msg)
            
            # שמירה לקובץ התראות
            with open('auth_alerts.log', 'a', encoding='utf-8') as f:
                f.write(f"\n{alert_msg}\n" + "="*80 + "\n")
    
    def monitor_continuously(self, interval_minutes: int = 5):
        """מוניטור מתמשך"""
        print(f"🚀 מתחיל מוניטור הרשאות (בדיקה כל {interval_minutes} דקות)")
        print("❌ לעצור: Ctrl+C")
        
        try:
            while True:
                print(f"\n🔍 בדיקה מקיפה {datetime.now().strftime('%H:%M:%S')}")
                
                results = self.run_comprehensive_check()
                
                # דיווח תוצאות
                total_issues = sum(len(issues) for issues in results.values())
                if total_issues == 0:
                    print("✅ כל הבדיקות תקינות")
                else:
                    print(f"⚠️ נמצאו {total_issues} בעיות:")
                    for category, issues in results.items():
                        if issues:
                            print(f"  {category}: {len(issues)} בעיות")
                            for issue in issues[:3]:  # מציג רק 3 ראשונות
                                print(f"    {issue}")
                    
                    self.send_alert_if_needed(results)
                
                # המתנה לבדיקה הבאה
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\n👋 מוניטור הופסק על ידי המשתמש")
        except Exception as e:
            print(f"\n💥 שגיאה במוניטור: {e}")
            logger.error(f"Monitor error: {e}")


def main():
    """פונקציה ראשית"""
    monitor = AuthorizationMonitor()
    
    # אפשרויות הרצה
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # בדיקה חד-פעמית
        print("🔍 מריץ בדיקת הרשאות חד-פעמית...")
        results = monitor.run_comprehensive_check()
        
        total_issues = sum(len(issues) for issues in results.values())
        if total_issues == 0:
            print("✅ כל הבדיקות תקינות - אין בעיות הרשאה")
            sys.exit(0)
        else:
            print(f"❌ נמצאו {total_issues} בעיות הרשאה")
            for category, issues in results.items():
                if issues:
                    print(f"\n{category}:")
                    for issue in issues:
                        print(f"  {issue}")
            sys.exit(1)
    else:
        # מוניטור מתמשך
        monitor.monitor_continuously()


if __name__ == "__main__":
    main() 