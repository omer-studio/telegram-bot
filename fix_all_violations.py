#!/usr/bin/env python3
"""
🔧 תיקון מערכתי פשוט
מתקן את כל הhardcode paths וimports לא נכונים
"""

import os
import re

# רשימת הקבצים שצריכים תיקון config
CONFIG_FILES = [
    "search_live_debug.py",
    "search_debug_in_deployment_logs.py", 
    "search_correct_code.py",
    "fetch_render_service_logs.py",
    "export_chat_history_5676571979.py",
    "check_table_structure.py",
    "check_render_logs_db.py",
    "check_render_api.py", 
    "check_debug_db.py",
    "check_code_direct.py"
]

# רשימת הקבצים שצריכים תיקון import
IMPORT_FILES = [
    "utils.py",
    "simple_logger.py",
    "simple_data_manager.py",
    "profile_utils.py",
    "message_handler.py",
    "notifications.py",
    "gpt_e_handler.py",
    "gpt_c_handler.py", 
    "gpt_d_handler.py",
    "gpt_b_handler.py",
    "gpt_a_handler.py",
    "deployment_check.py"
]

def fix_config_file(filepath):
    """תיקון קובץ עם hardcode config path"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # החלפת קריאה ישירה בget_config
        old_pattern = r"with open\('etc/secrets/config\.json'[^}]*\) as f:\s*\n\s*config = json\.load\(f\)"
        new_code = "from config import get_config\n    config = get_config()"
        
        if "with open('etc/secrets/config.json'" in content:
            # תיקון פשוט יותר
            content = content.replace(
                "with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:\n        config = json.load(f)",
                "from config import get_config\n    config = get_config()"
            )
            content = content.replace(
                "with open('etc/secrets/config.json', encoding='utf-8') as f:\n    config = json.load(f)",
                "from config import get_config\n    config = get_config()"
            )
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ {filepath}")
            return True
    except Exception as e:
        print(f"❌ {filepath}: {e}")
        return False

def fix_import_file(filepath):
    """תיקון קובץ עם import לא נכון"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # החלפת import
        if "from user_friendly_errors import safe_str" in content:
            content = content.replace(
                "from user_friendly_errors import safe_str",
                "from db_manager import safe_str"
            )
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ {filepath}")
            return True
    except Exception as e:
        print(f"❌ {filepath}: {e}")
        return False

def main():
    """תיקון מערכתי"""
    print("🔧 מתקן config paths...")
    config_fixed = 0
    for file in CONFIG_FILES:
        if os.path.exists(file) and fix_config_file(file):
            config_fixed += 1
    
    print(f"\n🔧 מתקן imports...")
    import_fixed = 0
    for file in IMPORT_FILES:
        if os.path.exists(file) and fix_import_file(file):
            import_fixed += 1
    
    print(f"\n📊 תוצאות:")
    print(f"✅ Config paths: {config_fixed}/{len(CONFIG_FILES)}")
    print(f"✅ Imports: {import_fixed}/{len(IMPORT_FILES)}")
    
    if config_fixed == len(CONFIG_FILES) and import_fixed == len(IMPORT_FILES):
        print("🎉 הכל תוקן!")
        return True
    else:
        print("⚠️ יש קבצים שלא תוקנו")
        return False

if __name__ == "__main__":
    main() 