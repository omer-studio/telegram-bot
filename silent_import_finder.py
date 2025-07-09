#!/usr/bin/env python3
"""
🔍 Silent Import Finder - כלי לזיהוי try/except ImportError בעייתיים
===================================================================

🎯 מטרה: למצוא את כל המקומות שבהם try/except ImportError עלולים להסתיר בעיות אמיתיות

🚀 הפעלה: python silent_import_finder.py
"""

import os
import re
import ast
import json
from typing import List, Dict, Tuple
from datetime import datetime

class SilentImportFinder:
    """מוצא try/except ImportError בעייתיים שעלולים להסתיר בעיות"""
    
    # קבצים שמותר להם להשתמש ב-try/except ImportError (CI/tests)
    ALLOWED_SILENT_IMPORTS = {
        "tests/",  # כל הקבצים בתיקיית tests
        "scripts/", # כל הקבצים בתיקיית scripts  
        "temp_files/", # קבצים זמניים
        "venv/", # Virtual environment
        "backups/", # גיבויים
        ".git/", # גיט
        "__pycache__/", # Python cache
    }
    
    # דפוסים של try/except ImportError בעייתיים
    PROBLEMATIC_PATTERNS = [
        r"except ImportError.*:\s*pass",  # except ImportError: pass
        r"except ImportError.*:\s*#.*continue", # except ImportError: # continue
        r"except ImportError.*:\s*return.*None", # except ImportError: return None
        r"except ImportError.*:\s*print", # except ImportError: print (...)
    ]
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "silent_imports_found": [],
            "critical_files": [],
            "summary": {
                "total_files_checked": 0,
                "files_with_silent_imports": 0,
                "total_silent_imports": 0
            }
        }
    
    def is_file_allowed(self, file_path: str) -> bool:
        """בודק אם הקובץ מותר להשתמש ב-silent imports"""
        for allowed_pattern in self.ALLOWED_SILENT_IMPORTS:
            if allowed_pattern in file_path.replace("\\", "/"):
                return True
        return False
    
    def find_silent_imports_in_file(self, file_path: str) -> List[Dict]:
        """מוצא silent imports בקובץ אחד"""
        silent_imports = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            # חיפוש דרך regex patterns
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                # בדיקה אם יש try/except ImportError בשורה הזו או הבאה
                if "except ImportError" in line_stripped:
                    # בדיקה של כמה שורות אחרי except
                    except_block = []
                    for j in range(i, min(i + 5, len(lines))):  # עד 5 שורות אחרי
                        if j < len(lines):
                            except_block.append(lines[j].strip())
                    
                    except_content = " ".join(except_block)
                    
                    # בדיקה אם זה silent import בעייתי
                    is_silent = False
                    problem_type = ""
                    
                    if "pass" in except_content:
                        is_silent = True
                        problem_type = "silent_pass"
                    elif "return None" in except_content or "return {}" in except_content:
                        is_silent = True
                        problem_type = "silent_return"
                    elif "print" in except_content and "fallback" in except_content.lower():
                        is_silent = True
                        problem_type = "silent_fallback"
                    elif "dummy" in except_content.lower() or "DummyModule" in except_content:
                        is_silent = True
                        problem_type = "dummy_module"
                    
                    if is_silent:
                        silent_imports.append({
                            "line_number": i,
                            "line_content": line.strip(),
                            "problem_type": problem_type,
                            "context": except_content[:200] + "..." if len(except_content) > 200 else except_content
                        })
                        
        except Exception as e:
            # לא נוסיף לרשימת שגיאות - רק נדלג על הקובץ
            pass
            
        return silent_imports
    
    def scan_all_files(self) -> None:
        """סריקת כל הקבצים בפרויקט"""
        print("🔍 מתחיל סריקת silent imports...")
        print("=" * 60)
        
        python_files = []
        
        # מציאת כל קבצי Python
        for root, dirs, files in os.walk("."):
            # דילוג על תיקיות שמותר להן לעשות silent imports
            if any(allowed in root.replace("\\", "/") for allowed in self.ALLOWED_SILENT_IMPORTS):
                continue
                
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    python_files.append(file_path)
        
        self.results["summary"]["total_files_checked"] = len(python_files)
        
        for file_path in python_files:
            if self.is_file_allowed(file_path):
                continue
                
            silent_imports = self.find_silent_imports_in_file(file_path)
            
            if silent_imports:
                self.results["summary"]["files_with_silent_imports"] += 1
                self.results["summary"]["total_silent_imports"] += len(silent_imports)
                
                file_info = {
                    "file_path": file_path.replace("\\", "/"),
                    "silent_imports": silent_imports
                }
                
                self.results["silent_imports_found"].append(file_info)
                
                # קבצים קריטיים (לא בתיקיות מיוחדות)
                if not any(folder in file_path for folder in ["temp_", "test_", "backup_"]):
                    self.results["critical_files"].append(file_path.replace("\\", "/"))
    
    def generate_report(self) -> None:
        """יצירת דוח מפורט"""
        print("\n" + "=" * 60)
        print("📊 דוח Silent Import Errors")
        print("=" * 60)
        
        summary = self.results["summary"]
        
        print(f"\n📈 **סטטיסטיקות:**")
        print(f"  • קבצים שנבדקו: {summary['total_files_checked']}")
        print(f"  • קבצים עם silent imports: {summary['files_with_silent_imports']}")
        print(f"  • סה״כ silent imports: {summary['total_silent_imports']}")
        
        if self.results["critical_files"]:
            print(f"\n🚨 **קבצים קריטיים עם בעיות ({len(self.results['critical_files'])}):**")
            for critical_file in self.results["critical_files"]:
                print(f"  • {critical_file}")
        
        if self.results["silent_imports_found"]:
            print(f"\n🔍 **פירוט בעיות:**")
            
            for file_info in self.results["silent_imports_found"]:
                print(f"\n📁 {file_info['file_path']}")
                print("-" * 40)
                
                for import_issue in file_info["silent_imports"]:
                    line_num = import_issue["line_number"]
                    problem_type = import_issue["problem_type"]
                    line_content = import_issue["line_content"]
                    
                    # אימוג'י לפי סוג הבעיה
                    if problem_type == "silent_pass":
                        emoji = "🤐"
                        desc = "Silent Pass"
                    elif problem_type == "silent_return":
                        emoji = "🔄"
                        desc = "Silent Return"
                    elif problem_type == "silent_fallback":
                        emoji = "⚠️"
                        desc = "Silent Fallback"
                    elif problem_type == "dummy_module":
                        emoji = "🎭"
                        desc = "Dummy Module"
                    else:
                        emoji = "❓"
                        desc = "Unknown"
                    
                    print(f"  {emoji} שורה {line_num}: {desc}")
                    print(f"      {line_content}")
        
        # המלצות תיקון
        if self.results["silent_imports_found"]:
            print(f"\n💡 **המלצות תיקון:**")
            print("  1. החלף silent imports במנגנון לוגינג מפורש")
            print("  2. השתמש בהודעות שגיאה ברורות במקום pass")
            print("  3. הוסף בדיקות CI שימנעו silent imports חדשים")
            print("  4. העבר fallbacks למקום מרכזי במקום פיזור בקוד")
        
        # שמירה לקובץ
        try:
            with open("data/silent_imports_report.json", "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"\n💾 דוח נשמר ב: data/silent_imports_report.json")
        except Exception as e:
            print(f"\n⚠️ לא ניתן לשמור דוח: {e}")

def main():
    """הפעלה ראשית"""
    finder = SilentImportFinder()
    
    try:
        finder.scan_all_files()
        finder.generate_report()
        
        # החזרת exit code
        if finder.results["summary"]["total_silent_imports"] == 0:
            print("\n✅ לא נמצאו silent imports בעייתיים!")
            exit(0)
        elif len(finder.results["critical_files"]) == 0:
            print("\n⚠️ נמצאו silent imports, אבל לא בקבצים קריטיים")
            exit(1)
        else:
            print(f"\n❌ נמצאו {len(finder.results['critical_files'])} קבצים קריטיים עם בעיות!")
            exit(2)
            
    except Exception as e:
        print(f"\n💥 שגיאה לא צפויה: {e}")
        import traceback
        traceback.print_exc()
        exit(3)

if __name__ == "__main__":
    main() 