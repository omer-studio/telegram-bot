#!/usr/bin/env python3
"""
🩺 Import Health Checker - מערכת לזיהוי מוקדם של בעיות import
==========================================

🎯 מטרה: למנוע מצבים שבהם פונקציות "נעלמות" ו-try/except ImportError מסתירים בעיות

🚀 הפעלה: python import_health_checker.py
"""

import importlib
import inspect
import json
import traceback
from datetime import datetime
from typing import Dict, List, Tuple, Any

class ImportHealthChecker:
    """בודק בריאות imports ופונקציות חיוניות"""
    
    # פונקציות קריטיות שחייבות להיות זמינות
    CRITICAL_FUNCTIONS = {
        "notifications": [
            "send_admin_notification_raw",
            "send_error_notification", 
            "send_admin_profile_change_notification"
        ],
        "profile_utils": [
            "send_admin_profile_notification",
            "_detect_profile_changes",
            "_send_admin_profile_overview_notification"
        ],
        "message_handler": [
            "handle_message",
            "handle_background_tasks",
            "run_background_processors"
        ],
        "config": [
            "get_config",
            "should_log_debug_prints"
        ],
        "db_manager": [
            "safe_str",
            "get_user_profile",
            "save_gpt_chat_message"
        ]
    }
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "critical_failures": [],
            "missing_functions": [],
            "import_warnings": [],
            "health_score": 0
        }
    
    def check_all_imports(self) -> Dict[str, Any]:
        """בדיקה מקיפה של כל ה-imports הקריטיים"""
        print("🩺 מתחיל בדיקת בריאות imports...")
        print("=" * 60)
        
        total_functions = 0
        working_functions = 0
        
        for module_name, functions in self.CRITICAL_FUNCTIONS.items():
            print(f"\n📦 בודק מודול: {module_name}")
            print("-" * 40)
            
            # בדיקת import של המודול
            try:
                module = importlib.import_module(module_name)
                print(f"✅ {module_name} - יובא בהצלחה")
            except ImportError as e:
                error_msg = f"❌ CRITICAL: לא ניתן לייבא {module_name}: {e}"
                print(error_msg)
                self.results["critical_failures"].append(error_msg)
                continue
            except Exception as e:
                error_msg = f"⚠️  שגיאה לא צפויה ב-{module_name}: {e}"
                print(error_msg)
                self.results["import_warnings"].append(error_msg)
                continue
            
            # בדיקת פונקציות בתוך המודול
            for func_name in functions:
                total_functions += 1
                
                if hasattr(module, func_name):
                    func = getattr(module, func_name)
                    if callable(func):
                        # בדיקת חתימת הפונקציה
                        try:
                            sig = inspect.signature(func)
                            param_count = len(sig.parameters)
                            print(f"  ✅ {func_name}() - קיימת ({param_count} פרמטרים)")
                            working_functions += 1
                        except Exception as e:
                            warning_msg = f"  ⚠️  {func_name}() - קיימת אבל בעיה בחתימה: {e}"
                            print(warning_msg)
                            self.results["import_warnings"].append(warning_msg)
                            working_functions += 1  # עדיין נחשב כעובד
                    else:
                        error_msg = f"  ❌ {func_name} - קיים אבל לא callable"
                        print(error_msg)
                        self.results["missing_functions"].append(f"{module_name}.{func_name}")
                else:
                    error_msg = f"  ❌ {func_name}() - חסרה!"
                    print(error_msg)
                    self.results["missing_functions"].append(f"{module_name}.{func_name}")
        
        # חישוב ציון בריאות
        if total_functions > 0:
            self.results["health_score"] = round((working_functions / total_functions) * 100, 1)
        
        return self.results
    
    def generate_report(self) -> str:
        """יצירת דוח מסכם"""
        print("\n" + "=" * 60)
        print("📊 דוח סיכום - בריאות Imports")
        print("=" * 60)
        
        score = self.results["health_score"]
        
        if score >= 95:
            status = "🟢 מצוין"
            emoji = "✅"
        elif score >= 80:
            status = "🟡 סביר"
            emoji = "⚠️ "
        else:
            status = "🔴 בעייתי"
            emoji = "❌"
        
        print(f"\n{emoji} **ציון בריאות כללי: {score}% ({status})**")
        
        if self.results["critical_failures"]:
            print(f"\n🚨 **שגיאות קריטיות ({len(self.results['critical_failures'])}):**")
            for failure in self.results["critical_failures"]:
                print(f"  • {failure}")
        
        if self.results["missing_functions"]:
            print(f"\n❌ **פונקציות חסרות ({len(self.results['missing_functions'])}):**")
            for missing in self.results["missing_functions"]:
                print(f"  • {missing}")
        
        if self.results["import_warnings"]:
            print(f"\n⚠️  **אזהרות ({len(self.results['import_warnings'])}):**")
            for warning in self.results["import_warnings"]:
                print(f"  • {warning}")
        
        # המלצות תיקון
        print(f"\n💡 **המלצות תיקון:**")
        if self.results["missing_functions"]:
            print("  1. הוסף את הפונקציות החסרות לקבצים המתאימים")
            print("  2. בדוק שלא נמחקו פונקציות בטעות")
        
        if self.results["critical_failures"]:
            print("  3. תקן שגיאות import קריטיות מיד!")
            print("  4. בדוק dependencies ב-requirements.txt")
        
        if score < 100:
            print("  5. הרץ שוב את הבדיקה אחרי התיקונים")
        
        # שמירה לקובץ JSON
        try:
            with open("data/import_health_report.json", "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"\n💾 דוח נשמר ב: data/import_health_report.json")
        except Exception as e:
            print(f"\n⚠️  לא ניתן לשמור דוח: {e}")
        
        return status

def main():
    """הפעלה ראשית"""
    checker = ImportHealthChecker()
    
    try:
        results = checker.check_all_imports()
        status = checker.generate_report()
        
        # החזרת exit code לפי התוצאה
        if results["health_score"] >= 95:
            exit(0)  # הכל תקין
        elif results["health_score"] >= 80:
            exit(1)  # אזהרות
        else:
            exit(2)  # שגיאות קריטיות
            
    except Exception as e:
        print(f"\n💥 שגיאה לא צפויה בבדיקת imports: {e}")
        print("\n🔧 פירוט טכני:")
        traceback.print_exc()
        exit(3)

if __name__ == "__main__":
    main() 