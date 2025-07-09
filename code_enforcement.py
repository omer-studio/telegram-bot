#!/usr/bin/env python3
"""
code_enforcement.py - מערכת אכיפה אוטומטית
מונעת שימוש לא בטוח ומוודא עקביות
"""

import re
import ast
import os
from typing import List, Dict, Any
from pathlib import Path

class CodeEnforcer:
    """מערכת אכיפה אוטומטית - מונעת שימוש לא בטוח"""
    
    def __init__(self):
        self.rules = {
            "no_direct_chat_id": {
                "pattern": r"chat_id\s*=\s*[^s]",  # לא chat_id = משהו
                "message": "❌ אסור להשתמש ב-chat_id ישירות! השתמש ב-safe_chat_id()",
                "fix": "from user_friendly_errors import safe_str; chat_id = safe_str(chat_id)"
            },
            "no_direct_user_id": {
                "pattern": r"user_id\s*=\s*[^s]",
                "message": "❌ אסור להשתמש ב-user_id ישירות! השתמש ב-safe_str()",
                "fix": "from user_friendly_errors import safe_str; user_id = safe_str(user_id)"
            },
            "no_direct_psycopg2": {
                "pattern": r"psycopg2\.connect\(",
                "message": "❌ אסור להתחבר ישירות למסד נתונים! השתמש ב-data_manager",
                "fix": "from simple_data_manager import data_manager"
            },
            "no_direct_logging": {
                "pattern": r"logging\.(info|error|warning|debug)\(",
                "message": "❌ אסור להשתמש ב-logging ישירות! השתמש ב-logger",
                "fix": "from simple_logger import logger"
            }
        }
    
    def check_file(self, file_path: str) -> List[Dict]:
        """בדיקת קובץ לפי כל הכללים"""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for rule_name, rule in self.rules.items():
                matches = re.finditer(rule["pattern"], content)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    violations.append({
                        "file": file_path,
                        "line": line_num,
                        "rule": rule_name,
                        "message": rule["message"],
                        "fix": rule["fix"],
                        "code": match.group(0)
                    })
        
        except Exception as e:
            print(f"⚠️ שגיאה בבדיקת קובץ {file_path}: {e}")
        
        return violations
    
    def check_all_files(self, directory: str = ".") -> List[Dict]:
        """בדיקת כל הקבצים בתיקייה"""
        all_violations = []
        
        for file_path in Path(directory).rglob("*.py"):
            if "venv" not in str(file_path) and "node_modules" not in str(file_path):
                violations = self.check_file(str(file_path))
                all_violations.extend(violations)
        
        return all_violations
    
    def print_violations(self, violations: List[Dict]):
        """הדפסת הפרות בצורה ידידותית"""
        if not violations:
            print("✅ אין הפרות! הקוד עקבי ובטוח")
            return
        
        print(f"🚨 נמצאו {len(violations)} הפרות:")
        print("=" * 60)
        
        for violation in violations:
            print(f"📁 קובץ: {violation['file']}")
            print(f"📍 שורה: {violation['line']}")
            print(f"❌ בעיה: {violation['message']}")
            print(f"🔧 קוד: {violation['code']}")
            print(f"💡 תיקון: {violation['fix']}")
            print("-" * 40)

def create_pre_commit_hook():
    """יצירת pre-commit hook אוטומטי"""
    hook_content = """#!/bin/bash
# Pre-commit hook - בדיקת עקביות קוד

echo "בודק עקביות קוד..."

python code_enforcement.py

if [ $? -ne 0 ]; then
    echo "נמצאו הפרות! קומיט נחסם"
    exit 1
fi

echo "קוד תקין - קומיט מאושר"
exit 0
"""
    
    hook_path = ".git/hooks/pre-commit"
    os.makedirs(os.path.dirname(hook_path), exist_ok=True)
    
    with open(hook_path, 'w', encoding='utf-8') as f:
        f.write(hook_content)
    
    os.chmod(hook_path, 0o755)
    print("✅ Pre-commit hook נוצר!")

def create_contributing_guide():
    """יצירת מדריך CONTRIBUTING"""
    guide_content = """# מדריך לתרומה לקוד

## 🚨 כללי ברזל - אל תפר!

### 1. טיפוסים בטוחים
❌ אסור:
```python
chat_id = update.message.chat_id  # לא בטוח!
user_id = user.id  # לא בטוח!
```

✅ מותר:
```python
from user_friendly_errors import safe_str
chat_id = safe_str(update.message.chat_id)
user_id = safe_str(user.id)
```

### 2. מסד נתונים
❌ אסור:
```python
import psycopg2
conn = psycopg2.connect(DB_URL)
```

✅ מותר:
```python
from simple_data_manager import data_manager
data_manager.save_chat_message(...)
```

### 3. לוגים
❌ אסור:
```python
import logging
logging.info("הודעה")
```

✅ מותר:
```python
from simple_logger import logger
logger.info("הודעה", source="module_name")
```

### 4. שגיאות
❌ אסור:
```python
raise Exception("שגיאה")
```

✅ מותר:
```python
from user_friendly_errors import UserFriendlyError
raise UserFriendlyError("הודעה ידידותית למשתמש")
```

## 🔍 בדיקות אוטומטיות
הרץ לפני כל קומיט:
```bash
python code_enforcement.py
```

## 📞 תמיכה
אם יש שאלות - פנה למפתח הראשי
"""
    
    with open("CONTRIBUTING.md", 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print("✅ מדריך CONTRIBUTING נוצר!")

if __name__ == "__main__":
    # בדיקת כל הקבצים
    enforcer = CodeEnforcer()
    violations = enforcer.check_all_files()
    
    if violations:
        enforcer.print_violations(violations)
        print("\n🚨 קומיט נחסם - יש לתקן הפרות!")
        exit(1)
    else:
        print("✅ כל הקבצים תקינים!")
        exit(0) 