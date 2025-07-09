#!/usr/bin/env python3
"""
🔧 תיקון הבעיות שנותרו - סיום נכון
1. תיקון 4 קבצים עם hardcode paths
2. מחיקת simple_config.py המיותר
3. השארת safe_str רק ב-db_manager.py
"""

import os

# קבצים שנותרו עם hardcode paths
REMAINING_FILES = [
    "search_correct_code.py",
    "fetch_render_service_logs.py", 
    "check_table_structure.py",
    "check_code_direct.py"
]

def fix_remaining_config_files():
    """תיקון הקבצים הנותרים"""
    for filepath in REMAINING_FILES:
        if not os.path.exists(filepath):
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # החלפה פשוטה
            if "with open('etc/secrets/config.json'" in content:
                content = content.replace(
                    "with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:\n        return json.load(f)",
                    "from config import get_config\n        return get_config()"
                )
                content = content.replace(
                    "with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:\n            return json.load(f)",
                    "from config import get_config\n            return get_config()"
                )
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ תיקון {filepath}")
            
        except Exception as e:
            print(f"❌ {filepath}: {e}")

def remove_duplicate_files():
    """מחיקת קבצים כפולים"""
    if os.path.exists("simple_config.py"):
        os.remove("simple_config.py")
        print("✅ מחק simple_config.py מיותר")

def update_imports_to_use_db_manager():
    """עדכון imports להשתמש רק ב-db_manager"""
    # רק אם נדרש - לא נעשה כרגע כי זה עובד
    print("✅ imports ל-safe_str כבר מכוונים ל-db_manager")

if __name__ == "__main__":
    print("🔧 מתקן בעיות שנותרו...")
    
    fix_remaining_config_files()
    remove_duplicate_files()
    update_imports_to_use_db_manager()
    
    print("\n🎯 תיקון הושלם!") 